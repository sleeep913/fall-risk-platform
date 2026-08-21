from __future__ import annotations

from collections.abc import Iterable


def _validated_binary_inputs(
    y_true: Iterable[int | bool], probabilities: Iterable[float]
) -> tuple[list[int], list[float]]:
    truth = [int(value) for value in y_true]
    scores = [float(value) for value in probabilities]
    if not truth:
        raise ValueError("y_true must not be empty")
    if len(truth) != len(scores):
        raise ValueError("y_true and probabilities must have the same length")
    if any(value not in (0, 1) for value in truth):
        raise ValueError("y_true must contain only binary values")
    if any(not 0.0 <= value <= 1.0 for value in scores):
        raise ValueError("probabilities must be within [0, 1]")
    return truth, scores


def brier_score(y_true: Iterable[int | bool], probabilities: Iterable[float]) -> float:
    truth, scores = _validated_binary_inputs(y_true, probabilities)
    return sum((score - label) ** 2 for label, score in zip(truth, scores, strict=True)) / len(
        truth
    )


def expected_calibration_error(
    y_true: Iterable[int | bool],
    probabilities: Iterable[float],
    *,
    bins: int = 10,
) -> float:
    truth, scores = _validated_binary_inputs(y_true, probabilities)
    if bins < 1:
        raise ValueError("bins must be positive")

    total = len(truth)
    error = 0.0
    for bin_index in range(bins):
        lower = bin_index / bins
        upper = (bin_index + 1) / bins
        members = [
            index
            for index, score in enumerate(scores)
            if lower <= score < upper or (bin_index == bins - 1 and score == 1.0)
        ]
        if not members:
            continue
        confidence = sum(scores[index] for index in members) / len(members)
        accuracy = sum(truth[index] for index in members) / len(members)
        error += (len(members) / total) * abs(accuracy - confidence)
    return error
