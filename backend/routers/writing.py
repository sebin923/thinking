from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

import models
from database import get_db
import requests
from clova import create_draft_with_ai, create_feedback_with_ai

router = APIRouter(
    prefix="/api",
    tags=["Writing"]
)


class DocumentCreate(BaseModel):
    document_type: str
    title: str


class ThoughtCreate(BaseModel):
    document_id: int
    content: str


class DraftCreate(BaseModel):
    document_id: int
    content: str


@router.post("/documents")
def create_document(request: DocumentCreate, db: Session = Depends(get_db)):
    document = models.Document(
        document_type=request.document_type,
        title=request.title
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document


@router.get("/documents")
def get_documents(db: Session = Depends(get_db)):
    return db.query(models.Document).all()


@router.post("/thoughts")
def create_thought(request: ThoughtCreate, db: Session = Depends(get_db)):
    document = db.query(models.Document).filter(
        models.Document.id == request.document_id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")

    thought = models.Thought(
        document_id=request.document_id,
        content=request.content
    )

    db.add(thought)
    db.commit()
    db.refresh(thought)

    return thought


@router.get("/documents/{document_id}/thoughts")
def get_thoughts(document_id: int, db: Session = Depends(get_db)):
    return db.query(models.Thought).filter(
        models.Thought.document_id == document_id
    ).all()


@router.post("/documents/{document_id}/draft-ai")
def create_ai_draft(document_id: int, db: Session = Depends(get_db)):
    document = db.query(models.Document).filter(
        models.Document.id == document_id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")

    thoughts = db.query(models.Thought).filter(
        models.Thought.document_id == document_id
    ).all()

    thought_text = "\n".join([t.content for t in thoughts])

    if not thought_text.strip():
        raise HTTPException(status_code=400, detail="작성할 생각 내용이 없습니다.")

    content = create_draft_with_ai(
        thought_text=thought_text,
        document_type=document.document_type
    )

    return {"content": content}


@router.post("/drafts")
def save_draft(request: DraftCreate, db: Session = Depends(get_db)):
    document = db.query(models.Document).filter(
        models.Document.id == request.document_id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")

    last_draft = db.query(models.Draft).filter(
        models.Draft.document_id == request.document_id
    ).order_by(models.Draft.version.desc()).first()

    next_version = 1 if not last_draft else last_draft.version + 1

    draft = models.Draft(
        document_id=request.document_id,
        content=request.content,
        version=next_version
    )

    db.add(draft)
    db.commit()
    db.refresh(draft)

    return draft


@router.get("/documents/{document_id}/drafts")
def get_drafts(document_id: int, db: Session = Depends(get_db)):
    return db.query(models.Draft).filter(
        models.Draft.document_id == document_id
    ).order_by(models.Draft.version.desc()).all()


@router.post("/drafts/{draft_id}/feedback-ai")
def create_ai_feedback(
    draft_id: int,
    db: Session = Depends(get_db)
):
    draft = db.query(models.Draft).filter(
        models.Draft.id == draft_id
    ).first()

    if not draft:
        raise HTTPException(
            status_code=404,
            detail="저장된 글을 찾을 수 없습니다."
        )

    document = db.query(models.Document).filter(
        models.Document.id == draft.document_id
    ).first()

    if not document:
        raise HTTPException(
            status_code=404,
            detail="문서를 찾을 수 없습니다."
        )

    if not draft.content.strip():
        raise HTTPException(
            status_code=400,
            detail="피드백을 받을 글이 비어 있습니다."
        )

    try:
        feedback_result = create_feedback_with_ai(
            content=draft.content,
            document_type=document.document_type
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except (requests.RequestException, KeyError, TypeError) as e:
        raise HTTPException(
            status_code=502,
            detail="AI 피드백 서비스 호출에 실패했습니다."
        ) from e

    feedback = models.AIFeedback(
        draft_id=draft.id,
        feedback_data=feedback_result
    )

    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    return {
        "message": "AI 피드백 생성 성공",
        "feedback_id": feedback.id,
        "draft_id": draft.id,
        "version": draft.version,
        "feedback": feedback.feedback_data
    }


@router.get("/drafts/{draft_id}/feedbacks")
def get_ai_feedbacks(
    draft_id: int,
    db: Session = Depends(get_db)
):
    draft = db.query(models.Draft).filter(
        models.Draft.id == draft_id
    ).first()

    if not draft:
        raise HTTPException(
            status_code=404,
            detail="저장된 글을 찾을 수 없습니다."
        )

    return db.query(models.AIFeedback).filter(
        models.AIFeedback.draft_id == draft_id
    ).order_by(
        models.AIFeedback.id.desc()
    ).all()


@router.patch("/documents/{document_id}/complete")
def complete_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    document = db.query(models.Document).filter(
        models.Document.id == document_id
    ).first()

    if not document:
        raise HTTPException(
            status_code=404,
            detail="문서를 찾을 수 없습니다."
        )

    latest_draft = db.query(models.Draft).filter(
        models.Draft.document_id == document_id
    ).order_by(
        models.Draft.version.desc()
    ).first()

    if not latest_draft:
        raise HTTPException(
            status_code=400,
            detail="저장된 글이 없습니다."
        )

    document.status = "완료"
    db.commit()
    db.refresh(document)

    return {
        "message": "최종 저장 완료",
        "document_id": document.id,
        "status": document.status,
        "final_draft_id": latest_draft.id,
        "version": latest_draft.version
    }
