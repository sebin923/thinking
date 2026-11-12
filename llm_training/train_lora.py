"""Qwen3.5-2B text-only LoRA. Run --smoke before full training."""
import argparse
import math
import re
import json
from datetime import datetime
from pathlib import Path
import torch
from datasets import Dataset
from transformers import (AutoProcessor, Qwen3_5ForConditionalGeneration,
                          Trainer, TrainingArguments, DataCollatorForSeq2Seq, set_seed)
from peft import LoraConfig, get_peft_model, PeftModel


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--train-file', required=True)
    parser.add_argument('--valid-file', required=True)
    parser.add_argument('--init-adapter', required=True, help='복사 시작점인 공통 LoRA 경로')
    parser.add_argument('--run-name', required=True)
    parser.add_argument('--epochs', type=float, default=1)
    parser.add_argument('--lr', type=float, default=2e-5)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.run_name):
        raise ValueError('run-name은 영문, 숫자, _, -만 사용하세요.')
    if args.epochs <= 0 or args.lr <= 0:
        raise ValueError('epochs와 lr은 양수여야 합니다.')
    root = Path.cwd()
    data_dir = root / 'data' / 'qwen35'
    model_id = 'Qwen/Qwen3.5-2B'
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA GPU가 필요합니다.')
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError('이 설정은 BF16 지원 GPU용입니다.')
    set_seed(42)
    print('GPU:', torch.cuda.get_device_name(0), flush=True)
    processor = AutoProcessor.from_pretrained(model_id)
    tokenizer = processor.tokenizer
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = 'right'
    if tokenizer.eos_token_id is None:
        raise RuntimeError('EOS 토큰이 없습니다.')

    def read_data(name):
        path = Path(name)
        if not path.is_file():
            raise FileNotFoundError(f'파일을 넣어 주세요: {path}')
        result = []
        with path.open(encoding='utf-8-sig') as f:
            for number, line in enumerate(f, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                if len(row['completion']) != 1 or row['completion'][0]['role'] != 'assistant':
                    raise ValueError(f'{name}:{number} 정답 형식 오류')
                answer = row['completion'][0]['content'].strip()
                if not answer:
                    raise ValueError(f'{name}:{number} 빈 정답')
                prefix = processor.apply_chat_template(
                    row['prompt'], tokenize=False, add_generation_prompt=True,
                    enable_thinking=False,
                )
                prompt_ids = tokenizer(prefix, add_special_tokens=False)['input_ids']
                answer_ids = tokenizer(answer, add_special_tokens=False)['input_ids']
                answer_ids += [tokenizer.eos_token_id]
                ids = prompt_ids + answer_ids
                # Never silently truncate a target answer.
                if len(ids) > 1024:
                    raise ValueError(f'{name}:{number} {len(ids)}토큰: 최대 길이 재검토 필요')
                result.append({'input_ids': ids, 'attention_mask': [1] * len(ids),
                               'labels': [-100] * len(prompt_ids) + answer_ids})
        if not result:
            raise ValueError(f'{name}: 데이터가 없습니다.')
        print(name, len(result), '건 / 최대', max(len(r['input_ids']) for r in result), '토큰', flush=True)
        return Dataset.from_list(result)

    train = read_data(args.train_file)
    valid = read_data(args.valid_file)
    # recommended_test.jsonl is deliberately not read during training.
    if args.smoke:
        train = train.select(range(min(4, len(train))))
    print('기본 모델 로딩', flush=True)
    model = Qwen3_5ForConditionalGeneration.from_pretrained(
        model_id, dtype=torch.bfloat16, device_map={'': 0},
        attn_implementation='eager',
    )
    model.config.use_cache = False
    if hasattr(model.config, 'text_config'):
        model.config.text_config.use_cache = False
    suffixes = {'q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'}
    targets = [name for name, module in model.named_modules()
               if isinstance(module, torch.nn.Linear)
               and 'language_model' in name
               and name.rsplit('.', 1)[-1] in suffixes]
    if not targets:
        raise RuntimeError('언어 모델의 LoRA 대상 레이어를 찾지 못했습니다.')
    print('LoRA 대상 레이어:', len(targets), flush=True)
    init_path = Path(args.init_adapter)
    cfg = json.loads((init_path / 'adapter_config.json').read_text(encoding='utf-8'))
    if cfg.get('base_model_name_or_path', '').rstrip('/') != model_id:
        raise ValueError('기본 모델이 Qwen/Qwen3.5-2B인 어댑터가 필요합니다.')
    model = PeftModel.from_pretrained(model, str(init_path), is_trainable=True)
    model.enable_input_require_grads()
    model.print_trainable_parameters()
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    output = root / 'outputs' / (('smoke_' if args.smoke else '') + args.run_name + '_' + stamp)
    config = TrainingArguments(
        output_dir=str(output), num_train_epochs=args.epochs,
        max_steps=2 if args.smoke else -1,
        per_device_train_batch_size=1, per_device_eval_batch_size=1,
        gradient_accumulation_steps=1 if args.smoke else 4,
        learning_rate=args.lr, warmup_steps=0 if args.smoke else max(1, math.ceil(math.ceil(len(train) / 4) * args.epochs * 0.1)),
        bf16=True, fp16=False,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={'use_reentrant': False},
        optim='adamw_torch', logging_steps=1,
        eval_strategy='no' if args.smoke else 'epoch',
        save_strategy='no' if args.smoke else 'epoch',
        save_total_limit=2, prediction_loss_only=True,
        report_to='none', dataloader_num_workers=0,
        remove_unused_columns=False, seed=42,
    )
    trainer = Trainer(
        model=model, args=config, train_dataset=train, eval_dataset=valid,
        data_collator=DataCollatorForSeq2Seq(
            tokenizer=tokenizer, padding=True, label_pad_token_id=-100,
            pad_to_multiple_of=8,
        ),
    )
    trainer.model_accepts_loss_kwargs = False
    baseline = None
    if not args.smoke:
        print('학습 전 검증 손실 측정', flush=True)
        baseline = trainer.evaluate()
        print('학습 전:', baseline, flush=True)
    print('학습 시작', flush=True)
    result = trainer.train()
    if args.smoke:
        print('소량 시험 성공. 정식 학습 명령을 실행하세요.')
    else:
        final = trainer.evaluate()
        adapter = output / 'adapter'
        model.save_pretrained(adapter)
        processor.save_pretrained(adapter)
        (output / 'metrics.json').write_text(json.dumps(
            {'base_model': model_id, 'init_adapter': str(init_path.resolve()), 'train_file': str(Path(args.train_file).resolve()), 'valid_file': str(Path(args.valid_file).resolve()), 'learning_rate': args.lr, 'epochs': args.epochs, 'train_count': len(train), 'valid_count': len(valid),
             'before': baseline, 'train': result.metrics, 'after': final},
            ensure_ascii=False, indent=2), encoding='utf-8')
        print('어댑터 저장:', adapter)
        print('학습 전 검증:', baseline)
        print('학습 후 검증:', final)
    print('최대 GPU 메모리(GB):', round(torch.cuda.max_memory_allocated() / 1024**3, 2))


if __name__ == '__main__':
    main()
