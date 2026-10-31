
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

input_path = BASE_DIR / "data" / "raw" / "wiki_corpus.jsonl"
output_path = BASE_DIR / "data" / "processed" / "cleaned.jsonl"

output_path.parent.mkdir(parents=True, exist_ok=True)

seen = set()
total = 0
cleaned_count = 0

with open(input_path, "r", encoding="utf-8") as src, \
     open(output_path, "w", encoding="utf-8") as dst:

    for line in src:
        if not line.strip():
            continue

        total += 1

        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        # 원문 필드 확인
        field = next(
            (key for key in ("content", "text", "body")
             if isinstance(record.get(key), str)),
            None
        )

        if field is None:
            continue

        content = record[field]

        # 불필요한 공백 정리
        content = re.sub(r"[ \t]+", " ", content)
        content = re.sub(r"\n{3,}", "\n\n", content)
        content = content.strip()

        # 짧은 문서 제외
        if len(content) < 100:
            continue

        # 중복 본문 제거
        if content in seen:
            continue

        seen.add(content)

        # 학습용 필드 통일
        record.pop("content", None)
        record.pop("body", None)
        record["text"] = content

        dst.write(json.dumps(record, ensure_ascii=False) + "\n")
        cleaned_count += 1

print("원본 문서 수:", total)
print("정제된 문서 수:", cleaned_count)
print("저장 위치:", output_path)
