from __future__ import annotations

import pickle
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from fall_risk.contracts.labels import FallState, Modality, Split
from fall_risk.datasets.leakage import audit_leakage
from fall_risk.datasets.manifest import ManifestRecord

A1_STATE_ORDER: tuple[FallState, ...] = (
    FallState.NORMAL,
    FallState.UNSTABLE,
    FallState.FALLING,
)
STATE_TO_CLASS: Mapping[str, int] = {
    state.value: index for index, state in enumerate(A1_STATE_ORDER)
}


@dataclass(frozen=True)
class PoseAnnotationSummary:
    sample_count: int
    split_counts: Mapping[str, int]
    class_counts: Mapping[str, int]
    num_keypoints: int


def _resolve_artifact_path(record: ManifestRecord, data_root: Path) -> Path:
    raw_path = Path(record.modalities[Modality.SKELETON.value])
    artifact_path = raw_path if raw_path.is_absolute() else data_root / raw_path
    artifact_path = artifact_path.resolve()
    if not artifact_path.is_file():
        raise ValueError(
            f"skeleton artifact for {record.sample_id!r} does not exist: {artifact_path}"
        )
    if artifact_path.suffix.lower() != ".npz":
        raise ValueError(
            f"skeleton artifact for {record.sample_id!r} must be a .npz file"
        )
    return artifact_path


def _load_pose_npz(
    artifact_path: Path,
    *,
    sample_id: str,
    expected_num_keypoints: int,
) -> tuple[np.ndarray, np.ndarray, tuple[int, int], tuple[int, int]]:
    try:
        with np.load(artifact_path, allow_pickle=False) as payload:
            missing = {"keypoint", "keypoint_score", "img_shape"} - set(payload.files)
            if missing:
                raise ValueError(f"missing arrays: {sorted(missing)}")
            keypoint = np.asarray(payload["keypoint"], dtype=np.float32)
            keypoint_score = np.asarray(payload["keypoint_score"], dtype=np.float32)
            img_shape_raw = np.asarray(payload["img_shape"]).reshape(-1)
            original_shape_raw = np.asarray(
                payload["original_shape"] if "original_shape" in payload else img_shape_raw
            ).reshape(-1)
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid pose artifact for {sample_id!r}: {exc}") from exc

    if keypoint.ndim != 4 or keypoint.shape[-1] != 2:
        raise ValueError(
            f"{sample_id!r} keypoint must have shape [M,T,V,2], got {keypoint.shape}"
        )
    if keypoint_score.shape != keypoint.shape[:3]:
        raise ValueError(
            f"{sample_id!r} keypoint_score must have shape {keypoint.shape[:3]}, "
            f"got {keypoint_score.shape}"
        )
    if keypoint.shape[0] < 1 or keypoint.shape[1] < 1:
        raise ValueError(f"{sample_id!r} must contain at least one person and one frame")
    if keypoint.shape[2] != expected_num_keypoints:
        raise ValueError(
            f"{sample_id!r} must contain {expected_num_keypoints} keypoints, "
            f"got {keypoint.shape[2]}"
        )
    if not np.isfinite(keypoint).all() or not np.isfinite(keypoint_score).all():
        raise ValueError(f"{sample_id!r} contains NaN or infinite pose values")
    if np.any((keypoint_score < 0.0) | (keypoint_score > 1.0)):
        raise ValueError(f"{sample_id!r} keypoint scores must be within [0, 1]")
    if img_shape_raw.size != 2 or original_shape_raw.size != 2:
        raise ValueError(f"{sample_id!r} img_shape and original_shape must contain H,W")

    img_shape = tuple(int(value) for value in img_shape_raw)
    original_shape = tuple(int(value) for value in original_shape_raw)
    if any(value <= 0 for value in (*img_shape, *original_shape)):
        raise ValueError(f"{sample_id!r} image dimensions must be positive")
    return keypoint, keypoint_score, img_shape, original_shape


def build_mmaction_pose_annotations(
    records: Iterable[ManifestRecord],
    *,
    data_root: str | Path,
    expected_num_keypoints: int = 17,
) -> tuple[dict[str, Any], PoseAnnotationSummary]:
    rows = list(records)
    if not rows:
        raise ValueError("cannot build PoseC3D annotations from an empty manifest")
    if expected_num_keypoints <= 0:
        raise ValueError("expected_num_keypoints must be positive")
    if any(record.split is None for record in rows):
        raise ValueError("every PoseC3D record must have an assigned split")
    if len({record.sample_id for record in rows}) != len(rows):
        raise ValueError("PoseC3D sample_id values must be unique")

    audit_leakage(rows).raise_for_errors()
    root = Path(data_root).resolve()
    split_ids: dict[str, list[str]] = {split.value: [] for split in Split}
    annotations: list[dict[str, Any]] = []
    split_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()

    for record in rows:
        if record.state_label not in A1_STATE_ORDER:
            raise ValueError(
                f"{record.sample_id!r} uses {record.state_label.value}, but the A1 PoseC3D "
                "baseline only supports NORMAL, UNSTABLE, and FALLING"
            )
        if Modality.SKELETON.value not in record.modalities:
            raise ValueError(f"{record.sample_id!r} does not provide a skeleton modality")
        artifact_path = _resolve_artifact_path(record, root)
        keypoint, keypoint_score, img_shape, original_shape = _load_pose_npz(
            artifact_path,
            sample_id=record.sample_id,
            expected_num_keypoints=expected_num_keypoints,
        )
        split_name = record.split.value
        split_ids[split_name].append(record.sample_id)
        split_counts[split_name] += 1
        class_counts[record.state_label.value] += 1
        annotations.append(
            {
                "frame_dir": record.sample_id,
                "total_frames": int(keypoint.shape[1]),
                "img_shape": img_shape,
                "original_shape": original_shape,
                "label": STATE_TO_CLASS[record.state_label.value],
                "keypoint": keypoint,
                "keypoint_score": keypoint_score,
            }
        )

    empty_splits = sorted(name for name, sample_ids in split_ids.items() if not sample_ids)
    if empty_splits:
        raise ValueError(f"PoseC3D annotations require non-empty splits: {empty_splits}")

    payload = {"split": split_ids, "annotations": annotations}
    summary = PoseAnnotationSummary(
        sample_count=len(annotations),
        split_counts=dict(sorted(split_counts.items())),
        class_counts=dict(sorted(class_counts.items())),
        num_keypoints=expected_num_keypoints,
    )
    return payload, summary


def write_mmaction_pose_annotations(
    records: Iterable[ManifestRecord],
    output_path: str | Path,
    *,
    data_root: str | Path,
    expected_num_keypoints: int = 17,
) -> PoseAnnotationSummary:
    payload, summary = build_mmaction_pose_annotations(
        records,
        data_root=data_root,
        expected_num_keypoints=expected_num_keypoints,
    )
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return summary
