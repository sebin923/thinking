"""Compare common/personal adapters with and without the same style settings.

Default/--plan is CPU-only. --generate explicitly starts GPU inference.
Use valid to choose an epoch, then a single chosen epoch for test/transfer.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path

from personalization_data import MODEL_ID, PROFILES, adapter_fingerprint, file_hash, load_prepared, parse_facts, value_hash

ROOT = Path(__file__).resolve().parent
CONDITIONS = ("common_neutral", "common_settings", "personal_neutral", "personal_settings")


def evaluation_cases(data_dir, datasets, split):
    if split == "transfer":
        cases = json.loads((data_dir / "transfer_eval_cases.json").read_text(encoding="utf-8"))
        return {uid: cases for uid in PROFILES}
    return {uid: [{"id": row["metadata"]["case_id"], **parse_facts(row), "reference": row["completion"][0]["content"],
                  **({"target_chars": row["metadata"]["request"]["target_chars"]} if "request" in row["metadata"] else {})}
                  for row in splits[split]] for uid, splits in datasets.items()}


def request_for(case, user_id, settings, target_chars=160):
    profile = PROFILES[user_id]
    prefs = profile["user_preferences"] if settings else None
    tone = {"natural": "친근", "formal": "격식", "confident": "격식"}[prefs["preferred_tone"]] if prefs else "기본"
    return {key: case[key] for key in ("document_type", "topic", "facts")} | {
        "target_chars": case.get("target_chars", target_chars), "tone": tone, "user_preferences": prefs}


def comparison_plan(data_dir, datasets, split, epochs, target_chars):
    cases = evaluation_cases(data_dir, datasets, split)
    common_keys = set()
    personal_generations = 0
    for uid, rows in cases.items():
        for row in rows:
            for settings in (False, True):
                common_keys.add(value_hash(request_for(row, uid, settings, target_chars)))
                personal_generations += len(epochs)
    return {"split": split, "epochs": epochs, "conditions": list(CONDITIONS),
            "cases_per_user": {uid: len(rows) for uid, rows in cases.items()},
            "logical_comparisons": sum(len(rows) for rows in cases.values()) * len(epochs) * 4,
            "maximum_actual_generations_with_cached_common": len(common_keys) + personal_generations,
            "target_chars_for_legacy_cases": target_chars, "do_sample": False, "seed": 42,
            "service_prompt_builder": "common_llm.messages_for", "quality_approved": False,
            "manual_review_required": True}


def generate_comparison(data_dir, datasets, study_dir, epochs, split, target_chars, output=None):
    study_path = study_dir / "study.json"
    study = json.loads(study_path.read_text(encoding="utf-8"))
    if study.get("kind") != "personalization_study_v1" or study.get("smoke") or study.get("demo_only") is not True:
        raise ValueError("Expected a completed non-smoke personalization study")
    if study.get("data_manifest_sha256") != file_hash(data_dir / "manifest.json"):
        raise ValueError("The study and prepared data do not match")
    if set(study.get("completed_users", [])) != set(PROFILES):
        raise ValueError("Finish the three independent user runs before comparing them")
    common = adapter_fingerprint(study["common"]["path"])
    if common["sha256"] != study["common"]["sha256"]:
        raise ValueError("The selected common adapter changed")
    adapters = {}
    for uid in PROFILES:
        for epoch in epochs:
            folder = study_dir / f"user_{uid}/epoch_{epoch}/adapter"
            adapters[uid, epoch] = adapter_fingerprint(folder)
        metrics = json.loads((study_dir / f"user_{uid}/metrics.json").read_text(encoding="utf-8"))
        if metrics.get("user_id") != uid or metrics.get("parent_common", {}).get("sha256") != common["sha256"]:
            raise ValueError(f"Wrong parent or user in checkpoint metadata: {uid}")

    import torch
    from peft import PeftModel
    from transformers import AutoProcessor, Qwen3_5ForConditionalGeneration
    from common_llm import DraftRequest, messages_for
    from compare_qwen35 import generate
    from writing_prompts import finish_text

    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("A CUDA GPU with BF16 support is required")
    processor = AutoProcessor.from_pretrained(common["path"])
    if processor.tokenizer.pad_token_id is None:
        processor.tokenizer.pad_token = processor.tokenizer.eos_token
    common_metrics_path = Path(common["path"]).parent / "metrics.json"
    common_metrics = json.loads(common_metrics_path.read_text(encoding="utf-8")) if common_metrics_path.is_file() else {}
    revision = common_metrics.get("base_commit")
    kwargs = {"revision": revision} if revision else {}
    base = Qwen3_5ForConditionalGeneration.from_pretrained(
        MODEL_ID, dtype=torch.bfloat16, device_map={"": 0}, attn_implementation="eager", **kwargs)
    model = PeftModel.from_pretrained(base, common["path"], adapter_name="common", is_trainable=False)
    loaded = {"common"}
    plan = comparison_plan(data_dir, datasets, split, epochs, target_chars)
    directory = output or study_dir / (f"comparison_{split}_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    directory.mkdir(parents=True, exist_ok=False)
    result = {"plan": plan, "common": common, "data_manifest_sha256": file_hash(data_dir / "manifest.json"),
              "study_sha256": file_hash(study_path), "comparison_script_sha256": file_hash(Path(__file__)),
              "adapters": {f"user_{uid}_epoch_{epoch}": info for (uid, epoch), info in adapters.items()},
              "prompt_builder_sha256": file_hash(ROOT / "common_llm.py"),
              "writing_prompts_sha256": file_hash(ROOT / "writing_prompts.py"), "cases": []}
    cache = {}
    for uid, cases in evaluation_cases(data_dir, datasets, split).items():
        for case in cases:
            for epoch in epochs:
                entry = {"user_id": uid, "case_id": case["id"], "epoch": epoch,
                         "material": {key: case[key] for key in ("document_type", "topic", "facts")},
                         "reference": case.get("reference"), "review": {key: None for key in (
                             "facts_preserved", "no_invented_claims", "style_preference", "genre_appropriate", "notes")}}
                for condition in CONDITIONS:
                    settings = condition.endswith("settings")
                    adapter_name = "common" if condition.startswith("common_") else f"user_{uid}_epoch_{epoch}"
                    request = request_for(case, uid, settings, target_chars)
                    cache_key = value_hash([adapter_name, request])
                    if cache_key not in cache:
                        if adapter_name not in loaded:
                            model.load_adapter(adapters[uid, epoch]["path"], adapter_name=adapter_name, is_trainable=False)
                            loaded.add(adapter_name)
                        model.set_adapter(adapter_name)
                        model.requires_grad_(False)
                        model.eval()
                        kind, messages = messages_for(DraftRequest(**request))
                        encoded = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
                        if len(processor.tokenizer(encoded, add_special_tokens=False)["input_ids"]) > 2048:
                            messages = [messages[0], messages[-1]]
                            encoded = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
                        if len(processor.tokenizer(encoded, add_special_tokens=False)["input_ids"]) > 2048:
                            raise ValueError(f"Input exceeds the service's token limit: {case['id']}")
                        print(uid, case["id"], epoch, condition, flush=True)
                        answer = generate(model, processor, messages, 768, "greedy", 42, "chat")
                        answer["text_before_service_cleanup"] = answer["text"]
                        answer["text"] = finish_text(answer["text"], kind)
                        answer["char_count"] = len(answer["text"])
                        answer["length_compliant"] = round(request["target_chars"] * .8) <= answer["char_count"] <= round(request["target_chars"] * 1.2)
                        answer["request"] = request
                        answer["effective_prompt"] = messages
                        cache[cache_key] = answer
                    entry[condition] = cache[cache_key]
                result["cases"].append(entry)
                (directory / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = []
    for case in result["cases"]:
        lines.extend([f"User {case['user_id']} / {case['case_id']} / epoch {case['epoch']}", json.dumps(case["material"], ensure_ascii=False)])
        for condition in CONDITIONS:
            lines.extend([f"[{condition}] {case[condition]['char_count']} chars / length compliant: {case[condition]['length_compliant']}", case[condition]["text"]])
        lines.append("")
    (directory / "comparison.txt").write_text("\n".join(lines), encoding="utf-8")
    print("Comparison saved:", directory)
    print("Manual fact/style review is required. No model was selected for serving.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--study-dir", type=Path)
    parser.add_argument("--split", choices=("valid", "test", "transfer"), default="valid")
    parser.add_argument("--epochs", type=int, nargs="+", choices=(1, 2, 3), default=[1, 2, 3])
    parser.add_argument("--target-chars", type=int, default=160, choices=range(100, 901))
    parser.add_argument("--output-dir", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--generate", action="store_true")
    args = parser.parse_args()
    if len(args.epochs) != len(set(args.epochs)):
        parser.error("--epochs must not contain duplicates")
    if args.split != "valid" and len(args.epochs) != 1:
        parser.error("Select one epoch using validation before evaluating test/transfer")
    data_dir = (args.data_dir if args.data_dir.is_absolute() else ROOT / args.data_dir).resolve()
    manifest, datasets = load_prepared(data_dir)
    plan = comparison_plan(data_dir, datasets, args.split, args.epochs, args.target_chars)
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if not args.generate:
        print("CPU plan only. No model was loaded.")
        return
    if args.study_dir is None:
        parser.error("--generate requires --study-dir")
    study = (args.study_dir if args.study_dir.is_absolute() else ROOT / args.study_dir).resolve()
    output = None if args.output_dir is None else (args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir).resolve()
    if output is not None:
        protected = (data_dir, (ROOT / "outputs/personalized").resolve())
        if any(output == path or path in output.parents for path in protected):
            parser.error("Write comparisons outside training data and serving-adapter folders")
    generate_comparison(data_dir, datasets, study, args.epochs, args.split, args.target_chars, output)


if __name__ == "__main__":
    main()
