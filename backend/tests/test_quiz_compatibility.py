"""통합 후에도 Git 프론트의 문법 난이도와 DB O/X 조회가 유지되는지 확인한다."""
from test_qwen_features import api, models


def test_grammar_quiz_filters_rds_shaped_level_values(api):
    client, db, _ = api
    for level in ('easy', 'medium', 'hard'):
        db.add(models.Quiz(category='grammar', level=level, question=f'{level} 문제',
                           options=['보기 1', '보기 2'], answer='보기 1', explanation='난이도별 해설'))
    db.commit()
    for level in ('easy', 'medium', 'hard'):
        response = client.get(f'/api/quizzes/?category=grammar&level={level}')
        assert response.status_code == 200, response.text
        assert [(row['question'], row['level']) for row in response.json()] == [(f'{level} 문제', level)]
    assert len(client.get('/api/quizzes/?category=grammar').json()) == 3


def test_existing_db_ox_endpoint_keeps_category_and_unit_filters(api):
    client, db, _ = api
    for category, unit_id, question in [('report', 1, '첫 단원 문제'), ('report', 2, '다음 단원 문제'),
                                         ('speech', 1, '다른 유형 문제')]:
        db.add(models.OxQuiz(category=category, unit_id=unit_id, question=question,
                             answer=True, explanation='기존 설명'))
    db.commit()
    response = client.get('/api/learn/quizzes?category=report&unit_id=1')
    assert response.status_code == 200, response.text
    assert len(response.json()) == 1
    assert {key: value for key, value in response.json()[0].items() if key != 'quiz_id'} == {
        'q': '첫 단원 문제', 'a': True, 'e': '기존 설명',
    }


def test_admin_can_save_and_change_grammar_level(api):
    client, db, _ = api
    db.get(models.User, 1).role = 'admin'
    db.commit()
    body = {'category': 'grammar', 'level': 'hard', 'question': '난이도 저장 확인',
            'options': ['보기 1', '보기 2'], 'answer': '보기 1', 'explanation': '기존 해설'}
    created = client.post('/api/admin/quizzes', json=body)
    assert created.status_code == 201, created.text
    assert created.json()['level'] == 'hard'
    updated = client.put(f'/api/admin/quizzes/{created.json()["quiz_id"]}', json={**body, 'level': 'easy'})
    assert updated.status_code == 200, updated.text
    assert updated.json()['level'] == 'easy'
    assert client.get('/api/quizzes/?category=grammar&level=hard').json() == []
    assert len(client.get('/api/quizzes/?category=grammar&level=easy').json()) == 1
