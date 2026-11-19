"""Build three synthetic writing styles from a shared, explicit fact bank.

CPU only. No LLM calls, model training, database writes or mutation of v1 files.
All output clauses are deterministic paraphrases of selected source facts.
"""
import argparse
from collections import Counter
from copy import deepcopy
from itertools import combinations
import json
from pathlib import Path
import re
from types import SimpleNamespace

from personalization_data import PROFILES, SPLITS, file_hash, value_hash
from personalization_scenarios_v2 import SCENARIOS
from writing_prompts import _polite_word, build_messages, finish_text

ROOT = Path(__file__).resolve().parent
TARGETS = (160, 350, 500)
RECIPE = "controlled_fact_paraphrases_v2"


def nominal_note(text):
    stem = text.rstrip(".")
    for ending, replacement in (("아니다", "아님"), ("이다", "임"), ("한다", "함"), ("된다", "됨"), ("는다", "음")):
        if stem.endswith(ending):
            return stem[:-len(ending)] + replacement
    if not stem.endswith("다"):
        raise ValueError(f"Unsupported canonical ending: {text}")
    syllable = ord(stem[-2])
    if 0xAC00 <= syllable <= 0xD7A3 and (syllable - 0xAC00) % 28 == 4:
        return stem[:-2] + chr(syllable - 4 + 16)
    return stem[:-1] + "음"


def formal_words(text):
    return text.replace("했다", "하였다").replace("봤다", "보았다").replace("따로", "별도로")


def easy_words(text):
    for old, new in (
        ("별도로", "따로"), ("기재했다", "적었다"), ("기재하였다", "적었다"),
        ("동일한", "같은"), ("해당 ", "그 "), ("사본", "복사본"),
        ("대조하는", "서로 비교하는"), ("대조했다", "서로 비교했다"),
        ("대조한", "서로 비교한"), ("대조할", "서로 비교할"),
        ("수령한", "받은"), ("수령 표시", "받았다는 표시"),
        ("자료만으로는", "이 자료만 보고는"), ("확인 시점", "확인한 때"),
        ("원본 파일", "원래 파일"), ("이후", "그 뒤"), ("현재", "지금"),
    ):
        text = text.replace(old, new)
    return text


def connective(text):
    stem = text.rstrip(".")
    if not stem.endswith("다"):
        raise ValueError(f"Cannot coordinate clause: {text}")
    if stem.endswith("는다"):
        return stem[:-2] + "으며"
    stem = stem[:-1]
    syllable = ord(stem[-1])
    if not 0xAC00 <= syllable <= 0xD7A3:
        raise ValueError("Expected Korean sentence ending")
    final = (syllable - 0xAC00) % 28
    if final == 4:  # Declarative -nda -> -myeo; keep tense and negation.
        stem = stem[:-1] + chr(syllable - final)
        return stem + "며"
    return stem + ("며" if final == 0 else "으며")


def polite(text, friendly=False):
    if not friendly:
        return re.sub(r"[가-힣]+(?=[.!?](?:\s|$))", lambda m: _polite_word(m[0]), text)
    def replace(match):
        word = match[0]
        for ending, replacement in (
            ("것이다", "거예요"), ("아니다", "아니에요"), ("하였다", "했어요"), ("했다", "했어요"),
            ("었다", "었어요"), ("았다", "았어요"), ("였다", "였어요"),
            ("있다", "있어요"), ("없다", "없어요"), ("않는다", "않아요"), ("않다", "않아요"),
            ("한다", "해요"), ("된다", "돼요"), ("쓴다", "써요"), ("준다", "줘요"),
        ):
            if word.endswith(ending):
                return word[:-len(ending)] + replacement
        if word.endswith("이다"):
            noun = word[:-2]
            final = (ord(noun[-1]) - 0xAC00) % 28
            return noun + ("이에요" if final else "예요")
        raise ValueError(f"Unsupported friendly speech ending: {word}")
    return re.sub(r"[가-힣]+(?=[.!?](?:\s|$))", replace, text)


def split_concise(text):
    # Only split explicitly coordinated past-tense clauses; never invent causality.
    return re.sub(r"([가-힣]+)(었|았|였|했|썼|봤|뒀|켰|졌|됐)(?:으며|고)\s+", r"\1\2다. ", text)


def render(facts, user_id, genre):
    pieces = []
    if user_id == 7:
        for start in range(0, len(facts), 2):
            pair = facts[start:start + 2]
            words = [formal_words(item["canonical"]) for item in pair]
            if len(words) == 2:
                # Avoid chains of three or more -myeo clauses in formal writing.
                text = (words[0] + " 또한 " + words[1]) if any("며 " in word for word in words) else connective(words[0]) + " " + words[1]
            else:
                text = words[0]
            pieces.append((text, [item["id"] for item in pair]))
    else:
        for index, fact in enumerate(facts):
            text = split_concise(fact["canonical"]) if user_id == 6 else easy_words(fact.get("friendly", fact["canonical"]))
            if user_id == 8:
                text = text.replace("없으며 ", "없다. ").replace("있으며 ", "있다. ")
                text = re.sub(r"([가-힣]+)(었|았|였|했|썼|봤|뒀|켰|졌|됐)지만\s+", r"\1\2다. 다만 ", text)
            if user_id == 8 and index == 1:
                text = "그리고 " + text
            pieces.append((text, [fact["id"]]))
    spans, parts, position = [], [], 0
    for text, ids in pieces:
        if genre in ("자기소개서", "발표문"):
            text = polite(text, friendly=user_id == 8 and genre == "발표문")
        if parts:
            position += 1
        spans.append({"start": position, "end": position + len(text), "fact_ids": ids, "text": text})
        parts.append(text)
        position += len(text)
    return " ".join(parts), spans


def supported_facts(scenario):
    return [{"id": f"f{index + 1:02d}", "canonical": text, "note": nominal_note(text),
             **({"friendly": scenario["friendly_opening"]} if index == 0 else {})}
            for index, text in enumerate(scenario["facts"])]


def choose_facts(scenario, target):
    facts = supported_facts(scenario)
    lower, upper = round(target * .8), round(target * 1.2)
    best = None
    minimum = {160: 3, 350: 5, 500: 8}[target]
    maximum = {160: 5, 350: 10, 500: 12}[target]
    for count in range(minimum, maximum + 1):
        for indices in combinations(range(12), count):
            # Keep the scenario context, an issue/observation, and an action/method.
            if 0 not in indices or not any(3 <= i < 6 for i in indices) or not any(6 <= i < 9 for i in indices):
                continue
            if target != 160 and not any(i >= 9 for i in indices):
                continue
            selected = [facts[index] for index in indices]
            variants = {uid: render(selected, uid, scenario["document_type"]) for uid in PROFILES}
            lengths = [len(text) for text, _ in variants.values()]
            if not all(lower <= length <= upper for length in lengths):
                continue
            core = sum(i in indices for i in (0, 3, 6, 9))
            distance = sum(abs(length - target) for length in lengths)
            score = (-core, distance, -count, indices)
            if best is None or score < best[0]:
                best = (score, selected, variants)
    if best is None:
        raise ValueError(f"{scenario['id']}: not enough supported material for {target} characters")
    return best[1], best[2]


def split_for(scenario_id):
    number = int(scenario_id.rsplit("_", 1)[1])
    return "train" if number <= 12 else "valid" if number <= 14 else "test"


def validate_authored_row(row):
    meta, answer = row["metadata"], row["completion"][0]["content"]
    target = meta["request"]["target_chars"]
    if not round(target * .8) <= len(answer) <= round(target * 1.2):
        raise ValueError(f"Length violation: {row['id']}")
    facts = meta["evidence_facts"]
    expected = {item["id"] for item in facts}
    seen, position = [], 0
    for span in meta["evidence_alignment"]:
        if span["start"] != position or answer[span["start"]:span["end"]] != span["text"]:
            raise ValueError(f"Alignment gap: {row['id']}")
        seen.extend(span["fact_ids"])
        position = span["end"] + 1
    if set(seen) != expected or len(seen) != len(expected) or position != len(answer) + 1:
        raise ValueError(f"Fact omission or duplication: {row['id']}")
    rebuilt, alignment = render(facts, meta["user_id"], meta["genre"])
    if rebuilt != answer or alignment != meta["evidence_alignment"]:
        raise ValueError(f"Answer is not a supported controlled paraphrase: {row['id']}")
    if [item["note"] for item in facts] != meta["request"]["facts"]:
        raise ValueError(f"Input/source mismatch: {row['id']}")
    _, expected_prompt = build_messages(SimpleNamespace(**meta["request"]))
    if row["prompt"] != expected_prompt:
        raise ValueError(f"Training prompt differs from its service request: {row['id']}")
    if finish_text(answer, meta["genre"]) != answer:
        raise ValueError(f"Service would change target morphology: {row['id']}")
    for fact in facts:
        if nominal_note(fact["canonical"]) != fact["note"]:
            raise ValueError("Unverifiable fact note")


def build(output, legacy):
    output, legacy = Path(output).resolve(), Path(legacy).resolve()
    if output.exists():
        raise ValueError("Choose a new output directory; existing data will not be overwritten")
    if len(SCENARIOS) != 64 or len({item["id"] for item in SCENARIOS}) != 64:
        raise ValueError("Expected 64 unique scenarios")
    rows = {uid: {split: [] for split in SPLITS} for uid in PROFILES}
    comparison_rows = []
    for scenario in SCENARIOS:
        split = split_for(scenario["id"])
        for target in TARGETS:
            selected, variants = choose_facts(scenario, target)
            request = {"document_type": scenario["document_type"], "topic": scenario["topic"],
                       "facts": [item["note"] for item in selected], "tone": "기본", "target_chars": target}
            _, prompt = build_messages(SimpleNamespace(**request))
            case_id = f"{scenario['id']}_chars{target}"
            if len({text for text, _ in variants.values()}) != 3:
                raise ValueError(f"Styles are indistinguishable: {case_id}")
            for uid, (answer, alignment) in variants.items():
                row = {"id": f"{PROFILES[uid]['account_key']}__{case_id}", "prompt": deepcopy(prompt),
                       "completion": [{"role": "assistant", "content": answer}],
                       "metadata": {"user_id": uid, "account_key": PROFILES[uid]["account_key"], "genre": scenario["document_type"],
                                    "case_id": case_id, "group_id": scenario["id"], "split": split,
                                    "synthetic": True, "human_approved": False, "common_training_allowed": False, "demo_only": True,
                                    "recipe": RECIPE, "request": deepcopy(request), "source_scenario_sha256": value_hash(scenario),
                                    "evidence_facts": deepcopy(selected), "evidence_alignment": alignment}}
                validate_authored_row(row)
                rows[uid][split].append(row)
            comparison_rows.append({"case_id": case_id, "group_id": scenario["id"], "split": split,
                                    "request": request, "canonical_facts": [item["canonical"] for item in selected],
                                    "answers": {str(uid): {"text": text, "chars": len(text)} for uid, (text, _) in variants.items()}})
    output.mkdir(parents=True)
    source_copy = output / "source_scenarios.json"
    source_copy.write_text(json.dumps(SCENARIOS, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {"kind": "synthetic_personalization_pilot_v2", "demo_only": True, "human_approved": False,
                "common_training_allowed": False, "production_ready": False, "recipe": RECIPE,
                "profiles": [{"user_id": uid, **profile} for uid, profile in PROFILES.items()],
                "source_bank": {"path": source_copy.name, "sha256": file_hash(source_copy)},
                "length_policy": {"targets": list(TARGETS), "tolerance": .2, "counting": "Python len, including spaces"},
                "training_max_sequence_length": 2048, "generation_input_token_limit": 2048,
                "generator_sha256": file_hash(Path(__file__)),
                "scenario_definitions_sha256": file_hash(ROOT / "personalization_scenarios_v2.py"),
                "prompt_builder_sha256": file_hash(ROOT / "writing_prompts.py"),
                "training_policy": "Independent continuation of one selected common LoRA per profile; no test/valid training.",
                "semantic_review": "Controlled clause-to-fact alignment, deterministic rewriting and agent spot review; not human approval.",
                "legacy_policy": "Preserved verbatim in legacy_archive; excluded from the v2 training/validation/test files.",
                "files": [], "legacy_files": [], "evaluation_files": []}
    for uid in PROFILES:
        folder = output / f"user_{uid}"
        folder.mkdir()
        for split in SPLITS:
            path = folder / f"{split}.jsonl"
            path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows[uid][split]), encoding="utf-8")
            manifest["files"].append({"path": path.relative_to(output).as_posix(), "count": len(rows[uid][split]), "sha256": file_hash(path)})
            old = legacy / f"user_{uid}/{split}.jsonl"
            dest = output / "legacy_archive" / f"user_{uid}/{split}.jsonl"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(old.read_bytes())
            manifest["legacy_files"].append({"path": dest.relative_to(output).as_posix(), "source": str(old), "sha256": file_hash(dest)})
    transfer = legacy / "transfer_eval_cases.json"
    legacy_transfer = output / "legacy_archive" / transfer.name
    legacy_transfer.write_bytes(transfer.read_bytes())
    manifest["legacy_files"].append({"path": legacy_transfer.relative_to(output).as_posix(), "source": str(transfer), "sha256": file_hash(legacy_transfer)})
    destination = output / transfer.name
    destination.write_bytes(transfer.read_bytes())
    manifest["evaluation_files"].append({"path": destination.name, "count": 12, "sha256": file_hash(destination)})
    review = output / "style_comparison.jsonl"
    review.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in comparison_rows), encoding="utf-8")
    profile_audits = []
    for uid, splits in rows.items():
        all_rows = [row for items in splits.values() for row in items]
        lengths = [len(row["completion"][0]["content"]) for row in all_rows]
        sentences = [len([s for s in re.split(r"[.!?]", row["completion"][0]["content"]) if s.strip()]) for row in all_rows]
        profile_audits.append({"user_id": uid, "style": PROFILES[uid]["style"], "counts": {split: len(items) for split, items in splits.items()},
                               "length_passed": len(all_rows), "length_total": len(all_rows),
                               "chars": {"min": min(lengths), "mean": round(sum(lengths) / len(lengths), 1), "max": max(lengths)},
                               "mean_sentence_chars": round(sum(lengths) / sum(sentences), 1),
                               "targets": dict(Counter(row["metadata"]["request"]["target_chars"] for row in all_rows))})
    audit = {"kind": "personalization_v2_quality_audit", "profiles": profile_audits,
             "unique_scenario_groups": 64, "unique_length_variants": len(comparison_rows), "total_records": 576,
             "training_records": 432, "validation_records": 72, "test_records": 72,
             "groups_per_split": dict(Counter(split_for(item["id"]) for item in SCENARIOS)),
             "same_input_across_profiles": True, "length_pass_rate": 1.0,
             "fact_alignment_pass_rate": 1.0, "human_approved": False, "production_ready": False,
             "distinct_answers_per_matched_request": 3,
             "style_scope": "Genre endings preserved; concise short clauses, formal coordinated clauses, friendly accessible words and spoken speech endings.",
             "limitations": ["Synthetic controlled paraphrases, not real-user writing.",
                             "Style distinctness metrics do not prove learned personalization.",
                             "Length variants share a scenario; count 64 independent groups, not 576 independent topics.",
                             "Human factual/naturalness review and GPU comparison are still required."]}
    audit_path = output / "audit.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest["audit_sha256"] = file_hash(audit_path)
    manifest["review_file"] = {"path": review.name, "sha256": file_hash(review)}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/personalization_demo_v2"))
    parser.add_argument("--legacy", type=Path, default=Path("data/personalization_demo_v1"))
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    legacy = args.legacy if args.legacy.is_absolute() else ROOT / args.legacy
    print(json.dumps(build(output, legacy), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
