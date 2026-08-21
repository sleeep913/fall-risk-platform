from __future__ import annotations

from collections.abc import Iterable


def average_precision(y_true: Iterable[int | bool], y_score: Iterable[float]) -> float:
    """Compute binary average precision, the step-wise area under the PR curve."""

    truth = [int(value) for value in y_true]
    scores = [float(value) for value in y_score]
    if not truth:
        raise ValueError("y_true must not be empty")
    if len(truth) != len(scores):
        raise ValueError("y_true and y_score must have the same length")
    if any(value not in (0, 1) for value in truth):
        raise ValueError("y_true must contain only binary values")
    if any(not 0.0 <= value <= 1.0 for value in scores):
        raise ValueError("y_score values must be within [0, 1]")
    positive_count = sum(truth)
    if positive_count == 0:
        raise ValueError("average precision is undefined without positive samples")

    ranked = sorted(zip(scores, truth, strict=True), key=lambda item: item[0], reverse=True)
    true_positives = 0
    false_positives = 0
    previous_recall = 0.0
    area = 0.0
    index = 0
    while index < len(ranked):
        score = ranked[index][0]
        group_end = index
        while group_end < len(ranked) and ranked[group_end][0] == score:
            if ranked[group_end][1]:
                true_positives += 1
            else:
                false_positives += 1
            group_end += 1
        recall = true_positives / positive_count
        precision = true_positives / (true_positives + false_positives)
        area += (recall - previous_recall) * precision
        previous_recall = recall
        index = group_end
    return area
