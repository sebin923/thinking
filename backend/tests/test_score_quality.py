from copy import deepcopy
import json
from unittest.mock import Mock

import pytest

from test_qwen_features import api,reply,score_request,score_payload,unlock
from score_quality import canonicalize_rules,unsupported_han,language_issues,build_summary,OLD_STATE,OLD_SCOPE,STATE_RULE,SCOPE_RULE

def test_canonical_rules_preserve_count_and_separate_state_from_generalization():
    assert canonicalize_rules([OLD_STATE,OLD_SCOPE])==[STATE_RULE,SCOPE_RULE]
    assert canonicalize_rules(['  결과를 먼저 쓴다.  '])==['결과를 먼저 쓴다.']

def test_language_guard_allows_source_quotes_and_rejects_new_sequences():
    assert unsupported_han('인용한 漢字 표현입니다.','자료에 漢字가 있다.')==[]
    assert unsupported_han('교내 체육대会对의 결과','교내 체육대회')==['会对']
    assert unsupported_han('漢字','漢')==['漢字']
    assert unsupported_han('Qwen API 2회, 30%','')==[]

def test_summary_uses_checked_reasons_without_changing_scores():
    scored=[{'score':10,'comment':'역할을 구분했습니다.'},{'score':3,'comment':'자료의 수치와 다릅니다.'},
            {'score':5,'comment':'과제를 일부 수행했습니다.'},{'score':10,'comment':'문법은 바릅니다.'}]
    before=deepcopy(scored)
    assert build_summary(scored,True)=='자료의 수치와 다릅니다.'
    assert scored==before
    assert build_summary(scored,False)=='과제를 일부 수행했습니다. 문법은 바릅니다.'

def test_foreign_raw_summary_is_not_reused_or_retried(api):
    client,db,post=api;unlock(db)
    payload=score_payload();payload['overall_feedback']='학생 미술 전시会的 경험입니다.'
    reply(post,json.dumps(payload,ensure_ascii=False))
    response=client.post('/api/learn/writing-score',json=score_request())
    assert response.status_code==200,response.text
    assert response.json()['score']==90
    assert response.json()['overall_feedback']=='글에 확인한 사실이 나타납니다.'
    assert post.call_count==1

def test_foreign_criterion_reason_is_regenerated_once(api):
    client,db,post=api;unlock(db)
    bad=score_payload();bad['criteria']['criterion_1']['comment']='교내 체육대会对의 자료입니다.'
    good=score_payload()
    first,second=Mock(status_code=200),Mock(status_code=200)
    first.json.return_value={'content':json.dumps(bad,ensure_ascii=False),'adapter':'common'}
    second.json.return_value={'content':json.dumps(good,ensure_ascii=False),'adapter':'common'}
    post.side_effect=[first,second]
    response=client.post('/api/learn/writing-score',json=score_request())
    assert response.status_code==200,response.text
    assert post.call_count==2
    assert '출력 언어 오류' in post.call_args.kwargs['json']['messages'][0]['content']
    assert '체육대会对' not in post.call_args.kwargs['json']['messages'][0]['content']

@pytest.mark.parametrize('field',['comment','next_step'])
def test_persistent_foreign_output_does_not_save_progress(api,field):
    client,db,post=api;unlock(db)
    bad=score_payload()
    if field=='comment':bad['criteria']['criterion_1']['comment']='体験을 잘 썼습니다.'
    else:bad['next_step']='体験을 더 설명하세요.'
    reply(post,json.dumps(bad,ensure_ascii=False))
    response=client.post('/api/learn/writing-score',json=score_request())
    assert response.status_code==502,response.text
    assert post.call_count==2
    from learning_progress import LearningProgress
    assert 'writing' not in db.query(LearningProgress).filter_by(user_id=1).one().payload['units']['report-1']

def test_hanja_already_in_source_is_preserved(api):
    client,db,post=api;unlock(db)
    request=score_request();request['practice']['facts'].append('인용어: 漢字.')
    payload=score_payload();payload['criteria']['criterion_1']['comment']='자료의 漢字 표현을 그대로 인용했습니다.'
    reply(post,json.dumps(payload,ensure_ascii=False))
    response=client.post('/api/learn/writing-score',json=request)
    assert response.status_code==200,response.text
    assert '漢字' in response.json()['overall_feedback']

def test_input_rules_are_normalized_before_training_collection():
    from routers.learn import LearnScoreIn
    request=score_request();request['rules']=[OLD_STATE,OLD_SCOPE]
    data=LearnScoreIn(**request)
    assert data.rules==[STATE_RULE,SCOPE_RULE]
