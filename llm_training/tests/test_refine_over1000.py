"""Adversarial checks for the curation boundaries, without training/inference."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import refine_over1000 as q


def control(fact='동료는 상자 12개의 표지를 확인할 계획이며 아직 실행하지 않음',
            answer='동료는 상자 12개의 표지를 확인할 계획이며 아직 실행하지 않았다.'):
    return {'id':'CONTROL','category':'report','topic':'표지 확인',
        'request':{'facts':[fact]},'requested_char_bounds':[10,400],
        'prompt':[{'role':'system','content':'자료만 쓴다.'},{'role':'user','content':'- '+fact}],
        'completion':[{'role':'assistant','content':answer}],
        'assertion_trace':[{'source_fact_index':0,'source':fact,'rendered':answer,'status':'preserved'}],
        '_curation':{'target_edits':[]}}


def corrupt_target(row,before,after):
    r=deepcopy(row)
    r['completion'][0]['content']=r['completion'][0]['content'].replace(before,after)
    # Also change the row's own evidence, so controls cannot pass merely by
    # spotting a stale target hash or trace substring.
    for t in r['assertion_trace']:t['rendered']=t['rendered'].replace(before,after)
    return r


@pytest.mark.parametrize(('before','after','expected'),[
    ('동료는','저는','actor_alignment_review'),
    ('12개','21개','new_number_review'),
    ('실행하지 않았다','실행했다','negative_alignment_review'),
    ('확인할 계획이며','확인했으며','intention_alignment_review'),
])
def test_independent_source_checks_detect_aligned_but_corrupt_targets(before,after,expected):
    row=control()
    assert not q.audit_row(row)
    bad=corrupt_target(row,before,after)
    assert expected in {f['kind'] for f in q.audit_row(bad)}


def test_literal_quotes_and_receipt_conditions_are_not_approximations():
    quote=control('쪽지에 “오후 2시”라고 적음','쪽지에 “오후 2시”라고 적었다.')
    assert 'literal_quote_difference' in {f['kind'] for f in q.audit_row(corrupt_target(quote,'오후 2시','오후 3시'))}
    receipt=control('받았다는 답을 받은 뒤 목록을 넘길 계획임','답을 받은 뒤 목록을 넘길 계획이다.')
    assert 'receipt_condition_review' in {f['kind'] for f in q.audit_row(receipt)}


def test_native_count_aliases_do_not_turn_putting_into_two_places():
    assert '2' not in q.numbers('공동 재료를 둘 곳을 정한다.')
    assert '12' in q.numbers('열두 파일의 이름을 적는다.')
    assert '1' in q.numbers('하나의 버튼을 고른다.')
    assert '2' not in q.numbers('잠깐 둘 수 있다.')


def test_proposal_is_not_a_negative_action():
    row=control('담당자에게 목록 대조를 제안함','담당자에게 목록 대조를 제안했다.')
    assert 'negative_alignment_review' not in {f['kind'] for f in q.audit_row(row)}


def test_source_memos_are_not_expanded_into_completed_choices_or_current_intentions():
    facts=['처음에는 종이를 더 넣으려 함','제출할지는 참가자가 선택함',
           '친구에게 “아직 확인 중”이라고 알림']
    messages=q.curated_messages('free_writing','메모',facts,[120,180])
    assert [m['role'] for m in messages]==['system','user']
    assert all('- '+s in messages[-1]['content'] for s in facts)
    assert '선택했다' not in messages[-1]['content']
    assert '넣으려 한다' not in messages[-1]['content']
    cover=q.curated_messages('cover_letter','역할',facts,[120,180])
    assert '모든 문장을 일인칭' not in str(cover)
    assert '그 사람을 주어로' in cover[0]['content']


def test_identical_heldout_answer_detected_even_without_shared_source_ngrams():
    row=control()
    cases=[{'id':'HOLDOUT','category':'report','facts':['서로 완전히 다른 입력'],
        'answer_digest':q.digest(q.compact(row['completion'][0]['content'])),'origin':'test'}]
    conflicts=q.heldout_conflicts([row],cases)
    assert conflicts[row['id']][0]['same_answer'] is True


@pytest.mark.skipif(not all((folder/'train.jsonl').is_file() for folder in (q.SOURCE, q.PARENT)),
                    reason='Requires preserved local training data; datasets are excluded from Git')
def test_manual_resolutions_cannot_apply_to_changed_content():
    rows={r['id']:r for r in q.staged_rows()}
    row=rows['Q2K4-report-034']
    assert not any(f['kind']=='actor_alignment_review' for f in q.screened_flags(row))
    altered=corrupt_target(row,'녹음 담당자는','저는')
    assert any(f['kind']=='actor_alignment_review' for f in q.screened_flags(altered))


def test_existing_output_directory_is_never_overwritten(tmp_path,monkeypatch):
    monkeypatch.setattr(q,'DEST',tmp_path)
    with pytest.raises(RuntimeError,match='already exists'):q.build()
