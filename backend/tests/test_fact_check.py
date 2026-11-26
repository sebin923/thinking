"""V7 보조 검사: 신원·근거·오류 처리 및 기존 점수/진도 불변 검증."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from test_qwen_features import api, unlock, score_request, database, LearningProgress, app, get_current_user
from factcheck_protocol import normalize_input, public_result, diagnose, input_digest, MODEL_SHA256
import fact_check


def payload():
    return dict(type_label='보고서', task='자료 정리 결과를 설명하세요.',
                material='자료 12개 중 중복 2개를 제외하고 10개를 사용했다.',
                text='자료 12개 중 중복 2개를 제외하고 최종 자료 9개를 발표 준비에 사용했다.', practice=None)


def diagnosis(kind='numbers'):
    return {'on_task': True, 'errors': [{'kind': kind, 'material': ['S1'], 'student': ['T1']}]}


def response(post, data=None, result=None):
    data = data or payload()
    reply = Mock(status_code=200)
    reply.json.return_value = dict(model_version='v7', adapter_sha256=MODEL_SHA256,
                                  input_digest=input_digest(data), diagnosis=result or diagnosis())
    post.return_value = reply
    return reply.json.return_value


def test_optional_practice_and_score_free_result():
    assert normalize_input(payload())['source_kind'] == 'data'
    result = public_result(payload(), diagnosis())
    assert result['findings'][0]['source_quotes'] == [payload()['material']]
    assert result['findings'][0]['text_quotes'] == [payload()['text']]
    assert not {'score', 'passed', 'criteria', 'progress'} & result.keys()


@pytest.mark.parametrize('change', [dict(text='짧음'), dict(text='가'*3001), dict(task=''), dict(practice=[]), dict(source_kind='invalid')])
def test_bad_input(change):
    with pytest.raises(ValueError): normalize_input({**payload(), **change})


def test_question_does_not_accuse_personal_experience():
    data = {**payload(), 'type_label': '자기소개서', 'practice': {'kind': 'question'}, 'material': '문항: 강점을 쓰세요.'}
    with pytest.raises(ValueError): public_result(data, diagnosis())
    assert public_result(data, {'on_task': True, 'errors': []})['scope'] == 'question'
    grammar = diagnosis('grammar'); grammar['errors'][0]['material'] = []
    assert public_result(data, grammar)['findings'][0]['kind'] == 'grammar'


def test_invalid_output_retries_then_withholds():
    generate = Mock(return_value='{"score":100}')
    with pytest.raises(ValueError): diagnose(payload(), generate)
    assert generate.call_count == 2
    assert generate.call_args.kwargs == {'max_tokens': 512}


@pytest.mark.parametrize('mutate', ['hash', 'input', 'version', 'evidence', 'extra', 'not_json'])
def test_wrong_model_or_malformed_response_rejected(api, monkeypatch, mutate):
    _, _, post = api
    monkeypatch.setenv('FACTCHECK_LLM_URL', 'http://fact.test:8002')
    value = response(post)
    if mutate == 'hash': value['adapter_sha256'] = 'wrong'
    if mutate == 'input': value['input_digest'] = 'wrong'
    if mutate == 'version': value['model_version'] = 'v5'
    if mutate == 'evidence': value['diagnosis']['errors'][0]['student'] = ['T999']
    if mutate == 'extra': value['score'] = 100
    if mutate == 'not_json': post.return_value.json.side_effect = ValueError('json')
    with pytest.raises(Exception) as error: fact_check.check_facts(payload())
    assert error.value.status_code == 502


@pytest.mark.parametrize('failure,status', [(requests.Timeout(),504), (requests.ConnectionError(),503)])
def test_network_failure_does_not_fallback(api, monkeypatch, failure, status):
    _, _, post = api
    monkeypatch.setenv('FACTCHECK_LLM_URL', 'http://fact.test:8002')
    post.side_effect = failure
    with pytest.raises(Exception) as error: fact_check.check_facts(payload())
    assert error.value.status_code == status
    assert '단원 채점은 계속' in error.value.detail
    assert post.call_count == 1


def test_no_shared_writer_fallback(api, monkeypatch):
    _, _, post = api
    monkeypatch.delenv('FACTCHECK_LLM_URL', raising=False)
    with pytest.raises(Exception) as error: fact_check.check_facts(payload())
    assert error.value.status_code == 503
    post.assert_not_called()


def test_route_auth_lock_and_no_database_writes(api, monkeypatch):
    client, db, post = api
    monkeypatch.setenv('FACTCHECK_LLM_URL', 'http://fact.test:8002')
    request = {**score_request(), **payload(), 'training_consent': True}
    assert client.post('/api/learn/fact-check', json=request).status_code == 403
    assert db.query(LearningProgress).count() == 0
    unlock(db)
    before = [(name, db.connection().exec_driver_sql(f'SELECT * FROM "{name}"').fetchall())
              for name in database.Base.metadata.tables]
    # LearnScoreIn converts practice/material, so bind the response digest to the actual outgoing payload.
    def reply(*args, **kwargs):
        assert args[0] == 'http://fact.test:8002/fact-check'
        assert set(kwargs['json']) == {'type_label','task','material','text','source_kind'}
        mocked = Mock(status_code=200)
        mocked.json.return_value = dict(model_version='v7',adapter_sha256=MODEL_SHA256,
            input_digest=input_digest(kwargs['json']),diagnosis=diagnosis())
        return mocked
    post.side_effect = reply
    checked = client.post('/api/learn/fact-check', json=request)
    assert checked.status_code == 200, checked.text
    db.expire_all()
    after = [(name, db.connection().exec_driver_sql(f'SELECT * FROM "{name}"').fetchall())
             for name in database.Base.metadata.tables]
    assert before == after  # scores, progress, credits, training candidates and documents unchanged
    app.dependency_overrides.pop(get_current_user)
    assert client.post('/api/learn/fact-check', json=request).status_code == 401


def test_server_auth_busy_and_bad_output(monkeypatch):
    from fastapi.testclient import TestClient
    path = Path(__file__).resolve().parents[2] / 'llm_training/factcheck_server.py'
    if not path.is_file():
        pytest.skip('GPU PC 전용 사실검사 서버는 웹 저장소에서 제외합니다.')
    spec = importlib.util.spec_from_file_location('v7_server_test', path)
    server = importlib.util.module_from_spec(spec); spec.loader.exec_module(server)
    monkeypatch.setenv('FACTCHECK_LLM_TOKEN','test-token')
    monkeypatch.setattr(server,'load_model',lambda: None)
    monkeypatch.setattr(server,'_identity',{'adapter_sha256': MODEL_SHA256})
    monkeypatch.setattr(server,'generate',Mock(return_value=json.dumps(diagnosis())))
    data = {k:v for k,v in normalize_input(payload()).items() if k!='practice'}
    with TestClient(server.app) as client:
        assert client.post('/fact-check',json=data).status_code == 401
        headers = {'X-LLM-Token':'test-token'}
        assert client.post('/fact-check',json=data,headers=headers).status_code == 200
        server._lock.acquire()
        try: assert client.post('/fact-check',json=data,headers=headers).status_code == 503
        finally: server._lock.release()
        server.generate.return_value='{"score":100}'
        assert client.post('/fact-check',json=data,headers=headers).status_code == 502
        assert not server._lock.locked()
        assert client.post('/fact-check',json={**data,'text':'가'*3001},headers=headers).status_code == 422
