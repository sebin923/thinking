"""기존 화면의 별점 요청을 서버에 저장한다. 토큰이 없는 요청은 익명이다."""
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from routers.auth import bearer_scheme, get_current_user

router = APIRouter(prefix="/api/ai-ratings", tags=["AI Ratings"])

def optional_rating_user(request: Request, credentials=Depends(bearer_scheme), db: Session = Depends(get_db)):
    # 기존 프론트는 인증 헤더를 보내지 않는다. 문서 번호로 작성자를 추정하지 않는다.
    if credentials is None and not request.headers.get("Authorization"):
        return None
    return get_current_user(credentials, db)


@router.post("", response_model=dict)
def save_ai_rating(data: schemas.AiRatingCreate, db: Session = Depends(get_db),
                   user=Depends(optional_rating_user)):
    rating = models.AiRating(
        id=uuid4().hex,
        user_id=str(user.user_id) if user is not None else "guest",
        kind=data.kind,
        model=data.model,
        rating=data.rating,
        comment=(data.comment or "").strip(),
        # 클라이언트가 보낸 참고 값이며 문서 조회·소유권 판단에는 사용하지 않는다.
        document_id=str(data.documentId) if data.documentId is not None else None,
        result_text=data.resultText or "",
        request_text=data.requestText or "",
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    try:
        db.add(rating)
        db.commit()
        db.refresh(rating)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(503, "평가를 서버에 저장하지 못했어요. 잠시 후 다시 시도해 주세요.") from exc
    return {
        "success": True,
        "data": {
            "id": rating.id,
            "kind": rating.kind,
            "model": rating.model,
            "rating": rating.rating,
            "comment": rating.comment,
            "documentId": rating.document_id,
            "resultText": rating.result_text,
            "requestText": rating.request_text,
            "createdAt": rating.created_at,
        }
    }
