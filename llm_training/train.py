
import torch
from pathlib import Path
from datasets import load_dataset
from transformers import AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig
from trl import SFTTrainer, SFTConfig

# 경로 설정
BASE_DIR = Path(__file__).resolve().parent

model_name = "Qwen/Qwen2.5-0.5B-Instruct"
data_path = BASE_DIR / "data" / "processed" / "cleaned.jsonl"
output_path = BASE_DIR / "outputs" / "qwen-writing"
save_path = BASE_DIR / "outputs" / "final-adapter"

# 1. GPU 확인
if not torch.cuda.is_available():
    raise RuntimeError("CUDA GPU를 사용할 수 없습니다.")

print("GPU:", torch.cuda.get_device_name(0))

# 2. 데이터 확인
if not data_path.exists():
    raise FileNotFoundError(f"학습 데이터 없음: {data_path}")

dataset = load_dataset(
    "json",
    data_files=str(data_path),
    split="train"
)

if len(dataset) < 2:
    raise ValueError("학습 데이터가 너무 적습니다.")

if "text" not in dataset.column_names:
    raise ValueError("JSONL에 text 필드가 필요합니다.")

print("학습 데이터:", len(dataset), "건")

# 3. 토크나이저
tokenizer = AutoTokenizer.from_pretrained(model_name)

if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

# 4. 4비트 양자화
quant_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True
)

# 5. LoRA 설정
lora_config = LoraConfig(
    r=8,
    lora_alpha=16,
    lora_dropout=0.05,
    target_modules=["q_proj", "v_proj"],
    bias="none",
    task_type="CAUSAL_LM"
)

# 6. 학습 설정
training_args = SFTConfig(
    output_dir=str(output_path),
    num_train_epochs=1,
    max_steps=20,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=4,
    learning_rate=1e-4,
    max_length=256,
    dataset_text_field="text",
    completion_only_loss=False,
    fp16=False,
    bf16=False,
    gradient_checkpointing=True,
    gradient_checkpointing_kwargs={"use_reentrant": False},
    logging_steps=1,
    save_strategy="no",
    report_to="none",
    optim="adamw_torch",
    model_init_kwargs={
        "dtype": torch.float16,
        "quantization_config": quant_config,
        "device_map": {"": 0}
    }
)

# 7. 학습기 생성
trainer = SFTTrainer(
    model=model_name,
    args=training_args,
    train_dataset=dataset,
    processing_class=tokenizer,
    peft_config=lora_config
)

print("학습 파라미터 데이터 타입:")

for name, param in trainer.model.named_parameters():
    if param.requires_grad:
        print(name, param.dtype)
        break

# 8. 학습 실행
print("QLoRA 학습 시작")
trainer.train()

# 9. LoRA 저장
save_path.mkdir(parents=True, exist_ok=True)

trainer.save_model(str(save_path))
tokenizer.save_pretrained(str(save_path))

print("QLoRA 학습 완료")
print("저장 위치:", save_path)
