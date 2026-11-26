"""Retrieve grounded writing exercises using explicit or consented interests.

This is profile/content based retrieval, not LoRA training or AI-authored source
material. Neither private text nor another account's records leave the server.
"""
import json
import re

from fastapi import HTTPException
from sqlalchemy import desc

from practice_bank import materials
from recommendation_profile import RecommendationHistory, RecommendationProfile
from training_models import TrainingCandidate


DOMAIN_TERMS = {
    "cs": ("컴퓨터공학", "컴공", "소프트웨어", "정보통신", "정보보안", "computer science"),
    "web": ("웹개발", "웹 개발", "프론트엔드", "백엔드", "리액트", "react", "fastapi", "javascript"),
    "database": ("데이터베이스", "database", "sql", "인덱스"),
    "ai": ("인공지능", "머신러닝", "딥러닝", "llm", "ai"),
    "security": ("보안", "개인정보", "인증"),
    "data": ("데이터분석", "데이터 분석", "통계", "설문"),
    "design": ("디자인", "시각디자인", "접근성", "포스터", "ux", "ui"),
    "business": ("경영", "경제", "마케팅", "예산", "회계", "카페"),
    "environment": ("환경", "분리배출", "재활용"),
    "community": ("봉사", "학생회", "지역사회", "사회복지"),
    "study": ("학습", "공부", "교육", "스터디"),
    "collaboration": ("협업", "팀워크", "팀프로젝트", "팀 프로젝트"),
}


def domains_in(value):
    value = value.casefold()
    found = set()
    for domain, terms in DOMAIN_TERMS.items():
        for term in terms:
            # ASCII words such as AI/UI must not match 'mail' or 'build'.
            pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])" if term.isascii() else re.escape(term)
            if re.search(pattern, value):
                found.add(domain)
                break
    return found


def personal_context(db, user_id):
    profile = db.get(RecommendationProfile, user_id)
    explicit = " ".join([profile.major or "", *(profile.interests or [])]) if profile else ""
    domains = domains_in(explicit)
    sources = ["profile"] if domains else []
    if not profile or profile.use_training_data:
        # Only this account's reviewed, consented, non-synthetic examples.
        records = db.query(TrainingCandidate).filter_by(
            user_id=user_id, status="approved", consent=True, synthetic=False,
        ).order_by(desc(TrainingCandidate.id)).limit(30).all()
        learned = set()
        for row in records:
            learned.update(domains_in(json.dumps(row.source, ensure_ascii=False)[:6000]
                                      + " " + row.answer[:3000] + " " + (row.training_context or "")[:3000]))
        if learned:
            domains.update(learned)
            sources.append("approved_writing")
    return domains, sources


def recommendation_reason(sources, personalized):
    if personalized:
        basis = "저장한 전공·관심사" if "profile" in sources else "학습에 동의하고 검토된 내 글의 관심 분야"
    else:
        basis = "여러 이용자가 연습할 수 있도록 준비한 공통 주제"
    return basis + "를 바탕으로 골랐어요. 현재 단원의 과제와 기준에 맞춰 써 보세요."


def recent_history(db, user_id, unit_id):
    return db.query(RecommendationHistory).filter_by(user_id=user_id, unit_id=unit_id).order_by(
        desc(RecommendationHistory.id)).limit(60).all()


def remember(db, user_id, unit_id, practice_id, history):
    db.add(RecommendationHistory(user_id=user_id, unit_id=unit_id, practice_id=practice_id))
    # 계정·단원별 최근 40개만 유지하며 진도·사용량·학습 동의는 바꾸지 않는다.
    for row in history[39:]:
        db.delete(row)
    db.commit()


def recommend_compatible(data, user_id, db):
    """기존 프론트의 응답 형식을 유지하면서 새 개인화를 자동 적용한다.

    보고서·발표문은 브라우저가 실제로 표시할 수 있는 후보 ID만 반환한다.
    맞는 관심 분야가 없으면 기존 AI 추천으로 넘겨 개인화라고 과장하지 않는다.
    """
    domains, sources = personal_context(db, user_id)
    if not domains:
        return None
    if data.type_label == "자기소개서":
        result = recommend(data, user_id, db)
        return {"question": result["question"], "reason": result["reason"]}

    current = data.current_topic.strip()
    matches = []
    for candidate in data.candidates:
        candidate_domains = domains_in(candidate.title + " " + candidate.summary)
        overlap = domains.intersection(candidate_domains)
        if candidate.title.strip() != current and overlap:
            matches.append((candidate, candidate_domains, overlap))
    if not matches:
        return None

    history = recent_history(db, user_id, data.unit_id)
    seen = {row.practice_id: row.id for row in reversed(history)}
    unit_domains = domains_in(" ".join([data.unit_title, data.task, *data.rules]))

    def history_id(candidate):
        # 새 API의 자료 ID와 브라우저에서만 쓰는 후보 ID를 구분한다.
        return f"client:{data.type_label}:{candidate.id}"

    def rank(item):
        candidate, candidate_domains, overlap = item
        key = history_id(candidate)
        return (key in seen, seen.get(key, 0), -len(overlap),
                -len(unit_domains.intersection(candidate_domains)), candidate.id)

    selected, _, _ = min(matches, key=rank)
    remember(db, user_id, data.unit_id, history_id(selected), history)
    return {"candidate_id": selected.id, "reason": recommendation_reason(sources, True)}


def recommend(data, user_id, db):
    domains, sources = personal_context(db, user_id)
    current = data.current_topic.strip()
    pool = [item for item in materials(data.type_label)
            if (item["practice"].get("question") or item["practice"].get("topic")) != current]
    matched = [item for item in pool if domains.intersection(item["domains"])] if domains else []
    personalized = bool(matched)
    pool = matched or [item for item in pool if "general" in item["domains"]]
    if not pool:
        raise HTTPException(422, "다른 연습 자료가 없습니다.")
    history = recent_history(db, user_id, data.unit_id)
    seen = {row.practice_id: row.id for row in reversed(history)}
    unit_words = domains_in(" ".join([data.unit_title, data.task, *data.rules]))
    def rank(item):
        return (item["id"] in seen,
                seen.get(item["id"], 0),
                -len(domains.intersection(item["domains"])),
                -len(unit_words.intersection(item["domains"])), item["id"])
    selected = min(pool, key=rank)
    practice = selected["practice"]
    reason = recommendation_reason(sources, personalized)
    remember(db, user_id, data.unit_id, selected["id"], history)
    result = {"practice": practice, "reason": reason, "personalized": personalized,
              "recommendation_source": "personalized_bank" if personalized else "common_bank"}
    if practice["kind"] == "question":
        result["question"] = practice["question"]
    return result
