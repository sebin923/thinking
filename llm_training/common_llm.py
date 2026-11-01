"""생각한줄 공통 LLM: 보고서 / 자기소개서 초안 생성.

기존 SFT v3 어댑터 보존. 출력 품질 미달 시 미리 작성된 글로 대체하지 않음.
실행: python -m uvicorn common_llm:app --host 127.0.0.1 --port 8001
"""
from __future__ import annotations

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
MODEL_ID = "Qwen/Qwen2.5-1.5B-Instruct"
ADAPTER_PATH = Path(os.getenv("THINKING_ADAPTER", str(ROOT / "outputs" / "writing-sft-v3-adapter")))
USE_ADAPTER = os.getenv("THINKING_USE_ADAPTER", "1") == "1"

app = FastAPI(title="생각한줄 공통 LLM")
_lock = threading.RLock()
_model = None
_tokenizer = None


class DraftRequest(BaseModel):
    document_type: Literal["report", "cover_letter", "보고서", "자기소개서"]
    topic: str = Field(min_length=2, max_length=200)
    facts: list[str] = Field(default_factory=list, max_length=15)
    tone: Literal["기본", "격식", "담백", "친근"] = "기본"
    target_chars: int = Field(default=450, ge=150, le=900)
    user_id: int | None = None
    mode: Literal["common", "personal"] = "common"


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
        raise RuntimeError("CUDA GPU가 필요합니다")
    if USE_ADAPTER and not (ADAPTER_PATH / "adapter_config.json").is_file():
        raise RuntimeError(f"어댑터가 없습니다: {ADAPTER_PATH}")
    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    quant = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, dtype=torch.float16, device_map={"": 0}, quantization_config=quant
    )
    if USE_ADAPTER:
        import json
        cfg = json.loads((ADAPTER_PATH / "adapter_config.json").read_text(encoding="utf-8"))
        if cfg.get("base_model_name_or_path", "").rstrip("/") != MODEL_ID:
            raise RuntimeError("어댑터와 기본 모델이 일치하지 않습니다")
        model = PeftModel.from_pretrained(model, str(ADAPTER_PATH), is_trainable=False)
    model.eval()
    _model, _tokenizer = model, tok


def clean(text: str) -> str:
    text = re.sub(r"(?m)^\s{0,3}(?:#{1,6}\s*|\d+[.)]\s+|[-*]\s+)", "", text)
    text = re.sub(r"\*\*|__|```", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    # 불필요한 소제목·목록 방지. 서론·본론·결론은 호출마다 별도 붙임.
    text = re.sub(r"(?m)^\s*(?:서론|본론|결론|원인|문제점|개선\s*방안)\s*[:：]?\s*$", "", text)
    return text.strip()


def complete_sentences(text: str) -> str:
    """잘린 마지막 문장이 있으면 완성된 문장까지만 반환."""
    text = text.strip()
    if not text:
        return text
    if re.search(r"[.!?。][\"'’”)]?$", text):
        return text
    # 줄 중간에서 끝났을 경우 마지막 완성 문장까지만 남김
    marks = list(re.finditer(r"[.!?。](?=\s|$)", text))
    return text[:marks[-1].end()].strip() if marks else text


def select_adapter(req: DraftRequest) -> str:
    """지정한 사용자 어댑터가 실제로 존재할 때만 개인화 사용."""
    if req.mode == 'common':
        return 'default'
    if req.user_id is None or req.user_id < 1:
        raise HTTPException(status_code=400, detail='personal 모드에는 user_id가 필요합니다.')
    personal = ROOT / 'outputs' / 'personalized' / f'user_{req.user_id}'
    if not (personal/'adapter_config.json').is_file():
        raise HTTPException(status_code=404, detail='해당 사용자의 학습된 개인 어댑터가 없습니다.')
    name = f'user_{req.user_id}'
    if name not in _model.peft_config:
        import json
        cfg = json.loads((personal/'adapter_config.json').read_text(encoding='utf-8'))
        if cfg.get('base_model_name_or_path', '').rstrip('/') != MODEL_ID:
            raise HTTPException(status_code=422, detail='개인 어댑터 기본 모델 불일치')
        _model.load_adapter(str(personal), adapter_name=name, is_trainable=False)
    return name


def run_once(system: str, user: str, max_tokens: int) -> tuple[str, bool]:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    inputs = _tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True,
        return_tensors="pt", return_dict=True,
    )
    inputs = {k: v.to("cuda:0") for k, v in inputs.items()}
    with torch.inference_mode():
        out = _model.generate(
            **inputs, max_new_tokens=max_tokens, do_sample=False,
            repetition_penalty=1.12, no_repeat_ngram_size=5,
            pad_token_id=_tokenizer.pad_token_id, eos_token_id=_tokenizer.eos_token_id,
        )
    new = out[0][inputs["input_ids"].shape[-1]:]
    eos = int(_tokenizer.eos_token_id) if _tokenizer.eos_token_id is not None else -1
    stopped_by_limit = len(new) >= max_tokens and (not len(new) or int(new[-1]) != eos)
    return complete_sentences(clean(_tokenizer.decode(new, skip_special_tokens=True))), stopped_by_limit


def format_facts(req: DraftRequest) -> str:
    facts = [x.strip() for x in req.facts if x.strip()]
    return "\n".join(f"- {x}" for x in facts) if facts else "(사용자가 제공한 구체적인 사실 없음)"

def draft_short_report(req: DraftRequest) -> tuple[str, list[str]]:
    system = (
        "너는 한국어 글쓰기 초안 작성 AI다. "
        "사용자가 제공한 사실만 자연스럽게 정리한다. "
        "제공하지 않은 경험, 원인, 행동, 사례를 추가하지 않는다. "
        "서론, 본론, 결론 같은 소제목을 쓰지 않는다. "
        "입력된 정보가 적으면 짧게 작성한다. "
        "같은 뜻을 반복하지 않고 완성된 문장 2~3개만 작성한다. "
        "번역 안내나 질문 응답을 출력하지 않는다. "
        "사용자가 작성한 내용과 같은 주제만 다룬다."
    )

    user = (
        f"주제: {req.topic}\n"
        f"사용자가 제공한 사실:\n{format_facts(req)}\n"
        f"문체: {req.tone}\n"
        "제공된 사실을 바탕으로 짧은 한국어 본문만 작성해."
    )

    content, cut = run_once(system, user, max_tokens=100)

    if not content:
        raise HTTPException(
            status_code=422,
            detail="짧은 보고서 생성에 실패했습니다."
        )

    return content, ["출력 제한 도달"] if cut else []

def draft_report(req: DraftRequest) -> tuple[str, list[str]]:
    if req.target_chars <= 200:
        return draft_short_report(req)
    checks = []
    system = (
        "너는 생각한줄의 한국어 보고서 초안 작성 AI다. "
        "사용자가 제공한 사실과 주제만 활용하여 글을 작성한다. "
        "입력에 없는 개인 경험, 행동, 감정, 통계, 사례, 출처를 절대 지어내지 않는다. "
        "주어진 정보가 적으면 글도 짧게 작성하고 분량을 억지로 늘리지 않는다. "
        "같은 사실이나 의미를 반복하지 않는다. "
        "자연스럽고 정확한 한국어를 사용한다. "
        "한 문단은 1~2개의 완성된 문장으로 작성한다. "
        "제목, 번호, 목록, 소제목은 출력하지 않는다. "
        "서론과 본론, 결론의 역할에 맞는 본문만 작성한다. "
        "추측이나 과장된 표현을 사용하지 않는다. "
        "사용자가 제공하지 않은 해결 방법을 임의로 추가하지 않는다. "
    )

    segments = [
        ("서론", "주제를 소개하고 왜 다룰 필요가 있는지 설명하라. 원인과 해결책은 아직 설명하지 말라."),
        ("본론", "사용자가 제공한 사실을 중심으로 원인, 문제점, 실천 가능한 개선 방안을 구체적으로 연결해 설명하라. 근거 없는 단정은 피하라."),
        ("결론", "본문 핵심을 정리하고 현실적인 제안으로 마무리하라. 새로운 사실은 추가하지 말라."),
    ]
    weights = [0.24, 0.53, 0.23]
    sections = []
    for (heading, instruction), weight in zip(segments, weights):
        section_chars = max(35, round(req.target_chars * weight))
        prompt = (
            f"주제: {req.topic}\n제공 사실:\n{format_facts(req)}\n문체: {req.tone}\n"
            f"이번에 작성할 부분: {heading}\n지침: {instruction}\n"
            f"분량: 한국어 공백 포함 약 {section_chars}자. 완성된 본문 문단만 작성."
        )
        # 너무 긴 출력으로 반복하거나 결론이 잘리는 것을 방지: 작은 문단 3회
        body, cut = run_once(
            system, prompt,
            min(120, max(50, round(section_chars * 0.75)))
        )
        if cut:
            checks.append(f"{heading}: 출력 제한 도달")
        if not body:
            raise HTTPException(status_code=422, detail=f"{heading} 생성 실패: 빈 출력")
        sections.append(f"{heading}\n{body}")
    return "\n\n".join(sections), checks


def draft_cover(req: DraftRequest) -> tuple[str, list[str]]:
    if not any(x.strip() for x in req.facts):
        raise HTTPException(status_code=422, detail="자기소개서에는 실제 경험을 facts에 1개 이상 입력해 주세요")
    system = (
        "너는 생각한줄의 한국어 자기소개서 초안 작성 AI다. "
        "반드시 사용자가 실제로 제공한 경험만 활용한다. "
        "제공되지 않은 직무 경험, 역할, 자격증, 성과, 감정, 수치를 지어내지 않는다. "
        "사용자의 경험이 적으면 글도 짧게 작성한다. "
        "경험을 과장하거나 새로운 사건을 만들어내지 않는다. "
        "같은 의미를 반복하지 않는다. "
        "자연스러운 1인칭 존댓말로 작성한다. "
        "제공된 사실을 명확하게 연결하고 문장은 짧고 간결하게 작성한다. "
        "제목, 번호, 목록, 소제목은 출력하지 않는다. "
        "입력에 없는 내용을 추가하여 분량을 채우지 않는다. "
    )
    
    user = (
        f"지원 직무: {req.topic}\n실제 제공 경험:\n{format_facts(req)}\n"
        f"문체: {req.tone}\n목표: {req.target_chars}자 내외. "
        "제공된 경험을 구체적으로 설명하고 직무 관련성을 조심스럽게 연결하라. "
        "경험이 부족하면 분량을 억지로 늘리거나 없는 사실을 만들지 말라."
    )
    content, cut = run_once(system, user, min(280, max(125, round(req.target_chars * 0.60))))
    if not content:
        raise HTTPException(status_code=422, detail="자기소개서 생성 실패: 빈 출력")
    return content, ["출력 제한 도달"] if cut else []


def checks_for(content: str, req: DraftRequest, old: list[str]) -> list[str]:
    checks = list(old)
    ratio = len(content) / req.target_chars
    if ratio < 0.7 or ratio > 1.3:
        checks.append(f"목표 분량과 차이 있음: {len(content)}자 / {req.target_chars}자")
    if re.search(r"[\u4e00-\u9fff]", content):
        checks.append("한자 혼용 확인 필요")
    if re.search(r"\b(?:planners|asleep)\b", content, re.I):
        checks.append("영어 혼용 확인 필요")
    lines = [re.sub(r"\s+", "", p) for p in re.split(r"[.!?。]", content) if len(p.strip()) > 18]
    if len(lines) != len(set(lines)):
        checks.append("동일 문장 반복 탐지")
    return checks


@app.get("/health")
def health():
    return {"status": "ok", "loaded": _model is not None,
            "adapter_configured": USE_ADAPTER,
            "adapter_found": (ADAPTER_PATH / "adapter_config.json").is_file()}


@app.post("/draft", response_model=DraftResponse)
def draft(req: DraftRequest):
    try:
        with _lock:
            load_model()
            if not USE_ADAPTER and req.mode == 'personal':
                raise HTTPException(status_code=400, detail='공통 어댑터 사용이 비활성화되어 있습니다.')
            adapter_name = select_adapter(req) if USE_ADAPTER else None
            if adapter_name is not None:
                _model.set_adapter(adapter_name)
            kind = "보고서" if req.document_type in ("report", "보고서") else "자기소개서"
            try:
                if kind == "보고서":
                    content, notes = draft_report(req)
                else:
                    content, notes = draft_cover(req)
            finally:
                if USE_ADAPTER:
                    _model.set_adapter('default')
        using_personal = req.mode == 'personal'
        return DraftResponse(
            document_type=kind, content=content, char_count=len(content),
            model=MODEL_ID + (f' + personalized/user_{req.user_id}' if using_personal
                  else (' + writing-sft-v3' if USE_ADAPTER else ' (base)')),
            personalized=using_personal,
            checks=checks_for(content, req, notes),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8001)