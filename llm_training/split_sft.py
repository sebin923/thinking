
import json
import random
from pathlib import Path
from collections import defaultdict

BASE = Path("data/sft")
SOURCE = BASE / "sft_approved.jsonl"

with SOURCE.open(encoding="utf-8-sig") as f:
    records = [json.loads(line) for line in f if line.strip()]

if not records:
    raise ValueError("승인 데이터가 없습니다.")

# 동일한 질문과 답변 쌍 제거
unique = {}
for record in records:
    key = json.dumps(
        [record["prompt"], record["completion"]],
        ensure_ascii=False,
        sort_keys=True,
    )
    unique[key] = record

records = list(unique.values())
random.Random(42).shuffle(records)

n = len(records)
n_test = round(n * 0.1)
n_valid = round(n * 0.1)

test = records[:n_test]
valid = records[n_test:n_test + n_valid]
train = records[n_test + n_valid:]

for name, data in [
    ("train", train),
    ("valid", valid),
    ("test", test),
]:
    path = BASE / f"sft_{name}_v2.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"{name}: {len(data)}건 -> {path}")

print("전체 고유 데이터:", n)
print("분리 완료")
