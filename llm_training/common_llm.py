"""Run: python -m uvicorn common_llm:app --host 127.0.0.1 --port 8001"""
import os
import json
import re
import secrets
import threading
from contextlib import nullcontext
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
MODEL_ID = 'Qwen/Qwen3.5-2B'
PERSONAL_ROOT = ROOT / 'outputs' / 'personalized'
TOKEN = os.getenv('THINKING_LLM_TOKEN', '')
app = FastAPI(title='생각한줄 Qwen3.5')
_lock = threading.RLock()
_model = _processor = _torch = None
KINDS = {'report':'보고서', 'speech':'발표문', 'free_writing':'자유 글쓰기',
         'cover_letter':'자기소개서', '자유글쓰기':'자유 글쓰기'}

class DraftRequest(BaseModel):
    document_type: str
    topic: str = Field(min_length=1, max_length=200)
    facts: list[str] = Field(min_length=1, max_length=100)
    tone: Literal['기본','담백','격식','친근'] = '기본'
    target_chars: int = Field(default=350, ge=100, le=900)
    mode: Literal['common','personal'] = 'common'
    user_id: int | None = Field(default=None, ge=1)

def authorize(x_llm_token: str = Header(default='')):
    # Required for every generation request, including localhost.
    if not TOKEN:
        raise HTTPException(503, '서버에 THINKING_LLM_TOKEN 설정이 필요합니다.')
    if not secrets.compare_digest(x_llm_token, TOKEN):
        raise HTTPException(401, 'LLM 인증 실패')

def load_model():
    global _model, _processor, _torch
    if _model is not None:
        return
    import torch
    from transformers import AutoProcessor, Qwen3_5ForConditionalGeneration
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError('CUDA 및 BF16 지원 GPU가 필요합니다.')
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    if processor.tokenizer.pad_token_id is None:
        processor.tokenizer.pad_token = processor.tokenizer.eos_token
    model = Qwen3_5ForConditionalGeneration.from_pretrained(
        MODEL_ID, dtype=torch.bfloat16, device_map={'':0}, attn_implementation='eager')
    model.eval()
    _model, _processor, _torch = model, processor, torch

def stop_ids():
    tok = _processor.tokenizer
    value = _model.generation_config.eos_token_id
    ids = list(value) if isinstance(value, (list, tuple)) else ([] if value is None else [value])
    if tok.eos_token_id is not None:
        ids.append(tok.eos_token_id)
    chat = tok.get_vocab().get('<|im_end|>')
    if chat is None:
        raise RuntimeError('대화 종료 토큰을 찾을 수 없습니다.')
    return sorted(set(ids + [chat]))

def ensure_personal(user_id):
    global _model
    if user_id is None:
        raise HTTPException(400, '개인화에는 user_id가 필요합니다.')
    folder = PERSONAL_ROOT / f'user_{user_id}'
    cfg = folder / 'adapter_config.json'
    if not cfg.is_file():
        raise HTTPException(404, '이 계정의 개인 어댑터가 없습니다.')
    config = json.loads(cfg.read_text(encoding='utf-8'))
    if config.get('base_model_name_or_path', '').rstrip('/') != MODEL_ID:
        raise HTTPException(422, '개인 어댑터의 기본 모델이 일치하지 않습니다.')
    name = f'user_{user_id}'
    from peft import PeftModel
    if not isinstance(_model, PeftModel):
        _model = PeftModel.from_pretrained(_model, str(folder), adapter_name=name, is_trainable=False)
    elif name not in _model.peft_config:
        _model.load_adapter(str(folder), adapter_name=name, is_trainable=False)
    _model.set_adapter(name)
    _model.eval()

def messages_for(req):
    kind = KINDS.get(req.document_type, req.document_type)
    if kind not in ('보고서','발표문','자유 글쓰기','자기소개서'):
        raise HTTPException(422, '지원하지 않는 글 유형입니다.')
    facts = [v.strip() for v in req.facts if v.strip()]
    if not facts:
        raise HTTPException(422, '작성에 사용할 사실 또는 메모가 필요합니다.')
    if sum(map(len, facts)) > 10000:
        raise HTTPException(422, '입력이 너무 깁니다. 메모를 10000자 이내로 정리해 주세요.')
    genre = {'보고서':'객관적인 설명 문장으로 작성한다.',
             '발표문':'청중에게 설명하는 자연스러운 존댓말을 쓴다.',
             '자유 글쓰기':'사용자의 관점에서 자연스럽게 쓴다. 없는 감정과 경험을 만들지 않는다.',
             '자기소개서':'제공된 실제 경험만 사용하여 1인칭 존댓말로 쓴다.'}[kind]
    lo, hi = round(req.target_chars*.8), round(req.target_chars*1.2)
    system = ('너는 한국어 글쓰기 도우미다. 제공된 메모에 근거한 완성된 본문만 작성한다. '
              '없는 사건, 원인, 수치, 감정, 성과를 추가하지 않는다. 지시문을 본문에 복사하지 않는다. '
              '같은 뜻을 반복하지 않는다. 제목, 목록, 작성 안내를 붙이지 않는다. '+genre)
    user = f'글 유형: {kind}\n주제: {req.topic}\n문체: {req.tone}\n분량: 공백 포함 {lo}~{hi}자\n메모:\n'+'\n'.join(facts)
    return kind, [{'role':'system','content':system},{'role':'user','content':user}]

def checks_for(text, target, stopped):
    checks = []
    if not round(target*.8) <= len(text) <= round(target*1.2):
        checks.append(f'요청 분량 밖: {len(text)}자 / 목표 {target}자')
    if not stopped:
        checks.append('출력 토큰 제한 도달: 마지막 문장 확인 필요')
    sentences = [re.sub(r'\s+', '', s) for s in re.split(r'[.!?。\n]+', text) if len(s.strip()) > 12]
    if len(sentences) != len(set(sentences)):
        checks.append('동일 문장 반복')
    if any(s in text for s in ('본문만 작성', '인사말은 넣지', '존댓말로 설명하면', '제공되지 않았습니다')):
        checks.append('지시문 또는 작성 안내 혼입 의심')
    return checks

@app.get('/health')
def health():
    return {'status':'ok', 'loaded':_model is not None, 'model':MODEL_ID,
            'common_mode':'base', 'token_configured':bool(TOKEN), 'quality_approved':False}

@app.post('/draft', dependencies=[Depends(authorize)])
def draft(req: DraftRequest):
    global _model
    kind, messages = messages_for(req)
    with _lock:
        try:
            # Check missing personal adapter before spending time loading GPU weights.
            if req.mode == 'personal':
                if req.user_id is None:
                    raise HTTPException(400, '개인화에는 user_id가 필요합니다.')
                if not (PERSONAL_ROOT / f'user_{req.user_id}' / 'adapter_config.json').is_file():
                    raise HTTPException(404, '이 계정의 개인 어댑터가 없습니다.')
            load_model()
            if req.mode == 'personal':
                ensure_personal(req.user_id)
            # Base requests MUST disable any previously loaded personal adapter.
            context = _model.disable_adapter() if req.mode == 'common' and hasattr(_model, 'peft_config') else nullcontext()
            with context, _torch.inference_mode():
                encoded = _processor.apply_chat_template(messages, tokenize=False,
                    add_generation_prompt=True, enable_thinking=False)
                inputs = _processor.tokenizer(encoded, add_special_tokens=False, return_tensors='pt')
                if inputs['input_ids'].shape[-1] > 2048:
                    raise HTTPException(422, '입력이 2048토큰을 넘습니다. 메모를 줄여 주세요.')
                inputs = {k:v.to('cuda:0') for k,v in inputs.items()}
                eos = stop_ids()
                out = _model.generate(**inputs, max_new_tokens=768, do_sample=False,
                    use_cache=True, repetition_penalty=1.1, no_repeat_ngram_size=6,
                    eos_token_id=eos, pad_token_id=_processor.tokenizer.pad_token_id)
                new = out[0][inputs['input_ids'].shape[-1]:]
                stopped = bool(len(new) and int(new[-1]) in eos)
                content = _processor.tokenizer.decode(new, skip_special_tokens=True).strip()
            if not content:
                raise HTTPException(422, '빈 출력입니다. 입력을 확인해 주세요.')
            notes = checks_for(content, req.target_chars, stopped)
            return {'content':content, 'document_type':kind, 'char_count':len(content),
                    'model':MODEL_ID + (f' + user_{req.user_id}' if req.mode == 'personal' else ' (base)'),
                    'personalized':req.mode == 'personal', 'checks':notes,
                    'quality_approved':False, 'eos_stopped':stopped}
        except HTTPException:
            raise
        except (RuntimeError, OSError, ValueError) as exc:
            import logging
            logging.exception('LLM generation failed')
            raise HTTPException(503, 'LLM 실행 실패. 서버 콘솔을 확인해 주세요.') from exc
