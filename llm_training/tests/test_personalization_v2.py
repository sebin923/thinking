from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from build_personalization_v2 import build, nominal_note, polite, split_concise, validate_authored_row
from compare_personal import evaluation_cases, request_for
from personalization_data import PROFILES, SPLITS, load_prepared
from personalization_scenarios_v2 import SCENARIOS
from train_personal import tokenize_personal_rows


@pytest.fixture(scope="module")
def prepared_v2(tmp_path_factory):
    base = tmp_path_factory.mktemp("personalization-v2")
    legacy = base / "legacy"
    for uid in PROFILES:
        folder = legacy / f"user_{uid}"
        folder.mkdir(parents=True)
        for split in SPLITS:
            (folder / f"{split}.jsonl").write_text(json.dumps({"legacy": True, "user_id": uid, "split": split}) + "\n", encoding="utf-8")
    (legacy / "transfer_eval_cases.json").write_bytes((ROOT / "personalization_eval_cases.json").read_bytes())
    output = base / "prepared"
    audit = build(output, legacy)
    manifest, datasets = load_prepared(output)
    return output, legacy, audit, manifest, datasets


def test_all_lengths_and_facts_are_valid_with_balanced_genres(prepared_v2):
    _, _, audit, _, datasets = prepared_v2
    assert audit["total_records"] == 576
    assert audit["training_records"] == 432
    for uid, splits in datasets.items():
        assert {split: len(rows) for split, rows in splits.items()} == {"train": 144, "valid": 24, "test": 24}
        all_rows = [row for rows in splits.values() for row in rows]
        assert Counter(row["metadata"]["request"]["target_chars"] for row in all_rows) == {160: 64, 350: 64, 500: 64}
        assert Counter(row["metadata"]["genre"] for row in all_rows) == {genre: 48 for genre in ("보고서", "자기소개서", "발표문", "자유 글쓰기")}
        for row in all_rows:
            validate_authored_row(row)
            assert row["metadata"]["human_approved"] is False
            assert row["metadata"]["common_training_allowed"] is False


def test_matched_styles_have_identical_inputs_and_distinct_answers(prepared_v2):
    _, _, _, _, datasets = prepared_v2
    for split in SPLITS:
        for examples in zip(*(datasets[uid][split] for uid in PROFILES)):
            assert len({json.dumps(row["prompt"], ensure_ascii=False) for row in examples}) == 1
            assert len({row["completion"][0]["content"] for row in examples}) == 3
            assert len({json.dumps(row["metadata"]["request"], sort_keys=True) for row in examples}) == 1


def test_length_variants_never_cross_scenario_splits(prepared_v2):
    _, _, _, _, datasets = prepared_v2
    groups = {}
    for splits in datasets.values():
        for split, rows in splits.items():
            for row in rows:
                groups.setdefault(row["metadata"]["group_id"], set()).add(split)
    assert len(groups) == 64 and all(len(splits) == 1 for splits in groups.values())


def test_legacy_records_preserved_byte_for_byte_outside_training(prepared_v2):
    output, legacy, _, manifest, datasets = prepared_v2
    for item in manifest["legacy_files"]:
        suffix = item["path"].split("legacy_archive/", 1)[1]
        assert (legacy / suffix).read_bytes() == (output / item["path"]).read_bytes()
    assert all(not row.get("legacy") for splits in datasets.values() for rows in splits.values() for row in rows)


def test_rejects_added_claim_even_if_length_remains_acceptable(prepared_v2):
    row = deepcopy(prepared_v2[-1][6]["train"][0])
    row["completion"][0]["content"] = row["completion"][0]["content"].replace("확인했다", "성공했다", 1)
    with pytest.raises(ValueError):
        validate_authored_row(row)


def test_rejects_unbacked_alignment_and_changed_service_prompt(prepared_v2):
    row = deepcopy(prepared_v2[-1][7]["train"][0])
    row["metadata"]["evidence_alignment"][0]["fact_ids"].append("invented_fact")
    with pytest.raises(ValueError, match="Fact omission or duplication"):
        validate_authored_row(row)
    row = deepcopy(prepared_v2[-1][7]["train"][0])
    row["prompt"][-1]["content"] += "\n사용자가 말하지 않은 성과를 추가하세요."
    with pytest.raises(ValueError, match="service request"):
        validate_authored_row(row)


def test_comparison_reuses_each_records_real_target(prepared_v2):
    output, _, _, _, datasets = prepared_v2
    cases = evaluation_cases(output, datasets, "valid")
    assert {case["target_chars"] for case in cases[6]} == {160, 350, 500}
    longest = next(case for case in cases[6] if case["target_chars"] == 500)
    assert request_for(longest, 6, False, target_chars=160)["target_chars"] == 500


def test_rendering_retains_negation_and_tense():
    assert split_concise("사진을 받았으며 수정 여부는 확인하지 않았다.") == "사진을 받았다. 수정 여부는 확인하지 않았다."
    assert nominal_note("기록의 이유는 모른다.") == "기록의 이유는 모름"
    assert polite("아직 적용하지 않았다.", friendly=True) == "아직 적용하지 않았어요."


def test_friendly_openings_are_explicit_and_do_not_make_meetings_recurring():
    assert len(SCENARIOS) == 64
    assert all(row["friendly_opening"] for row in SCENARIOS)
    cover = next(row for row in SCENARIOS if row["id"] == "cover_04")
    assert "회의가 끝난 뒤" in cover["friendly_opening"]
    assert "끝나면" not in cover["friendly_opening"]


def test_2048_tokenizer_masks_input_and_rejects_truncation(monkeypatch):
    module = ModuleType("datasets")
    module.Dataset = SimpleNamespace(from_list=lambda rows: rows)
    monkeypatch.setitem(sys.modules, "datasets", module)
    class Tokenizer:
        eos_token_id = 9
        def __call__(self, text, **kwargs):
            return {"input_ids": [1] * len(text)}
    processor = SimpleNamespace(tokenizer=Tokenizer(), apply_chat_template=lambda *args, **kwargs: "prefix")
    row = {"prompt": [{"role": "user", "content": "ignored"}], "completion": [{"role": "assistant", "content": "answer"}]}
    result = tokenize_personal_rows([row], processor, "fixture", 2048)
    assert result[0]["labels"] == [-100] * 6 + [1] * 6 + [9]
    processor.apply_chat_template = lambda *args, **kwargs: "x" * 2049
    with pytest.raises(ValueError, match="never truncated"):
        tokenize_personal_rows([row], processor, "too-long", 3072)
