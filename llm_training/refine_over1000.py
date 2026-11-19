"""Offline, conservative curation of the frozen final 2,000 examples.

Only explicit build writes a new dataset. Never trains, calls a teacher API,
changes serving configuration, or overwrites the source. Lexical checks are
triage signals, not semantic certification. All decisions retain source hashes.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'data/final_2000_20261119'
PARENT = ROOT / 'data/quality_2000_balanced_v2'
DEST = ROOT / 'data/curated_over1000_20261119'
PROFILE = 'curated_over1000_20261119'
POLICY = {
    'minimum_train_rows':1001,
    'maximum_rows_per_scenario_family':2,
    'maximum_identical_long_sentence_rows':8,
    'long_sentence_min_compact_chars':20,
    'near_answer_jaccard':.80,
    'heldout_source_jaccard':.80,
    'max_total_tokens_with_eos':1024,
    'unresolved_surface_or_alignment_flags':'quarantine, not confirmed errors',
    'no_padding_or_threshold_relaxation_to_meet_count':True,
    'not_a_model_quality_score':True,
}

# Direct comparisons against the source facts in this session. No facts, dates,
# roles or requested lengths are changed, and no generated benchmark answer is
# used. Each substitution is constrained to one identified source row.
TARGET_EDITS = {
    'Q2K4-speech-035': [('도구를 빌렸다고 알리는 방법','도구를 빌릴 때 알리는 방법',
        '지침의 미래 조건을 이미 빌린 사건처럼 읽히는 표현에서 복원')],
    'Q2K4-speech-025': [('같은 글의 제목이 같을 때','제목이 같을 때',
        '같은/같다의 불필요한 중복 제거; 파일 구별 기준은 보존')],
    'Q2K-report-025-V0': [
        ('검토 결과 12건 중 4건은 재료비 포함 여부가 없어 비용 표기 상태를 기록했다.',
         '12건 중 4건에는 재료비 포함 여부가 없었다. 검토자는 비용 표기 상태를 기록했다.',
         '누락 상태와 기록 행동을 나누고 원문에 명시된 검토자를 복원')],
    'Q2K-report-043-V0': [
        ('파일 이름 대신 파일 속성에 표시된 값을 기준으로 모둠 발표 파일의 형식을 목록화했다.',
         '검토자는 파일 이름 대신 파일 속성에 표시된 값을 기준으로 모둠 발표 파일의 형식을 목록으로 작성했다.',
         '원문에 명시된 검토자를 보존하고 목록화 표현을 풀어 씀')],
    'Q2KR-speech-046': [('담당자가 명단을 확인하고 번호표를 드립니다.',
        '접수 담당자가 명단을 확인하고 번호표를 드립니다.', '원문의 접수 담당 역할을 명시')],
    'Q2K4-report-053': [
        ('시작과 끝 시각은 다른 칸에 적고 장비별로 모아 앞선 예약의 종료 시각과 다음 예약의 시작 시각을 비교했다.',
         '시작과 끝 시각은 다른 칸에 적었다. 담당자는 장비별로 예약을 모아 앞선 예약의 종료 시각과 다음 예약의 시작 시각을 비교했다.',
         '시간 표기 방식과 담당자의 비교 행동을 구분하고 원문의 행동 주체를 명시')],
    'Q2K-cover_letter-009-V2': [
        ('직접 대조한 정보의 범위를 밝히는 태도를 중요하게 생각합니다.',
         '정보를 직접 대조하는 범위를 밝히는 태도를 중요하게 생각합니다.',
         '아직 실행하지 않은 대조 계획이 완료 경험으로 읽히지 않도록 과거 관형 표현을 수정')],
    'V3Q-BASE-train-0272': [('가상의 경험으로, ','',
        '가상 사례라는 작성 맥락은 입력에 유지하고 부자연스러운 본문 작성 설명은 제거')],
}

# Source/target comparisons above showed these particular rule hits to be
# ellipsis or modality paraphrases. Resolutions are bound to exact hashes when
# persisted. No row-wide approval and no thresholds are relaxed.
REVIEW_RESOLUTIONS = {
    'Q2K4-free_writing-062':{('actor_alignment_review',2):
        '앞 문장의 진행자가 알려 준 예정 시각을 다음 문장에서 가리킴. 진행자가 기록했다는 의미로 바꾸지 않음.'},
    'Q2K4-report-034':{('actor_alignment_review',2):
        '바로 앞 문장의 주어 녹음 담당자가 이어지는 재생·대조 문장에도 적용되며 다른 주체가 끼어들지 않음.'},
    'Q2K4-report-005':{('actor_alignment_review',3):
        '검수자가 표지 대조 후 본문을 비교하고 점검표에 적는 연속 행동으로 읽히며 포장 담당자와 구분됨.'},
    'Q2K4-report-014':{('actor_alignment_review',3):
        '관리자의 확인·번호표 교체·목록 기록이 이어지는 문맥이며 별도의 행위자로 귀속하지 않음.'},
    'V3Q-BASE-train-0184':{('intention_alignment_review',0):
        '오늘 발표할 사례는이라는 미래 관형절이 발표 예정을 보존함. 완료된 발표로 바꾸지 않음.'},
    'Q2KR-speech-016':{('intention_alignment_review',4):
        '강제로 정하려는 절차가 아니다를 강제로 정하는 절차가 아니다로 표현함. 목적 부정을 유지함.'},
    'Q2KR-speech-075':{('intention_alignment_review',5):
        '다음 활동도 같은 방에서 이어지니 시작 시각에 돌아오라는 안내로 예정과 장소를 보존함.'},
}
RESOLUTION_PAIR_SHA = {
    'Q2K4-free_writing-062':'80b4e830854b2484c48fee4722dfc4e8d8bff4888ce03c7dad02307c930b59d6',
    'Q2K4-report-034':'9e808ad651f448849021a17776e7ec21c485a26dd2f5512c6e7d0d908d2ade8a',
    'Q2K4-report-005':'689e52a3b96c2fdf9fac704466e59412d8ab6bd5176a0bd0a7d66f8877e34cc4',
    'Q2K4-report-014':'8275fb7d57805e495a8db5ef85907af97a3cb8585006598223cb43648def4ae9',
    'V3Q-BASE-train-0184':'dfa1952d5de4c9d40cefc9320b95c2da02ff5e305ae9b5dc5e75f03934c0c6c1',
    'Q2KR-speech-016':'0559a430e39d333888e0d55d73bcfba8aca9b0842f686cc369a46cc79f7964eb',
    'Q2KR-speech-075':'b2217d77a4b662694b8617fdd554382040ecba30731122e2d7623f5854607737',
}
DIRECT_REVIEW_PAIRS = {
    'MERGED-ver2-train-0107':'28877c8128fc4b9e1ad49bbfa282443048f98c401d8cc51a11994e8b05445248',
    'MERGED-ver4-train-0093':'f45b36834beff2ee35955611261155ae9fb761129dafb353043f78ed459188a0',
    'MERGED-ver2-train-0241':'69c6766e1afca9dcbdd067152d0d2e26c0759018fa765bd66f17692d0199f270',
    'MERGED-ver3_supplement-train-0006':'838277fcccab8914fe97346eb0ba7361d84990278d445e5a81b14fe0d7ac6567',
    'Q2K4-report-049':'6f222f4811707f75878adcdae9eb6966213624d273881a133e23390483a0f66b',
    'REFINED-qwen35_service-train-0004':'2118086ef7964eedc0414fe187f5a1db56b81f32b1c3fdaf68d55b2405bb7777',
    'MERGED-ver2-train-0072':'a492b89613ecc56c09b5fe14c6cb59a2b10e37ce8eb7673327685829499b503c',
    'MERGED-ver2-train-0181':'f76d182d4ec7f718c6ed62ceee47d6b21b80bc135600b73cf8b96e77ac5a0ad5',
    'MERGED-ver4-train-0169':'282a05452d4990ae7ce1abcf9e9831276334cdd1c83272efcd286879be9f5efc',
    'MERGED-ver4-train-0122':'2edc962b5ab24b3ac68541af6854bfe517f78e1d773a2c58a48c26c25f88b180',
    'Q2K-cover_letter-012-V0':'8bf611000d9427eeeb7133c65ad9f4194d9874f2b5dd1849cb1c8bb558269163',
    'Q2K-cover_letter-009-V2':'9fddd4bbc092bc9d05f73b7ca90e0c03823b6e8fcdeeaaaedc49a261c6eeddce',
    'V3Q-BASE-train-0300':'cfd73dd1bac138340d91bdecaa5a00ccccaac4e9810d620a950ae6852f48ff46',
    'MERGED-ver4-train-0258':'fd3f3346cd0a4a858a42fc122ae75fe8a74d5a7b2cb88cf493bfb6e800b2295e',
    'Q2K-speech-051-V0':'15408957eab24d7f2e8d53f66d5819a0ba376b448979dbd1ec54d6daf92ecca8',
    'Q2K-speech-039-V1':'32a11d0fec273f616fb915fa302942d12ec045df7d8e1e266cbebf0a4e99eb5f',
    'Q2K4-speech-033':'00db190dfce75a7c0da6613289056eb2ea86baac3a3b13d9d10de7a788f15de4',
    'Q2K4-speech-030':'8e4c9f0d75d0a14838f9720759aa38aee0c34f0703f039c19344d8e22d189b8d',
    'V3Q-BASE-train-0272':'704e0c41f1ca10b5e2676144ab441fa2804335f38ff49b17abb59471c3c51317',
    'V3Q-BASE-train-0096':'1740015d0919fe30518b4bae17ad84c68c74d29d5b96298977bfc57d68fa9ae2',
    'REFINED-qwen35_service-train-0021':'9783462269077ff9b122abdea4c4afeb7361e0bbf0edfd7c4eee665ac90cae94',
    'Q2KR-free_writing-001':'dafd2756b485650a38960f0f94e13c94d0146538d283a2d4823a0974dbe6817a',
    'Q2K-free_writing-012-V0':'bdc5ebc6137cb4377ac83593867dd0e325b925aa94e09e19d2de602bd8c60d46',
    'Q2K4-free_writing-050':'2240e8e3b20f05e73927dfe2665e8e3cc8d7a73e3f32267527b05f9d9fd39292',
}

COMMON_SYSTEM = (
    '입력 자료를 요청한 글 유형의 자연스러운 한국어 본문으로 다듬는다. '
    '사실·행동·명시된 생각만 사용하고 주체·수치·단위·날짜·인용문·부정·조건을 보존한다. '
    '계획·제안·완료·미완료·미확인을 구분한다. 다른 사람의 행동을 화자의 행동으로 바꾸지 않는다. '
    '자료에 없는 사건·감각·감정·원인·성과·교훈·다짐을 보태지 않는다. '
    '작성 참고와 미제공 설명은 본문에서 제외하되 실제로 하지 않은 일과 확인하지 못한 상태는 유지한다. '
    '뜻을 바꾸지 않고 메모체와 띄어쓰기를 다듬으며 관련 내용을 자연스럽게 연결한다. '
    '같은 뜻은 한 번만 전하고 분량을 채우려고 반복하지 않는다. 제목·목록·작업 설명 없이 한 문단만 출력한다. '
)
GENRE_SYSTEM = {
    'report':'객관적인 설명체(~했다, ~이다)로 쓴다. 사람의 행동과 물건의 상태를 구분한다. '
        '같은 주어의 관련 행동은 연결할 수 있지만 주체가 다른 행동은 분명히 구별한다. 누락된 정보의 이름과 점검 범위를 보존한다.',
    'cover_letter':'본인의 행동은 일인칭 존댓말(~했습니다, ~합니다)로 쓴다. '
        '동료나 담당자의 행동과 계획은 그 사람을 주어로 한 존댓말 문장으로 쓴다. 명시된 태도만 행동과 연결한다.',
    'speech':'청중에게 직접 말하는 자연스러운 존댓말로 쓴다. 인사말은 생략하고 도입과 결말을 되풀이하지 않는다. '
        '선택권을 이미 선택한 사건으로 쓰지 않는다. 수량의 대상, 지참 의무, 수령 확인 조건을 보존한다.',
    'free_writing':'담백한 문체(~했다, ~한다, ~이다)로 관찰·행동·생각을 자연스럽게 잇는다. '
        '제목을 실제 사건으로 만들지 않는다. 가상 경험 같은 자료 성격은 작성 맥락이다. '
        '메모의 명사형 어미를 기계적으로 바꾸어 시점이나 의도를 확정하지 않는다.',
}
GENRE_NAMES={'report':'보고서','cover_letter':'자기소개서','speech':'발표문','free_writing':'자유 글쓰기'}


def curated_messages(genre, topic, facts, bounds, fictional_context=False):
    """Candidate-only prompt. Raw source bullets remain byte-for-byte strings.

    No demonstrations, source expansion, inferred background, or tense rewrite.
    Future training/serving must explicitly select this profile together; this
    function does not modify the currently running application.
    """
    user=f'글 유형: {GENRE_NAMES[genre]}\n주제: {topic}\n'
    if fictional_context:
        user+='자료 성격: 실제 인물의 실적이 아닌 가상 연습 사례\n'
    user+='작성 자료:\n'+'\n'.join('- '+f for f in facts)
    user+=f'\n출력 조건: 공백 포함 {bounds[0]}~{bounds[1]}자. 핵심 사실을 모두 보존하고 본문 한 문단만 출력한다.'
    return [{'role':'system','content':COMMON_SYSTEM+GENRE_SYSTEM[genre]},
            {'role':'user','content':user}]


def apply_target_edits(row):
    edits=[]
    for before,after,reason in TARGET_EDITS.get(row['id'],[]):
        text=row['completion'][0]['content']
        assert text.count(before)==1,(row['id'],before)
        row['completion'][0]['content']=text.replace(before,after)
        for tr in row['assertion_trace']:
            tr['rendered']=tr.get('rendered','').replace(before,after)
        edits.append({'before':before,'after':after,'reason_ko':reason})
    return edits


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def read_rows(path):
    return [json.loads(s) for s in Path(path).read_text(encoding='utf-8-sig').splitlines() if s.strip()]


def facts_of(row):
    return row.get('request', {}).get('facts') or re.findall(r'^-\s*(.+)$', row['prompt'][-1]['content'], re.M)


def staged_rows():
    """Recover owning-source inputs, not previously expanded prompt text.

    Some final rows lack request metadata. For these, the immutable parent is
    the source of truth. Trace strings alone are never used to invent inputs.
    """
    original=read_rows(SOURCE/'train.jsonl')
    parents={r['id']:r for r in read_rows(PARENT/'train.jsonl')}
    rows=[]
    for before in original:
        r=deepcopy(before)
        owner=before if before.get('request',{}).get('facts') else parents[r['id']]
        assert before['completion']==owner['completion'],r['id']
        raw=facts_of(owner)
        prior=re.findall(r'^-\s*(.+)$',before['prompt'][-1]['content'],re.M)
        r['request']={**r.get('request',{}),'document_type':r['category'],
            'topic':r['topic'],'facts':list(raw),'tone':'기본',
            'target_chars':r.get('request',{}).get('target_chars',round(sum(r['requested_char_bounds'])/2))}
        context=bool(re.search(r'자료 성격:.*가상|가상 연습 사례',owner['prompt'][-1]['content']))
        r['_curation']={'source_row_sha256':digest(before),
            'input_owner':'final_2000_20261119' if owner is before else 'quality_2000_balanced_v2',
            'owner_row_sha256':digest(owner),'raw_facts_sha256':digest(raw),
            'restore_unexpanded_input':raw!=prior,'fictional_context':context}
        r['_curation']['before_target_edits_pair_sha256']=digest({'facts':raw,'answer':r['completion'][0]['content']})
        r['_curation']['target_edits']=apply_target_edits(r)
        rows.append(r)
    return rows


def compact(text):
    return re.sub(r'[^가-힣A-Za-z0-9]', '', text)


def grams(text, n=2):
    value = compact(text)
    return {value[i:i+n] for i in range(len(value)-n+1)}


def sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+(?![”’])', text) if s.strip()]


def numbers(text):
    # Explicit counters only. Never interpret auxiliary '둘 수' as the count two.
    native = {'한':1, '하나':1, '두':2, '둘':2, '세':3, '셋':3, '네':4, '넷':4,
              '다섯':5, '여섯':6, '일곱':7, '여덟':8, '아홉':9, '열':10,
              '열한':11, '열두':12, '열세':13, '열네':14, '열다섯':15,
              '스무':20, '스물한':21, '서른':30}
    units = r'(?:개|명|장|곳|번|차례|칸|대|권|벌|묶음|상자|가지|구간|줄|쪽|가닥|그루|봉지|통|팀|분|시간)'
    # 둘 곳 / 둘 칸 is the verb 'to put', not two places/cells.
    for word, value in sorted(native.items(), key=lambda p: -len(p[0])):
        if word in ('하나','둘','셋','넷'):continue
        text = re.sub(r'(?<![가-힣])'+word+r'\s*(?='+units+r')', str(value), text)
    # Count words before common counted nouns, including '열두 파일'.
    nouns=r'(?:파일|사진|책|색|표|질문|판본|작품|받침|문장|번호|버튼|조각|고리|바퀴|목록|그림|장소|물건|순서|활동)'
    for word,value in sorted(native.items(), key=lambda p:-len(p[0])):
        if word in ('한','하나','둘','셋','넷'):continue
        text=re.sub(r'(?<![가-힣])'+word+r'\s+(?='+nouns+r')',str(value),text)
    text = re.sub(r'(?<![가-힣])(하나|둘|셋|넷)(?=[을를이가만도와과의씩는은]|[.,!?]|$)',
                  lambda m: str(native[m[1]]), text)
    return set(re.findall(r'\d+(?:\.\d+)?', text))


def quotes(text):
    return Counter(next(s for s in m if s) for m in re.findall(r'“([^”]+)”|「([^」]+)」|‘([^’]+)’|"([^"\n]+)"', text))


def content_fact(text, trace):
    if trace.get('status') in ('writing_note', 'redundant'):
        return False
    return not text.startswith(('작성 메모:', '작성 참고:', '작성 조건:', '주의 사항:'))


def audit_row(row):
    """Independent surface checks plus trace consistency; no quality score."""
    flags = []
    def add(kind, **details):
        flags.append({'kind':kind, **details})
    facts = facts_of(row)
    text = row['completion'][0]['content']
    traces = row.get('assertion_trace', [])
    if not facts or not traces or len(row['completion']) != 1:
        add('invalid_structure')
    lo, hi = row['requested_char_bounds']
    if not lo <= len(text) <= hi:
        add('length_outside_original_bounds', chars=len(text), bounds=[lo,hi])
    if text.strip() != text or '\n' in text or re.search(r'[\ufffd\u0000-\u0008]', text):
        add('invalid_text_surface')
    if re.search(r'알림했|고침했|생각남했|보관함으로\s*두|함했다', text):
        add('malformed_memo_conjugation')
    if re.search(r'(?:했음|않음|없음|있음|안함|모름)[.!?](?:\s|$)', text):
        add('unfinished_memo_ending')
    ss = sentences(text)
    if len({compact(s) for s in ss}) != len(ss):
        add('repeated_sentence')
    source = ' '.join(facts)
    source_terms = grams(source+' '+row.get('topic',''))
    extra = numbers(text) - numbers(source+' '+row.get('topic',''))
    missing = numbers(source) - numbers(text)
    if extra: add('new_number_review', values=sorted(extra))
    if missing: add('missing_number_review', values=sorted(missing))
    if quotes(source) != quotes(text):
        add('literal_quote_difference')
    for i, fact in enumerate(facts):
        matches = [t for t in traces if t.get('source_fact_index') == i]
        if len(matches) != 1 or matches[0].get('source') != fact:
            add('stale_source_trace', fact_index=i)
            continue
        tr = matches[0]
        if not content_fact(fact, tr):
            continue
        rendered = tr.get('rendered','')
        if not rendered or rendered not in text:
            add('stale_target_trace', fact_index=i)
            continue
        terms = grams(fact)
        coverage = len(terms & grams(text))/max(1,len(terms))
        if len(compact(fact)) >= 12 and coverage < .32:
            add('weak_fact_support_review', fact_index=i, coverage=round(coverage,4))
        # A role is checked in its own aligned clause, rather than anywhere in
        # the paragraph. Missing explicit roles need source review, not guessing.
        actor = re.match(r'^((?:(?:다른|별도의|접수|기록|녹음|모임|포장|수령|받는)\s+)?(?:동료|직원|담당자|관리자|검토자|점검자|검수자|진행자))(?:은|는|이|가)\s*', fact)
        role=actor[1] if actor else ''
        alias=re.sub(r'^(?:모임|기록|녹음)\s+', '', role)
        if actor and role not in rendered and alias not in rendered:
            add('actor_alignment_review', fact_index=i, actor=actor[1])
        if re.search(r'계획|예정|하려(?!면)|두려|보려|싶', fact) and not re.search(r'계획|예정|려|싶|할지|겠습니다|검토|제안|하자|생각|정하기로|선택', rendered):
            add('intention_alignment_review', fact_index=i)
        # '제안함' contains the syllables 안함 but is not a negation.
        if re.search(r'않|없|못|(?<!제)안함|미정|모름|알 수 없', fact) and not re.search(r'않|없|못|안 |미정|모르|모른|정하지|알 수', rendered):
            add('negative_alignment_review', fact_index=i)
        if re.search(r'받았다는\s*답|수령\s*확인',fact) and not re.search(r'받았|수령',rendered):
            add('receipt_condition_review', fact_index=i)
    for s in ss:
        terms=grams(s)
        support=len(terms & source_terms)/max(1,len(terms))
        if len(compact(s))>=18 and support < .40:
            add('weak_sentence_support_review', sentence=s, coverage=round(support,4))
        if row['category'] in ('speech','cover_letter') and not re.search(r'(?:니다|세요|나요|가요|까요|어요|아요|해요|죠|지요|시다)[.!?]$',s):
            add('honorific_ending_review', sentence=s)
    if re.search(r'생각을 생각|마음을 생각',text):
        add('awkward_thought_phrase_review')
    if re.search(r'배웠|다짐|강점|중요하게|싶습니다', text) and not re.search(r'배웠|배운|배움|다짐|강점|중요|싶|태도|강조|중시|의견',source):
        add('unsupported_reflection_review')
    return flags


def screened_flags(row):
    flags=audit_row(row)
    resolutions=REVIEW_RESOLUTIONS.get(row['id'],{})
    if resolutions:
        actual=digest({'facts':facts_of(row),'answer':row['completion'][0]['content']})
        if actual!=RESOLUTION_PAIR_SHA[row['id']]:return flags
    return [f for f in flags if (f['kind'],f.get('fact_index')) not in resolutions]


def near_pairs(rows, threshold=.80):
    """Answer character-4-gram Jaccard; similarities are review signals only."""
    features=[grams(r['completion'][0]['content'],4) for r in rows]
    inverted=defaultdict(list)
    out=[]
    for i,feature in enumerate(features):
        counts=Counter(j for t in feature for j in inverted[t])
        for j,n in counts.items():
            if rows[i]['category']!=rows[j]['category']: continue
            score=n/(len(feature)+len(features[j])-n)
            if score>=threshold:out.append((rows[j]['id'],rows[i]['id'],round(score,5)))
        for t in feature:inverted[t].append(i)
    return sorted(out,key=lambda x:(-x[2],x[0],x[1]))


def state_signature(row):
    facts=facts_of(row)
    # Only for diversity sampling within an already-declared family. This is
    # deliberately not used as a claim of semantic equivalence across families.
    return tuple(sorted((bool(re.search(r'(?<!제)안함|않|없|못|미정|모름',f)),
                         bool(re.search(r'계획|예정|려|싶|겠습니다',f)),
                         tuple(sorted(numbers(f)))) for f in facts))


def protected_sources():
    cases=[]
    paths=[SOURCE/'valid.jsonl',SOURCE/'test.jsonl',
           ROOT/'outputs/final_release_20261119/cases.json',
           ROOT/'outputs/final_release_20261119/application_v2/fresh_cases.json']
    hashes={}
    def collect(value, origin):
        if isinstance(value,list):
            for v in value:collect(v,origin)
        elif isinstance(value,dict):
            if value.get('facts') and (value.get('genre') or value.get('category')):
                cases.append({'id':value.get('id',''), 'category':value.get('genre') or value.get('category'),
                    'facts':value['facts'],'family':value.get('scenario_family_id'),'origin':origin})
            else:
                for v in value.values():
                    if isinstance(v,(dict,list)):collect(v,origin)
    for p in paths:
        if not p.exists():raise FileNotFoundError(p)
        hashes[str(p.relative_to(ROOT))]=sha(p)
        if p.suffix=='.jsonl':
            for r in read_rows(p):
                cases.append({'id':r['id'],'category':r['category'],'facts':facts_of(r),
                    'answer_digest':digest(compact(r['completion'][0]['content'])),
                    'family':r.get('scenario_family_id'),'origin':str(p.relative_to(ROOT))})
        else:collect(json.loads(p.read_text(encoding='utf-8')),str(p.relative_to(ROOT)))
    return cases,hashes


def heldout_conflicts(rows, cases):
    index=defaultdict(list)
    features=[]
    for i,c in enumerate(cases):
        feature=grams(' '.join(c['facts']),4);features.append(feature)
        for g in feature:index[g].append(i)
    out=defaultdict(list)
    for r in rows:
        answer_hash=digest(compact(r['completion'][0]['content']))
        for c in cases:
            if c.get('answer_digest')==answer_hash:
                out[r['id']].append({'heldout_id':c['id'],'same_answer':True,'origin':c['origin']})
        feature=grams(' '.join(facts_of(r)),4)
        counts=Counter(i for g in feature for i in index.get(g,[]))
        for i,n in counts.items():
            c=cases[i]
            if c['category']!=r['category']:continue
            score=n/max(1,len(feature)+len(features[i])-n)
            same_family=bool(r.get('scenario_family_id') and r['scenario_family_id']==c.get('family'))
            same_answer=c.get('answer_digest')==digest(compact(r['completion'][0]['content']))
            if score>=POLICY['heldout_source_jaccard'] or same_family or same_answer:
                out[r['id']].append({'heldout_id':c['id'],'source_jaccard':round(score,5),
                    'same_family':same_family,'same_answer':same_answer,'origin':c['origin']})
    return dict(out)


def select_rows(rows, cases):
    flags={r['id']:screened_flags(r) for r in rows}
    conflicts=heldout_conflicts(rows,cases)
    pairs=near_pairs(rows,POLICY['near_answer_jaccard'])
    neighbors=defaultdict(list)
    for a,b,s in pairs:
        neighbors[a].append((b,s));neighbors[b].append((a,s))
    def priority(r):
        mode=r.get('input_refinement',{}).get('input_mode','')
        return (not bool(r['_curation']['target_edits']),mode=='spacing_error',digest(r['id']))
    family_counts=Counter();family_states=defaultdict(set);sentence_counts=Counter()
    kept=[];kept_ids=set();decisions={}
    for r in sorted(rows,key=priority):
        rid=r['id'];reason=None;detail=None
        family=r.get('scenario_family_id') or rid
        sig=state_signature(r)
        long_sentences={compact(s) for s in sentences(r['completion'][0]['content'])
                        if len(compact(s))>=POLICY['long_sentence_min_compact_chars']}
        if r['_curation'].get('total_tokens',0)>POLICY['max_total_tokens_with_eos']:
            reason='token_limit_quarantine';detail={'total_tokens':r['_curation']['total_tokens']}
        elif flags[rid]:reason='unresolved_check_quarantine';detail=flags[rid]
        elif rid in conflicts:reason='heldout_similarity_quarantine';detail=conflicts[rid]
        elif family_counts[family]>=POLICY['maximum_rows_per_scenario_family']:
            reason='scenario_family_downsample'
        elif sig in family_states[family]:reason='same_family_state_downsample'
        else:
            close=[{'kept_id':other,'answer_jaccard':s} for other,s in neighbors[rid]
                   if other in kept_ids and (next(x for x in kept if x['id']==other).get('scenario_family_id') or other)!=family]
            repeated=sorted(s for s in long_sentences if sentence_counts[s]>=POLICY['maximum_identical_long_sentence_rows'])
            if close:reason='near_template_downsample';detail=close
            elif repeated:reason='frequent_sentence_downsample';detail=repeated
        if reason:
            decisions[rid]={'status':'excluded','reason':reason,'details':detail}
        else:
            kept.append(r);kept_ids.add(rid);family_counts[family]+=1;family_states[family].add(sig)
            sentence_counts.update(long_sentences)
            decisions[rid]={'status':'retained','reason':'passed_declared_screening'}
    kept.sort(key=lambda r:digest(r['id']))
    return kept,decisions,flags,conflicts,pairs


def summary(rows, kept, decisions, flags, pairs):
    return {'input_rows':len(rows),'retained_rows':len(kept),'excluded_rows':len(rows)-len(kept),
        'retained_categories':dict(Counter(r['category'] for r in kept)),
        'exclusion_reasons':dict(Counter(d['reason'] for d in decisions.values() if d['status']=='excluded')),
        'source_flags_before':dict(Counter(f['kind'] for fs in flags.values() for f in fs)),
        'raw_inputs_restored_retained':sum(r['_curation']['restore_unexpanded_input'] for r in kept),
        'target_edits_retained':[r['id'] for r in kept if r['_curation']['target_edits']],
        'near_answer_pairs_before':len(pairs),'near_answer_pairs_after':len(near_pairs(kept,POLICY['near_answer_jaccard']))}


def input_hashes():
    manifest=json.loads((SOURCE/'manifest.json').read_text(encoding='utf-8'))
    for name in ('train','valid','test'):
        assert sha(SOURCE/f'{name}.jsonl')==manifest['files'][name]['sha256'],('changed source',name)
    assert sha(PARENT/'train.jsonl')==manifest['parent_train_sha256'],'changed owning parent'
    paths=[SOURCE/p for p in ('train.jsonl','valid.jsonl','test.jsonl','manifest.json','replacement_ledger.json')]
    paths += [PARENT/'train.jsonl',PARENT/'manifest.json',ROOT/'model_selection.json',
              ROOT/'outputs/final_release_20261119/selection.json']
    return {str(p.relative_to(ROOT)):sha(p) for p in paths}


def assert_protected(hashes):
    for path,value in hashes.items():
        assert sha(ROOT/path)==value,('protected file changed',path)


def token_lengths(rows, processor):
    lengths=[]
    for r in rows:
        prefix=processor.apply_chat_template(r['prompt'],tokenize=False,
                    add_generation_prompt=True,enable_thinking=False)
        prompt=len(processor.tokenizer(prefix,add_special_tokens=False)['input_ids'])
        answer=len(processor.tokenizer(r['completion'][0]['content'],add_special_tokens=False)['input_ids'])
        assert answer>0,r['id']
        lengths.append({'prompt':prompt,'answer':answer,'total':prompt+answer+1})
    return lengths


def slim_row(r):
    return {k:deepcopy(r[k]) for k in ('id','category','topic','request','requested_char_bounds','prompt','completion','assertion_trace')}


def verify_rows(rows,cases):
    assert len(rows)>=POLICY['minimum_train_rows'],('below minimum',len(rows))
    assert len({r['id'] for r in rows})==len(rows),'duplicate IDs'
    assert len({digest(r['prompt']) for r in rows})==len(rows),'duplicate prompts'
    assert len({compact(r['completion'][0]['content']) for r in rows})==len(rows),'duplicate answers'
    assert set(Counter(r['category'] for r in rows))==set(GENRE_SYSTEM),'missing genre'
    for r in rows:
        assert not screened_flags(r),(r['id'],screened_flags(r))
        assert [m['role'] for m in r['prompt']]==['system','user'],r['id']
        assert re.findall(r'^-\s*(.+)$',r['prompt'][-1]['content'],re.M)==facts_of(r),r['id']
        assert '모든 문장을 일인칭' not in str(r['prompt']),r['id']
        assert '항목마다 완성 문장' not in str(r['prompt']),r['id']
        assert r['human_review'] is False and r['curation']['quality_certified'] is False,r['id']
    assert not heldout_conflicts(rows,cases),'heldout overlap/similarity'
    family_counts=Counter(r.get('scenario_family_id') or r['id'] for r in rows)
    assert max(family_counts.values())<=POLICY['maximum_rows_per_scenario_family']
    counts=Counter(s for r in rows for s in {compact(v) for v in sentences(r['completion'][0]['content'])}
                   if len(s)>=POLICY['long_sentence_min_compact_chars'])
    assert max(counts.values(),default=0)<=POLICY['maximum_identical_long_sentence_rows']
    return {'rows_checked':len(rows),'facts_checked':sum(len(facts_of(r)) for r in rows),
        'unique_ids_prompts_answers':True,'unresolved_declared_checks':0,
        'heldout_exact_or_high_similarity_conflicts':0,
        'maximum_rows_per_family':max(family_counts.values()),
        'maximum_long_sentence_frequency':max(counts.values(),default=0),
        'all_source_bullets_preserved_exactly':True,'quality_certified':False}


def build():
    if DEST.exists():raise RuntimeError('Candidate folder already exists; use verify. Never overwrite frozen datasets.')
    protected=input_hashes()
    cases,heldout_hashes=protected_sources();protected.update(heldout_hashes)
    rows=staged_rows()
    for r in rows:
        r['prompt']=curated_messages(r['category'],r['topic'],facts_of(r),r['requested_char_bounds'],r['_curation']['fictional_context'])
    from transformers import AutoProcessor
    processor=AutoProcessor.from_pretrained('Qwen/Qwen3.5-2B',local_files_only=True)
    lengths=token_lengths(rows,processor)
    for r,n in zip(rows,lengths):r['_curation'].update({'total_tokens':n['total'],'prompt_tokens':n['prompt'],'answer_tokens':n['answer']})
    kept,decisions,flags,conflicts,pairs=select_rows(rows,cases)
    stats=summary(rows,kept,decisions,flags,pairs)
    output=[];ledger=[]
    for r in rows:
        rid=r['id'];evidence=deepcopy(r['_curation']);actual_pair=digest({'facts':facts_of(r),'answer':r['completion'][0]['content']})
        direct=DIRECT_REVIEW_PAIRS.get(rid)
        if direct:
            assert direct==evidence['before_target_edits_pair_sha256'],('stale direct review',rid,direct,evidence['before_target_edits_pair_sha256'])
        resolutions=[]
        if rid in REVIEW_RESOLUTIONS:
            assert actual_pair==RESOLUTION_PAIR_SHA[rid],('stale resolution',rid)
            resolutions=[{'kind':k[0],'fact_index':k[1],'note_ko':v} for k,v in REVIEW_RESOLUTIONS[rid].items()]
        item={'id':rid,**decisions[rid],**evidence,'input_answer_pair_sha256':actual_pair,
              'automatic_flags':audit_row(r),'resolved_rule_hits':resolutions,
              'primary_assistant_source_review':bool(direct or rid in TARGET_EDITS or resolutions),
              'independent_human_review':False}
        ledger.append(item)
        if decisions[rid]['status']=='retained':
            out=slim_row(r)
            out.update({'synthetic':True,'human_review':False,'revision':PROFILE,
                'scenario_family_id':r.get('scenario_family_id'),
                'curation':{'source_row_sha256':evidence['source_row_sha256'],
                    'raw_facts_sha256':evidence['raw_facts_sha256'],'profile':PROFILE,
                    'total_tokens':evidence['total_tokens'],'quality_certified':False,
                    'primary_assistant_source_review':item['primary_assistant_source_review']}})
            output.append(out)
    output.sort(key=lambda r:digest(r['id']))
    verification=verify_rows(output,cases)
    assert_protected(protected)
    manifest={'status':'screened_candidate_not_trained','created_utc':datetime.now(timezone.utc).isoformat(),
        'profile':PROFILE,'policy':POLICY,'counts':stats,'verification':verification,
        'training_count':len(output),'validation_count':184,'test_count':182,
        'synthetic_data':True,'new_generated_examples':0,'external_api_used':False,
        'training_performed':False,'service_configuration_changed':False,'quality_approved':False,
        'primary_assistant_review':{'stratified_source_target_pairs':len(DIRECT_REVIEW_PAIRS),
            'target_edit_candidates':len(TARGET_EDITS),'resolved_row_specific_rule_hits':len(REVIEW_RESOLUTIONS),
            'reviewed_retained_rows':sum(r['curation']['primary_assistant_source_review'] for r in output),
            'independent_human_review':False,'all_rows_semantically_reviewed':False},
        'split_policy':'Train is curated. Valid/test are byte-identical legacy parent files, never edited using their answers. '
            'Their prompts differ from the new candidate profile; a future quality comparison must use the same new profile for every model and fresh held-out cases.',
        'limitations':['Rule checks can miss semantic errors; quarantined rows include valid paraphrases.',
            'This is a synthetic subset, not proof of improved model naturalness or superiority to Ver3.',
            'Do not mix this candidate with its 2000-row source, which would restore removed patterns.',
            'New training and matching serving-profile changes require a separate user instruction.'],
        'protected_files':protected,'source_code_sha256':sha(Path(__file__)),
        'token_summary':{'max_total':max(r['curation']['total_tokens'] for r in output),
            'mean_total':round(sum(r['curation']['total_tokens'] for r in output)/len(output),1)},
        'files':{}}
    DEST.mkdir(parents=True)
    (DEST/'train.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in output),encoding='utf-8')
    for split in ('valid','test'):(DEST/f'{split}.jsonl').write_bytes((SOURCE/f'{split}.jsonl').read_bytes())
    (DEST/'curation_ledger.json').write_text(json.dumps({'policy':POLICY,'decisions':ledger},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for name in ('train.jsonl','valid.jsonl','test.jsonl','curation_ledger.json'):
        manifest['files'][name]={'sha256':sha(DEST/name),'bytes':(DEST/name).stat().st_size}
    (DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    counts=' / '.join(f'{GENRE_NAMES[k]} {v}개' for k,v in stats['retained_categories'].items())
    report=(f'데이터 정제 결과\n\n학습 후보: {len(output):,}개 (기존 2,000개 중 {stats["excluded_rows"]:,}개 보류·축소)\n'
        f'{counts}\n검증 184개, 테스트 182개는 원본 그대로 별도 보존. 학습 후보 수에 합산하지 않음.\n\n'
        f'원래 메모로 복원한 입력: {stats["raw_inputs_restored_retained"]}개\n'
        f'정답 문장을 직접 수정한 채택 사례: {len(stats["target_edits_retained"])}개\n'
        '자기소개서의 모든 문장을 일인칭으로 강제하는 지시를 제거하고 타인의 주체 보존을 명시.\n'
        '보고서의 항목별 한 문장 강제를 제거하고 같은 주어의 관련 사실을 연결하도록 정리.\n'
        '입력 사실의 시제·장소·의도를 자동으로 확장하지 않는 짧은 후보 프롬프트 사용.\n'
        f'같은 계열은 최대 2개, 20자 이상 동일 문장은 최대 8개 사례까지만 유지.\n'
        f'모든 학습 후보의 형식·분량·원문 연결·인용문·수치·주체·부정·계획 관련 규칙 점검.\n'
        f'주 어시스턴트가 장르·분량별 표본 24개 및 수정·오탐 해결 대상을 직접 대조.\n'
        f'직렬화 후 최대 {manifest["token_summary"]["max_total"]}토큰; 1,024토큰 제한에서 원문·정답 잘림 없음.\n\n'
        '주의: 규칙 검사는 의미의 완전한 보존을 보증하지 않음. 보류 사례가 모두 오류라는 뜻도 아님.\n'
        '독립적인 사람의 전수 검수나 모델 개선 검증은 수행하지 않음. Ver3보다 좋아졌다고 확정할 수 없음.\n'
        '학습·웹 모델·전역 모델 선택은 변경하지 않음. 이 후보를 학습할 때는 후보 프롬프트를 평가·서빙에도 일치시켜 비교해야 함.\n'
        '제거한 패턴이 돌아오므로 기존 2,000개와 다시 합치지 않는 것을 권장.\n\n'
        'train.jsonl: 학습 후보 / valid.jsonl·test.jsonl: 보존된 평가 자료\n'
        'manifest.json: 수량·해시·점검 범위 / curation_ledger.json: 원본 2,000개 각각의 채택·보류·수정 근거\n')
    (DEST/'정제_결과.txt').write_text(report,encoding='utf-8')
    verify(processor)
    print(json.dumps({'destination':str(DEST),**stats,'verification':verification,'token_summary':manifest['token_summary']},ensure_ascii=False,indent=2))


def verify(processor=None):
    manifest=json.loads((DEST/'manifest.json').read_text(encoding='utf-8'))
    assert_protected(manifest['protected_files'])
    assert sha(Path(__file__))==manifest['source_code_sha256'],'curation script changed'
    for path,info in manifest['files'].items():assert sha(DEST/path)==info['sha256'],path
    for s in ('valid','test'):assert (DEST/f'{s}.jsonl').read_bytes()==(SOURCE/f'{s}.jsonl').read_bytes(),s
    rows=read_rows(DEST/'train.jsonl')
    result=verify_rows(rows,protected_sources()[0])
    assert result==manifest['verification']
    if processor is None:
        from transformers import AutoProcessor
        processor=AutoProcessor.from_pretrained('Qwen/Qwen3.5-2B',local_files_only=True)
    lengths=token_lengths(rows,processor)
    assert all(n['total']==r['curation']['total_tokens']<=1024 for r,n in zip(rows,lengths))
    ledger=json.loads((DEST/'curation_ledger.json').read_text(encoding='utf-8'))['decisions']
    assert len(ledger)==2000 and len({d['id'] for d in ledger})==2000
    assert {d['id'] for d in ledger if d['status']=='retained'}=={r['id'] for r in rows}
    assert len(rows)==manifest['training_count']
    print(json.dumps({'readback_verified':True,**result},ensure_ascii=False))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['inspect','preview','build','verify'])
    args=parser.parse_args()
    if args.action=='build':build();return
    if args.action=='verify':verify();return
    rows=staged_rows()
    by_id={r['id']:r for r in rows}
    if args.action=='preview':
        cases,_=protected_sources()
        kept,decisions,flags,conflicts,pairs=select_rows(rows,cases)
        print(json.dumps(summary(rows,kept,decisions,flags,pairs),ensure_ascii=False,indent=2))
        return
    flags={r['id']:audit_row(r) for r in rows}
    pairs=near_pairs(rows,.80)
    print(json.dumps({'source_rows':len(rows),'flagged_rows':sum(bool(x) for x in flags.values()),
       'flag_counts':dict(Counter(f['kind'] for fs in flags.values() for f in fs)),
       'clean_categories':dict(Counter(r['category'] for r in rows if not flags[r['id']])),
       'near_answer_pairs_080':len(pairs),'pair_sample':pairs[:15],
       'flag_sample':[{'id':k,'flags':v,'facts':facts_of(by_id[k]),'answer':by_id[k]['completion'][0]['content']} for k,v in flags.items() if v][:12]},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
