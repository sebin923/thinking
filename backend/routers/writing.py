from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from routers.auth import get_current_user
from models import UserWritingPreference

import models
from database import get_db
import requests
from clova import create_draft_with_ai, create_feedback_with_ai

router = APIRouter(prefix="/api", tags=["Writing"])


def get_user_preferences(db: Session, user_id: int):
    preference = db.query(UserWritingPreference).filter(
        UserWritingPreference.user_id == user_id
    ).first()
    if preference is None:
        return None
    return {
        "preferred_tone": preference.preferred_tone,
        "sentence_length": preference.sentence_length,
        "feedback_style": preference.feedback_style,
        "ai_assistance": preference.ai_assistance,
    }


def get_owned_document(db: Session, document_id: int, user_id: int):
    document = db.query(models.Document).filter(
        models.Document.id == document_id,
        models.Document.user_id == user_id,
    ).first()
    if document is None:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    return document


class DocumentCreate(BaseModel):
    document_type: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=50)


class ThoughtCreate(BaseModel):
    document_id: int
    content: str = Field(min_length=1)


class DraftCreate(BaseModel):
    document_id: int
    content: str = Field(min_length=1, max_length=2000)


@router.post("/documents")
def create_document(
    request: DocumentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not request.title.strip() or not request.document_type.strip():
        raise HTTPException(status_code=400, detail="제목과 글 유형을 입력해 주세요.")
    document = models.Document(
        user_id=current_user.user_id,
        document_type=request.document_type.strip(),
        title=request.title.strip(),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.get("/documents")
def get_documents(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return db.query(models.Document).filter(
        models.Document.user_id == current_user.user_id
    ).order_by(models.Document.id.desc()).all()


@router.post("/thoughts")
def create_thought(
    request: ThoughtCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    get_owned_document(db, request.document_id, current_user.user_id)
    if not request.content.strip():
        raise HTTPException(status_code=400, detail="생각 내용을 입력해 주세요.")
    thought = models.Thought(document_id=request.document_id, content=request.content.strip())
    db.add(thought)
    db.commit()
    db.refresh(thought)
    return thought


@router.get("/documents/{document_id}/thoughts")
def get_thoughts(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    get_owned_document(db, document_id, current_user.user_id)
    return db.query(models.Thought).filter(
        models.Thought.document_id == document_id
    ).all()


@router.post("/documents/{document_id}/draft-ai")
def create_ai_draft(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    document = get_owned_document(db, document_id, current_user.user_id)
    thoughts = db.query(models.Thought).filter(
        models.Thought.document_id == document_id
    ).all()
    thought_text = "\n".join(thought.content for thought in thoughts)
    if not thought_text.strip():
        raise HTTPException(status_code=400, detail="작성할 생각 내용이 없습니다.")
    preferences = get_user_preferences(db, current_user.user_id)
    try:
        content = create_draft_with_ai(
            thought_text=thought_text,
            document_type=document.document_type,
            user_preferences=preferences,
        )
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except (requests.RequestException, KeyError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="AI 초안 생성 서비스에 연결하지 못했습니다.") from exc
    return {"content": content}


@router.post("/drafts")
def save_draft(
    request: DraftCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    get_owned_document(db, request.document_id, current_user.user_id)
    if not request.content.strip():
        raise HTTPException(status_code=400, detail="본문을 입력해 주세요.")
    last_draft = db.query(models.Draft).filter(
        models.Draft.document_id == request.document_id
    ).order_by(models.Draft.version.desc()).first()
    next_version = 1 if last_draft is None else last_draft.version + 1
    draft = models.Draft(
        document_id=request.document_id,
        content=request.content.strip(),
        version=next_version,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


@router.get("/documents/{document_id}/drafts")
def get_drafts(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    get_owned_document(db, document_id, current_user.user_id)
    return db.query(models.Draft).filter(
        models.Draft.document_id == document_id
    ).order_by(models.Draft.version.desc()).all()


@router.post("/drafts/{draft_id}/feedback-ai")
def create_ai_feedback(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    draft = db.query(models.Draft).filter(
        models.Draft.id == draft_id
    ).first()
    if draft is None:
        raise HTTPException(status_code=404, detail="저장된 글을 찾을 수 없습니다.")
    document = get_owned_document(db, draft.document_id, current_user.user_id)
    if not draft.content.strip():
        raise HTTPException(status_code=400, detail="피드백을 받을 글이 비어 있습니다.")
    preferences = get_user_preferences(db, current_user.user_id)
    try:
        feedback_result = create_feedback_with_ai(
            content=draft.content,
            document_type=document.document_type,
            user_preferences=preferences,
        )
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except (requests.RequestException, KeyError, TypeError) as e:
        raise HTTPException(
            status_code=502,
            detail="AI 피드백 서비스 호출에 실패했습니다.",
        ) from e
    feedback = models.AIFeedback(draft_id=draft.id, feedback_data=feedback_result)
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return {
        "message": "AI 피드백 생성 성공",
        "feedback_id": feedback.id,
        "draft_id": draft.id,
        "version": draft.version,
        "feedback": feedback.feedback_data,
    }


@router.get("/drafts/{draft_id}/feedbacks")
def get_ai_feedbacks(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    draft = db.query(models.Draft).filter(models.Draft.id == draft_id).first()
    if draft is None:
        raise HTTPException(status_code=404, detail="저장된 글을 찾을 수 없습니다.")
    get_owned_document(db, draft.document_id, current_user.user_id)
    return db.query(models.AIFeedback).filter(
        models.AIFeedback.draft_id == draft_id
    ).order_by(models.AIFeedback.id.desc()).all()


@router.patch("/documents/{document_id}/complete")
def complete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    document = get_owned_document(db, document_id, current_user.user_id)
    latest_draft = db.query(models.Draft).filter(
        models.Draft.document_id == document_id
    ).order_by(models.Draft.version.desc()).first()
    if latest_draft is None:
        raise HTTPException(status_code=400, detail="저장된 글이 없습니다.")
    document.status = "완료"
    db.commit()
    db.refresh(document)
    return {
        "message": "최종 저장 완료",
        "document_id": document.id,
        "status": document.status,
        "final_draft_id": latest_draft.id,
        "version": latest_draft.version,
    }


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # 1. 로그인한 사용자의 문서인지 확인
    document = get_owned_document(
        db, document_id, current_user.user_id
    )

    try:
        # 2. 문서에 연결된 초안 ID 조회
        draft_ids = [
            draft_id
            for (draft_id,) in db.query(models.Draft.id).filter(
                models.Draft.document_id == document.id
            ).all()
        ]

        # 3. 초안과 연결된 AI 피드백 삭제
        if draft_ids:
            db.query(models.AIFeedback).filter(
                models.AIFeedback.draft_id.in_(draft_ids)
            ).delete(synchronize_session=False)

        # 4. 저장된 초안 및 수정본 삭제
        db.query(models.Draft).filter(
            models.Draft.document_id == document.id
        ).delete(synchronize_session=False)

        # 5. 생각 입력 기록 삭제
        db.query(models.Thought).filter(
            models.Thought.document_id == document.id
        ).delete(synchronize_session=False)

        # 6. 문서 삭제
        db.delete(document)

        # 7. 모든 삭제가 성공했을 때만 DB에 반영
        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "message": "글이 삭제되었습니다.",
        "document_id": document_id,
    }

from difflib import SequenceMatcher

@router.get("/users/me/writing-profile")
def get_my_writing_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # 1. 로그인한 사용자의 AI 피드백만 조회
    feedbacks = (
        db.query(models.AIFeedback)
        .join(
            models.Draft,
            models.AIFeedback.draft_id == models.Draft.id
        )
        .join(
            models.Document,
            models.Draft.document_id == models.Document.id
        )
        .filter(
            models.Document.user_id == current_user.user_id
        )
        .order_by(models.AIFeedback.id.desc())
        .all()
    )

    # 2. 오류 유형별 개수 저장
    category_counts = {
        "맞춤법": 0,
        "문법": 0,
        "표현": 0,
        "논리": 0,
        "구성": 0,
    }

    # 같은 초안에 여러 번 피드백을 받았다면
    # 가장 최근 피드백만 분석
    processed_drafts = set()
    analyzed_feedback_count = 0

    for feedback in feedbacks:
        if feedback.draft_id in processed_drafts:
            continue

        processed_drafts.add(feedback.draft_id)

        data = feedback.feedback_data
        if not isinstance(data, dict):
            continue

        highlights = data.get("highlights", [])
        if not isinstance(highlights, list):
            continue

        analyzed_feedback_count += 1

       
        # 3. 피드백의 오류 유형 집계
        for item in highlights:
            if not isinstance(item, dict):
                continue

            category = item.get("type", "")

            # AI 피드백 유형을 공통 분류 체계로 변환
            category_mapping = {
                "맞춤법": "맞춤법",
                "문법": "문법",
                "표현": "표현",
                "반복": "표현",
                "구체성": "논리",
                "근거 부족": "논리",
                "논리": "논리",
                "구조": "구성",
                "구성": "구성",
            }

            normalized_category = category_mapping.get(
                category
            )

            if normalized_category in category_counts:
                category_counts[normalized_category] += 1


    # 4. 오류가 많이 발생한 유형부터 정렬
    sorted_weaknesses = sorted(
        category_counts.items(),
        key=lambda item: item[1],
        reverse=True
    )

    main_weaknesses = [
        {
            "category": category,
            "count": count
        }
        for category, count in sorted_weaknesses
        if count > 0
    ][:3]

    return {
        "user_id": current_user.user_id,
        "analyzed_feedback_count": analyzed_feedback_count,
        "category_counts": category_counts,
        "main_weaknesses": main_weaknesses,
    }

@router.get("/documents/{document_id}/revision-review")
def review_document_revision(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # 1. 로그인한 사용자의 문서인지 확인
    document = get_owned_document(
        db,
        document_id,
        current_user.user_id
    )

    # 2. 최신 글 버전 2개 불러오기
    drafts = (
        db.query(models.Draft)
        .filter(models.Draft.document_id == document.id)
        .order_by(
            models.Draft.version.desc(),
            models.Draft.id.desc()
        )
        .limit(2)
        .all()
    )

    if len(drafts) < 2:
        raise HTTPException(
            status_code=400,
            detail="수정 비교를 위해 글 버전이 2개 이상 필요합니다."
        )

    latest_draft = drafts[0]
    previous_draft = drafts[1]

    # 3. 이전 버전에서 받은 최신 AI 피드백
    previous_feedback = (
        db.query(models.AIFeedback)
        .filter(
            models.AIFeedback.draft_id == previous_draft.id
        )
        .order_by(models.AIFeedback.id.desc())
        .first()
    )

    # 4. 이전 글과 수정 글의 유사도 계산
    similarity = SequenceMatcher(
        None,
        previous_draft.content,
        latest_draft.content
    ).ratio()

    # 5. 이전 피드백에서 지적한 부분 확인
    reviewed_items = []

    if previous_feedback:
        feedback_data = previous_feedback.feedback_data

        if isinstance(feedback_data, dict):
            highlights = feedback_data.get("highlights", [])

            if not isinstance(highlights, list):
                highlights = []

            for item in highlights:
                if not isinstance(item, dict):
                    continue

                original_text = item.get("original_text", "")

                if not isinstance(original_text, str):
                    continue

                if not original_text.strip():
                    continue

                # 원래 지적한 문구가 수정본에도 남아 있는지 확인
                still_exists = (
                    original_text in latest_draft.content
                )

                reviewed_items.append({
                    "category": item.get("type"),
                    "original_text": original_text,
                    "reason": item.get("reason"),
                    "suggestion": item.get("suggestion"),
                    "status": (
                        "원문 유지"
                        if still_exists
                        else "원문 변경 또는 삭제"
                    )
                })

    # 6. 비교 결과 반환
    return {
        "document_id": document.id,
        "previous_version": previous_draft.version,
        "latest_version": latest_draft.version,
        "previous_content": previous_draft.content,
        "latest_content": latest_draft.content,
        "similarity_percent": round(similarity * 100, 2),
        "has_previous_feedback": previous_feedback is not None,
        "reviewed_items": reviewed_items,
        "note": (
            "원문 변경 여부는 실제 글쓰기 문제의 개선 여부를 "
            "의미하지 않습니다. 개선 평가는 별도로 필요합니다."
        )
    }


@router.get("/documents/{document_id}/training-candidates")
def get_training_candidates(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # 1. 로그인 사용자의 문서인지 확인
    document = get_owned_document(
        db,
        document_id,
        current_user.user_id
    )

    # 2. 문서의 모든 저장 버전을 순서대로 조회
    drafts = (
        db.query(models.Draft)
        .filter(models.Draft.document_id == document.id)
        .order_by(
            models.Draft.version.asc(),
            models.Draft.id.asc()
        )
        .all()
    )

    candidates = []

    # 3. 이전 버전과 다음 버전을 연결
    for index in range(len(drafts) - 1):
        before = drafts[index]
        after = drafts[index + 1]

        # 내용이 동일하면 제외
        if before.content.strip() == after.content.strip():
            continue

        # 4. 이전 버전에 제공된 최신 AI 피드백
        feedback = (
            db.query(models.AIFeedback)
            .filter(models.AIFeedback.draft_id == before.id)
            .order_by(models.AIFeedback.id.desc())
            .first()
        )

        # AI 피드백이 없으면 학습 후보에서 제외
        if feedback is None:
            continue

        # 5. 피드백 결과 확인
        feedback_data = feedback.feedback_data

        if not isinstance(feedback_data, dict):
            continue

        highlights = feedback_data.get("highlights", [])

        if not isinstance(highlights, list):
            continue

        # 6. 학습 후보 데이터 구성
        candidate = {
            "document_id": document.id,
            "document_type": document.document_type,
            "before_draft_id": before.id,
            "after_draft_id": after.id,
            "before_version": before.version,
            "after_version": after.version,
            "original_text": before.content,
            "feedback": {
                "overall_feedback": feedback_data.get(
                    "overall_feedback", ""
                ),
                "highlights": highlights
            },
            "revised_text": after.content,
            "review_status": "검토 필요"
        }

        candidates.append(candidate)

    # 7. 최종 결과 반환
    return {
        "user_id": current_user.user_id,
        "document_id": document.id,
        "candidate_count": len(candidates),
        "training_candidates": candidates,
        "note": (
            "사용자의 수정본은 아직 검증되지 않은 "
            "학습 후보입니다. 실제 모델 학습 전에 "
            "내용과 피드백을 검토해야 합니다."
        )
    }
