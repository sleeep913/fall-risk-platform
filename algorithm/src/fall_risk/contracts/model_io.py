from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from fall_risk.contracts.labels import MODALITY_ORDER, STATE_ORDER, Modality


class ContractError(ValueError):
    """Raised when model input or output violates the frozen A0 contract."""


def _shape(value: Any, field: str) -> tuple[int, ...]:
    raw_shape = getattr(value, "shape", None)
    if raw_shape is None:
        raise ContractError(f"{field} must expose a shape attribute")
    try:
        return tuple(int(part) for part in raw_shape)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"{field} has an invalid shape: {raw_shape!r}") from exc


def _matrix_shape(value: Sequence[Sequence[Any]], field: str) -> tuple[int, int]:
    rows = list(value)
    if not rows:
        raise ContractError(f"{field} must contain at least one sample")
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ContractError(f"{field} must be rectangular")
    return len(rows), width


@dataclass(frozen=True)
class ModelInput:
    skeleton: Any | None
    imu: Any | None
    environment: Any | None
    physiology: Any | None
    timestamps: Mapping[str, Any]
    modality_mask: Sequence[Sequence[bool]]
    quality: Sequence[Sequence[float]]

    def validate(self) -> int:
        batch_size, mask_width = _matrix_shape(self.modality_mask, "modality_mask")
        quality_batch, quality_width = _matrix_shape(self.quality, "quality")
        expected_width = len(MODALITY_ORDER)
        if mask_width != expected_width or quality_width != expected_width:
            raise ContractError(
                f"modality_mask and quality must have {expected_width} columns "
                f"in the order {[item.value for item in MODALITY_ORDER]}"
            )
        if quality_batch != batch_size:
            raise ContractError("quality batch size must match modality_mask")

        for sample_index, (mask_row, quality_row) in enumerate(
            zip(self.modality_mask, self.quality, strict=True)
        ):
            if not any(bool(flag) for flag in mask_row):
                raise ContractError(f"sample {sample_index} has no available modality")
            for value in quality_row:
                if not 0.0 <= float(value) <= 1.0:
                    raise ContractError("quality values must be within [0, 1]")

        tensors = {
            Modality.SKELETON: self.skeleton,
            Modality.IMU: self.imu,
            Modality.ENVIRONMENT: self.environment,
            Modality.PHYSIOLOGY: self.physiology,
        }
        expected_ranks = {
            Modality.SKELETON: 4,
            Modality.IMU: 3,
            Modality.ENVIRONMENT: 3,
            Modality.PHYSIOLOGY: 3,
        }

        for column, modality in enumerate(MODALITY_ORDER):
            tensor = tensors[modality]
            is_used = any(bool(row[column]) for row in self.modality_mask)
            if is_used and tensor is None:
                raise ContractError(f"{modality.value} is marked available but has no tensor")
            if tensor is None:
                continue
            tensor_shape = _shape(tensor, modality.value)
            if len(tensor_shape) != expected_ranks[modality]:
                raise ContractError(
                    f"{modality.value} must have rank {expected_ranks[modality]}, "
                    f"got {tensor_shape}"
                )
            if tensor_shape[0] != batch_size:
                raise ContractError(f"{modality.value} batch size must be {batch_size}")
            if modality is Modality.SKELETON and tensor_shape[-1] != 3:
                raise ContractError("skeleton last dimension must be x, y, confidence")

            timestamp_tensor = self.timestamps.get(modality.value)
            if timestamp_tensor is None:
                raise ContractError(f"timestamps.{modality.value} is required")
            timestamp_shape = _shape(timestamp_tensor, f"timestamps.{modality.value}")
            if timestamp_shape != tensor_shape[:2]:
                raise ContractError(
                    f"timestamps.{modality.value} shape must be {tensor_shape[:2]}, "
                    f"got {timestamp_shape}"
                )
        return batch_size


@dataclass(frozen=True)
class ModelOutput:
    state_probabilities: Sequence[Sequence[float]]
    risk_probabilities: Sequence[Sequence[float]]
    uncertainty: Sequence[float]
    modality_weights: Sequence[Sequence[float]]

    def validate(self, expected_batch_size: int | None = None) -> int:
        batch_size, state_width = _matrix_shape(
            self.state_probabilities, "state_probabilities"
        )
        risk_batch, risk_width = _matrix_shape(
            self.risk_probabilities, "risk_probabilities"
        )
        weight_batch, weight_width = _matrix_shape(self.modality_weights, "modality_weights")

        if expected_batch_size is not None and batch_size != expected_batch_size:
            raise ContractError(f"output batch size must be {expected_batch_size}")
        if risk_batch != batch_size or weight_batch != batch_size:
            raise ContractError("all output tensors must share the same batch size")
        if len(self.uncertainty) != batch_size:
            raise ContractError("uncertainty must contain one value per sample")
        if state_width != len(STATE_ORDER):
            raise ContractError(f"state_probabilities must have {len(STATE_ORDER)} columns")
        if risk_width != 2:
            raise ContractError("risk_probabilities must contain 1-second and 3-second risk")
        if weight_width != len(MODALITY_ORDER):
            raise ContractError(f"modality_weights must have {len(MODALITY_ORDER)} columns")

        for row in self.state_probabilities:
            if any(not 0.0 <= float(value) <= 1.0 for value in row):
                raise ContractError("state probabilities must be within [0, 1]")
            if abs(sum(float(value) for value in row) - 1.0) > 1e-6:
                raise ContractError("state probabilities must sum to 1")
        for risk_1s, risk_3s in self.risk_probabilities:
            if not 0.0 <= float(risk_1s) <= float(risk_3s) <= 1.0:
                raise ContractError("risk probabilities must satisfy 0 <= risk_1s <= risk_3s <= 1")
        for value in self.uncertainty:
            if not 0.0 <= float(value) <= 1.0:
                raise ContractError("uncertainty must be within [0, 1]")
        for row in self.modality_weights:
            if any(not 0.0 <= float(value) <= 1.0 for value in row):
                raise ContractError("modality weights must be within [0, 1]")
            if abs(sum(float(value) for value in row) - 1.0) > 1e-6:
                raise ContractError("modality weights must sum to 1")
        return batch_size
