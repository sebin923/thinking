"""생각한줄 SFT 실행: GTX 1660 6GB 테스트용 (최초 5 step)."""
from pathlib import Path
import torch
from datasets import load_dataset
from transformers import AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig
from trl import SFTConfig, SFTTrainer

BASE = Path(__file__).resolve().parent
DATA = BASE / 'data' / 'sft' / 'sft_train.jsonl'
MODEL = 'Qwen/Qwen2.5-0.5B-Instruct'
OUTPUT = BASE / 'outputs' / 'qwen-sft'
ADAPTER = BASE / 'outputs' / 'sft-adapter'

if not torch.cuda.is_available():
    raise RuntimeError('CUDA GPU를 찾지 못했습니다.')
if not DATA.exists():
    raise FileNotFoundError(f'SFT 데이터 파일이 없습니다: {DATA}')

print('GPU:', torch.cuda.get_device_name(0))
dataset = load_dataset('json', data_files=str(DATA), split='train')
print('SFT 데이터 수:', len(dataset))
assert {'prompt', 'completion'} <= set(dataset.column_names), 'prompt와 completion 필드가 필요합니다.'

TOKENIZER = AutoTokenizer.from_pretrained(MODEL)
if TOKENIZER.pad_token is None:
    TOKENIZER.pad_token = TOKENIZER.eos_token

quant = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type='nf4',
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
)
lora = LoraConfig(
    r=8, lora_alpha=16, lora_dropout=0.05,
    target_modules=['q_proj', 'v_proj'], bias='none', task_type='CAUSAL_LM',
)
args = SFTConfig(
    output_dir=str(OUTPUT),
    num_train_epochs=3,
    max_steps=-1,  # 기능 검증 후 -1로 바꾸면 전체 1 epoch
    per_device_train_batch_size=1,
    gradient_accumulation_steps=2,
    learning_rate=1e-4,
    max_length=384,
    completion_only_loss=True,
    fp16=False,  # 기존 GTX1660 환경의 BF16 gradient 문제 회피
    bf16=False,
    gradient_checkpointing=True,
    gradient_checkpointing_kwargs={'use_reentrant': False},
    logging_steps=1,
    save_strategy='no',
    report_to='none',
    optim='adamw_torch',
    model_init_kwargs={
        'dtype': torch.float16,
        'quantization_config': quant,
        'device_map': {'': 0},
    },
)
trainer = SFTTrainer(
    model=MODEL,
    args=args,
    train_dataset=dataset,
    processing_class=TOKENIZER,
    peft_config=lora,
)
print('SFT 학습 시작')
trainer.train()
ADAPTER.mkdir(parents=True, exist_ok=True)
trainer.save_model(str(ADAPTER))
TOKENIZER.save_pretrained(str(ADAPTER))
print('SFT 학습 완료:', ADAPTER)
