"""Qwen3.5-2B 새 LoRA 학습. 학교 RTX A4000 / 기존 .venv용.

이 파일을 llm_training에 저장하고 data/qwen35/train.jsonl, valid.jsonl을 사용한다.
--check-data: 형식/길이 검사, --smoke: 2스텝 시험, 옵션 없음: 1에포크 학습.
--data-dir data/qwen35_service: 보완 데이터 폴더 지정. 기본값은 data/qwen35.
--epochs 3: 3에포크 이내 비교 실험. 매 에포크 어댑터와 검증 응답을 별도 저장.
매번 기본 모델에서 시작한다. 이전 어댑터나 체크포인트를 이어받지 않는다.
test.jsonl은 학습 및 검증 손실 계산에 사용하지 않는다.
"""
import argparse
import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model
from transformers import (
    AutoProcessor, DataCollatorForSeq2Seq,
    Qwen3_5ForConditionalGeneration, Trainer, TrainerCallback, TrainingArguments, set_seed,
)

ROOT = Path(__file__).resolve().parent
MODEL_ID = 'Qwen/Qwen3.5-2B'
MAX_LENGTH = 1024


def resolve_eos_ids(model_eos, tokenizer):
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


class EpochMonitor(TrainerCallback):
    """검증 데이터의 원문 생성 결과를 기록한다. 자동으로 최고 모델을 선정하지 않는다."""
    def __init__(self, processor, rows, output, metadata):
        self.processor, self.rows = processor, rows
        self.output, self.metadata = output, metadata
        self.snapshots = {}

    def on_evaluate(self, args, state, control, model=None, metrics=None, **kwargs):
        epoch = int(round(state.epoch or 0))
        key = str(epoch)
        if key in self.snapshots:
            return control
        self.output.mkdir(parents=True, exist_ok=True)
        # 생성 중 실패해도 해당 에포크의 학습 결과는 먼저 보존한다.
        if epoch:
            stage = self.output / f'epoch_{epoch}'
            adapter = stage / 'adapter'
            adapter.mkdir(parents=True, exist_ok=True)
            model.save_pretrained(adapter)
            self.processor.save_pretrained(adapter)
            stage_metrics = dict(self.metadata)
            stage_metrics.update({'epochs': epoch, 'before': self.snapshots.get('0', {}).get('metrics'),
                                  'after': metrics, 'selection_status': 'not_selected'})
            (stage / 'metrics.json').write_text(json.dumps(stage_metrics, ensure_ascii=False, indent=2), encoding='utf-8')
        tok = self.processor.tokenizer
        snapshot = {'epoch': epoch, 'metrics': metrics, 'responses': []}
        self.snapshots[key] = snapshot
        was_training = model.training
        try:
            model.eval()
            # 중간 생성 평가가 학습의 난수 상태를 바꾸지 않도록 복원한다.
            with torch.random.fork_rng(devices=[0]), torch.inference_mode():
                for index, row in enumerate(self.rows, 1):
                    print(f'[epoch {epoch}] 검증 답변 {index}/{len(self.rows)} 생성', flush=True)
                    prefix = self.processor.apply_chat_template(
                        row['prompt'], tokenize=False, add_generation_prompt=True, enable_thinking=False,
                    )
                    inputs = tok(prefix, add_special_tokens=False, return_tensors='pt')
                    inputs = {k: v.to('cuda:0') for k, v in inputs.items()}
                    eos = model.generation_config.eos_token_id
                    if eos is None:
                        eos = tok.eos_token_id
                    eos_ids = resolve_eos_ids(eos, tok)
                    generation_config = deepcopy(model.generation_config)
                    generation_config.update(
                        max_new_tokens=512, do_sample=False, num_beams=1,
                        repetition_penalty=1.0, no_repeat_ngram_size=0, use_cache=True,
                        pad_token_id=tok.pad_token_id, eos_token_id=eos_ids,
                        return_dict_in_generate=False,
                    )
                    output = model.generate(
                        **inputs, generation_config=generation_config,
                    )
                    generated = output[0, inputs['input_ids'].shape[1]:].tolist()
                    text = tok.decode(generated, skip_special_tokens=True)
                    answer = {'number': index, 'text': text, 'chars': len(text.strip()),
                              'tokens': len(generated),
                              'ended_with_eos': bool(generated and generated[-1] in eos_ids),
                              'eos_token_ids': eos_ids,
                              'raw_text_with_special_tokens': tok.decode(generated, skip_special_tokens=False)}
                    snapshot['responses'].append(answer)
                    print(f'  {answer["chars"]}자 / EOS 종료: {answer["ended_with_eos"]}', flush=True)
                    self.write_report()
        finally:
            model.train(was_training)
        return control

    def write_report(self):
        payload = {'metadata': self.metadata, 'validation_prompts': self.rows,
                   'generation': {'do_sample': False, 'max_new_tokens': 512,
                                  'repetition_penalty': 1.0, 'enable_thinking': False,
                                  'stop_policy': 'model_and_chat_eos'},
                   'snapshots': self.snapshots}
        (self.output / 'epoch_comparison.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        lines = ['에포크별 검증 응답 비교', f'실험 폴더: {self.output}',
                 'epoch 0은 초기 LoRA(기본 모델과 같은 초기 출력)입니다.',
                 '같은 검증 입력과 greedy 설정으로 비교합니다. 분량 통과는 품질 합격이 아닙니다.',
                 '학습 기간에 맞춰 선형 학습률 감소도 늘어나므로 이전 1에포크 실험과 첫 에포크가 완전히 같지는 않습니다.', '']
        for key, snap in self.snapshots.items():
            successes = 0
            for answer in snap['responses']:
                prompt = self.rows[answer['number'] - 1]['prompt'][-1]['content']
                bounds = re.search(r'(\d+)\s*[~～∼–-]\s*(\d+)\s*자', prompt)
                successes += int(bool(bounds and int(bounds[1]) <= answer['chars'] <= int(bounds[2])))
            lines.append(f'epoch {key}: 검증 손실 {(snap["metrics"] or {}).get("eval_loss")} / 분량 충족 {successes}/{len(snap["responses"])}')
        for index, row in enumerate(self.rows, 1):
            lines.extend(['', f'===== 검증 {index} =====', '[입력]',
                          json.dumps(row['prompt'], ensure_ascii=False, indent=2)])
            for key, snap in self.snapshots.items():
                answer = next((x for x in snap['responses'] if x['number'] == index), None)
                if answer:
                    lines.extend([f'[epoch {key}] {answer["chars"]}자 / EOS 종료: {answer["ended_with_eos"]}', answer['text'], ''])
            lines.extend(['[참고 정답]', row['completion'][0]['content']])
        (self.output / 'epoch_comparison.txt').write_text('\n'.join(lines), encoding='utf-8')


def read_rows(path):
    if not path.is_file():
        raise FileNotFoundError(f'데이터 파일이 없습니다: {path}')
    rows = []
    for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            prompt, completion = row['prompt'], row['completion']
            assert isinstance(prompt, list) and prompt
            assert isinstance(completion, list) and len(completion) == 1
            assert completion[0]['role'] == 'assistant'
            assert prompt[-1]['role'] == 'user'
            for message in prompt + completion:
                assert isinstance(message['content'], str) and message['content'].strip()
                assert message['role'] in {'system', 'user', 'assistant'}
        except (ValueError, KeyError, TypeError, IndexError, AssertionError) as exc:
            raise ValueError(f'{path.name}:{number} prompt/completion 형식을 확인해 주세요.') from exc
        rows.append(row)
    if not rows:
        raise ValueError(f'빈 데이터 파일입니다: {path}')
    return rows


def tokenize_rows(rows, processor, name):
    tok = processor.tokenizer
    result, chars, lengths = [], [], []
    for number, row in enumerate(rows, 1):
        prefix = processor.apply_chat_template(
            row['prompt'], tokenize=False, add_generation_prompt=True,
            enable_thinking=False,
        )
        answer = row['completion'][0]['content'].strip()
        prompt_ids = tok(prefix, add_special_tokens=False)['input_ids']
        answer_ids = tok(answer, add_special_tokens=False)['input_ids']
        if not answer_ids:
            raise ValueError(f'{name}:{number} 빈 정답 토큰')
        chars.append(len(answer))
        lengths.append(len(answer_ids))
        answer_ids = answer_ids + [tok.eos_token_id]
        ids = prompt_ids + answer_ids
        if len(ids) > MAX_LENGTH:
            raise ValueError(f'{name}:{number} {len(ids)}토큰으로 {MAX_LENGTH} 초과. 자동으로 자르지 않습니다.')
        result.append({
            'input_ids': ids,
            'attention_mask': [1] * len(ids),
            'labels': [-100] * len(prompt_ids) + answer_ids,
        })
    print(f'{name}: {len(result)}건 / 전체 최대 {max(len(x["input_ids"]) for x in result)}토큰', flush=True)
    print(f'  정답 글자 수: 최소 {min(chars)} / 평균 {sum(chars)/len(chars):.1f} / 최대 {max(chars)}', flush=True)
    print(f'  정답 토큰 수: 최소 {min(lengths)} / 평균 {sum(lengths)/len(lengths):.1f} / 최대 {max(lengths)}', flush=True)
    return Dataset.from_list(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--check-data', action='store_true')
    modes.add_argument('--smoke', action='store_true')
    parser.add_argument('--epochs', type=int, choices=[1, 2, 3], default=1)
    parser.add_argument('--data-dir', type=Path, default=Path('data/qwen35'),
                        help='train.jsonl과 valid.jsonl이 있는 폴더. 상대 경로는 이 스크립트 기준.')
    args = parser.parse_args()
    monitor_enabled = args.epochs > 1 and not args.smoke
    set_seed(42)

    data_dir = (args.data_dir if args.data_dir.is_absolute() else ROOT / args.data_dir).resolve()
    print('데이터 폴더:', data_dir, flush=True)
    paths = {name: data_dir / f'{name}.jsonl' for name in ('train', 'valid')}
    rows = {name: read_rows(path) for name, path in paths.items()}
    # 완전히 같은 정답이 학습/검증에 겹치면 중단한다. 의미 중복 검사를 대신하지 않는다.
    answers = {name: {''.join(r['completion'][0]['content'].split()) for r in items}
               for name, items in rows.items()}
    if answers['train'] & answers['valid']:
        raise ValueError('학습/검증 데이터에 동일한 정답이 있습니다.')

    processor = AutoProcessor.from_pretrained(MODEL_ID)
    tok = processor.tokenizer
    if tok.eos_token_id is None:
        raise RuntimeError('EOS 토큰이 없습니다.')
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = 'right'
    datasets = {name: tokenize_rows(items, processor, paths[name].name) for name, items in rows.items()}
    if args.check_data:
        print('데이터 검사 완료. 학습하지 않았습니다. 맞춤법/사실성 검사는 별도입니다.')
        return

    if not torch.cuda.is_available():
        raise RuntimeError('CUDA GPU를 사용할 수 없습니다. 학교 PC의 기존 .venv로 실행하세요.')
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError('이 스크립트는 BF16 지원 GPU용입니다.')
    torch.cuda.reset_peak_memory_stats()
    print('GPU:', torch.cuda.get_device_name(0), flush=True)
    print('기본 모델 로딩:', MODEL_ID, flush=True)
    model = Qwen3_5ForConditionalGeneration.from_pretrained(
        MODEL_ID, dtype=torch.bfloat16, device_map={'': 0}, attn_implementation='eager',
    )
    model.config.use_cache = False
    if hasattr(model.config, 'text_config'):
        model.config.text_config.use_cache = False
    suffixes = {'q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'}
    targets = [name for name, module in model.named_modules()
               if isinstance(module, torch.nn.Linear) and 'language_model' in name
               and name.rsplit('.', 1)[-1] in suffixes]
    if not targets:
        raise RuntimeError('언어 모델의 LoRA 대상 레이어를 찾지 못했습니다.')
    print('LoRA 대상 레이어:', len(targets), flush=True)
    model = get_peft_model(model, LoraConfig(
        r=8, lora_alpha=16, lora_dropout=0.05, target_modules=targets,
        bias='none', task_type='CAUSAL_LM',
    ))
    model.enable_input_require_grads()
    model.print_trainable_parameters()

    train = datasets['train']
    if args.smoke:
        train = train.select(range(min(4, len(train))))
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    prefix = 'qwen35_smoke_' if args.smoke else ('qwen35_epoch_study_' if monitor_enabled else 'qwen35_fresh_')
    output = ROOT / 'outputs' / (prefix + stamp)
    metadata = {
        'base_model': MODEL_ID, 'base_commit': getattr(model.config, '_commit_hash', None),
        'fresh_lora': True, 'epochs': args.epochs, 'learning_rate': 2e-5, 'seed': 42,
        'lr_scheduler_type': 'linear', 'warmup_steps': 0 if args.smoke else 2,
        'generation_stop_policy': 'model_and_chat_eos',
        'data': {name: {'path': str(path), 'count': len(rows[name]),
                       'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                 for name, path in paths.items()},
        'versions': {name: version(name) for name in ('torch', 'transformers', 'peft', 'datasets', 'accelerate')},
    }
    monitor = EpochMonitor(processor, rows['valid'], output, metadata) if monitor_enabled else None
    config = TrainingArguments(
        output_dir=str(output), num_train_epochs=args.epochs,
        max_steps=2 if args.smoke else -1,
        per_device_train_batch_size=1, per_device_eval_batch_size=1,
        gradient_accumulation_steps=1 if args.smoke else 4,
        learning_rate=2e-5, warmup_steps=0 if args.smoke else 2,
        bf16=True, fp16=False, gradient_checkpointing=True,
        gradient_checkpointing_kwargs={'use_reentrant': False},
        optim='adamw_torch', logging_steps=1,
        eval_strategy='epoch' if monitor_enabled else 'no', save_strategy='no',
        prediction_loss_only=True, report_to='none',
        dataloader_num_workers=0, remove_unused_columns=False, seed=42,
    )
    trainer = Trainer(
        model=model, args=config, train_dataset=train,
        eval_dataset=datasets['valid'],
        callbacks=[monitor] if monitor is not None else None,
        data_collator=DataCollatorForSeq2Seq(
            tokenizer=tok, padding=True, label_pad_token_id=-100, pad_to_multiple_of=8,
        ),
    )
    trainer.model_accepts_loss_kwargs = False
    baseline = None
    if not args.smoke:
        print('학습 전 검증 손실 측정', flush=True)
        baseline = trainer.evaluate()
        print('학습 전:', baseline, flush=True)
    print('새 LoRA 학습 시작', flush=True)
    result = trainer.train()
    if args.smoke:
        print('소량 시험 성공. 정식 학습 명령을 실행하세요. 시험 어댑터는 저장하지 않았습니다.')
    else:
        final = trainer.evaluate()
        if not monitor_enabled:
            adapter = output / 'adapter'
            adapter.mkdir(parents=True, exist_ok=True)
            model.save_pretrained(adapter)
            processor.save_pretrained(adapter)
            print('어댑터 저장:', adapter, flush=True)
        metrics = dict(metadata)
        metrics.update({'before': baseline, 'train': result.metrics, 'after': final,
                        'log_history': trainer.state.log_history})
        (output / 'metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')
        if monitor_enabled:
            print('에포크별 어댑터:', output / 'epoch_에포크번호' / 'adapter', flush=True)
            print('보내줄 비교 파일:', output / 'epoch_comparison.txt', flush=True)
            print('최종 에포크를 자동으로 채택하지 않았습니다. 검증 답변을 확인해 선택하세요.', flush=True)
        print('학습 전 검증:', baseline, flush=True)
        print('학습 후 검증:', final, flush=True)
    print('최대 GPU 메모리(GB):', round(torch.cuda.max_memory_allocated() / 1024**3, 2))


if __name__ == '__main__':
    main()
