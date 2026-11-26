"""O/X 해설 인용 표시 정리. 기본은 조회이며 --apply는 원본 백업 후에만 반영한다."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from sqlalchemy import MetaData, Table, bindparam, inspect, select, text, update


def _protected_records(connection):
    """진도·정답 기록은 DB 안에서 지문만 계산하고 내용은 로그나 백업에 담지 않는다."""
    result = {}
    names = set(inspect(connection).get_table_names())
    for name in ('learning_progress', 'quiz_results'):
        if name not in names:
            continue
        if connection.dialect.name == 'postgresql':
            row = connection.execute(text(
                f'SELECT count(*) AS count, md5(COALESCE(string_agg(md5(row_to_json(t)::text), '
                f"'' ORDER BY md5(row_to_json(t)::text)), '')) AS digest FROM {name} AS t"
            )).mappings().one()
            result[name] = dict(row)
        else:
            rows = [dict(row) for row in connection.execute(text(f'SELECT * FROM {name}')).mappings()]
            rendered = sorted(json.dumps(row, sort_keys=True, ensure_ascii=False, default=str) for row in rows)
            result[name] = {'count': len(rows), 'digest': hashlib.sha256('\n'.join(rendered).encode()).hexdigest()}
    return result


def clean_database(engine, *, apply=False, backup_file=None, expected_count=None):
    from ox_explanations import CITATION_PLACEHOLDER, clean_ox_explanation

    connection = engine.connect()
    if engine.dialect.name == 'postgresql':
        connection = connection.execution_options(isolation_level='REPEATABLE READ')
    with connection:
        with connection.begin():
            if connection.dialect.name == 'postgresql':
                connection.execute(text("SET LOCAL lock_timeout = '5s'"))
                connection.execute(text("SET LOCAL statement_timeout = '30s'"))
                if not apply:
                    connection.execute(text('SET TRANSACTION READ ONLY'))
            table = Table('ox_quizzes', MetaData(), autoload_with=connection)
            statement = select(table).order_by(table.c.quiz_id)
            if apply:
                statement = statement.with_for_update()
            before = [dict(row) for row in connection.execute(statement).mappings()]
            changed = []
            unrecognized = []
            for row in before:
                original = row.get('explanation')
                cleaned = clean_ox_explanation(original)
                if isinstance(cleaned, str) and re.search(r'\[cite:', cleaned, re.IGNORECASE):
                    unrecognized.append(row['quiz_id'])
                if original != cleaned:
                    if not cleaned.strip():
                        raise ValueError('표시를 제거하면 해설이 비는 문제가 있습니다.')
                    changed.append({'target_id': row['quiz_id'], 'before_value': original, 'after_value': cleaned})
            receipt = {'total_rows': len(before), 'affected_rows': len(changed), 'applied': False,
                       'removed_markers': sum(len(CITATION_PLACEHOLDER.findall(row['before_value'])) for row in changed),
                       'unrecognized_marker_ids': unrecognized}
            if not apply:
                return receipt
            if expected_count is not None and len(changed) != expected_count:
                raise ValueError(f'예상 수정 건수 {expected_count}와 현재 {len(changed)}가 다릅니다.')
            if unrecognized:
                raise ValueError('숫자형이 아닌 인용 표시가 있어 먼저 확인해야 합니다.')
            if not backup_file:
                raise ValueError('반영 전 원본 백업 파일 경로가 필요합니다.')
            protected_before = _protected_records(connection)
            backup = Path(backup_file).resolve()
            backup.parent.mkdir(parents=True, exist_ok=True)
            payload = {'format': 'thinking-ox-explanations-v1', 'created_utc': datetime.now(timezone.utc).isoformat(),
                       'rows': before, 'protected_records_fingerprints': protected_before,
                       'placeholder_pattern': CITATION_PLACEHOLDER.pattern}
            # 같은 이름의 백업을 덮어쓰지 않고 디스크에 기록을 마친 뒤 DB를 수정한다.
            with backup.open('x', encoding='utf-8') as file:
                os.chmod(backup, 0o600)
                json.dump(payload, file, ensure_ascii=False, indent=2, default=str)
                file.flush()
                os.fsync(file.fileno())
            if changed:
                result = connection.execute(update(table).where(table.c.quiz_id == bindparam('target_id'))
                    .where(table.c.explanation == bindparam('before_value')).values(explanation=bindparam('after_value')), changed)
                if result.rowcount != len(changed):
                    raise ValueError('원본과 다른 행이 있어 변경을 취소합니다.')
            after = [dict(row) for row in connection.execute(select(table).order_by(table.c.quiz_id)).mappings()]
            expected = [{**row, 'explanation': clean_ox_explanation(row.get('explanation'))} for row in before]
            if after != expected:
                raise ValueError('해설 표시 외의 데이터가 달라 변경을 취소합니다.')
            if _protected_records(connection) != protected_before:
                raise ValueError('진도 또는 정답 기록이 달라 변경을 취소합니다.')
            receipt.update(applied=True, backup_file=str(backup), remaining_marker_rows=0,
                           question_answer_and_ids_preserved=True, progress_records_preserved=True)
        # 이 지점은 검증과 트랜잭션 커밋이 모두 끝난 뒤다.
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend-dir', type=Path, default=Path(__file__).resolve().parents[1] / 'backend')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup-file', type=Path)
    parser.add_argument('--expected-count', type=int)
    args = parser.parse_args()
    if args.apply and args.backup_file is None:
        parser.error('--apply에는 --backup-file이 필요합니다.')
    backend = args.backend_dir.resolve()
    if not (backend / 'database.py').is_file():
        parser.error('기존 백엔드 경로를 지정해 주세요.')
    sys.path.insert(0, str(backend))
    from dotenv import load_dotenv
    load_dotenv(backend / '.env')
    from database import engine
    result = clean_database(engine, apply=args.apply, backup_file=args.backup_file, expected_count=args.expected_count)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    raise SystemExit(main())
