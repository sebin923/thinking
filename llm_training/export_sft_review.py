import json
import csv
from pathlib import Path

source = Path("data/sft/sft_unique_for_review.jsonl")
output = Path("data/sft/sft_review.csv")

with source.open("r", encoding="utf-8-sig") as f:
    records = [json.loads(line) for line in f if line.strip()]

with output.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "번호", "유형", "질문", "답변",
        "검토결과", "수정할 답변", "검토메모"
    ])

    for i, item in enumerate(records, 1):
        writer.writerow([
            i,
            item["category"],
            item["prompt"][-1]["content"],
            item["completion"][0]["content"],
            "검토대기",
            "",
            ""
        ])

print("검토용 CSV 생성 완료:", output)
print("검토 대상:", len(records))
