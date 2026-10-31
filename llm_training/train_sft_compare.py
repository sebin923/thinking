
"""생각한줄 공통 글쓰기 모델 SFT 비교 학습."""

import argparse
from pathlib import Path

import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)
from peft import (
    LoraConfig,
    PeftModel,
    prepare_model_for_kbit_training,
)
from trl import SFTConfig, SFTTrainer


BASE = Path(__file__).resolve().parent
DATA = BASE / "data" / "sft" / "sft_train.jsonl"
MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
WIKI_ADAPTER = BASE / "outputs" / "wiki-full-adapter"

parser = argparse.ArgumentParser()
parser.add_argument(
    "--source",
    choices=["base", "wiki"],
    required=True,
)
args_cli = parser.parse_args()
source = args_cli.source

OUTPUT = BASE / "outputs" / f"sft-{source}-run"
ADAPTER = BASE / "outputs" / f"sft-{source}-adapter"

if not torch.cuda.is_available():
    raise RuntimeError("CUDA GPU를 찾지 못했습니다.")

if not DATA.exists():
    raise FileNotFoundError(f"데이터 파일 없음: {DATA}")

if source == "wiki" and not (WIKI_ADAPTER / "adapter_config.json").exists():
    raise FileNotFoundError(
        f"위키백과 LoRA 어댑터 없음: {WIKI_ADAPTER}"
    )

print("GPU:", torch.cuda.get_device_name(0))
print("학습 출발점:", source)

dataset = load_dataset(
    "json",
    data_files=str(DATA),
    split="train",
)
print("SFT 데이터 수:", len(dataset))

assert {"prompt", "completion"} <= set(dataset.column_names)

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

train_args = SFTConfig(
    output_dir=str(OUTPUT),
    num_train_epochs=3,
    max_steps=-1,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=2,
    learning_rate=1e-4,
    max_length=384,
    completion_only_loss=True,
    fp16=False,
    bf16=False,
    gradient_checkpointing=True,
    gradient_checkpointing_kwargs={"use_reentrant": False},
    logging_steps=1,
    save_strategy="no",
    report_to="none",
    optim="adamw_torch",
)

if source == "base":
    # 기본 Qwen에서 새로운 LoRA 학습
    train_args.model_init_kwargs = {
        "dtype": torch.float16,
        "quantization_config": quant,
        "device_map": {"": 0},
    }

    trainer = SFTTrainer(
        model=MODEL,
        args=train_args,
        train_dataset=dataset,
        processing_class=tokenizer,
        peft_config=lora,
    )

else:
    # 위키백과 LoRA를 학습 가능한 상태로 불러오기
    model = AutoModelForCausalLM.from_pretrained(
        MODEL,
        dtype=torch.float16,
        quantization_config=quant,
        device_map={"": 0},
    )

    model = prepare_model_for_kbit_training(
        model,
        use_gradient_checkpointing=True,
        gradient_checkpointing_kwargs={
            "use_reentrant": False
        },
    )

    model = PeftModel.from_pretrained(
        model,
        str(WIKI_ADAPTER),
        is_trainable=True,
    )

    model.config.use_cache = False
    model.print_trainable_parameters()

    trainer = SFTTrainer(
        model=model,
        args=train_args,
        train_dataset=dataset,
        processing_class=tokenizer,
    )

print("SFT 학습 시작:", source)
trainer.train()

ADAPTER.mkdir(parents=True, exist_ok=True)
trainer.save_model(str(ADAPTER))
tokenizer.save_pretrained(str(ADAPTER))

print("SFT 학습 완료:", ADAPTER)
