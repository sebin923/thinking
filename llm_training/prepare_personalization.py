"""Freeze the three existing synthetic profiles without training or changing source data.

python prepare_personalization.py --output data/personalization_demo_v1
"""
import argparse
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path

from personalization_data import PROFILES, SPLITS, audit_dataset, file_hash, parse_facts, value_hash

ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE = ROOT.parent / "backend/personalization_setup/export_20261110_161038_544356"


def prepare(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("Output already exists; choose a new snapshot directory")
    datasets, audit = audit_dataset(source)
    output.mkdir(parents=True)
    manifest = {"kind": "synthetic_personalization_pilot_v1", "demo_only": True,
                "human_approved": False, "common_training_allowed": False, "production_ready": False,
                "source_directory": str(source), "source_database_links_reverified": False,
                "source_manifest_sha256": file_hash(source / "manifest.json") if (source / "manifest.json").is_file() else None,
                "profiles": [{"user_id": uid, **profile} for uid, profile in PROFILES.items()], "files": [],
                "training_policy": "Continue a selected common LoRA independently for each user; never train on valid/test or mix profiles.",
                "activation_policy": "Save experiment checkpoints outside outputs/personalized; no automatic serving selection."}
    review = []
    for user_id, splits in datasets.items():
        folder = output / f"user_{user_id}"
        folder.mkdir()
        for split in SPLITS:
            rows = []
            for original in splits[split]:
                row = deepcopy(original)
                row["metadata"]["source_record_sha256"] = value_hash(original)
                row["metadata"]["demo_only"] = True
                rows.append(row)
                if split == "train":
                    material = parse_facts(row)
                    answer = row["completion"][0]["content"].strip()
                    review.append({"user_id": user_id, "id": row["id"], "split": split,
                                   "issues": ["short_target", *( ["exact_fact_join"] if answer == " ".join(material["facts"]) else [])],
                                   "material": material, "answer": answer,
                                   "fact_preservation_review": "pending", "style_review": "pending", "human_approved": False})
            path = folder / f"{split}.jsonl"
            path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
            manifest["files"].append({"path": path.relative_to(output).as_posix(), "count": len(rows), "sha256": file_hash(path)})
    (output / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest["audit_sha256"] = file_hash(output / "audit.json")
    review_path = output / "train_review_queue.jsonl"
    review_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in review), encoding="utf-8")
    eval_source = ROOT / "personalization_eval_cases.json"
    if eval_source.is_file():
        cases = json.loads(eval_source.read_text(encoding="utf-8"))
        old_material = {value_hash(parse_facts(row)) for splits in datasets.values() for rows in splits.values() for row in rows}
        if any(value_hash({key: case[key] for key in ("document_type", "topic", "facts")}) in old_material for case in cases):
            raise ValueError("New transfer evaluation input overlaps legacy material")
        destination = output / "transfer_eval_cases.json"
        destination.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest["evaluation_files"] = [{"path": destination.name, "count": len(cases), "sha256": file_hash(destination)}]
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    plan = {"data": str(output), "model": "Qwen/Qwen3.5-2B", "demo_only": True,
            "train_users_independently": [6, 7, 8], "epochs_to_compare": [1, 2, 3],
            "conditions": ["common_neutral", "common_settings", "personal_neutral", "personal_settings"],
            "selection_split": "valid", "final_splits": ["test", "transfer"],
            "decoding": {"do_sample": False, "seed": 42, "max_new_tokens": 768, "stop_policy": "chat"},
            "manual_review": ["unsupported facts", "subject/time/negation preserved", "genre appropriate", "style preference", "repetition", "length compliance"],
            "minimum_claim": "A controlled demo; improved loss or shorter answers alone do not establish personalization.",
            "expansion_priorities": ["notes that need rewriting rather than joined complete sentences", "richer independent topics and longer supported answers", "explicit negation, uncertain outcomes and time order", "more held-out topics in each genre"]}
    (output / "experiment_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or ROOT / "data" / ("personalization_demo_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    if not output.is_absolute():
        output = ROOT / output
    manifest, audit = prepare(args.source, output)
    print("Prepared:", output)
    for profile in audit["profiles"]:
        print(profile["user_id"], profile["style"], profile["counts"], profile["answer_chars"])
    print("Source manifest mismatches:", len(audit["stale_manifest_files"]))
    print("Demo only. No training, model activation or database changes performed.")


if __name__ == "__main__":
    main()
