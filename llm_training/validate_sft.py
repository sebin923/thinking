import json
from pathlib import Path
from collections import Counter

path = Path("data/sft/sft_candidates_300.jsonl")

with path.open("r", encoding="utf-8-sig") as f:
    data = [json.loads(line) for line in f if line.strip()]

print("전체 데이터:", len(data))
print("유형별:", dict(Counter(x["category"] for x in data)))
print("검토 상태:", dict(Counter(x["review_status"] for x in data)))
print("고유 답변:", len(set(x["completion"][0]["content"] for x in data)))
print("중복 답변:", len(data) - len(set(x["completion"][0]["content"] for x in data)))

for x in data:
    assert "prompt" in x and "completion" in x
    assert x["prompt"] and x["completion"]

print("JSONL 구조 검증 완료")
