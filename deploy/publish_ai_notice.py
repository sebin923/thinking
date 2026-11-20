"""Publish the reviewed AI notice after its images and renderer are deployed.

Run with the existing backend Python environment. Default is check-only.
No passwords, tokens, roles, schemas, or other notices are changed.
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
    parser.add_argument('--expected-index-sha256', help='Required with --apply; use the verified image-capable build index hash')
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
        raise ValueError('The reviewed notice must contain its two local comparison images')
    for src in images:
        path = (args.web_root/src.lstrip('/')).resolve()
        if not path.is_relative_to(args.web_root.resolve()) or not path.is_file():
            raise ValueError('Deploy both comparison images before publishing')
        if path.read_bytes()[:8] != b'\x89PNG\r\n\x1a\n':
            raise ValueError('Comparison asset is not a PNG')
    if args.apply:
        if not args.expected_index_sha256:
            raise ValueError('--apply requires --expected-index-sha256 from the verified build')
        actual = hashlib.sha256((args.web_root/'index.html').read_bytes()).hexdigest()
        if actual != args.expected_index_sha256:
            raise ValueError('The deployed web build does not match the verified notice renderer')

    with SessionLocal() as db:
        if args.apply and db.bind.dialect.name == 'postgresql':
            db.execute(text('SELECT pg_advisory_xact_lock(71120261120)'))
        existing = db.query(models.Notice).filter(models.Notice.title == payload.title).with_for_update().all()
        if len(existing) > 1:
            raise ValueError('Several notices have the same title; choose the intended record manually')
        current = existing[0] if existing else None
        admins = db.query(models.User).filter(models.User.role == 'admin', models.User.status == 'active')
        if args.author_id:
            admins = admins.filter(models.User.user_id == args.author_id)
        authors = admins.order_by(models.User.user_id).all()
        if not current and len(authors) != 1:
            raise ValueError('Specify one active administrator with --author-id')

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
