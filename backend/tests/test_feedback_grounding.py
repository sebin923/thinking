"""모델 판단과 별개로 지켜야 하는 인용·수량·표기·교체 안전 규칙."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import feedback_grounding as grounding
from qwen_ai import _preserves_revision_facts


def test_source_ids_retain_exact_original_with_offsets():
    content = '  수치 1.5를 기록했다.\n\n원본은 수정하지 않았다.  '
    rows = grounding.source_rows(content)
    assert len(rows) == 2
    assert [row['id'] for row in rows] == ['S1', 'S2']
    assert all(content[row['start']:row['end']] == row['text'] for row in rows)


@pytest.mark.parametrize('target,expected', [
    ('따라서 자료 9개가 모두 정확하다고 결론 냈다.', True),
    ('따라서 9개 모두 정확하다고 결론 냈다.', True),
    ('따라서 자료 전체가 틀렸다고 결론 냈다.', True),
    ('따라서 자료 전체의 정확성은 아직 판단할 수 없다.', False),
    ('따라서 안내판 9개는 모두 정리되어 있었다.', False),
    ('따라서 자료 9개는 모두 목록에 실려 있다.', False),
    ('따라서 자료 전체가 정확할 수도 있다.', False),
    ('자료 9개는 모두 정리되어 있었다.', False),
    ('“따라서 자료 9개 모두 정확하다”는 잘못된 결론이다.', False),
])
def test_scope_proof_does_not_invent_results_or_mix_objects(target, expected):
    text = '자료 9개 중 3개만 확인했다. 나머지 6개는 아직 확인하지 않았다. ' + target
    items = grounding.scope_items(grounding.source_rows(text))
    assert bool(items) == expected
    if items:
        assert items[0]['original_text'] == target
        assert items[0]['target_id'] == 'S3'
        assert items[0]['revised_text'] == ''
        assert '정상' not in items[0]['suggestion']


@pytest.mark.parametrize('text', [
    '장비 5대 중 2대만 시험했다. 나머지 3대는 아직 시험하지 않았다.',
    '장비 5대 중 2대만 시험했다. 나머지 2대는 아직 시험하지 않았다. 따라서 장비 모두 정상이다.',
    '장비 5대 중 2대만 시험했다. 나머지 3대도 시험했고 정상이었다. 따라서 장비 모두 정상이다.',
    '장비 5대 중 5대를 시험했다. 나머지는 미확인이다. 따라서 장비 모두 정상이다.',
])
def test_scope_rules_are_conservative_outside_explicit_partial_inspection(text):
    assert grounding.scope_items(grounding.source_rows(text)) == []


@pytest.mark.parametrize('text,expected', [
    ('제 역활은 표기를 점검하는 것입니다.', ['역활']),
    ('역활이 아니라 역할이라고 써야 한다.', []),
    ('역활은 틀린 표기다.', []),
    ('교사는 “역활”이라는 오탈자를 설명했다.', []),
    ('코드 예시는 `역활`이고 실제 안내문의 표기는 역할이다.', []),
    ('몇일 뒤에 제가 맡은 역활을 발표합니다.', ['몇일', '역활']),
    ('명단을 확인할수 없었습니다.', ['확인할수']),
    ('역활이 아니라 역할이라고 써야 한다며 몇일 뒤 다시 설명했다.', ['몇일']),
])
def test_spelling_distinguishes_errors_from_explanations_and_quotes(text, expected):
    items = grounding.spelling_items(text, grounding.source_rows(text), {})
    assert [item['original_text'] for item in items] == expected
    guided = grounding.spelling_items(text, grounding.source_rows(text), {'ai_assistance': 'guided'})
    assert all(item['revised_text'] == '' for item in guided)


@pytest.mark.parametrize('original,revised', [
    ('여섯 개를 확인했습니다.', '세 개를 확인했습니다.'),
    ('민수가 확인하고 지수가 기록했다.', '지수가 확인하고 민수가 기록했다.'),
    ('아직 시험하지 않았다.', '정상적으로 작동했다.'),
    ('충전기 2대와 안내판 2개를 확인했다.', '충전기 2대와 안내판 3개를 확인했다.'),
    ('답장이 오면 제가 확인합니다.', '제가 확인합니다.'),
    ('저는 안내판을 확인했습니다.', '안내판을 확인했습니다.'),
])
def test_automatic_replacements_cannot_change_facts_or_actor_action_relations(original, revised):
    assert grounding.safe_revision(original, revised, _preserves_revision_facts) == ''


@pytest.mark.parametrize('original,revised', [
    ('제 역활은 기록입니다.', '제 역할은 기록입니다.'),
    ('명단을 확인할수 없었습니다.', '명단을 확인할 수 없었습니다.'),
    ('제가 확인했다.', '제가 확인했습니다.'),
])
def test_mechanical_corrections_can_still_be_applied(original, revised):
    assert grounding.safe_revision(original, revised, _preserves_revision_facts) == revised


def test_invalid_ids_are_not_used_as_display_quotes():
    rows = grounding.source_rows('확인한 내용을 기록했다.')
    item = {'target_id': 'S999', 'evidence_ids': [], 'type': '표현',
            'reason': '표현을 다듬습니다.', 'suggestion': '다시 써 보세요.', 'revised_text': ''}
    with pytest.raises(ValueError, match='문장 번호'):
        grounding.parse_issues(json.dumps({'issues': [item]}), rows)


@pytest.mark.parametrize('reason,suggestion', [
    ('출입문은 닫혀 있었다.', '출입문은 닫혀 있었다.'),
    ('출입문은 닫혀 있었다.', '표현을 고쳐 주세요.'),
    ('닫힌 출입문을 설명한 문장입니다.', '닫힌 출입문을 설명해 주세요.'),
])
def test_restatement_of_a_normal_fact_is_not_an_error(reason, suggestion):
    rows = grounding.source_rows('출입문은 닫혀 있었다.')
    value = {'issues': [{'target_id': 'S1', 'evidence_ids': ['S1'], 'type': '표현',
                        'reason': reason, 'suggestion': suggestion, 'revised_text': ''}]}
    assert grounding.parse_issues(json.dumps(value), rows) == []


def test_reviewer_must_return_each_candidate_once():
    raw = {'reviews': [{'issue_id': 'C1', 'verdict': 'confirmed'}, {'issue_id': 'C1', 'verdict': 'confirmed'}]}
    with pytest.raises(ValueError, match='재검토'):
        grounding.approved_indexes(json.dumps(raw), 2)


def test_combined_feedback_keeps_logic_and_spacing_and_ignores_model_summary():
    content = '상자 11개 중 4개만 검사했다. 나머지 7개는 아직 검사하지 않았다. 따라서 상자가 전부 정상이다. 명단은 확인할수 없다.'
    seen = []
    def call(messages, **kwargs):
        seen.append(kwargs['schema'])
        return json.dumps({'issues': []})
    result = grounding.grounded_feedback(content, '보고서', {}, '', call, _preserves_revision_facts)
    assert {item['type'] for item in result['highlights']} == {'논리', '맞춤법'}
    assert all(item['original_text'] in content for item in result['highlights'])
    assert '논리' in result['overall_feedback'] and '맞춤법' in result['overall_feedback']
    assert len(seen) == 1


def test_brief_and_guided_apply_after_all_verified_items_are_combined():
    items = [{'original_text': word, 'type': kind, 'reason': '이유입니다.',
              'suggestion': '고쳐 보세요.', 'revised_text': '바른 표기'}
             for word, kind in [('역활', '맞춤법'), ('전체 결론', '논리'), ('반복 문장', '표현')]]
    result = grounding.finish_feedback(items, {'feedback_style': 'brief', 'ai_assistance': 'guided'})
    assert len(result['highlights']) == 3
    assert all(item['revised_text'] == '' for item in result['highlights'])
    assert '표현' in result['overall_feedback']
    assert '오류가 없' not in grounding.finish_feedback([], {}, deferred=True)['overall_feedback']


@pytest.mark.parametrize('revision', ['동료는 원본을 수정했습니다.', '제가 원본 3장을 수정했습니다.'])
def test_model_approval_cannot_enable_a_fact_changing_replacement(revision):
    text = '제가 원본 2장은 아직 수정하지 않았습니다.'
    issue = {'target_id': 'S1', 'evidence_ids': ['S1'], 'type': '문법',
             'reason': '조사 연결이 어색합니다.', 'suggestion': '원문의 사실은 유지하고 조사만 확인하세요.',
             'revised_text': revision}
    def call(messages, **kwargs):
        if 'reviews' in kwargs['schema']['properties']:
            return json.dumps({'reviews': [{'issue_id': 'C1', 'verdict': 'confirmed'}]})
        return json.dumps({'issues': [issue]})
    value = grounding.grounded_feedback(text, '보고서', {}, '', call, _preserves_revision_facts)
    assert value['highlights'][0]['original_text'] == text
    assert value['highlights'][0]['revised_text'] == ''
    assert '문법' in value['overall_feedback']
