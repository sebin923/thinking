import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from compare_personal import comparison_plan, request_for
from personalization_data import PROFILES, SPLITS, adapter_fingerprint, audit_dataset, file_hash, load_prepared
from prepare_personalization import prepare
from train_personal import train_user


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "source"
    for uid, profile in PROFILES.items():
        folder = root / f"user_{uid}"
        folder.mkdir(parents=True)
        for split in SPLITS:
            row = {"id": f"{uid}_{split}", "prompt": [
                {"role": "system", "content": "입력한 사실만 사용한다."},
                {"role": "user", "content": f"글 유형: 보고서\n주제: {split} 점검\n제공한 내용:\n- {split} 자료를 확인했다.\n- 차이를 기록했다.\n- 담당자에게 전달했다."}],
                "completion": [{"role": "assistant", "content": f"{split} 자료를 확인하고 차이를 기록해 전달했다. {uid}"}],
                "metadata": {"user_id": uid, "account_key": profile["account_key"], "split": split, "genre": "보고서", "case_id": split,
                             "synthetic": True, "human_approved": False, "common_training_allowed": False}}
            (folder / f"{split}.jsonl").write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps({"files": [{"path": "user_6/train.jsonl", "count": 99, "sha256": "old"}]}), encoding="utf-8")
    return root


def rewrite(path, change):
    row = json.loads(path.read_text(encoding="utf-8"))
    change(row)
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")


def test_preparation_preserves_sources_targets_and_splits(source, tmp_path):
    before = {str(path): file_hash(path) for path in source.rglob("*") if path.is_file()}
    output = tmp_path / "prepared"
    manifest, audit = prepare(source, output)
    assert before == {str(path): file_hash(path) for path in source.rglob("*") if path.is_file()}
    assert manifest["demo_only"] is True and manifest["production_ready"] is False
    assert len(audit["stale_manifest_files"]) == 9
    assert audit["semantic_fact_review_completed"] is False
    loaded, rows = load_prepared(output)
    for uid in PROFILES:
        for split in SPLITS:
            original = json.loads((source / f"user_{uid}/{split}.jsonl").read_text(encoding="utf-8"))
            assert rows[uid][split][0]["completion"] == original["completion"]
            assert rows[uid][split][0]["prompt"] == original["prompt"]
            assert rows[uid][split][0]["metadata"]["split"] == split
    assert len(loaded["evaluation_files"]) == 1
    assert len(json.loads((output / "transfer_eval_cases.json").read_text(encoding="utf-8"))) == 12


def test_owner_mix_is_rejected(source):
    rewrite(source / "user_6/train.jsonl", lambda r: r["metadata"].update(user_id=7))
    with pytest.raises(ValueError, match="ownership"):
        audit_dataset(source)


@pytest.mark.parametrize("key,value", [("synthetic", False), ("human_approved", True), ("common_training_allowed", True)])
def test_synthetic_provenance_is_not_promoted(source, key, value):
    rewrite(source / "user_6/train.jsonl", lambda r: r["metadata"].update({key: value}))
    with pytest.raises(ValueError, match="provenance"):
        audit_dataset(source)


def test_case_group_cannot_cross_splits(source):
    rewrite(source / "user_6/valid.jsonl", lambda r: r["metadata"].update(case_id="train"))
    with pytest.raises(ValueError, match="Case leakage"):
        audit_dataset(source)


def test_paired_profiles_must_receive_same_material(source):
    rewrite(source / "user_7/train.jsonl", lambda r: r["prompt"][-1].update(content=r["prompt"][-1]["content"].replace("차이를 기록했다", "다른 사실이다")))
    with pytest.raises(ValueError, match="mismatched"):
        audit_dataset(source)


def test_prepared_file_tampering_is_rejected(source, tmp_path):
    output = tmp_path / "prepared"
    prepare(source, output)
    rewrite(output / "user_6/train.jsonl", lambda r: r["completion"][0].update(content="changed"))
    with pytest.raises(ValueError, match="file changed"):
        load_prepared(output)


def test_existing_snapshot_is_not_overwritten(source, tmp_path):
    output = tmp_path / "prepared"
    output.mkdir()
    with pytest.raises(ValueError, match="already exists"):
        prepare(source, output)


def test_factorial_comparison_controls_settings(source, tmp_path):
    output = tmp_path / "prepared"
    prepare(source, output)
    manifest, datasets = load_prepared(output)
    plan = comparison_plan(output, datasets, "valid", [1, 2, 3], 160)
    assert plan["logical_comparisons"] == 36
    assert plan["maximum_actual_generations_with_cached_common"] < 36
    case = {"document_type": "보고서", "topic": "점검", "facts": ["차이가 있었다."]}
    neutral = request_for(case, 6, False)
    settings = request_for(case, 6, True)
    assert neutral["facts"] == settings["facts"]
    assert neutral["target_chars"] == settings["target_chars"]
    assert neutral["user_preferences"] is None
    assert settings["user_preferences"]["sentence_length"] == "short"


def test_check_data_does_not_import_gpu_dependencies(source, tmp_path):
    output = tmp_path / "prepared"
    prepare(source, output)
    code = "import runpy,sys; sys.path.insert(0,sys.argv[1]); sys.argv=['train_personal.py','--data-dir',sys.argv[2],'--check-data']; runpy.run_module('train_personal',run_name='__main__'); assert 'torch' not in sys.modules; assert 'transformers' not in sys.modules"
    result = subprocess.run([sys.executable, "-c", code, str(ROOT), str(output)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_final_test_requires_one_selected_epoch(source, tmp_path):
    output = tmp_path / "prepared"
    prepare(source, output)
    result = subprocess.run([sys.executable, str(ROOT / "compare_personal.py"), "--data-dir", str(output), "--split", "test", "--plan"], capture_output=True, text=True)
    assert result.returncode != 0 and "Select one epoch" in result.stderr


def test_adapter_requires_real_matching_weights(tmp_path):
    folder = tmp_path / "adapter"
    folder.mkdir()
    (folder / "adapter_config.json").write_text(json.dumps({"base_model_name_or_path": "Qwen/Qwen3.5-2B", "peft_type": "LORA"}))
    with pytest.raises(ValueError, match="no safetensors"):
        adapter_fingerprint(folder)
    (folder / "adapter_model.safetensors").write_bytes(b"fake-weight-fixture")
    first = adapter_fingerprint(folder)
    (folder / "adapter_model.safetensors").write_bytes(b"different-weight-fixture")
    assert adapter_fingerprint(folder)["sha256"] != first["sha256"]


def test_training_continues_common_adapter_and_never_tokenizes_test(source, tmp_path, monkeypatch):
    datasets, _ = audit_dataset(source)
    config = SimpleNamespace(use_cache=True, text_config=SimpleNamespace(use_cache=True), _commit_hash="test-commit")
    base = SimpleNamespace(config=config)
    model = Mock(config=config)
    tokenizer = SimpleNamespace(eos_token_id=2, eos_token="<end>", pad_token_id=None, pad_token=None, padding_side="left")
    processor = SimpleNamespace(tokenizer=tokenizer)
    modules = {name: ModuleType(name) for name in ("torch", "peft", "transformers", "train_qwen35")}
    modules["torch"].cuda = SimpleNamespace(is_available=lambda: True, is_bf16_supported=lambda: True, empty_cache=lambda: None)
    modules["torch"].bfloat16 = "bf16"
    peft_load = Mock(return_value=model)
    modules["peft"].PeftModel = SimpleNamespace(from_pretrained=peft_load)
    modules["transformers"].AutoProcessor = SimpleNamespace(from_pretrained=Mock(return_value=processor))
    modules["transformers"].Qwen3_5ForConditionalGeneration = SimpleNamespace(from_pretrained=Mock(return_value=base))
    modules["transformers"].DataCollatorForSeq2Seq = Mock()
    modules["transformers"].TrainingArguments = lambda **kw: SimpleNamespace(**kw)
    modules["transformers"].set_seed = Mock()
    trainer = SimpleNamespace(train=Mock(return_value=SimpleNamespace(metrics={"train_loss": 1.0})))
    modules["transformers"].Trainer = Mock(return_value=trainer)
    modules["train_qwen35"].EpochMonitor = type("FakeMonitor", (), {})
    tokenized_splits = []
    def tokenize(rows, proc, name):
        tokenized_splits.append(name)
        return SimpleNamespace(select=lambda indices: "smoke dataset")
    modules["train_qwen35"].tokenize_rows = tokenize
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    (source / "manifest.json").write_text("{}")
    parent = tmp_path / "parent"
    parent.mkdir()
    parent_file = parent / "adapter_model.safetensors"
    parent_file.write_bytes(b"unchanged parent")
    before = file_hash(parent_file)
    output = tmp_path / "experiment"
    train_user(6, datasets[6], {"path": str(parent), "sha256": "parent-fingerprint"}, output, 3, True, source)
    assert peft_load.call_args.kwargs["is_trainable"] is True
    assert peft_load.call_args.args == (base, str(parent))
    assert tokenized_splits == ["user_6/train", "user_6/valid"]
    assert file_hash(parent_file) == before
    metrics = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["initialization"] == "continued_common_lora" and metrics["fresh_lora"] is False
