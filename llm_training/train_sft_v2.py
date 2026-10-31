
"""생각한줄 SFT v2: 학습 141건 + 검증 18건"""

import argparse
import json
import random
from pathlib import Path

import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, PeftModel, prepare_model_for_kbit_training
from trl import SFTConfig, SFTTrainer

BASE = Path(__file__).resolve().parent
DATA = BASE / "data" / "sft"
MODEL = "Qwen/Qwen2.5-0.5B-Instruct"

parser = argparse.ArgumentParser()
parser.add_argument("--source", choices=["base", "wiki"], required=True)
opt = parser.parse_args()

OUTPUT = BASE / "outputs" / f"sft-v2-{opt.source}-run"
ADAPTER = BASE / "outputs" / f"sft-v2-{opt.source}-adapter"
WIKI = BASE / "outputs" / "wiki-full-adapter"

if not torch.cuda.is_available():
    raise RuntimeError("CUDA GPU가 필요합니다.")

if ADAPTER.exists():
    raise FileExistsError(
        f"기존 결과를 보호하기 위해 중단합니다: {ADAPTER}"
    )

if opt.source == "wiki" and not (WIKI / "adapter_config.json").exists():
    raise FileNotFoundError(f"위키백과 어댑터 없음: {WIKI}")

random.seed(42)
torch.manual_seed(42)
torch.cuda.manual_seed_all(42)

print("GPU:", torch.cuda.get_device_name(0))
print("학습 모델:", opt.source)

train = load_dataset(
    "json",
    data_files=str(DATA / "sft_train_v2.jsonl"),
    split="train",
)
valid = load_dataset(
    "json",
    data_files=str(DATA / "sft_valid_v2.jsonl"),
    split="train",
)

print("학습 데이터:", len(train))
print("검증 데이터:", len(valid))

tokenizer = AutoTokenizer.from_pretrained(MODEL)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

quant = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
)

lora = LoraConfig(
    r=8,
    lora_alpha=16,
    lora_dropout=0.05,
    target_modules=["q_proj", "v_proj"],
    bias="none",
    task_type="CAUSAL_LM",
)

args = SFTConfig(
    output_dir=str(OUTPUT),
    num_train_epochs=3,
    max_steps=-1,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=2,
    per_device_eval_batch_size=1,
    learning_rate=1e-4,
    max_length=384,
    completion_only_loss=True,
    fp16=False,
    bf16=False,
    gradient_checkpointing=True,
    gradient_checkpointing_kwargs={"use_reentrant": False},
    eval_strategy="epoch",
    save_strategy="no",
    logging_steps=10,
    report_to="none",
    optim="adamw_torch",
    seed=42,
)

if opt.source == "base":
    args.model_init_kwargs = {
        "dtype": torch.float16,
        "quantization_config": quant,
        "device_map": {"": 0},
    }

    trainer = SFTTrainer(
        model=MODEL,
        args=args,
        train_dataset=train,
        eval_dataset=valid,
        processing_class=tokenizer,
        peft_config=lora,
    )

else:
    model = AutoModelForCausalLM.from_pretrained(
        MODEL,
        dtype=torch.float16,
        quantization_config=quant,
        device_map={"": 0},
    )

    model = prepare_model_for_kbit_training(
        model,
        use_gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
    )

    model = PeftModel.from_pretrained(
        model,
        str(WIKI),
        is_trainable=True,
    )
    model.config.use_cache = False
    model.print_trainable_parameters()

    trainer = SFTTrainer(
        model=model,
        args=args,
        train_dataset=train,
        eval_dataset=valid,
        processing_class=tokenizer,
    )

print("학습 시작")

train_result = trainer.train()
eval_result = trainer.evaluate()

ADAPTER.mkdir(parents=True, exist_ok=False)
trainer.save_model(str(ADAPTER))
tokenizer.save_pretrained(str(ADAPTER))

metrics = {
    "source": opt.source,
    "train_examples": len(train),
    "valid_examples": len(valid),
    "train_loss": train_result.metrics.get("train_loss"),
    "eval_loss": eval_result.get("eval_loss"),
}

with (ADAPTER / "metrics.json").open("w", encoding="utf-8") as f:
    json.dump(metrics, f, ensure_ascii=False, indent=2)

print("\n===== 최종 학습 결과 =====")
print(json.dumps(metrics, ensure_ascii=False, indent=2))
print("모델 저장:", ADAPTER)
