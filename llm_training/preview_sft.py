import json
from pathlib import Path

path = Path("data/sft/sft_unique_for_review.jsonl")
seen = set()

with path.open("r", encoding="utf-8-sig") as f:
    for line in f:
        if not line.strip():
            continue

        item = json.loads(line)
        category = item["category"]

        if category in seen:
            continue

        seen.add(category)

        print("\n" + "=" * 60)
        print("유형:", category)
        print("질문:", item["prompt"][-1]["content"])
        print("답변:", item["completion"][0]["content"])
        print("=" * 60)
