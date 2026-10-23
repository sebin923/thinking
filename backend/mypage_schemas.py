# =============================================================
# mypage_schemas.py — 마이페이지 API가 주고받는 데이터 모양 정의
# -------------------------------------------------------------
# 스키마(schema) = "이 API는 이런 모양의 데이터만 받고, 이런 모양으로 돌려준다"는 약속
# Pydantic이 들어온 JSON을 자동으로 검사해서, 규칙에 안 맞으면
# 함수가 실행되기도 전에 422 에러로 돌려보냄
#
# 회원가입(auth_schemas.py)과 같은 규칙(이름 2~20자, 비밀번호 8자 이상 등)을
# 그대로 써야 하니까, 검사 함수는 여기에 따로 모아 두고 각 스키마에서 불러 씀
# =============================================================

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

# 휴대전화 번호 규칙은 회원가입과 똑같이 쓰려고 auth_schemas.py에서 가져옴
from auth_schemas import PHONE_PATTERN, normalize_email


# ===================== 공통 검사 함수 =====================
# (회원가입 SignupRequest의 검사 규칙과 똑같이 맞춤)


def check_name(value: str) -> str:
    """이름: 앞뒤 공백을 지우고 2~20자인지 확인"""
    value = value.strip()
    if not 2 <= len(value) <= 20:
        raise ValueError("이름은 2~20자로 입력해 주세요.")
    return value


def check_phone(value: str) -> str:
    """전화번호: 숫자만 남긴 뒤 010-xxxx-xxxx 형식인지 확인 (하이픈이 와도 괜찮게)"""
    digits = re.sub(r"\D", "", value)  # \D: 숫자가 아닌 글자 → 전부 지움
    if not PHONE_PATTERN.match(digits):
        raise ValueError("휴대전화 번호를 정확히 입력해 주세요.")
    return digits


def check_new_password(value: str) -> str:
    """새 비밀번호: 8~64자, 영문+숫자 포함, 공백 없음"""
    if not 8 <= len(value) <= 64:
        raise ValueError("비밀번호는 8~64자로 입력해 주세요.")
    # isascii() and isalpha(): 영어 알파벳인지 / isdigit(): 숫자인지
    if not any(c.isascii() and c.isalpha() for c in value) or not any(c.isdigit() for c in value):
        raise ValueError("비밀번호는 영문과 숫자를 모두 포함해야 해요.")
    if any(c.isspace() for c in value):
        raise ValueError("비밀번호에 공백은 넣을 수 없어요.")
    # bcrypt는 72바이트까지만 쓰기 때문에 그보다 길면 막음 (한글은 한 글자에 3바이트)
    if len(value.encode("utf-8")) > 72:
        raise ValueError("비밀번호가 너무 길어요. 조금 짧게 입력해 주세요.")
    return value


# ===================== 요청(프론트 → 서버) =====================


class ProfileUpdateRequest(BaseModel):
    """회원정보 수정 요청 { "name": "...", "phone": "...", "email": "..." }
    - 이메일을 바꾸는 경우에는 새 이메일로 인증을 먼저 마쳐야 함 (서버에서 확인)
    - 아이디는 바꿀 수 없음 (로그인 기준이라서)
    """

    name: str
    phone: str
    email: EmailStr  # EmailStr: 이메일 형식이 아니면 자동으로 거절

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return check_name(value)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return check_phone(value)

    @field_validator("email", mode="after")
    @classmethod
    def lower_email(cls, value: str) -> str:
        # 대소문자를 통일해서 저장 (A@Gmail.com 과 a@gmail.com 을 같은 이메일로 보기 위해)
        return normalize_email(value)


class PasswordChangeRequest(BaseModel):
    """비밀번호 변경 요청 { "current_password": "...", "new_password": "..." }"""

    current_password: str  # 지금 비밀번호 (본인 확인용 → 형식 검사는 안 함)
    new_password: str  # 새 비밀번호 (회원가입과 같은 규칙으로 검사)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return check_new_password(value)


class WithdrawRequest(BaseModel):
    """회원 탈퇴 요청 { "password": "..." }
    실수로 탈퇴하거나, 잠깐 자리를 비운 사이 남이 탈퇴시키는 걸 막으려고 비밀번호를 한 번 더 받음
    """

    password: str


# ===================== 응답(서버 → 프론트) =====================


class ProfileOut(BaseModel):
    """마이페이지 프로필 카드에 보여줄 정보 (★ password_hash는 절대 포함하지 않음)"""

    # from_attributes=True: DB 모델(User) 객체를 그대로 넣어도 칸 이름을 맞춰서 읽어 줌
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    login_id: str
    name: str
    email: str
    phone: str
    created_at: datetime | None = None  # 가입일 (예전 데이터는 비어 있을 수도 있어서 None 허용)

    # ----- 활동 요약 (User 테이블에는 없고, 라우터에서 세어서 채워 넣음) -----
    document_count: int = 0  # 내가 쓴 글 수
    completed_count: int = 0  # 그중 "완료"된 글 수
    best_challenge_score: int = 0  # 맞춤법 도전 모드 최고 기록 (연속 정답 수)


class MyVersionOut(BaseModel):
    """글 하나의 저장본 하나 (마이페이지 단계 탭에 한 장씩 보여줄 카드)"""

    version: int  # 몇 번째 저장인지 (1, 2, 3...)
    # 이 저장본이 들어갈 단계 탭
    #  - "초안": 첫 번째 저장본
    #  - "수정": 두 번째 저장본부터 (글마다 최근 3개까지만 남김)
    #  - "완료": 최종 저장한 저장본
    kind: str
    created_at: datetime | None = None  # 저장한 시각
    preview: str = ""  # 이 저장본 앞부분 미리보기


class MyDocumentOut(BaseModel):
    """'내가 쓴 글' 목록의 한 줄"""

    id: int
    title: str
    document_type: str  # 글 유형 (자기소개서, 리포트 등)
    status: str  # DB에 저장된 상태: "작성중" 또는 "완료"
    # 마이페이지에 보여줄 단계: "초안" / "수정" / "완료" (status와 저장 횟수로 서버가 계산해서 채움)
    stage: str = "초안"
    created_at: datetime | None = None
    updated_at: datetime | None = None
    latest_version: int = 0  # 마지막으로 저장한 버전 번호 (저장한 적 없으면 0)
    preview: str = ""  # 마지막 저장본 앞부분 미리보기 (최대 120자)
    # 이 글의 저장본들 (오래된 것부터) → 마이페이지에서 초안/수정/완료 탭을 누르면 저장본 하나하나가 카드로 보임
    versions: list[MyVersionOut] = []


class ProfileUpdateResponse(BaseModel):
    message: str
    profile: ProfileOut
