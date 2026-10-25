
import json
from pathlib import Path

# 학습 후보 데이터 파일
input_path = Path("training_candidates_10.json")

with open(input_path, "r", encoding="utf-8") as f:
    data = json.load(f)

user_id = int(data["user_id"])
candidates = data["training_candidates"]

approved_records = []
demo_records = []
review_records = []

system_instruction = (
    "너는 생각한줄의 글쓰기 전문 AI야. "
    "사용자가 제공한 사실만 사용하고 내용을 지어내지 마. "
    "초안 작성은 자연스러운 본문만 출력해. "
    "피드백 요청에는 문제 유형, 설명, 수정 방향을 알려줘."
)

for candidate in candidates:
    print("\n" + "=" * 50)
    print("문서:", candidate["document_id"])
    print("글 유형:", candidate["document_type"])

    print("\n[수정 전]")
    print(candidate["original_text"])

    print("\n[AI 피드백]")
    print(json.dumps(
        candidate["feedback"],
        ensure_ascii=False,
        indent=2
    ))

    print("\n[수정 후]")
    print(candidate["revised_text"])

    print("\n승인 여부를 선택하세요.")
    print("y: 사실 확인 완료, 학습용 승인")
    print("d: 가상 시연 데이터로 승인")
    print("n: 승인하지 않음")

    choice = input("선택 (y/d/n): ").strip().lower()

    status = {
        "y": "학습 승인",
        "d": "시연용",
        "n": "승인 거절"
    }.get(choice, "승인 거절")

    review_records.append({
        "user_id": user_id,
        "document_id": candidate["document_id"],
        "before_draft_id": candidate["before_draft_id"],
        "after_draft_id": candidate["after_draft_id"],
        "review_status": status
    })

    if choice not in ("y", "d"):
        continue

    # Qwen 학습용 대화 데이터
    prompt_text = (
        "작업: AI 피드백 반영 수정\n"
        f"글 유형: {candidate['document_type']}\n\n"
        f"[수정 전 글]\n{candidate['original_text']}\n\n"
        "[이전 AI 피드백]\n"
        + json.dumps(
            candidate["feedback"],
            ensure_ascii=False
        )
        + "\n\n피드백을 참고하여 제공된 사실만으로 "
          "글을 수정하세요."
    )

    record = {
        "prompt": [
            {
                "role": "system",
                "content": system_instruction
            },
            {
                "role": "user",
                "content": prompt_text
            }
        ],
        "completion": [
            {
                "role": "assistant",
                "content": candidate["revised_text"]
            }
        ]
    }

    if choice == "y":
        approved_records.append(record)
    else:
        demo_records.append(record)

# 결과 저장 폴더
output_dir = Path("training_data")
output_dir.mkdir(exist_ok=True)

def save_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(
                json.dumps(record, ensure_ascii=False) + "\n"
            )

# 실제 학습 승인 데이터
approved_path = output_dir / f"user_{user_id}_approved.jsonl"
save_jsonl(approved_path, approved_records)

# 가상 시연 데이터
demo_path = output_dir / f"user_{user_id}_demo.jsonl"
save_jsonl(demo_path, demo_records)

# 검토 결과 기록
review_path = output_dir / f"user_{user_id}_reviews.json"

with open(review_path, "w", encoding="utf-8") as f:
    json.dump(
        review_records,
        f,
        ensure_ascii=False,
        indent=2
    )

print("\n========== 완료 ==========")
print("실제 학습 승인:", len(approved_records), "건")
print("시연용 데이터:", len(demo_records), "건")
print("학습 승인 파일:", approved_path)
print("시연용 파일:", demo_path)
print("검토 기록:", review_path)
