"""어미·조사 검사를 늘려도 정상 높임말과 인용, 채점을 바꾸지 않는다."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from feedback_grounding import grounded_feedback, safe_revision, source_rows, spelling_items
from feedback_rules import grammar_items
from feedback_spelling import spelling_findings
from qwen_ai import _preserves_revision_facts
from score_evidence import spelling_findings as grading_spelling_findings


@pytest.mark.parametrize('wrong,right', [
    ('정리할께요', '정리할게요'), ('해드릴께요', '해드릴게요'),
    ('찾아갈께', '찾아갈게'), ('받을께요', '받을게요'),
    ('될께요', '될게요'), ('읽을께요', '읽을게요'),
    ('되요', '돼요'), ('뵈요', '봬요'), ('웬지', '왠지'), ('오랫만', '오랜만'),
])
def test_more_spelling_errors_are_grounded_and_have_minimal_corrections(wrong, right):
    text = '저는 ' + wrong + '. 아직 원본은 수정하지 않았습니다.'
    findings = spelling_findings(text)
    assert len(findings) == 1
    item = findings[0]
    assert text[item['start']:item['end']] == wrong
    assert item['suggested'] == right
    value = spelling_items(text, source_rows(text), {})
    assert value[0]['revised_text'] == right
    assert safe_revision(wrong, right, _preserves_revision_facts) == right


@pytest.mark.parametrize('text', [
    '선생님께 편지를 보냈습니다.', '선물은 아들께요.', '가족들께 감사드립니다.',
    '동료에게 말씀드릴게요.', '내일 뵈어요.', '내일 봬요.', '모임에 가도 돼요.',
    '이게 웬일인가요?', '물건의 금새를 알아봤다.', '오랫동안 기다렸습니다.',
    '‘할께요’는 ‘할게요’로 고쳐야 한다.',
    '뵈요가 아니라 봬요라고 써야 한다.',
    '코드 예시는 `되요`입니다.',
])
def test_valid_honorifics_forms_and_teaching_are_not_edited(text):
    assert spelling_items(text, source_rows(text), {}) == []


@pytest.mark.parametrize('text,wrong,right', [
    ('저는 학회를 가입했습니다.', '학회를', '학회에'),
    ('저는 사진 동아리를 가입했다.', '동아리를', '동아리에'),
    ('저는 보험을 아직 가입하지 않았습니다.', '보험을', '보험에'),
    ('저는 서비스를 가입할 계획입니다.', '서비스를', '서비스에'),
    ('저는 동호회를 가입할께요.', '동호회를', '동호회에'),
])
def test_join_particle_edits_preserve_tense_and_negation(text, wrong, right):
    items = grammar_items(text, source_rows(text), {})
    assert len(items) == 1
    assert items[0]['original_text'] == wrong
    assert items[0]['revised_text'] == right
    assert text.replace(wrong, right).endswith(text[text.index(' 가입'):])


@pytest.mark.parametrize('text', [
    '저는 학회에 가입했습니다.',
    '저는 학생들을 동아리에 가입시켰다.',
    '담당자는 그 단체를 가입하게 했다.',
    '담당자는 그 모임을 가입하지 못하게 했다.',
    '저는 동아리를 가입 대상으로 골랐다.',
    '‘동아리를 가입했다’라는 표현을 설명했다.',
    '예문은 동아리를 가입했다.',
    '저는 학회를 방문했습니다.',
])
def test_join_rules_do_not_rewrite_causatives_quotes_or_other_verbs(text):
    assert grammar_items(text, source_rows(text), {}) == []


def test_feedback_spelling_extension_does_not_change_grading_observations():
    text = '제가 정리할께요. 내일 뵈요.'
    assert len(spelling_findings(text)) == 2
    assert grading_spelling_findings(text) == []


def test_multiple_errors_are_combined_without_overlapping_replacement_ranges():
    text = '저는 동호회를 가입할께요. 원본은 아직 확인하지 않았습니다.'
    call = lambda *args, **kwargs: json.dumps({'issues': []})
    value = grounded_feedback(text, '보고서', {}, '', call, _preserves_revision_facts)
    assert {item['type'] for item in value['highlights']} == {'맞춤법', '문법'}
    assert {item['original_text'] for item in value['highlights']} == {'동호회를', '가입할께요'}
    revised = text
    for item in value['highlights']:
        revised = revised.replace(item['original_text'], item['revised_text'])
    assert revised == '저는 동호회에 가입할게요. 원본은 아직 확인하지 않았습니다.'
    guided = grounded_feedback(text, '보고서', {'ai_assistance': 'guided'}, '', call, _preserves_revision_facts)
    assert all(item['revised_text'] == '' for item in guided['highlights'])


@pytest.mark.parametrize('style', ['brief', 'detailed'])
def test_verified_errors_are_not_lost_to_display_limits(style):
    text = ('제 역활은 기록 정리입니다. 몇일 뒤에 발표할께요. 필요하면 정리해도 되요. '
            '내일 다시 뵈요. 웬지 마음이 편했습니다. 오랫만에 자료를 확인했습니다. '
            '아직 명단은 확인할수 없습니다. 저는 학회를 가입했습니다. 저는 원본을 열지 않았습니다를.')
    call = lambda *args, **kwargs: json.dumps({'issues': []})
    value = grounded_feedback(text, '보고서', {'feedback_style': style, 'ai_assistance': 'guided'}, '', call, _preserves_revision_facts)
    assert len(value['highlights']) == 10
    assert all(item['original_text'] in text for item in value['highlights'])
    assert all(item['revised_text'] == '' for item in value['highlights'])
