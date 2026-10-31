"""Audit SFT candidate response duplication without modifying original data."""
import json
from pathlib import Path
from collections import Counter, defaultdict

BASE = Path(__file__).resolve().parent
# Place this script in C:\thinking\llm_training
SRC = BASE / 'data' / 'sft' / 'sft_candidates_300.jsonl'
OUT = BASE / 'data' / 'sft'
if not SRC.exists():
    raise FileNotFoundError(SRC)
entries = []
with SRC.open(encoding='utf-8-sig') as f:
    for n, line in enumerate(f, 1):
        if not line.strip():
            continue
        item = json.loads(line)
        if not isinstance(item.get('completion'), list) or not item['completion'] or not isinstance(item['completion'][0].get('content'), str):
            raise ValueError(f'Invalid completion at line {n}')
        entries.append(item)
seen = {}
unique, duplicates = [], []
for item in entries:
    response = item['completion'][0]['content'].strip()
    if response in seen:
        duplicates.append({'id': item.get('id'), 'category': item.get('category'), 'same_answer_as': seen[response], 'topic': item.get('topic')})
    else:
        seen[response] = item.get('id')
        unique.append(item)
OUT.mkdir(parents=True, exist_ok=True)
with (OUT / 'sft_unique_for_review.jsonl').open('w', encoding='utf-8') as f:
    for item in unique:
        f.write(json.dumps(item, ensure_ascii=False) + '\n')
with (OUT / 'sft_duplicate_report.json').open('w', encoding='utf-8') as f:
    json.dump(duplicates, f, ensure_ascii=False, indent=2)
print('원본 후보:', len(entries))
print('서로 다른 답변 후보:', len(unique))
print('동일 답변 제외:', len(duplicates))
for category in sorted(set(x.get('category') for x in entries)):
    total = sum(x.get('category') == category for x in entries)
    remain = sum(x.get('category') == category for x in unique)
    print(f'{category}: 전체 {total} / 남은 후보 {remain}')
print('검토용 파일:', OUT / 'sft_unique_for_review.jsonl')
print('중복 보고서:', OUT / 'sft_duplicate_report.json')
print('주의: 남은 후보는 검토 대기 상태이며 학습용 승인 데이터가 아닙니다.')
