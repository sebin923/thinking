"""사용자가 명시적으로 승인한 JSONL만 사용해 공통 LoRA를 사용자별로 추가 학습.
실행: python train_personal.py --user-id 4 --data data/personalized/user_4_approved.jsonl
주의: 연구/시연용. 사용자 동의와 데이터 검토 후에만 실행.
"""
import argparse
import json
from pathlib import Path

import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel, prepare_model_for_kbit_training
from trl import SFTConfig, SFTTrainer

ROOT = Path(__file__).resolve().parent
MODEL = 'Qwen/Qwen2.5-1.5B-Instruct'
COMMON = ROOT / 'outputs' / 'writing-sft-v3-adapter'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--user-id', type=int, required=True)
    p.add_argument('--data', type=Path, required=True, help='명시적으로 승인된 사용자 전용 JSONL')
    p.add_argument('--epochs', type=int, default=1)
    args = p.parse_args()
    if args.user_id < 1 or not args.data.is_file() or args.epochs < 1:
        p.error('유효한 사용자 ID, 데이터 파일, epoch 값이 필요합니다.')
    if not (COMMON / 'adapter_config.json').exists():
        raise FileNotFoundError(f'공통 어댑터 없음: {COMMON}')
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA GPU가 필요합니다.')

    target = ROOT / 'outputs' / 'personalized' / f'user_{args.user_id}'
    if target.exists():
        raise FileExistsError(f'기존 개인 어댑터 보호: {target}')
    cfg = json.loads((COMMON/'adapter_config.json').read_text(encoding='utf-8'))
    if cfg.get('base_model_name_or_path', '').rstrip('/') != MODEL:
        raise RuntimeError('공통 어댑터의 기본 모델이 1.5B 모델과 다릅니다.')

    dataset = load_dataset('json', data_files=str(args.data.resolve()), split='train')
    if not {'prompt', 'completion'}.issubset(dataset.column_names):
        raise ValueError('prompt와 completion 필드가 필요합니다.')
    if len(dataset) < 3:
        raise ValueError('승인된 데이터가 3건 미만입니다. 개인 LoRA를 학습하지 않습니다.')
    for record in dataset:
        if not isinstance(record['prompt'], (str, list)) or not isinstance(record['completion'], (str, list)):
            raise ValueError('잘못된 prompt/completion 형식')
        if not record['prompt'] or not record['completion']:
            raise ValueError('빈 prompt/completion이 있습니다.')
    if len(dataset) < 20:
        print('경고: 데이터가 20건 미만입니다. 시연 가능하더라도 개인화 품질이 보장되지 않습니다.')
    dataset = dataset.select_columns(['prompt', 'completion'])
    tok = AutoTokenizer.from_pretrained(MODEL)
    if tok.pad_token is None: tok.pad_token = tok.eos_token
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                               bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
    base = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float16,
                                                quantization_config=quant, device_map={'': 0})
    base = prepare_model_for_kbit_training(base, use_gradient_checkpointing=True,
                                           gradient_checkpointing_kwargs={'use_reentrant': False})
    model = PeftModel.from_pretrained(base, str(COMMON), is_trainable=True)
    model.config.use_cache = False
    print('학습 가능 파라미터:')
    model.print_trainable_parameters()
    settings = SFTConfig(
        output_dir=str(ROOT/'outputs'/'personalized_runs'/f'user_{args.user_id}'),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=1, gradient_accumulation_steps=2,
        learning_rate=2e-5, max_length=768, completion_only_loss=True,
        fp16=False, bf16=False, gradient_checkpointing=True,
        gradient_checkpointing_kwargs={'use_reentrant': False},
        save_strategy='no', eval_strategy='no', report_to='none',
        optim='adamw_torch', seed=42,
    )
    trainer = SFTTrainer(model=model, args=settings, train_dataset=dataset, processing_class=tok)
    stats = trainer.train()
    target.mkdir(parents=True, exist_ok=False)
    trainer.save_model(str(target))
    tok.save_pretrained(str(target))
    (target/'personal_metrics.json').write_text(json.dumps({
        'user_id': args.user_id, 'train_examples': len(dataset),
        'train_loss': stats.metrics.get('train_loss'),
        'parent_adapter': 'writing-sft-v3-adapter',
        'note': '기존 공통 LoRA를 시작점으로 추가 학습한 별도 사용자 어댑터'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('개인 어댑터 저장:', target)

if __name__ == '__main__':
    main()