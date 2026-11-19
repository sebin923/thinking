from pathlib import Path
import sys
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from application_service_profile import safe_fact,profile_messages,source_checks


def test_count_object_is_explicit_without_inventing_a_person():
    assert safe_fact('재료 바구니는45개 준비함','발표문')=='재료 바구니를 45개 준비했다.'
    assert safe_fact('담당자는45개 준비함','발표문')=='담당자는45개 준비함'


def test_choices_are_not_changed_to_completed_actions():
    req=SimpleNamespace(document_type='speech',topic='후기 카드',target_chars=150,tone='기본',
        facts=['카드를 제출할지는 참가자가 선택함'])
    _,values=profile_messages(req)
    assert '- 카드를 제출할지는 참가자가 선택함' in values[-1]['content']
    assert '참가자가 선택했다' not in values[-1]['content']


def test_free_thought_tense_and_heard_name_keep_the_preserved_builder():
    req=SimpleNamespace(document_type='free_writing',topic='시장',target_chars=150,tone='기본',
        facts=['처음에는 무엇을 더 넣으려 함','처음 듣는 향신료 이름을 메모해 두었다','다른 사람에게 보내지 않고 그대로 보관함'])
    _,values=profile_messages(req)
    text=values[-1]['content']
    assert '넣으려 했다' in text and '처음 듣는 향신료 이름' in text and '보관했다' in text
    assert '처음 봤다' not in text and '넣으려 한다' not in text


def test_role_and_reply_conditions_are_visible_checks_not_silent_rewrites():
    facts=['동료는 나머지40개를 내일 확인할 계획임','받았다는 답이 온 경우에만 수령 완료로 적으려 함']
    text='나머지40개를 내일 확인할 계획입니다. 받은 답이 오면 완료로 적습니다.'
    checks=source_checks(facts,text)
    assert any('주체' in c and '동료' in c for c in checks)
    assert any('수령 확인' in c for c in checks)
    assert not source_checks(facts,'동료는 나머지40개를 내일 확인할 계획입니다. 받았다는 답이 온 경우에만 수령 완료로 적습니다.')


def test_schema_instruction_is_merged_with_existing_system_message():
    from common_llm import with_system_instruction
    original=[{'role':'system','content':'Feedback task'},{'role':'user','content':'Source prose'}]
    actual=with_system_instruction(original,'JSON schema')
    assert [m['role'] for m in actual]==['system','user']
    assert actual[0]['content']=='JSON schema\n\nFeedback task'
    assert original[0]['content']=='Feedback task'
