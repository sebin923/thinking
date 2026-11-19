"""The deployed candidate must preserve the frozen evaluation prompts."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import common_llm as server
from curated_writing_profile import PROFILE_NAME,profile_messages
from curated_writing_profile import edit_preferences,prose_sentences
from curated_writing_profile import restore_source_actors

LOCAL_CASES = ROOT/'outputs/curated_1459_study_20261119/inputs.json'
requires_local_comparison = pytest.mark.skipif(
    not LOCAL_CASES.is_file(), reason='Requires local comparison artifacts; training outputs are excluded from Git')


@requires_local_comparison
def test_all_frozen_case_prompts_are_reproduced_without_source_expansion():
    cases=json.loads((ROOT/'outputs/curated_1459_study_20261119/inputs.json').read_text(encoding='utf-8'))
    assert len(cases)==56
    for c in cases:
        req=SimpleNamespace(document_type=c['genre'],topic=c['topic'],facts=c['facts'],
            target_chars=round(sum(c['bounds'])/2),tone='기본',source_context=c.get('source_context',''))
        _,messages=profile_messages(req,bounds=c['bounds'])
        assert messages==c['prompt'],c['id']


@requires_local_comparison
def test_actual_serving_path_matches_all_40_fresh_inputs(monkeypatch):
    monkeypatch.setattr(server,'selected_profile',lambda:PROFILE_NAME)
    cases=json.loads((ROOT/'outputs/curated_1459_study_20261119/inputs.json').read_text(encoding='utf-8'))
    for c in cases[:40]:
        req=server.DraftRequest(document_type=c['genre'],topic=c['topic'],facts=c['facts'],
            target_chars=round(sum(c['bounds'])/2))
        assert server.messages_for(req)[1]==c['prompt'],c['id']


def test_ambiguous_storage_rejected_before_model_loading(monkeypatch):
    monkeypatch.setattr(server,'selected_profile',lambda:PROFILE_NAME)
    monkeypatch.setattr(server,'load_model',lambda:pytest.fail('Ambiguity must not load GPU'))
    req=server.DraftRequest(document_type='free_writing',topic='보관',facts=['도구는 보관함'])
    with pytest.raises(HTTPException) as caught:server.draft(req)
    assert caught.value.status_code==422
    assert caught.value.detail['code']=='ambiguous_writing_input'


def test_explicit_tone_and_preferences_still_apply_without_changing_facts(monkeypatch):
    monkeypatch.setattr(server,'selected_profile',lambda:PROFILE_NAME)
    facts=['처음에는 빈 줄에 그림을 더 넣으려 함','카드를 제출할지는 참가자가 선택함']
    req=server.DraftRequest(document_type='speech',topic='선택',facts=facts,tone='친근',
        user_preferences=server.WritingPreferences(preferred_tone='formal',sentence_length='short'))
    _,messages=server.messages_for(req)
    assert all('- '+f in messages[-1]['content'] for f in facts)
    assert '요청 말투' in messages[0]['content'] and '사용자 문체 설정' in messages[0]['content']
    assert '선택했다' not in messages[-1]['content'] and '넣으려 한다' not in messages[-1]['content']


def test_personal_requests_keep_the_existing_prompt(monkeypatch):
    monkeypatch.setattr(server,'selected_profile',lambda:PROFILE_NAME)
    req=server.DraftRequest(document_type='report',topic='목록',facts=['번호를 대조함'],mode='personal',user_id=1)
    assert server.messages_for(req)==server.build_messages(req)


def test_surface_editing_changes_formality_and_rhythm_without_dropping_clauses():
    text='저는 신청서 12장을 비교했습니다. 그중 2장에는 시간이 없었습니다. 동료가 시간을 확인했습니다. 저는 원본을 아직 수정하지 않았습니다.'
    formal=edit_preferences(text,server.WritingPreferences(preferred_tone='formal'))
    assert '비교하였습니다.' in formal and '확인하였습니다.' in formal
    long=edit_preferences(text,server.WritingPreferences(sentence_length='long'))
    assert len(prose_sentences(long))<len(prose_sentences(text))
    for phrase in ('신청서 12장','2장','동료가 시간을 확인','저는 원본을 아직 수정하지 않았습니다'):
        assert phrase in long
    assert edit_preferences(text,None)==text


def test_short_splits_past_coordination_and_preserves_each_subject():
    text='담당자가 신청서 12장을 시간표와 비교했고, 동료는 신청자에게 연락해 빠진 시간을 확인했으며, 저는 원본을 아직 수정하지 않았습니다.'
    short=edit_preferences(text,server.WritingPreferences(sentence_length='short'))
    assert len(prose_sentences(short))==3
    for phrase in ('담당자가 신청서 12장','동료는 신청자에게','저는 원본을 아직 수정하지 않았습니다'):
        assert phrase in short


@pytest.mark.parametrize('text',[
    '받았다는 답장이 오면 확인한다. 보내기만 한 상태다.',
    '희망자에만 카드를 나눠 준다. 다른 사람은 선택하지 않았다.',
])
def test_quotes_conditions_and_status_are_not_rewritten(text):
    assert edit_preferences(text,server.WritingPreferences(preferred_tone='formal',sentence_length='long'))==text


def test_quoted_speech_and_decimal_are_retained_verbatim():
    text='담당자는 “아직 수정하지 않았다.”라고 말했다. 저는 1.5시간 뒤에 확인했다.'
    edited=edit_preferences(text,server.WritingPreferences(preferred_tone='formal',sentence_length='long'))
    assert '“아직 수정하지 않았다.”' in edited
    assert '1.5시간' in edited
    assert len(prose_sentences(edited))==2


def test_confident_tone_does_not_turn_uncertainty_or_plans_into_facts():
    text='결과가 좋은지는 아직 모른다. 동료가 내일 확인할 계획이다.'
    assert edit_preferences(text,server.WritingPreferences(preferred_tone='confident'))==text


def test_restores_narrator_after_other_person_without_transferring_their_action():
    facts=['담당자가 신청자에게 확인했고, 저는 확인된 표기를 별도 메모에 적었다.']
    text='담당자가 신청자에게 확인했고, 확인된 표기는 별도 메모에 적었습니다.'
    edited,notes,count=restore_source_actors(text,facts,'자기소개서')
    assert edited=='담당자가 신청자에게 확인했고, 저는 확인된 표기를 별도 메모에 적었습니다.'
    assert count==1 and not notes
    assert '담당자가 신청자에게 확인' in edited


def test_restores_narrator_after_colleague_plan_and_retains_its_future_status():
    facts=['동료가 다음 주에 내용을 살펴볼 계획이라고 말했다.','나는 안에 무엇이 있는지는 모른다고 적었다.']
    text='동료가 다음 주에 내용을 살펴볼 계획이라고 말했다. 안에 무엇이 있는지는 모른다고 적었다.'
    edited,notes,count=restore_source_actors(text,facts,'자유 글쓰기')
    assert edited.endswith('나는 안에 무엇이 있는지는 모른다고 적었다.')
    assert '동료가 다음 주에 내용을 살펴볼 계획' in edited
    assert count==1 and not notes


def test_never_assigns_shared_action_to_narrator_by_guessing():
    facts=['저는 확인된 번호를 별도 메모에 기록했다.','동료는 확인된 번호를 별도 메모에 기록했다.']
    text='확인된 번호를 별도 메모에 기록했습니다.'
    edited,notes,count=restore_source_actors(text,facts,'자기소개서')
    assert edited==text and count==0 and notes


@pytest.mark.parametrize('facts,text',[
    (['담당자가 별도 메모에 번호를 기록했다.'],'담당자가 별도 메모에 번호를 기록했습니다.'),
    (['메모에는 “나는 별도 메모에 번호를 기록했다.”라고 적혀 있다.'],'별도 메모에 번호를 기록했다.'),
    (['저는 별도 메모에 번호를 기록했다.'],'다른 문장에 제목을 붙였습니다.'),
])
def test_does_not_invent_narrator_from_genre_quotes_or_unmatched_actions(facts,text):
    edited,notes,count=restore_source_actors(text,facts,'자기소개서')
    assert edited==text and count==0


def test_actor_restoration_is_idempotent_and_survives_preference_editing():
    facts=['담당자가 신청자에게 확인했다.','저는 확인된 표기를 별도 메모에 적었다.']
    text='담당자가 신청자에게 확인했습니다. 확인된 표기는 별도 메모에 적었습니다.'
    restored,_,count=restore_source_actors(text,facts,'자기소개서')
    assert count==1
    for length in ('short','normal','long'):
        edited=edit_preferences(restored,server.WritingPreferences(preferred_tone='formal',sentence_length=length))
        assert '담당자가' in edited and '저는 확인된 표기를 별도 메모에 적' in edited
    assert restore_source_actors(restored,facts,'자기소개서')[0]==restored


def test_structured_chat_regenerates_once_and_validates_the_replacement(monkeypatch):
    monkeypatch.setattr(server,'load_model',lambda:None)
    monkeypatch.setattr(server,'_model',SimpleNamespace(set_adapter=lambda _:None,eval=lambda:None))
    replies=iter(['{"wrong":"값"}', '{"question":"실제 경험을 설명해 보세요."}'])
    calls=[]
    def generate(messages,maximum,structured):
        calls.append(messages)
        assert structured
        return next(replies)
    monkeypatch.setattr(server,'_chat_text',generate)
    schema={'type':'object','properties':{'question':{'type':'string','minLength':1}},'required':['question']}
    result=server.chat(server.ChatRequest(messages=[server.ChatMessage(role='user',content='실제 경험을 묻는 문항을 추천하세요.')],schema_spec=schema))
    assert result['format_attempts']==2 and result['adapter']=='base'
    assert json.loads(result['content'])=={'question':'실제 경험을 설명해 보세요.'}
    assert calls[1][-1]['content']=='실제 경험을 묻는 문항을 추천하세요.'
    assert sum(m['role']=='system' for m in calls[1])==1


def test_structured_chat_does_not_fabricate_values_after_two_invalid_responses(monkeypatch):
    monkeypatch.setattr(server,'load_model',lambda:None)
    monkeypatch.setattr(server,'_model',SimpleNamespace(set_adapter=lambda _:None,eval=lambda:None))
    calls=[]
    def generate(*args):
        calls.append(1)
        return '{"score":99} extra text'
    monkeypatch.setattr(server,'_chat_text',generate)
    req=server.ChatRequest(messages=[server.ChatMessage(role='user',content='채점')],schema_spec={'type':'object','properties':{'score':{'type':'integer','minimum':0,'maximum':10}},'required':['score']})
    with pytest.raises(HTTPException) as caught:server.chat(req)
    assert caught.value.status_code==502 and len(calls)==2


def test_truncated_structured_response_gets_one_concise_regeneration(monkeypatch):
    monkeypatch.setattr(server,'load_model',lambda:None)
    monkeypatch.setattr(server,'_model',SimpleNamespace(set_adapter=lambda _:None,eval=lambda:None))
    calls=[]
    def generate(messages,*args):
        calls.append(messages)
        if len(calls)==1:raise ValueError('응답이 토큰 제한으로 중단되었습니다.')
        return '{"question":"본인이 한 일을 설명해 보세요."}'
    monkeypatch.setattr(server,'_chat_text',generate)
    req=server.ChatRequest(messages=[server.ChatMessage(role='user',content='새 문항을 추천하세요.')],schema_spec={'type':'object','properties':{'question':{'type':'string','minLength':1}},'required':['question']})
    assert server.chat(req)['format_attempts']==2
    assert '간결하게' in calls[1][0]['content']
