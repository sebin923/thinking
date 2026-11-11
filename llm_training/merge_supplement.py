import json
from pathlib import Path

folder = Path("data/qwen35")
train_path = folder / "train.jsonl"
supp_path = folder / "approved_supplement.jsonl"
valid_path = folder / "valid.jsonl"
test_path = folder / "recommended_test.jsonl"

def read(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]

def normalized(text):
    return "".join(text.split())

train = read(train_path)
supp = read(supp_path)
valid = read(valid_path)
test = read(test_path)

def prompt_key(row):
    return normalized(row["prompt"][-1]["content"])

def answer_key(row):
    return normalized(row["completion"][0]["content"])

protected = train + valid + test
seen_prompts = {prompt_key(r) for r in protected}
seen_answers = {
    answer_key(r) for r in protected
    if r.get("completion")
}

added = []
for row in supp:
    p = prompt_key(row)
    a = answer_key(row)

    if p in seen_prompts or a in seen_answers:
        print("중복 제외:", row["id"])
        continue

    added.append(row)
    seen_prompts.add(p)
    seen_answers.add(a)

combined = train + added
target = folder / "train_merged.jsonl"

with target.open("w", encoding="utf-8") as f:
    for row in combined:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

print("기존 학습 데이터:", len(train))
print("새로 추가한 데이터:", len(added))
print("통합 학습 데이터:", len(combined))
print("검증 데이터:", len(valid))
print("생성 파일:", target)
print("기존 train.jsonl은 변경하지 않았습니다.")
