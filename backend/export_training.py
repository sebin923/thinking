"""생각한줄 DB에서 사용자별 글 수정 학습 후보를 검토하고 JSONL로 내보낸다.

실행 예시 (backend 폴더):
  python export_training.py --user-id 4

승인(y): 실제 사용자 작성·수정 내용으로 검증한 학습 예시
시연(d): 가상/연습 예시(실제 개인화 학습에는 사용하지 않음)
제외(n): 사용하지 않음
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

import models
from database import SessionLocal

BACKEND_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BACKEND_DIR.parent / "llm_training" / "data" / "personalized"

SYSTEM_INSTRUCTION = (
    "너는 생각한줄의 글쓰기 전문 AI야. "
    "사용자가 제공한 사실만 사용하고 내용을 지어내지 마. "
    "피드백을 참고하여 자연스럽게 글을 수정해."
)


def get_candidates(db, user_id):
    """문서 소유자, 이어지는 초안 버전, 이전 버전의 최신 피드백을 검사한다."""
    documents = (
        db.query(models.Document)
        .filter(models.Document.user_id == user_id)
        .order_by(models.Document.id.asc())
        .all()
    )
    results = []
    for document in documents:
        drafts = (
            db.query(models.Draft)
            .filter(models.Draft.document_id == document.id)
            .order_by(models.Draft.version.asc(), models.Draft.id.asc())
            .all()
        )
        for before, after in zip(drafts, drafts[1:]):
            if not before.content or not after.content:
                continue
            if before.content.strip() == after.content.strip():
                continue
            feedback = (
                db.query(models.AIFeedback)
                .filter(models.AIFeedback.draft_id == before.id)
                .order_by(models.AIFeedback.id.desc())
                .first()
            )
            if feedback is None or not isinstance(feedback.feedback_data, dict):
                continue
            if not isinstance(feedback.feedback_data.get("highlights", []), list):
                continue
            results.append({
                "document_id": document.id,
                "document_type": document.document_type,
                "title": document.title,
                "before_draft_id": before.id,
                "after_draft_id": after.id,
                "original_text": before.content,
                "feedback": feedback.feedback_data,
                "revised_text": after.content,
            })
    return results


def to_training_record(candidate):
    prompt_text = (
        "작업: AI 피드백 반영 수정\n"
        f"글 유형: {candidate['document_type']}\n\n"
        f"[수정 전 글]\n{candidate['original_text']}\n\n"
        "[이전 AI 피드백]\n"
        + json.dumps(candidate["feedback"], ensure_ascii=False)
        + "\n\n피드백을 참고하여 제공된 사실만으로 글을 수정하세요."
    )
    return {
        "prompt": [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": prompt_text},
        ],
        "completion": [
            {"role": "assistant", "content": candidate["revised_text"]}
        ],
    }


def save_jsonl(path, rows):
    with path.open("x", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description="사용자 글 수정 데이터 검토 및 추출")
    parser.add_argument("--user-id", type=int, required=True)
    args = parser.parse_args()
    if args.user_id < 1:
        parser.error("--user-id는 1 이상이어야 합니다.")

    db = SessionLocal()
    try:
        candidates = get_candidates(db, args.user_id)
    finally:
        db.close()

    print(f"사용자 {args.user_id}의 학습 후보: {len(candidates)}건")
    if not candidates:
        print("학습 후보가 없습니다. 파일은 만들지 않습니다.")
        return

    approved, demo, reviews = [], [], []
    for i, c in enumerate(candidates, 1):
        print("\n" + "=" * 60)
        print(f"[{i}/{len(candidates)}] 문서 {c['document_id']} / {c['document_type']} / {c['title']}")
        print(f"초안 ID: {c['before_draft_id']} -> {c['after_draft_id']}")
        print("\n[수정 전]\n", c["original_text"])
        print("\n[AI 피드백]\n", json.dumps(c["feedback"], ensure_ascii=False, indent=2))
        print("\n[수정 후]\n", c["revised_text"])
        while True:
            choice = input("\ny=실제 데이터 승인 / d=연습·시연용 / n=제외 : ").strip().lower()
            if choice in {"y", "d", "n"}:
                break
            print("y, d, n 중 하나를 입력하세요.")
        reviews.append({
            "user_id": args.user_id,
            "document_id": c["document_id"],
            "before_draft_id": c["before_draft_id"],
            "after_draft_id": c["after_draft_id"],
            "review_status": {"y": "학습 승인", "d": "시연용", "n": "제외"}[choice],
        })
        if choice == "y":
            approved.append(to_training_record(c))
        elif choice == "d":
            demo.append(to_training_record(c))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # 실행을 반복해도 기존 검토 결과·학습 파일을 덮어쓰지 않도록 실행별로 보관한다.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    prefix = f"user_{args.user_id}_{stamp}"
    if approved:
        path = OUTPUT_DIR / f"{prefix}_approved.jsonl"
        save_jsonl(path, approved)
        print("학습 승인 파일:", path)
        print("학습 명령: .\\.venv\\Scripts\\python.exe train_personal.py --user-id", args.user_id, "--data", str(path), "--epochs 1")
    if demo:
        path = OUTPUT_DIR / f"{prefix}_demo.jsonl"
        save_jsonl(path, demo)
        print("시연용 파일(학습 제외):", path)
    review_path = OUTPUT_DIR / f"{prefix}_reviews.json"
    with review_path.open("x", encoding="utf-8") as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)
    print("검토 기록:", review_path)
    print(f"결과: 학습 승인 {len(approved)}건 / 시연용 {len(demo)}건 / 제외 {len(candidates)-len(approved)-len(demo)}건")
    if len(approved) < 3:
        print("주의: 학습 승인 데이터가 3건 미만이므로 현재 train_personal.py로 학습할 수 없습니다.")
    elif len(approved) < 20:
        print("참고: 20건 미만으로 기능 시험은 가능하지만 개인화 품질은 보장되지 않습니다.")


if __name__ == "__main__":
    main()
