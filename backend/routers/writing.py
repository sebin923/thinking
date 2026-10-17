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
