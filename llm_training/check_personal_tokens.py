"""Count tokens locally using the saved tokenizer and chat template; no Torch/GPU.

Requires tokenizers and jinja2. Never downloads model weights or truncates data.
"""
import argparse
import json
from pathlib import Path

from personalization_data import file_hash, load_prepared


def check_tokens(data_dir, tokenizer_dir):
    from jinja2.sandbox import ImmutableSandboxedEnvironment
    from tokenizers import Tokenizer

    manifest, datasets = load_prepared(data_dir)
    tokenizer_path = tokenizer_dir / "tokenizer.json"
    template_path = tokenizer_dir / "chat_template.jinja"
    config = json.loads((tokenizer_dir / "tokenizer_config.json").read_text(encoding="utf-8"))
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    env = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True, extensions=["jinja2.ext.loopcontrols"])
    def fail(message):
        raise ValueError(message)
    env.globals["raise_exception"] = fail
    template = env.from_string(template_path.read_text(encoding="utf-8"))
    eos = config.get("eos_token")
    eos = eos.get("content") if isinstance(eos, dict) else eos
    eos_id = tokenizer.token_to_id(eos)
    if eos_id is None:
        raise ValueError("Cannot identify the saved tokenizer EOS")
    result = {"tokenizer_sha256": file_hash(tokenizer_path), "chat_template_sha256": file_hash(template_path),
              "model_weights_loaded": False, "gpu_used": False, "profiles": [], "violations": []}
    maximum = manifest.get("training_max_sequence_length", 1024)
    for uid, splits in datasets.items():
        prefixes, totals = [], []
        for split, rows in splits.items():
            for row in rows:
                prefix = template.render(messages=row["prompt"], add_generation_prompt=True, enable_thinking=False,
                                         bos_token=config.get("bos_token"), eos_token=eos)
                prefix_ids = tokenizer.encode(prefix, add_special_tokens=False).ids
                answer_ids = tokenizer.encode(row["completion"][0]["content"], add_special_tokens=False).ids
                prefixes.append(len(prefix_ids))
                totals.append(len(prefix_ids) + len(answer_ids) + 1)
                if len(prefix_ids) > 2048 or totals[-1] > maximum:
                    result["violations"].append({"id": row["id"], "split": split, "input_tokens": len(prefix_ids), "total_tokens": totals[-1]})
        result["profiles"].append({"user_id": uid, "records": len(totals), "maximum_input_tokens": max(prefixes),
                                   "maximum_total_tokens": max(totals), "training_limit": maximum, "generation_input_limit": 2048})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--tokenizer-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = check_tokens(args.data_dir.resolve(), args.tokenizer_dir.resolve())
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["violations"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
