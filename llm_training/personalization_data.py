"""CPU-only checks for isolated, synthetic personalization experiments."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

MODEL_ID = "Qwen/Qwen3.5-2B"
SPLITS = ("train", "valid", "test")
PROFILES = {
    6: {"account_key": "demo_concise", "style": "간결", "user_preferences": {
        "preferred_tone": "natural", "sentence_length": "short", "feedback_style": "brief", "ai_assistance": "balanced"}},
    7: {"account_key": "demo_formal", "style": "격식", "user_preferences": {
        "preferred_tone": "formal", "sentence_length": "normal", "feedback_style": "detailed", "ai_assistance": "balanced"}},
    8: {"account_key": "demo_friendly", "style": "친근", "user_preferences": {
        "preferred_tone": "natural", "sentence_length": "normal", "feedback_style": "detailed", "ai_assistance": "balanced"}},
}


def file_hash(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def value_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def normalized(text):
    return re.sub(r"\s+", "", text)


def read_jsonl(path):
    result = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError as exc:
            raise ValueError(f"{path}:{number}: invalid JSON") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{number}: expected an object")
        result.append(row)
    if not result:
        raise ValueError(f"Empty dataset: {path}")
    return result


def parse_facts(row):
    text = row["prompt"][-1]["content"]
    facts = re.findall(r"^- (.+)$", text, re.MULTILINE)
    genre = re.search(r"^글 유형:\s*(.+)$", text, re.MULTILINE)
    topic = re.search(r"^주제:\s*(.+)$", text, re.MULTILINE)
    if not facts or not genre or not topic:
        raise ValueError(f"Cannot identify genre/topic/facts: {row.get('id')}")
    return {"document_type": genre[1].strip(), "topic": topic[1].strip(), "facts": facts}


def validate_row(row, user_id, split):
    if not isinstance(row.get("id"), str) or not row["id"].strip():
        raise ValueError("Every record needs a nonempty id")
    prompt, completion, meta = row.get("prompt"), row.get("completion"), row.get("metadata")
    if not isinstance(prompt, list) or not prompt or not isinstance(prompt[-1], dict) or prompt[-1].get("role") != "user":
        raise ValueError(f"Invalid prompt: {row['id']}")
    if not isinstance(completion, list) or len(completion) != 1 or not isinstance(completion[0], dict) or completion[0].get("role") != "assistant":
        raise ValueError(f"Invalid completion: {row['id']}")
    for message in prompt + completion:
        if (not isinstance(message, dict) or message.get("role") not in {"system", "user", "assistant"}
                or not isinstance(message.get("content"), str) or not message["content"].strip()):
            raise ValueError(f"Invalid message: {row['id']}")
    if not isinstance(meta, dict) or type(meta.get("user_id")) is not int or meta["user_id"] != user_id:
        raise ValueError(f"User ownership mismatch: {row['id']}")
    if meta.get("split") != split or meta.get("account_key") != PROFILES[user_id]["account_key"]:
        raise ValueError(f"Split/profile mismatch: {row['id']}")
    if meta.get("synthetic") is not True or meta.get("human_approved") is not False or meta.get("common_training_allowed") is not False:
        raise ValueError(f"Demo provenance must be explicit: {row['id']}")
    if not isinstance(meta.get("case_id"), str) or not meta["case_id"]:
        raise ValueError(f"Missing case group: {row['id']}")
    material = parse_facts(row)
    if material["document_type"] not in ("보고서", "자기소개서", "발표문", "자유 글쓰기"):
        raise ValueError(f"Unsupported genre: {row['id']}")
    if material["document_type"] != meta.get("genre"):
        raise ValueError(f"Genre mismatch: {row['id']}")
    return material


def audit_dataset(source):
    source = Path(source)
    datasets, sources, warnings, profiles = {}, [], [], []
    cases, ids, input_splits, answer_splits, owned_inputs, group_splits = {}, set(), {}, {}, set(), {}
    for user_id in PROFILES:
        datasets[user_id] = {}
        lengths, joined, genres, fact_counts = [], 0, Counter(), Counter()
        for split in SPLITS:
            path = source / f"user_{user_id}" / f"{split}.jsonl"
            rows = read_jsonl(path)
            datasets[user_id][split] = rows
            sources.append({"path": path.relative_to(source).as_posix(), "count": len(rows), "sha256": file_hash(path)})
            for row in rows:
                material = validate_row(row, user_id, split)
                if row["id"] in ids:
                    raise ValueError(f"Duplicate record id: {row['id']}")
                ids.add(row["id"])
                group = row["metadata"]["case_id"]
                scenario_group = row["metadata"].get("group_id", group)
                if group_splits.setdefault(scenario_group, split) != split:
                    raise ValueError(f"Case leakage: scenario variants cross splits: {scenario_group}")
                seen = cases.setdefault(group, {"split": split, "material": material, "users": set()})
                if seen["split"] != split or seen["material"] != material or user_id in seen["users"]:
                    raise ValueError(f"Case leakage or mismatched matched-case input: {group}")
                seen["users"].add(user_id)
                input_key = value_hash(material)
                if (user_id, input_key) in owned_inputs:
                    raise ValueError(f"Duplicate material for one user: {row['id']}")
                owned_inputs.add((user_id, input_key))
                old_split = input_splits.setdefault(input_key, split)
                if old_split != split:
                    raise ValueError(f"Same material crosses splits: {row['id']}")
                answer = row["completion"][0]["content"].strip()
                answer_key = (user_id, normalized(answer))
                old_split = answer_splits.setdefault(answer_key, split)
                if old_split != split:
                    raise ValueError(f"Same answer crosses splits: {row['id']}")
                lengths.append(len(answer))
                joined += answer == " ".join(material["facts"])
                genres[material["document_type"]] += 1
                fact_counts[len(material["facts"])] += 1
        profiles.append({"user_id": user_id, **deepcopy(PROFILES[user_id]),
                         "counts": {split: len(rows) for split, rows in datasets[user_id].items()},
                         "genres": dict(genres), "answer_chars": {"min": min(lengths), "mean": round(sum(lengths) / len(lengths), 1), "max": max(lengths)},
                         "exact_fact_join_answers": joined, "fact_counts": dict(fact_counts),
                         "below_service_short_lower_bound_128": sum(n < 128 for n in lengths)})
    if any(case["users"] != set(PROFILES) for case in cases.values()):
        raise ValueError("The three profiles must share the same cases and splits")
    manifest_path = source / "manifest.json"
    stale = []
    if manifest_path.is_file():
        old = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        declared = {item["path"].replace("\\", "/"): item for item in old.get("files", [])}
        for actual in sources:
            previous = declared.get(actual["path"], {})
            if previous.get("count") != actual["count"] or previous.get("sha256") != actual["sha256"]:
                stale.append({"path": actual["path"], "declared_count": previous.get("count"), "actual_count": actual["count"]})
    else:
        warnings.append("The source has no manifest; provenance was not verified against a database.")
    if stale:
        warnings.append("The source manifest is stale; actual file counts/hashes are recorded in this snapshot.")
    warnings.extend([
        "Synthetic, unapproved demo data; not evidence of any real user's writing style.",
        "Only six validation and six test cases per profile; results are exploratory.",
        "All legacy targets are shorter than the service's short-output range (128-192 characters).",
        "The concise profile joins complete input sentences unchanged; it weakly tests rewriting ability.",
        "Legacy test examples have been inspected during dataset preparation; use separate new prompts for final transfer checks.",
    ])
    return datasets, {"profiles": profiles, "sources": sources, "unique_cases": len(cases),
                      "stale_manifest_files": stale, "warnings": warnings,
                      "structural_checks_passed": True, "production_ready": False,
                      "semantic_fact_review_completed": False}


def load_prepared(folder):
    folder = Path(folder).resolve()
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    version = manifest.get("kind")
    if version not in ("synthetic_personalization_pilot_v1", "synthetic_personalization_pilot_v2") or manifest.get("demo_only") is not True:
        raise ValueError("Expected a prepared synthetic demo dataset")
    if manifest.get("profiles") != [{"user_id": uid, **profile} for uid, profile in PROFILES.items()]:
        raise ValueError("The prepared profile definitions changed")
    audit_path = folder / "audit.json"
    if file_hash(audit_path) != manifest.get("audit_sha256"):
        raise ValueError("Prepared audit hash mismatch")
    expected_paths = {f"user_{uid}/{split}.jsonl" for uid in PROFILES for split in SPLITS}
    if set(item["path"] for item in manifest["files"]) != expected_paths:
        raise ValueError("Prepared file list does not match the three users and splits")
    for item in manifest["files"]:
        path = folder / item["path"]
        if file_hash(path) != item["sha256"] or len(read_jsonl(path)) != item["count"]:
            raise ValueError(f"Prepared file changed: {item['path']}")
    datasets, checked = audit_dataset(folder)
    if version == "synthetic_personalization_pilot_v2":
        from build_personalization_v2 import supported_facts, validate_authored_row
        bank = manifest["source_bank"]
        bank_path = (folder / bank["path"]).resolve()
        if folder not in bank_path.parents or file_hash(bank_path) != bank["sha256"]:
            raise ValueError("Source scenario bank changed")
        scenarios = {item["id"]: item for item in json.loads(bank_path.read_text(encoding="utf-8"))}
        for splits in datasets.values():
            for rows in splits.values():
                for row in rows:
                    meta = row["metadata"]
                    scenario = scenarios[meta["group_id"]]
                    if value_hash(scenario) != meta["source_scenario_sha256"]:
                        raise ValueError("Source scenario fingerprint mismatch")
                    allowed = {fact["id"]: fact for fact in supported_facts(scenario)}
                    if any(allowed.get(fact["id"]) != fact for fact in meta["evidence_facts"]):
                        raise ValueError("A completion uses facts outside the source scenario")
                    validate_authored_row(row)
        for item in [*manifest.get("legacy_files", []), manifest["review_file"]]:
            path = (folder / item["path"]).resolve()
            if folder not in path.parents or file_hash(path) != item["sha256"]:
                raise ValueError("Legacy/review snapshot changed")
    for item in manifest.get("evaluation_files", []):
        path = (folder / item["path"]).resolve()
        if folder not in path.parents or file_hash(path) != item["sha256"]:
            raise ValueError("Evaluation input changed")
    return manifest, datasets


def adapter_fingerprint(folder):
    folder = Path(folder).resolve()
    config = json.loads((folder / "adapter_config.json").read_text(encoding="utf-8"))
    if config.get("base_model_name_or_path", "").rstrip("/") != MODEL_ID or config.get("peft_type") != "LORA":
        raise ValueError("Expected a Qwen3.5-2B LoRA adapter")
    weights = sorted(folder.glob("adapter_model*.safetensors"))
    if not weights:
        raise ValueError("The common adapter has no safetensors weights")
    files = {"adapter_config.json": file_hash(folder / "adapter_config.json")}
    files.update({p.name: file_hash(p) for p in weights})
    return {"path": str(folder), "files": files, "sha256": value_hash(files)}
