import json
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained(
    "Qwen/Qwen2.5-0.5B-Instruct"
)

lengths = []

with open("data/sft/sft_train_v2.jsonl", encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        item = json.loads(line)
        messages = item["prompt"] + item["completion"]
        tokens = tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=False
        )
        lengths.append(len(tokens))

print("전체 데이터:", len(lengths))
print("최대 토큰:", max(lengths))
print("평균 토큰:", round(sum(lengths) / len(lengths), 1))
print("384토큰 초과:", sum(x > 384 for x in lengths))
print("512토큰 초과:", sum(x > 512 for x in lengths))
