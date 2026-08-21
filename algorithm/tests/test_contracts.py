from dataclasses import dataclass

import pytest

from fall_risk.contracts import ContractError, ModelInput, ModelOutput
from fall_risk.models import ProtocolProbeModel


@dataclass(frozen=True)
class FakeTensor:
    shape: tuple[int, ...]


def valid_input() -> ModelInput:
    return ModelInput(
        skeleton=FakeTensor((2, 16, 17, 3)),
        imu=FakeTensor((2, 100, 6)),
        environment=None,
        physiology=None,
        timestamps={
            "skeleton": FakeTensor((2, 16)),
            "imu": FakeTensor((2, 100)),
        },
        modality_mask=((True, True, False, False), (True, False, False, False)),
        quality=((0.9, 0.8, 0.0, 0.0), (0.6, 0.0, 0.0, 0.0)),
    )


def test_model_input_accepts_multimodal_and_missing_modalities() -> None:
    assert valid_input().validate() == 2


def test_model_input_rejects_sample_with_all_modalities_missing() -> None:
    model_input = valid_input()
    invalid = ModelInput(
        skeleton=model_input.skeleton,
        imu=model_input.imu,
        environment=None,
        physiology=None,
        timestamps=model_input.timestamps,
        modality_mask=((False, False, False, False), (True, False, False, False)),
        quality=model_input.quality,
    )
    with pytest.raises(ContractError, match="no available modality"):
        invalid.validate()


def test_model_input_rejects_timestamp_shape_mismatch() -> None:
    model_input = valid_input()
    invalid = ModelInput(
        skeleton=model_input.skeleton,
        imu=model_input.imu,
        environment=None,
        physiology=None,
        timestamps={"skeleton": FakeTensor((2, 15)), "imu": FakeTensor((2, 100))},
        modality_mask=model_input.modality_mask,
        quality=model_input.quality,
    )
    with pytest.raises(ContractError, match="timestamps.skeleton shape"):
        invalid.validate()


def test_protocol_probe_produces_valid_monotonic_risk() -> None:
    output = ProtocolProbeModel().predict(valid_input())
    assert output.validate(expected_batch_size=2) == 2
    assert all(risk_3s >= risk_1s for risk_1s, risk_3s in output.risk_probabilities)
    assert output.modality_weights[1][1:] == (0.0, 0.0, 0.0)


def test_model_output_rejects_non_monotonic_risk() -> None:
    output = ModelOutput(
        state_probabilities=((0.2, 0.2, 0.2, 0.2, 0.2),),
        risk_probabilities=((0.8, 0.4),),
        uncertainty=(0.2,),
        modality_weights=((1.0, 0.0, 0.0, 0.0),),
    )
    with pytest.raises(ContractError, match="risk probabilities"):
        output.validate()
