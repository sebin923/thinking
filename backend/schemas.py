from datetime import datetime
from typing import List, Optional, Any, Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

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
    category: str        # 'spelling' 또는 'grammar'
    question: str        # 문제 내용
    options: List[Any]    # 보기 목록
    answer: str           # 정답
    explanation: Optional[str] = None # 정답 및 해설
    level: Optional[str] = None       # 난이도 'easy'(하) / 'medium'(중) / 'hard'(상), 맞춤법은 None

class QuizCreate(QuizBase):
    pass

class QuizResponse(QuizBase):
    quiz_id: int
    created_at: Optional[datetime] = None 

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
    elapsed_time: float = 0.0

class RankingResponse(BaseModel):
    ranking_id: int
    user_id: int
    nickname: Optional[str] = None
    category: str
    score: int
    elapsed_time: float
    challenged_at: datetime

    class Config:
        from_attributes = True


# --- AI 결과 별점 평가 스키마 ---
class AiRatingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["draft", "feedback"]
    model: Literal["common", "personal"]
    rating: StrictInt = Field(ge=1, le=5)
    comment: Optional[str] = Field("", max_length=100)
    documentId: str | int | None = None
    resultText: Optional[str] = Field("", max_length=2000)
    requestText: Optional[str] = Field("", max_length=2000)

    @field_validator("documentId", mode="before")
    @classmethod
    def validate_document_id(cls, value):
        if value is None:
            return None
        if type(value) is int:
            if value <= 0 or len(str(value)) > 50:
                raise ValueError("문서 번호를 확인해 주세요.")
            return value
        if isinstance(value, str):
            value = value.strip()
            if len(value) > 50:
                raise ValueError("문서 번호는 50자 이하여야 합니다.")
            return value or None
        raise ValueError("문서 번호는 문자열이나 양의 정수여야 합니다.")

class AiRatingResponse(BaseModel):
    id: str
    kind: str
    model: str
    rating: int
    comment: Optional[str] = ""
    documentId: Optional[Any] = None
    resultText: Optional[str] = ""
    requestText: Optional[str] = ""
    createdAt: str

    class Config:
        from_attributes = True
