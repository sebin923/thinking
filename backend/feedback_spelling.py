"""피드백 전용 표기 검사. 채점용 표기 관찰 규칙은 변경하지 않는다.

표기 근거: 국립국어원 상담 사례(314870, 6761, 6103) 및
https://www.korean.go.kr/nkview/nknews/200211/52_3.html
"""
import re

from score_evidence import spelling_findings as basic_spelling_findings


_QUOTES = re.compile(r'```[\s\S]*?```|`[^`\n]*`|“[^”]*”|‘[^’]*’|"[^"\n]*"|\'[^\'\n]*\'')
# 명사 뒤의 높임 조사 '께'(아들께/선생님께 등)를 고치지 않도록
# 모든 ㄹ 받침 단어를 일괄 치환하지 않고 용언의 일부 활용형만 찾는다.
_PROMISE = re.compile(
    r'(?<![가-힣])(?P<verb>[가-힣]*(?:드릴|읽을|먹을|받을|찾을|만들|기다릴|알릴|놓을|할|될|갈|올|볼|줄|쓸|낼|뵐|쉴))'
    r'께(?P<polite>요)?(?=$|[^가-힣])'
)
_EXTRA = (
    ('promise_ending', _PROMISE, lambda m: m['verb'] + '게' + (m['polite'] or ''),
     '앞으로 할 일을 약속하는 어미는 된소리로 적지 않고 ‘-ㄹ게’ 또는 ‘-을게’로 적어요.'),
    ('doeyo', re.compile(r'되요(?=$|[^가-힣])'), lambda m: '돼요',
     '‘되어요’를 줄인 바른 표기는 ‘돼요’예요.'),
    ('bweyo', re.compile(r'뵈요(?=$|[^가-힣])'), lambda m: '봬요',
     '‘뵈어요’를 줄인 바른 표기는 ‘봬요’예요.'),
    ('waenji', re.compile(r'(?<![가-힣])웬지(?=$|[^가-힣])'), lambda m: '왠지',
     '이유를 알 수 없다는 뜻의 ‘왜인지’가 줄어든 말은 ‘왠지’로 적어요.'),
    ('oraenman', re.compile(r'(?<![가-힣])오랫만(?=$|[^가-힣]|[은는이가을를의도만과와에])'), lambda m: '오랜만',
     '‘오래간만’의 준말은 ‘오랜만’으로 적어요.'),
)


def spelling_findings(text):
    findings = list(basic_spelling_findings(text))
    quotes = [(match.start(), match.end()) for match in _QUOTES.finditer(text)]
    for kind, pattern, replacement, reason in _EXTRA:
        for match in pattern.finditer(text):
            findings.append({'kind': kind, 'original': match[0], 'suggested': replacement(match), 'reason': reason,
                             'start': match.start(), 'end': match.end(),
                             'quoted': any(start <= match.start() and match.end() <= end for start, end in quotes)})
    return sorted(findings, key=lambda item: (item['start'], item['end']))
