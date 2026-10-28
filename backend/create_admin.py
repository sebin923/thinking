# =============================================================
# create_admin.py — 관리자 계정 만들기 (터미널에서 한 번 실행하는 도구)
# -------------------------------------------------------------
# 관리자 계정은 아무나 만들면 안 돼서 회원가입 화면에는 일부러 기능을 안 넣음
# → 서버 컴퓨터(DB에 접속할 수 있는 컴퓨터)에서 이 파일을 직접 실행해서 만듦
#
# 실행 방법 (backend 폴더에서, 가상환경 켠 상태로)
#   python create_admin.py
#
# 하는 일
#   1) 아이디·비밀번호·이름·전화번호·이메일을 입력받음
#      (비밀번호는 getpass로 받아서 화면에 안 보이고, 기록에도 안 남음)
#   2) 회원가입과 똑같은 규칙으로 검사 (아이디 형식, 비밀번호 영문+숫자 8자 이상 등)
#   3) 비밀번호를 bcrypt 해시로 바꿔서 role = "admin" 으로 users 테이블에 저장
#      (이메일 인증은 건너뜀 — 관리자가 직접 만드는 계정이라서)
#
# ※ 이미 있는 아이디를 입력하면, 새로 만들지 않고 할 일을 고르게 함
#     1) 관리자로 바꾸기   2) 비밀번호 다시 정하기   3) 계정 삭제 (다시 만들고 싶을 때)
# ※ DB 접속 정보는 다른 백엔드 코드처럼 .env에서 읽음 (database.py)
# =============================================================

from getpass import getpass

from pydantic import ValidationError

import models
from auth_schemas import SignupRequest
from database import Base, SessionLocal, engine
from routers.admin import ensure_user_status_column
from security import hash_password


def ask(label: str, default: str = "") -> str:
    """한 줄 입력받기 (그냥 엔터를 치면 default 값 사용)"""
    shown = f" [{default}]" if default else ""
    value = input(f"{label}{shown}: ").strip()
    return value or default


def ask_password() -> str:
    """비밀번호를 두 번 입력받아서 같은지 확인 (입력하는 글자는 화면에 안 보임)"""
    while True:
        first = getpass("비밀번호 (영문+숫자 8자 이상, 입력해도 화면에 안 보여요): ")
        second = getpass("비밀번호 확인: ")
        if first == second:
            return first
        print("  → 두 비밀번호가 달라요. 다시 입력해 주세요.\n")


def check_password_rule(password: str) -> list[str]:
    """비밀번호가 회원가입 규칙에 맞는지 검사 → 틀린 이유 목록 (맞으면 빈 목록)
    SignupRequest가 비밀번호 규칙을 갖고 있어서, 다른 칸은 규칙에 맞는 임시 값을 넣고 비밀번호만 검사함
    """
    try:
        SignupRequest(
            login_id="checkonly1",
            password=password,
            name="확인용",
            phone="01000000000",
            email="check@saenggakhanjul.com",
        )
        return []
    except ValidationError as error:
        return [str(item["msg"]).replace("Value error, ", "") for item in error.errors()]


def handle_existing(db, user: models.User) -> None:
    """이미 있는 아이디일 때: 관리자로 바꾸기 / 비밀번호 다시 정하기 / 삭제 중에서 고르기"""
    role_text = "관리자" if user.role == "admin" else "일반 회원"
    print(f"\n'{user.login_id}' 아이디가 이미 있어요. ({user.name}, {role_text}, 상태: {user.status})")
    print("  1) 관리자로 바꾸기")
    print("  2) 비밀번호 다시 정하기 (로그인이 안 될 때)")
    print("  3) 계정 삭제 (지우고 다시 만들고 싶을 때)")
    print("  0) 취소")
    choice = ask("번호를 고르세요", "0")

    if choice == "1":
        user.role = "admin"
        user.status = "active"  # 혹시 정지된 계정이었으면 같이 풀어 줌
        db.commit()
        print(f"\n✅ '{user.login_id}' 계정을 관리자로 바꿨어요. 로그아웃 후 다시 로그인하면 '관리자' 버튼이 보여요.")

    elif choice == "2":
        password = ask_password()
        problems = check_password_rule(password)
        if problems:
            print("\n❌ 비밀번호가 규칙에 맞지 않아요:")
            for problem in problems:
                print("  -", problem)
            return
        user.password_hash = hash_password(password)  # ★ 해시로 바꿔서 저장
        user.status = "active"
        db.commit()
        print(f"\n✅ '{user.login_id}' 비밀번호를 새로 정했어요. 새 비밀번호로 로그인해 보세요.")

    elif choice == "3":
        # 이 계정이 쓴 글·퀴즈 기록·랭킹이 있으면 지우지 않음 (실수로 진짜 회원 데이터를 날리지 않게)
        has_data = (
            db.query(models.Document).filter(models.Document.user_id == user.user_id).first()
            or db.query(models.QuizResult).filter(models.QuizResult.user_id == user.user_id).first()
            or db.query(models.Ranking).filter(models.Ranking.user_id == user.user_id).first()
        )
        if has_data:
            print("\n❌ 이 계정은 쓴 글이나 퀴즈·랭킹 기록이 있어서 여기서는 지우지 않아요.")
            print("   로그인이 안 되는 거라면 2) 비밀번호 다시 정하기를 써 주세요.")
            return
        answer = ask(f"정말 '{user.login_id}' 계정을 삭제할까요? 되돌릴 수 없어요. (y/n)", "n")
        if answer.lower() != "y":
            print("취소했어요.")
            return
        # 딸린 개인 맞춤 설정부터 지우고 계정 삭제 (자식 → 부모 순서)
        db.query(models.UserWritingPreference).filter(models.UserWritingPreference.user_id == user.user_id).delete(
            synchronize_session=False
        )
        db.delete(user)
        db.commit()
        print(f"\n✅ '{user.login_id}' 계정을 삭제했어요. 다시 만들려면 python create_admin.py 를 한 번 더 실행하세요.")

    else:
        print("취소했어요.")


def main() -> None:
    print("=" * 50)
    print(" 생각한줄 관리자 계정 만들기")
    print("=" * 50)

    # 테이블이 없으면 만들고, users 테이블에 status 칸이 없으면 추가 (서버를 아직 안 켰을 수도 있어서)
    Base.metadata.create_all(bind=engine)
    ensure_user_status_column(engine)

    db = SessionLocal()
    try:
        login_id = ask("관리자 아이디").lower()

        # ----- 이미 있는 아이디면: 관리자로 바꾸기 / 비밀번호 다시 정하기 / 삭제 중에서 고르기 -----
        existing = db.query(models.User).filter(models.User.login_id == login_id).first()
        if existing:
            handle_existing(db, existing)
            return

        # ----- 새 관리자 계정 정보 입력 -----
        password = ask_password()
        name = ask("이름", "관리자")
        phone = ask("전화번호 (숫자만)", "01000000000")
        # 기본값은 형식만 맞춘 관리용 주소 (.local 같은 예약 주소는 이메일 검사에서 거절돼서 일반 도메인 모양으로)
        email = ask("이메일 (다른 계정과 겹치면 안 돼요)", f"{login_id}@saenggakhanjul.com")

        # 회원가입과 같은 규칙으로 검사 (SignupRequest가 아이디·비밀번호·이름·전화번호·이메일을 한 번에 검사해 줌)
        try:
            data = SignupRequest(login_id=login_id, password=password, name=name, phone=phone, email=email)
        except ValidationError as error:
            print("\n❌ 입력값이 규칙에 맞지 않아요:")
            for item in error.errors():
                # "Value error, " 같은 앞부분은 떼고 우리말 문구만 보여줌
                print("  -", str(item["msg"]).replace("Value error, ", ""))
            return

        if db.query(models.User).filter(models.User.email == data.email).first():
            print(f"\n❌ '{data.email}'은(는) 이미 가입된 이메일이에요. 다른 이메일로 다시 실행해 주세요.")
            return

        user = models.User(
            login_id=data.login_id,
            password_hash=hash_password(data.password),  # ★ 비밀번호는 해시로만 저장
            name=data.name,
            phone=data.phone,
            email=data.email,
            email_verified=True,  # 관리자가 직접 만드는 계정이라 이메일 인증 생략
            role="admin",
            status="active",
        )
        db.add(user)
        db.commit()
        print(f"\n✅ 관리자 계정 '{data.login_id}'를 만들었어요. 사이트에서 이 아이디로 로그인하면 '관리자' 버튼이 보여요.")
    finally:
        db.close()  # 성공·실패와 상관없이 DB 연결은 꼭 닫기


# 이 파일을 직접 실행했을 때만 main() 실행 (다른 파일에서 import하면 실행 안 됨)
if __name__ == "__main__":
    main()
