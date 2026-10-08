# =============================================================
# email_service.py — 인증번호 메일 보내기
# -------------------------------------------------------------
# 파이썬 기본 기능(smtplib)으로 메일을 보냄 → 따로 설치할 패키지 없음
#
# ★ .env에 아래 값을 넣으면 진짜 메일이 나감 (예: Gmail)
#   SMTP_HOST=smtp.gmail.com
#   SMTP_PORT=587
#   SMTP_USER=보내는gmail주소@gmail.com
#   SMTP_PASSWORD=앱비밀번호16자리   ← Gmail 로그인 비밀번호가 아님!
#   MAIL_FROM=보내는gmail주소@gmail.com
#   (Gmail 앱 비밀번호: 구글 계정 → 보안 → 2단계 인증 켜기 → "앱 비밀번호"에서 발급)
#
# ★ SMTP 설정이 없으면 "개발 모드"
#   메일을 안 보내고 인증번호를 백엔드 터미널에 출력함 → 메일 설정 없이도 회원가입 테스트 가능
# =============================================================

import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
MAIL_FROM = os.getenv("MAIL_FROM") or SMTP_USER


def is_dev_mode() -> bool:
    """메일 설정이 하나라도 비어 있으면 개발 모드 (터미널 출력)"""
    return not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def send_verification_email(to_email: str, code: str, expire_minutes: int) -> bool:
    """인증번호 메일 보내기
    반환값: 개발 모드였으면 True, 진짜 메일을 보냈으면 False
    메일 서버 오류가 나면 예외가 그대로 올라감 (routers/auth.py에서 처리)
    """
    if is_dev_mode():
        # 터미널에 눈에 띄게 출력
        print("=" * 50)
        print(f"[개발 모드] 이메일 인증번호  →  {to_email} : {code}")
        print("(.env에 SMTP 설정을 넣으면 실제 메일로 발송돼요)")
        print("=" * 50)
        return True

    # ----- 메일 내용 만들기 -----
    message = EmailMessage()
    message["Subject"] = "[생각한줄] 이메일 인증번호 안내"
    message["From"] = MAIL_FROM
    message["To"] = to_email
    message.set_content(
        "안녕하세요, 생각한줄입니다.\n\n"
        f"회원가입 인증번호는 [{code}] 입니다.\n"
        f"{expire_minutes}분 안에 입력해 주세요.\n\n"
        "본인이 요청하지 않았다면 이 메일은 무시하셔도 됩니다."
    )

    # ----- 메일 서버에 접속해서 보내기 -----
    # with 문: 다 쓰면 자동으로 연결을 닫아줌
    if SMTP_PORT == 465:
        # 465번 포트: 처음부터 암호화된 연결(SSL)
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(message)
    else:
        # 587번 포트: 일반 연결 후 starttls()로 암호화 전환
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(message)

    return False
