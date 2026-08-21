from __future__ import annotations

from fall_risk.contracts.model_io import ModelInput, ModelOutput


class ProtocolProbeModel:
    """Dependency-free deterministic model used to verify the frozen A0 protocol."""

    def predict(self, model_input: ModelInput) -> ModelOutput:
        batch_size = model_input.validate()
        state_probabilities: list[tuple[float, ...]] = []
        risk_probabilities: list[tuple[float, float]] = []
        uncertainty: list[float] = []
        modality_weights: list[tuple[float, ...]] = []

        for sample_index in range(batch_size):
            mask = [bool(value) for value in model_input.modality_mask[sample_index]]
            quality = [float(value) for value in model_input.quality[sample_index]]
            active_quality = [
                value if available else 0.0
                for value, available in zip(quality, mask, strict=True)
            ]
            total_quality = sum(active_quality)
            available_count = sum(mask)
            if total_quality > 0:
                weights = tuple(value / total_quality for value in active_quality)
            else:
                weights = tuple((1.0 / available_count) if available else 0.0 for available in mask)

            weighted_quality = sum(
                weight * value for weight, value in zip(weights, active_quality, strict=True)
            )
            risk_1s = min(0.95, max(0.05, 0.35 - 0.20 * weighted_quality))
            risk_3s = min(1.0, risk_1s + 0.15)
            normal = 0.45 + 0.25 * weighted_quality
            remaining = 1.0 - normal
            states = (
                normal,
                remaining * 0.35,
                remaining * 0.25,
                remaining * 0.25,
                remaining * 0.15,
            )

            state_probabilities.append(states)
            risk_probabilities.append((risk_1s, risk_3s))
            uncertainty.append(1.0 - weighted_quality)
            modality_weights.append(weights)

        output = ModelOutput(
            state_probabilities=tuple(state_probabilities),
            risk_probabilities=tuple(risk_probabilities),
            uncertainty=tuple(uncertainty),
            modality_weights=tuple(modality_weights),
        )
        output.validate(expected_batch_size=batch_size)
        return output
