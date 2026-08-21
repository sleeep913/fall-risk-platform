from __future__ import annotations

from collections.abc import Hashable, Iterable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ClassMetrics:
    precision: float
    recall: float
    f1: float
    support: int


@dataclass(frozen=True)
class ClassificationReport:
    labels: tuple[Hashable, ...]
    confusion_matrix: tuple[tuple[int, ...], ...]
    per_class: dict[Hashable, ClassMetrics]
    accuracy: float
    macro_f1: float


def _safe_divide(numerator: int | float, denominator: int | float) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def classification_report(
    y_true: Iterable[Hashable],
    y_pred: Iterable[Hashable],
    *,
    labels: Sequence[Hashable] | None = None,
) -> ClassificationReport:
    truth = list(y_true)
    predictions = list(y_pred)
    if not truth:
        raise ValueError("y_true must not be empty")
    if len(truth) != len(predictions):
        raise ValueError("y_true and y_pred must have the same length")

    ordered_labels = (
        tuple(labels) if labels is not None else tuple(dict.fromkeys(truth + predictions))
    )
    if not ordered_labels:
        raise ValueError("labels must not be empty")
    label_to_index = {label: index for index, label in enumerate(ordered_labels)}
    if len(label_to_index) != len(ordered_labels):
        raise ValueError("labels must be unique")
    unknown = (set(truth) | set(predictions)) - set(ordered_labels)
    if unknown:
        raise ValueError(f"values not present in labels: {sorted(map(str, unknown))}")

    matrix = [[0 for _ in ordered_labels] for _ in ordered_labels]
    for actual, predicted in zip(truth, predictions, strict=True):
        matrix[label_to_index[actual]][label_to_index[predicted]] += 1

    per_class: dict[Hashable, ClassMetrics] = {}
    for index, label in enumerate(ordered_labels):
        true_positive = matrix[index][index]
        false_positive = sum(row[index] for row in matrix) - true_positive
        false_negative = sum(matrix[index]) - true_positive
        support = sum(matrix[index])
        precision = _safe_divide(true_positive, true_positive + false_positive)
        recall = _safe_divide(true_positive, true_positive + false_negative)
        f1 = _safe_divide(2 * precision * recall, precision + recall)
        per_class[label] = ClassMetrics(precision, recall, f1, support)

    correct = sum(matrix[index][index] for index in range(len(ordered_labels)))
    accuracy = correct / len(truth)
    macro_f1 = sum(item.f1 for item in per_class.values()) / len(per_class)
    return ClassificationReport(
        labels=ordered_labels,
        confusion_matrix=tuple(tuple(row) for row in matrix),
        per_class=per_class,
        accuracy=accuracy,
        macro_f1=macro_f1,
    )
