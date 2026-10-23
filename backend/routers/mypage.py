# =============================================================
# routers/mypage.py — 마이페이지 API
# -------------------------------------------------------------
# 주소는 전부 /api/mypage/... 로 시작하고, 전부 "로그인한 사람만" 쓸 수 있음
# (Depends(get_current_user): 요청 헤더의 토큰을 확인해서 누가 보낸 요청인지 알아냄
#  → 토큰이 없거나 잘못됐으면 함수가 실행되기 전에 401 에러)
#
#  GET  /api/mypage/profile    내 프로필 + 활동 요약 (마이페이지 위쪽 카드)
#  GET  /api/mypage/documents  내가 쓴 글 목록 (마이페이지 아래쪽 목록, 글마다 단계 "초안/수정/완료" 포함)
#                              + 글마다 저장본 목록(versions): 단계 탭에서 저장본을 한 장씩 보여줄 때 씀
#                                (수정본은 글마다 최근 3개만 남기고 더 오래된 수정본은 이때 자동으로 지움)
#  PUT  /api/mypage/profile    회원정보 수정 (이름, 전화번호, 이메일)
#  PUT  /api/mypage/password   비밀번호 변경
#  POST /api/mypage/withdraw   회원 탈퇴
#  DELETE /api/mypage/documents/{id}  쓰다 만 글 지우기 (한 번도 저장 안 한 글만)
#
# ※ 프로필·글 목록을 불러올 때마다, 한 번도 저장 안 하고 하루 넘게 방치된 글은 자동으로 지움
#   (컴퓨터가 꺼지거나 브라우저가 튕겨서 프론트가 지우기 요청을 못 보낸 글 정리용)
#
# ※ 글 하나의 본문 전체는 팀원이 만든 GET /api/documents/{id}/drafts 를 그대로 씀
# =============================================================

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models
from database import get_db
from mypage_schemas import (
    MyDocumentOut,
    MyVersionOut,
    PasswordChangeRequest,
    ProfileOut,
    ProfileUpdateRequest,
    ProfileUpdateResponse,
    WithdrawRequest,
)
from auth_schemas import MessageResponse
from security import hash_password, verify_password

# 로그인 확인 함수와 이메일 인증 관련 도우미는 회원가입 API(routers/auth.py)에 이미 있으니까 그대로 가져다 씀
from routers.auth import (
    VERIFIED_VALID_MINUTES,
    as_utc,
    get_current_user,
    latest_verification,
    now_utc,
)

router = APIRouter(prefix="/api/mypage", tags=["mypage"])

# 미리보기로 보여줄 최대 글자 수
PREVIEW_LENGTH = 120

# 글 하나에 남겨 둘 수정본(두 번째 저장부터) 개수
# 더 저장하면 가장 오래된 수정본부터 지움 (첫 저장본 = 초안, 최종 저장본 = 완료는 항상 남김)
MAX_REVISIONS = 3

# 한 번도 저장 안 한 글을 이 시간이 지나면 "버려진 글"로 보고 자동으로 지움
# (지금 쓰고 있는 글이 지워지면 안 되니까 넉넉하게 하루)
ABANDONED_AFTER = timedelta(days=1)

# 글 단계 이름 (프론트 MyPage.jsx의 STAGES와 글자까지 똑같이 맞춤)
STAGE_DRAFT = "초안"  # 아직 처음 쓰는 중 (저장한 적 없거나 1번만 저장)
STAGE_REVISING = "수정"  # 2번 이상 저장 = 초안을 고쳐 쓰는 중
STAGE_DONE = "완료"  # 글쓰기 화면에서 "최종 저장"까지 끝낸 글


# ===================== 도우미 함수 =====================


def delete_document_with_thoughts(db: Session, document_id: int) -> None:
    """글 하나와 거기 딸린 "생각"(AI 초안 만들 때 저장됨)을 지움 (자식 → 부모 순서, commit은 부르는 쪽에서)"""
    db.query(models.Thought).filter(models.Thought.document_id == document_id).delete(synchronize_session=False)
    db.query(models.Document).filter(models.Document.id == document_id).delete(synchronize_session=False)


def cleanup_abandoned_documents(db: Session, user: models.User) -> None:
    """한 번도 저장 안 하고 하루 넘게 방치된 내 글을 지움
    보통은 글쓰기 화면을 떠날 때 프론트가 바로 지우지만(DELETE /documents/{id}),
    컴퓨터가 꺼지거나 브라우저가 튕기면 그 요청이 안 와서 빈 글이 남음 → 마이페이지를 열 때 여기서 정리

    지우는 조건 (셋 다 맞아야 함)
      1) 저장본(Draft)이 하나도 없음
      2) 완료된 글이 아님
      3) 마지막으로 바뀐 지 하루(ABANDONED_AFTER)가 넘음 → 지금 쓰고 있는 글은 안 지워짐
    """
    # 저장본이 하나라도 있는 글 번호들 (서브쿼리: SELECT document_id FROM drafts)
    saved_ids = db.query(models.Draft.document_id)

    candidates = (
        db.query(models.Document)
        .filter(
            models.Document.user_id == user.user_id,
            models.Document.status != "완료",
            ~models.Document.id.in_(saved_ids),  # ~ : NOT → 저장본 목록에 없는 글 = 저장 0번
        )
        .all()
    )

    # 시각 비교는 파이썬에서 함 (DB 종류마다 시간대 처리가 달라서 as_utc로 맞춘 뒤 비교)
    limit = now_utc() - ABANDONED_AFTER
    old_ids = [
        document.id
        for document in candidates
        if as_utc(document.updated_at or document.created_at) < limit
    ]
    if not old_ids:
        return

    try:
        for document_id in old_ids:
            delete_document_with_thoughts(db, document_id)
        db.commit()
    except Exception:
        # 정리에 실패해도 마이페이지는 보여야 하니까 되돌리기만 하고 넘어감 (다음에 다시 시도됨)
        db.rollback()


def build_profile(db: Session, user: models.User) -> ProfileOut:
    """DB에서 활동 요약(글 수, 완료 글 수, 도전 최고 기록)을 세어서 프로필 응답을 만듦"""

    # 내가 쓴 글 수: SELECT COUNT(*) FROM documents WHERE user_id = 나
    document_count = (
        db.query(func.count(models.Document.id))
        .filter(models.Document.user_id == user.user_id)
        .scalar()  # scalar(): 결과가 숫자 하나일 때 그 숫자만 꺼냄
    )

    # 그중 "완료" 상태인 글 수
    completed_count = (
        db.query(func.count(models.Document.id))
        .filter(models.Document.user_id == user.user_id, models.Document.status == "완료")
        .scalar()
    )

    # 맞춤법 도전 모드 최고 기록: SELECT MAX(score) FROM rankings WHERE user_id = 나 AND category = 'spelling'
    best_score = (
        db.query(func.max(models.Ranking.score))
        .filter(models.Ranking.user_id == user.user_id, models.Ranking.category == "spelling")
        .scalar()
    )

    # model_validate(user): User 객체에서 칸 이름이 같은 값(이름, 이메일 등)을 꺼내서 채움
    profile = ProfileOut.model_validate(user)
    profile.document_count = document_count or 0  # or 0: 결과가 None이면 0으로
    profile.completed_count = completed_count or 0
    profile.best_challenge_score = best_score or 0
    return profile


def get_stage(status: str | None, latest_version: int) -> str:
    """글의 단계(초안 / 수정 / 완료)를 정함
    DB에는 "작성중" / "완료" 두 가지만 저장되니까, 저장 횟수(버전 번호)를 보고 초안과 수정을 나눔
      - 최종 저장(status = "완료")      → 완료
      - 2번 이상 저장(버전 2 이상)      → 수정  (처음 쓴 글을 다시 고쳐서 저장했다는 뜻)
      - 그 외(저장 안 함 또는 1번 저장)  → 초안
    """
    if status == "완료":
        return STAGE_DONE
    if latest_version >= 2:
        return STAGE_REVISING
    return STAGE_DRAFT


def get_version_kind(version: int, is_final: bool) -> str:
    """저장본 하나가 어느 단계 탭에 들어가는지
      - 최종 저장한 저장본            → 완료
      - 첫 번째 저장본                → 초안
      - 그 사이(두 번째 저장부터)      → 수정
    ※ 글 하나가 여러 탭에 동시에 들어갈 수 있음
      (예: 3번 저장 후 최종 저장 → 초안 1장 + 수정 2장 + 완료 1장)
    """
    if is_final:
        return STAGE_DONE
    if version == 1:
        return STAGE_DRAFT
    return STAGE_REVISING


def prune_old_revisions(db: Session, document: models.Document, drafts: list) -> list:
    """수정본이 MAX_REVISIONS개를 넘으면 오래된 수정본을 지우고, 남은 저장본 목록을 돌려줌
    drafts: 이 글의 저장본들 (버전 오름차순 = 오래된 것부터)
    ※ commit은 부르는 쪽에서 한 번에 함
    """
    if not drafts:
        return drafts

    # 최종 저장한 글이면 마지막 저장본이 "완료"본 → 수정본 개수에서 빼고 항상 남김
    final_version = drafts[-1].version if document.status == STAGE_DONE else None

    # 수정본 = 첫 번째(초안)도 아니고 최종본도 아닌 저장본들 (오래된 것부터)
    revisions = [d for d in drafts if d.version != 1 and d.version != final_version]
    # [:-3]: 뒤에서 3개(가장 최근 3개)를 뺀 나머지 = 지울 것들
    to_delete = revisions[:-MAX_REVISIONS] if len(revisions) > MAX_REVISIONS else []
    if not to_delete:
        return drafts

    delete_ids = [d.id for d in to_delete]
    # 저장본에 딸린 AI 피드백부터 지우고 저장본을 지움 (자식 → 부모 순서)
    db.query(models.AIFeedback).filter(models.AIFeedback.draft_id.in_(delete_ids)).delete(
        synchronize_session=False
    )
    db.query(models.Draft).filter(models.Draft.id.in_(delete_ids)).delete(synchronize_session=False)
    # 지운 것을 뺀 나머지만 돌려줌
    return [d for d in drafts if d.id not in delete_ids]


def make_preview(text: str) -> str:
    """본문 앞부분만 잘라서 미리보기 글자로 만듦 (줄바꿈은 공백으로 바꿔서 한 줄로)"""
    one_line = " ".join(text.split())  # split(): 공백·줄바꿈 기준으로 나눔 → 다시 공백 하나로 이어 붙임
    if len(one_line) <= PREVIEW_LENGTH:
        return one_line
    return one_line[:PREVIEW_LENGTH] + "…"


# ===================== 1. 내 프로필 =====================


@router.get("/profile", response_model=ProfileOut)
def read_profile(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """마이페이지 위쪽 프로필 카드 정보"""
    cleanup_abandoned_documents(db, user)  # 방치된 빈 글은 "내가 쓴 글 수"에서도 빠지게 먼저 정리
    return build_profile(db, user)


# ===================== 2. 내가 쓴 글 목록 =====================


@router.get("/documents", response_model=list[MyDocumentOut])
def read_my_documents(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """내가 쓴 글 목록 (최근에 수정한 글이 위로)
    글마다 마지막 저장본의 앞부분을 미리보기로 붙여 줌
    """
    cleanup_abandoned_documents(db, user)  # 하루 넘게 방치된 빈 글은 목록에 안 나오게 먼저 정리
    documents = (
        db.query(models.Document)
        .filter(models.Document.user_id == user.user_id)
        # 최근 수정한 글 먼저, 수정 시각이 같으면 나중에 만든 글(id가 큰 글) 먼저
        .order_by(models.Document.updated_at.desc(), models.Document.id.desc())
        .all()
    )

    result = []
    pruned = False  # 오래된 수정본을 하나라도 지웠는지 (지웠으면 마지막에 commit)
    for document in documents:
        # 이 글의 저장본 전부 (오래된 것부터)
        drafts = (
            db.query(models.Draft)
            .filter(models.Draft.document_id == document.id)
            .order_by(models.Draft.version.asc())
            .all()
        )
        # 수정본이 3개를 넘으면 오래된 수정본 정리
        kept = prune_old_revisions(db, document, drafts)
        if len(kept) != len(drafts):
            pruned = True
        drafts = kept

        # 이 글의 마지막 저장본 (버전 번호가 가장 큰 것 = 맨 뒤)
        latest_draft = drafts[-1] if drafts else None
        latest_version = latest_draft.version if latest_draft else 0  # 저장한 적 없으면 0
        is_complete = document.status == STAGE_DONE

        # 저장본마다 어느 탭(초안/수정/완료)에 들어가는지 붙여서 목록으로
        versions = [
            MyVersionOut(
                version=draft.version,
                # 최종 저장한 글의 마지막 저장본만 "완료"
                kind=get_version_kind(draft.version, is_complete and draft is latest_draft),
                created_at=draft.created_at,
                preview=make_preview(draft.content),
            )
            for draft in drafts
        ]

        result.append(
            MyDocumentOut(
                id=document.id,
                title=document.title,
                document_type=document.document_type,
                status=document.status or "작성중",
                stage=get_stage(document.status, latest_version),  # 초안 / 수정 / 완료
                created_at=document.created_at,
                updated_at=document.updated_at,
                latest_version=latest_version,
                preview=make_preview(latest_draft.content) if latest_draft else "",
                versions=versions,
            )
        )

    if pruned:
        try:
            db.commit()  # 오래된 수정본 지운 것 확정
        except Exception:
            db.rollback()  # 실패해도 목록은 보여줌 (다음에 다시 정리됨)
    return result


# ===================== 2-1. 쓰다 만 글 지우기 =====================


@router.delete("/documents/{document_id}", response_model=MessageResponse)
def delete_unsaved_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """글쓰기 화면에서 쓰다가 다른 곳으로 가면 프론트가 부르는 API
    ★ 한 번도 저장하지 않은 글(저장본 0개)만 지움
      - "AI 초안 작성"을 누르면 저장 전에도 글이 먼저 만들어지는데, 그대로 떠나면 빈 글이 남음 → 그걸 정리
      - 한 번이라도 저장한 글(초안·수정)이나 최종 저장한 글(완료)은 실수로 지워지지 않게 거절(409)
    """
    # 내 글인지 확인 (남의 글 번호를 넣어도 못 지우게)
    document = (
        db.query(models.Document)
        .filter(models.Document.id == document_id, models.Document.user_id == user.user_id)
        .first()
    )
    if document is None:
        # 이미 지워졌거나 없는 글 → 프론트 입장에서는 목적 달성이니까 에러 대신 404만 알려줌
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="글을 찾을 수 없어요.")

    saved_count = db.query(func.count(models.Draft.id)).filter(models.Draft.document_id == document_id).scalar()
    if saved_count or document.status == "완료":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="저장한 글은 여기서 지울 수 없어요.")

    try:
        # 이 글에 딸린 "생각"(AI 초안 만들 때 저장됨)부터 지우고 글을 지움 (자식 → 부모 순서)
        delete_document_with_thoughts(db, document_id)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return MessageResponse(message="쓰다 만 글을 지웠어요.")


# ===================== 3. 회원정보 수정 =====================


@router.put("/profile", response_model=ProfileUpdateResponse)
def update_profile(
    body: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """이름, 전화번호, 이메일 수정
    이메일을 바꿀 때는 회원가입과 똑같이 새 이메일로 인증번호 확인을 먼저 마쳐야 함
    (프론트: /api/auth/email/send-code → /api/auth/email/verify → 이 API)
    """
    email_changed = body.email != user.email

    if email_changed:
        # 다른 사람이 이미 쓰는 이메일이면 거절
        if db.query(models.User).filter(models.User.email == body.email).first():
            raise HTTPException(status.HTTP_409_CONFLICT, detail="이미 가입된 이메일이에요.")

        # 새 이메일 인증을 마쳤는지 확인 (인증 성공 후 30분 안이어야 함)
        record = latest_verification(db, body.email)
        if (
            record is None
            or record.verified_at is None
            or now_utc() - as_utc(record.verified_at) > timedelta(minutes=VERIFIED_VALID_MINUTES)
        ):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="새 이메일 인증을 먼저 완료해 주세요.")

    # 값 바꾸기 (DB 객체의 칸을 바꾸고 commit하면 UPDATE 문이 실행됨)
    user.name = body.name
    user.phone = body.phone
    if email_changed:
        user.email = body.email
        user.email_verified = True
        # 다 쓴 인증 기록은 지움 (같은 인증으로 또 바꾸지 못하게)
        db.query(models.EmailVerification).filter(models.EmailVerification.email == body.email).delete()

    try:
        db.commit()
    except IntegrityError as error:
        # 아주 드물게 같은 순간에 다른 사람이 같은 이메일로 가입하면 여기서 걸림
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="이미 가입된 이메일이에요.") from error

    db.refresh(user)
    return ProfileUpdateResponse(message="회원정보를 수정했어요.", profile=build_profile(db, user))


# ===================== 4. 비밀번호 변경 =====================


@router.put("/password", response_model=MessageResponse)
def change_password(
    body: PasswordChangeRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """지금 비밀번호가 맞을 때만 새 비밀번호로 바꿈"""
    # 1) 본인 확인: 지금 비밀번호가 맞는지 (저장된 해시와 비교)
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="현재 비밀번호가 올바르지 않아요.")

    # 2) 새 비밀번호가 지금 비밀번호와 같으면 바꿀 의미가 없으니 거절
    if verify_password(body.new_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="지금 쓰는 비밀번호와 다른 비밀번호를 입력해 주세요.")

    # 3) 새 비밀번호도 원문 대신 bcrypt 해시로 저장
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return MessageResponse(message="비밀번호를 변경했어요.")


# ===================== 5. 회원 탈퇴 =====================


@router.post("/withdraw", response_model=MessageResponse)
def withdraw(
    body: WithdrawRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """비밀번호를 한 번 더 확인하고, 이 사람과 연결된 데이터를 전부 지운 뒤 계정을 삭제
    ★ 지우는 순서가 중요함: 다른 표가 참조하고 있는 줄(부모)을 먼저 지우면 외래키 에러가 남
       → 가장 안쪽(자식)부터 지움: AI 피드백 → 저장본·생각 → 글 → 퀴즈·랭킹·취향 → 회원
    """
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="비밀번호가 올바르지 않아요.")

    user_id = user.user_id

    # 이 사람이 쓴 글 번호 목록 (서브쿼리: 다른 쿼리 안에 넣어 쓰는 쿼리)
    my_document_ids = db.query(models.Document.id).filter(models.Document.user_id == user_id)
    # 그 글들의 저장본 번호 목록
    my_draft_ids = db.query(models.Draft.id).filter(models.Draft.document_id.in_(my_document_ids))

    try:
        # synchronize_session=False: 지운 줄을 지금 메모리에 올라온 객체와 맞추는 작업을 생략 (한꺼번에 지울 때 씀)
        db.query(models.AIFeedback).filter(models.AIFeedback.draft_id.in_(my_draft_ids)).delete(
            synchronize_session=False
        )
        db.query(models.Draft).filter(models.Draft.document_id.in_(my_document_ids)).delete(
            synchronize_session=False
        )
        db.query(models.Thought).filter(models.Thought.document_id.in_(my_document_ids)).delete(
            synchronize_session=False
        )
        db.query(models.Document).filter(models.Document.user_id == user_id).delete(synchronize_session=False)
        db.query(models.QuizResult).filter(models.QuizResult.user_id == user_id).delete(synchronize_session=False)
        db.query(models.Ranking).filter(models.Ranking.user_id == user_id).delete(synchronize_session=False)
        db.query(models.UserWritingPreference).filter(models.UserWritingPreference.user_id == user_id).delete(
            synchronize_session=False
        )
        db.query(models.EmailVerification).filter(models.EmailVerification.email == user.email).delete(
            synchronize_session=False
        )
        # 마지막으로 회원 자체를 지움
        db.query(models.User).filter(models.User.user_id == user_id).delete(synchronize_session=False)
        db.commit()
    except Exception:
        # 중간에 하나라도 실패하면 지금까지 지운 것도 전부 취소 (반쯤 지워진 상태로 남지 않게)
        db.rollback()
        raise

    return MessageResponse(message="회원 탈퇴가 완료됐어요. 그동안 이용해 주셔서 감사해요.")
