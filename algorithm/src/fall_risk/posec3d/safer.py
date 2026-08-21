from __future__ import annotations

import builtins
import hashlib
import pickle
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

import numpy as np

from fall_risk.contracts import FallState, Split

# The SAFER non-wheelchair model card lists 15 activity classes. The annotation
# pickle additionally contains 0 for background/unannotated frames.
SAFER_NON_WHEELCHAIR_LABELS: Mapping[int, str] = {
    0: "background",
    1: "stand",
    2: "stand_activity",
    3: "walk",
    4: "sit",
    5: "sit_activity",
    6: "sitting_down",
    7: "getting_up",
    8: "bend",
    9: "unstable",
    10: "fall",
    11: "lie_down",
    12: "lying_down",
    13: "reach",
    14: "run",
    15: "jump",
}

A1_STATE_ORDER: tuple[FallState, ...] = (
    FallState.NORMAL,
    FallState.UNSTABLE,
    FallState.FALLING,
)
A1_STATE_TO_CLASS: Mapping[FallState, int] = {
    state: index for index, state in enumerate(A1_STATE_ORDER)
}

# Background is deliberately ignored: it is not a reliable negative label.
SAFER_RAW_TO_A1_CLASS: Mapping[int, int | None] = {
    0: None,
    **{raw_label: A1_STATE_TO_CLASS[FallState.NORMAL] for raw_label in range(1, 9)},
    9: A1_STATE_TO_CLASS[FallState.UNSTABLE],
    10: A1_STATE_TO_CLASS[FallState.FALLING],
    **{raw_label: A1_STATE_TO_CLASS[FallState.NORMAL] for raw_label in range(11, 16)},
}

_SUBJECT_PATTERN = re.compile(r"(?:^|[_-])p(?P<subject>\d+)(?:[_\-.]|$)", re.IGNORECASE)
_ALLOWED_NUMPY_GLOBALS: Mapping[tuple[str, str], Any] = {
    ("numpy", "dtype"): np.dtype,
    ("numpy", "ndarray"): np.ndarray,
    ("numpy.core.multiarray", "_reconstruct"): np.core.multiarray._reconstruct,
    ("numpy.core.multiarray", "scalar"): np.core.multiarray.scalar,
}
_ALLOWED_BUILTINS = {"complex", "frozenset", "set", "slice"}


class NumpyOnlyUnpickler(pickle.Unpickler):
    """Unpickle NumPy annotation arrays without allowing arbitrary imports."""

    def find_class(self, module: str, name: str) -> Any:
        allowed = _ALLOWED_NUMPY_GLOBALS.get((module, name))
        if allowed is not None:
            return allowed
        if module == "builtins" and name in _ALLOWED_BUILTINS:
            return getattr(builtins, name)
        raise pickle.UnpicklingError(f"forbidden pickle global: {module}.{name}")


@dataclass(frozen=True)
class SaferPoseSummary:
    video_count: int
    window_count: int
    split_counts: Mapping[str, int]
    class_counts: Mapping[str, int]
    validation_subjects: tuple[str, ...]
    ignored_background_centers: int
    rejected_low_purity: int


@dataclass(frozen=True)
class _WindowCandidate:
    annotation_index: int
    frame_dir: str
    split: Split
    label: int
    start: int
    stop: int


def load_numpy_pickle(source: str | Path | BinaryIO) -> Any:
    """Load a trusted-format NumPy pickle with a restricted global allow-list."""

    if hasattr(source, "read"):
        return NumpyOnlyUnpickler(source).load()
    path = Path(source)
    with path.open("rb") as handle:
        return NumpyOnlyUnpickler(handle).load()


def extract_safer_subject(frame_dir: str) -> str:
    match = _SUBJECT_PATTERN.search(Path(frame_dir).name)
    if match is None:
        raise ValueError(f"cannot extract SAFER subject id from frame_dir: {frame_dir!r}")
    return f"P{int(match.group('subject')):03d}"


def _choose_validation_subjects(
    train_names: set[str],
    *,
    validation_fraction: float,
    seed: int,
) -> tuple[str, ...]:
    subjects = sorted({extract_safer_subject(name) for name in train_names})
    if len(subjects) < 2:
        raise ValueError("subject protocol needs at least two training subjects")
    if not 0.0 < validation_fraction < 1.0:
        raise ValueError("validation_fraction must be between 0 and 1")
    count = min(len(subjects) - 1, max(1, round(len(subjects) * validation_fraction)))
    ranked = sorted(
        subjects,
        key=lambda subject: hashlib.sha256(f"{seed}:{subject}".encode()).digest(),
    )
    return tuple(sorted(ranked[:count]))


def _validate_root(payload: Any) -> tuple[list[Mapping[str, Any]], Mapping[str, Sequence[str]]]:
    if not isinstance(payload, dict):
        raise ValueError("SAFER pickle root must be a dictionary")
    annotations = payload.get("annotations")
    split = payload.get("split")
    if not isinstance(annotations, list) or not annotations:
        raise ValueError("SAFER pickle must contain a non-empty annotations list")
    if not isinstance(split, dict):
        raise ValueError("SAFER pickle must contain a split dictionary")
    if "sub_train" not in split or "sub_test" not in split:
        raise ValueError("SAFER pickle does not provide sub_train/sub_test protocol splits")
    if not all(isinstance(item, dict) for item in annotations):
        raise ValueError("every SAFER annotation must be a dictionary")
    return annotations, split


def _validate_video(
    item: Mapping[str, Any],
    *,
    expected_num_keypoints: int,
) -> tuple[str, np.ndarray, np.ndarray, np.ndarray, tuple[int, int], tuple[int, int]]:
    required = {"frame_dir", "keypoint", "keypoint_score", "labels", "img_shape"}
    missing = required - set(item)
    if missing:
        raise ValueError(f"SAFER annotation is missing fields: {sorted(missing)}")
    frame_dir = str(item["frame_dir"])
    keypoint = np.asarray(item["keypoint"])
    score = np.asarray(item["keypoint_score"])
    labels = np.asarray(item["labels"])
    if keypoint.ndim != 4 or keypoint.shape[-1] != 2:
        raise ValueError(f"{frame_dir!r} keypoint must have shape [M,T,V,2]")
    if score.shape != keypoint.shape[:3]:
        raise ValueError(f"{frame_dir!r} keypoint_score shape does not match keypoint")
    if labels.ndim != 1 or labels.shape[0] != keypoint.shape[1]:
        raise ValueError(f"{frame_dir!r} labels must have one value per frame")
    if keypoint.shape[0] < 1 or keypoint.shape[1] < 1:
        raise ValueError(f"{frame_dir!r} must contain a person and at least one frame")
    if keypoint.shape[2] != expected_num_keypoints:
        raise ValueError(
            f"{frame_dir!r} must contain {expected_num_keypoints} keypoints, "
            f"got {keypoint.shape[2]}"
        )
    if not np.issubdtype(labels.dtype, np.integer):
        raise ValueError(f"{frame_dir!r} labels must use an integer dtype")
    unknown = sorted(set(int(value) for value in np.unique(labels)) - set(SAFER_RAW_TO_A1_CLASS))
    if unknown:
        raise ValueError(f"{frame_dir!r} contains unknown SAFER labels: {unknown}")
    if not np.isfinite(keypoint).all() or not np.isfinite(score).all():
        raise ValueError(f"{frame_dir!r} contains NaN or infinite pose values")
    if np.any((score < 0.0) | (score > 1.0)):
        raise ValueError(f"{frame_dir!r} keypoint scores must be within [0, 1]")

    img_shape = tuple(int(value) for value in np.asarray(item["img_shape"]).reshape(-1))
    original_shape = tuple(
        int(value)
        for value in np.asarray(item.get("original_shape", img_shape)).reshape(-1)
    )
    if len(img_shape) != 2 or len(original_shape) != 2:
        raise ValueError(f"{frame_dir!r} img_shape/original_shape must contain H,W")
    if any(value <= 0 for value in (*img_shape, *original_shape)):
        raise ValueError(f"{frame_dir!r} image dimensions must be positive")
    return frame_dir, keypoint, score, labels, img_shape, original_shape


def _mapped_labels(labels: np.ndarray) -> np.ndarray:
    mapped = np.full(labels.shape, -1, dtype=np.int8)
    for raw_label, target in SAFER_RAW_TO_A1_CLASS.items():
        if target is not None:
            mapped[labels == raw_label] = target
    return mapped


def _candidate_rank(candidate: _WindowCandidate, seed: int) -> bytes:
    token = f"{seed}:{candidate.frame_dir}:{candidate.start}:{candidate.stop}"
    return hashlib.sha256(token.encode()).digest()


def build_safer_posec3d_annotations(
    payload: Any,
    *,
    window_size: int = 48,
    stride: int = 24,
    minimum_purity: float = 0.6,
    validation_fraction: float = 0.15,
    max_per_class_per_split: int | None = 200,
    seed: int = 42,
    expected_num_keypoints: int = 17,
) -> tuple[dict[str, Any], SaferPoseSummary]:
    """Convert long SAFER videos into subject-safe three-class PoseC3D windows."""

    if window_size <= 0 or stride <= 0:
        raise ValueError("window_size and stride must be positive")
    if not 0.0 < minimum_purity <= 1.0:
        raise ValueError("minimum_purity must be within (0, 1]")
    if max_per_class_per_split is not None and max_per_class_per_split <= 0:
        raise ValueError("max_per_class_per_split must be positive or None")
    if expected_num_keypoints <= 0:
        raise ValueError("expected_num_keypoints must be positive")

    annotations, source_split = _validate_root(payload)
    train_names = {str(value) for value in source_split["sub_train"]}
    test_names = {str(value) for value in source_split["sub_test"]}
    overlap = train_names & test_names
    if overlap:
        raise ValueError(f"SAFER subject split overlaps for {len(overlap)} videos")
    validation_subjects = _choose_validation_subjects(
        train_names,
        validation_fraction=validation_fraction,
        seed=seed,
    )
    validation_subject_set = set(validation_subjects)

    validated: list[
        tuple[str, np.ndarray, np.ndarray, np.ndarray, tuple[int, int], tuple[int, int]]
    ] = []
    candidates: list[_WindowCandidate] = []
    ignored_background = 0
    rejected_low_purity = 0
    seen_names: set[str] = set()

    for annotation_index, raw_item in enumerate(annotations):
        video = _validate_video(raw_item, expected_num_keypoints=expected_num_keypoints)
        frame_dir, _, _, labels, _, _ = video
        if frame_dir in seen_names:
            raise ValueError(f"duplicate SAFER frame_dir: {frame_dir!r}")
        seen_names.add(frame_dir)
        validated.append(video)
        if frame_dir in test_names:
            target_split = Split.TEST
        elif frame_dir in train_names:
            subject = extract_safer_subject(frame_dir)
            target_split = (
                Split.VALIDATION if subject in validation_subject_set else Split.TRAIN
            )
        else:
            continue
        if labels.shape[0] < window_size:
            continue

        starts = list(range(0, labels.shape[0] - window_size + 1, stride))
        tail_start = labels.shape[0] - window_size
        if starts[-1] != tail_start:
            starts.append(tail_start)
        mapped = _mapped_labels(labels)
        for start in starts:
            stop = start + window_size
            center_target = int(mapped[start + window_size // 2])
            if center_target < 0:
                ignored_background += 1
                continue
            purity = float(np.mean(mapped[start:stop] == center_target))
            if purity < minimum_purity:
                rejected_low_purity += 1
                continue
            candidates.append(
                _WindowCandidate(
                    annotation_index=annotation_index,
                    frame_dir=frame_dir,
                    split=target_split,
                    label=center_target,
                    start=start,
                    stop=stop,
                )
            )

    missing_protocol_videos = (train_names | test_names) - seen_names
    if missing_protocol_videos:
        examples = sorted(missing_protocol_videos)[:5]
        raise ValueError(
            "SAFER subject split references videos absent from annotations: "
            f"{examples}"
        )

    grouped: dict[tuple[Split, int], list[_WindowCandidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[(candidate.split, candidate.label)].append(candidate)
    selected: list[_WindowCandidate] = []
    for group in grouped.values():
        ranked = sorted(group, key=lambda candidate: _candidate_rank(candidate, seed))
        selected.extend(
            ranked
            if max_per_class_per_split is None
            else ranked[:max_per_class_per_split]
        )
    selected.sort(key=lambda item: (item.split.value, item.frame_dir, item.start))

    output_splits: dict[str, list[str]] = {split.value: [] for split in Split}
    output_annotations: list[dict[str, Any]] = []
    split_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    for candidate in selected:
        frame_dir, keypoint, score, _, img_shape, original_shape = validated[
            candidate.annotation_index
        ]
        sample_id = f"{frame_dir}::frames-{candidate.start:06d}-{candidate.stop:06d}"
        output_splits[candidate.split.value].append(sample_id)
        split_counts[candidate.split.value] += 1
        state = A1_STATE_ORDER[candidate.label]
        class_counts[state.value] += 1
        output_annotations.append(
            {
                "frame_dir": sample_id,
                "total_frames": window_size,
                "img_shape": img_shape,
                "original_shape": original_shape,
                "label": candidate.label,
                "keypoint": keypoint[:, candidate.start : candidate.stop].astype(
                    np.float32, copy=True
                ),
                "keypoint_score": score[:, candidate.start : candidate.stop].astype(
                    np.float32, copy=True
                ),
                "source_frame_dir": frame_dir,
                "source_start_frame": candidate.start,
                "source_end_frame": candidate.stop,
            }
        )

    missing_groups = [
        f"{split.value}/{state.value}"
        for split in Split
        for state in A1_STATE_ORDER
        if not grouped.get((split, A1_STATE_TO_CLASS[state]))
    ]
    if missing_groups:
        raise ValueError(
            "SAFER conversion produced no eligible windows for: " + ", ".join(missing_groups)
        )

    summary = SaferPoseSummary(
        video_count=len(validated),
        window_count=len(output_annotations),
        split_counts=dict(sorted(split_counts.items())),
        class_counts=dict(sorted(class_counts.items())),
        validation_subjects=validation_subjects,
        ignored_background_centers=ignored_background,
        rejected_low_purity=rejected_low_purity,
    )
    return {"split": output_splits, "annotations": output_annotations}, summary


def write_safer_posec3d_annotations(
    source: str | Path | BinaryIO,
    output_path: str | Path,
    **kwargs: Any,
) -> SaferPoseSummary:
    destination = Path(output_path).resolve()
    if destination.suffix.lower() != ".pkl":
        raise ValueError("output_path must use the .pkl suffix")
    if not hasattr(source, "read") and Path(source).resolve() == destination:
        raise ValueError("output_path must not overwrite the source SAFER pickle")
    payload = load_numpy_pickle(source)
    converted, summary = build_safer_posec3d_annotations(payload, **kwargs)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        pickle.dump(converted, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return summary
