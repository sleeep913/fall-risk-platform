from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True, order=True)
class Event:
    start: float
    end: float
    event_id: str = ""

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError("event start must be non-negative")
        if self.end < self.start:
            raise ValueError("event end must not precede event start")


@dataclass(frozen=True)
class EventMetrics:
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    false_alarms_per_hour: float
    mean_lead_time_seconds: float | None


def _safe_divide(numerator: int | float, denominator: int | float) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def event_metrics(
    truth_events: Iterable[Event],
    predicted_events: Iterable[Event],
    *,
    observation_seconds: float,
    max_early_warning_seconds: float = 3.0,
) -> EventMetrics:
    """Greedily match one predicted alarm to one true event.

    A prediction may begin within the configured early-warning window or during the true event.
    Repeated frame alarms must be merged into event intervals before calling this function.
    """

    truth = sorted(truth_events)
    predictions = sorted(predicted_events)
    if observation_seconds <= 0:
        raise ValueError("observation_seconds must be positive")
    if max_early_warning_seconds < 0:
        raise ValueError("max_early_warning_seconds must be non-negative")

    unmatched = set(range(len(predictions)))
    lead_times: list[float] = []
    matched = 0
    for event in truth:
        candidates = [
            index
            for index in unmatched
            if predictions[index].start >= event.start - max_early_warning_seconds
            and predictions[index].start <= event.end
        ]
        if not candidates:
            continue
        selected = min(candidates, key=lambda index: predictions[index].start)
        unmatched.remove(selected)
        matched += 1
        lead_times.append(event.start - predictions[selected].start)

    false_positives = len(unmatched)
    false_negatives = len(truth) - matched
    precision = _safe_divide(matched, matched + false_positives)
    recall = _safe_divide(matched, matched + false_negatives)
    f1 = _safe_divide(2 * precision * recall, precision + recall)
    return EventMetrics(
        true_positives=matched,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=precision,
        recall=recall,
        f1=f1,
        false_alarms_per_hour=false_positives / (observation_seconds / 3600.0),
        mean_lead_time_seconds=mean(lead_times) if lead_times else None,
    )
