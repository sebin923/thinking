# =============================================================
# security.py — 보안 관련 기능 모음
# -------------------------------------------------------------
#  1. 비밀번호 암호화(해시) / 비교      → bcrypt
#  2. 로그인 토큰(JWT) 만들기 / 풀기    → PyJWT
#  3. 이메일 인증번호 만들기 / 해시      → secrets, hashlib
#
# ※ "해시"란?
#   비밀번호를 정해진 규칙으로 뒤섞어서 원래 값으로 되돌릴 수 없는 글자로 바꾸는 것.
#   로그인할 때는 입력한 비밀번호를 똑같이 해시해서 저장된 값과 "비교"만 함.
#   그래서 DB가 유출돼도 원래 비밀번호는 알 수 없음.
#   bcrypt는 일부러 느리게(수천 번 반복) 계산해서 무작위 대입 공격도 어렵게 만든 해시 방식.
#
# 필요한 패키지: pip install bcrypt PyJWT
# =============================================================

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from dotenv import load_dotenv

# .env 파일의 값을 환경변수로 불러오기
load_dotenv()

# -------------------------------------------------------------
# 설정값
# -------------------------------------------------------------

# JWT 서명에 쓰는 비밀 키 (이 키를 아는 서버만 토큰을 만들고 검증할 수 있음)
# ★ .env에 JWT_SECRET_KEY를 꼭 넣기! (팀원 모두 같은 값, Git에는 절대 올리지 않기)
#   만드는 법: python -c "import secrets; print(secrets.token_urlsafe(48))"
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    # 키가 없으면 임시 키를 만들어서라도 실행되게 함
    # (단, 서버를 껐다 켜면 키가 바뀌어서 이전 로그인 토큰이 전부 무효가 됨)
    JWT_SECRET_KEY = secrets.token_urlsafe(48)
    print("[경고] .env에 JWT_SECRET_KEY가 없어서 임시 키를 사용합니다. 서버를 재시작하면 로그인이 풀려요.")

JWT_ALGORITHM = "HS256"  # 토큰 서명 방식

# 로그인 토큰 유효 시간 (분). .env에 없으면 120분(2시간)
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))

# bcrypt 반복 강도 (숫자가 1 커질 때마다 계산 시간이 2배). 12가 일반적인 권장값
BCRYPT_ROUNDS = 12


# -------------------------------------------------------------
# 1. 비밀번호 해시
# -------------------------------------------------------------

def hash_password(password: str) -> str:
    """비밀번호 → bcrypt 해시 문자열 (회원가입할 때 사용)"""
    # bcrypt는 글자가 아니라 바이트를 다뤄서 encode()로 바꿈
    # gensalt(): 비밀번호마다 다른 "소금(salt)"을 섞음
    #   → 같은 비밀번호라도 사람마다 해시 결과가 달라서, 미리 계산한 표로 역추적하는 공격을 막음
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS))
    return hashed.decode("utf-8")  # DB에 글자로 저장하려고 다시 문자열로


def verify_password(password: str, password_hash: str) -> bool:
    """입력한 비밀번호가 저장된 해시와 맞는지 확인 (로그인할 때 사용)"""
    try:
        # checkpw: 저장된 해시 안에 들어 있는 salt로 입력값을 똑같이 해시해서 비교
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # 해시 형식이 이상하거나 비밀번호가 너무 길면(72바이트 초과) 그냥 불일치로 처리
        return False


# 존재하지 않는 아이디로 로그인할 때 비교용으로 쓰는 가짜 해시
# → 아이디가 없을 때도 bcrypt 계산을 똑같이 해서, 응답 속도 차이로 "이 아이디는 있다/없다"를
#   알아내는 공격(타이밍 공격)을 막음
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(16))


# -------------------------------------------------------------
# 2. 로그인 토큰 (JWT)
# -------------------------------------------------------------

def create_access_token(user_id: int, login_id: str) -> str:
    """로그인 성공한 사용자에게 줄 토큰 만들기
    토큰 안에는 누구인지(sub)와 만료 시각(exp)이 들어 있고, 비밀 키로 서명돼서 위조가 불가능
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),  # subject: 토큰 주인 (JWT 규칙상 문자열)
        "login_id": login_id,
        "iat": now,  # issued at: 발급 시각
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),  # 만료 시각
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """토큰을 풀어서 내용(payload)을 돌려줌. 위조됐거나 만료됐으면 None"""
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


# -------------------------------------------------------------
# 3. 이메일 인증번호
# -------------------------------------------------------------

def generate_verification_code() -> str:
    """6자리 숫자 인증번호 만들기 (예: "048213")
    secrets: 보안용 난수 (random 모듈보다 예측하기 어려움)
    """
    # randbelow(1_000_000): 0 ~ 999999 중 하나 / :06d → 6자리가 안 되면 앞을 0으로 채움
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_verification_code(email: str, code: str) -> str:
    """인증번호를 DB에 저장할 해시값으로 바꾸기
    이메일 + 비밀 키를 같이 섞어서(HMAC), 6자리 숫자 표를 미리 만들어 역추적하는 것도 막음
    """
    message = f"{email}:{code}".encode("utf-8")
    return hmac.new(JWT_SECRET_KEY.encode("utf-8"), message, hashlib.sha256).hexdigest()


def is_same_hash(a: str, b: str) -> bool:
    """두 해시가 같은지 비교 (compare_digest: 비교 시간이 항상 같아서 타이밍 공격 방지)"""
    return hmac.compare_digest(a, b)
