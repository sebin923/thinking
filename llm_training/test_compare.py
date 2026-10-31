
from pathlib import Path
import gc

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

BASE = Path(__file__).resolve().parent
MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"

ADAPTERS = {
    "1": ("기본 Qwen", None),
    "2": ("위키백과 학습 Qwen", BASE / "outputs" / "wiki-full-adapter"),
    "3": ("기본 Qwen + SFT v2", BASE / "outputs" / "sft-v2-base-adapter"),
    "4": ("위키백과 Qwen + SFT v2", BASE / "outputs" / "sft-v2-wiki-adapter"),
}

if not torch.cuda.is_available():
    raise RuntimeError("CUDA GPU를 찾지 못했습니다.")

print("GPU:", torch.cuda.get_device_name(0))

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

while True:
    print("\n===== 모델 선택 =====")
    for key, (name, _) in ADAPTERS.items():
        print(f"{key}. {name}")
    print("0. 종료")

    choice = input("선택: ").strip()

    if choice == "0":
        break

    if choice not in ADAPTERS:
        print("올바른 번호를 선택하세요.")
        continue

    name, adapter_path = ADAPTERS[choice]

    if adapter_path is not None:
        if not (adapter_path / "adapter_config.json").exists():
            print("어댑터 파일이 없습니다:", adapter_path)
            continue

    print("\n모델 불러오는 중:", name)

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        dtype=torch.float16,
        device_map={"": 0},
    )

    if adapter_path is not None:
        model = PeftModel.from_pretrained(
            model,
            str(adapter_path),
            is_trainable=False,
        )

    model.eval()
    print("모델 준비 완료:", name)

    while True:
        question = input("\n질문 입력 (뒤로: back): ").strip()

        if question.lower() == "back":
            break

        if not question:
            continue

        messages = [
            {
                "role": "system",
                "content": (
                    "너는 생각한줄의 한국어 글쓰기 AI다. "
                    "사용자가 제공한 사실만 사용하고 "
                    "경험이나 출처를 지어내지 않는다."
                ),
            },
            {"role": "user", "content": question},
        ]

        inputs = tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
        )

        inputs = {
            key: value.to("cuda:0")
            for key, value in inputs.items()
        }

        with torch.inference_mode():
            outputs = model.generate(
                **inputs,
                max_new_tokens=700,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
            )

        new_tokens = outputs[0][inputs["input_ids"].shape[-1]:]

        answer = tokenizer.decode(
            new_tokens,
            skip_special_tokens=True,
        )

        print("\n========== AI 답변 ==========")
        print(answer)
        print("=============================")

        del inputs, outputs, new_tokens

    del model
    gc.collect()
    torch.cuda.empty_cache()

print("테스트 종료")
