"""학습 후보 전용 테이블. 기존 문서·평가 모델을 변경하지 않는다."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, UniqueConstraint
from database import Base

def now():
    return datetime.now(timezone.utc)

class TrainingCandidate(Base):
    __tablename__ = 'training_candidates'
    __table_args__ = (UniqueConstraint('user_id', 'sample_hash'),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False, index=True)
    sample_hash = Column(String(64), nullable=False)
    source = Column(JSON, nullable=False)
    answer = Column(Text, nullable=False)
    assessment = Column(JSON, nullable=False)
    score = Column(Integer, nullable=False)
    consent = Column(Boolean, nullable=False, default=True)
    consent_version = Column(String(50), nullable=False, default='common-training-v1')
    consent_at = Column(DateTime(timezone=True), nullable=False, default=now)
    status = Column(String(20), nullable=False, default='pending', index=True)
    revision = Column(Integer, nullable=False, default=1)
    training_context = Column(Text, nullable=False, default='')
    synthetic = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)

class TrainingReview(Base):
    __tablename__ = 'training_reviews'
    id = Column(Integer, primary_key=True)
    candidate_id = Column(Integer, ForeignKey('training_candidates.id', ondelete='CASCADE'), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True)
    event = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)

class TrainingSplit(Base):
    __tablename__ = 'training_split_registry'
    key = Column(String(80), primary_key=True)
    split = Column(String(10), nullable=False)

class TrainingExport(Base):
    __tablename__ = 'training_exports'
    id = Column(String(32), primary_key=True)
    created_by = Column(Integer, ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True)
    manifest = Column(JSON, nullable=False)
    payload = Column(JSON, nullable=False)
    revoked = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)

class TrainingRun(Base):
    __tablename__ = 'training_runs'
    id = Column(Integer, primary_key=True)
    export_id = Column(String(32), ForeignKey('training_exports.id'), nullable=False)
    created_by = Column(Integer, ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True)
    details = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
