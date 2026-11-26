from copy import deepcopy
import json
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

ROOT=Path(__file__).resolve().parent
if (ROOT/'candidate/backend/tests').is_dir():sys.path.insert(0,str(ROOT/'candidate/backend/tests'))
from test_qwen_features import api,reply,score_request,score_payload,unlock
from score_evidence import sentences,spelling_findings,evidence_context,grounding_issues

def test_sentence_offsets_preserve_decimal_numbers_and_original_words():
    text='온도는 21.5도였다. 동료가 프로그램을 작성했다.\n완료 여부는 아직 확인되지 않았다.'
    rows=sentences(text,'S')
    assert len(rows)==3 and rows[0]['text']=='온도는 21.5도였다.'
    assert all(text[r['start']:r['end']]==r['text'] for r in rows)

def test_spelling_rules_do_not_treat_quotes_code_or_regional_activity_as_errors():
    text='지역활동이 완료됬다. \'됬다\'는 잘못된 표기의 예다. `됬다`는 코드다. 역활을 확인할수 있다.'
    found=spelling_findings(text)
    assert len([r for r in found if r['kind']=='role_word'])==1
    assert sum(not r['quoted'] for r in found)==3
    assert sum(r['quoted'] for r in found)==2

def test_evidence_pairs_only_reference_original_sentences():
    context=evidence_context('동료가 제어 프로그램을 작성했다. 본인은 측정을 맡았다.',
                             '제어 프로그램도 제가 작성했습니다. 측정 결과는 기록으로 남겼습니다.')
    source={r['id']:r for r in context['source']};target={r['id']:r for r in context['submission']}
    for pair in context['pairs']:
        assert pair['source_id']in source and pair['submission_id']in target
        assert all(v in source[pair['source_id']]['text'] for values in pair['source_marks'].values() for v in values)

def test_quote_checker_allows_grounded_correction_and_rejects_fabricated_evidence():
    normalized={'criteria':[{'index':1,'score':7,'comment':'‘완료됐다’로 고쳐야 합니다.'},
                             {'index':2,'score':7,'comment':'표기를 고쳐야 합니다.'}]}
    assert grounding_issues(normalized,'자료 공유가 완료됬다.','')==[]
    normalized['criteria'][0]['comment']='‘제대로 작성했습니다.’처럼 역할을 구분했습니다.'
    assert grounding_issues(normalized,'제어 프로그램도 제가 작성했습니다.','동료가 작성했다.')[0]['kind']=='quote_not_in_input'

def test_known_unquoted_typo_with_perfect_grammar_is_regenerated(api):
    client,db,post=api;unlock(db)
    request=score_request();request['text']='자료실 안내판과 실제 책장 위치를 확인하고 담당자에게 전달한 뒤 기록 정리가 완료됬다.'
    bad=score_payload(score=10);good=score_payload(score=9)
    good['criteria']['criterion_3']={'score':7,'comment':'‘완료됬다’는 ‘완료됐다’로 고쳐야 합니다.'}
    first,second=Mock(status_code=200),Mock(status_code=200)
    first.json.return_value={'content':json.dumps(bad,ensure_ascii=False),'adapter':'common'}
    second.json.return_value={'content':json.dumps(good,ensure_ascii=False),'adapter':'common'}
    post.side_effect=[first,second]
    response=client.post('/api/learn/writing-score',json=request)
    assert response.status_code==200,response.text
    assert post.call_count==2 and response.json()['criteria'][-1]['score']==7
    assert '맞춤법 관찰' in post.call_args.kwargs['json']['messages'][1]['content']

def test_quoted_typo_does_not_force_a_penalty(api):
    client,db,post=api;unlock(db)
    request=score_request();request['text']='문장에서 ‘됬다’는 틀린 표기의 예로 인용한 것이며, 바른 표기인 ‘됐다’를 함께 제시하여 차이를 설명했습니다.'
    payload=score_payload(score=10);reply(post,json.dumps(payload,ensure_ascii=False))
    response=client.post('/api/learn/writing-score',json=request)
    assert response.status_code==200,response.text
    assert post.call_count==1 and response.json()['criteria'][-1]['score']==10

def test_persistent_invented_quote_cannot_save_progress(api):
    client,db,post=api;unlock(db)
    payload=score_payload();payload['criteria']['criterion_1']['comment']='‘제대로 작성했습니다.’라는 문장에서 역할이 드러납니다.'
    reply(post,json.dumps(payload,ensure_ascii=False))
    response=client.post('/api/learn/writing-score',json=score_request())
    assert response.status_code==502,response.text
    assert post.call_count==2
    from learning_progress import LearningProgress
    assert 'writing' not in db.query(LearningProgress).filter_by(user_id=1).one().payload['units']['report-1']
