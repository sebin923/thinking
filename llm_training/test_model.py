
import torch
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

# 1. 기본 설정
BASE_DIR = Path(__file__).resolve().parent
MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"
ADAPTER_PATH = BASE_DIR / "outputs" / "wiki-full-adapter"

# 2. GPU 확인
if not torch.cuda.is_available():
    raise RuntimeError("CUDA GPU를 사용할 수 없습니다.")

print("GPU:", torch.cuda.get_device_name(0))

# 3. 사용할 모델 선택
print("\n===== 모델 선택 =====")
print("1. 학습 전 기본 Qwen 모델")
print("2. 학습 후 LoRA 적용 모델")

choice = input("선택 (1 또는 2): ").strip()

if choice not in ("1", "2"):
    raise ValueError("1 또는 2를 입력해 주세요.")

# 4. 토크나이저 로드
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

# 5. 기본 Qwen 모델 로드
print("\n모델 불러오는 중...")

model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    dtype=torch.float16,
    device_map="auto"
)

# 6. 학습된 LoRA 적용
if choice == "2":
    if not (ADAPTER_PATH / "adapter_config.json").exists():
        raise FileNotFoundError(
            f"LoRA 가중치를 찾을 수 없습니다: {ADAPTER_PATH}"
        )

    model = PeftModel.from_pretrained(
        model,
        str(ADAPTER_PATH)
    )
    print("LoRA 적용 확인:", model.peft_config.keys())
    print("LoRA 경로:", ADAPTER_PATH)
    model.print_trainable_parameters()
    print("학습된 LoRA 모델 로드 완료")
else:
    print("기본 Qwen 모델 로드 완료")

model.eval()

# 7. 대화 반복
while True:
    question = input("\n질문 입력 (종료: exit): ").strip()

    if question.lower() == "exit":
        print("테스트 종료")
        break

    if not question:
        continue

    messages = [
        {
            "role": "system",
            "content": (
                "너는 생각한줄의 한국어 글쓰기 도우미야. "
                "사용자의 요청에 명확하고 자연스럽게 답변해."
            )
        },
        {
            "role": "user",
            "content": question
        }
    ]

    # Qwen 채팅 형식 적용
    
    # Qwen 채팅 형식 적용
    prompt_text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    inputs = tokenizer(
        prompt_text,
        return_tensors="pt",
        return_attention_mask=True
    ).to("cuda")

    # 답변 생성
    with torch.inference_mode():
        outputs = model.generate(
            **inputs,
            max_new_tokens=800,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id
        )

    generated_tokens = outputs[0][
        inputs["input_ids"].shape[-1]:
    ]

    answer = tokenizer.decode(
        generated_tokens,
        skip_special_tokens=True
    )

    print("\n========== AI 답변 ==========")
    print(answer)
    print("=============================")
