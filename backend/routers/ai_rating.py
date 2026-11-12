import time
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db

router = APIRouter(prefix="/api/ai-ratings", tags=["AI Ratings"])

@router.post("", response_model=dict)
def save_ai_rating(
    data: schemas.AiRatingCreate, 
    db: Session = Depends(get_db)
):
    # 1. 별점 1~5 정수 유효성 검증
    if not (1 <= data.rating <= 5):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="별점을 1~5개 중에서 골라 주세요."
        )

    # 2. 고유 ID 생성 (타임스탬프 + 랜덤 문자열)
    rating_id = f"{int(time.time() * 1000)}-{int(time.time() % 1000)}"

    # 3. DB 모델 객체 생성 (데이터 길이 제한 적용)
    new_rating = models.AiRating(
        id=rating_id,
        user_id="guest",  # 로그인 사용자 정보 연동 시 해당 유저 ID로 변경 가능
        kind=data.kind,
        model=data.model,
        rating=data.rating,
        comment=(data.comment or "").strip()[:100],
        document_id=str(data.documentId) if data.documentId is not None else None,
        result_text=(data.resultText or "")[:2000],
        request_text=(data.requestText or "")[:2000],
        created_at=datetime.utcnow().isoformat()
    )

    # 4. 데이터베이스 저장
    try:
        db.add(new_rating)
        db.commit()
        db.refresh(new_rating)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="평가를 저장하지 못했어요. 잠시 후 다시 시도해 주세요."
        )

    # 5. 프론트엔드가 기대하는 성공 응답 포맷 반환
    return {
        "success": True,
        "data": {
            "id": new_rating.id,
            "kind": new_rating.kind,
            "model": new_rating.model,
            "rating": new_rating.rating,
            "comment": new_rating.comment,
            "documentId": new_rating.document_id,
            "resultText": new_rating.result_text,
            "requestText": new_rating.request_text,
            "createdAt": new_rating.created_at
        }
    }