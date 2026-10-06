from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

import models
from database import get_db
from clova import create_draft_with_ai

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