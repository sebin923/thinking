"""채점 기준 정리 및 노출할 평가 설명의 언어 검사. 점수는 변경하지 않는다."""
import re

OLD_STATE='자료에 제시된 확인 범위·미완료 상태·조건부 계획을 해당 활동에 맞게 정확히 전달한다.'
OLD_SCOPE='자료에 제시된 경험이나 관찰의 범위를 해당 활동에 맞게 정확히 전달한다.'
STATE_RULE=('자료에 명시된 계획·미확인·미완료·승인 상태를 해당 활동에 맞게 그대로 전달한다. '
            '결과를 모든 상황으로 일반화했는지는 이 항목에서 평가하지 않는다.')
SCOPE_RULE=('결론을 자료가 뒷받침하는 경험·관찰의 범위로 한정한다. '
            '계획이나 완료 상태를 바꾸었는지는 이 항목에서 평가하지 않는다.')
RULE_REPLACEMENTS={OLD_STATE:STATE_RULE,OLD_SCOPE:SCOPE_RULE}
_HAN=re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002fa1f]+')

def canonicalize_rules(rules):
    return [RULE_REPLACEMENTS.get(rule.strip(),rule.strip()) for rule in rules]

def unsupported_han(text,source_text):
    return sorted({m.group(0) for m in _HAN.finditer(text) if m.group(0) not in source_text})

def language_issues(normalized,source_text):
    """Raw overall_feedback is discarded; inspect every model-authored field that will be shown."""
    issues=[]
    for item in normalized.get('criteria',[]):
        comment=item.get('comment')
        if isinstance(comment,str):
            foreign=unsupported_han(comment,source_text)
            if foreign:issues.append({'field':f"criteria.criterion_{item['index']}.comment",'segments':foreign})
    next_step=normalized.get('next_step')
    if isinstance(next_step,str):
        foreign=unsupported_han(next_step,source_text)
        if foreign:issues.append({'field':'next_step','segments':foreign})
    return issues

def build_summary(scored,on_task):
    """Copy complete, already checked reasons. Do not invent facts or silently change scores."""
    if not scored:raise ValueError('요약할 채점 항목이 없습니다.')
    if not on_task:
        selected=[scored[-2]]
        if scored[-1]['score']>=7:selected.append(scored[-1])
    else:
        selected=[min(enumerate(scored),key=lambda pair:(pair[1]['score'],pair[0]))[1]]
    comments=[]
    for item in selected:
        text=item['comment'].strip()
        if text and text not in comments:comments.append(text)
    if not comments:raise ValueError('요약할 평가 근거가 없습니다.')
    return ' '.join(comments)
