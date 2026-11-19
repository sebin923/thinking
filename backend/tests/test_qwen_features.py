"""Run: .venv-review/Scripts/python -m pytest backend/tests -q

Use an isolated SQLite database and a fake Qwen HTTP response; never load GPU weights.
"""
import json
import os
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest
import requests
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "llm_training"))
for key, value in {"DB_HOST": "localhost", "DB_PORT": "5432", "DB_NAME": "test",
                   "DB_USER": "test", "DB_PASSWORD": "test", "JWT_SECRET_KEY": "test-only-secret-key-for-isolated-tests"}.items():
    os.environ[key] = value

import database

database.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
database.SessionLocal = sessionmaker(bind=database.engine)

import models
from main import app
from routers.auth import get_current_user
from learning_progress import LearningProgress
import qwen_ai
import common_llm


@pytest.fixture
def api(monkeypatch):
    database.Base.metadata.drop_all(database.engine)
    database.Base.metadata.create_all(database.engine)
    db = database.SessionLocal()
    user = models.User(user_id=1, email="test@example.com", login_id="tester", name="테스트",
                       phone="01000000000", password_hash="unused", role="general")
    other = models.User(user_id=2, email="other@example.com", login_id="other", name="다른 회원",
                        phone="01000000001", password_hash="unused", role="general")
    db.add_all([user, other])
    db.commit()
    app.dependency_overrides[get_current_user] = lambda: user
    monkeypatch.setenv("THINKING_LLM_TOKEN", "test-qwen-token")
    monkeypatch.setenv("COMMON_LLM_URL", "http://qwen.test:8001/")
    post = Mock()
    monkeypatch.setattr(qwen_ai.requests, "post", post)
    with TestClient(app) as client:
        yield client, db, post
    app.dependency_overrides.clear()
    db.close()


def reply(post, content, **extra):
    response = Mock(status_code=200)
    response.json.return_value = {"content": content, **extra}
    post.return_value = response


def document(client, text="자료실 안내판이 책장 위치와 달라 담당자에게 알렸다."):
    doc = client.post("/api/documents", json={"title": "안내판 점검", "document_type": "보고서"}).json()
    assert "id" in doc
    assert client.post("/api/thoughts", json={"document_id": doc["id"], "content": text}).status_code == 200
    return doc


def feedback_payload(quote="안내판을 확인했다."):
    return {"overall_feedback": "핵심 사실이 잘 드러납니다.", "highlights": [{
        "original_text": quote, "type": "표현", "reason": "행동을 더 명확히 표현할 수 있어요.",
        "suggestion": "문장을 간결하게 다듬어 보세요.", "revised_text": "안내판의 위치를 점검했다.",
    }]}


def score_payload(on_task=True, score=9):
    return {"criteria": {f"criterion_{i}": {"score": score, "comment": "글에 확인한 사실이 나타납니다."} for i in range(1, 4)},
            "on_task": on_task, "overall_feedback": "주어진 사실을 중심으로 잘 썼어요.", "next_step": "확인 결과를 먼저 써 보세요."}


def score_request():
    return {"unit_id": "report-1", "type_label": "보고서", "unit_title": "핵심부터 쓰기",
            "task": "결과부터 제시하세요.", "rules": ["확인한 결과를 먼저 쓴다."],
            "text": "자료실 안내판과 실제 책장 위치가 다른 점을 확인하여 담당자에게 그 차이를 기록해 전달했습니다.",
            "practice": {"kind": "data", "topic": "새 추천 주제", "facts": ["안내판과 책장 위치가 다르다."],
                         "source": "연습 자료", "url": "https://example.com/source", "example": "비교할 원문입니다."}}


def unlock(db):
    db.add(LearningProgress(user_id=1, revision=0, legacy_imported=0,
                            payload={"units": {"report-1": {"passed": True}}, "wrong": {}}))
    db.commit()


def test_preferences_saved_and_used_by_default_qwen_draft(api):
    client, db, post = api
    prefs = {"preferred_tone": "confident", "sentence_length": "short", "feedback_style": "brief", "ai_assistance": "guided"}
    assert client.put("/api/writing/preferences", json=prefs).status_code == 200
    assert client.get("/api/writing/preferences").json()["preferred_tone"] == "confident"
    doc = document(client)
    reply(post, "담당자는 안내판과 책장 위치의 차이를 확인했습니다.", personalized=False)
    response = client.post(f"/api/documents/{doc['id']}/draft-ai")
    assert response.status_code == 200, response.text
    args, kwargs = post.call_args
    assert args == ("http://qwen.test:8001/draft",)
    assert kwargs["json"]["mode"] == "common"
    assert kwargs["json"]["user_preferences"] == prefs
    assert kwargs["headers"] == {"X-LLM-Token": "test-qwen-token"}
    assert kwargs["json"]["user_id"] == 1


def test_personal_draft_requires_applied_adapter(api):
    client, db, post = api
    doc = document(client)
    reply(post, "개인화 초안", personalized=False)
    assert client.post(f"/api/documents/{doc['id']}/draft-personal-ai").status_code == 502
    reply(post, "개인화 초안", personalized=True)
    response = client.post(f"/api/documents/{doc['id']}/draft-personal-ai")
    assert response.status_code == 200
    assert post.call_args.kwargs["json"]["mode"] == "personal"


def test_sentence_rhythm_does_not_change_total_document_target(api):
    client,db,post=api
    doc=document(client)
    targets=[]
    for length in ('short','normal','long'):
        client.put('/api/writing/preferences',json={'sentence_length':length})
        reply(post,'확인한 사실만 작성했습니다.',personalized=False)
        assert client.post(f'/api/documents/{doc["id"]}/draft-ai').status_code==200
        targets.append(post.call_args.kwargs['json']['target_chars'])
    assert targets==[350,350,350]


def test_feedback_handles_exact_repetition_without_inventing_other_problems(api):
    client,db,post=api
    text='저는 신청서 12장을 확인했습니다. 저는 신청서 12장을 확인했습니다. 원본은 아직 수정하지 않았습니다.'
    doc=document(client)
    draft=client.post('/api/drafts',json={'document_id':doc['id'],'content':text}).json()
    client.put('/api/writing/preferences',json={'ai_assistance':'guided','feedback_style':'brief'})
    guided=client.post(f'/api/drafts/{draft["id"]}/feedback-ai').json()['feedback']
    assert len(guided['highlights'])==1
    assert guided['highlights'][0]['revised_text']==''
    assert guided['highlights'][0]['original_text'] in text
    client.put('/api/writing/preferences',json={'ai_assistance':'draft','feedback_style':'detailed'})
    detailed=client.post(f'/api/drafts/{draft["id"]}/feedback-ai').json()['feedback']
    assert detailed['highlights'][0]['revised_text']=='저는 신청서 12장을 확인했습니다.'
    post.assert_not_called()


@pytest.mark.parametrize('quote,revised',[
    ('원본은 아직 수정하지 않았습니다.','원본을 수정했습니다.'),
    ('신청서 12장을 확인했습니다.','신청서 15장을 확인했습니다.'),
    ('신청서 12장을 확인했습니다.','신청서 12개를 확인했습니다.'),
    ('원본을 수정했습니다.','원본을 수정하지 않았습니다.'),
    ('동료가 내일 확인할 계획입니다.','제가 오늘 확인했습니다.'),
    ('답장이 오면 확인합니다.','답장과 관계없이 확인합니다.'),
])
def test_feedback_rejects_rewrites_that_drop_protected_facts(quote,revised):
    payload=feedback_payload(quote)
    payload['highlights'][0]['revised_text']=revised
    actual=qwen_ai._feedback_from_content(json.dumps(payload,ensure_ascii=False),quote)
    assert actual['highlights']==[]


def test_feedback_does_not_present_praise_or_optional_unit_spacing_as_a_problem():
    quote='참가 신청서 12장을 시간표와 비교했습니다.'
    payload=feedback_payload(quote)
    payload['highlights'][0]['revised_text']='참가 신청서 12 장을 시간표와 비교했습니다.'
    assert qwen_ai._feedback_from_content(json.dumps(payload,ensure_ascii=False),quote)['highlights']==[]
    payload['highlights'][0].update(reason='구체적인 설명이 강점입니다.',suggestion='구체적인 설명이 강점입니다.',revised_text='신청서 12장을 시간표에 대조했습니다.')
    assert qwen_ai._feedback_from_content(json.dumps(payload,ensure_ascii=False),quote)['highlights']==[]


def test_feedback_retains_real_korean_word_spacing_correction():
    quote='안내판을 확인할수 있습니다.'
    payload=feedback_payload(quote)
    payload['highlights'][0]['revised_text']='안내판을 확인할 수 있습니다.'
    assert qwen_ai._feedback_from_content(json.dumps(payload,ensure_ascii=False),quote)['highlights'][0]['revised_text']=='안내판을 확인할 수 있습니다.'


@pytest.mark.parametrize('assistance', ['guided','draft'])
def test_clear_spacing_feedback_keeps_negation_and_mode(monkeypatch, assistance):
    monkeypatch.setattr(qwen_ai,'call_qwen',lambda *a,**k:pytest.fail('A verified spacing correction needs no speculative rewrite'))
    text='저는 명단을 확인할수 없었습니다. 원본은 아직 수정하지 않았습니다.'
    value=qwen_ai.create_feedback_with_ai(text,'자기소개서',{'ai_assistance':assistance})
    item=value['highlights'][0]
    assert item['original_text']=='확인할수'
    assert item['revised_text']==('' if assistance=='guided' else '확인할 수')
    assert not qwen_ai._spacing_feedback('철수는 명단을 확인했습니다.',{})


def test_feedback_cannot_undo_an_explicit_narrator():
    quote='저는 확인된 표기를 별도 메모에 적었습니다.'
    payload=feedback_payload(quote)
    payload['highlights'][0]['revised_text']='확인된 표기는 별도 메모에 적었습니다.'
    value=qwen_ai._feedback_from_content(json.dumps(payload,ensure_ascii=False),quote)
    assert value['highlights']==[] and '행동 주체와 사실' in value['overall_feedback']


def test_custom_document_type_also_uses_qwen(api):
    client, db, post = api
    doc = client.post("/api/documents", json={"title": "내 감상", "document_type": "독후감"}).json()
    client.post("/api/thoughts", json={"document_id": doc["id"], "content": "책을 읽고 기록과 확인의 차이를 생각했다."})
    reply(post, "책을 읽으며 기록한 내용과 직접 확인한 내용의 차이를 생각했다.")
    response = client.post(f"/api/documents/{doc['id']}/draft-ai")
    assert response.status_code == 200, response.text
    assert post.call_args.args == ("http://qwen.test:8001/chat",)
    assert "독후감" in post.call_args.kwargs["json"]["messages"][1]["content"]


@pytest.mark.parametrize("status, expected", [(401, 503), (503, 503), (422, 422), (404, 404)])
def test_qwen_status_is_visible_without_other_provider_fallback(api, status, expected):
    client, db, post = api
    doc = document(client)
    post.return_value = Mock(status_code=status)
    response = client.post(f"/api/documents/{doc['id']}/draft-personal-ai")
    assert response.status_code == expected
    assert post.call_count == 1


def test_missing_token_does_not_call_any_provider(api, monkeypatch):
    client, db, post = api
    doc = document(client)
    monkeypatch.delenv("THINKING_LLM_TOKEN")
    assert client.post(f"/api/documents/{doc['id']}/draft-ai").status_code == 503
    post.assert_not_called()


def test_qwen_timeout(api):
    client, db, post = api
    doc = document(client)
    post.side_effect = requests.Timeout()
    assert client.post(f"/api/documents/{doc['id']}/draft-ai").status_code == 504


def test_feedback_uses_chat_schema_and_guided_preference(api):
    client, db, post = api
    client.put("/api/writing/preferences", json={"ai_assistance": "guided"})
    doc = document(client)
    draft = client.post("/api/drafts", json={"document_id": doc["id"], "content": "안내판을 확인했다."}).json()
    reply(post, json.dumps(feedback_payload(), ensure_ascii=False))
    response = client.post(f"/api/drafts/{draft['id']}/feedback-ai")
    assert response.status_code == 200, response.text
    assert response.json()["feedback"]["highlights"][0]["revised_text"] == ""
    assert post.call_args.args == ("http://qwen.test:8001/chat",)
    assert post.call_args.kwargs["json"]["schema_spec"]["required"] == ["overall_feedback", "highlights"]
    assert "힌트 중심 설정" in post.call_args.kwargs["json"]["messages"][0]["content"]
    assert db.query(models.AIFeedback).count() == 1


def test_feedback_rejects_invented_quote_without_saving(api):
    client, db, post = api
    doc = document(client)
    draft = client.post("/api/drafts", json={"document_id": doc["id"], "content": "안내판을 확인했다."}).json()
    reply(post, json.dumps(feedback_payload("없는 경험을 지어냈다."), ensure_ascii=False))
    assert client.post(f"/api/drafts/{draft['id']}/feedback-ai").status_code == 502
    assert db.query(models.AIFeedback).count() == 0


def test_other_users_document_is_never_sent_to_qwen(api):
    client, db, post = api
    doc = models.Document(user_id=2, document_type="보고서", title="다른 회원의 문서")
    db.add(doc)
    db.commit()
    assert client.post(f"/api/documents/{doc.id}/draft-ai").status_code == 404
    post.assert_not_called()


def test_score_saves_exact_recommended_material_and_90_point_completion(api):
    client, db, post = api
    unlock(db)
    reply(post, json.dumps(score_payload(), ensure_ascii=False))
    request = score_request()
    response = client.post("/api/learn/writing-score", json=request)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["score"] == 90 and data["passed"] is True and data["progress_saved"] is True
    saved = data["saved_progress"]["progress"]["units"]["report-1"]
    assert saved["completed"] is True
    assert saved["writing"]["practice"]["topic"] == "새 추천 주제"
    prompt = post.call_args.kwargs["json"]["messages"][1]["content"]
    assert "새 추천 주제" in prompt
    assert "비교할 원문입니다." not in prompt


def test_off_task_score_is_capped_at_50(api):
    client, db, post = api
    unlock(db)
    reply(post, json.dumps(score_payload(on_task=False, score=10), ensure_ascii=False))
    data = client.post("/api/learn/writing-score", json=score_request()).json()
    assert data["score"] == 50 and data["passed"] is False


def test_score_requires_quiz_pass_before_qwen_call(api):
    client, db, post = api
    assert client.post("/api/learn/writing-score", json=score_request()).status_code == 403
    post.assert_not_called()


@pytest.mark.parametrize("bad_score", [True, 11, -1, 8.5])
def test_invalid_model_scores_are_rejected(api, bad_score):
    client, db, post = api
    unlock(db)
    raw = score_payload()
    raw["criteria"]["criterion_1"]["score"] = bad_score
    reply(post, json.dumps(raw, ensure_ascii=False))
    assert client.post("/api/learn/writing-score", json=score_request()).status_code == 502
    assert "writing" not in db.query(LearningProgress).filter_by(user_id=1).one().payload["units"]["report-1"]


def recommendation_request(type_label="보고서"):
    return {"unit_id": "report-1", "type_label": type_label, "unit_title": "핵심부터 쓰기",
            "task": "경험의 결과를 먼저 쓴다.", "rules": ["결과를 먼저 쓴다."], "current_topic": "이전 주제",
            "candidates": [{"id": "report-2", "title": "새 주제", "summary": "기존 자료의 사실 요약"}]}


def test_recommendation_selects_only_provided_topic(api):
    client, db, post = api
    reply(post, json.dumps({"candidate_id": "report-2", "reason": "결과부터 쓰는 연습에 적합해요."}, ensure_ascii=False))
    response = client.post("/api/learn/practice-recommendation", json=recommendation_request())
    assert response.status_code == 200, response.text
    assert response.json()["candidate_id"] == "report-2"
    schema = post.call_args.kwargs["json"]["schema_spec"]
    assert schema["properties"]["candidate_id"]["enum"] == ["report-2"]
    reply(post, json.dumps({"candidate_id": "invented-id", "reason": "없는 자료"}, ensure_ascii=False))
    assert client.post("/api/learn/practice-recommendation", json=recommendation_request()).status_code == 502


def test_cover_letter_recommendation_is_a_question(api):
    client, db, post = api
    question = "실제로 겪은 문제를 해결한 경험에서 본인이 한 행동과 확인한 결과를 써 보세요."
    reply(post, json.dumps({"question": question, "reason": "행동과 결과를 연결하는 연습에 좋아요."}, ensure_ascii=False))
    request = recommendation_request("자기소개서")
    request["candidates"] = []
    response = client.post("/api/learn/practice-recommendation", json=request)
    assert response.status_code == 200 and response.json()["question"] == question


def test_cover_letter_question_does_not_treat_missing_reference_facts_as_fabrication(api):
    client,db,post=api
    unlock(db)
    request=score_request()
    request.update(type_label='자기소개서',practice={'kind':'question','question':'본인이 한 행동과 경험을 설명해 보세요.'})
    reply(post,json.dumps(score_payload(),ensure_ascii=False))
    response=client.post('/api/learn/writing-score',json=request)
    assert response.status_code==200,response.text
    messages=post.call_args.kwargs['json']['messages']
    assert '참고 자료에 없다는 이유로 지어냈다고 표현하거나 감점하지 마세요' in messages[0]['content']
    assert '연습 자료에 없는 사실·수치·경험을 지어내지 않았다' not in messages[1]['content']


def test_recommendation_preferences_do_not_ask_for_rewrites_or_fictional_examples(api):
    client,db,post=api
    client.put('/api/writing/preferences',json={'ai_assistance':'draft','feedback_style':'detailed'})
    reply(post,json.dumps({'question':'본인이 실제로 맡은 역할과 행동을 설명해 보세요.','reason':'행동 주체를 구분하는 연습입니다.'},ensure_ascii=False))
    response=client.post('/api/learn/practice-recommendation',json=recommendation_request('자기소개서'))
    assert response.status_code==200,response.text
    system=post.call_args.kwargs['json']['messages'][0]['content']
    assert "'본인이 실제로'로 시작" in system
    assert '구체적인 수정 문장 예시 제공' not in system


def test_common_server_receives_distinct_confident_tone_and_sentence_preference():
    request = common_llm.DraftRequest(document_type="보고서", topic="안내판 점검", facts=["위치가 다르다."],
                                     user_preferences={"preferred_tone": "confident", "sentence_length": "short"})
    kind, messages = common_llm.messages_for(request)
    assert kind == "보고서"
    assert "자신감 있고 명확하게" in messages[0]["content"]
    assert "문장을 짧고 간결하게" in messages[0]["content"]
    assert "위치가 다르다." in messages[-1]["content"]


def test_no_active_clova_module_or_import():
    assert not (ROOT / "backend" / "clova.py").exists()
    for path in (ROOT / "backend").rglob("*.py"):
        if "tests" not in path.parts:
            assert "from clova import" not in path.read_text(encoding="utf-8-sig")
