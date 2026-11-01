"""생각한줄 공통 LLM: 단일 모델 로딩 + 보고서/자기소개서 초안 + 선호 반영.
Run: uvicorn common_llm:app --host 127.0.0.1 --port 8001
On GTX 1660 6GB use 4-bit QLoRA inference. This is not per-user fine-tuning.
"""
import os
import re
import threading
from pathlib import Path
from typing import Literal

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

ROOT = Path(__file__).resolve().parent
BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
ADAPTER_PATH = Path(os.getenv("THINKING_ADAPTER", str(ROOT / "outputs" / "writing-sft-v3-adapter")))
USE_ADAPTER = os.getenv("THINKING_USE_ADAPTER", "1") == "1"
app = FastAPI(title="생각한줄 공통 글쓰기 LLM")
_lock = threading.Lock()
_model = None
_tokenizer = None

class DraftRequest(BaseModel):
    document_type: Literal["report", "cover_letter", "보고서", "자기소개서"]
    topic: str = Field(min_length=2, max_length=200)
    facts: list[str] = Field(default_factory=list, max_length=15)
    tone: Literal["기본", "격식", "담백", "친근"] = "기본"
    target_chars: int = Field(default=450, ge=150, le=900)
    user_id: int | None = None  # 메타정보: 이 서비스에 저장하거나 개인 식별에 활용하지 않음

class DraftResponse(BaseModel):
    document_type: str
    content: str
    char_count: int
    model: str
    personalized: bool
    checks: list[str]


def load_model():
    global _model, _tokenizer
    if _model is not None:
        return
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU 없음: 이 구성은 GTX 1660에서 실행하도록 설정됨")
    if USE_ADAPTER and not (ADAPTER_PATH / "adapter_config.json").is_file():
        raise RuntimeError(f"어댑터가 없습니다: {ADAPTER_PATH}")
    _tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    if _tokenizer.pad_token is None:
        _tokenizer.pad_token = _tokenizer.eos_token
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
    base = AutoModelForCausalLM.from_pretrained(BASE_MODEL, dtype=torch.float16, device_map={"": 0}, quantization_config=quant)
    if USE_ADAPTER:
        from json import loads
        cfg = loads((ADAPTER_PATH / "adapter_config.json").read_text(encoding="utf-8"))
        if cfg.get("base_model_name_or_path", "").rstrip("/") != BASE_MODEL:
            raise RuntimeError("어댑터와 기본 모델이 일치하지 않음")
        base = PeftModel.from_pretrained(base, str(ADAPTER_PATH), is_trainable=False)
    base.eval()
    _model = base


def build_messages(req: DraftRequest):
    kind = "보고서" if req.document_type in ("report", "보고서") else "자기소개서"
    facts = [f.strip() for f in req.facts if f.strip()]
    fact_lines = "\n".join(f"- {x}" for x in facts) if facts else "(제공된 개인 경험 또는 구체적 사실 없음)"
    # 중요한 사실: 제공한 경험이 없으면 자기소개서 개인경험을 창작하지 않는다.
    if kind == "보고서":
        format_spec = "서론, 본론, 결론을 각각 한 문단으로 쓰되, 본론에는 원인/문제점/개선 방안을 담아라. 소제목은 서론, 본론, 결론 3개만 사용하라."
    else:
        format_spec = "자연스럽게 연결된 2~3문단의 자기소개서 초안만 출력하라. 실제 역할, 행동, 배운 점을 우선하라."
    system = ("너는 생각한줄의 한국어 글쓰기 도우미다. 요청한 초안 본문만 작성한다. "
              "같은 내용을 반복하지 말고 구체적으로 쓴다. 사실로 주어지지 않은 수치, 연구, 출처, 경력, 성과, 감정은 창작하지 않는다. "
              "정보가 부족하면 일반적인 설명에 머물고, 개인 경험을 지어내지 않는다. "
              "요청한 분량은 가능한 한 준수하고, 메타 설명이나 작성 방법 안내를 출력하지 않는다.")
    user = (f"글 유형: {kind}\n주제/지원 분야: {req.topic}\n문체: {req.tone}\n"
            f"목표 분량: 공백 포함 약 {req.target_chars}자\n"
            f"사용자가 제공한 사실:\n{fact_lines}\n작성 형식: {format_spec}\n초안을 작성하라.")
    return kind, [{"role": "system", "content": system}, {"role": "user", "content": user}]


def generate(req: DraftRequest) -> DraftResponse:
    load_model()
    kind, messages = build_messages(req)
    inputs = _tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors="pt", return_dict=True)
    inputs = {k: v.to("cuda:0") for k,v in inputs.items()}
    # Small models sometimes fail to terminate: bounded output plus explicit truncation warning.
    token_budget = min(950, max(300, int(req.target_chars * 1.4)))
    with _lock, torch.inference_mode():
        output = _model.generate(**inputs, max_new_tokens=token_budget, do_sample=False,
                                 repetition_penalty=1.12, no_repeat_ngram_size=5,
                                 pad_token_id=_tokenizer.pad_token_id, eos_token_id=_tokenizer.eos_token_id)
    generated = output[0][inputs["input_ids"].shape[-1]:]
    text = _tokenizer.decode(generated, skip_special_tokens=True).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    flags=[]
    if len(generated) >= token_budget: flags.append("출력 제한 도달: 문장이 잘렸을 수 있음")
    if not (req.target_chars * .7 <= len(text) <= req.target_chars * 1.3): flags.append("목표 글자 수와 차이 있음")
    if kind == "보고서" and not all(x in text for x in ("서론", "본론", "결론")): flags.append("보고서의 3개 구분 누락")
    if kind == "자기소개서" and not req.facts: flags.append("제공된 경험 없음: 개인 경험 작성 불가")
    return DraftResponse(document_type=kind, content=text, char_count=len(text), model=BASE_MODEL + (" + writing-sft-v3" if USE_ADAPTER else " (base)"), personalized=req.tone != "기본", checks=flags)

@app.get("/health")
def health():
    return {"status":"ok", "loaded":_model is not None, "adapter_configured":USE_ADAPTER, "adapter_found":(ADAPTER_PATH / "adapter_config.json").is_file()}

@app.post("/draft", response_model=DraftResponse)
def draft(req: DraftRequest):
    try:
        return generate(req)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)