import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

SPEC = importlib.util.spec_from_file_location("check_gpu_server", Path(__file__).parents[1] / "check_gpu_server.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def make_run(tmp_path):
    adapter = tmp_path / "run" / "adapter"
    adapter.mkdir(parents=True)
    (adapter / "adapter_config.json").write_text(json.dumps({"base_model_name_or_path": module.MODEL_ID}))
    (adapter / "adapter_model.safetensors").write_bytes(b"test-only")
    return adapter


def test_partial_run_cannot_be_started(tmp_path):
    adapter = make_run(tmp_path)
    with pytest.raises(ValueError, match="final metrics"):
        module.completed_adapter(adapter)
    (adapter.parent / "metrics.json").write_text(json.dumps({"epochs": 3, "train": {"train_runtime": 10}, "after": {"epoch": 1, "eval_loss": 0.4}}))
    with pytest.raises(ValueError, match="not completed"):
        module.completed_adapter(adapter)


def test_finished_run_is_not_quality_approval(tmp_path):
    adapter = make_run(tmp_path)
    (adapter.parent / "metrics.json").write_text(json.dumps({"epochs": 1, "train": {"train_runtime": 10}, "after": {"epoch": 1, "eval_loss": 0.4}}))
    result = module.completed_adapter(adapter)
    assert result["training_complete"] is True
    assert result["quality_approved"] is False


def test_epoch_checkpoint_requires_whole_run_completion(tmp_path):
    adapter = make_run(tmp_path / "run" / "epoch_1")
    # Construct the real epoch layout explicitly.
    epoch_adapter = tmp_path / "study" / "epoch_1" / "adapter"
    epoch_adapter.mkdir(parents=True)
    for name in ("adapter_config.json", "adapter_model.safetensors"):
        (epoch_adapter / name).write_bytes((adapter / name).read_bytes())
    (epoch_adapter.parent / "metrics.json").write_text(json.dumps({"after": {"eval_loss": 0.4}}))
    with pytest.raises(ValueError, match="final metrics"):
        module.completed_adapter(epoch_adapter)
    (epoch_adapter.parents[1] / "metrics.json").write_text(json.dumps({"epochs": 3, "train": {"train_runtime": 20}, "after": {"epoch": 3, "eval_loss": 0.2}}))
    assert module.completed_adapter(epoch_adapter)["run"] == "study"


def test_launcher_defaults_to_checks_only(monkeypatch):
    spec = importlib.util.spec_from_file_location("gpu_server", Path(__file__).parents[1] / "gpu_server.py")
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    monkeypatch.setattr(sys, "argv", ["gpu_server.py"])
    monkeypatch.setattr(launcher.subprocess, "run", Mock(return_value=SimpleNamespace(returncode=0)))
    start = Mock(side_effect=AssertionError("preflight must not start an API"))
    monkeypatch.setattr(launcher.subprocess, "Popen", start)
    assert launcher.main() == 0
    start.assert_not_called()


def test_start_requires_explicit_selection(monkeypatch):
    spec = importlib.util.spec_from_file_location("gpu_server", Path(__file__).parents[1] / "gpu_server.py")
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    monkeypatch.setattr(sys, "argv", ["gpu_server.py", "--start"])
    with pytest.raises(SystemExit) as exc:
        launcher.main()
    assert exc.value.code == 2
