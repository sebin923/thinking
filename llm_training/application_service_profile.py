"""Conservative local-review profile. No broad tense guessing or background expansion.

Uses the preserved final v1 builders. The v2 experiment and its failed gates stay
unchanged. Warnings below are limited checks, not a factuality certification.
"""
import re
from types import SimpleNamespace
from final_writing_profiles import profile_messages as base_messages

PROFILE_NAME='application_service_20261119'


def kind_for(value):
    return {'report':'보고서','cover_letter':'자기소개서','speech':'발표문',
        'free_writing':'자유 글쓰기','자유글쓰기':'자유 글쓰기'}.get(value,value)


def safe_fact(text,kind):
    value=text.strip()
    # Only two irregular completed-action memos, with explicit object/recipient.
    m=re.search(r'(알림|고침|생각남)([.!?]?)$',value)
    if m:
        prefix=value[:m.start()]
        if m[1]=='생각남' or re.search(r'(?:에게|을|를)\s|다시\s',prefix):
            return prefix+{'알림':'알렸다','고침':'고쳤다','생각남':'생각났다'}[m[1]]+(m[2] or '.')
    # A storage action after an explicit action cue; never guess two-word nouns.
    if kind=='자유 글쓰기' and re.search(r'(?:그대로|넣어|않고)\s+보관함[.!?]?$',value):
        return re.sub(r'보관함[.!?]?$', '보관했다.',value)
    if kind=='발표문':
        # Clarify an object topic without inventing a person who prepared it.
        m=re.fullmatch(r'(.+?(?:바구니|봉투|자료집|안내문|상자|컵|카드))(?:은|는)\s*(\d+)\s*(개|부|장)\s*준비함[.!?]?',value)
        if m:
            noun=m[1];particle='을' if (ord(noun[-1])-0xAC00)%28 else '를'
            return f'{noun}{particle} {m[2]}{m[3]} 준비했다.'
        if re.search(r'가져와야\s*함[.!?]?$',value):return re.sub(r'가져와야\s*함[.!?]?$', '가져와야 한다.',value)
    return value


def profile_messages(req,*,bounds=None):
    kind=kind_for(req.document_type)
    values=vars(req).copy() if hasattr(req,'__dict__') else req.model_dump()
    values['facts']=[safe_fact(f,kind) for f in req.facts]
    actual,messages=base_messages(SimpleNamespace(**values),bounds=bounds)
    if kind=='자기소개서':
        messages[-1]['content']=messages[-1]['content'].replace(
            '제공된 맥락에서 내가 맡은 행동과 명시된 태도를 연결하고 모든 문장을 일인칭 존댓말로 통일한다.',
            '본인의 행동은 일인칭 존댓말로 쓴다. 다른 사람의 행동과 계획은 그 사람을 주어로 한 별도 존댓말 문장으로 쓴다.')
        messages[0]['content']+=' 동료나 담당자의 행동·계획을 본인의 일로 바꾸지 않는다. 다른 사람의 미래 계획에도 그 사람의 주어를 명시한다. 불참과 미확인 상태도 보존한다.'
    elif kind=='발표문':
        messages[0]['content']+=' 개수의 대상을 그대로 유지한다. 지참 의무는 보유 의무와 다르다. 받았다는 확인 답장 조건을 단순한 답장 조건으로 바꾸지 않는다. 선택권을 이미 선택한 사건으로 쓰지 않는다. 원문에 없는 발표 상황이나 청중의 계획을 덧붙이지 않는다.'
    return actual,messages


def source_checks(facts,text):
    checks=[]
    for fact in facts:
        m=re.match(r'^(.{1,24}?)(?:은|는|이|가)\s',fact.strip())
        if m:
            actor=m[1]
            if actor.endswith(('동료','직원','담당자','관리자','진행자','검토자','점검자','검수자','수령자','기록자')):
                if not re.search(re.escape(actor)+r'\s*(?:은|는|이|가|께서|였|입니다|이다|라고)',text):
                    checks.append('다른 사람의 행동·계획 주체 확인 필요: '+actor)
        m=re.fullmatch(r'(.+?(?:바구니|봉투|자료집|안내문|상자|컵|카드))(?:은|는)\s*(\d+)\s*(개|부|장)\s*준비함[.!?]?',fact.strip())
        if m and re.search(re.escape(m[1])+r'에(?:는)?\s*'+m[2],text):
            checks.append(f'준비 수량의 대상 확인 필요: {m[1]} {m[2]}{m[3]}')
    compact=re.sub(r'\s+','',text)
    if any('받았다는답' in re.sub(r'\s+','',f) for f in facts):
        if not any(x in compact for x in ('받았다는답','받았다고','수령확인','수령했다는','수령했다는회신')):
            checks.append('수령 확인 답장이라는 조건 보존 여부 확인 필요')
    if re.search(r'알림했|고침했|보관함으로\s*두',text):checks.append('메모 표현의 동사 활용 확인 필요')
    return list(dict.fromkeys(checks))
