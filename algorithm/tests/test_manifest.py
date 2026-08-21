from pathlib import Path

import pytest

from fall_risk.contracts import FallState, Split
from fall_risk.datasets import (
    ManifestRecord,
    assign_subject_splits,
    audit_leakage,
    load_manifest,
    write_manifest,
)


def make_record(
    subject: str,
    *,
    trial: str = "trial-1",
    sample_suffix: str = "0001",
    split: Split | None = None,
    path: str | None = None,
) -> ManifestRecord:
    sample_id = f"sample-{subject}-{trial}-{sample_suffix}"
    return ManifestRecord(
        sample_id=sample_id,
        dataset="SAFER",
        subject_id=subject,
        trial_id=trial,
        start_time=0.0,
        end_time=2.0,
        state_label=FallState.NORMAL,
        modalities={"skeleton": path or f"processed/{sample_id}.json"},
        split=split,
    )


def test_manifest_jsonl_round_trip(workspace_tmp_path: Path) -> None:
    path = workspace_tmp_path / "manifest.jsonl"
    expected = [make_record("s01", split=Split.TRAIN)]
    write_manifest(expected, path)
    assert load_manifest(path) == expected


def test_subject_split_is_deterministic_and_leak_free() -> None:
    records = [
        make_record(f"s{index:02d}", trial=f"trial-{trial}", sample_suffix=str(trial))
        for index in range(1, 7)
        for trial in range(1, 3)
    ]
    first = assign_subject_splits(records, seed=7)
    second = assign_subject_splits(records, seed=7)
    assert [record.split for record in first] == [record.split for record in second]
    assert {record.split for record in first} == {Split.TRAIN, Split.VALIDATION, Split.TEST}
    assert audit_leakage(first).is_clean


def test_leakage_audit_detects_subject_trial_and_path_cross_split() -> None:
    train = make_record("s01", split=Split.TRAIN, path="shared.json")
    test = make_record(
        "s01",
        sample_suffix="0002",
        split=Split.TEST,
        path="shared.json",
    )
    report = audit_leakage([train, test])
    codes = {issue.code for issue in report.issues}
    assert "SUBJECT_CROSS_SPLIT" in codes
    assert "TRIAL_CROSS_SPLIT" in codes
    assert "OVERLAPPING_WINDOW_CROSS_SPLIT" in codes
    assert "SOURCE_PATH_CROSS_SPLIT" in codes
    with pytest.raises(ValueError, match="data leakage audit failed"):
        report.raise_for_errors()


def test_manifest_rejects_unknown_modality() -> None:
    with pytest.raises(ValueError, match="unknown modalities"):
        ManifestRecord(
            sample_id="bad",
            dataset="SAFER",
            subject_id="s01",
            trial_id="t01",
            start_time=0.0,
            end_time=1.0,
            state_label=FallState.NORMAL,
            modalities={"temperature_camera": "bad.json"},
        )
