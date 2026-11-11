
from pathlib import Path
from threading import Lock

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from transformers import AutoProcessor, AutoModelForMultimodalLM
from peft import PeftModel

app = FastAPI(title="생각한줄 LLM 서버")

BASE_MODEL = "Qwen/Qwen3.5-2B"
ADAPTER_PATH = (
    Path(__file__).resolve().parent
    / "outputs"
    / "qwen35_fresh_20261110_152041_837194"
    / "adapter"
)

model = None
processor = None
generation_lock = Lock()


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10000)
    max_new_tokens: int = Field(default=256, ge=1, le=1024)


@app.on_event("startup")
def load_model():
    global model, processor

    if not (ADAPTER_PATH / "adapter_config.json").exists():
        raise RuntimeError(f"어댑터가 없습니다: {ADAPTER_PATH}")

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU를 사용할 수 없습니다.")

    print("Qwen3.5 기본 모델 로딩")
    processor = AutoProcessor.from_pretrained(BASE_MODEL)

    base = AutoModelForMultimodalLM.from_pretrained(
        BASE_MODEL,
        dtype=torch.float16,
        device_map="auto",
    )

    print("공통 LoRA 어댑터 로딩")
    model = PeftModel.from_pretrained(
        base, str(ADAPTER_PATH)
    )
    model.eval()
    print("LLM 준비 완료")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "loaded": model is not None,
        "model": BASE_MODEL,
        "adapter": ADAPTER_PATH.parent.name,
        "device": "cuda" if torch.cuda.is_available() else "cpu",
    }


@app.post("/generate")
def generate(req: GenerateRequest):
    if model is None:
        raise HTTPException(503, "모델이 로딩되지 않았습니다.")

    messages = [
        {
            "role": "user",
            "content": req.prompt,
        }
    ]

    with generation_lock:
        inputs = processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
            enable_thinking=False,
        ).to(model.device)

        with torch.inference_mode():
            output = model.generate(
                **inputs,
                max_new_tokens=req.max_new_tokens,
                do_sample=False,
                pad_token_id=processor.tokenizer.eos_token_id,
            )

        new_tokens = output[0][inputs["input_ids"].shape[-1]:]
        result = processor.decode(
            new_tokens, skip_special_tokens=True
        )

    return {"text": result.strip()}
