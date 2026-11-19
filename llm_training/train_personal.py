"""Continue a selected common Qwen LoRA separately for demo users 6, 7, 8.

Default/--check-data uses CPU only. --train or --smoke explicitly starts GPU work.
Checkpoints stay in an experiment directory and are never activated for serving.
"""
import argparse
from datetime import datetime
import gc
import json
from pathlib import Path

from personalization_data import MODEL_ID, PROFILES, adapter_fingerprint, file_hash, load_prepared

ROOT = Path(__file__).resolve().parent


def tokenize_personal_rows(rows, processor, name, maximum):
    from datasets import Dataset
    result = []
    for index, row in enumerate(rows, 1):
        prefix = processor.apply_chat_template(row["prompt"], tokenize=False, add_generation_prompt=True, enable_thinking=False)
        input_ids = processor.tokenizer(prefix, add_special_tokens=False)["input_ids"]
        answer = processor.tokenizer(row["completion"][0]["content"], add_special_tokens=False)["input_ids"]
        if not answer:
            raise ValueError(f"{name}:{index}: empty answer tokens")
        answer += [processor.tokenizer.eos_token_id]
        if len(input_ids) > 2048 or len(input_ids) + len(answer) > maximum:
            raise ValueError(f"{name}:{index}: token limit exceeded; data is never truncated")
        result.append({"input_ids": input_ids + answer, "attention_mask": [1] * (len(input_ids) + len(answer)),
                       "labels": [-100] * len(input_ids) + answer})
    print(name, len(result), "records; maximum tokens:", max(len(row["input_ids"]) for row in result), flush=True)
    return Dataset.from_list(result)


def train_user(user_id, datasets, common, output, epochs, smoke, data_dir):
    import torch
    from peft import PeftModel
    from transformers import AutoProcessor, DataCollatorForSeq2Seq, Qwen3_5ForConditionalGeneration, Trainer, TrainingArguments, set_seed
    from train_qwen35 import EpochMonitor, tokenize_rows

    class PersonalEpochMonitor(EpochMonitor):
        def write_report(self):
            super().write_report()
            report = self.output / "epoch_comparison.txt"
            report.write_text(report.read_text(encoding="utf-8").replace(
                "epoch 0은 초기 LoRA(기본 모델과 같은 초기 출력)입니다.",
                "epoch 0은 개인 학습을 시작하기 전의 선택된 공통 어댑터입니다."), encoding="utf-8")

    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("A CUDA GPU with BF16 support is required")
    set_seed(42)
    common_path = Path(common["path"])
    metrics_path = common_path.parent / "metrics.json"
    previous = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.is_file() else {}
    revision = previous.get("base_commit")
    processor = AutoProcessor.from_pretrained(str(common_path))
    tok = processor.tokenizer
    if tok.eos_token_id is None:
        raise ValueError("The tokenizer has no EOS token")
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "right"
    # Only train/valid are tokenized or passed to Trainer; test is reserved.
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    maximum = manifest.get("training_max_sequence_length", 1024)
    tokenized = {split: (tokenize_personal_rows(datasets[split], processor, f"user_{user_id}/{split}", maximum)
                         if maximum > 1024 else tokenize_rows(datasets[split], processor, f"user_{user_id}/{split}"))
                 for split in ("train", "valid")}
    kwargs = {"revision": revision} if revision else {}
    base = Qwen3_5ForConditionalGeneration.from_pretrained(
        MODEL_ID, dtype=torch.bfloat16, device_map={"": 0}, attn_implementation="eager", **kwargs)
    # This is a full continuation of the common adapter, not a fresh small-data LoRA.
    model = PeftModel.from_pretrained(base, str(common_path), is_trainable=True)
    model.config.use_cache = False
    if hasattr(model.config, "text_config"):
        model.config.text_config.use_cache = False
    model.enable_input_require_grads()
    model.print_trainable_parameters()
    numbers = list(range(1, len(datasets["valid"]) + 1))
    metadata = {"base_model": MODEL_ID, "base_commit": getattr(base.config, "_commit_hash", None),
                "fresh_lora": False, "initialization": "continued_common_lora", "parent_common": common,
                "user_id": user_id, "demo_only": True, "human_approved": False, "quality_approved": False,
                "epochs": epochs, "learning_rate": 2e-5, "seed": 42, "generation_stop_policy": "model_and_chat_eos",
                "data_manifest_sha256": file_hash(data_dir / "manifest.json"),
                "training_script_sha256": file_hash(Path(__file__)),
                "trainer_implementation_sha256": file_hash(ROOT / "train_qwen35.py"),
                "training_max_sequence_length": maximum,
                "generation_sample": {"per_type": 0, "selection": "all_validation_rows", "source_valid_numbers": numbers,
                                      "counts_by_type": {}, "count": len(numbers)},
                "data": {split: {"count": len(datasets[split]), "sha256": file_hash(data_dir / f"user_{user_id}/{split}.jsonl")}
                         for split in ("train", "valid")}}
    output.mkdir(parents=True, exist_ok=False)
    monitor = None if smoke else PersonalEpochMonitor(processor, datasets["valid"], output, metadata)
    args = TrainingArguments(
        output_dir=str(output), num_train_epochs=epochs, max_steps=2 if smoke else -1,
        per_device_train_batch_size=1, per_device_eval_batch_size=1,
        gradient_accumulation_steps=1 if smoke else 4, learning_rate=2e-5,
        warmup_steps=0 if smoke else 2, bf16=True, fp16=False,
        gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False},
        optim="adamw_torch", logging_steps=1, eval_strategy="no" if smoke else "epoch", save_strategy="no",
        prediction_loss_only=True, report_to="none", dataloader_num_workers=0,
        remove_unused_columns=False, seed=42,
    )
    train_data = tokenized["train"].select(range(min(4, len(datasets["train"])))) if smoke else tokenized["train"]
    trainer = Trainer(model=model, args=args, train_dataset=train_data, eval_dataset=tokenized["valid"],
                      callbacks=[monitor] if monitor else None,
                      data_collator=DataCollatorForSeq2Seq(tokenizer=tok, padding=True, label_pad_token_id=-100, pad_to_multiple_of=8))
    trainer.model_accepts_loss_kwargs = False
    before = None if smoke else trainer.evaluate()
    trained = trainer.train()
    after = None if smoke else trainer.evaluate()
    metadata.update(before=before, after=after, train=trained.metrics, smoke=smoke)
    (output / "metrics.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    del trainer, model, base, tokenized
    gc.collect()
    torch.cuda.empty_cache()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--users", type=int, nargs="+", choices=tuple(PROFILES), default=list(PROFILES))
    parser.add_argument("--common-adapter", type=Path)
    parser.add_argument("--epochs", type=int, choices=(1, 2, 3), default=3)
    parser.add_argument("--output-dir", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-data", action="store_true")
    mode.add_argument("--train", action="store_true")
    mode.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    data_dir = (args.data_dir if args.data_dir.is_absolute() else ROOT / args.data_dir).resolve()
    manifest, datasets = load_prepared(data_dir)
    if len(args.users) != len(set(args.users)):
        parser.error("--users must not contain duplicates")
    common = None
    if args.common_adapter:
        common_path = args.common_adapter if args.common_adapter.is_absolute() else ROOT / args.common_adapter
        common = adapter_fingerprint(common_path)
    for uid in args.users:
        print(f"user_{uid}:", {split: len(rows) for split, rows in datasets[uid].items()})
    if not args.train and not args.smoke:
        print("CPU data checks passed. Synthetic demo only; no model was loaded or trained.")
        return
    if common is None:
        parser.error("Choose the completed common adapter explicitly with --common-adapter")
    output = args.output_dir or ROOT / "outputs" / ("personalization_study_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    output = (output if output.is_absolute() else ROOT / output).resolve()
    serving_root = (ROOT / "outputs/personalized").resolve()
    if output == serving_root or serving_root in output.parents or output == Path(common["path"]) or Path(common["path"]) in output.parents:
        parser.error("Use a new experiment directory outside serving and parent-adapter folders")
    output.mkdir(parents=True, exist_ok=False)
    study = {"kind": "personalization_study_v1", "data_dir": str(data_dir), "data_manifest_sha256": file_hash(data_dir / "manifest.json"),
             "common": common, "users": args.users, "epochs": args.epochs, "demo_only": True,
             "quality_approved": False, "smoke": args.smoke, "completed_users": []}
    study_file = output / "study.json"
    study_file.write_text(json.dumps(study, ensure_ascii=False, indent=2), encoding="utf-8")
    for uid in args.users:
        # Recheck immutable parent weights before every independent continuation.
        if adapter_fingerprint(common["path"])["sha256"] != common["sha256"]:
            raise ValueError("The common adapter changed during the study")
        train_user(uid, datasets[uid], common, output / f"user_{uid}", args.epochs, args.smoke, data_dir)
        study["completed_users"].append(uid)
        study_file.write_text(json.dumps(study, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Experiment saved:", output)
    print("No serving adapter or model-selection setting was changed.")


if __name__ == "__main__":
    main()
