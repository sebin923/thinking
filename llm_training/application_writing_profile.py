"""Source-only memo normalization and actor-safe application instructions.

No target answers or evaluation IDs are read. Frozen training/profile v1 stays
unchanged; this application profile requires its own fresh confirmation.
"""
import re
from types import SimpleNamespace
from final_writing_profiles import profile_messages as original_messages
from final_writing_profiles import f_prepared_input, AmbiguousWritingInput

PROFILE_NAME='application_v2_20261119'


def sentence_from_memo(text,kind):
    value=text.strip()
    if value.startswith(('작성 메모:','작성 참고:','작성 조건:','주의 사항:','가상 장면:')):
        return value
    match=re.search(r'([가-힣]+)([.!?]?)$',value)
    if not match:return value
    word=match[1];prefix=value[:match.start()];punct=match[2] or '.'
    if word.endswith(('다','니다','세요','어요','아요')):return value
    if word in ('보관함','정리함'):
        if re.fullmatch(r'[^\s]+(?:은|는)\s*'+word+r'[.!?]?',value):return value
        if not re.search(r'(?:을|를|에)\s|그대로\s|넣어\s|않고\s',prefix):return value
        return prefix+word[:-1]+'했다'+punct
    if word.endswith(('했음','였음','었음','았음')):return prefix+word[:-1]+'다'+punct
    if word=='함':
        if prefix.rstrip().endswith(('야','려','으려','려고')):return prefix.rstrip()+' 한다'+punct
        return prefix+'했다'+punct
    if word=='안됨' or (word=='됨' and prefix.rstrip().endswith('안')):
        return (prefix+'안 된다' if word=='안됨' else prefix+'된다')+punct
    for old,new in [('않음','않았다'),('못함','못했다')]:
        if word.endswith(old):return prefix+word[:-len(old)]+new+punct
    exact={'알림':'알렸다','고침':'고쳤다','생각남':'생각났다','들음':'들었다',
        '적음':'적었다','씀':'썼다','폄':'폈다','꺼냄':'꺼냈다','넣음':'넣었다','놓음':'놓았다',
        '둠':'두었다','봄':'보았다','받음':'받았다','보냄':'보냈다','전함':'전했다',
        '남김':'남겼다','띔':'띄었다','느껴짐':'느껴졌다','모름':'모른다',
        '않음':'않았다','못함':'못했다','안함':'하지 않았다','없음':'없다','있음':'있다',
        '여김':'여긴다','싶음':'싶다','됨':'되었다','끝냄':'끝냈다',
        '생각듦':'생각이 들었다','펼침':'펼쳤다','읽음':'읽었다','나눔':'나눴다'}
    if word in ('알림','고침') and not re.search(r'(?:에게|을|를)\s|다시\s',prefix):return value
    if word in exact:return prefix+exact[word]+punct
    for old,new in [('하려고함','하려고 한다'),('하려함','하려 한다'),('으려함','으려 한다'),
        ('려함','려 한다'),('야함','야 한다'),('수있음','수 있다'),('수없음','수 없다'),
        ('싶음','싶다'),('예정임','예정이다'),('계획임','계획이다'),('선택임','선택이다'),
        ('동료임','동료이다'),('중임','중이다'),('여김','여긴다'),('생각함','생각한다')]:
        if word.endswith(old):return prefix+word[:-len(old)]+new+punct
    # Closed verb list: 사물함/재료함 are nouns, not 사물했다/재료했다.
    verbs={'참여함','대조함','확인함','준비함','기록함','정리함','표시함','시험함','평가함','조사함',
        '부착함','연락함','집계함','분류함','작성함','수정함','완성함','선정함','담당함','선택함',
        '공개함','사용함','구분함','수령함','반납함','통보함','점검함','인쇄함','연습함','보류함',
        '재개함','시작함','중단함','배부함','전달함','설명함','추가함','검사함','완료함','제안함'}
    if word in verbs and prefix.strip():
        if word.endswith('제안함') and kind=='발표문':return prefix+word[:-1]+'한다'+punct
        return prefix+word[:-1]+'했다'+punct
    return value


def profile_messages(req,*,bounds=None):
    kind={'report':'보고서','cover_letter':'자기소개서','speech':'발표문',
        'free_writing':'자유 글쓰기','자유글쓰기':'자유 글쓰기'}.get(req.document_type,req.document_type)
    if kind=='자유 글쓰기':
        value=f_prepared_input({'facts':req.facts,'source_context':getattr(req,'source_context','')})
        if value['ambiguous']:raise AmbiguousWritingInput('메모의 뜻을 확인해 주세요: '+value['ambiguous'][0]+' — 보관한 행동인지 보관함이라는 물건인지 적어 주세요.')
    values=vars(req).copy() if hasattr(req,'__dict__') else req.model_dump()
    values['facts']=[sentence_from_memo(f,kind) for f in req.facts]
    normalized=SimpleNamespace(**values)
    actual,messages=original_messages(normalized,bounds=bounds)
    if kind=='자기소개서':
        old='제공된 맥락에서 내가 맡은 행동과 명시된 태도를 연결하고 모든 문장을 일인칭 존댓말로 통일한다.'
        new='본인의 행동은 일인칭 존댓말로 쓴다. 다른 사람의 행동과 계획은 그 사람을 주어로 한 별도 존댓말 문장으로 쓴다.'
        messages[-1]['content']=messages[-1]['content'].replace(old,new)
        messages[0]['content']+=' 자기소개서의 화자는 본인이지만 모든 행동의 주체가 본인인 것은 아니다. 동료·담당자·다른 직원의 행동과 미래 계획은 그 사람을 명시한다. 문장마다 누가 무엇을 하는지 유지한다. 다른 사람이 할 일을 내가 할 일로 바꾸지 않는다. 자료에 명시된 불참·미확인·미측정도 생략하지 않는다. 확인하는 행위와 대상의 상태를 주어가 다른 한 문장으로 합치지 않는다.'
    elif kind=='발표문':
        messages[0]['content']+=' 청중을 부르기 위해 원문에 없는 여러분을 행동 주체로 넣지 않는다. 개수의 대상과 준비·점검·배부의 주어를 유지한다. 가져오라는 지참 의무를 가지고 있으라는 보유 의무로 바꾸지 않는다. 조건의 수신자와 확인할 내용을 생략하지 않는다. 받았다는 답과 단순한 답장은 다르다. 수령 완료로 적을 조건만 있으면 현재 기록 상태를 추측하지 않는다. 필수와 선택, 현재 상태와 계획을 각각 보존한다.'
    if kind=='자유 글쓰기':
        value=f_prepared_input({'facts':values['facts'],'source_context':getattr(req,'source_context','')})
        facts=[sentence_from_memo(f,kind) for f in value['facts']]
        if value['background']:facts.insert(0,'장면 배경의 구체적 소재: '+' / '.join(value['background']))
        if value['fictional']:facts.insert(0,'가상으로 설정한 장면이다.')
        lo,hi=bounds if bounds is not None else [round(req.target_chars*.8),round(req.target_chars*1.2)]
        messages[-1]['content']='본문에 보존할 자료:\n'+'\n'.join('- '+f for f in facts)+f'\n공백 포함 {lo}~{hi}자. 자료의 장면·행동·생각을 모두 보존한다. 같은 사실은 한 번만 쓰고 새 행동·이유·감정을 붙이지 않는다. 본문 한 문단만 출력한다.'
        if value['fictional']:messages[-1]['content']+=' 가상 장면이면 상상 속 장면이라는 점을 짧게 자연스럽게 드러낸다. 배경의 구체적 소재도 보존한다.'
    return actual,messages
