
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import User, UserWritingPreference
from routers.auth import get_current_user


router = APIRouter(
    prefix="/api/writing",
    tags=["Writing Preferences"]
)


class PreferenceInput(BaseModel):
    preferred_tone: Literal[
        "natural", "formal", "confident"
    ] = "natural"

    sentence_length: Literal[
        "short", "normal", "long"
    ] = "normal"

    feedback_style: Literal[
        "brief", "detailed"
    ] = "detailed"

    ai_assistance: Literal[
        "guided", "balanced", "draft"
    ] = "balanced"


# 기본 취향 설정
DEFAULT_PREFERENCES = PreferenceInput()


def preference_response(user_id, preference):
    return {
        "user_id": user_id,
        **preference.model_dump()
    }


# 내 글쓰기 취향 조회
@router.get("/preferences")
def get_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    saved = db.query(UserWritingPreference).filter(
        UserWritingPreference.user_id == current_user.user_id
    ).first()

    if saved is None:
        return preference_response(
            current_user.user_id,
            DEFAULT_PREFERENCES
        )

    return {
        "user_id": current_user.user_id,
        "preferred_tone": saved.preferred_tone,
        "sentence_length": saved.sentence_length,
        "feedback_style": saved.feedback_style,
        "ai_assistance": saved.ai_assistance
    }


# 내 글쓰기 취향 저장 또는 수정
@router.put("/preferences")
def save_preferences(
    request: PreferenceInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    saved = db.query(UserWritingPreference).filter(
        UserWritingPreference.user_id == current_user.user_id
    ).first()

    if saved is None:
        saved = UserWritingPreference(
            user_id=current_user.user_id
        )
        db.add(saved)

    saved.preferred_tone = request.preferred_tone
    saved.sentence_length = request.sentence_length
    saved.feedback_style = request.feedback_style
    saved.ai_assistance = request.ai_assistance

    try:
        db.commit()
        db.refresh(saved)
    except Exception:
        db.rollback()
        raise

    return {
        "message": "글쓰기 취향 저장 성공",
        "user_id": current_user.user_id,
        "preferred_tone": saved.preferred_tone,
        "sentence_length": saved.sentence_length,
        "feedback_style": saved.feedback_style,
        "ai_assistance": saved.ai_assistance
    }
