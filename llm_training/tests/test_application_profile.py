"""Observed actor, obligation, and memo-noun regressions."""
from pathlib import Path
import sys
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from application_writing_profile import profile_messages,sentence_from_memo


def test_irregular_action_memos_become_complete_without_changing_actions():
    assert sentence_from_memo('나는 기록을 고침','자기소개서')=='나는 기록을 고쳤다.'
    assert sentence_from_memo('나는 번호를 담당자에게 알림','자기소개서')=='나는 번호를 담당자에게 알렸다.'
    assert sentence_from_memo('친구가 생각남','자유 글쓰기')=='친구가 생각났다.'
    assert sentence_from_memo('담당자는 기록을 가져와야 함','발표문')=='담당자는 기록을 가져와야 한다.'
    assert sentence_from_memo('예정일을 실제로 적으면 안 됨','발표문')=='예정일을 실제로 적으면 안 된다.'


def test_storage_verbs_and_storage_nouns_remain_distinct():
    assert sentence_from_memo('자료는 보내지 않고 그대로 보관함','자유 글쓰기')=='자료는 보내지 않고 그대로 보관했다.'
    assert sentence_from_memo('문 옆에 사물함','자유 글쓰기')=='문 옆에 사물함'
    assert sentence_from_memo('도구는 보관함','자유 글쓰기')=='도구는 보관함'
    req=SimpleNamespace(document_type='free_writing',topic='물건',facts=['문 옆에 사물함'],target_chars=150,tone='기본')
    _,values=profile_messages(req)
    assert '사물했다' not in values[-1]['content']
    assert '문 옆에 사물함' in values[-1]['content']


def test_cover_letter_all_first_person_conflict_is_removed():
    req=SimpleNamespace(document_type='cover_letter',topic='확인 범위',
        facts=['나는 앞쪽10개만 확인함','동료는 나머지20개를 내일 확인할 계획임'],target_chars=150,tone='기본')
    _,values=profile_messages(req)
    assert '모든 문장을 일인칭' not in values[-1]['content']
    assert '동료는 나머지20개를 내일 확인할 계획이다.' in values[-1]['content']
    assert '다른 사람의 행동과 계획은 그 사람을 주어로' in values[-1]['content']


def test_free_background_and_quoted_words_are_not_dropped_or_inflected():
    req=SimpleNamespace(document_type='free_writing',topic='제목에만있는행동',
        facts=['가상 장면: 낯선 시장의 향신료','관찰한 장면: 종이에 “고침”이라고 적음'],target_chars=150,tone='기본')
    _,values=profile_messages(req)
    text=values[-1]['content']
    assert '낯선 시장의 향신료' in text and '“고침”' in text
    assert '제목에만있는행동' not in text
