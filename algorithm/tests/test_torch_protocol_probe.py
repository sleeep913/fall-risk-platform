import os

import pytest

torch = pytest.importorskip("torch")

from fall_risk.models.torch_protocol_probe import TorchProtocolProbe  # noqa: E402


def test_torch_protocol_probe_random_tensor_forward() -> None:
    require_cuda = os.environ.get("FALL_RISK_REQUIRE_CUDA") == "1"
    if require_cuda and not torch.cuda.is_available():
        pytest.fail("FALL_RISK_REQUIRE_CUDA=1 but PyTorch cannot access CUDA")
    device = torch.device("cuda:0" if require_cuda else "cpu")
    expected_gpu = os.environ.get("FALL_RISK_EXPECTED_GPU")
    if require_cuda and expected_gpu:
        actual_gpu = torch.cuda.get_device_name(0)
        if expected_gpu.casefold() not in actual_gpu.casefold():
            pytest.fail(f"expected GPU containing {expected_gpu!r}, got {actual_gpu!r}")

    model = TorchProtocolProbe().to(device).eval()
    modality_mask = torch.tensor(
        [[True, True, False, False], [True, False, False, True]], device=device
    )
    quality = torch.rand(2, 4, device=device)
    with torch.inference_mode():
        output = model(modality_mask, quality)
    assert output["state_probabilities"].shape == (2, 5)
    assert output["risk_probabilities"].shape == (2, 2)
    assert output["uncertainty"].shape == (2,)
    assert output["modality_weights"].shape == (2, 4)
    assert torch.all(output["risk_probabilities"][:, 1] >= output["risk_probabilities"][:, 0])
    assert torch.allclose(output["modality_weights"].sum(dim=1), torch.ones(2, device=device))
    assert output["risk_probabilities"].device == device
