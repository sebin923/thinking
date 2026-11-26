"""실제 사실검사 HTTP 계약과 채점·저장 경계. 모든 DB는 격리 SQLite다."""
import json
from unittest.mock import Mock

import pytest

from test_qwen_features import api, score_payload, score_request, unlock
from factcheck_protocol import MODEL_SHA256, input_digest
from grading_validation import audit_for_grading, arithmetic_issues, normalize_findings
from learning_progress import LearningProgress
from routers import learn


def audited_reply(post, diagnosis, grade):
    def respond(url, **kwargs):
        response = Mock(status_code=200)
        if url.endswith('/fact-check'):
            response.json.return_value = {'model_version': 'v7', 'adapter_sha256': MODEL_SHA256,
                'input_digest': input_digest(kwargs['json']), 'diagnosis': diagnosis}
        else:
            response.json.return_value = {'content': json.dumps(grade, ensure_ascii=False), 'adapter': 'common'}
        return response
    post.side_effect = respond


def use_real_audit(monkeypatch):
    monkeypatch.setattr(learn, 'audit_for_grading', audit_for_grading)
    monkeypatch.setenv('FACTCHECK_LLM_URL', 'http://fact.test:8002')


def state(db):
    return db.query(LearningProgress).filter_by(user_id=1).one().payload['units']['report-1']


def conflicting_request():
    request = score_request()
    request['practice']['facts'].append('담당자는 위치 수정 여부를 검토할 예정이며 아직 수정하지 않았다.')
    request['text'] = '자료실 안내판과 실제 책장 위치는 모두 일치한다고 확인했습니다. 담당자는 이미 위치 수정을 완료했습니다.'
    return request


def test_verified_fact_conflict_cannot_pass_but_grammar_remains_independent(api, monkeypatch):
    client, db, post = api
    unlock(db); use_real_audit(monkeypatch)
    grade = score_payload(score=10)
    grade['criteria']['criterion_2']['score'] = 3
    audited_reply(post, {'on_task': True, 'errors': [{'kind': 'status', 'material': ['S3'], 'student': ['T2']}]}, grade)
    response = client.post('/api/learn/writing-score', json=conflicting_request())
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['score'] < 90 and not result['passed'] and result['on_task']
    assert result['criteria'][-1]['score'] == 10
    assert '완료·예정 상태' in result['criteria'][-2]['comment']
    assert not state(db)['completed']
    assert post.call_count == 2


def test_many_criteria_cannot_cancel_a_critical_source_conflict(api, monkeypatch):
    client, db, post = api
    unlock(db); use_real_audit(monkeypatch)
    request = conflicting_request(); request['rules'] = [f'검토 기준 {i}' for i in range(8)]
    grade = score_payload(score=10)
    grade['criteria'] = {f'criterion_{i}': {'score': 3 if i == 9 else 10, 'comment': '글을 기준으로 평가했습니다.'} for i in range(1, 11)}
    audited_reply(post, {'on_task': True, 'errors': [{'kind': 'status', 'material': ['S3'], 'student': ['T2']}]}, grade)
    response = client.post('/api/learn/writing-score', json=request)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['score'] == 89 and not result['passed']
    assert '합산 점수와 관계없이' in result['overall_feedback']
    assert not state(db)['completed']


def test_off_topic_writing_cannot_get_a_passing_score(api, monkeypatch):
    client, db, post = api
    unlock(db); use_real_audit(monkeypatch)
    request = score_request()
    request['text'] = '어제 공원에서 산책하며 나무와 꽃을 보았습니다. 다음 주에도 친구와 함께 공원을 방문할 계획입니다.'
    grade = score_payload(on_task=False, score=10)
    grade['criteria']['criterion_2']['score'] = 0
    audited_reply(post, {'on_task': False, 'errors': []}, grade)
    response = client.post('/api/learn/writing-score', json=request)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['score'] <= 50 and not result['on_task'] and not result['passed']
    assert result['criteria'][-1]['score'] == 10
    assert not state(db)['completed']


@pytest.mark.parametrize('kind', ['off_topic', 'source_conflict'])
def test_untrusted_high_scores_cannot_override_the_verified_audit(api, monkeypatch, kind):
    client, db, post = api
    unlock(db); use_real_audit(monkeypatch)
    diagnosis = {'on_task': False, 'errors': []} if kind == 'off_topic' else {
        'on_task': True, 'errors': [{'kind': 'status', 'material': ['S3'], 'student': ['T2']}]}
    audited_reply(post, diagnosis, score_payload(score=10))
    response = client.post('/api/learn/writing-score', json=conflicting_request())
    assert response.status_code == 200, response.text
    assert response.json()['score'] < 90 and not response.json()['passed']
    assert not state(db)['completed'] and state(db)['writingAttempts'] == 1
    assert post.call_count == 2  # 사실검사 1회 + 채점 1회


def test_unavailable_source_checker_withholds_grade_without_writer_fallback(api, monkeypatch):
    client, db, post = api
    unlock(db); use_real_audit(monkeypatch)
    monkeypatch.delenv('FACTCHECK_LLM_URL')
    response = client.post('/api/learn/writing-score', json=score_request())
    assert response.status_code == 503 and '채점을 보류' in response.json()['detail']
    assert 'writing' not in state(db)
    post.assert_not_called()


def test_cover_letter_experiences_are_not_checked_against_missing_facts(api, monkeypatch):
    client, db, post = api
    unlock(db); use_real_audit(monkeypatch)
    request = score_request()
    request.update(type_label='자기소개서', practice={'kind': 'question', 'question': '본인이 실제로 팀에서 문제를 해결한 경험을 설명해 보세요.'},
                   text='저는 팀 과제에서 설문 응답 40개를 직접 정리하고, 회의에서 결과를 설명해 팀원들이 역할을 나누도록 도왔습니다.')
    audited_reply(post, {'on_task': True, 'errors': []}, score_payload())
    response = client.post('/api/learn/writing-score', json=request)
    assert response.status_code == 200, response.text
    assert response.json()['passed']
    assert post.call_args_list[0].kwargs['json']['source_kind'] == 'question'
    assert '자료에 없는' not in response.json()['overall_feedback']


@pytest.mark.parametrize('bad_score', [True, 11, -1, 3.5])
def test_verified_rules_do_not_repair_invalid_model_scores(api, monkeypatch, bad_score):
    client, db, post = api
    unlock(db); use_real_audit(monkeypatch)
    grade = score_payload(score=10)
    grade['criteria']['criterion_2']['score'] = bad_score
    audited_reply(post, {'on_task': True, 'errors': [{'kind': 'status', 'material': ['S3'], 'student': ['T2']}]}, grade)
    response = client.post('/api/learn/writing-score', json=conflicting_request())
    assert response.status_code == 502, response.text
    assert 'writing' not in state(db)


@pytest.mark.parametrize('task,rule,text', [
    ('자료로 제목 한 줄과 핵심 요약을 쓰세요.', '제목을 본문 앞에 따로 제시한다.',
     '자료실 안내판과 실제 책장 위치가 다릅니다. 위치 차이를 확인하여 담당자에게 기록으로 전달했습니다.'),
    ('자료를 번호와 기호가 있는 개조식으로 정리하세요.', '번호와 기호로 항목을 구분한다.',
     '자료실 안내판과 실제 책장 위치가 다릅니다. 위치 차이를 확인하여 담당자에게 기록으로 전달했습니다.'),
])
def test_missing_required_format_cannot_pass(api, monkeypatch, task, rule, text):
    client, db, post = api
    unlock(db); use_real_audit(monkeypatch)
    request = score_request(); request.update(task=task, rules=[rule], text=text)
    audited_reply(post, {'on_task': True, 'errors': []}, score_payload(score=10))
    response = client.post('/api/learn/writing-score', json=request)
    assert response.status_code == 200, response.text
    assert response.json()['score'] < 90 and response.json()['on_task'] and not response.json()['passed']
    assert not state(db)['completed']


@pytest.mark.parametrize('task,rule,text', [
    ('자료로 제목 한 줄과 핵심 요약을 쓰세요.', '제목을 본문 앞에 따로 제시한다.',
     '안내판 위치 점검 결과\n자료실 안내판과 실제 책장 위치가 달라 담당자에게 기록으로 전달했습니다.'),
    ('자료를 번호와 기호가 있는 개조식으로 정리하세요.', '번호와 기호로 항목을 구분한다.',
     '- 자료실 안내판과 실제 책장 위치가 다름.\n- 확인한 차이를 기록하여 담당자에게 전달함.'),
])
def test_valid_required_formats_keep_model_scores(api, monkeypatch, task, rule, text):
    client, db, post = api
    unlock(db); use_real_audit(monkeypatch)
    request = score_request(); request.update(task=task, rules=[rule], text=text)
    audited_reply(post, {'on_task': True, 'errors': []}, score_payload(score=10))
    response = client.post('/api/learn/writing-score', json=request)
    assert response.status_code == 200, response.text
    assert response.json()['score'] == 100 and response.json()['passed']


def test_verified_grammar_error_has_a_grounded_reason(api, monkeypatch):
    client, db, post = api
    unlock(db); use_real_audit(monkeypatch)
    request = score_request()
    request['text'] = '자료실 안내판과 책장 위치의 차이를 담당자에게 전달하고 관련 기록 정리가 완료됬다.'
    audited_reply(post, {'on_task': True, 'errors': [{'kind': 'grammar', 'material': [], 'student': ['T1']}]}, score_payload(score=10))
    response = client.post('/api/learn/writing-score', json=request)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['criteria'][-1]['score'] == 9
    assert '완료됬다' in result['criteria'][-1]['comment']
    assert '맞춤법' in result['next_step']


@pytest.mark.parametrize('text', [
    '설문 응답 12개 가운데 중복된 2개를 빼고, 남은 9개를 최종 분석에 사용했다.',
    '신청서 1,200장 중 200장을 제외하고 남은 999장을 제출했습니다.',
])
def test_explicit_remainder_arithmetic_is_checked(text):
    assert arithmetic_issues(text)


@pytest.mark.parametrize('text', [
    '설문 응답 12개 가운데 중복된 2개를 빼고, 남은 10개를 최종 분석에 사용했다.',
    '설문 응답 12개 가운데 중복된 2개를 빼고, 남은 10개 중 9개를 분석했다.',
    '설문 응답 12개 가운데 중복된 2개를 빼고, 남은 9개를 사용하지 않았다.',
    '설문 응답 12개 가운데 중복된 2개를 빼고, 남은 9개를 사용할 예정이다.',
    '설문 응답 12개 가운데 중복된 2명을 빼고, 남은 9개를 분석했다.',
    '“설문 응답 12개 가운데 중복된 2개를 빼고, 남은 9개를 분석했다.”는 계산이 틀린 예시다.',
    '설문 응답 12개 가운데 중복된 2개를 빼고, 남은 9개에 1개를 추가하여 사용했다.',
    '신청서 12장 중 15장을 제외하고 남은 9장을 제출했다.',
])
def test_arithmetic_check_does_not_infer_unstated_operations(text):
    assert not arithmetic_issues(text)


def test_number_claim_without_a_quantity_is_removed():
    findings = [{'kind': 'numbers', 'source_quotes': ['지연은 분석 프로그램을 작성했다.'],
                 'text_quotes': ['민수는 분석 프로그램을 작성했다.']}]
    assert normalize_findings(findings) == []


def test_same_actor_plan_to_completion_is_status_not_roles():
    findings = [{'kind':'roles', 'source_quotes':['담당자는 금요일에 통신 시험을 진행할 예정이다.'],
                 'text_quotes':['담당자는 금요일에 통신 시험까지 마쳐 정상 작동을 확인했다.']}]
    assert normalize_findings(findings)[0]['kind'] == 'status'
    findings[0]['text_quotes'] = ['학생은 금요일에 통신 시험까지 마쳐 정상 작동을 확인했다.']
    assert normalize_findings(findings)[0]['kind'] == 'roles'


def test_missed_arithmetic_cannot_pass_even_when_both_models_give_a_clean_result(api, monkeypatch):
    client, db, post = api
    unlock(db); use_real_audit(monkeypatch)
    request = score_request()
    request.update(rules=['자료의 사실과 수치를 정확하게 써요.'],
                   text='설문 응답 12개 가운데 중복된 2개를 빼고, 남은 9개를 최종 분석에 사용했다.')
    audited_reply(post, {'on_task': True, 'errors': []}, score_payload(score=10))
    response = client.post('/api/learn/writing-score', json=request)
    assert response.status_code == 200, response.text
    result = response.json()
    assert not result['passed'] and result['on_task'] and result['criteria'][-1]['score'] == 10
    assert result['criteria'][0]['score'] <= 3
    assert '12 - 2 = 10' in result['overall_feedback']
    assert not state(db)['completed']


@pytest.mark.parametrize('persistent', [False, True])
def test_format_server_error_is_regenerated_once_without_default_scores(api, monkeypatch, persistent):
    from fastapi import HTTPException
    client, db, post = api
    unlock(db)
    calls = []
    def grade(messages, **options):
        calls.append(json.loads(json.dumps(messages)))
        if persistent or len(calls) == 1:
            raise HTTPException(502, '생성 응답 형식 오류')
        return json.dumps(score_payload(score=9), ensure_ascii=False)
    monkeypatch.setattr(learn, 'call_qwen', grade)
    response = client.post('/api/learn/writing-score', json=score_request())
    assert len(calls) == 2
    assert 'type, properties, required는 출력 키가 아닙니다.' in calls[1][0]['content']
    if persistent:
        assert response.status_code == 502
        assert 'writing' not in state(db)
    else:
        assert response.status_code == 200, response.text
        assert response.json()['score'] == 90
