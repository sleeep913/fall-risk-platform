import pytest

from fall_risk.evaluation import (
    Event,
    average_precision,
    brier_score,
    classification_report,
    event_metrics,
    expected_calibration_error,
)


def test_classification_report_separates_accuracy_and_macro_f1() -> None:
    report = classification_report(
        ["NORMAL", "NORMAL", "FALL", "FALL"],
        ["NORMAL", "FALL", "FALL", "FALL"],
        labels=["NORMAL", "FALL"],
    )
    assert report.accuracy == pytest.approx(0.75)
    assert report.per_class["NORMAL"].recall == pytest.approx(0.5)
    assert report.per_class["FALL"].precision == pytest.approx(2 / 3)
    assert report.macro_f1 == pytest.approx((2 / 3 + 0.8) / 2)


def test_average_precision() -> None:
    assert average_precision([1, 0, 1], [0.9, 0.8, 0.7]) == pytest.approx((1 + 2 / 3) / 2)


def test_average_precision_groups_tied_scores() -> None:
    assert average_precision([1, 0], [0.5, 0.5]) == pytest.approx(0.5)


def test_calibration_metrics() -> None:
    assert brier_score([0, 1], [0.1, 0.9]) == pytest.approx(0.01)
    assert expected_calibration_error([0, 1], [0.1, 0.9], bins=2) == pytest.approx(0.1)


def test_event_metrics_include_false_alarms_and_lead_time() -> None:
    result = event_metrics(
        [Event(10.0, 11.0, "fall-1"), Event(30.0, 31.0, "fall-2")],
        [Event(8.5, 9.5, "alarm-1"), Event(30.2, 30.5, "alarm-2"), Event(50.0, 51.0)],
        observation_seconds=3600.0,
        max_early_warning_seconds=3.0,
    )
    assert result.true_positives == 2
    assert result.false_positives == 1
    assert result.false_negatives == 0
    assert result.precision == pytest.approx(2 / 3)
    assert result.recall == pytest.approx(1.0)
    assert result.f1 == pytest.approx(0.8)
    assert result.false_alarms_per_hour == pytest.approx(1.0)
    assert result.mean_lead_time_seconds == pytest.approx(0.65)
