"""이미지 표시 기능과 비교 이미지를 배포한 뒤 검토한 AI 공지를 등록합니다.

기존 백엔드 Python 환경에서 실행하며 기본 동작은 확인만 수행합니다.
비밀번호·토큰·권한·DB 구조·다른 공지는 변경하지 않습니다.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-dir', type=Path, default=Path('/home/ec2-user/thinking'))
    parser.add_argument('--service-env', type=Path, default=Path('/home/ec2-user/.config/thinking/llm.env'))
    parser.add_argument('--web-root', type=Path, default=Path('/var/www/thinking'))
    parser.add_argument('--payload', type=Path, default=Path(__file__).parent/'notices/ai-writing-20261120.json')
    parser.add_argument('--author-id', type=int)
    parser.add_argument('--expected-index-sha256', help='실제 등록 시 필요합니다. 이미지 표시를 확인한 웹 빌드의 index.html 파일 해시를 입력하세요.')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(args.app_dir/'backend/.env')
    load_dotenv(args.service_env, override=True)
    sys.path.insert(0, str(args.app_dir/'backend'))
    from admin_schemas import NoticeIn
    from database import SessionLocal
    import models
    from sqlalchemy import text

    payload = NoticeIn.model_validate(json.loads(args.payload.read_text(encoding='utf-8')))
    images = re.findall(r'^!\[[^\]\r\n]*\]\((/notice-assets/[a-zA-Z0-9/_-]+\.png)\)$', payload.content, re.M)
    if len(images) != 2 or len(set(images)) != 2:
        raise ValueError('검토한 공지에는 사이트 내부 비교 이미지 두 장이 포함되어야 합니다.')
    for src in images:
        path = (args.web_root/src.lstrip('/')).resolve()
        if not path.is_relative_to(args.web_root.resolve()) or not path.is_file():
            raise ValueError('공지 등록 전에 비교 이미지 두 장을 먼저 배포해 주세요.')
        if path.read_bytes()[:8] != b'\x89PNG\r\n\x1a\n':
            raise ValueError('비교 이미지가 PNG 파일이 아닙니다.')
    if args.apply:
        if not args.expected_index_sha256:
            raise ValueError('--apply로 등록할 때는 검증한 웹 빌드의 --expected-index-sha256 값이 필요합니다.')
        actual = hashlib.sha256((args.web_root/'index.html').read_bytes()).hexdigest()
        if actual != args.expected_index_sha256:
            raise ValueError('배포된 웹 파일이 이미지 표시를 검증한 빌드와 다릅니다.')

    with SessionLocal() as db:
        if args.apply and db.bind.dialect.name == 'postgresql':
            db.execute(text('SELECT pg_advisory_xact_lock(71120261120)'))
        existing = db.query(models.Notice).filter(models.Notice.title == payload.title).with_for_update().all()
        if len(existing) > 1:
            raise ValueError('같은 제목의 공지가 여러 개입니다. 수정할 공지를 직접 확인해 주세요.')
        current = existing[0] if existing else None
        admins = db.query(models.User).filter(models.User.role == 'admin', models.User.status == 'active')
        if args.author_id:
            admins = admins.filter(models.User.user_id == args.author_id)
        authors = admins.order_by(models.User.user_id).all()
        if not current and len(authors) != 1:
            raise ValueError('--author-id로 이용 중인 관리자 한 명을 지정해 주세요.')

        result = {'apply': args.apply, 'title': payload.title, 'characters': len(payload.content),
                  'images': len(images), 'existing_notice_id': current.notice_id if current else None}
        if not args.apply:
            print(json.dumps(result, ensure_ascii=False))
            return 0
        backup_dir = Path.home()/'.config/thinking/notice-backups'
        backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
        before = {'notice_id': current.notice_id, 'title': current.title, 'content': current.content,
                  'is_pinned': current.is_pinned, 'author_id': current.author_id} if current else None
        backup = backup_dir/f'ai-notice-{stamp}.json'
        backup.write_text(json.dumps({'before': before, 'requested': payload.model_dump()}, ensure_ascii=False, indent=2), encoding='utf-8')
        backup.chmod(0o600)
        if current:
            current.content = payload.content
            action = 'updated'
        else:
            current = models.Notice(**payload.model_dump(), author_id=authors[0].user_id)
            db.add(current)
            action = 'created'
        db.commit()
        db.refresh(current)
        result.update(notice_id=current.notice_id, action=action, backup=str(backup))
        print(json.dumps(result, ensure_ascii=False))
        return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
    except Exception as error:
        print(json.dumps({'ok': False, 'error': type(error).__name__}), file=sys.stderr)
        raise SystemExit(1)
