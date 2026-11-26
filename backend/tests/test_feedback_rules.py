"""명시적 상반 진술과 문장 끝 조사 검사의 적용 범위를 확인한다."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from feedback_grounding import grounded_feedback, source_rows
from feedback_rules import contradiction_items, grammar_items
from qwen_ai import _preserves_revision_facts


@pytest.mark.parametrize('text', [
    '이번 회의는 월요일에 열렸습니다. 그러나 같은 회의는 월요일에 열리지 않았습니다.',
    '저는 안내문을 제출했다. 하지만 저는 안내문을 제출하지 않았다.',
    '담당자는 신청서를 확인하였습니다. 담당자는 신청서를 확인하지 않았다.',
    '민수는 서류를 작성했습니다. 민수는 서류를 작성하지 않았습니다.',
    '저는 원본을 수정하지 않았다. 그러나 제가 원본을 수정했다.',
    '담당자는 명단을 확인한다. 담당자는 명단을 확인하지 않는다.',
    '나는 회의에 안 갔다. 그러나 나는 회의에 갔다.',
])
def test_explicit_opposite_claims_are_flagged_without_deciding_which_is_true(text):
    rows = source_rows(text)
    items = contradiction_items(rows)
    assert len(items) == 1
    assert items[0]['original_text'] == rows[-1]['text']
    assert rows[0]['text'] in items[0]['reason']
    assert '실제 사실인지 확인' in items[0]['suggestion']
    assert items[0]['revised_text'] == ''


@pytest.mark.parametrize('text', [
    '전시회는 월요일에 열렸다. 전시회는 화요일에 열리지 않았다.',
    '민수는 서류를 작성했다. 지수는 서류를 작성하지 않았다.',
    '저는 신청서를 제출했다. 저는 보고서를 제출하지 않았다.',
    '저는 회의에 참석할 계획이었다. 하지만 저는 회의에 참석하지 않았다.',
    '담당자는 원본을 수정했다. 담당자는 사본을 수정하지 않았다.',
    '“회의가 열렸다”는 말과 “회의가 열리지 않았다”는 말은 반대다.',
    '회의는 열렸다고 들었다. 그러나 같은 회의는 열리지 않았다.',
    '회의는 열렸다. 정정하면 같은 회의는 열리지 않았다.',
    '회의는 열렸다. 같은 회의는 열리지 않았을 수도 있다.',
    '회의는 열렸다. 같은 회의는 열리지 않았나요?',
    '담당자는 문서를 확인했다. 담당자는 문서를 확인하지 않는다.',
])
def test_different_contexts_quotes_plans_and_uncertainty_are_not_contradictions(text):
    assert contradiction_items(source_rows(text)) == []


@pytest.mark.parametrize('bad,fixed', [
    ('읽었습니다를', '읽었습니다'), ('확인했습니다가', '확인했습니다'),
    ('맡았습니다이', '맡았습니다'), ('진행해요를', '진행해요'),
    ('방문했어요을', '방문했어요'), ('알렸다를', '알렸다'),
])
def test_bad_particles_after_finite_endings_are_minimal_corrections(bad, fixed):
    text = f'저는 내용을 {bad}. 원본은 아직 수정하지 않았습니다.'
    items = grammar_items(text, source_rows(text), {})
    assert len(items) == 1
    assert items[0]['original_text'] == bad
    assert items[0]['revised_text'] == fixed
    assert grammar_items(text, source_rows(text), {'ai_assistance': 'guided'})[0]['revised_text'] == ''


@pytest.mark.parametrize('text', [
    '저는 도서관에서 책을 읽었습니다.',
    '‘읽었습니다’를 예로 들어 설명했습니다.',
    '코드에는 `읽었습니다를`이라고 적었다.',
    '틀린 문장의 예시는 읽었습니다를.',
    '저는 교실에서 감사합니다를 연습했습니다.',
    '그는 사이다를 마셨다.',
])
def test_valid_sentences_and_language_examples_are_not_particle_errors(text):
    assert grammar_items(text, source_rows(text), {}) == []


def test_local_checks_survive_when_model_misses_both_problems():
    text = '저는 명단을 확인했다. 저는 명단을 확인하지 않았다. 저는 책을 읽었습니다를.'
    call = lambda *args, **kwargs: json.dumps({'issues': []})
    value = grounded_feedback(text, '보고서', {}, '', call, _preserves_revision_facts)
    assert {item['type'] for item in value['highlights']} == {'논리', '문법'}
    assert all(item['original_text'] in text for item in value['highlights'])
