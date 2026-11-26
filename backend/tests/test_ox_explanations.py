"""해설 정리 시 문제·정답·사용자 진도를 보존하는지 확인한다."""
from copy import deepcopy

import pytest

from test_qwen_features import api, models, LearningProgress
from ox_explanations import clean_ox_explanation


@pytest.mark.parametrize('before,after', [
    ('핵심을 먼저 씁니다[cite: 12].', '핵심을 먼저 씁니다.'),
    ('자료[cite:1]와 근거[CITE: 2, 3]를 확인해요.', '자료와 근거를 확인해요.'),
    ('본문 [참고 12]와 https://example.com/source는 유지해요.',
     '본문 [참고 12]와 https://example.com/source는 유지해요.'),
    ('숫자 12와 인용문, 문장.\n다음 문장.', '숫자 12와 인용문, 문장.\n다음 문장.'),
    (None, None), ('', ''),
])
def test_only_generation_placeholders_are_removed(before, after):
    assert clean_ox_explanation(before) == after


def test_public_ox_response_is_clean_without_changing_stored_question(api):
    client, db, _ = api
    original = '독자의 목적을 고려해요[cite: 12].'
    row = models.OxQuiz(category='report', unit_id=1, question='독자를 고려해야 한다.',
                        answer=True, explanation=original)
    db.add(row)
    db.commit()
    response = client.get('/api/learn/quizzes?category=report&unit_id=1')
    assert response.status_code == 200, response.text
    assert response.json() == [{'quiz_id': row.quiz_id, 'q': row.question, 'a': True, 'e': '독자의 목적을 고려해요.'}]
    db.refresh(row)
    assert row.explanation == original


def test_old_wrong_note_is_clean_in_response_and_db_progress_is_unchanged(api):
    client, db, _ = api
    payload = {'units': {'report-01': {'passed': True, 'correctQuestionIds': ['ox:1'],
                                      'writing': {'text': '사용자가 쓴 [cite: 12]는 수정하지 않는다.', 'score': 92}}},
               'wrong': {'report-01#ox:2': {'q': '문제 원문', 'a': False, 'e': '해설[cite: 12].',
                                           'resolved': False, 'wrongCount': 2}}}
    original = deepcopy(payload)
    row = LearningProgress(user_id=1, revision=7, legacy_imported=1, payload=payload)
    db.add(row)
    db.commit()
    response = client.get('/api/learn/progress')
    assert response.status_code == 200, response.text
    expected = deepcopy(original)
    expected['wrong']['report-01#ox:2']['e'] = '해설.'
    assert response.json() == {'progress': expected, 'revision': 7, 'legacy_imported': True}
    db.refresh(row)
    assert row.payload == original and row.revision == 7


def test_new_admin_ox_explanation_is_cleaned_without_changing_lesson_or_answer(api):
    client, db, _ = api
    db.get(models.User, 1).role = 'admin'
    db.commit()
    response = client.put('/api/admin/learn/units/report-01', json={
        'title': '팀원의 단원 설명은 수정하지 않는다.',
        'quiz': [{'q': '문제는 그대로인가?', 'a': False, 'e': '해설만 정리해요[cite: 2].'}],
    })
    assert response.status_code == 200, response.text
    saved = db.query(models.OxQuiz).filter_by(category='report', unit_id=1).one()
    assert (saved.question, saved.answer, saved.explanation) == ('문제는 그대로인가?', False, '해설만 정리해요.')
