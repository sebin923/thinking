"""같은 수량 진술의 충돌만 찾고 집계 범위·시점·단위를 섞지 않는다."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from feedback_grounding import grounded_feedback, source_rows
from feedback_rules import numeric_contradiction_items
from qwen_ai import _preserves_revision_facts


@pytest.mark.parametrize('text', [
    '올해 행사 참가자는 정확히 7명입니다. 같은 행사의 올해 참가자는 정확히 9명입니다.',
    '오늘 신청 건수는 12건입니다. 오늘 신청 건수는 15건입니다.',
    '행사 예산은 1,000원입니다. 같은 행사 예산은 2,000원입니다.',
    '어제 전체 참석 인원은 14명이었습니다. 어제 전체 참석 인원은 16명이었습니다.',
    '올해 검토 문서는 총 23개이다. 해당 올해 검토 문서는 총 24개이다.',
])
def test_exact_quantity_conflicts_are_reported_with_both_source_statements(text):
    rows = source_rows(text)
    items = numeric_contradiction_items(rows)
    assert len(items) == 1
    assert items[0]['original_text'] == rows[-1]['text']
    assert rows[0]['text'] in items[0]['reason']
    assert items[0]['revised_text'] == ''


@pytest.mark.parametrize('text', [
    '참가자는 7명입니다. 참가자는 7명입니다.',
    '예산은 1,000원입니다. 예산은 1000원입니다.',
    '참가자는 7명입니다. 참가자는 7.0명입니다.',
    '오늘 참가자는 7명입니다. 어제 참가자는 9명입니다.',
    '올해 참가자는 7명입니다. 작년 참가자는 9명입니다.',
    '전체 참가자는 7명입니다. 여성 참가자는 4명입니다.',
    '신청자는 7명입니다. 참석자는 5명입니다.',
    '회의 시간은 60분입니다. 회의 시간은 1시간입니다.',
    '참가자는 최소 7명입니다. 참가자는 9명입니다.',
    '참가자는 약 7명입니다. 참가자는 9명입니다.',
    '참가자는 7명 이상입니다. 참가자는 9명입니다.',
    '참가자는 7명입니다. 정정하면 참가자는 9명입니다.',
    '“참가자는 7명입니다.”와 “참가자는 9명입니다.”를 비교했다.',
    '참가자는 7명입니다. 참가자는 9명일 수도 있다.',
    '참가자는 7명이었습니다. 참가자는 9명입니다.',
    '행사 총원은 7명입니다. 다른 행사 총원은 9명입니다.',
])
def test_different_scopes_or_non_exact_values_are_not_reported(text):
    assert numeric_contradiction_items(source_rows(text)) == []


def test_numeric_feedback_does_not_choose_a_correct_number_for_the_user():
    text = '올해 참가자는 정확히 11명입니다. 올해 참가자는 정확히 12명입니다.'
    call = lambda *args, **kwargs: json.dumps({'issues': []})
    value = grounded_feedback(text, '보고서', {}, '', call, _preserves_revision_facts)
    assert len(value['highlights']) == 1
    item = value['highlights'][0]
    assert item['type'] == '논리' and item['revised_text'] == ''
    assert '수치를 다시 확인' in item['suggestion']
