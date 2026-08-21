from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import sys
from typing import Any

EXPECTED_PREFIXES = {
    "numpy": "1.",
    "torch": "2.4.1",
    "torchvision": "0.19.1",
    "mmengine": "0.10.5",
    "mmcv-lite": "2.1.0",
    "mmaction2": "1.2.0",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the A1 PoseC3D training environment")
    parser.add_argument("--require-cuda", action="store_true")
    parser.add_argument("--expected-gpu", help="Case-insensitive GPU name fragment")
    return parser.parse_args()


def installed_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def main() -> None:
    args = parse_args()
    report: dict[str, Any] = {
        "python": platform.python_version(),
        "packages": {},
        "cuda": {},
        "errors": [],
    }
    if not ((3, 10) <= sys.version_info[:2] < (3, 13)):
        report["errors"].append("Python must be 3.10, 3.11, or 3.12")

    for distribution, expected_prefix in EXPECTED_PREFIXES.items():
        version = installed_version(distribution)
        report["packages"][distribution] = version
        if version is None:
            report["errors"].append(f"missing package: {distribution}")
        elif not version.startswith(expected_prefix):
            report["errors"].append(
                f"{distribution} must start with {expected_prefix}, got {version}"
            )
    conflicting_mmcv = installed_version("mmcv")
    if conflicting_mmcv is not None:
        report["errors"].append(
            f"mmcv {conflicting_mmcv} conflicts with the required mmcv-lite 2.1.0"
        )

    try:
        import torch

        available = bool(torch.cuda.is_available())
        report["cuda"]["available"] = available
        report["cuda"]["torch_cuda"] = torch.version.cuda
        report["cuda"]["device_count"] = torch.cuda.device_count() if available else 0
        report["cuda"]["device"] = torch.cuda.get_device_name(0) if available else None
        if args.require_cuda and not available:
            report["errors"].append("CUDA is required but torch.cuda.is_available() is false")
        if args.expected_gpu and available:
            if args.expected_gpu.casefold() not in report["cuda"]["device"].casefold():
                report["errors"].append(
                    f"visible GPU does not contain expected text: {args.expected_gpu!r}"
                )
    except Exception as exc:  # pragma: no cover - depends on the server installation
        report["errors"].append(f"failed to import torch: {type(exc).__name__}: {exc}")

    try:
        import mmaction  # noqa: F401
        from mmaction.utils import register_all_modules

        register_all_modules(init_default_scope=True)
    except Exception as exc:  # pragma: no cover - depends on the server installation
        report["errors"].append(f"failed to initialize MMAction2: {type(exc).__name__}: {exc}")

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
