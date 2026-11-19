"""Serve the exact frozen Curated1459 prompt without rewriting source facts."""
import re

from final_writing_profiles import AmbiguousWritingInput
from refine_over1000 import PROFILE as PROFILE_NAME, GENRE_NAMES, curated_messages

MAX_NEW_TOKENS = 512
PREFERENCE_EDITING_VERSION = 'surface_v1'
ACTOR_EDITING_VERSION = 'source_actor_v1'
_FIRST_PERSON = re.compile(r'^(저는|제가|나는|내가)\s+')
_OTHER_PERSON = re.compile(r'(?:동료|담당자|친구|관리자|진행자|검토자|기록자|팀원)(?:께서|은|는|이|가)\s')


def prose_sentences(text):
    """Split at sentence boundaries outside quotes, retaining quoted text verbatim."""
    result, start, quote = [], 0, None
    pairs = {'“': '”', '‘': '’', '"': '"', "'": "'"}
    for index, char in enumerate(text):
        if quote:
            if char == quote:
                quote = None
        elif char in pairs:
            quote = pairs[char]
        elif char in '.!?。' and (index + 1 == len(text) or text[index + 1].isspace()):
            result.append(text[start:index + 1].strip())
            start = index + 1
    if text[start:].strip():
        result.append(text[start:].strip())
    return [sentence for sentence in result if sentence]


def _clauses(sentence):
    if any(c in sentence for c in '“”‘’"\''):
        return [sentence]
    boundaries = [0] + [match.end() for match in re.finditer(
        r'[가-힣]*(?:했|었|았|였)(?:고|으며),?\s+|,\s+', sentence)] + [len(sentence)]
    return [sentence[a:b] for a, b in zip(boundaries, boundaries[1:]) if a < b]


def _action_key(clause):
    """Alignment only; never use normalized tokens as generated prose."""
    words = re.findall(r'[가-힣0-9]+', clause)
    if len(words) < 2:
        return None
    for ending in ('하였습니다', '했습니다', '하였으며', '했으며', '하였고', '했고',
                   '하였다', '했다', '합니다', '한다', '했음', '함',
                   '었습니다', '았습니다', '었으며', '았으며', '었다', '았다',
                   '었고', '았고', '습니다', '으며', '이다', '다', '고'):
        if words[-1].endswith(ending):
            words[-1] = words[-1][:-len(ending)]
            break
    particles = ('에서는', '에게는', '으로는', '에서', '에게', '으로',
                 '와', '과', '을', '를', '은', '는', '이', '가', '에', '의')
    for index, word in enumerate(words[:-1]):
        for particle in particles:
            if word.endswith(particle) and len(word) > len(particle) + 1:
                words[index] = word[:-len(particle)]
                break
    key = tuple(word for word in words if word)
    return key if len(key) >= 2 and sum(map(len, key)) >= 6 else None


def restore_source_actors(text, facts, kind):
    """Restore an explicit source narrator only for unique matching actions.

    No first person is inferred from genre alone. Collisions, paraphrases and
    quoted statements are left for source review rather than assigned an actor.
    """
    catalog, narrator_keys, narrator_actions = {}, set(), {}
    for fact in facts:
        for sentence in prose_sentences(fact):
            if any(c in sentence for c in '“”‘’"\''):
                continue
            for clause in _clauses(sentence):
                match = re.match(r'^(\S+(?:께서|은|는|이|가))\s+(.+)', clause.strip())
                if not match:
                    continue
                actor, action = match.groups()
                key = _action_key(action)
                if key is None:
                    continue
                catalog.setdefault(key, set()).add(actor)
                if actor in ('저는', '제가', '나는', '내가'):
                    narrator_keys.add(key)
                    narrator_actions.setdefault(key, set()).add(action)
    if not narrator_keys:
        return text, [], 0
    found, notes, restored = set(), [], 0
    result = []
    for sentence in prose_sentences(text):
        if any(c in sentence for c in '“”‘’"\''):
            result.append(sentence)
            continue
        clauses = []
        for clause in _clauses(sentence):
            narrator = _FIRST_PERSON.match(clause)
            key = _action_key(clause[narrator.end():] if narrator else clause)
            if key in narrator_keys:
                actors = catalog[key]
                if all(actor in ('저는', '제가', '나는', '내가') for actor in actors):
                    found.add(key)
                    if narrator is None:
                        actor = '저는' if kind == '자기소개서' else ('나는' if '나는' in actors or '내가' in actors else '저는')
                        if len(narrator_actions[key]) == 1:
                            # With the narrator restored, retain an object particle
                            # explicitly provided by the source: 저는 표기를 ...
                            for word in next(iter(narrator_actions[key])).split()[:-1]:
                                if word.endswith(('을', '를')):
                                    clause = re.sub(r'(?<!\S)' + re.escape(word[:-1]) + r'[은는](?=\s)', word, clause)
                        clause = actor + ' ' + clause
                        restored += 1
                elif narrator is None:
                    notes.append('같은 행동을 한 사람이 여럿입니다. 원문과 행동 주체를 확인해 주세요.')
            clauses.append(clause)
        result.append(''.join(clauses))
    if narrator_keys - found and any(_OTHER_PERSON.search(fact) for fact in facts):
        notes.append('본인과 다른 사람의 행동이 섞여 있습니다. 생략된 행동 주체를 원문과 확인해 주세요.')
    return ' '.join(result), list(dict.fromkeys(notes)), restored


def _guarded(sentence):
    # A conjunction can accidentally extend a condition to the following clause.
    return bool(re.search(r'[“”‘’"\'!?]|경우|조건|선택권|(?:^|\s)\S*면(?:\s|[,，])|때|에만', sentence))


def _connect(sentence):
    if (not sentence.endswith('.') or _guarded(sentence)
            or re.search(r'(?:으며|이며|했고|었고|았고|였고),?\s', sentence)):
        return None
    body = sentence[:-1]
    for ending, connective in (('입니다', '이며'), ('합니다', '하며'), ('됩니다', '되며'),
                               ('습니다', '으며'), ('이다', '이며'), ('한다', '하며'),
                               ('된다', '되며'), ('있다', '있으며'), ('없다', '없으며')):
        if body.endswith(ending):
            return body[:-len(ending)] + connective
    if body.endswith('다') and len(body) > 1 and '가' <= body[-2] <= '힣':
        # Closed past-tense/있- endings, never guess tense from memo shorthand.
        if (ord(body[-2]) - ord('가')) % 28 == 20:
            return body[:-1] + '으며'
    return None


def edit_preferences(text, preferences):
    """Surface editing only: retain every clause, actor, quantity and status.

    This is settings-based formatting, not a learned personal adapter. Do not
    expand scarce facts just to hit a requested total character count.
    """
    if preferences is None:
        return text
    sentences = prose_sentences(text)
    if preferences.preferred_tone == 'formal':
        endings = (('했습니다', '하였습니다'), ('됐습니다', '되었습니다'),
                   ('봤습니다', '보았습니다'), ('했다', '하였다'),
                   ('됐다', '되었다'), ('봤다', '보았다'))
        for index, sentence in enumerate(sentences):
            if _guarded(sentence):
                continue
            for before, after in endings:
                if sentence.endswith(before + '.'):
                    sentences[index] = sentence[:-len(before) - 1] + after + '.'
                    break
    if preferences.sentence_length == 'short':
        short = []
        for sentence in sentences:
            if len(sentence) <= 40 or _guarded(sentence):
                short.append(sentence)
                continue
            # Only split explicitly past-tense coordinations. Preserve order,
            # subjects and negation; do not split inferred or conditional events.
            ending = '습니다.' if sentence.endswith(('습니다.', '입니다.')) else '다.'
            divided = re.sub(r'([가-힣]+(?:했|하였|었|았|였))(?:고|으며),?\s+',
                             lambda m: m[1] + ending + ' ', sentence)
            short.extend(prose_sentences(divided))
        sentences = short
    elif preferences.sentence_length == 'long':
        combined, index = [], 0
        while index < len(sentences):
            first = sentences[index]
            link = _connect(first)
            if (link is not None and index + 1 < len(sentences)
                    and _connect(sentences[index + 1]) is not None
                    and len(first) + len(sentences[index + 1]) <= 150):
                # Keep the next clause's explicit subject, even when repeated.
                combined.append(link + ', ' + sentences[index + 1])
                index += 2
            else:
                combined.append(first)
                index += 1
        sentences = combined
    # Clear existing statements already satisfy confident style. Never turn
    # uncertainty into certainty or add achievements to manufacture a difference.
    return ' '.join(sentences)


def profile_messages(req, *, bounds=None):
    genre = {label: key for key, label in GENRE_NAMES.items()}.get(req.document_type, req.document_type)
    if genre == '자유글쓰기':
        genre = 'free_writing'
    if genre not in GENRE_NAMES:
        raise ValueError('지원하지 않는 글 유형입니다.')
    facts = list(req.facts)
    if genre == 'free_writing':
        for fact in facts:
            if re.fullmatch(r'[^\s]+(?:은|는)\s*(?:보관함|정리함)[.!?]?', fact.strip()):
                raise AmbiguousWritingInput(
                    '메모의 뜻을 확인해 주세요: '+fact+' — 보관했다는 뜻인지 보관함이라는 물건을 말하는지 적어 주세요.')
    bounds = list(bounds) if bounds is not None else [round(req.target_chars*.8), round(req.target_chars*1.2)]
    context = getattr(req, 'source_context', '') or ''
    messages = curated_messages(genre, req.topic, facts, bounds, fictional_context='가상' in context)
    extra = {'담백':'수식어를 줄여 담백하게 쓴다.', '격식':'차분하고 격식 있는 표현을 쓴다.',
             '친근':'글 유형의 말투를 유지하면서 부드럽게 설명한다.'}.get(getattr(req, 'tone', '기본'), '')
    if extra:
        messages[0]['content'] += ' 요청 말투: '+extra
    return GENRE_NAMES[genre], messages
