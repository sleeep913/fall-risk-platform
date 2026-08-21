from __future__ import annotations

import io
import os
import pickle
from pathlib import Path

import numpy as np
import pytest

from fall_risk.posec3d import (
    A1_STATE_ORDER,
    build_safer_posec3d_annotations,
    extract_safer_subject,
    load_numpy_pickle,
    write_safer_posec3d_annotations,
)


def _video(name: str, *, unknown_label: int | None = None) -> dict[str, object]:
    labels = np.concatenate(
        [
            np.full(48, 1, dtype=np.int16),
            np.full(48, 9, dtype=np.int16),
            np.full(48, 10, dtype=np.int16),
            np.full(48, 11, dtype=np.int16),
        ]
    )
    if unknown_label is not None:
        labels[-1] = unknown_label
    frames = labels.shape[0]
    return {
        "frame_dir": name,
        "total_frames": frames,
        "img_shape": (1080, 1920),
        "original_shape": (1080, 1920),
        "keypoint": np.zeros((1, frames, 17, 2), dtype=np.float32),
        "keypoint_score": np.ones((1, frames, 17), dtype=np.float32),
        "labels": labels,
    }


def _payload(*, unknown_label: int | None = None) -> dict[str, object]:
    train = [f"Day_01_P{subject:02d}_Camera_01.mp4" for subject in (1, 2, 3)]
    test = ["Day_01_P04_Camera_01.mp4"]
    annotations = [_video(name) for name in train]
    annotations.append(_video(test[0], unknown_label=unknown_label))
    return {
        "annotations": annotations,
        "split": {"sub_train": train, "sub_test": test},
    }


def test_safer_converter_builds_subject_safe_three_class_windows() -> None:
    converted, summary = build_safer_posec3d_annotations(
        _payload(),
        window_size=48,
        stride=48,
        minimum_purity=1.0,
        validation_fraction=0.34,
        max_per_class_per_split=None,
        seed=7,
    )

    assert set(converted["split"]) == {"train", "validation", "test"}
    assert set(item["label"] for item in converted["annotations"]) == {0, 1, 2}
    assert summary.window_count == 16
    assert summary.class_counts == {"FALLING": 4, "NORMAL": 8, "UNSTABLE": 4}
    assert len(summary.validation_subjects) == 1

    subjects_by_split: dict[str, set[str]] = {}
    by_id = {item["frame_dir"]: item for item in converted["annotations"]}
    for split_name, sample_ids in converted["split"].items():
        subjects_by_split[split_name] = {
            extract_safer_subject(str(by_id[sample_id]["source_frame_dir"]))
            for sample_id in sample_ids
        }
    assert subjects_by_split["train"].isdisjoint(subjects_by_split["validation"])
    assert subjects_by_split["train"].isdisjoint(subjects_by_split["test"])
    assert subjects_by_split["validation"].isdisjoint(subjects_by_split["test"])

    lying_down = [
        item
        for item in converted["annotations"]
        if item["source_start_frame"] == 144
    ]
    assert lying_down
    assert {item["label"] for item in lying_down} == {0}
    assert all(item["keypoint"].shape == (1, 48, 17, 2) for item in converted["annotations"])
    assert tuple(state.value for state in A1_STATE_ORDER) == (
        "NORMAL",
        "UNSTABLE",
        "FALLING",
    )


def test_safer_converter_rejects_unknown_raw_label() -> None:
    with pytest.raises(ValueError, match="unknown SAFER labels"):
        build_safer_posec3d_annotations(_payload(unknown_label=99))


def test_safer_converter_rejects_split_entry_without_annotation() -> None:
    payload = _payload()
    payload["split"]["sub_test"].append("Day_01_P99_Camera_01.mp4")
    with pytest.raises(ValueError, match="absent from annotations"):
        build_safer_posec3d_annotations(payload)


def test_safer_writer_never_overwrites_source(workspace_tmp_path: Path) -> None:
    source = workspace_tmp_path / "source.pkl"
    source.write_bytes(pickle.dumps(_payload()))
    before = source.read_bytes()

    with pytest.raises(ValueError, match="must not overwrite"):
        write_safer_posec3d_annotations(source, source)

    assert source.read_bytes() == before


class _UnsafePicklePayload:
    def __reduce__(self) -> tuple[object, tuple[str]]:
        return os.system, ("this-must-never-run",)


def test_restricted_pickle_loader_rejects_arbitrary_globals() -> None:
    serialized = pickle.dumps(_UnsafePicklePayload())
    with pytest.raises(pickle.UnpicklingError, match="forbidden pickle global"):
        load_numpy_pickle(io.BytesIO(serialized))


def test_posec3d_config_declares_three_classes() -> None:
    config_path = (
        Path(__file__).resolve().parents[1]
        / "configs"
        / "posec3d"
        / "safer_posec3d_a1.py"
    )
    source = config_path.read_text(encoding="utf-8")
    assert "num_classes=3" in source
    assert "stage_blocks=(4, 6, 3)" in source
    assert 'save_best="acc/mean1"' in source
