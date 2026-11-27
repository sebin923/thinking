from copy import deepcopy

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from test_qwen_features import api, app, models, recommendation_request
from recommendation_profile import RecommendationProfile
from learning_progress import LearningProgress
from practice_bank import materials
from routers.auth import get_current_user
from database import get_db


@pytest.fixture(autouse=True)
def authenticated_user_and_route_share_session(api):
    # 실제 요청에서는 인증 의존성과 라우터가 같은 get_db 세션을 공유한다.
    _, db, _ = api
    app.dependency_overrides[get_db] = lambda: db


def update(**values):
    return {'name': '테스트', 'phone': '01000000000', 'email': 'test@example.com', **values}


def test_mypage_defaults_do_not_create_a_profile(api):
    client, db, _ = api
    value = client.get('/api/mypage/profile').json()
    assert value['major'] == '' and value['interests'] == []
    assert db.get(RecommendationProfile, 1) is None


def test_mypage_save_is_shared_with_recommendation_and_survives_reload(api):
    client, db, post = api
    first = client.put('/api/mypage/profile', json=update(major='  컴퓨터공학과 ', interests=[' 웹   개발 ', '데이터베이스', '웹 개발']))
    assert first.status_code == 200, first.text
    assert first.json()['profile']['major'] == '컴퓨터공학과'
    assert first.json()['profile']['interests'] == ['웹 개발', '데이터베이스']
    assert client.get('/api/mypage/profile').json()['interests'] == ['웹 개발', '데이터베이스']
    assert client.get('/api/writing/recommendation-profile').json()['major'] == '컴퓨터공학과'
    assert client.post('/api/learn/practice-recommendation-v2', json=recommendation_request()).json()['personalized']
    second = client.put('/api/mypage/profile', json=update(major='경영학과', interests=['경영', '예산']))
    assert second.status_code == 200
    value = client.post('/api/learn/practice-recommendation-v2', json=recommendation_request()).json()
    entry = next(e for e in materials('보고서') if e['practice']['topic'] == value['practice']['topic'])
    assert 'business' in entry['domains']
    assert db.query(models.User).filter_by(user_id=1).populate_existing().one().email == 'test@example.com'
    post.assert_not_called()


def test_legacy_updates_preserve_recommendation_profile_and_consent(api):
    client, db, _ = api
    client.put('/api/writing/recommendation-profile', json={'major': '컴퓨터공학과', 'interests': ['인공지능'], 'use_training_data': False})
    assert client.put('/api/mypage/profile', json=update(name='새이름')).status_code == 200
    assert client.get('/api/writing/recommendation-profile').json() == {'major': '컴퓨터공학과', 'interests': ['인공지능'], 'use_training_data': False}
    assert client.put('/api/mypage/profile', json=update(name='새이름', major='', interests=[])).status_code == 200
    assert client.get('/api/writing/recommendation-profile').json() == {'major': '', 'interests': [], 'use_training_data': False}
    assert db.get(RecommendationProfile, 1) is not None


def test_mypage_fields_are_scoped_to_authenticated_user(api):
    client, db, _ = api
    assert client.put('/api/mypage/profile', json=update(user_id=2, major='환경공학과', interests=['환경'])).status_code == 200
    assert db.get(RecommendationProfile, 2) is None
    other = db.get(models.User, 2)
    app.dependency_overrides[get_current_user] = lambda: other
    value = client.get('/api/mypage/profile').json()
    assert value['user_id'] == 2 and value['major'] == '' and value['interests'] == []


@pytest.mark.parametrize('changes', [
    {'major': '가' * 81}, {'major': 123}, {'interests': ['분야'] * 9},
    {'interests': ['가' * 41]}, {'interests': ['   ']}, {'interests': [123]}, {'interests': '웹 개발'},
])
def test_invalid_fields_do_not_save_member_or_recommendation_data(api, changes):
    client, db, _ = api
    result = client.put('/api/mypage/profile', json=update(name='새이름', **changes))
    assert result.status_code == 422
    assert db.query(models.User).filter_by(user_id=1).populate_existing().one().name == '테스트'
    assert db.get(RecommendationProfile, 1) is None


def test_unverified_email_does_not_partially_save_recommendation_fields(api):
    client, db, _ = api
    result = client.put('/api/mypage/profile', json=update(name='새이름', email='new@example.com', major='경영학과', interests=['경영']))
    assert result.status_code == 400
    assert db.query(models.User).filter_by(user_id=1).populate_existing().one().name == '테스트'
    assert db.get(RecommendationProfile, 1) is None


def test_commit_failure_rolls_back_member_and_recommendation_together(api, monkeypatch):
    client, db, _ = api

    def fail_commit(self):
        raise IntegrityError('test transaction failure', {}, Exception('test'))

    monkeypatch.setattr(Session, 'commit', fail_commit)
    result = client.put('/api/mypage/profile', json=update(name='새이름', major='경영학과', interests=['경영']))
    assert result.status_code == 409
    assert db.query(models.User).filter_by(user_id=1).populate_existing().one().name == '테스트'
    assert db.get(RecommendationProfile, 1) is None


def test_profile_save_preserves_progress_style_and_credits(api):
    client, db, _ = api
    payload = {'units': {'report-01': {'passed': True, 'completed': True, 'writingBest': 95, 'writing': {'text': '기존 글'}}}, 'wrong': {}}
    db.add(LearningProgress(user_id=1, payload=deepcopy(payload), revision=3))
    db.get(models.User, 1).ai_credits = 7
    db.add(models.UserWritingPreference(user_id=1, preferred_tone='formal', sentence_length='short'))
    db.commit()
    assert client.put('/api/mypage/profile', json=update(major='경영학과', interests=['경영'])).status_code == 200
    assert db.query(LearningProgress).filter_by(user_id=1).populate_existing().one().payload == payload
    assert db.query(LearningProgress).filter_by(user_id=1).one().revision == 3
    assert db.query(models.User).filter_by(user_id=1).populate_existing().one().ai_credits == 7
    style = db.query(models.UserWritingPreference).filter_by(user_id=1).populate_existing().one()
    assert style.preferred_tone == 'formal' and style.sentence_length == 'short'


def test_mypage_recommendation_fields_require_login(api):
    client, _, _ = api
    app.dependency_overrides.pop(get_current_user)
    assert client.get('/api/mypage/profile').status_code == 401
    assert client.put('/api/mypage/profile', json=update(major='컴퓨터공학과', interests=['인공지능'])).status_code == 401
