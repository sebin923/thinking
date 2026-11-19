"""Frozen report/free-writing profiles for final training and serving.

Vendored pure builders; no experiment files, network calls, or model loads.
"""

import re

from writing_prompts import build_messages

PROFILE_NAME = "final_20261119"

PROMPT_TOKEN_BUDGET = 1536

r_SYSTEM = ('한국어 보고서를 다듬는 편집자다. 원문 자료의 모든 사실을 객관적인 완성 문장으로 쓴다. 문장마다 주어와 서술어가 직접 맞도록 한다. 사람이 한 점검·기록·전달의 주어는 그 사람이다. 물건이나 문서의 '
 '누락·상태를 서술할 때는 그 물건이나 문서를 주어로 삼는다. 행동을 길게 관형어로 붙이지 말고, 사람이 확인했다는 문장 뒤에 항목의 상태를 별도 문장으로 쓴다. 주어가 다른 사실을 무리하게 한 '
 '문장으로 합치지 않는다. 같은 주어의 관련 행동은 자연스럽게 연결할 수 있다. 행동한 사람·수치·단위·시각·날짜·인용문·조건·부정을 그대로 보존한다. 이미 한 일, 아직 하지 않은 일, 할 계획, '
 '제안만 한 일을 구별한다. 다른 사람의 일을 점검자의 일로 바꾸지 않는다. 전달과 수신, 확인과 수정, 준비와 실제 배부, 누락과 부재를 구분한다. 효과를 조사하지 않았다는 말은 효과가 없다는 뜻이 '
 '아니다. 모르는 결과를 추측하지 않는다. 새 원인·배경·성과·판단을 보태지 않는다. 같은 사실은 한 번만 전한다. 했다·였다·이다·없다 등의 보고서 문체를 유지하고 함·음·봄의 메모체를 남기지 '
 '않는다. 작성 참고는 본문에서 제외하되 실제로 하지 않은 행동과 미확인 상태는 유지한다. 제목·목록·설명 없이 본문 한 문단만 출력한다. 예시의 물건과 수치를 이번 자료에 섞지 않는다.')

r_EXAMPLES = [({'facts': ['점검자는 대여용 손전등 12개의 이름표를 원본 목록과 대조함',
             '2개 이름표에는 반납 칸 번호가 없었음',
             '점검자는 빠진 두 이름표의 손전등 번호를 기록함',
             '관리자에게 번호를 보완하자고 제안했지만 아직 이름표를 수정하지 않음',
             '밝기와 사용 시간은 시험하지 않음'],
   'bounds': [120, 180]},
  '점검자는 대여용 손전등 12개의 이름표를 원본 목록과 대조했다. 이름표 2개에는 반납 칸 번호가 없었다. 점검자는 해당 손전등의 번호를 기록하고 관리자에게 보완을 제안했다. 아직 이름표를 수정하지는 '
  '않았으며, 손전등의 밝기와 사용 시간도 시험하지 않았다.'),
 ({'facts': ['검토자는 행사 안내문 14장의 시간표를 확인함',
             '3장에 시작 시각이 빠져 있었음',
             '원본 시간표를 찾아본 사람은 동료였음',
             '검토자는 빠진 세 안내문의 번호를 적음',
             '검토자는 안내문을 담당자에게 전달할 계획이지만 아직 전달하지 않음',
             '실제 참석자의 불편은 조사하지 않음'],
   'bounds': [120, 180]},
  '검토자는 행사 안내문 14장의 시간표를 확인했다. 그중 3장에는 시작 시각이 빠져 있었다. 원본 시간표를 찾아본 사람은 동료였다. 검토자는 해당 안내문의 번호를 적었다. 담당자에게 전달할 계획이지만 '
  '아직 전달하지 않았고, 실제 참석자의 불편도 조사하지 않았다.'),
 ({'facts': ['기록 담당자는 재료 상자 10개의 표지를 목록과 대조함',
             '2개의 표지에 재료 이름이 잘못 적혀 있었음',
             '기록 담당자가 두 표지의 이름을 수정함',
             '다른 검수자는 수정된 두 이름을 원본 목록과 다시 대조함',
             '수정된 두 이름이 원본과 같았음',
             '재료의 강도와 수업 효과는 평가하지 않음'],
   'bounds': [120, 180]},
  '기록 담당자는 재료 상자 10개의 표지를 목록과 대조했다. 표지 2개에는 재료 이름이 잘못 적혀 있어 담당자가 수정했다. 다른 검수자는 수정된 두 이름을 원본 목록과 다시 대조했고, 두 이름은 모두 '
  '원본과 같았다. 재료의 강도와 수업 효과는 평가하지 않았다.')]

r_ANONYMOUS_RULE = (' 원문에 행동 주체가 명시된 경우에는 그 주체를 반드시 유지한다. 원문에 주체가 없는 행동은 누가 했는지 추정하지 않는다. 기록 담당자가 번호를 적었다고 해서 물품을 받은 사람이나 수정한 사람도 기록 '
 '담당자라고 쓰지 않는다. 주체 없는 수령·반납은 주어를 보충하지 않은 문장으로 쓸 수 있다. 자연스러운 문장을 만들기 위해 원문에 없는 담당자·장소·시간을 넣지 않는다.')

r_ANONYMOUS_EXAMPLE = ({'facts': ['빌려준 안전모 24개 중 첫날에 15개를 돌려받음',
            '나머지 9개는 다음 날 돌려받음',
            '기록 담당자는 반납 날짜별로 안전모 번호를 나누어 적음',
            '최종 기록에서 24개의 번호를 모두 확인함',
            '안전모의 위생 상태는 조사하지 않음'],
  'bounds': [120, 180]},
 '빌려준 안전모 24개 중 첫날에 15개를 돌려받았고, 나머지 9개는 다음 날 돌려받았다. 기록 담당자는 반납 날짜별로 안전모 번호를 나누어 적었다. 최종 기록에서는 24개의 번호를 모두 확인했다. '
 '안전모의 위생 상태는 조사하지 않았다.')

def r_repair_messages(case):

    def user(c):
        lo, hi = c['bounds']
        return '보고서에 보존할 원문 자료:\n' + '\n'.join(('- ' + f for f in c['facts'])) + f'\n공백 포함 {lo}~{hi}자. 사람의 행동과 대상의 상태를 구분해 주어·서술어가 맞는 완성 문장으로 쓴다. 원문의 모든 사실을 보존하고 본문 한 문단만 출력한다.'
    messages = [{'role': 'system', 'content': r_SYSTEM}]
    for source, answer in r_EXAMPLES:
        assert source['bounds'][0] <= len(answer) <= source['bounds'][1], len(answer)
        messages.extend([{'role': 'user', 'content': user(source)}, {'role': 'assistant', 'content': answer}])
    messages.append({'role': 'user', 'content': user(case)})
    return messages

def r_repair_messages_v2(case):
    messages = r_repair_messages(case)
    messages[0]['content'] += r_ANONYMOUS_RULE
    source, answer = r_ANONYMOUS_EXAMPLE
    assert source['bounds'][0] <= len(answer) <= source['bounds'][1]
    messages[-1:-1] = [{'role': 'user', 'content': r_repair_messages(source)[-1]['content']}, {'role': 'assistant', 'content': answer}]
    return messages

def r_repair_messages_v3(case):
    messages = r_repair_messages_v2(case)
    messages[0]['content'] = messages[0]['content'].replace('같은 주어의 관련 행동은 자연스럽게 연결할 수 있다.', '서로 다른 자료 항목을 한 문장으로 합치지 않는다. 항목 순서를 유지하고 항목마다 완성 문장을 쓴다. 한 항목 안에 서로 다른 주체가 있으면 문장을 나눌 수 있다.')
    messages[0]['content'] += ' 누락은 무엇이 빠졌는지 정보의 이름까지 반드시 쓴다. 특정 칸이 빈 문서를 문서 전체가 빈 것으로 줄이지 않는다. 원문에 찾는 사람과 기록하는 사람이 따로 있으면 두 사람의 행동을 각각 다른 문장으로 유지한다.'
    answers = ['점검자는 대여용 손전등 12개의 이름표를 원본 목록과 대조했다. 2개 이름표에는 반납 칸 번호가 없었다. 점검자는 빠진 두 이름표의 손전등 번호를 기록했다. 관리자에게 번호 보완을 제안했지만 아직 이름표를 수정하지 않았다. 밝기와 사용 시간은 시험하지 않았다.', '검토자는 행사 안내문 14장의 시간표를 확인했다. 3장에는 시작 시각이 빠져 있었다. 원본 시간표를 찾아본 사람은 동료였다. 검토자는 빠진 세 안내문의 번호를 적었다. 담당자에게 전달할 계획이지만 아직 전달하지 않았다. 실제 참석자의 불편은 조사하지 않았다.', '기록 담당자는 재료 상자 10개의 표지를 목록과 대조했다. 2개의 표지에는 재료 이름이 잘못 적혀 있었다. 기록 담당자가 두 표지의 이름을 수정했다. 다른 검수자는 수정된 두 이름을 원본 목록과 다시 대조했다. 두 이름은 원본과 같았다. 재료 강도와 수업 효과는 평가하지 않았다.', '빌려준 안전모 24개 중 첫날에 15개를 돌려받았다. 나머지 9개는 다음 날 돌려받았다. 기록 담당자는 반납 날짜별로 안전모 번호를 나누어 적었다. 최종 기록에서 24개의 번호를 모두 확인했다. 안전모의 위생 상태는 조사하지 않았다.']
    for i, answer in enumerate(answers):
        assert 120 <= len(answer) <= 180, len(answer)
        messages[2 + 2 * i]['content'] = answer
    return messages

def r_repair_messages_v4(case):
    messages = r_repair_messages_v3(case)
    fields = r_missing_field_names(case['facts'])
    if fields:
        messages[-1]['content'] += '\n원문에서 빠졌다고 한 정보·대상 이름(본문에서 생략하지 않기): ' + ', '.join(fields)
    return messages

def r_missing_field_names(facts):
    """Extract literal noun phrases only; never infer a field from the topic."""
    result = []
    for original in facts:
        fact = re.sub('“[^”]*”|‘[^’]*’|"[^"]*"|\\\'[^\\\']*\\\'', lambda m: ' ' * len(m[0]), original)
        if not re.search('빈|비어|없|빠져', fact):
            continue
        m = re.search('(?:에는?|에서)\\s+([가-힣· ]{1,24}?)(?:\\s*칸)?(?:이|가)\\s*(?:빈|비어|없|빠져)', fact)
        if not m:
            m = re.match('([가-힣· ]{1,24}?)(?:\\s*칸)?(?:이|가)\\s*(?:빈|비어|없|빠져)', fact)
        if m:
            name = m[1].strip()
            if name not in result:
                result.append(name)
    return result

f_SYSTEM = ('한국어 자유 글쓰기 본문을 쓰는 편집자다. 자료에 있는 관찰·행동·명시된 생각만 쓴다. 사람·수치·순서·부정과 이미 한 일/하려는 일/아직 안 한 일을 그대로 보존한다. 장면의 행동을 빠뜨리지 '
 '않는다. 없는 감각·감정·이유·결심·교훈을 보태지 않는다. 제목은 글의 이름이다. 제목을 살펴보거나 경험했다는 사건을 만들지 않는다. 화자의 생각이 명사구여도 사람을 마음이라고 서술하지 않는다. '
 '구분하는 마음은 구분해 생각했다처럼, 대하는 마음은 그 대상을 대하는 마음을 생각했다처럼 풀어 쓴다. 자료에 없는 정리하고 싶다·다짐했다 같은 마무리를 붙이지 않는다. 이미 보낸 메시지는 전했다로 '
 '쓰고 전하고 싶었다로 바꾸지 않는다. 하지 못했다를 일부러 하지 않았다로 바꾸거나 그 이유를 만들지 않는다. 주제·배경 명사구에 조사를 기계적으로 붙이지 말고 물건을 장소로 쓰지 않는다. 함·음·봄 '
 '같은 메모 종결과 합니다·했어요를 본문에 남기지 않는다. 했다·였다·한다·이다의 담백한 문체를 끝까지 쓴다. 같은 생각은 한 번만 전한다. 작성 참고와 예시의 물건·상황을 본문에 섞지 않는다. 주어진 '
 '사실을 연결해 한 문단만 출력한다. 제목·항목명·작업 설명은 쓰지 않는다. 모호한 말 때문에 사실을 확정할 수 없으면 억지로 쓰지 말고 그 뜻만 짧게 질문한다.')

f_EXAMPLES = [({'topic': '접은 종이 모형',
   'facts': ['종이 모형의 날개를 접음', '다리는 아직 붙이지 않음', '화자의 생각: 끝낸 부분과 남은 부분을 구분하는 마음', '당시 마음: 잠깐 손을 멈추고 싶었음'],
   'context': '',
   'bounds': [70, 150]},
  '종이 모형의 날개를 접었다. 다리는 아직 붙이지 않았다. 끝낸 부분과 남은 부분을 구분해 생각하며 잠깐 손을 멈추고 싶었다.'),
 ({'topic': '창고 점검 결과',
   'facts': ['현장에서는 관리자에게 결과를 말하지 못함',
             '집에 와서 실제 결과를 관리자에게 문자로 보냄',
             '관리자의 답은 아직 없음',
             '정리할 날짜는 아직 정하지 않음',
             '작성 메모: 연락처는 제공하지 않았음. 본문에 넣지 않기.'],
   'context': '',
   'bounds': [60, 140]},
  '현장에서는 점검 결과를 말하지 못했지만 집에 와서 관리자에게 문자로 전했다. 답변은 아직 받지 못했다. 정리할 날짜는 정하지 않았다.'),
 ({'topic': '천천히 고르는 기준',
   'facts': ['책갈피 두 개를 공책 옆에 놓음',
             '한 개만 공책에 끼움',
             '다른 하나는 접지 않고 그대로 둠',
             '다음에 쓸 색은 정하지 않음',
             '화자의 생각: 새로운 모양을 대하는 마음'],
   'context': '가상으로 설정한 장면',
   'bounds': [80, 160]},
  '가상의 장면에서 책갈피 두 개를 공책 옆에 놓았다. 한 개만 공책에 끼우고 다른 하나는 접지 않은 채 두었다. 새로운 모양을 대하는 내 마음을 생각했다. 다음에 쓸 색은 정하지 않았다.')]

def f_prepared_input(case):
    facts = []
    notes = []
    background = []
    seen = set()
    ambiguous = []
    fictional = '가상' in case.get('source_context', '')
    for source in case['facts']:
        text = source.strip()
        if text.startswith(('작성 메모:', '작성 참고:')):
            continue
        if text.startswith(('작성 조건:', '주의 사항:')):
            notes.append(text.split(':', 1)[1].strip())
            continue
        if text.rstrip('. ') in ['가상 경험', '가상 장면', '가상 연습 사례']:
            fictional = True
            continue
        if text.startswith('가상 장면:'):
            fictional = True
            background.append(text.split(':', 1)[1].strip())
            continue
        thought = text.startswith(('화자의 생각:', '생각:'))
        if text.startswith(('관찰한 장면:', '화자의 생각:', '생각:', '화자의 당시 마음:', '당시 마음:', '정리하고 싶은 생각:')):
            text = text.split(':', 1)[1].strip()
        if thought:
            value = text.rstrip('. ')
            m = re.fullmatch('(.+?)(을|를) 구분하는 마음', value)
            n = re.fullmatch('(.+?)(을|를) 대하는 마음', value)
            if m:
                text = m[1] + m[2] + ' 구분해 생각했다.'
            elif n:
                text = n[1] + n[2] + ' 대하는 내 마음을 생각했다.'
            elif value.endswith('마음'):
                text = value + '에 관해 생각했다.'
        if re.fullmatch('[^\\s]+(?:은|는)\\s*(?:보관함|정리함)[.!?]?', text):
            ambiguous.append(source)
        match = re.search('([가-힣]+)음([.!?]?)$', text)
        if match and len(match[1]) > 1 and ((ord(match[1][-1]) - 44032) % 28 == 20):
            text = text[:match.start()] + match[1] + '다' + (match[2] or '.')
        if text not in seen:
            facts.append(text)
            seen.add(text)
    return {'facts': facts, 'notes': notes, 'background': background, 'fictional': fictional, 'ambiguous': ambiguous}

def f_narrative_fact(text):
    """Finite, source-only narrative memo expansion; no target answer is used."""
    m = re.search('([가-힣]+)([.!?]?)$', text)
    if not m:
        return text
    word = m[1]
    prefix = text[:m.start()]
    punct = m[2] or '.'
    if word.endswith(('다', '니다', '세요', '어요', '아요')):
        return text
    exact = {'봄': '보았다', '함': '했다', '않음': '않았다', '있음': '있었다', '없음': '없다', '모름': '모른다', '느낌': '느꼈다', '여김': '여겼다', '싶음': '싶다', '둠': '두었다', '넣음': '넣었다', '펼침': '펼쳤다', '읽음': '읽었다', '받음': '받았다', '전함': '전했다', '적음': '적었다', '나눔': '나눴다'}
    if word in exact:
        if word == '없음' and (not re.search('알 수|아직|답|응답|기록|확인', prefix)):
            return text
        return prefix + exact[word] + punct
    if word == '못함':
        return prefix + ('못한다' if re.search('알지\\s*$', prefix) else '못했다') + punct
    if word.endswith('안옴'):
        return prefix + word[:-2] + '오지 않았다' + punct
    if word.endswith('안함'):
        base = word[:-2]
        return prefix + base + '하지 않았다' + punct if base else text
    if word.endswith('함'):
        if word in ['보관함', '정리함'] and (not re.search('(?:을|를|에)\\s', prefix)):
            return text
        return prefix + word[:-1] + '했다' + punct
    return text

def f_narrative_fact_v3(text):
    first = f_narrative_fact(text)
    if first != text:
        return first
    m = re.search('([가-힣]+)([.!?]?)$', text)
    if not m:
        return text
    word = m[1]
    prefix = text[:m.start()]
    punct = m[2] or '.'
    endings = [('느껴짐', '느껴졌다'), ('띔', '띄었다'), ('남김', '남겼다'), ('끼움', '끼웠다'), ('꺼냄', '꺼냈다'), ('놓음', '놓았다'), ('씀', '썼다'), ('폄', '폈다'), ('나옴', '나왔다'), ('받음', '받았다'), ('줌', '주었다'), ('있음', '있었다'), ('싶음', '싶다'), ('모름', '모른다')]
    for ending, replacement in endings:
        if word.endswith(ending):
            return prefix + word[:-len(ending)] + replacement + punct
    return text

def f_source_user_v3(case):
    value = f_prepared_input(case)
    facts = [f_narrative_fact_v3(f) for f in value['facts']]
    if not facts:
        raise ValueError('본문에 쓸 사실이나 생각이 필요합니다.')
    for background in value['background']:
        setting = re.match('(.+?(?:수족관|시장|도서관|정류장|공원|교실|공방|작업실|골목|역))(?:의\\s|\\s|$)', background)
        if setting and setting[1] not in facts[0]:
            facts[0] = setting[1] + '에서 ' + facts[0]
    if value['fictional']:
        facts.insert(0, '가상으로 설정한 장면이다.')
    lo, hi = case['bounds']
    return ('본문에 보존할 자료:\n' + '\n'.join(('- ' + f for f in facts)) + f'\n공백 포함 {lo}~{hi}자. 자료의 장면·행동·생각을 모두 보존한다. 같은 사실은 한 번만 쓰고 새 행동·이유·감정을 붙이지 않는다. 본문 한 문단만 출력한다.', value)

def f_repair_messages_v3(case):
    user, value = f_source_user_v3(case)
    system = f_SYSTEM + ' 자료의 핵심 장면뿐 아니라 명시된 비유와 생각도 빠뜨리지 않는다. 자료에 가상이라고 있으면 가상 장면임을 유지한다.'
    if value['notes']:
        system += ' 이번 요청의 추가 규칙: ' + ' '.join(value['notes'])
    messages = [{'role': 'system', 'content': system}]
    for source, answer in f_EXAMPLES:
        demo = {**source, 'source_context': source['context']}
        demo_user, _ = f_source_user_v3(demo)
        messages.extend([{'role': 'user', 'content': demo_user}, {'role': 'assistant', 'content': answer}])
    messages.append({'role': 'user', 'content': user})
    return messages


class AmbiguousWritingInput(ValueError):
    pass


def profile_messages(req, *, bounds=None):
    kind = {'report':'보고서','free_writing':'자유 글쓰기','자유글쓰기':'자유 글쓰기',
            'speech':'발표문','cover_letter':'자기소개서'}.get(req.document_type, req.document_type)
    case = {'facts':list(req.facts), 'topic':req.topic,
            'bounds':list(bounds) if bounds is not None else [round(req.target_chars*.8),round(req.target_chars*1.2)],
            'source_context':getattr(req,'source_context','')}
    if kind == '보고서':
        messages = r_repair_messages_v4(case)
    elif kind == '자유 글쓰기':
        value = f_prepared_input(case)
        if value['ambiguous']:
            raise AmbiguousWritingInput('메모의 뜻을 확인해 주세요: '+value['ambiguous'][0]+' — 물건을 보관했다는 뜻인지 보관함이라는 물건을 말하는지 적어 주세요.')
        messages = f_repair_messages_v3(case)
    else:
        kind,messages = build_messages(req)
        if bounds is not None:
            messages[-1]['content']=re.sub(r'공백 포함 \d+~\d+자', f'공백 포함 {bounds[0]}~{bounds[1]}자', messages[-1]['content'])
    return kind,messages


def fit_messages(messages, processor, max_tokens=PROMPT_TOKEN_BUDGET):
    values=[dict(x) for x in messages]
    removed=0
    def count():
        text=processor.apply_chat_template(values,tokenize=False,add_generation_prompt=True,enable_thinking=False)
        return len(processor.tokenizer(text,add_special_tokens=False)['input_ids'])
    while count()>max_tokens and len(values)>2:
        # Remove only a complete demonstration. Never remove user facts.
        del values[-3:-1]
        removed+=1
    tokens=count()
    if tokens>max_tokens:
        raise ValueError('입력 자료가 너무 깁니다. 사실을 삭제하지 않고 메모를 나누어 요청해 주세요.')
    return values,{'prompt_tokens':tokens,'removed_examples':removed}
