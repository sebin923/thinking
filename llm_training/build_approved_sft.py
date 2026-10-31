
import csv
import json
from pathlib import Path
from collections import Counter

BASE = Path("data/sft")
SOURCE = BASE / "sft_unique_for_review.jsonl"
REVIEW = BASE / "sft_review.csv"
OUTPUT = BASE / "sft_approved.jsonl"

with SOURCE.open(encoding="utf-8-sig") as f:
    originals = [json.loads(line) for line in f if line.strip()]

try:
    with REVIEW.open(encoding="utf-8-sig", newline="") as f:
        reviews = list(csv.DictReader(f))
except UnicodeDecodeError:
    with REVIEW.open(encoding="cp949", newline="") as f:
        reviews = list(csv.DictReader(f))

if len(originals) != len(reviews):
    raise ValueError("원본과 검토 CSV의 행 개수가 다릅니다.")

approved = []
stats = Counter()

for expected_num, (item, review) in enumerate(
    zip(originals, reviews), start=1
):
    if str(review["번호"]).strip() != str(expected_num):
        raise ValueError(f"{expected_num}번째 행 번호가 일치하지 않습니다.")

    if review["유형"] != item["category"]:
        raise ValueError(f"{expected_num}번째 유형이 변경되었습니다.")

    if review["질문"] != item["prompt"][-1]["content"]:
        raise ValueError(f"{expected_num}번째 질문이 변경되었습니다.")

    if review["답변"] != item["completion"][0]["content"]:
        raise ValueError(f"{expected_num}번째 원본 답변이 변경되었습니다.")

    status = review["검토결과"].strip()
    stats[status] += 1

    if status == "승인":
        answer = item["completion"][0]["content"]

    elif status == "수정":
        answer = review["수정할 답변"].strip()
        if not answer:
            raise ValueError(f"{expected_num}번: 수정 답변이 비어 있습니다.")

    elif status in ("제외", "검토대기", ""):
        continue

    else:
        raise ValueError(f"{expected_num}번: 알 수 없는 상태 {status}")

    approved.append({
        "prompt": item["prompt"],
        "completion": [{"role": "assistant", "content": answer}],
    })

with OUTPUT.open("w", encoding="utf-8") as f:
    for record in approved:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

print("검토 현황:", dict(stats))
print("승인된 학습 후보:", len(approved))
print("출력 파일:", OUTPUT)
