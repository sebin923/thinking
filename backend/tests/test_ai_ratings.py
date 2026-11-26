"""별점 수집의 기존 화면 호환성·검증·저장·관리자 조회. 격리 SQLite만 사용한다."""
import time

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from test_qwen_features import api
import models
from security import create_access_token


def payload(**updates):
    return {"kind": "feedback", "model": "common", "rating": 4, "comment": "  도움이 됐어요.  ",
            "documentId": 7, "resultText": "원문을 유지하며 표기를 고쳐 보세요.",
            "requestText": "제 역활은 기록 정리입니다.", **updates}


def test_existing_frontend_request_is_saved_as_guest(api):
    client, db, post = api
    response = client.post('/api/ai-ratings', json=payload())
    assert response.status_code == 200, response.text
    value = response.json()
    assert value['success'] is True
    row = db.query(models.AiRating).one()
    assert row.id == value['data']['id']
    assert row.user_id == 'guest' and row.document_id == '7'
    assert row.comment == '도움이 됐어요.'
    assert value['data'] == {'id': row.id, 'kind': 'feedback', 'model': 'common', 'rating': 4,
        'comment': row.comment, 'documentId': '7', 'resultText': row.result_text,
        'requestText': row.request_text, 'createdAt': row.created_at}
    assert db.query(models.Document).count() == 0
    post.assert_not_called()


@pytest.mark.parametrize('kind,model', [('draft','common'),('draft','personal'),('feedback','common'),('feedback','personal')])
def test_frontend_rating_kinds_and_models(api, kind, model):
    client, db, post = api
    response = client.post('/api/ai-ratings', json=payload(kind=kind, model=model))
    assert response.status_code == 200
    row = db.query(models.AiRating).one()
    assert row.kind == kind and row.model == model


@pytest.mark.parametrize('updates', [
    {'rating': 0}, {'rating': 6}, {'rating': True}, {'rating': 4.5}, {'rating': '4'},
    {'kind': 'score'}, {'model': 'unknown'}, {'comment': '가'*101},
    {'resultText': '가'*2001}, {'requestText': '가'*2001},
    {'documentId': True}, {'documentId': 1.5}, {'documentId': {}}, {'documentId': [1]},
    {'documentId': 0}, {'documentId': -1}, {'documentId': '가'*51},
    {'documentId': 10**50}, {'user_id': '1'}, {'userId': 1},
])
def test_invalid_or_spoofed_inputs_do_not_create_records(api, updates):
    client, db, post = api
    response = client.post('/api/ai-ratings', json=payload(**updates))
    assert response.status_code == 422, response.text
    assert db.query(models.AiRating).count() == 0
    post.assert_not_called()


@pytest.mark.parametrize('document_id,expected', [(None,None),('',None),('  ',None),(' 15 ','15'),('가'*50,'가'*50)])
def test_optional_reference_and_nullable_text(api, document_id, expected):
    client, db, post = api
    response = client.post('/api/ai-ratings', json=payload(documentId=document_id, comment=None, resultText=None, requestText=None))
    assert response.status_code == 200, response.text
    row = db.query(models.AiRating).one()
    assert row.document_id == expected
    assert row.comment == row.result_text == row.request_text == ''


def test_authenticated_rating_uses_the_verified_user(api):
    client, db, post = api
    token = create_access_token(2, 'other')
    response = client.post('/api/ai-ratings', json=payload(), headers={'Authorization': 'Bearer '+token})
    assert response.status_code == 200, response.text
    assert db.query(models.AiRating).one().user_id == '2'


@pytest.mark.parametrize('authorization', ['Bearer invalid', 'Basic invalid'])
def test_invalid_authentication_is_not_saved_as_guest(api, authorization):
    client, db, post = api
    response = client.post('/api/ai-ratings', json=payload(), headers={'Authorization': authorization})
    assert response.status_code == 401, response.text
    assert db.query(models.AiRating).count() == 0


def test_suspended_account_cannot_submit_authenticated_rating(api):
    client, db, post = api
    db.get(models.User, 2).status = 'suspended'; db.commit()
    token = create_access_token(2, 'other')
    response = client.post('/api/ai-ratings', json=payload(), headers={'Authorization': 'Bearer '+token})
    assert response.status_code == 403
    assert db.query(models.AiRating).count() == 0


def test_same_millisecond_submissions_have_distinct_ids(api, monkeypatch):
    client, db, post = api
    monkeypatch.setattr(time, 'time', lambda: 1800000000.0)
    responses = [client.post('/api/ai-ratings', json=payload()) for _ in range(5)]
    assert all(response.status_code == 200 for response in responses)
    assert len({response.json()['data']['id'] for response in responses}) == 5
    assert db.query(models.AiRating).count() == 5


def test_database_failure_never_reports_success(api, monkeypatch):
    client, db, post = api
    def failed_commit(self):
        raise SQLAlchemyError('검사용 저장 실패')
    monkeypatch.setattr(Session, 'commit', failed_commit)
    response = client.post('/api/ai-ratings', json=payload())
    assert response.status_code == 503
    assert response.json().get('success') is not True
    assert db.query(models.AiRating).count() == 0


def test_saved_rating_is_available_only_through_admin_reads(api):
    client, db, post = api
    response = client.post('/api/ai-ratings', json=payload())
    rating_id = response.json()['data']['id']
    assert client.get('/api/admin/ratings').status_code == 403
    assert client.get('/api/ai-ratings').status_code == 405
    db.get(models.User, 1).role = 'admin'; db.commit()
    listing = client.get('/api/admin/ratings').json()
    assert listing['total'] == 1 and listing['distribution']['4'] == 1
    assert listing['items'][0]['id'] == rating_id
    detail = client.get('/api/admin/ratings/'+rating_id)
    assert detail.status_code == 200 and detail.json()['request_text'] == payload()['requestText']
