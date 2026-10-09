from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base  # database.py에서 설정한 Base를 임포트한다고 가정합니다.

def utc_now():
    """지금 시각(UTC 기준)을 돌려주는 함수. 생성 시각 기본값으로 씀"""
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    # 회원가입에서 닉네임은 안 받아서 비어 있어도 되게 nullable=True로 변경
    # (비어 있으면 화면·랭킹에서는 name을 대신 보여주면 됨)
    nickname = Column(String(50), nullable=True)
    role = Column(String(20), default="general") # general(일반), admin(관리자)
    created_at = Column(DateTime, default=datetime.utcnow)

    # ----- 회원가입 / 로그인용 칸 (routers/auth.py 에서 사용) -----
    # 로그인 아이디 (unique: 중복 불가, index: 검색 빠르게)
    login_id = Column(String(20), unique=True, index=True, nullable=False)
    # ★ 비밀번호 원문이 아니라 bcrypt로 암호화(해시)한 값만 저장 → 원래 비밀번호로 되돌릴 수 없음
    password_hash = Column(String(255), nullable=False)
    # 이름
    name = Column(String(20), nullable=False)
    # 전화번호: 하이픈 없이 숫자만 (예: "01012345678")
    phone = Column(String(11), nullable=False)
    # 이메일 인증을 마쳤는지 (가입은 인증해야만 되니까 가입하면 항상 True)
    email_verified = Column(Boolean, nullable=False, default=False)

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


class EmailVerification(Base):
    """이메일 인증번호 기록 테이블 (회원가입용)
    인증번호를 보낼 때마다 한 줄씩 생기고, 회원가입이 끝나면 지움
    """

    __tablename__ = "email_verifications"

    id = Column(Integer, primary_key=True, index=True)
    # 인증번호를 보낸 이메일
    email = Column(String(255), nullable=False, index=True)
    # ★ 인증번호도 원문 대신 해시값으로 저장 (DB가 털려도 인증번호를 알 수 없게)
    code_hash = Column(String(64), nullable=False)
    # 인증번호 만료 시각 (보낸 시각 + 5분)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    # 틀리게 입력한 횟수 (5번 넘으면 다시 받아야 함)
    attempts = Column(Integer, nullable=False, default=0)
    # 인증에 성공한 시각 (아직이면 None)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class AIFeedback(Base):
    __tablename__ = "ai_feedbacks"

    id = Column(Integer, primary_key=True, index=True)

    draft_id = Column(
        Integer,
        ForeignKey("drafts.id", ondelete="CASCADE"),
        nullable=False
    )

    feedback_data = Column(JSON, nullable=False)

    created_at = Column(
        DateTime,
        server_default=func.now()
    )

    draft = relationship("Draft")
