"""Topic preferences are separate from writing style and model training data."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String

from database import Base


class RecommendationProfile(Base):
    __tablename__ = "user_recommendation_profiles"
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    major = Column(String(80), nullable=False, default="")
    interests = Column(JSON, nullable=False, default=list)
    use_training_data = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class RecommendationHistory(Base):
    __tablename__ = "practice_recommendation_history"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    unit_id = Column(String(100), nullable=False)
    practice_id = Column(String(80), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))
