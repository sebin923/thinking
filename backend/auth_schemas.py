# =============================================================
# auth_schemas.py — 회원가입/로그인 요청·응답 데이터 모양과 검사 규칙 (Pydantic)
# (퀴즈·랭킹용 스키마는 schemas.py에 따로 있음 → 팀원 파일과 안 겹치게 분리)
# -------------------------------------------------------------
# 프론트에서 보낸 JSON이 여기 정의한 모양과 규칙에 맞는지 FastAPI가 자동으로 검사함
# → 규칙에 안 맞으면 함수가 실행되기도 전에 422 에러를 돌려줌
#
# ★ 프론트(frontend/src/utils/validation.js)와 같은 규칙을 씀
#   브라우저 검사는 우회할 수 있어서, 서버에서 한 번 더 검사하는 게 필수!
#   규칙을 바꾸면 양쪽을 같이 바꿔야 함
#
# Spring의 DTO + @Valid 와 같은 역할
# =============================================================

import re

# BaseModel: 데이터 모양을 정의하는 기본 클래스
# EmailStr: 이메일 형식을 자동으로 검사해주는 타입 (email-validator 패키지 필요 — fastapi[standard]에 포함)
# field_validator: 칸 하나에 대한 검사 함수를 붙이는 장식자
# ConfigDict: 모델 설정
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

# ----- 검사 규칙 (정규표현식) -----
LOGIN_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{3,19}$")  # 소문자로 시작, 4~20자
PHONE_PATTERN = re.compile(r"^01[016789][0-9]{7,8}$")  # 010으로 시작하는 10~11자리
CODE_PATTERN = re.compile(r"^[0-9]{6}$")  # 숫자 6자리


# ----- 여러 스키마에서 같이 쓰는 검사 함수 -----

def check_login_id(value: str) -> str:
    value = value.strip().lower()
    if not LOGIN_ID_PATTERN.match(value):
        # ValueError를 던지면 Pydantic이 422 에러로 바꿔서 프론트에 알려줌
        raise ValueError("아이디는 영문 소문자로 시작하는 4~20자(소문자, 숫자, _)로 입력해 주세요.")
    return value


def normalize_email(value: str) -> str:
    """이메일을 소문자로 통일 (A@Gmail.com 과 a@gmail.com 을 같은 사람으로 보기 위해)"""
    return value.strip().lower()


def check_password(value: str) -> str:
    """비밀번호 규칙 (회원가입·비밀번호 재설정이 같이 씀)"""
    if not 8 <= len(value) <= 64:
        raise ValueError("비밀번호는 8~64자로 입력해 주세요.")
    # any(): 하나라도 조건에 맞으면 True
    if not any(c.isascii() and c.isalpha() for c in value) or not any(c.isdigit() for c in value):
        raise ValueError("비밀번호는 영문과 숫자를 모두 포함해야 해요.")
    if any(c.isspace() for c in value):
        raise ValueError("비밀번호에 공백은 넣을 수 없어요.")
    # bcrypt는 72바이트까지만 처리할 수 있음 (한글은 한 글자에 3바이트라 길면 넘을 수 있음)
    if len(value.encode("utf-8")) > 72:
        raise ValueError("비밀번호가 너무 길어요. 조금 짧게 입력해 주세요.")
    return value


def check_code(value: str) -> str:
    """인증번호 6자리 숫자 검사"""
    value = value.strip()
    if not CODE_PATTERN.match(value):
        raise ValueError("인증번호 6자리 숫자를 입력해 주세요.")
    return value


# =============================================================
# 요청(Request) 스키마: 프론트 → 서버
# =============================================================

class SendCodeRequest(BaseModel):
    """인증번호 보내기 요청 { "email": "..." }"""

    email: EmailStr

    # mode="after": EmailStr 형식 검사가 끝난 다음에 실행
    @field_validator("email", mode="after")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return normalize_email(value)


class VerifyCodeRequest(BaseModel):
    """인증번호 확인 요청 { "email": "...", "code": "123456" }"""

    email: EmailStr
    code: str

    @field_validator("email", mode="after")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("code")
    @classmethod
    def check_code(cls, value: str) -> str:
        value = value.strip()
        if not CODE_PATTERN.match(value):
            raise ValueError("인증번호 6자리 숫자를 입력해 주세요.")
        return value


class SignupRequest(BaseModel):
    """회원가입 요청"""

    login_id: str
    password: str
    name: str
    phone: str
    email: EmailStr

    @field_validator("login_id")
    @classmethod
    def validate_login_id(cls, value: str) -> str:
        return check_login_id(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return check_password(value)  # 규칙은 위의 check_password (비밀번호 재설정과 같이 씀)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not 2 <= len(value) <= 20:
            raise ValueError("이름은 2~20자로 입력해 주세요.")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        digits = re.sub(r"\D", "", value)  # 숫자만 남기기 (하이픈이 와도 괜찮게)
        if not PHONE_PATTERN.match(digits):
            raise ValueError("휴대전화 번호를 정확히 입력해 주세요.")
        return digits

    @field_validator("email", mode="after")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return normalize_email(value)


class LoginRequest(BaseModel):
    """로그인 요청 { "login_id": "...", "password": "..." }
    로그인은 형식 검사를 자세히 하지 않음 (틀리면 그냥 "불일치"로 응답)
    """

    login_id: str
    password: str

    @field_validator("login_id")
    @classmethod
    def lower_login_id(cls, value: str) -> str:
        return value.strip().lower()


# =============================================================
# 아이디 찾기 / 비밀번호 재설정 요청 (routers/auth.py 아래쪽 API)
# -------------------------------------------------------------
# 아이디 찾기:  이름 + 이메일 → 인증번호 → 확인하면 아이디를 알려줌
# 비밀번호 찾기: 아이디 + 이메일 → 인증번호 → 확인 → 새 비밀번호 저장
# =============================================================

class FindIdSendCodeRequest(BaseModel):
    """아이디 찾기 인증번호 받기 { "name": "한세빈", "email": "..." }"""

    name: str
    email: EmailStr

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("이름을 입력해 주세요.")
        return value

    @field_validator("email", mode="after")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return normalize_email(value)


class FindIdVerifyRequest(FindIdSendCodeRequest):
    """아이디 찾기 인증번호 확인 (받기 요청 + code)"""

    code: str

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        return check_code(value)


class ResetSendCodeRequest(BaseModel):
    """비밀번호 재설정 인증번호 받기 { "login_id": "sebin", "email": "..." }"""

    login_id: str
    email: EmailStr

    @field_validator("login_id")
    @classmethod
    def lower_login_id(cls, value: str) -> str:
        value = value.strip().lower()
        if not value:
            raise ValueError("아이디를 입력해 주세요.")
        return value

    @field_validator("email", mode="after")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return normalize_email(value)


class ResetVerifyRequest(ResetSendCodeRequest):
    """비밀번호 재설정 인증번호 확인 (받기 요청 + code)"""

    code: str

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        return check_code(value)


class ResetPasswordRequest(ResetVerifyRequest):
    """새 비밀번호 저장 (확인 요청 + new_password)
    인증번호(code)도 다시 보냄 → 서버가 "그 인증번호로 인증을 마친 사람"인지 한 번 더 확인
    """

    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return check_password(value)


# =============================================================
# 응답(Response) 스키마: 서버 → 프론트
# =============================================================

class UserOut(BaseModel):
    """프론트에 돌려줄 사용자 정보 (★ password_hash는 절대 포함하지 않음)"""

    # from_attributes=True: SQLAlchemy 모델 객체(User)를 그대로 넣어도 알아서 변환
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    login_id: str
    name: str
    email: str
    # 역할: "general"(일반) / "admin"(관리자) → 프론트가 이 값을 보고 헤더에 "관리자" 버튼을 보여줌
    # (예전 회원은 비어 있을 수 있어서 None도 허용, 비어 있으면 일반 회원으로 봄)
    role: str | None = "general"


class MessageResponse(BaseModel):
    message: str


class CheckLoginIdResponse(BaseModel):
    available: bool
    message: str


class SendCodeResponse(BaseModel):
    message: str
    expires_in: int  # 인증번호 유효 시간(초)
    dev_mode: bool  # True면 메일 대신 터미널에 인증번호 출력


class VerifyCodeResponse(BaseModel):
    message: str
    verified: bool


class SignupResponse(BaseModel):
    message: str
    user: UserOut


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class FindIdResponse(BaseModel):
    """아이디 찾기 결과 (이메일 인증을 마친 본인에게만 알려줌)"""

    message: str
    login_id: str
    created_at: datetime | None = None  # 가입일 (화면에 "2026.11.03 가입"처럼 보여줌)
