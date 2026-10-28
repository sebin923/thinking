# =============================================================
# admin_schemas.py — 관리자 페이지 API가 주고받는 데이터 모양 정의
# -------------------------------------------------------------
# 스키마(schema) = "이 API는 이런 모양의 데이터만 받고, 이런 모양으로 돌려준다"는 약속
# Pydantic이 들어온 JSON을 자동으로 검사해서, 규칙에 안 맞으면
# 함수가 실행되기도 전에 422 에러로 돌려보냄
#
# 관리자 페이지 구성 (기획서 그림 기준)
#   1. 퀴즈 관리: 문제·정답·해설 추가 / 수정 / 삭제
#   2. 회원 관리: 회원 조회 + 이용 상태(정상 / 정지) 관리
#   3. 랭킹 관리: 도전 점수·기록 조회 / 삭제
# =============================================================

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

# ----- 정해진 값 목록 -----
# Literal["a", "b"]: 이 두 값 말고 다른 값이 오면 Pydantic이 자동으로 422 에러를 냄
QuizCategory = Literal["spelling", "grammar"]  # 맞춤법 / 문법 (퀴즈 화면과 똑같은 이름)
UserStatus = Literal["active", "suspended"]  # 정상 / 이용 정지


# =============================================================
# 1. 퀴즈 관리
# =============================================================


class QuizIn(BaseModel):
    """퀴즈 추가·수정할 때 관리자가 보내는 값"""

    category: QuizCategory  # 맞춤법(spelling) 또는 문법(grammar)
    question: str  # 문제 내용 (예: "약속은 '____' 지켜야 한다.")
    options: list[str]  # 보기 목록 (예: ["반드시", "반듯이"])
    answer: str  # 정답 (보기 중 하나와 글자까지 똑같아야 함)
    explanation: str | None = None  # 해설 (없어도 됨)

    # ----- 문제: 앞뒤 공백 지우고, 비어 있거나 너무 길면 거절 -----
    @field_validator("question")
    @classmethod
    def check_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("문제를 입력해 주세요.")
        if len(value) > 500:
            raise ValueError("문제는 500자 이하로 입력해 주세요.")
        return value

    # ----- 보기: 빈 칸은 빼고, 2~6개, 같은 보기 중복 금지 -----
    @field_validator("options")
    @classmethod
    def check_options(cls, value: list[str]) -> list[str]:
        # 각 보기의 앞뒤 공백을 지우고, 빈 보기는 버림 (입력칸만 만들고 안 쓴 경우)
        cleaned = [option.strip() for option in value if option and option.strip()]
        if len(cleaned) < 2:
            raise ValueError("보기는 2개 이상 입력해 주세요.")
        if len(cleaned) > 6:
            raise ValueError("보기는 6개까지만 넣을 수 있어요.")
        # set: 중복을 없앤 묶음 → 개수가 줄었으면 같은 보기가 있었다는 뜻
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("같은 보기가 두 번 들어가 있어요.")
        return cleaned

    # ----- 해설: 빈 글자면 None으로 (DB에 빈 문자열 대신 "없음"으로 저장) -----
    @field_validator("explanation")
    @classmethod
    def check_explanation(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) > 1000:
            raise ValueError("해설은 1000자 이하로 입력해 주세요.")
        return value or None

    # ----- 정답이 보기 안에 있는지 (여러 칸을 같이 봐야 해서 model_validator 사용) -----
    # mode="after": 위의 칸별 검사가 다 끝난 뒤에 실행 → 이미 공백이 정리된 값으로 비교함
    @model_validator(mode="after")
    def check_answer_in_options(self):
        self.answer = self.answer.strip()
        if self.answer not in self.options:
            # 퀴즈 채점은 "고른 보기 == 정답" 글자 비교라서, 정답이 보기에 없으면 아무도 못 맞힘
            raise ValueError("정답은 보기 중 하나와 똑같아야 해요.")
        return self


class QuizOut(BaseModel):
    """관리자 퀴즈 목록의 한 줄"""

    # from_attributes=True: SQLAlchemy 모델 객체(Quiz)를 그대로 넣어도 알아서 변환
    model_config = ConfigDict(from_attributes=True)

    quiz_id: int
    category: str
    question: str
    options: list
    answer: str
    explanation: str | None = None
    created_at: datetime | None = None
    solved_count: int = 0  # 사용자들이 이 문제를 푼 횟수 (삭제할 때 참고용)


# =============================================================
# 2. 회원 관리
# =============================================================


class AdminUserOut(BaseModel):
    """관리자 회원 목록의 한 줄 (★ 비밀번호 해시는 절대 포함하지 않음)"""

    user_id: int
    login_id: str
    name: str
    email: str
    phone: str
    role: str  # "general"(일반) / "admin"(관리자)
    status: str  # "active"(정상) / "suspended"(정지)
    created_at: datetime | None = None  # 가입일
    document_count: int = 0  # 쓴 글 수
    ranking_count: int = 0  # 도전 기록 수
    best_score: int = 0  # 도전 최고 점수


class UserStatusIn(BaseModel):
    """회원 이용 상태 바꾸기"""

    status: UserStatus


# =============================================================
# 3. 랭킹 관리
# =============================================================


class AdminRankingOut(BaseModel):
    """관리자 랭킹 기록 목록의 한 줄 (도전 한 번 = 한 줄)"""

    ranking_id: int
    user_id: int
    login_id: str | None = None  # 탈퇴 등으로 회원이 없으면 None
    name: str | None = None
    category: str
    score: int
    elapsed_time: float = 0.0  # 걸린 시간(초)
    challenged_at: datetime | None = None
