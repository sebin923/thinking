"""Check the Windows inference host without loading model weights or starting services."""
import argparse
import importlib.metadata
import json
import math
from pathlib import Path

MODEL_ID = "Qwen/Qwen3.5-2B"


def completed_adapter(value):
    """Require an explicit adapter from a finished run, including epoch studies."""
    adapter = Path(value).expanduser().resolve()
    for name in ("adapter_config.json", "adapter_model.safetensors"):
        path = adapter / name
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f"Missing adapter file: {path}")
    config = json.loads((adapter / "adapter_config.json").read_text(encoding="utf-8"))
    if config.get("base_model_name_or_path", "").rstrip("/") != MODEL_ID:
        raise ValueError(f"Adapter must use {MODEL_ID}")
    stage = adapter.parent
    run = stage.parent if stage.name.startswith("epoch_") else stage
    metrics_path = run / "metrics.json"
    if not metrics_path.is_file():
        raise ValueError("Run has no final metrics.json; training may still be running")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    train, after = metrics.get("train", {}), metrics.get("after", {})
    epochs = metrics.get("epochs")
    loss = after.get("eval_loss")
    if not isinstance(epochs, (int, float)) or epochs <= 0:
        raise ValueError("Final training epoch count is missing")
    if not train.get("train_runtime", 0) > 0 or after.get("epoch", 0) < epochs:
        raise ValueError("Run has not completed training and final evaluation")
    if not isinstance(loss, (int, float)) or not math.isfinite(loss):
        raise ValueError("Final evaluation loss is missing or invalid")
    if stage.name.startswith("epoch_"):
        stage_metrics = stage / "metrics.json"
        if not stage_metrics.is_file():
            raise ValueError("Selected epoch has no evaluation metrics")
    return {"adapter": str(adapter), "run": run.name, "training_complete": True,
            "quality_approved": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", help="Explicit completed common adapter; no automatic selection")
    args = parser.parse_args()
    result = {"services_started": False}
    try:
        result["versions"] = {name: importlib.metadata.version(name) for name in
                              ("torch", "transformers", "peft", "accelerate", "fastapi", "uvicorn")}
        import torch
        result["cuda"] = torch.cuda.is_available()
        result["bf16"] = result["cuda"] and torch.cuda.is_bf16_supported()
        if not result["bf16"]:
            raise ValueError("CUDA and BF16 support are required")
        result["gpu"] = torch.cuda.get_device_name(0)
        result["selected_model"] = completed_adapter(args.adapter) if args.adapter else None
        result["host_ready"] = True
    except (ValueError, OSError, ImportError, RuntimeError) as exc:
        result.update(host_ready=False, error=str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["host_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
