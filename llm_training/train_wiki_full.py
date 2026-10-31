
import json
import torch
from pathlib import Path
from datasets import load_dataset
from transformers import AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig
from trl import SFTTrainer, SFTConfig

BASE = Path(__file__).resolve().parent
DATA = BASE / "data" / "processed" / "cleaned.jsonl"
OUTPUT = BASE / "outputs" / "wiki-full"
ADAPTER = BASE / "outputs" / "wiki-full-adapter"

MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
SEED = 42

# GPU 확인
if not torch.cuda.is_available():
    raise RuntimeError("CUDA GPU가 필요합니다.")

print("GPU:", torch.cuda.get_device_name(0))

# 데이터 확인
if not DATA.is_file():
    raise FileNotFoundError(DATA)

dataset = load_dataset(
    "json",
    data_files=str(DATA),
    split="train"
)

if "text" not in dataset.column_names:
    raise ValueError("text 필드가 없습니다.")

dataset = dataset.filter(
    lambda x: isinstance(x["text"], str)
    and bool(x["text"].strip())
)

print("전체 데이터:", len(dataset))

# 학습과 검증을 분리
split = dataset.train_test_split(
    test_size=0.1,
    seed=SEED,
    shuffle=True
)

train_data = split["train"]
valid_data = split["test"]

print("학습 데이터:", len(train_data))
print("검증 데이터:", len(valid_data))

# 분리된 문서 ID 기록
OUTPUT.mkdir(parents=True, exist_ok=True)

with open(
    OUTPUT / "data_split.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        {
            "seed": SEED,
            "train_count": len(train_data),
            "valid_count": len(valid_data),
            "train_ids": train_data["id"]
                if "id" in train_data.column_names else [],
            "valid_ids": valid_data["id"]
                if "id" in valid_data.column_names else []
        },
        f,
        ensure_ascii=False,
        indent=2
    )

# 토크나이저
tokenizer = AutoTokenizer.from_pretrained(MODEL)

if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

# 4비트 양자화
quant_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True
)

# LoRA
lora_config = LoraConfig(
    r=8,
    lora_alpha=16,
    lora_dropout=0.05,
    target_modules=["q_proj", "v_proj"],
    bias="none",
    task_type="CAUSAL_LM"
)

# 학습 설정
args = SFTConfig(
    output_dir=str(OUTPUT),
    num_train_epochs=1,
    max_steps=-1,

    per_device_train_batch_size=1,
    gradient_accumulation_steps=4,
    per_device_eval_batch_size=1,

    learning_rate=5e-5,
    max_length=512,
    dataset_text_field="text",
    completion_only_loss=False,

    fp16=False,
    bf16=False,
    gradient_checkpointing=True,
    gradient_checkpointing_kwargs={
        "use_reentrant": False
    },

    logging_steps=20,
    eval_strategy="epoch",
    save_strategy="epoch",
    save_total_limit=1,
    report_to="none",
    optim="adamw_torch",
    seed=SEED,

    model_init_kwargs={
        "dtype": torch.float16,
        "quantization_config": quant_config,
        "device_map": {"": 0}
    }
)

# 학습기 생성
trainer = SFTTrainer(
    model=MODEL,
    args=args,
    train_dataset=train_data,
    eval_dataset=valid_data,
    processing_class=tokenizer,
    peft_config=lora_config
)

# 학습 실행
print("\n위키백과 전체 학습 실험 시작")
trainer.train()

# 검증
metrics = trainer.evaluate()

print("\n검증 결과:", metrics)

# LoRA 저장
ADAPTER.mkdir(parents=True, exist_ok=True)
trainer.save_model(str(ADAPTER))
tokenizer.save_pretrained(str(ADAPTER))

with open(
    OUTPUT / "evaluation.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(metrics, f, indent=2)

print("\n학습 및 검증 완료")
print("어댑터 위치:", ADAPTER)
