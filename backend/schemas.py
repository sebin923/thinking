from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel

# --- 사용자 관련 스키마 ---
class UserBase(BaseModel):
    email: str
    nickname: str
    role: Optional[str] = "general"

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- 퀴즈 관련 스키마 ---
class QuizBase(BaseModel):
    category: str         # 'spelling' 또는 'grammar'
    question: str         # 문제 내용
    options: List[Any]    # 보기 목록
    answer: str           # 정답
    explanation: Optional[str] = None # 정답 및 해설

class QuizCreate(QuizBase):
    pass

class QuizResponse(QuizBase):
    quiz_id: int
    created_at: Optional[datetime] = None  # 이 부분 수정

    class Config:
        from_attributes = True


# --- 퀴즈 풀이 및 제출 스키마 ---
class QuizSubmitRequest(BaseModel):
    user_id: int
    quiz_id: int
    user_answer: str

class QuizSubmitResponse(BaseModel):
    result_id: int
    is_correct: bool
    correct_answer: str
    explanation: Optional[str] = None


# --- 오답 복습 응답 스키마 ---
class IncorrectQuizResponse(BaseModel):
    result_id: int
    quiz_id: int
    question: str
    options: List[Any]
    correct_answer: str
    user_answer: str
    explanation: Optional[str] = None
    solved_at: datetime

    class Config:
        from_attributes = True


# --- 랭킹 관련 스키마 (category 추가) ---
class RankingSubmitRequest(BaseModel):
    user_id: int
    category: str = "spelling" # 기본값 spelling (맞춤법 랭킹 도전용)
    score: int

class RankingResponse(BaseModel):
    ranking_id: int
    user_id: int
    nickname: Optional[str] = None
    category: str
    score: int
    challenged_at: datetime

    class Config:
        from_attributes = True