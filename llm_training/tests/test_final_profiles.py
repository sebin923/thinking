"""Regression coverage for factual states and the actual serving prompt path."""
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import common_llm as server
from final_writing_profiles import PROFILE_NAME, profile_messages, fit_messages


def test_free_serving_retains_completed_action_and_ignores_title(monkeypatch):
    monkeypatch.setattr(server,'selected_profile',lambda:PROFILE_NAME)
    req=server.DraftRequest(document_type='free_writing',topic='원문에없는재출발',target_chars=150,
        facts=['그 자리에서는 말하지 못함','집에서 메시지로 실제로 전함','답장은 아직 받지 못함'])
    _,messages=server.messages_for(req)
    source=messages[-1]['content']
    assert '원문에없는재출발' not in source
    assert '실제로 전했다.' in source and '받지 못했다.' in source
    assert '전하고 싶' not in source


def test_ambiguous_input_is_rejected_before_loading_gpu(monkeypatch):
    monkeypatch.setattr(server,'selected_profile',lambda:PROFILE_NAME)
    monkeypatch.setattr(server,'load_model',lambda:pytest.fail('Ambiguous input must not load GPU'))
    req=server.DraftRequest(document_type='free_writing',topic='취미',facts=['도구는 보관함'])
    with pytest.raises(HTTPException) as caught:server.draft(req)
    assert caught.value.status_code==422
    assert caught.value.detail['code']=='ambiguous_writing_input'


def test_report_serving_keeps_actor_and_missing_field(monkeypatch):
    monkeypatch.setattr(server,'selected_profile',lambda:PROFILE_NAME)
    req=server.DraftRequest(document_type='report',topic='목록 점검',target_chars=150,
        facts=['2개 항목에 반납 요일이 없었음','동료는 원본에서 요일을 찾아냄','검토자는 번호만 적음'])
    _,messages=server.messages_for(req)
    assert all(f in messages[-1]['content'] for f in req.facts)
    assert '반납 요일' in messages[0]['content'] or '누락' in messages[0]['content']
    assert '주체' in messages[0]['content']


def test_token_budget_removes_complete_examples_without_removing_source():
    class Processor:
        tokenizer=staticmethod(lambda t,**kw:{'input_ids':list(range(len(t.split())))})
        def apply_chat_template(self,values,**kw):return ' '.join(x['content'] for x in values)
    messages=[{'role':'system','content':'instruction'},
        {'role':'user','content':'example one'},{'role':'assistant','content':'answer one'},
        {'role':'user','content':'example two'},{'role':'assistant','content':'answer two'},
        {'role':'user','content':'real actor 71 unfinished facts'}]
    result,stats=fit_messages(messages,Processor(),10)
    assert result[-1]==messages[-1] and result[0]==messages[0]
    assert [m['role'] for m in result]==['system','user','assistant','user']
    assert stats['removed_examples']==1 and len(messages)==6
    with pytest.raises(ValueError):fit_messages(messages,Processor(),3)


def test_loaded_identity_does_not_change_when_selection_file_changes(monkeypatch,tmp_path):
    monkeypatch.setattr(server,'_loaded_identity',{'profile':PROFILE_NAME,'adapter_sha256':'loaded'})
    path=tmp_path/'selection.json';path.write_text('{"writing_profile":"legacy"}')
    monkeypatch.setattr(server,'MODEL_SELECTION_PATH',path)
    assert server.selected_profile()==PROFILE_NAME
    assert server.health()['loaded_identity']['adapter_sha256']=='loaded'


def test_personal_adapter_keeps_existing_prompt(monkeypatch):
    monkeypatch.setattr(server,'selected_profile',lambda:PROFILE_NAME)
    req=server.DraftRequest(document_type='report',topic='번호 확인',facts=['번호를 확인함'],mode='personal',user_id=1)
    assert server.messages_for(req)==server.build_messages(req)
