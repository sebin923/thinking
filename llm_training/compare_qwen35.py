r"""학습 전/후 응답 비교. 학습하거나 가중치를 수정하지 않는다.

실행: .\.venv\Scripts\python.exe compare_qwen35.py --split valid --decoding both
선택: --adapter outputs/qwen35_fresh_날짜/adapter
동일한 검증 입력으로 기본/학습 모델, greedy/공식 권장 샘플링을 비교한다.
샘플링은 seed 42의 단일 진단 실행이며 최종 성능 판정이 아니다.
"""
import argparse
import hashlib
import json
import re
import time
from difflib import SequenceMatcher
from datetime import datetime
from pathlib import Path

import torch
from peft import PeftModel
from transformers import (AutoProcessor, Qwen3_5ForConditionalGeneration,
                          LogitsProcessor, LogitsProcessorList, set_seed)
from copy import deepcopy

ROOT = Path(__file__).resolve().parent
MODEL_ID = 'Qwen/Qwen3.5-2B'


def resolve_eos_ids(model_eos, tokenizer):
    """학습에 쓴 턴 종료 EOS와 기본 모델의 종료 EOS를 모두 보존한다."""
    values = [model_eos] if isinstance(model_eos, int) else list(model_eos or [])
    if tokenizer.eos_token_id is not None:
        values.append(tokenizer.eos_token_id)
    vocab = tokenizer.get_vocab()
    if '<|im_end|>' in vocab:
        values.append(vocab['<|im_end|>'])
    values = list(dict.fromkeys(int(x) for x in values if x is not None))
    if not values:
        raise ValueError('종료 토큰을 찾지 못했습니다.')
    return values

# Qwen3.5-2B 모델 카드의 Non-thinking text 권장 값 (2026-11-09 확인).
# https://huggingface.co/Qwen/Qwen3.5-2B#best-practices
PROFILES = {
    'greedy': {'do_sample': False, 'presence_penalty': 0.0},
    'recommended': {'do_sample': True, 'temperature': 1.0, 'top_p': 1.0,
                    'top_k': 20, 'min_p': 0.0, 'presence_penalty': 2.0},
}


class GeneratedPresencePenalty(LogitsProcessor):
    """프롬프트를 제외하고 이미 생성한 토큰의 logit에서 한 번만 penalty를 뺀다."""
    def __init__(self, prompt_length, penalty):
        self.prompt_length = prompt_length
        self.penalty = penalty

    def __call__(self, input_ids, scores):
        generated = input_ids[:, self.prompt_length:]
        if generated.shape[1] == 0:
            return scores
        scores = scores.clone()
        for batch in range(generated.shape[0]):
            seen = torch.unique(generated[batch])
            scores[batch, seen] -= self.penalty
        return scores


def find_adapter(value):
    if value:
        path = Path(value)
        if not path.is_absolute():
            path = ROOT / path
    else:
        candidates = [p for p in (ROOT / 'outputs').glob('qwen35_fresh_*/adapter')
                      if (p / 'adapter_config.json').is_file()
                      and (p / 'adapter_model.safetensors').is_file()
                      and (p.parent / 'metrics.json').is_file()]
        if not candidates:
            raise FileNotFoundError('완료된 새 학습 결과가 없습니다. --adapter로 adapter 폴더를 지정하세요.')
        path = max(candidates, key=lambda p: (p.parent / 'metrics.json').stat().st_mtime)
    config_path = path / 'adapter_config.json'
    if not config_path.is_file():
        raise FileNotFoundError(f'어댑터 설정이 없습니다: {config_path}')
    cfg = json.loads(config_path.read_text(encoding='utf-8'))
    if cfg.get('base_model_name_or_path', '').rstrip('/') != MODEL_ID:
        raise ValueError('Qwen3.5-2B용 어댑터가 아닙니다.')
    return path.resolve()


def checks(text, prompt, hit_limit):
    flags = []
    if not text.strip():
        flags.append('빈 출력')
    if hit_limit:
        flags.append('출력 토큰 제한 도달: 마지막 문장 확인')
    bounds = re.search(r'(\d+)\s*[~～∼–-]\s*(\d+)\s*자', prompt)
    if bounds and not int(bounds[1]) <= len(text.strip()) <= int(bounds[2]):
        flags.append(f'요청 분량 밖: {len(text.strip())}자 (목표 {bounds[1]}~{bounds[2]}자)')
    if re.search(r'[\u4e00-\u9fff]', text):
        flags.append('한자/중국어 문자 포함: 확인 필요')
    if re.search(r'[A-Za-z]', text):
        flags.append('영문자 포함: 확인 필요')
    if re.search(r'(?m)^\s*(?:요청|메모|글 유형|제공한 사실과 관점)\s*:', text):
        flags.append('입력 항목명 출력: 요청 복사 여부 확인')
    sentences = [re.sub(r'\s+', '', s) for s in re.split(r'[.!?。]', text) if len(s.strip()) > 15]
    if len(sentences) != len(set(sentences)):
        flags.append('동일 문장 반복')
    for i, a in enumerate(sentences):
        if any(a != b and SequenceMatcher(None, a, b, autojunk=False).ratio() >= 0.80
               for b in sentences[i + 1:]):
            flags.append('유사 문장 반복 의심: 의미 중복 수동 확인')
            break
    if re.search(r'(?m)^\s*(?:#{1,6}\s|\*\*|[-*]\s|\d+[.)]\s)', text):
        flags.append('제목/목록 형식 의심: 본문만 출력했는지 확인')
    if '존댓말' in prompt and re.search(r'(?:이다|한다|된다|있다|없다)[.!?](?:\s|$)', text):
        flags.append('존댓말 요청과 다른 문장 종결 의심')
    return flags


def generate(model, processor, prompt, max_tokens, profile, seed, stop_policy='chat'):
    tok = processor.tokenizer
    prefix = processor.apply_chat_template(
        prompt, tokenize=False, add_generation_prompt=True, enable_thinking=False,
    )
    inputs = tok(prefix, add_special_tokens=False, return_tensors='pt')
    inputs = {k: v.to('cuda:0') for k, v in inputs.items()}
    eos = model.generation_config.eos_token_id
    if eos is None:
        eos = tok.eos_token_id
    legacy_eos_ids = [eos] if isinstance(eos, int) else list(eos or [])
    eos_ids = resolve_eos_ids(eos, tok) if stop_policy == 'chat' else legacy_eos_ids
    if not eos_ids:
        raise RuntimeError('생성 종료 토큰이 없습니다.')
    settings = dict(PROFILES[profile])
    penalty = settings.pop('presence_penalty')
    # 프레임워크 버전별 presence_penalty 지원 차이를 피하고 동일하게 적용한다.
    generation_config = deepcopy(model.generation_config)
    if hasattr(generation_config, 'presence_penalty'):
        generation_config.presence_penalty = 0.0
    # generation_config와 같은 생성 인자를 generate에 중복 전달하지 않는다.
    generation_config.update(
        max_new_tokens=max_tokens, num_beams=1, **settings,
        repetition_penalty=1.0, no_repeat_ngram_size=0,
        use_cache=True, pad_token_id=tok.pad_token_id, eos_token_id=eos_ids,
        return_dict_in_generate=False,
    )
    processors = LogitsProcessorList()
    if penalty:
        processors.append(GeneratedPresencePenalty(inputs['input_ids'].shape[1], penalty))
    set_seed(seed)
    torch.cuda.synchronize()
    started = time.perf_counter()
    with torch.inference_mode():
        output = model.generate(
            **inputs, logits_processor=processors,
            generation_config=generation_config,
        )
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - started
    generated = output[0, inputs['input_ids'].shape[1]:].tolist()
    text = tok.decode(generated, skip_special_tokens=True)
    hit_limit = bool(generated and len(generated) >= max_tokens and generated[-1] not in eos_ids)
    all_stops = set(resolve_eos_ids(eos, tok))
    first_stop = next((i for i, token in enumerate(generated) if token in all_stops), None)
    return {
        'text': text, 'char_count': len(text.strip()), 'generated_tokens': len(generated),
        'seconds': round(elapsed, 2), 'hit_token_limit': hit_limit,
        'last_token_id': generated[-1] if generated else None,
        'ended_with_eos': bool(generated and generated[-1] in eos_ids),
        'stop_policy': stop_policy, 'eos_token_ids': eos_ids,
        'legacy_eos_token_ids': legacy_eos_ids, 'tokenizer_eos_token_id': tok.eos_token_id,
        'first_chat_or_model_eos_index': first_stop,
        'tokens_after_first_chat_or_model_eos': 0 if first_stop is None else len(generated) - first_stop - 1,
        'raw_text_with_special_tokens': tok.decode(generated, skip_special_tokens=False),
        'generated_token_ids': generated,
        'checks': checks(text, '\n'.join(m['content'] for m in prompt), hit_limit),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adapter')
    parser.add_argument('--max-new-tokens', type=int, default=512)
    parser.add_argument('--split', choices=['valid', 'test'], default='valid')
    parser.add_argument('--decoding', choices=['greedy', 'recommended', 'both'], default='both')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--input', help='별도 평가 JSONL 경로. 지정하면 --split보다 우선합니다.')
    parser.add_argument('--case', type=int, help='1부터 시작하는 특정 문항 하나만 검사합니다.')
    parser.add_argument('--stop-policy', choices=['chat', 'legacy', 'both'], default='chat',
                        help='chat: 답변 종료 포함(기본), legacy: 이전 종료 처리, both: 원인 비교')
    args = parser.parse_args()
    if args.max_new_tokens < 1:
        parser.error('--max-new-tokens는 양수여야 합니다.')
    if args.case is not None and args.case < 1:
        parser.error('--case는 1 이상이어야 합니다.')
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError('BF16 지원 CUDA GPU가 필요합니다. 학교 PC의 기존 .venv로 실행하세요.')
    adapter = find_adapter(args.adapter)
    test_path = Path(args.input) if args.input else ROOT / 'data' / 'qwen35' / f'{args.split}.jsonl'
    if not test_path.is_absolute():
        test_path = ROOT / test_path
    rows = [json.loads(line) for line in test_path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    if not rows:
        raise ValueError(f'{test_path.name}이 비었습니다.')
    for row in rows:
        if not isinstance(row.get('prompt'), list) or not row['prompt']:
            raise ValueError('테스트 prompt 형식 오류')
    indexed_rows = list(enumerate(rows, 1))
    if args.case is not None:
        if args.case > len(rows):
            parser.error(f'--case는 {len(rows)} 이하이어야 합니다.')
        indexed_rows = [indexed_rows[args.case - 1]]
    rows = [row for _, row in indexed_rows]
    metrics_path = adapter.parent / 'metrics.json'
    metrics = json.loads(metrics_path.read_text(encoding='utf-8')) if metrics_path.is_file() else {}
    print('비교할 어댑터:', adapter, flush=True)
    profiles = list(PROFILES) if args.decoding == 'both' else [args.decoding]
    policies = ['legacy', 'chat'] if args.stop_policy == 'both' else [args.stop_policy]
    print('입력:', test_path.name, len(rows), '건 / 생성 설정:', profiles, flush=True)
    print('종료 처리:', policies, '/ 전체 생성 수:', len(rows) * 2 * len(profiles) * len(policies), flush=True)
    print('학습 전 검증:', metrics.get('before'), flush=True)
    print('학습 후 검증:', metrics.get('after'), flush=True)
    revision = metrics.get('base_commit')
    load_kwargs = {'revision': revision} if revision else {}
    processor = AutoProcessor.from_pretrained(str(adapter))
    if processor.tokenizer.pad_token_id is None:
        processor.tokenizer.pad_token = processor.tokenizer.eos_token
    model = Qwen3_5ForConditionalGeneration.from_pretrained(
        MODEL_ID, dtype=torch.bfloat16, device_map={'': 0}, attn_implementation='eager', **load_kwargs,
    )
    model.eval()
    legacy_eos = model.generation_config.eos_token_id
    fixed_eos = resolve_eos_ids(legacy_eos, processor.tokenizer)
    print('기존 모델 종료 토큰:', legacy_eos, flush=True)
    print('학습 답변 종료 토큰:', processor.tokenizer.eos_token_id, flush=True)
    print('수정된 종료 토큰:', fixed_eos, flush=True)
    directory = adapter.parent / ('comparison_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    directory.mkdir(parents=True, exist_ok=False)
    result = {
        'model': MODEL_ID, 'base_revision': revision, 'adapter': str(adapter),
        'split': 'custom' if args.input else args.split, 'input_path': str(test_path),
        'input_sha256': hashlib.sha256(test_path.read_bytes()).hexdigest(),
        'training_metrics': metrics,
        'generation': {'max_new_tokens': args.max_new_tokens, 'seed': args.seed,
                       'profiles': {name: PROFILES[name] for name in profiles},
                       'repetition_penalty': 1.0, 'enable_thinking': False,
                       'stop_policies': policies, 'legacy_eos': legacy_eos, 'chat_eos': fixed_eos},
        'notes': '자동 점수 없음. 맞춤법·사실 보존·자연스러움은 입력과 대조하여 사람이 검토해야 합니다. 시간은 워밍업 없이 측정한 참고값입니다.',
        'cases': [{'number': i, 'id': row.get('id'), 'prompt': row['prompt'],
                   'reference': row.get('completion'), 'review': row.get('review')}
                  for i, row in indexed_rows],
    }
    for mode in ('base', 'trained'):
        if mode == 'trained':
            model = PeftModel.from_pretrained(model, str(adapter), is_trainable=False)
            model.eval()
        for row, case in zip(rows, result['cases']):
            for profile in profiles:
                for policy in policies:
                    key = mode + '_' + profile + '_' + policy
                    print(f'[{key}] 문항 {case["number"]} 생성 중...', flush=True)
                    answer = generate(model, processor, row['prompt'], args.max_new_tokens, profile, args.seed, policy)
                    case[key] = answer
                    print(answer['text'], flush=True)
                    print('글자 수:', answer['char_count'], '/ 확인 항목:', answer['checks'], flush=True)
                    print('EOS로 종료:', answer['ended_with_eos'],
                          '/ 답변 종료 뒤 추가 생성:', answer['tokens_after_first_chat_or_model_eos'], '토큰', flush=True)
                    (directory / 'compare_results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = [f'모델: {MODEL_ID}', f'어댑터: {adapter}', result['notes'], '']
    for case in result['cases']:
        lines.extend([f'===== 테스트 {case["number"]} =====', '[입력]',
                      json.dumps(case['prompt'], ensure_ascii=False, indent=2)])
        for mode, label in [('base', '학습 전'), ('trained', '학습 후')]:
            for profile in profiles:
                for policy in policies:
                    a = case[mode + '_' + profile + '_' + policy]
                    lines.extend([f'[{label}/{profile}/{policy}] {a["char_count"]}자 / {a["seconds"]}초 / EOS 종료: {a["ended_with_eos"]}', a['text'],
                                  '종료 토큰: ' + str(a['eos_token_ids']),
                                  '답변 종료 뒤 추가 생성 토큰: ' + str(a['tokens_after_first_chat_or_model_eos']),
                                  '자동 확인: ' + ('; '.join(a['checks']) or '감지된 항목 없음 — 품질 합격을 뜻하지 않음'), ''])
        if case.get('review'):
            lines.extend(['[수동 검토 기준]', json.dumps(case['review'], ensure_ascii=False, indent=2)])
        lines.extend(['[참고 정답]', json.dumps(case['reference'], ensure_ascii=False, indent=2), ''])
    (directory / 'compare_results.txt').write_text('\n'.join(lines), encoding='utf-8')
    print('비교 완료. 결과 파일:', directory / 'compare_results.txt', flush=True)


if __name__ == '__main__':
    main()
