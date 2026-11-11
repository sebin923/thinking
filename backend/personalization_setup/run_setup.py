"""Standard-library launcher: select an existing, working backend environment."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent


def choose_python():
    candidates = [
        BACKEND / '.venv/Scripts/python.exe', BACKEND / 'venv/Scripts/python.exe',
        BACKEND.parent / '.venv/Scripts/python.exe', BACKEND.parent / 'venv/Scripts/python.exe',
        BACKEND.parent / 'llm_training/.venv/Scripts/python.exe', Path(sys.executable),
    ]
    probe = ('import sqlalchemy; import database; import models; '
             'from security import hash_password, verify_password; '
             'from auth_schemas import UserOut, LoginRequest')
    seen = set()
    for candidate in candidates:
        key = str(candidate.resolve())
        if key in seen or not candidate.is_file():
            continue
        seen.add(key)
        try:
            result = subprocess.run([key, '-c', probe], cwd=BACKEND,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            return key
    return None


def main():
    if not (BACKEND / 'models.py').is_file() or not (BACKEND / 'database.py').is_file():
        print('personalization_setup 폴더를 backend 바로 아래에 넣어 주세요.')
        return 1
    chosen = choose_python()
    if not chosen:
        print('백엔드 모듈을 불러올 수 있는 기존 Python 환경을 찾지 못했습니다.')
        print('백엔드 서버를 실행하는 가상환경에서 setup_personalization.py를 직접 실행해 주세요.')
        print('새 패키지를 자동으로 설치하거나 기존 환경을 변경하지 않았습니다.')
        return 1
    print('사용할 Python:', chosen, flush=True)
    try:
        return subprocess.call([chosen, str(HERE / 'setup_personalization.py'), *sys.argv[1:]], cwd=BACKEND)
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
