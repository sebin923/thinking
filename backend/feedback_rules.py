"""원문에서 직접 확인할 수 있는 제한된 문법·상반 진술 검사.

관점·시점이 다른 문장을 임의로 모순이라고 판단하지 않는다. 문장 구조와
시제, 대상, 시점이 일치하는 명시적인 긍정/부정 진술만 비교한다.
"""
from decimal import Decimal
import re


_QUOTES = re.compile(r'```[\s\S]*?```|`[^`\n]*`|“[^”]*”|‘[^’]*’|"[^"\n]*"|\'[^\'\n]*\'')
_PARTICLE_END = re.compile(
    r'(?<![가-힣])(?P<word>[가-힣]+(?P<ending>습니다|입니다|합니다|했어요|해요|돼요|했다|렸다))'
    r'(?P<particle>를|을|가|이)(?=[.!?。]|$)'
)
_JOIN_PARTICLE = re.compile(
    r'(?<![가-힣])(?P<noun>[가-힣]*(?:동아리|동호회|학회|모임|단체|협회|조합|보험|서비스|사이트|멤버십|요금제))'
    r'(?P<particle>을|를)\s+(?:(?:새로|이미|아직|직접|먼저)\s+)?'
    r'가입(?:하였습니다|하였다|했습니다|했다|합니다|한다|해요|했어요|하겠다|하겠습니다|'
    r'하지\s*않(?:았습니다|았다|습니다|는다)|할\s*(?:계획|예정)(?:입니다|이다)|할(?:게|께)(?:요)?)'
    r'(?=[.!?。]|$)'
)
_CONNECTOR = re.compile(r'^(?:(?:그러나|하지만|그런데|반면|또한|그리고)\s*[,，]?\s*)+')
_UNASSERTED = re.compile(
    r'예정|계획|가능|추정|아마|가정|예시|예를\s*들|듯|것\s*같|수(?:도)?\s*있|'
    r'다고|라고|라며|다며|라면|다면|으면|경우|정정|바로잡|사실은|실제로는|앞서.*잘못'
)
_NEGATIVE = re.compile(r'(?<![가-힣])(?P<stem>[가-힣]+)지\s*않(?P<end>았습니다|았다|았어요|습니다|는다|아요|다)$')
_EXACT_NUMBER = re.compile(
    r'^(?P<subject>.+?)(?:은|는|이|가)\s*(?:(?:정확히|총)\s*)?'
    r'(?P<number>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*'
    r'(?P<unit>명|개|대|장|건|칸|원|시간|분|초|%)'
    r'(?P<ending>입니다|이다|이었습니다|이었다|였습니다|였다)$'
)
_TIME = re.compile(
    r'(?<![가-힣])(?P<time>올해|작년|내년|오늘|어제|내일|이번\s*달|지난\s*달|다음\s*달|'
    r'\d{4}년|\d{1,2}월|\d{1,2}일)(?:의|은|는)?(?=\s|$)'
)
_PAST_FORMS = (
    ('하였습니다', '하'), ('했습니다', '하'), ('하였다', '하'), ('했다', '하'),
    ('되었습니다', '되'), ('됐습니다', '되'), ('되었다', '되'), ('됐다', '되'),
    ('렸습니다', '리'), ('렸어요', '리'), ('렸다', '리'),
    ('갔습니다', '가'), ('갔어요', '가'), ('갔다', '가'),
    ('왔습니다', '오'), ('왔어요', '오'), ('왔다', '오'),
    ('봤습니다', '보'), ('봤어요', '보'), ('봤다', '보'),
    ('줬습니다', '주'), ('줬어요', '주'), ('줬다', '주'),
    ('썼습니다', '쓰'), ('썼어요', '쓰'), ('썼다', '쓰'),
    ('았습니다', ''), ('었습니다', ''), ('았어요', ''), ('었어요', ''), ('았다', ''), ('었다', ''),
)


def _overlaps_quote(start, end, quotes):
    return any(start < stop and end > begin for begin, stop in quotes)


def grammar_items(content, rows, preferences):
    quoted = [(match.start(), match.end()) for match in _QUOTES.finditer(content)]
    guided = (preferences or {}).get('ai_assistance') == 'guided'
    result = []
    for row in rows:
        if re.search(r'예시|예문|잘못된\s*(?:문장|표현)|틀린\s*(?:문장|표현)', row['text']):
            continue
        for match in _PARTICLE_END.finditer(row['text']):
            if _overlaps_quote(row['start'] + match.start(), row['start'] + match.end(), quoted):
                continue
            fixed = match['word']
            result.append({'target_id': row['id'], 'original_text': match[0], 'type': '문법',
                'reason': f'문장을 끝내는 ‘{match["ending"]}’ 뒤에 조사가 덧붙어 문장 끝이 어색해요.',
                'suggestion': f'‘{fixed}’처럼 끝에 붙은 조사를 빼 주세요.',
                'revised_text': '' if guided else fixed})
        # 국립국어원 한국어기초사전 '가입하다'(15392): 1이 2에 가입하다.
        # 명사+조사만 표시해 같은 문장 안의 오탈자 수정과 겹치지 않는다.
        for match in _JOIN_PARTICLE.finditer(row['text']):
            if _overlaps_quote(row['start'] + match.start(), row['start'] + match.end(), quoted):
                continue
            original = match['noun'] + match['particle']
            fixed = match['noun'] + '에'
            result.append({'target_id': row['id'], 'original_text': original, 'type': '문법',
                'reason': '가입하는 단체나 상품을 나타낼 때는 조사 ‘에’를 사용해요.',
                'suggestion': f'‘{fixed}’처럼 가입 대상을 나타내는 조사를 고쳐 주세요.',
                'revised_text': '' if guided else fixed})
    return result


def _without_final(char, final):
    code = ord(char) - 0xAC00
    if 0 <= code < 11172 and code % 28 == final:
        return chr(ord(char) - final)
    return None


def _finite_verb(word):
    for suffix, replacement in _PAST_FORMS:
        if word.endswith(suffix):
            stem = word[:-len(suffix)] + replacement
            return (stem, 'past') if stem else None
    for suffix in ('습니다', '어요', '아요', '는다'):
        if word.endswith(suffix) and len(word) > len(suffix):
            return word[:-len(suffix)], 'present'
    if word.endswith('니다') and len(word) > 2:
        stem = word[:-2]
        vowel_stem = _without_final(stem[-1], 17)  # 하 + ㅂ니다 -> 합니다
        if vowel_stem:
            return stem[:-1] + vowel_stem, 'present'
    if word.endswith('다') and len(word) > 1:
        stem = word[:-1]
        past = _without_final(stem[-1], 20)  # 나 + 았다 -> 났다
        if past:
            return stem[:-1] + past, 'past'
        present = _without_final(stem[-1], 4)  # 가 + ㄴ다 -> 간다
        return (stem[:-1] + present if present else stem), 'present'
    return None


def _claim(row):
    text = row['text'].strip()
    if text.endswith(('?', '？')) or _QUOTES.search(text) or _UNASSERTED.search(text):
        return None
    body = _CONNECTOR.sub('', text.rstrip('.!。').strip())
    negative = _NEGATIVE.search(body)
    if negative:
        prefix = body[:negative.start()].strip()
        stem = negative['stem']
        tense = 'past' if negative['end'].startswith('았') else 'present'
        polarity = False
    else:
        match = re.search(r'(?<![가-힣])([가-힣]+)$', body)
        if not match:
            return None
        verb = _finite_verb(match[1])
        if not verb:
            return None
        prefix, (stem, tense), polarity = body[:match.start()].strip(), verb, True
        if re.search(r'(?:^|\s)안$', prefix):
            prefix = re.sub(r'(?:^|\s)안$', '', prefix).strip()
            polarity = False
    # Require an explicit subject/topic, retaining dates and object particles.
    if not re.search(r'[가-힣]+(?:는|은|이|가)(?:\s|$)', prefix):
        return None
    prefix = re.sub(r'(?<![가-힣])(?:이번|해당|같은)\s+', '', prefix)
    prefix = re.sub(r'(?<![가-힣])(?:저는|제가|나는|내가)(?=\s|$)', '나', prefix)
    prefix = re.sub(r'(?<![가-힣])([가-힣]+?)(?:는|은|이|가)(?=\s|$)', r'\1', prefix)
    return {'key': (re.sub(r'\s+', '', prefix), stem, tense), 'polarity': polarity, 'row': row}


def contradiction_items(rows):
    result, previous = [], []
    for index, row in enumerate(rows):
        claim = _claim(row)
        if claim:
            conflict = next((old for pos, old in reversed(previous) if index - pos <= 3
                             and old['key'] == claim['key'] and old['polarity'] != claim['polarity']), None)
            if conflict:
                before = conflict['row']['text']
                result.append({'target_id': row['id'], 'original_text': row['text'], 'type': '논리',
                    'reason': f'앞에서는 “{before}”라고 했는데, 여기서는 반대 상태를 적었어요. 같은 대상과 시점을 말한 것인지 확인이 필요해요.',
                    'suggestion': '어느 내용이 실제 사실인지 확인한 뒤 두 문장의 설명을 맞춰 주세요. 시점이나 대상이 달라진 경우에는 그 차이를 밝혀 주세요.',
                    'revised_text': ''})
            previous.append((index, claim))
    return result


def numeric_contradiction_items(rows):
    """같은 대상·시점·단위의 확정 수량만 비교한다. 범위·추정은 판정하지 않는다."""
    result, previous = [], []
    for index, row in enumerate(rows):
        text = row['text'].strip()
        if text.endswith(('?', '？')) or _QUOTES.search(text) or _UNASSERTED.search(text):
            continue
        body = _CONNECTOR.sub('', text.rstrip('.!。').strip())
        match = _EXACT_NUMBER.fullmatch(body)
        if not match:
            continue
        subject = match['subject'].strip()
        times = tuple(sorted(re.sub(r'\s+', '', item['time']) for item in _TIME.finditer(subject)))
        subject = _TIME.sub('', subject)
        subject = re.sub(r'(?<![가-힣])(?:이번|해당|같은)\s+', '', subject)
        subject = re.sub(r'(?<=[가-힣])의(?=\s|$)', '', subject)
        subject = re.sub(r'\s+', '', subject)
        if not subject or len(subject) < 2:
            continue
        tense = 'present' if match['ending'] in ('입니다', '이다') else 'past'
        key = (subject, times, match['unit'], tense)
        number = Decimal(match['number'].replace(',', ''))
        conflict = next((old for old in reversed(previous) if index - old['index'] <= 4
                         and old['key'] == key and old['number'] != number), None)
        if conflict:
            result.append({'target_id': row['id'], 'original_text': row['text'], 'type': '논리',
                'reason': f'앞에서는 “{conflict["text"]}”라고 했는데, 같은 대상과 시점으로 보이는 수량을 여기서는 다르게 적었어요.',
                'suggestion': '기준이 되는 수치를 다시 확인해 두 문장의 설명을 맞춰 주세요. 집계 시점이나 대상 범위가 다르다면 그 차이를 함께 밝혀 주세요.',
                'revised_text': ''})
        previous.append({'key': key, 'number': number, 'index': index, 'text': row['text']})
    return result
