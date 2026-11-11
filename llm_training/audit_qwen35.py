"""데이터와 종료 토큰 점검. 가중치를 로딩하거나 학습하지 않는다.

기본: 현재 data/qwen35와 학교 PC에 캐시된 Qwen 프로세서/설정을 검사한다.
--data-only: 파이썬 표준 라이브러리만 사용한다.
결과: outputs/audit_날짜/audit.json, audit.txt
"""
import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent
MODEL_ID = 'Qwen/Qwen3.5-2B'
EXPECTED = {
    'train': 'efcb6c7805fe6d9f50dc2a8f463a57f15dd9200a283e2b6d84c040380c630e3c',
    'valid': '06c6ce2da8d8380030147391aa7b0346ce315a2e116c33c1db3473c89c70fcb5',
    'test': '876db76fbf7074c1741a4ef7f1f5ae5eb46079040fa36b241ff6d8d377c09f20',
}


def norm(text):
    return re.sub(r'\s+', '', text)


def read_rows(path):
    rows = []
    for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        prompt, completion = row.get('prompt'), row.get('completion')
        if not isinstance(prompt, list) or not prompt or prompt[-1].get('role') != 'user':
            raise ValueError(f'{path.name}:{number} prompt 형식 오류')
        if not isinstance(completion, list) or len(completion) != 1 or completion[0].get('role') != 'assistant':
            raise ValueError(f'{path.name}:{number} completion 형식 오류')
        if any(not isinstance(m.get('content'), str) or not m['content'].strip() for m in prompt + completion):
            raise ValueError(f'{path.name}:{number} 빈 글 또는 텍스트 형식 오류')
        rows.append(row)
    if not rows:
        raise ValueError(f'{path.name}이 비었습니다.')
    return rows


def data_summary(rows):
    genres, ranges, chars, issues = Counter(), Counter(), [], []
    for number, row in enumerate(rows, 1):
        user = row['prompt'][-1]['content']
        answer = row['completion'][0]['content'].strip()
        genres[(re.search(r'글 유형:\s*([^\n]+)', user) or [None, '미지정'])[1]] += 1
        bound = re.search(r'(\d+)\s*[~～∼–-]\s*(\d+)\s*자', user)
        flags = []
        if bound:
            lo, hi = int(bound[1]), int(bound[2])
            ranges[f'{lo}~{hi}'] += 1
            if not lo <= len(answer) <= hi:
                flags.append('요청 분량 밖')
        chars.append(len(answer))
        sentences = [norm(s) for s in re.split(r'[.!?。]', answer) if len(s.strip()) > 15]
        if len(sentences) != len(set(sentences)):
            flags.append('동일 문장 반복')
        if any(a != b and SequenceMatcher(None, a, b, autojunk=False).ratio() >= .80
               for i, a in enumerate(sentences) for b in sentences[i+1:]):
            flags.append('유사 문장 반복 의심')
        if re.search(r'[\u4e00-\u9fffA-Za-z]', answer):
            flags.append('한자/영문자 확인')
        if '존댓말' in user and re.search(r'(?:이다|한다|된다|있다|없다)[.!?](?:\s|$)', answer):
            flags.append('요청 말투와 다른 종결 의심')
        if flags:
            issues.append({'row': number, 'flags': flags})
    counts = Counter(norm(r['completion'][0]['content']) for r in rows)
    return {'count': len(rows), 'genres': dict(genres), 'requested_ranges': dict(ranges),
            'answer_chars': {'min': min(chars), 'mean': round(mean(chars), 1), 'max': max(chars)},
            'duplicate_answer_excess': sum(n - 1 for n in counts.values()), 'automatic_flags': issues}


def audit_tokens(rows_by_split, processor, config):
    tok = processor.tokenizer
    if tok.eos_token_id is None:
        raise ValueError('토크나이저 EOS 없음')
    text_cfg = getattr(config, 'text_config', config)
    model_eos = getattr(text_cfg, 'eos_token_id', None)
    model_ids = [model_eos] if isinstance(model_eos, int) else list(model_eos or [])
    # 설정만 읽는다. 모델 가중치는 필요 없다.
    from transformers import GenerationConfig
    generation_source = 'model_config_fallback'
    try:
        gen = GenerationConfig.from_pretrained(MODEL_ID, local_files_only=True)
        generation_source = 'cached_generation_config'
    except OSError:
        gen = GenerationConfig.from_model_config(config)
    eos = gen.eos_token_id
    generation_ids = [eos] if isinstance(eos, int) else list(eos or [])
    if not generation_ids:
        generation_ids = [tok.eos_token_id]  # 이전 비교 코드의 fallback과 동일
    fixed = list(dict.fromkeys(generation_ids + [tok.eos_token_id]))
    if '<|im_end|>' in tok.get_vocab() and tok.get_vocab()['<|im_end|>'] not in fixed:
        fixed.append(tok.get_vocab()['<|im_end|>'])
    result = {
        'model_config_eos': model_ids, 'generation_eos_source': generation_source,
        'legacy_generation_eos': generation_ids,
        'training_answer_eos': tok.eos_token_id, 'training_answer_eos_text': tok.eos_token,
        'training_eos_missing_from_legacy_generation': tok.eos_token_id not in generation_ids,
        'fixed_generation_eos': fixed,
        'config_revision': getattr(config, '_commit_hash', None), 'splits': {},
    }
    for split, rows in rows_by_split.items():
        errors, lengths, matched = [], [], 0
        for number, row in enumerate(rows, 1):
            answer = row['completion'][0]['content'].strip()
            prefix = processor.apply_chat_template(row['prompt'], tokenize=False,
                        add_generation_prompt=True, enable_thinking=False)
            full = processor.apply_chat_template(row['prompt'] + [{'role': 'assistant', 'content': answer}],
                        tokenize=False, add_generation_prompt=False, enable_thinking=False)
            prompt_ids = tok(prefix, add_special_tokens=False)['input_ids']
            answer_ids = tok(answer, add_special_tokens=False)['input_ids'] + [tok.eos_token_id]
            ids = prompt_ids + answer_ids
            canonical = tok(full, add_special_tokens=False)['input_ids']
            if not full.startswith(prefix) or canonical[:len(ids)] != ids:
                errors.append({'row': number, 'reason': '전체 대화 템플릿과 기존 학습 토큰 불일치'})
            else:
                matched += 1
            if len(ids) > 1024:
                errors.append({'row': number, 'reason': '학습 코드 최대 길이 1024 초과'})
            lengths.append(len(ids))
        result['splits'][split] = {'count': len(rows), 'canonical_match_count': matched,
                                  'max_tokens': max(lengths), 'errors': errors}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', default='data/qwen35')
    parser.add_argument('--data-only', action='store_true')
    args = parser.parse_args()
    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = ROOT / data_dir
    report = {'model': MODEL_ID, 'files': {}, 'cross_split_duplicates': {},
              'manual_review_required': True,
              'notes': ['자동 검사는 사실성·맞춤법·자연스러움의 합격 판정이 아닙니다.',
                        '이 프로그램은 데이터/가중치를 수정하지 않습니다.']}
    rows_by_split = {}
    for split in ('train', 'valid', 'test'):
        path = data_dir / f'{split}.jsonl'
        rows = read_rows(path)
        rows_by_split[split] = rows
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        report['files'][split] = {'path': str(path), 'sha256': sha,
                                 'matches_20261109_data': sha == EXPECTED[split], **data_summary(rows)}
    for a, b in [('train', 'valid'), ('train', 'test'), ('valid', 'test')]:
        sets = [{norm(r['completion'][0]['content']) for r in rows_by_split[x]} for x in (a, b)]
        report['cross_split_duplicates'][a + '/' + b] = len(sets[0] & sets[1])
    report['versions'] = {}
    for package in ['torch', 'transformers', 'peft', 'datasets']:
        try:
            report['versions'][package] = version(package)
        except PackageNotFoundError:
            report['versions'][package] = 'not_installed'
    if not args.data_only:
        try:
            from transformers import AutoConfig, AutoProcessor
            processor = AutoProcessor.from_pretrained(MODEL_ID, local_files_only=True)
            config = AutoConfig.from_pretrained(MODEL_ID, local_files_only=True)
            report['tokens'] = audit_tokens(rows_by_split, processor, config)
        except Exception as exc:
            report['token_check_error'] = f'{type(exc).__name__}: {exc}'
    output = ROOT / 'outputs' / ('audit_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    output.mkdir(parents=True, exist_ok=False)
    lines = ['Qwen3.5 데이터·종료 처리 점검', '']
    for split, info in report['files'].items():
        lines.extend([f'{split}: {info["count"]}건 / 어제 파일과 동일: {info["matches_20261109_data"]}',
                      f'  유형: {info["genres"]}', f'  정답 글자 수: {info["answer_chars"]}',
                      f'  자동 확인 필요: {len(info["automatic_flags"])}건'])
    lines.append('분할 간 같은 정답 수: ' + str(report['cross_split_duplicates']))
    if 'tokens' in report:
        t = report['tokens']
        lines.extend(['', f'학습 답변 끝 토큰: {t["training_answer_eos"]} {t["training_answer_eos_text"]}',
                      f'기존 생성 종료 토큰: {t["legacy_generation_eos"]}',
                      f'학습 종료 토큰 누락: {t["training_eos_missing_from_legacy_generation"]}',
                      f'수정할 생성 종료 토큰: {t["fixed_generation_eos"]}'])
        for split, info in t['splits'].items():
            lines.append(f'{split}: 공식 템플릿 일치 {info["canonical_match_count"]}/{info["count"]}, 최대 {info["max_tokens"]}토큰, 오류 {len(info["errors"])}건')
    elif 'token_check_error' in report:
        lines.extend(['', '토큰 점검 미완료: ' + report['token_check_error'],
                      '기존 .venv 및 모델 캐시를 확인하세요. 데이터 검사는 저장했습니다.'])
    lines.extend(['', *report['notes']])
    (output / 'audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'audit.txt').write_text('\n'.join(lines), encoding='utf-8')
    print('\n'.join(lines))
    print('\n결과:', output / 'audit.txt')
    failed = 'token_check_error' in report or any(x['errors'] for x in report.get('tokens', {}).get('splits', {}).values())
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
