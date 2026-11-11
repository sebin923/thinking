"""Run from backend with the existing backend Python environment. No API calls/emails."""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATASET = 'persona_ready_20261110_v1'
ACCOUNT_NAMES = {
    'demo_concise': ('persona_concise', '개인화테스트_간결', 'natural', 'short'),
    'demo_formal': ('persona_formal', '개인화테스트_격식', 'formal', 'normal'),
    'demo_friendly': ('persona_friendly', '개인화테스트_친근', 'natural', 'normal'),
}


class SetupError(Exception):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def load_data():
    rows = json.loads((HERE / 'data/personalization_records.json').read_text(encoding='utf-8-sig'))
    if len(rows) != 36 or len({r['record_id'] for r in rows}) != 36:
        raise SetupError('36개의 고유 레코드가 필요합니다.')
    for key in ACCOUNT_NAMES:
        part = [r for r in rows if r['account_key'] == key]
        if Counter(r['split'] for r in part) != {'train': 9, 'valid': 3}:
            raise SetupError(f'{key}: 학습 9건/검증 3건 구성 불일치')
        if Counter(r['document_type'] for r in part) != {'보고서': 4, '발표문': 4, '자유 글쓰기': 4}:
            raise SetupError(f'{key}: 글 유형 구성 불일치')
    for r in rows:
        if not r['synthetic'] or r['human_approved'] or r['common_training_allowed']:
            raise SetupError('데모 자료의 출처/승인 상태가 변경되었습니다.')
        if r['before_text'] == r['after_text'] or not r['after_text'].strip():
            raise SetupError('수정 전후 본문이 잘못되었습니다.')
        if r['completion'] != [{'role': 'assistant', 'content': r['after_text']}]:
            raise SetupError('수정 후 본문과 정답이 다릅니다.')
    return rows


def ledgers(m):
    from sqlalchemy import MetaData, Table, Column, String, Integer, ForeignKey, Boolean, JSON
    md = MetaData()
    accounts = Table('personalization_demo_accounts_v1', md,
        Column('account_key', String(40), primary_key=True),
        Column('user_id', Integer, ForeignKey(m.User.__table__.c.user_id), unique=True, nullable=False),
        Column('dataset_id', String(60), nullable=False),
        Column('login_id', String(20), nullable=False),
        Column('email', String(255), nullable=False))
    records = Table('personalization_demo_records_v1', md,
        Column('record_id', String(150), primary_key=True),
        Column('account_key', String(40), ForeignKey(accounts.c.account_key), nullable=False),
        Column('user_id', Integer, ForeignKey(m.User.__table__.c.user_id), nullable=False),
        Column('document_id', Integer, ForeignKey(m.Document.__table__.c.id), unique=True, nullable=False),
        Column('before_draft_id', Integer, ForeignKey(m.Draft.__table__.c.id), unique=True, nullable=False),
        Column('after_draft_id', Integer, ForeignKey(m.Draft.__table__.c.id), unique=True, nullable=False),
        Column('split', String(10), nullable=False),
        Column('data_sha256', String(64), nullable=False),
        Column('synthetic', Boolean, nullable=False),
        Column('human_approved', Boolean, nullable=False),
        Column('common_training_allowed', Boolean, nullable=False),
        Column('payload', JSON, nullable=False))
    return md, accounts, records


def check_schema(conn, m):
    from sqlalchemy import inspect
    inspector = inspect(conn)
    for model in [m.User, m.Document, m.Thought, m.Draft, m.UserWritingPreference]:
        table = model.__table__
        if not inspector.has_table(table.name, schema=table.schema):
            raise SetupError(f'필수 테이블 없음: {table.name}. 백엔드 DB 설정을 확인하세요.')
        cols = {c['name']: c for c in inspector.get_columns(table.name, schema=table.schema)}
        missing = set(table.columns.keys()) - set(cols)
        if missing:
            raise SetupError(f'{table.name}: models.py와 DB 열 불일치 {sorted(missing)}. 자동 변경하지 않았습니다.')
        for name, c in cols.items():
            if name not in table.columns and not c.get('nullable', True) and c.get('default') is None and not c.get('identity') and not c.get('computed'):
                raise SetupError(f'{table.name}.{name}: 코드에 없는 필수 열이 있습니다.')
        actual_pk = inspector.get_pk_constraint(table.name, schema=table.schema)['constrained_columns']
        if set(actual_pk) != set(c.name for c in table.primary_key.columns):
            raise SetupError(f'{table.name}: DB 기본키가 models.py와 다릅니다.')


def snapshot(conn, m, rows, accounts, records):
    from sqlalchemy import inspect, select, or_
    inspector = inspect(conn)
    a_rows = conn.execute(select(accounts)).mappings().all() if inspector.has_table(accounts.name) else []
    r_rows = conn.execute(select(records)).mappings().all() if inspector.has_table(records.name) else []
    by_account = {x['account_key']: x for x in a_rows}
    by_record = {x['record_id']: x for x in r_rows}
    expected = {r['record_id']: r for r in rows}
    if set(by_account) - set(ACCOUNT_NAMES) or set(by_record) - set(expected):
        raise SetupError('추적 테이블에 다른 자료가 있습니다. 자동 합치기/덮어쓰기를 중단합니다.')
    for key, (login, _, _, _) in ACCOUNT_NAMES.items():
        email = login + '@example.com'
        found = conn.execute(select(m.User.__table__).where(or_(m.User.login_id == login, m.User.email == email))).mappings().all()
        tracked = by_account.get(key)
        if tracked:
            if tracked['dataset_id'] != DATASET or tracked['login_id'] != login or tracked['email'] != email:
                raise SetupError(f'{key}: 기존 계정 추적 정보와 충돌합니다.')
            if len(found) != 1 or found[0]['user_id'] != tracked['user_id'] or found[0]['login_id'] != login or found[0]['email'] != email:
                raise SetupError(f'{key}: 추적한 계정이 변경되거나 사라졌습니다.')
        elif found:
            raise SetupError(f'{login}: 기존 계정과 충돌합니다. 기존 계정을 가져오거나 수정하지 않았습니다.')
    for record_id, tracked in by_record.items():
        r = expected[record_id]
        owner = by_account.get(r['account_key'])
        if not owner or tracked['user_id'] != owner['user_id'] or tracked['account_key'] != r['account_key']:
            raise SetupError(f'{record_id}: 계정 연결 불일치')
        if tracked['data_sha256'] != digest(r) or tracked['split'] != r['split'] or tracked['payload'] != r:
            raise SetupError(f'{record_id}: 원본 데이터가 달라졌습니다. 기존 내용을 보존합니다.')
        if not tracked['synthetic'] or tracked['human_approved'] or tracked['common_training_allowed']:
            raise SetupError(f'{record_id}: 데모 상태가 변경되었습니다.')
        doc = conn.execute(select(m.Document.__table__).where(m.Document.id == tracked['document_id'])).mappings().first()
        if not doc or doc['user_id'] != owner['user_id'] or doc['document_type'] != r['document_type']:
            raise SetupError(f'{record_id}: 문서 소유자/유형 불일치')
        for which, version in [('before', 1), ('after', 2)]:
            draft = conn.execute(select(m.Draft.__table__).where(m.Draft.id == tracked[f'{which}_draft_id'])).mappings().first()
            if not draft or draft['document_id'] != doc['id'] or draft['version'] != version or draft['content'] != r[f'{which}_text']:
                raise SetupError(f'{record_id}: 저장된 버전 {version}이 변경되거나 사라졌습니다. 덮어쓰지 않습니다.')
        thoughts = conn.execute(select(m.Thought.content).where(m.Thought.document_id == doc['id']).order_by(m.Thought.id)).scalars().all()
        if thoughts != r['facts']:
            raise SetupError(f'{record_id}: 저장된 생각 메모가 변경되었습니다. 덮어쓰지 않습니다.')
    return by_account, by_record


def seed(conn, m, rows, password, hash_password, verify_password, validate_user=None):
    from sqlalchemy import select
    check_schema(conn, m)
    md, accounts, records = ledgers(m)
    known_accounts, known_records = snapshot(conn, m, rows, accounts, records)
    md.create_all(conn, tables=[accounts, records], checkfirst=True)
    created = {'users': 0, 'documents': 0, 'drafts': 0, 'thoughts': 0}
    for key, (login, name, tone, length) in ACCOUNT_NAMES.items():
        if key in known_accounts:
            continue
        if not password:
            raise SetupError('새 계정의 비밀번호가 필요합니다.')
        hashed = hash_password(password)
        if not verify_password(password, hashed):
            raise SetupError('기존 보안 함수의 비밀번호 검증에 실패했습니다.')
        values = dict(login_id=login, email=login+'@example.com', name=name, nickname=name,
                      phone='00000000000', password_hash=hashed, role='general', status='active',
                      email_verified=False, ai_credits=3)
        uid = conn.execute(m.User.__table__.insert().values(**values).returning(m.User.user_id)).scalar_one()
        if validate_user:
            validate_user(dict(conn.execute(select(m.User.__table__).where(m.User.user_id == uid)).mappings().one()))
        conn.execute(m.UserWritingPreference.__table__.insert().values(
            user_id=uid, preferred_tone=tone, sentence_length=length,
            feedback_style='detailed', ai_assistance='balanced'))
        entry = dict(account_key=key, user_id=uid, dataset_id=DATASET, login_id=login, email=values['email'])
        conn.execute(accounts.insert().values(**entry))
        known_accounts[key] = entry
        created['users'] += 1
    for r in rows:
        if r['record_id'] in known_records:
            continue
        uid = known_accounts[r['account_key']]['user_id']
        part = '학습' if r['split'] == 'train' else '검증'
        title = f'[개인화테스트/{part}] {r["topic"]}'
        # A matching untracked title may be an earlier/manual import; never adopt silently.
        if conn.execute(select(m.Document.id).where(m.Document.user_id == uid, m.Document.title == title)).first():
            raise SetupError(f'{r["record_id"]}: 추적되지 않은 동일 제목의 문서가 있어 중단합니다.')
        did = conn.execute(m.Document.__table__.insert().values(user_id=uid, document_type=r['document_type'], title=title, status='완료').returning(m.Document.id)).scalar_one()
        for fact in r['facts']:
            conn.execute(m.Thought.__table__.insert().values(document_id=did, content=fact))
            created['thoughts'] += 1
        before_id = conn.execute(m.Draft.__table__.insert().values(document_id=did, version=1, content=r['before_text']).returning(m.Draft.id)).scalar_one()
        after_id = conn.execute(m.Draft.__table__.insert().values(document_id=did, version=2, content=r['after_text']).returning(m.Draft.id)).scalar_one()
        conn.execute(records.insert().values(record_id=r['record_id'], account_key=r['account_key'], user_id=uid,
            document_id=did, before_draft_id=before_id, after_draft_id=after_id, split=r['split'],
            data_sha256=digest(r), synthetic=True, human_approved=False, common_training_allowed=False, payload=r))
        created['documents'] += 1
        created['drafts'] += 2
    snapshot(conn, m, rows, accounts, records)
    return created


def verified_summary(conn, m, rows):
    _, accounts, records = ledgers(m)
    a, r = snapshot(conn, m, rows, accounts, records)
    return {'dataset_id': DATASET, 'synthetic': True,
            'accounts': [{'account_key': k, 'login_id': v['login_id'], 'user_id': v['user_id'],
                          'documents': sum(x['account_key'] == k for x in r.values())} for k, v in a.items()],
            'documents': len(r), 'drafts': len(r)*2,
            'splits': dict(Counter(x['split'] for x in r.values()))}


def export_from_db(conn, m, rows, destination):
    from sqlalchemy import select
    _, accounts, records = ledgers(m)
    a, r = snapshot(conn, m, rows, accounts, records)
    if len(a) != 3 or len(r) != 36:
        raise SetupError('계정 3개와 문서 36개를 먼저 저장해야 합니다.')
    if destination.exists():
        raise SetupError('내보내기 폴더가 이미 있습니다. 다른 경로를 사용하세요.')
    destination.mkdir(parents=True)
    manifest = {'dataset_id': DATASET, 'synthetic': True, 'human_approved': False, 'source': 'PostgreSQL linked drafts version 2', 'files': []}
    for key, owner in a.items():
        folder = destination / f'user_{owner["user_id"]}'
        folder.mkdir()
        for split in ['train', 'valid']:
            batch = []
            for row in rows:
                if row['account_key'] != key or row['split'] != split:
                    continue
                link = r[row['record_id']]
                content = conn.execute(select(m.Draft.content).where(m.Draft.id == link['after_draft_id'])).scalar_one()
                batch.append({'id': row['record_id'], 'prompt': row['prompt'], 'completion': [{'role': 'assistant', 'content': content}],
                    'metadata': {'user_id': owner['user_id'], 'account_key': key, 'genre': row['document_type'],
                                 'split': split, 'document_id': link['document_id'], 'after_draft_id': link['after_draft_id'],
                                 'synthetic': True, 'human_approved': False, 'common_training_allowed': False}})
            path = folder / f'{split}.jsonl'
            path.write_text(''.join(json.dumps(x, ensure_ascii=False)+'\n' for x in batch), encoding='utf-8')
            manifest['files'].append({'path': str(path.relative_to(destination)), 'count': len(batch), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    (destination / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


def ask_password():
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        pw = getpass.getpass('새 테스트 계정 3개의 공통 비밀번호(화면에 표시되지 않음): ')
        confirm = getpass.getpass('비밀번호 다시 입력: ')
    if pw != confirm:
        raise SetupError('비밀번호가 일치하지 않습니다.')
    if not 12 <= len(pw) or len(pw.encode('utf-8')) > 72:
        raise SetupError('비밀번호는 12자 이상, UTF-8 기준 72바이트 이내로 입력하세요.')
    return pw


def main():
    parser = argparse.ArgumentParser(description='생각한줄 개인화 데모 데이터 준비')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--check-data', action='store_true', help='파일만 검사. DB 연결 없음')
    group.add_argument('--check', action='store_true', help='DB 구조와 충돌 확인. 기본값이며 DB 변경 없음')
    group.add_argument('--apply', action='store_true', help='일반 테스트 계정과 문서/초안 저장')
    group.add_argument('--verify', action='store_true', help='저장된 자료 확인. DB 변경 없음')
    group.add_argument('--export', action='store_true', help='DB의 버전 2를 사용자별 JSONL 후보로 내보내기')
    parser.add_argument('--output', type=Path, help='--export 결과 폴더. 이미 있는 폴더에는 쓰지 않음')
    args = parser.parse_args()
    rows = load_data()
    print('데이터: 계정 3개 / 문서 36개 / 수정 전후 초안 72개 / 학습 후보 27건·검증 9건')
    if args.check_data:
        print('파일 검사 완료. DB에 연결하지 않았습니다.')
        return
    backend = HERE.parent
    if not (backend / 'models.py').is_file() or not (backend / 'database.py').is_file():
        raise SetupError('personalization_setup 폴더를 backend 폴더 안에 넣어 주세요.')
    sys.path.insert(0, str(backend))
    os.chdir(backend)
    from database import engine
    engine.echo = False
    engine.hide_parameters = True
    import models as m
    from sqlalchemy import text
    if engine.dialect.name != 'postgresql':
        raise SetupError('현재 연결은 PostgreSQL이 아닙니다. DB 설정을 확인하세요.')
    try:
        with engine.connect() as conn:
            conn.execute(text('SET TRANSACTION READ ONLY'))
            check_schema(conn, m)
            _, accounts, records = ledgers(m)
            a, r = snapshot(conn, m, rows, accounts, records)
            print(f'DB 구조 확인 완료. 신규 계정 {3-len(a)}개 / 신규 문서 {36-len(r)}개 예정')
            if args.verify:
                result = verified_summary(conn, m, rows)
                if len(a) != 3 or len(r) != 36:
                    raise SetupError('아직 모든 자료가 저장되지 않았습니다.')
                print(json.dumps(result, ensure_ascii=False, indent=2))
            elif args.export:
                dest = args.output.resolve() if args.output else HERE / ('export_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
                export_from_db(conn, m, rows, dest)
                print(f'합성 데모 학습 후보 내보내기: {dest}')
            elif not args.apply:
                print('읽기 전용 점검 완료. 저장하려면 같은 명령에 --apply를 사용하세요.')
            conn.rollback()
        if not args.apply:
            return
        password = ask_password() if len(a) < 3 else None
        from security import hash_password, verify_password
        from auth_schemas import UserOut, LoginRequest
        if password:
            for login, _, _, _ in ACCOUNT_NAMES.values():
                LoginRequest(login_id=login, password=password)
        with engine.begin() as conn:
            conn.execute(text("SET LOCAL lock_timeout = '5s'"))
            conn.execute(text("SET LOCAL statement_timeout = '60s'"))
            locked = conn.execute(text('SELECT pg_try_advisory_xact_lock(20261110, 7301)')).scalar_one()
            if not locked:
                raise SetupError('다른 준비 작업이 실행 중입니다. 완료 후 다시 실행하세요.')
            created = seed(conn, m, rows, password, hash_password, verify_password, UserOut.model_validate)
            result = verified_summary(conn, m, rows)
        print('DB 저장 완료:', json.dumps(created, ensure_ascii=False))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        # No plaintext credentials or hashes in the result file.
        try:
            (HERE / 'setup_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError:
            print('DB 저장은 완료되었지만 결과 파일을 쓰지 못했습니다. 위 user_id를 보관하세요.')
    finally:
        engine.dispose()


if __name__ == '__main__':
    try:
        main()
    except (SetupError, KeyboardInterrupt, EOFError) as exc:
        print('중단:', str(exc) or '입력이 취소되었습니다.', file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        # DB errors may embed a connection string or a password hash; never dump them.
        print(f'실행 실패: {type(exc).__name__}. 비밀정보 보호를 위해 원문 예외는 출력하지 않습니다.', file=sys.stderr)
        print('백엔드 가상환경과 DB 연결을 확인하세요. DB 저장 중 오류는 전체 취소됩니다.', file=sys.stderr)
        sys.exit(1)
