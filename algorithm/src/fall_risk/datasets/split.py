from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Iterable

from fall_risk.contracts.labels import Split
from fall_risk.datasets.manifest import ManifestRecord


def _split_counts(subject_count: int, ratios: tuple[float, float, float]) -> tuple[int, int, int]:
    if subject_count < 3:
        raise ValueError("at least three subjects are required for train/validation/test splitting")
    if any(value <= 0 for value in ratios):
        raise ValueError("all split ratios must be positive")
    total = sum(ratios)
    normalized = tuple(value / total for value in ratios)
    validation_count = max(1, round(subject_count * normalized[1]))
    test_count = max(1, round(subject_count * normalized[2]))
    train_count = subject_count - validation_count - test_count
    if train_count < 1:
        validation_count = 1
        test_count = 1
        train_count = subject_count - 2
    return train_count, validation_count, test_count


def assign_subject_splits(
    records: Iterable[ManifestRecord],
    *,
    ratios: tuple[float, float, float] = (0.7, 0.15, 0.15),
    seed: int = 20260821,
) -> list[ManifestRecord]:
    """Assign deterministic splits while keeping each dataset subject in exactly one split."""

    rows = list(records)
    if not rows:
        raise ValueError("records must not be empty")

    subjects_by_dataset: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for record in rows:
        subjects_by_dataset[record.dataset].add(record.subject_key)

    assignments: dict[tuple[str, str], Split] = {}
    for dataset in sorted(subjects_by_dataset):
        subjects = sorted(subjects_by_dataset[dataset])
        train_count, validation_count, _ = _split_counts(len(subjects), ratios)
        dataset_seed = f"{seed}:{dataset}"
        random.Random(dataset_seed).shuffle(subjects)
        train_end = train_count
        validation_end = train_end + validation_count
        for subject in subjects[:train_end]:
            assignments[subject] = Split.TRAIN
        for subject in subjects[train_end:validation_end]:
            assignments[subject] = Split.VALIDATION
        for subject in subjects[validation_end:]:
            assignments[subject] = Split.TEST

    return [record.with_split(assignments[record.subject_key]) for record in rows]
