# =============================================================
# routers/admin.py — 관리자 페이지 API
# -------------------------------------------------------------
# 주소는 전부 /api/admin/... 로 시작하고, 전부 "관리자(role = admin)만" 쓸 수 있음
#  → 로그인 안 했으면 401, 로그인했는데 관리자가 아니면 403
#
#  [퀴즈 관리]
#  GET    /api/admin/quizzes?category=spelling   퀴즈 목록 (푼 횟수 포함)
#  POST   /api/admin/quizzes                     퀴즈 추가
#  PUT    /api/admin/quizzes/{quiz_id}           퀴즈 수정
#  DELETE /api/admin/quizzes/{quiz_id}           퀴즈 삭제 (그 문제를 푼 기록도 같이 지움)
#
#  [회원 관리]
#  GET    /api/admin/users?q=검색어&status=active   회원 목록 (글 수·도전 기록 포함)
#  PATCH  /api/admin/users/{user_id}/status          이용 상태 바꾸기 (정상 ↔ 정지)
#
#  [랭킹 관리]
#  GET    /api/admin/rankings?category=spelling  도전 기록 전체 (점수 높은 순)
#  DELETE /api/admin/rankings/{ranking_id}       도전 기록 하나 삭제 (부정 기록 정리용)
#
# ★ 관리자 계정 만드는 법 (화면에는 일부러 안 만듦 — 아무나 관리자가 되면 안 되니까)
#   DB에서 직접:  UPDATE users SET role = 'admin' WHERE login_id = '아이디';
#   → 바꾼 뒤 그 계정으로 다시 로그인하면 헤더에 "관리자" 버튼이 생김
# =============================================================

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, inspect, or_, text
from sqlalchemy.orm import Session

import models
from admin_schemas import AdminRankingOut, AdminUserOut, QuizIn, QuizOut, UserStatusIn
from auth_schemas import MessageResponse
from database import get_db

# 로그인 확인 함수는 회원가입 API(routers/auth.py)에 이미 있으니까 그대로 가져다 씀
from routers.auth import get_current_user

router = APIRouter(prefix="/api/admin", tags=["admin"])

ROLE_ADMIN = "admin"  # 관리자 (models.User.role 값)
STATUS_ACTIVE = "active"  # 정상 이용
STATUS_SUSPENDED = "suspended"  # 이용 정지


# ===================== 서버 시작할 때 1번: DB 준비 =====================


def ensure_user_status_column(engine) -> None:
    """users 테이블에 status(이용 상태) 칸이 없으면 만들어 줌

    왜 필요하냐면:
      models.py에 status 칸을 새로 추가했는데,
      Base.metadata.create_all()은 "없는 테이블"만 새로 만들고 "있는 테이블에 칸 추가"는 안 해 줌
      → 이미 만들어진 AWS RDS의 users 테이블에는 status 칸이 없어서 에러가 남
      → 그래서 서버가 켜질 때 한 번 확인하고, 없으면 칸을 추가함 (있으면 아무것도 안 함)

    DEFAULT 'active': 기존 회원들은 전부 "정상" 상태로 채워짐
    """
    # inspect: DB에 지금 어떤 테이블·칸이 있는지 들여다보는 도구
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return  # 테이블이 아예 없으면 create_all이 status까지 포함해서 새로 만들어 줌

    columns = [column["name"] for column in inspector.get_columns("users")]
    if "status" in columns:
        return  # 이미 있음 → 할 일 없음

    # engine.begin(): 작업이 끝나면 자동으로 commit (중간에 에러 나면 자동으로 취소)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'"))
    print("[관리자] users 테이블에 status(이용 상태) 칸을 추가했어요.")


# ===================== 관리자 확인 =====================


def get_current_admin(user: models.User = Depends(get_current_user)) -> models.User:
    """로그인한 사람이 관리자인지 확인 (아니면 403)
    사용 예) def admin_api(admin: User = Depends(get_current_admin)): ...
    get_current_user가 먼저 실행돼서, 로그인 안 했으면 여기까지 오기 전에 401이 남
    """
    if user.role != ROLE_ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="관리자만 이용할 수 있어요.")
    return user


# =============================================================
# 1. 퀴즈 관리
# =============================================================


def solved_counts(db: Session, quiz_ids: list[int]) -> dict[int, int]:
    """퀴즈마다 사용자들이 푼 횟수 { 퀴즈번호: 횟수 }
    SELECT quiz_id, COUNT(*) FROM quiz_results WHERE quiz_id IN (...) GROUP BY quiz_id
    → 퀴즈마다 따로 묻지 않고 한 번에 셈 (DB 왕복 1번)
    """
    if not quiz_ids:
        return {}
    rows = (
        db.query(models.QuizResult.quiz_id, func.count(models.QuizResult.result_id))
        .filter(models.QuizResult.quiz_id.in_(quiz_ids))
        .group_by(models.QuizResult.quiz_id)
        .all()
    )
    # dict(rows): [(1, 5), (2, 3)] → {1: 5, 2: 3}
    return dict(rows)


def to_quiz_out(quiz: models.Quiz, solved: int = 0) -> QuizOut:
    """DB의 Quiz 한 줄 → 응답 모양(QuizOut)"""
    out = QuizOut.model_validate(quiz)
    out.solved_count = solved
    return out


def find_quiz(db: Session, quiz_id: int) -> models.Quiz:
    """퀴즈 번호로 찾기 (없으면 404)"""
    quiz = db.query(models.Quiz).filter(models.Quiz.quiz_id == quiz_id).first()
    if quiz is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="퀴즈를 찾을 수 없어요.")
    return quiz


@router.get("/quizzes", response_model=list[QuizOut])
def list_quizzes(
    # Query(None): 주소 뒤 ?category=spelling 값 (안 보내면 None = 전체)
    category: str | None = Query(None),
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    """퀴즈 목록 (최근에 만든 문제가 위로)"""
    query = db.query(models.Quiz)
    if category:
        query = query.filter(models.Quiz.category == category)
    quizzes = query.order_by(models.Quiz.quiz_id.desc()).all()

    counts = solved_counts(db, [quiz.quiz_id for quiz in quizzes])
    # counts.get(번호, 0): 한 번도 안 풀린 문제는 0
    return [to_quiz_out(quiz, counts.get(quiz.quiz_id, 0)) for quiz in quizzes]


@router.post("/quizzes", response_model=QuizOut, status_code=status.HTTP_201_CREATED)
def create_quiz(
    body: QuizIn,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    """퀴즈 추가 (입력값 검사는 QuizIn이 이미 끝냄: 보기 2개 이상, 정답은 보기 중 하나 등)"""
    # model_dump(): 스키마 → 딕셔너리, **: 딕셔너리를 이름=값 형태로 풀어서 넘김
    quiz = models.Quiz(**body.model_dump())
    db.add(quiz)
    db.commit()
    db.refresh(quiz)  # DB가 정해 준 번호(quiz_id)·만든 시각을 다시 읽어옴
    return to_quiz_out(quiz)


@router.put("/quizzes/{quiz_id}", response_model=QuizOut)
def update_quiz(
    quiz_id: int,
    body: QuizIn,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    """퀴즈 수정 (문제·보기·정답·해설·종류를 한 번에 바꿈)"""
    quiz = find_quiz(db, quiz_id)
    # items(): (칸 이름, 값) 짝을 하나씩 꺼냄 → setattr로 quiz.칸이름 = 값
    for field, value in body.model_dump().items():
        setattr(quiz, field, value)
    db.commit()
    db.refresh(quiz)
    return to_quiz_out(quiz, solved_counts(db, [quiz.quiz_id]).get(quiz.quiz_id, 0))


@router.delete("/quizzes/{quiz_id}", response_model=MessageResponse)
def delete_quiz(
    quiz_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    """퀴즈 삭제
    quiz_results(푼 기록)가 이 퀴즈를 가리키고 있어서, 기록부터 지우고 퀴즈를 지움 (자식 → 부모 순서)
    → 안 그러면 DB가 "가리키는 데이터가 남아 있다"며 삭제를 거절함
    """
    quiz = find_quiz(db, quiz_id)
    try:
        db.query(models.QuizResult).filter(models.QuizResult.quiz_id == quiz.quiz_id).delete(
            synchronize_session=False
        )
        db.delete(quiz)
        db.commit()
    except Exception:
        db.rollback()  # 중간에 실패하면 지운 것도 전부 되돌림
        raise
    return MessageResponse(message="퀴즈를 삭제했어요.")


# =============================================================
# 2. 회원 관리
# =============================================================


@router.get("/users", response_model=list[AdminUserOut])
def list_users(
    q: str | None = Query(None),  # 검색어 (아이디·이름·이메일 중 하나라도 포함되면 나옴)
    user_status: str | None = Query(None, alias="status"),  # active / suspended (안 보내면 전체)
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    """회원 목록 (최근 가입한 회원이 위로)
    회원마다 따로 묻지 않고, "글 수"와 "도전 기록"을 GROUP BY로 한 번씩만 세서 붙임
    → 회원이 몇 명이든 DB 왕복은 3번
    """
    # ----- 1) 회원 목록 -----
    query = db.query(models.User)
    if q and q.strip():
        keyword = f"%{q.strip()}%"  # %: "앞뒤로 아무 글자나" → 포함 검색
        # or_: 셋 중 하나라도 맞으면 / ilike: 대소문자 구분 없이 비교
        query = query.filter(
            or_(
                models.User.login_id.ilike(keyword),
                models.User.name.ilike(keyword),
                models.User.email.ilike(keyword),
            )
        )
    if user_status:
        query = query.filter(models.User.status == user_status)
    users = query.order_by(models.User.created_at.desc(), models.User.user_id.desc()).all()

    # ----- 2) 회원별 글 수 { 회원번호: 글 수 } -----
    document_counts = dict(
        db.query(models.Document.user_id, func.count(models.Document.id))
        .group_by(models.Document.user_id)
        .all()
    )

    # ----- 3) 회원별 도전 기록 수 + 최고 점수 -----
    ranking_stats = {
        user_id: (count, best)
        for user_id, count, best in db.query(
            models.Ranking.user_id,
            func.count(models.Ranking.ranking_id),
            func.max(models.Ranking.score),
        )
        .group_by(models.Ranking.user_id)
        .all()
    }

    result = []
    for user in users:
        ranking_count, best_score = ranking_stats.get(user.user_id, (0, 0))
        result.append(
            AdminUserOut(
                user_id=user.user_id,
                login_id=user.login_id,
                name=user.name,
                email=user.email,
                phone=user.phone,
                role=user.role or "general",
                status=user.status or STATUS_ACTIVE,
                created_at=user.created_at,
                document_count=document_counts.get(user.user_id, 0),
                ranking_count=ranking_count or 0,
                best_score=best_score or 0,
            )
        )
    return result


@router.patch("/users/{user_id}/status", response_model=AdminUserOut)
def change_user_status(
    user_id: int,
    body: UserStatusIn,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    """회원 이용 상태 바꾸기 (정상 ↔ 정지)
    정지된 회원은 로그인이 막히고, 이미 로그인해 있어도 다음 요청부터 막힘 (routers/auth.py 참고)
    """
    user = db.get(models.User, user_id)  # 기본키(user_id)로 찾기
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="회원을 찾을 수 없어요.")

    if body.status == STATUS_SUSPENDED:
        # 실수로 나 자신을 정지하면 관리자 페이지에 다시 못 들어오니까 막음
        if user.user_id == admin.user_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="자기 자신은 정지할 수 없어요.")
        # 관리자끼리 서로 정지하는 일도 막음 (관리자 권한은 DB에서 직접 관리)
        if user.role == ROLE_ADMIN:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="관리자 계정은 정지할 수 없어요.")

    user.status = body.status
    db.commit()
    db.refresh(user)

    # 바뀐 회원 한 줄만 다시 만들어서 돌려줌 (프론트가 목록에서 그 줄만 바꿔 끼움)
    document_count = (
        db.query(func.count(models.Document.id)).filter(models.Document.user_id == user.user_id).scalar()
    )
    ranking_count, best_score = (
        db.query(func.count(models.Ranking.ranking_id), func.max(models.Ranking.score))
        .filter(models.Ranking.user_id == user.user_id)
        .one()
    )
    return AdminUserOut(
        user_id=user.user_id,
        login_id=user.login_id,
        name=user.name,
        email=user.email,
        phone=user.phone,
        role=user.role or "general",
        status=user.status,
        created_at=user.created_at,
        document_count=document_count or 0,
        ranking_count=ranking_count or 0,
        best_score=best_score or 0,
    )


# =============================================================
# 3. 랭킹 관리
# =============================================================


@router.get("/rankings", response_model=list[AdminRankingOut])
def list_rankings(
    category: str | None = Query("spelling"),  # 기본은 맞춤법 도전 (랭킹은 맞춤법만 있음)
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    """도전 기록 전체 (랭킹 화면은 사람마다 최고 기록 1줄만 보여주지만, 여기서는 모든 도전을 다 보여줌)
    정렬: 점수 높은 순 → 점수가 같으면 빨리 끝낸 순 → 먼저 도전한 순 (랭킹 화면과 같은 기준)
    """
    # outerjoin: 회원이 탈퇴해서 없어도 기록은 보이게 (회원 칸만 비어서 나옴)
    query = db.query(models.Ranking, models.User).outerjoin(
        models.User, models.User.user_id == models.Ranking.user_id
    )
    if category:
        query = query.filter(models.Ranking.category == category)
    rows = (
        query.order_by(
            models.Ranking.score.desc(),
            models.Ranking.elapsed_time.asc(),
            models.Ranking.challenged_at.asc(),
        )
        .limit(500)  # 너무 많으면 화면이 느려지니까 상위 500개까지만
        .all()
    )

    return [
        AdminRankingOut(
            ranking_id=ranking.ranking_id,
            user_id=ranking.user_id,
            login_id=user.login_id if user else None,
            name=user.name if user else None,
            category=ranking.category,
            score=ranking.score,
            elapsed_time=ranking.elapsed_time or 0.0,
            challenged_at=ranking.challenged_at,
        )
        for ranking, user in rows
    ]


@router.delete("/rankings/{ranking_id}", response_model=MessageResponse)
def delete_ranking(
    ranking_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    """도전 기록 하나 삭제 (비정상적으로 높은 점수 등 부정 기록 정리용)
    지우면 랭킹 화면에서도 바로 빠짐 (그 사람의 다음 최고 기록이 대신 올라옴)
    """
    ranking = db.query(models.Ranking).filter(models.Ranking.ranking_id == ranking_id).first()
    if ranking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="기록을 찾을 수 없어요.")
    db.delete(ranking)
    db.commit()
    return MessageResponse(message="도전 기록을 삭제했어요.")
