"""Quota and payment regressions: in-memory SQLite, mocked AI and payments."""
import json
from datetime import date
from unittest.mock import Mock

import pytest
import requests
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError

from test_qwen_features import api, document, feedback_payload, reply
import ai_usage
import database
import models


def prepare(db, *, credits=0, used=0, role="general"):
    db.execute(update(models.User).where(models.User.user_id == 1)
               .values(ai_credits=credits, role=role).execution_options(synchronize_session=False))
    if used:
        db.add(ai_usage.AiDailyUsage(user_id=1, usage_date=ai_usage.today(), used=used))
    db.commit()


def status(client):
    response = client.get("/api/ai-usage/today")
    assert response.status_code == 200, response.text
    return response.json()


def test_three_free_uses_then_paid_uses_then_block(api):
    client, db, post = api
    prepare(db, credits=2)
    doc = document(client)
    reply(post, "확인한 내용을 바탕으로 작성한 초안입니다.", personalized=False)
    assert status(client)["remaining"] == 3
    for remaining, credits in [(2, 2), (1, 2), (0, 2), (0, 1), (0, 0)]:
        response = client.post(f"/api/documents/{doc['id']}/draft-ai")
        assert response.status_code == 200, response.text
        usage = response.json()["usage"]
        assert (usage["remaining"], usage["credits"]) == (remaining, credits)
        assert status(client) == usage
    response = client.post(f"/api/documents/{doc['id']}/draft-ai")
    assert response.status_code == 402
    assert post.call_count == 5
    assert status(client)["can_use"] is False


@pytest.mark.parametrize("route", ["draft-ai", "draft-common-ai", "draft-personal-ai"])
def test_every_draft_route_accepts_paid_credits_after_free_uses(api, route):
    client, db, post = api
    prepare(db, credits=1, used=3)
    doc = document(client)
    reply(post, "제공된 자료로 작성한 초안입니다.", personalized=True)
    response = client.post(f"/api/documents/{doc['id']}/{route}")
    assert response.status_code == 200, response.text
    assert response.json()["usage"]["credits"] == 0
    assert status(client)["used"] == 3


def test_custom_genre_also_charges_paid_credit(api):
    client, db, post = api
    prepare(db, credits=1, used=3)
    doc = client.post("/api/documents", json={"title": "내 감상", "document_type": "독후감"}).json()
    client.post("/api/thoughts", json={"document_id": doc["id"], "content": "책을 읽고 확인한 사실을 기록했다."})
    reply(post, "책에서 확인한 내용을 기록했다.")
    response = client.post(f"/api/documents/{doc['id']}/draft-ai")
    assert response.status_code == 200, response.text
    assert response.json()["usage"]["credits"] == 0


def test_feedback_and_drafts_share_free_and_paid_counts(api):
    client, db, post = api
    prepare(db, credits=1, used=2)
    doc = document(client)
    draft = client.post("/api/drafts", json={"document_id": doc["id"], "content": "안내판을 확인했다."}).json()
    reply(post, json.dumps(feedback_payload(), ensure_ascii=False))
    response = client.post(f"/api/drafts/{draft['id']}/feedback-ai")
    assert response.status_code == 200, response.text
    assert response.json()["usage"]["remaining"] == 0
    assert response.json()["usage"]["credits"] == 1
    reply(post, "담당자는 안내판을 확인했다.")
    assert client.post(f"/api/documents/{doc['id']}/draft-ai").json()["usage"]["credits"] == 0
    assert db.query(models.AIFeedback).count() == 1


@pytest.mark.parametrize("used", [0, 3])
@pytest.mark.parametrize("failure", ["timeout", "unavailable", "invalid", "personal_not_applied"])
def test_failed_generation_never_spends_free_or_paid_uses(api, used, failure):
    client, db, post = api
    prepare(db, credits=1, used=used)
    doc = document(client)
    before = status(client)
    route = "draft-ai"
    if failure == "timeout":
        post.side_effect = requests.Timeout()
    elif failure == "unavailable":
        post.return_value = Mock(status_code=503)
    elif failure == "invalid":
        reply(post, "")
    else:
        reply(post, "잘못된 개인화 응답", personalized=False)
        route = "draft-personal-ai"
    assert client.post(f"/api/documents/{doc['id']}/{route}").status_code in (502, 503, 504)
    assert status(client) == before


def test_invalid_feedback_never_charges_or_saves(api):
    client, db, post = api
    prepare(db, credits=1, used=3)
    doc = document(client)
    draft = client.post("/api/drafts", json={"document_id": doc["id"], "content": "안내판을 확인했다."}).json()
    reply(post, json.dumps(feedback_payload("원문에 없는 구절"), ensure_ascii=False))
    assert client.post(f"/api/drafts/{draft['id']}/feedback-ai").status_code == 502
    assert status(client)["credits"] == 1
    assert db.query(models.AIFeedback).count() == 0


@pytest.mark.parametrize("feedback", [False, True])
def test_failed_commit_rolls_back_result_and_charge(api, monkeypatch, feedback):
    client, db, post = api
    prepare(db, credits=1, used=3)
    doc = document(client)
    route = f"/api/documents/{doc['id']}/draft-ai"
    if feedback:
        draft = client.post("/api/drafts", json={"document_id": doc["id"], "content": "안내판을 확인했다."}).json()
        route = f"/api/drafts/{draft['id']}/feedback-ai"
        reply(post, json.dumps(feedback_payload(), ensure_ascii=False))
    else:
        reply(post, "안내판을 확인했다.")
    session_class = type(db)
    original_commit = session_class.commit

    def failing_commit(session):
        if post.call_count:
            raise SQLAlchemyError("test-only commit failure")
        original_commit(session)

    monkeypatch.setattr(session_class, "commit", failing_commit)
    with pytest.raises(SQLAlchemyError):
        client.post(route)
    assert status(client)["credits"] == 1
    assert db.query(models.AIFeedback).count() == 0


def test_next_korean_day_restores_free_uses_without_resetting_credits(api, monkeypatch):
    client, db, post = api
    monkeypatch.setattr(ai_usage, "today", lambda: date(2026, 11, 18))
    prepare(db, credits=2, used=3)
    assert status(client)["remaining"] == 0
    monkeypatch.setattr(ai_usage, "today", lambda: date(2026, 11, 19))
    assert status(client)["remaining"] == 3
    doc = document(client)
    reply(post, "새 날짜에 작성한 초안입니다.")
    result = client.post(f"/api/documents/{doc['id']}/draft-ai").json()["usage"]
    assert (result["remaining"], result["credits"]) == (2, 2)


def test_admin_is_unlimited_without_spending_credits(api):
    client, db, post = api
    prepare(db, credits=0, used=3, role="admin")
    doc = document(client)
    reply(post, "관리자 점검용 초안입니다.")
    result = client.post(f"/api/documents/{doc['id']}/draft-ai")
    assert result.status_code == 200, result.text
    assert result.json()["usage"]["unlimited"] is True
    assert result.json()["usage"]["credits"] == 0
    assert status(client)["used"] == 3


def test_late_competing_request_cannot_spend_last_credit_twice(api):
    client, db, post = api
    prepare(db, credits=1, used=3)
    doc = document(client)

    def generate_after_other_request_spends_credit(*args, **kwargs):
        with database.SessionLocal() as competing:
            ai_usage.consume(competing, 1)
            competing.commit()
        response = Mock(status_code=200)
        response.json.return_value = {"content": "초안입니다."}
        return response

    post.side_effect = generate_after_other_request_spends_credit
    response = client.post(f"/api/documents/{doc['id']}/draft-ai")
    assert response.status_code == 402
    assert status(client)["credits"] == 0
    assert status(client)["used"] == 3


def test_successful_top_up_reenables_usage_and_paid_use_decrements(api, monkeypatch):
    client, db, post = api
    prepare(db, credits=0, used=3)
    assert status(client)["can_use"] is False
    monkeypatch.setenv("TOSS_SECRET_KEY", "test-only-key")
    post.return_value = Mock(status_code=200)
    response = client.post("/api/payments/confirm", headers={"Authorization": "Bearer test"},
                           json={"paymentKey": "test-key", "orderId": "test-order", "amount": 1000})
    assert response.status_code == 200, response.text
    assert status(client)["credits"] == 5
    assert status(client)["can_use"] is True
    doc = document(client)
    reply(post, "충전한 이용권으로 작성한 초안입니다.")
    response = client.post(f"/api/documents/{doc['id']}/draft-ai")
    assert response.status_code == 200
    assert response.json()["usage"]["credits"] == 4


def test_top_up_does_not_overwrite_simultaneous_credit_spending(api):
    client, db, post = api
    prepare(db, credits=2)
    user = db.get(models.User, 1)
    assert user.ai_credits == 2

    def confirm_after_concurrent_spend(*args, **kwargs):
        with database.SessionLocal() as other:
            other.execute(update(models.User).where(models.User.user_id == 1).values(ai_credits=1))
            other.commit()
        return Mock(status_code=200)

    post.side_effect = confirm_after_concurrent_spend
    response = client.post("/api/payments/confirm", headers={"Authorization": "Bearer test"},
                           json={"paymentKey": "test-key", "orderId": "test-order", "amount": 1000})
    assert response.status_code == 200, response.text
    assert status(client)["credits"] == 6


def test_new_accounts_do_not_receive_duplicate_free_credits(api):
    client, db, post = api
    assert db.get(models.User, 1).ai_credits == 0
    assert status(client)["remaining"] == 3


def test_usage_is_per_account_and_rejects_unauthenticated_requests(api):
    client, db, post = api
    prepare(db, credits=0, used=3)
    assert status(client)["can_use"] is False
    assert ai_usage.get_usage(db, 2)["remaining"] == 3
    from main import app
    app.dependency_overrides.clear()
    assert client.get("/api/ai-usage/today").status_code == 401
