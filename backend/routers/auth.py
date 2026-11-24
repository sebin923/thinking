# =============================================================
# routers/auth.py — 회원가입 / 로그인 / 이메일 인증 API
# -------------------------------------------------------------
#   GET  /api/auth/check-login-id   아이디 중복 확인
#   POST /api/auth/email/send-code  이메일 인증번호 보내기
#   POST /api/auth/email/verify     이메일 인증번호 확인
#   POST /api/auth/signup           회원가입 (비밀번호 bcrypt 암호화 저장)
#   POST /api/auth/login            로그인 (아이디 + 비밀번호) → 토큰 발급
#   GET  /api/auth/me               토큰으로 내 정보 조회 (로그인 확인용)
#   POST /api/auth/find-id/send-code         아이디 찾기: 이름 + 이메일로 인증번호 보내기
#   POST /api/auth/find-id/verify            아이디 찾기: 인증번호 확인 → 아이디 알려줌
#   POST /api/auth/reset-password/send-code  비밀번호 찾기: 아이디 + 이메일로 인증번호 보내기
#   POST /api/auth/reset-password/verify     비밀번호 찾기: 인증번호 확인
#   POST /api/auth/reset-password            비밀번호 찾기: 새 비밀번호 저장
#
# APIRouter: 관련 있는 API들을 한 파일에 묶는 도구 (Spring의 @RestController 클래스와 비슷)
# main.py에서 app.include_router(auth.router)로 서버에 붙임
# =============================================================

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from email_service import send_verification_email
from models import EmailVerification, User
from auth_schemas import (
    LOGIN_ID_PATTERN,
    CheckLoginIdResponse,
    FindIdResponse,
    FindIdSendCodeRequest,
    FindIdVerifyRequest,
    MessageResponse,
    ResetPasswordRequest,
    ResetSendCodeRequest,
    ResetVerifyRequest,
    LoginRequest,
    LoginResponse,
    SendCodeRequest,
    SendCodeResponse,
    SignupRequest,
    SignupResponse,
    UserOut,
    VerifyCodeRequest,
    VerifyCodeResponse,
)
from security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    decode_access_token,
    generate_verification_code,
    hash_password,
    hash_verification_code,
    is_same_hash,
    verify_password,
)

# prefix: 이 파일의 모든 주소 앞에 "/api/auth"가 붙음
# tags: http://127.0.0.1:8000/docs 화면에서 묶여 보일 이름
router = APIRouter(prefix="/api/auth", tags=["auth"])

# ----- 이메일 인증 규칙 -----
CODE_EXPIRE_MINUTES = 5  # 인증번호 유효 시간
RESEND_COOLDOWN_SECONDS = 60  # 같은 이메일로 다시 보내려면 기다려야 하는 시간 (메일 폭탄 방지)
MAX_ATTEMPTS = 5  # 인증번호 틀릴 수 있는 최대 횟수
VERIFIED_VALID_MINUTES = 30  # 인증 성공 후 이 시간 안에 가입을 끝내야 함


# -------------------------------------------------------------
# 도우미 함수
# -------------------------------------------------------------

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """DB에서 꺼낸 시각에 시간대 정보가 없으면 UTC로 붙여줌 (DB 종류마다 다르게 돌려줘서)"""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def latest_verification(db: Session, email: str) -> EmailVerification | None:
    """이 이메일로 보낸 인증번호 중 가장 최근 것 하나"""
    return (
        db.query(EmailVerification)  # SELECT * FROM email_verifications
        .filter(EmailVerification.email == email)  # WHERE email = ?
        .order_by(EmailVerification.created_at.desc(), EmailVerification.id.desc())  # 최신순
        .first()  # LIMIT 1
    )


# -------------------------------------------------------------
# 아이디 중복 확인
# 예) GET /api/auth/check-login-id?login_id=sebin01
# -------------------------------------------------------------
@router.get("/check-login-id", response_model=CheckLoginIdResponse)
def check_login_id(
    login_id: str = Query(..., description="확인할 아이디"),  # Query(...): 주소 ?뒤에 꼭 있어야 하는 값
    db: Session = Depends(get_db),  # Depends(get_db): 요청마다 DB 연결을 하나 빌려 줌
):
    login_id = login_id.strip().lower()
    if not LOGIN_ID_PATTERN.match(login_id):
        return CheckLoginIdResponse(
            available=False,
            message="아이디는 영문 소문자로 시작하는 4~20자(소문자, 숫자, _)로 입력해 주세요.",
        )

    exists = db.query(User).filter(User.login_id == login_id).first() is not None
    if exists:
        return CheckLoginIdResponse(available=False, message="이미 사용 중인 아이디예요.")
    return CheckLoginIdResponse(available=True, message="사용할 수 있는 아이디예요.")


# -------------------------------------------------------------
# 이메일 인증번호 보내기
# -------------------------------------------------------------
@router.post("/email/send-code", response_model=SendCodeResponse)
def send_code(body: SendCodeRequest, db: Session = Depends(get_db)):
    email = body.email

    # 1. 이미 가입된 이메일이면 보내지 않음
    if db.query(User).filter(User.email == email).first():
        # HTTPException: 이 에러를 던지면 FastAPI가 { "detail": "..." } 응답으로 바꿔줌
        raise HTTPException(status.HTTP_409_CONFLICT, detail="이미 가입된 이메일이에요.")

    # 2. 너무 자주 보내는 것 막기 (60초)
    last = latest_verification(db, email)
    if last:
        passed = (now_utc() - as_utc(last.created_at)).total_seconds()
        if passed < RESEND_COOLDOWN_SECONDS:
            wait_seconds = int(RESEND_COOLDOWN_SECONDS - passed) + 1
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"{wait_seconds}초 후에 다시 요청해 주세요.",
            )

    # 3. 이 이메일의 예전 인증번호는 지우고 새로 만들기 (항상 최신 것 하나만 유효)
    db.query(EmailVerification).filter(EmailVerification.email == email).delete()

    code = generate_verification_code()
    record = EmailVerification(
        email=email,
        code_hash=hash_verification_code(email, code),  # 원문 대신 해시 저장
        expires_at=now_utc() + timedelta(minutes=CODE_EXPIRE_MINUTES),
    )
    db.add(record)

    # 4. 메일 보내기 (실패하면 DB 저장도 취소)
    try:
        dev_mode = send_verification_email(email, code, CODE_EXPIRE_MINUTES)
    except Exception as error:  # 메일 서버 접속 실패, 비밀번호 오류 등
        db.rollback()  # rollback: 이번 요청에서 DB에 한 변경을 전부 취소
        print(f"[메일 발송 실패] {error}")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="인증 메일을 보내지 못했어요. 잠시 후 다시 시도해 주세요.",
        ) from error

    db.commit()  # commit: DB 변경 확정
    return SendCodeResponse(
        message="인증번호를 보냈어요.",
        expires_in=CODE_EXPIRE_MINUTES * 60,
        dev_mode=dev_mode,
    )


# -------------------------------------------------------------
# 이메일 인증번호 확인
# -------------------------------------------------------------
@router.post("/email/verify", response_model=VerifyCodeResponse)
def verify_code(body: VerifyCodeRequest, db: Session = Depends(get_db)):
    record = latest_verification(db, body.email)

    # 보낸 적 없거나 만료
    if record is None or now_utc() > as_utc(record.expires_at):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="인증번호가 만료됐어요. 다시 받아 주세요.")

    # 이미 인증 완료
    if record.verified_at is not None:
        return VerifyCodeResponse(message="이미 인증이 완료된 이메일이에요.", verified=True)

    # 틀린 횟수 초과
    if record.attempts >= MAX_ATTEMPTS:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="인증번호를 너무 많이 틀렸어요. 인증번호를 다시 받아 주세요.",
        )

    # 입력한 번호도 똑같이 해시해서 저장된 해시와 비교
    if not is_same_hash(record.code_hash, hash_verification_code(body.email, body.code)):
        record.attempts += 1
        db.commit()
        left = MAX_ATTEMPTS - record.attempts
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"인증번호가 일치하지 않아요. (남은 횟수 {left}회)",
        )

    # 성공
    record.verified_at = now_utc()
    db.commit()
    return VerifyCodeResponse(message="이메일 인증이 완료됐어요.", verified=True)


# -------------------------------------------------------------
# 회원가입
# -------------------------------------------------------------
@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    # 1. 아이디 / 이메일 중복 확인 (프론트에서 확인했어도 그 사이에 누가 가입했을 수 있어서 다시 확인)
    if db.query(User).filter(User.login_id == body.login_id).first():
        raise HTTPException(status.HTTP_409_CONFLICT, detail="이미 사용 중인 아이디예요.")
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, detail="이미 가입된 이메일이에요.")

    # 2. 이메일 인증을 했는지, 너무 오래되진 않았는지 확인
    record = latest_verification(db, body.email)
    if (
        record is None
        or record.verified_at is None
        or now_utc() - as_utc(record.verified_at) > timedelta(minutes=VERIFIED_VALID_MINUTES)
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="이메일 인증을 먼저 완료해 주세요.")

    # 3. 사용자 저장 — ★ 비밀번호는 bcrypt 해시로 바꿔서 저장
    user = User(
        login_id=body.login_id,
        password_hash=hash_password(body.password),
        name=body.name,
        phone=body.phone,
        email=body.email,
        email_verified=True,
    )
    db.add(user)

    # 다 쓴 인증 기록은 삭제
    db.query(EmailVerification).filter(EmailVerification.email == body.email).delete()

    try:
        db.commit()
    except IntegrityError as error:
        # 아주 짧은 순간에 같은 아이디/이메일로 동시에 가입하면 DB의 unique 규칙에 걸림
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="이미 사용 중인 아이디 또는 이메일이에요.") from error

    db.refresh(user)  # DB가 만들어준 user_id, created_at 값을 다시 읽어옴
    return SignupResponse(message="회원가입이 완료됐어요.", user=UserOut.model_validate(user))


# -------------------------------------------------------------
# 로그인 (아이디 + 비밀번호)
# -------------------------------------------------------------
@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.login_id == body.login_id).first()

    # 아이디가 없어도 가짜 해시로 비교를 한 번 해서 응답 시간을 똑같이 맞춤 (security.py 설명 참고)
    password_ok = verify_password(body.password, user.password_hash if user else DUMMY_PASSWORD_HASH)

    if user is None or not password_ok:
        # 보안상 "아이디가 없음"인지 "비밀번호가 틀림"인지 구분해서 알려주지 않음
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 올바르지 않아요.",
        )

    # 관리자가 이용 정지한 회원은 로그인 막기 (403: "누군지는 알지만 허락 안 함")
    # ※ 비밀번호가 맞을 때만 알려줌 → 남의 아이디로 정지 여부를 떠보는 걸 막음
    if user.status == "suspended":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="이용이 정지된 계정이에요. 관리자에게 문의해 주세요.",
        )

    token = create_access_token(user.user_id, user.login_id)
    return LoginResponse(access_token=token, user=UserOut.model_validate(user))


# -------------------------------------------------------------
# 로그인한 사용자 확인용 (다른 API에서도 이 함수를 Depends로 가져다 쓰면 됨)
# -------------------------------------------------------------

# HTTPBearer: 요청 헤더의 "Authorization: Bearer 토큰"을 꺼내주는 도구
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """토큰을 확인해서 로그인한 사용자를 돌려줌. 토큰이 없거나 잘못됐으면 401
    사용 예) def my_api(user: User = Depends(get_current_user)): ...
    """
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail="로그인이 필요해요.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise unauthorized

    user = db.get(User, int(payload["sub"]))  # 기본키(user_id)로 사용자 찾기
    if user is None:
        raise unauthorized
    # 로그인해 있는 동안 관리자가 정지하면, 그다음 요청부터 바로 막힘
    if user.status == "suspended":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="이용이 정지된 계정이에요. 관리자에게 문의해 주세요.",
        )
    return user


@router.get("/me", response_model=UserOut)
def read_me(user: User = Depends(get_current_user)):
    """내 정보 (토큰이 올바르면 사용자 정보를 돌려줌)"""
    return user


# =============================================================
# 아이디 찾기 / 비밀번호 찾기 (2026.11 추가)
# -------------------------------------------------------------
# 회원가입 이메일 인증과 같은 표(email_verifications)와 같은 규칙을 씀
#   - 인증번호 5분 유효, 60초 안에 다시 보내기 금지, 5번 틀리면 다시 받기
# 다른 점: "이미 가입된" 이메일에만 보냄 (회원가입은 반대로 가입 안 된 이메일에만 보냄)
#
# ★ 인증번호를 용도별로 구분하는 방법
#   해시를 만들 때 이메일 앞에 용도("find-id:" / "reset:")를 붙여서 저장함
#   → 아이디 찾기로 받은 번호를 비밀번호 재설정이나 회원가입 인증에 넣어도 해시가 달라서 통과하지 못함
#   → 표에 칸을 새로 만들 필요가 없음 (DB 변경 없음)
# =============================================================

PURPOSE_FIND_ID = "find-id"
PURPOSE_RESET = "reset"
PURPOSE_LABEL = {PURPOSE_FIND_ID: "아이디 찾기", PURPOSE_RESET: "비밀번호 재설정"}
RESET_VALID_MINUTES = 10  # 인증을 마친 뒤 이 시간 안에 새 비밀번호를 저장해야 함


def purpose_code_hash(purpose: str, email: str, code: str) -> str:
    """용도가 섞인 인증번호 해시 (위 설명 참고)"""
    return hash_verification_code(f"{purpose}:{email}", code)


def issue_code(db: Session, email: str, purpose: str) -> SendCodeResponse:
    """인증번호를 새로 만들어 저장하고 메일로 보냄 (send_code와 같은 규칙)"""
    # 1. 너무 자주 보내는 것 막기 (60초)
    last = latest_verification(db, email)
    if last:
        passed = (now_utc() - as_utc(last.created_at)).total_seconds()
        if passed < RESEND_COOLDOWN_SECONDS:
            wait_seconds = int(RESEND_COOLDOWN_SECONDS - passed) + 1
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"{wait_seconds}초 후에 다시 요청해 주세요.",
            )

    # 2. 예전 인증번호는 지우고 새로 만들기 (항상 최신 것 하나만 유효)
    db.query(EmailVerification).filter(EmailVerification.email == email).delete()
    code = generate_verification_code()
    db.add(
        EmailVerification(
            email=email,
            code_hash=purpose_code_hash(purpose, email, code),
            expires_at=now_utc() + timedelta(minutes=CODE_EXPIRE_MINUTES),
        )
    )

    # 3. 메일 보내기 (실패하면 DB 저장도 취소)
    try:
        dev_mode = send_verification_email(email, code, CODE_EXPIRE_MINUTES, PURPOSE_LABEL[purpose])
    except Exception as error:
        db.rollback()
        print(f"[메일 발송 실패] {error}")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="인증 메일을 보내지 못했어요. 잠시 후 다시 시도해 주세요.",
        ) from error

    db.commit()
    return SendCodeResponse(
        message="인증번호를 보냈어요.",
        expires_in=CODE_EXPIRE_MINUTES * 60,
        dev_mode=dev_mode,
    )


def check_purpose_code(db: Session, email: str, purpose: str, code: str) -> EmailVerification:
    """인증번호가 맞는지 확인 (verify_code와 같은 규칙). 맞으면 그 기록을 돌려줌"""
    record = latest_verification(db, email)

    if record is None or now_utc() > as_utc(record.expires_at):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="인증번호가 만료됐어요. 다시 받아 주세요.")

    if record.attempts >= MAX_ATTEMPTS:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="인증번호를 너무 많이 틀렸어요. 인증번호를 다시 받아 주세요.",
        )

    if not is_same_hash(record.code_hash, purpose_code_hash(purpose, email, code)):
        record.attempts += 1
        db.commit()
        left = MAX_ATTEMPTS - record.attempts
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"인증번호가 일치하지 않아요. (남은 횟수 {left}회)",
        )
    return record


# 입력한 정보와 맞는 회원이 없을 때 공통 문구
NO_MATCH_DETAIL = "입력한 정보와 일치하는 회원이 없어요. 다시 확인해 주세요."


# -------------------------------------------------------------
# 아이디 찾기 ① 인증번호 받기 (이름 + 이메일이 둘 다 맞는 회원만)
# -------------------------------------------------------------
@router.post("/find-id/send-code", response_model=SendCodeResponse)
def find_id_send_code(body: FindIdSendCodeRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email, User.name == body.name).first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NO_MATCH_DETAIL)
    return issue_code(db, body.email, PURPOSE_FIND_ID)


# -------------------------------------------------------------
# 아이디 찾기 ② 인증번호 확인 → 맞으면 아이디를 알려줌
# (메일을 받을 수 있는 본인이 확인됐으니 아이디를 가리지 않고 그대로 보여줌)
# -------------------------------------------------------------
@router.post("/find-id/verify", response_model=FindIdResponse)
def find_id_verify(body: FindIdVerifyRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email, User.name == body.name).first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NO_MATCH_DETAIL)

    check_purpose_code(db, body.email, PURPOSE_FIND_ID, body.code)

    # 다 쓴 인증번호는 바로 지움 (같은 번호로 다시 조회 못 하게)
    db.query(EmailVerification).filter(EmailVerification.email == body.email).delete()
    db.commit()
    return FindIdResponse(message="아이디를 찾았어요.", login_id=user.login_id, created_at=user.created_at)


# -------------------------------------------------------------
# 비밀번호 찾기 ① 인증번호 받기 (아이디 + 이메일이 둘 다 맞는 회원만)
# -------------------------------------------------------------
@router.post("/reset-password/send-code", response_model=SendCodeResponse)
def reset_send_code(body: ResetSendCodeRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.login_id == body.login_id, User.email == body.email).first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NO_MATCH_DETAIL)
    return issue_code(db, body.email, PURPOSE_RESET)


# -------------------------------------------------------------
# 비밀번호 찾기 ② 인증번호 확인 (맞으면 "인증 완료" 표시 → 새 비밀번호 입력 화면으로)
# -------------------------------------------------------------
@router.post("/reset-password/verify", response_model=VerifyCodeResponse)
def reset_verify(body: ResetVerifyRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.login_id == body.login_id, User.email == body.email).first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NO_MATCH_DETAIL)

    record = check_purpose_code(db, body.email, PURPOSE_RESET, body.code)
    if record.verified_at is None:
        record.verified_at = now_utc()
        db.commit()
    return VerifyCodeResponse(message="인증이 완료됐어요. 새 비밀번호를 입력해 주세요.", verified=True)


# -------------------------------------------------------------
# 비밀번호 찾기 ③ 새 비밀번호 저장
#   - 같은 인증번호로 ②를 마쳤고(verified_at), 그게 10분 안이어야 함
#   - 저장할 때도 비밀번호는 bcrypt 해시로 바꿔서 저장
# -------------------------------------------------------------
@router.post("/reset-password", response_model=MessageResponse)
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.login_id == body.login_id, User.email == body.email).first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NO_MATCH_DETAIL)

    record = check_purpose_code(db, body.email, PURPOSE_RESET, body.code)
    if record.verified_at is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="인증번호 확인을 먼저 완료해 주세요.")
    if now_utc() - as_utc(record.verified_at) > timedelta(minutes=RESET_VALID_MINUTES):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="인증 시간이 지났어요. 인증번호를 다시 받아 주세요.",
        )

    # 예전 비밀번호와 똑같으면 바꾸는 의미가 없어서 알려줌
    if verify_password(body.new_password, user.password_hash):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="지금 쓰는 비밀번호와 달라야 해요.",
        )

    user.password_hash = hash_password(body.new_password)
    # 다 쓴 인증번호는 지움 (같은 번호로 또 바꾸지 못하게)
    db.query(EmailVerification).filter(EmailVerification.email == body.email).delete()
    db.commit()
    return MessageResponse(message="비밀번호를 바꿨어요. 새 비밀번호로 로그인해 주세요.")
