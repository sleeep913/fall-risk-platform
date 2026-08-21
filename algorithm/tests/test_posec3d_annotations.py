from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from fall_risk.contracts import FallState, Split
from fall_risk.datasets import ManifestRecord
from fall_risk.posec3d import build_mmaction_pose_annotations


def _record(root: Path, sample_id: str, state: FallState, split: Split) -> ManifestRecord:
    pose_path = root / f"{sample_id}.npz"
    np.savez_compressed(
        pose_path,
        keypoint=np.zeros((1, 48, 17, 2), dtype=np.float32),
        keypoint_score=np.ones((1, 48, 17), dtype=np.float32),
        img_shape=np.asarray([256, 256], dtype=np.int32),
    )
    return ManifestRecord(
        sample_id=sample_id,
        dataset="synthetic",
        subject_id=f"subject-{sample_id}",
        trial_id=f"trial-{sample_id}",
        start_time=0.0,
        end_time=2.0,
        state_label=state,
        modalities={"skeleton": pose_path.name},
        split=split,
    )


def test_generic_pose_adapter_uses_three_a1_classes(workspace_tmp_path: Path) -> None:
    records = [
        _record(workspace_tmp_path, "normal", FallState.NORMAL, Split.TRAIN),
        _record(workspace_tmp_path, "unstable", FallState.UNSTABLE, Split.VALIDATION),
        _record(workspace_tmp_path, "falling", FallState.FALLING, Split.TEST),
    ]

    payload, summary = build_mmaction_pose_annotations(
        records,
        data_root=workspace_tmp_path,
    )

    assert [item["label"] for item in payload["annotations"]] == [0, 1, 2]
    assert summary.class_counts == {"FALLING": 1, "NORMAL": 1, "UNSTABLE": 1}
    assert set(payload["split"]) == {"train", "validation", "test"}


def test_generic_pose_adapter_rejects_unavailable_five_state_label(
    workspace_tmp_path: Path,
) -> None:
    records = [
        _record(workspace_tmp_path, "train", FallState.NORMAL, Split.TRAIN),
        _record(workspace_tmp_path, "validation", FallState.NORMAL, Split.VALIDATION),
        _record(workspace_tmp_path, "fallen", FallState.FALLEN, Split.TEST),
    ]

    with pytest.raises(ValueError, match="only supports NORMAL, UNSTABLE, and FALLING"):
        build_mmaction_pose_annotations(records, data_root=workspace_tmp_path)
