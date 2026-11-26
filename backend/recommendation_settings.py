"""Authenticated profile endpoints, registered on the existing writing router."""
from fastapi import Depends
from pydantic import BaseModel, Field, StrictBool, field_validator
from sqlalchemy.orm import Session

from database import get_db
from models import User
from recommendation_profile import RecommendationProfile
from routers.auth import get_current_user


class RecommendationProfileInput(BaseModel):
    major: str = Field("", max_length=80)
    interests: list[str] = Field(default_factory=list, max_length=8)
    use_training_data: StrictBool = True

    @field_validator("major")
    @classmethod
    def clean_major(cls, value):
        return " ".join(value.split())

    @field_validator("interests")
    @classmethod
    def clean_interests(cls, values):
        result = []
        for value in values:
            value = " ".join(value.split())
            if not value or len(value) > 40:
                raise ValueError("관심사는 1~40자로 입력해 주세요.")
            if value not in result:
                result.append(value)
        return result


def response(row):
    return {"major": row.major, "interests": row.interests, "use_training_data": row.use_training_data}


def register_profile_routes(router):
    @router.get("/recommendation-profile")
    def get_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        row = db.get(RecommendationProfile, current_user.user_id)
        return response(row) if row else RecommendationProfileInput().model_dump()

    @router.put("/recommendation-profile")
    def save_profile(data: RecommendationProfileInput, current_user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
        row = db.get(RecommendationProfile, current_user.user_id)
        if row is None:
            row = RecommendationProfile(user_id=current_user.user_id)
            db.add(row)
        for key, value in data.model_dump().items():
            setattr(row, key, value)
        db.commit()
        return response(row)
