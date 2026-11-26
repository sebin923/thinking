"""원문에서 근거 후보와 제한된 맞춤법 관찰을 구성한다. 점수를 자동 보정하지 않는다."""
from difflib import SequenceMatcher
import json
import re

_QUOTES=re.compile(r'```[\s\S]*?```|`[^`\n]*`|“[^”]*”|‘[^’]*’|"[^"\n]*"|\'[^\'\n]*\'')
_ACTOR=re.compile(r'저는|제가|나는|내가|본인[은이가의]?|동료[가는의]?|팀원[은이가의]?|담당자[가는의]?|선배[가는의]?|조원[은이가의]?')
_NUMBER=re.compile(r'\d[\d,]*(?:\.\d+)?(?:\s*(?:원|분|초|개|명|도|회|대|%))?')
_STATUS=re.compile(r'아직|미확인|미완료|예정|계획|승인|않[가-힣]*|못[가-힣]*|없[가-힣]*|완료[가-힣]*|마쳤[가-힣]*|끝냈[가-힣]*|적용했[가-힣]*|교체했[가-힣]*')
_SPELL=[
    ('past_done',re.compile('됬'),'됐','되었다의 준말은 됐다입니다.'),
    ('role_word',re.compile(r'(?<![가-힣])역활(?=$|[^가-힣]|[은는이가을를의도만과와에로])'),'역할','맡은 일의 표기는 역할입니다.'),
    ('days_word',re.compile(r'(?<![가-힣])몇일'),'며칠','날짜나 기간을 나타내는 표기는 며칠입니다.'),
    ('dependent_su',re.compile(r'(?<![가-힣])(할|볼|될|알|갈|올|쓸|살펴볼|확인할|정리할|먹을|읽을)수(?=\s*(?:있|없))'),None,'의존 명사 수는 앞말과 띄어 씁니다.'),
]

def sentences(text,prefix):
    result=[];cursor=0
    for boundary in list(re.finditer(r'(?<=[.!?。])\s+|\n+',text))+[None]:
        end=boundary.start() if boundary else len(text)
        raw=text[cursor:end];value=raw.strip()
        if value:
            offset=cursor+len(raw)-len(raw.lstrip())
            result.append({'id':f'{prefix}{len(result)+1}','text':value,'start':offset,'end':offset+len(value)})
        if boundary is None:break
        cursor=boundary.end()
    return result

def spelling_findings(text):
    quoted=[(m.start(),m.end()) for m in _QUOTES.finditer(text)]
    found=[]
    for kind,pattern,replacement,reason in _SPELL:
        for match in pattern.finditer(text):
            suggestion=replacement if replacement is not None else match.group(1)+' 수'
            found.append({'kind':kind,'original':match.group(0),'suggested':suggestion,'reason':reason,
                          'start':match.start(),'end':match.end(),
                          'quoted':any(start<=match.start() and match.end()<=end for start,end in quoted)})
    return sorted(found,key=lambda row:row['start'])

def _marks(text):
    return {'actors':list(dict.fromkeys(m.group(0) for m in _ACTOR.finditer(text))),
            'numbers':list(dict.fromkeys(m.group(0) for m in _NUMBER.finditer(text))),
            'status':list(dict.fromkeys(m.group(0) for m in _STATUS.finditer(text)))}

def evidence_context(material,text):
    source=sentences(material,'S');submission=sentences(text,'T');pairs=[]
    for fact in source:
        if not submission:break
        ranked=sorted(submission,key=lambda row:SequenceMatcher(None,fact['text'],row['text'],autojunk=False).ratio(),reverse=True)
        candidate=ranked[0]
        if SequenceMatcher(None,fact['text'],candidate['text'],autojunk=False).ratio()<0.2:continue
        pairs.append({'source_id':fact['id'],'submission_id':candidate['id'],
                      'source_marks':_marks(fact['text']),'submission_marks':_marks(candidate['text'])})
    return {'source':source,'submission':submission,'pairs':pairs,'spelling':spelling_findings(text)}

def render_evidence_user(material,text,criteria_text,task):
    evidence=evidence_context(material,text)
    source='\n'.join(f"{row['id']}: {row['text']}" for row in evidence['source']) or '(없음)'
    submission='\n'.join(f"{row['id']}: {row['text']}" for row in evidence['submission'])
    # Keep complete pairs only. The full original sentences above remain available.
    rendered=[];used=0
    for pair in evidence['pairs']:
        line=json.dumps(pair,ensure_ascii=False,separators=(',',':'))
        if used+len(line)>900:continue
        rendered.append(line);used+=len(line)
        if len(rendered)>=4:break
    spell=[]
    for finding in evidence['spelling'][:8]:
        usage='인용·코드 안: 표기 예시인지 확인하며 자동 감점하지 않음' if finding['quoted'] else '비인용 본문: 문맥 확인 후 검토'
        spell.append(f"‘{finding['original']}’ → ‘{finding['suggested']}’: {finding['reason']} ({usage})")
    return (f'[할 일]\n{task}\n\n[연습 자료의 실제 문장]\n{source}\n\n[채점 기준]\n{criteria_text}\n\n'
            f'[학습자가 쓴 실제 문장]\n{submission}\n\n[문자열 기반 대조 후보: 오류 판정이 아님]\n'+
            ('\n'.join(rendered) or '(문장 후보 없음)')+'\n\n[맞춤법 관찰: 문맥과 인용을 확인]\n'+
            ('\n'.join(spell) or '(이 제한된 규칙에서 발견한 사항 없음. 맞춤법이 완벽하다는 뜻은 아님)'))

def grounding_issues(normalized,submission,material):
    """Check copied evidence and objective spelling contradictions, not arbitrary score targets."""
    source=material+'\n'+submission
    findings=spelling_findings(submission)
    active=[f for f in findings if not f['quoted']]
    corrected=submission
    for item in reversed(active):corrected=corrected[:item['start']]+item['suggested']+corrected[item['end']:]
    issues=[]
    for item in normalized.get('criteria',[]):
        comment=item.get('comment')
        if not isinstance(comment,str):continue
        fragments=[m.group(0)[1:-1].strip() for m in _QUOTES.finditer(comment) if not m.group(0).startswith('`')]
        original_anchor=any(fragment in submission for fragment in fragments)
        correction=bool(re.search(r'고치|고쳐|수정|바꾸|띄어|쓰세|써\s*보|로\s*쓰',comment))
        for fragment in fragments:
            if fragment in source or fragment in corrected:continue
            if original_anchor and correction:continue  # A grounded proposed rewrite may be new wording.
            if len(fragment)<3:continue
            issues.append({'field':f"criteria.criterion_{item['index']}.comment",'kind':'quote_not_in_input'})
            break
    rows=normalized.get('criteria',[])
    if active and rows and rows[-1].get('score')==10:
        issues.append({'field':f"criteria.criterion_{rows[-1]['index']}.score",'kind':'perfect_grammar_with_unquoted_known_typo'})
    return issues
