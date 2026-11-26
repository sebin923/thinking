"""운영 정리 도구의 백업·원본 보존·실패 시 롤백을 새 SQLite에서 검증한다."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest
from sqlalchemy import Boolean, Column, Integer, JSON, MetaData, String, Table, Text, create_engine, select, text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
spec = importlib.util.spec_from_file_location('clean_ox_explanations', ROOT / 'deploy/clean_ox_explanations.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def isolated_database():
    engine = create_engine('sqlite://')
    assert str(engine.url) == 'sqlite://'
    metadata = MetaData()
    quizzes = Table('ox_quizzes', metadata,
        Column('quiz_id', Integer, primary_key=True), Column('category', String), Column('unit_id', Integer),
        Column('question', Text), Column('answer', Boolean), Column('explanation', Text))
    progress = Table('learning_progress', metadata, Column('user_id', Integer, primary_key=True),
                     Column('revision', Integer), Column('payload', JSON))
    metadata.create_all(engine)
    before = [dict(quiz_id=1, category='report', unit_id=1, question='문제는 그대로[cite: 7]?',
                   answer=True, explanation='본문[cite: 12].'),
              dict(quiz_id=2, category='cover', unit_id=2, question='다른 문제',
                   answer=False, explanation='문장[CITE: 3, 4].'),
              dict(quiz_id=3, category='speech', unit_id=1, question='정상 문제',
                   answer=True, explanation='정상 [참고 12] 출처')]
    saved = {'user_id': 8, 'revision': 4, 'payload': {'units': {'report-01': {'passed': True}},
             'wrong': {'q1': {'e': '과거 해설[cite: 12].', 'wrongCount': 3}}}}
    with engine.begin() as connection:
        connection.execute(quizzes.insert(), before)
        connection.execute(progress.insert(), saved)
    yield engine, quizzes, progress, before, saved
    engine.dispose()


def test_apply_changes_only_explanations_and_keeps_backup_and_progress(isolated_database, tmp_path):
    engine, quizzes, progress, before, saved = isolated_database
    backup = tmp_path / 'before.json'
    check = module.clean_database(engine)
    assert check['affected_rows'] == 2 and check['applied'] is False
    assert not backup.exists()
    result = module.clean_database(engine, apply=True, backup_file=backup, expected_count=2)
    assert result['affected_rows'] == 2 and result['removed_markers'] == 2 and result['applied'] is True
    assert result['progress_records_preserved'] and result['question_answer_and_ids_preserved']
    with engine.connect() as connection:
        after = [dict(row) for row in connection.execute(select(quizzes).order_by(quizzes.c.quiz_id)).mappings()]
        assert dict(connection.execute(select(progress)).mappings().one()) == saved
    expected = [dict(before[0], explanation='본문.'), dict(before[1], explanation='문장.'), before[2]]
    assert after == expected
    assert json.loads(backup.read_text(encoding='utf-8'))['rows'] == before
    assert module.clean_database(engine)['affected_rows'] == 0


def test_changed_target_count_aborts_without_writing(isolated_database, tmp_path):
    engine, quizzes, _, before, _ = isolated_database
    backup = tmp_path / 'before.json'
    with pytest.raises(ValueError, match='예상 수정 건수'):
        module.clean_database(engine, apply=True, backup_file=backup, expected_count=3)
    assert not backup.exists()
    with engine.connect() as connection:
        assert [dict(row) for row in connection.execute(select(quizzes)).mappings()] == before


def test_original_backup_is_never_overwritten(isolated_database, tmp_path):
    engine, quizzes, _, before, _ = isolated_database
    backup = tmp_path / 'before.json'
    backup.write_text('보존할 원본', encoding='utf-8')
    with pytest.raises(FileExistsError):
        module.clean_database(engine, apply=True, backup_file=backup, expected_count=2)
    assert backup.read_text(encoding='utf-8') == '보존할 원본'
    with engine.connect() as connection:
        assert [dict(row) for row in connection.execute(select(quizzes)).mappings()] == before


def test_any_non_explanation_change_rolls_back_the_whole_update(isolated_database, tmp_path):
    engine, quizzes, _, before, _ = isolated_database
    with engine.begin() as connection:
        connection.execute(text("CREATE TRIGGER change_question AFTER UPDATE OF explanation ON ox_quizzes "
                                "BEGIN UPDATE ox_quizzes SET question = '예상 밖 변경' WHERE quiz_id = NEW.quiz_id; END"))
    with pytest.raises(ValueError, match='해설 표시 외의 데이터'):
        module.clean_database(engine, apply=True, backup_file=tmp_path / 'before.json', expected_count=2)
    with engine.connect() as connection:
        assert [dict(row) for row in connection.execute(select(quizzes)).mappings()] == before
