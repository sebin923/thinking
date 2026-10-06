from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base  # database.py에서 설정한 Base를 임포트한다고 가정합니다.

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    nickname = Column(String(50), nullable=False)
    role = Column(String(20), default="general") # general(일반), admin(관리자)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 관계 설정
    quiz_results = relationship("QuizResult", back_populates="user")
    rankings = relationship("Ranking", back_populates="user")


class Quiz(Base):
    __tablename__ = "quizzes"

    quiz_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    category = Column(String(50), nullable=False)  # 'spelling'(맞춤법) 또는 'grammar'(문법)
    question = Column(Text, nullable=False)        # 문제 내용
    options = Column(JSON, nullable=False)         # 보기 목록 (JSON 형태: ["보기1", "보기2"])
    answer = Column(String(255), nullable=False)   # 정답
    explanation = Column(Text, nullable=True)      # 정답 및 해설
    created_at = Column(DateTime, default=datetime.utcnow)

    # 관계 설정
    quiz_results = relationship("QuizResult", back_populates="quiz")


class QuizResult(Base):
    __tablename__ = "quiz_results"

    result_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    quiz_id = Column(Integer, ForeignKey("quizzes.quiz_id"), nullable=False)
    is_correct = Column(Boolean, nullable=False)   # 정답 여부 (True/False)
    user_answer = Column(String(255), nullable=False) # 사용자가 제출한 답
    solved_at = Column(DateTime, default=datetime.utcnow)

    # 관계 설정
    user = relationship("User", back_populates="quiz_results")
    quiz = relationship("Quiz", back_populates="quiz_results")


class Ranking(Base):
    __tablename__ = "rankings"

    ranking_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    category = Column(String(50), default="spelling", nullable=False) # 맞춤법 랭킹 분리를 위한 카테고리
    score = Column(Integer, nullable=False)        # 랭킹 점수
    challenged_at = Column(DateTime, default=datetime.utcnow)

    # 관계 설정
    user = relationship("User", back_populates="rankings")
    
class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    document_type = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    status = Column(String(20), default="작성중")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Thought(Base):
    __tablename__ = "thoughts"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    document = relationship("Document")


class Draft(Base):
    __tablename__ = "drafts"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, server_default=func.now())

    document = relationship("Document")