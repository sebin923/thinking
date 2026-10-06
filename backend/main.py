from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel

from sqlalchemy.orm import Session
from sqlalchemy import text

from database import engine, Base, get_db

import models

from clova import (
    structure_thought,
    create_draft_with_ai
)


# --------------------------------------------------
# DB 테이블 생성
# --------------------------------------------------
Base.metadata.create_all(bind=engine)


# --------------------------------------------------
# FastAPI
# --------------------------------------------------
app = FastAPI()


# --------------------------------------------------
# CORS
# --------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Pydantic Models
# --------------------------------------------------

class DocumentCreate(BaseModel):
    document_type: str
    title: str


class ThoughtCreate(BaseModel):
    document_id: int
    content: str


class StructureCreate(BaseModel):
    document_id: int
    situation: str
    problem: str
    action: str
    result: str
    meaning: str


class StructureFollowUp(BaseModel):
    situation: str | None = None
    problem: str | None = None
    action: str | None = None
    result: str | None = None
    meaning: str | None = None


class DraftCreate(BaseModel):
    document_id: int
    content: str


# --------------------------------------------------
# 기본 테스트
# --------------------------------------------------

@app.get("/")
def root():
    return {
        "message": "생각한줄 FastAPI 서버 실행 중"
    }


@app.get("/api/test")
def test_api():
    return {
        "message": "API 연결 성공"
    }


@app.get("/api/db-test")
def db_test(
    db: Session = Depends(get_db)
):
    result = db.execute(
        text("SELECT 1")
    )

    return {
        "message": "DB 연결 성공",
        "result": result.scalar()
    }


# --------------------------------------------------
# Document
# --------------------------------------------------

@app.post("/api/documents")
def create_document(
    document: DocumentCreate,
    db: Session = Depends(get_db)
):
    new_document = models.Document(
        document_type=document.document_type,
        title=document.title
    )

    db.add(new_document)
    db.commit()
    db.refresh(new_document)

    return new_document


@app.get("/api/documents")
def get_documents(
    db: Session = Depends(get_db)
):
    documents = (
        db.query(models.Document)
        .order_by(models.Document.id.desc())
        .all()
    )

    return documents


# --------------------------------------------------
# Thought
# --------------------------------------------------

@app.post("/api/thoughts")
def create_thought(
    thought: ThoughtCreate,
    db: Session = Depends(get_db)
):
    document = (
        db.query(models.Document)
        .filter(
            models.Document.id == thought.document_id
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="해당 문서를 찾을 수 없습니다."
        )

    new_thought = models.Thought(
        document_id=thought.document_id,
        content=thought.content
    )

    db.add(new_thought)
    db.commit()
    db.refresh(new_thought)

    return new_thought


@app.get(
    "/api/documents/{document_id}/thoughts"
)
def get_document_thoughts(
    document_id: int,
    db: Session = Depends(get_db)
):
    thoughts = (
        db.query(models.Thought)
        .filter(
            models.Thought.document_id
            == document_id
        )
        .order_by(models.Thought.id)
        .all()
    )

    return thoughts


# --------------------------------------------------
# Structure - 수동 저장
# --------------------------------------------------

@app.post("/api/structures")
def create_structure(
    structure: StructureCreate,
    db: Session = Depends(get_db)
):
    document = (
        db.query(models.Document)
        .filter(
            models.Document.id
            == structure.document_id
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="해당 문서를 찾을 수 없습니다."
        )

    new_structure = models.Structure(
        document_id=structure.document_id,
        situation=structure.situation,
        problem=structure.problem,
        action=structure.action,
        result=structure.result,
        meaning=structure.meaning
    )

    db.add(new_structure)
    db.commit()
    db.refresh(new_structure)

    return new_structure


@app.get(
    "/api/documents/{document_id}/structures"
)
def get_document_structures(
    document_id: int,
    db: Session = Depends(get_db)
):
    structures = (
        db.query(models.Structure)
        .filter(
            models.Structure.document_id
            == document_id
        )
        .order_by(models.Structure.id)
        .all()
    )

    return structures


# --------------------------------------------------
# Structure - AI 구조화
# --------------------------------------------------

@app.post(
    "/api/documents/{document_id}/structure-ai"
)
def create_ai_structure(
    document_id: int,
    db: Session = Depends(get_db)
):
    document = (
        db.query(models.Document)
        .filter(
            models.Document.id == document_id
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="해당 문서를 찾을 수 없습니다."
        )

    thoughts = (
        db.query(models.Thought)
        .filter(
            models.Thought.document_id
            == document_id
        )
        .order_by(models.Thought.id)
        .all()
    )

    if not thoughts:
        raise HTTPException(
            status_code=400,
            detail="구조화할 생각이 없습니다."
        )

    thought_text = "\n".join(
        f"- {thought.content}"
        for thought in thoughts
    )

    try:
        ai_result = structure_thought(
            thought_text
        )

    except Exception as error:
        print(
            "CLOVA 구조화 오류:",
            error
        )

        raise HTTPException(
            status_code=502,
            detail="CLOVA AI 호출에 실패했습니다."
        )

    existing_structure = (
        db.query(models.Structure)
        .filter(
            models.Structure.document_id
            == document_id
        )
        .order_by(
            models.Structure.id.desc()
        )
        .first()
    )

    if existing_structure:
        existing_structure.situation = (
            ai_result.get(
                "situation",
                ""
            )
        )

        existing_structure.problem = (
            ai_result.get(
                "problem",
                ""
            )
        )

        existing_structure.action = (
            ai_result.get(
                "action",
                ""
            )
        )

        existing_structure.result = (
            ai_result.get(
                "result",
                ""
            )
        )

        existing_structure.meaning = (
            ai_result.get(
                "meaning",
                ""
            )
        )

        structure = existing_structure

        save_type = "updated"

    else:
        structure = models.Structure(
            document_id=document_id,
            situation=ai_result.get(
                "situation",
                ""
            ),
            problem=ai_result.get(
                "problem",
                ""
            ),
            action=ai_result.get(
                "action",
                ""
            ),
            result=ai_result.get(
                "result",
                ""
            ),
            meaning=ai_result.get(
                "meaning",
                ""
            )
        )

        db.add(structure)

        save_type = "created"

    db.commit()
    db.refresh(structure)

    return {
        "message": "AI 구조화 성공",

        "save_type": save_type,

        "document_id": document_id,

        "input_thoughts": [
            thought.content
            for thought in thoughts
        ],

        "structure": {
            "id": structure.id,

            "situation":
                structure.situation,

            "problem":
                structure.problem,

            "action":
                structure.action,

            "result":
                structure.result,

            "meaning":
                structure.meaning
        }
    }


# --------------------------------------------------
# Structure - 추가 질문 답변 반영
# --------------------------------------------------

@app.post(
    "/api/documents/{document_id}/structure-followup"
)
def update_structure_followup(
    document_id: int,
    followup: StructureFollowUp,
    db: Session = Depends(get_db)
):
    document = (
        db.query(models.Document)
        .filter(
            models.Document.id == document_id
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="해당 문서를 찾을 수 없습니다."
        )

    structure = (
        db.query(models.Structure)
        .filter(
            models.Structure.document_id
            == document_id
        )
        .order_by(
            models.Structure.id.desc()
        )
        .first()
    )

    if not structure:
        raise HTTPException(
            status_code=404,
            detail="구조화 결과가 없습니다."
        )

    # 기존 값이 비어 있는 경우만
    # 사용자 추가 답변으로 채운다.

    if (
        not structure.situation
        and followup.situation
    ):
        structure.situation = (
            followup.situation
        )

    if (
        not structure.problem
        and followup.problem
    ):
        structure.problem = (
            followup.problem
        )

    if (
        not structure.action
        and followup.action
    ):
        structure.action = (
            followup.action
        )

    if (
        not structure.result
        and followup.result
    ):
        structure.result = (
            followup.result
        )

    if (
        not structure.meaning
        and followup.meaning
    ):
        structure.meaning = (
            followup.meaning
        )

    db.commit()
    db.refresh(structure)

    return {
        "message":
            "추가 답변 반영 성공",

        "structure": {
            "id":
                structure.id,

            "situation":
                structure.situation,

            "problem":
                structure.problem,

            "action":
                structure.action,

            "result":
                structure.result,

            "meaning":
                structure.meaning
        }
    }


# --------------------------------------------------
# AI 초안 작성
# --------------------------------------------------

@app.post(
    "/api/documents/{document_id}/draft-ai"
)
def create_ai_draft(
    document_id: int,
    db: Session = Depends(get_db)
):
    document = (
        db.query(models.Document)
        .filter(
            models.Document.id == document_id
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="해당 문서를 찾을 수 없습니다."
        )

    thoughts = (
        db.query(models.Thought)
        .filter(
            models.Thought.document_id
            == document_id
        )
        .order_by(models.Thought.id)
        .all()
    )

    if not thoughts:
        raise HTTPException(
            status_code=400,
            detail="초안을 작성할 생각이 없습니다."
        )

    thought_text = "\n".join(
        f"- {thought.content}"
        for thought in thoughts
    )

    try:
        draft_content = create_draft_with_ai(
            thought_text,
            document.document_type
        )

    except Exception as error:
        print(
            "CLOVA 초안 작성 오류:",
            error
        )

        raise HTTPException(
            status_code=502,
            detail="AI 초안 작성에 실패했습니다."
        )

    return {
        "message":
            "AI 초안 작성 성공",

        "document_id":
            document_id,

        "content":
            draft_content
    }


# --------------------------------------------------
# Draft 저장
# 버전 번호는 백엔드가 자동 계산
# --------------------------------------------------

@app.post("/api/drafts")
def create_draft(
    draft: DraftCreate,
    db: Session = Depends(get_db)
):
    document = (
        db.query(models.Document)
        .filter(
            models.Document.id
            == draft.document_id
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="해당 문서를 찾을 수 없습니다."
        )

    latest_draft = (
        db.query(models.Draft)
        .filter(
            models.Draft.document_id
            == draft.document_id
        )
        .order_by(
            models.Draft.version.desc()
        )
        .first()
    )

    if latest_draft:
        next_version = (
            latest_draft.version + 1
        )

    else:
        next_version = 1

    new_draft = models.Draft(
        document_id=draft.document_id,
        content=draft.content,
        version=next_version
    )

    db.add(new_draft)
    db.commit()
    db.refresh(new_draft)

    return new_draft


@app.get(
    "/api/documents/{document_id}/drafts"
)
def get_document_drafts(
    document_id: int,
    db: Session = Depends(get_db)
):
    drafts = (
        db.query(models.Draft)
        .filter(
            models.Draft.document_id
            == document_id
        )
        .order_by(
            models.Draft.version
        )
        .all()
    )

    return drafts