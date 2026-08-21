from __future__ import annotations

from typing import Any

try:
    import torch
    from torch import nn
except ImportError as exc:  # pragma: no cover - exercised only without the optional dependency
    raise ImportError("torch_protocol_probe requires the optional train dependency") from exc


class TorchProtocolProbe(nn.Module):
    """Small tensor-only module for CPU/GPU contract and export smoke tests."""

    def forward(self, modality_mask: Any, quality: Any) -> dict[str, Any]:
        mask = modality_mask.to(dtype=quality.dtype)
        if mask.ndim != 2 or mask.shape[1] != 4:
            raise ValueError("modality_mask must have shape [B, 4]")
        if quality.shape != mask.shape:
            raise ValueError("quality must have shape [B, 4]")
        if torch.any(mask.sum(dim=1) == 0):
            raise ValueError("each sample must have at least one available modality")

        masked_quality = quality.clamp(0.0, 1.0) * mask
        denominators = masked_quality.sum(dim=1, keepdim=True)
        uniform = mask / mask.sum(dim=1, keepdim=True)
        weights = torch.where(
            denominators > 0,
            masked_quality / denominators.clamp_min(1e-8),
            uniform,
        )
        aggregate_quality = (weights * masked_quality).sum(dim=1)
        uncertainty = 1.0 - aggregate_quality
        risk_1s = (0.35 - 0.20 * aggregate_quality).clamp(0.05, 0.95)
        risk_3s = (risk_1s + 0.15).clamp(max=1.0)
        remaining = 1.0 - (0.45 + 0.25 * aggregate_quality)
        state_probabilities = torch.stack(
            (
                1.0 - remaining,
                remaining * 0.35,
                remaining * 0.25,
                remaining * 0.25,
                remaining * 0.15,
            ),
            dim=1,
        )
        return {
            "state_probabilities": state_probabilities,
            "risk_probabilities": torch.stack((risk_1s, risk_3s), dim=1),
            "uncertainty": uncertainty,
            "modality_weights": weights,
        }
