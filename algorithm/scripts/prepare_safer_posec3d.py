from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from fall_risk.posec3d import write_safer_posec3d_annotations


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert the official SAFER non-wheelchair long-video pose pickle into "
            "subject-safe, three-class PoseC3D windows."
        )
    )
    parser.add_argument("input", type=Path, help="Extracted aic_normal_dataset_with_3d.pkl")
    parser.add_argument("output", type=Path, help="Destination MMAction2 .pkl file")
    parser.add_argument("--window-size", type=int, default=48)
    parser.add_argument("--stride", type=int, default=24)
    parser.add_argument("--minimum-purity", type=float, default=0.6)
    parser.add_argument("--validation-fraction", type=float, default=0.15)
    parser.add_argument(
        "--max-per-class-per-split",
        type=int,
        default=200,
        help="Deterministic cap for a first run; pass 0 to keep every eligible window",
    )
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.input.resolve()
    if not source.is_file() or source.suffix.lower() != ".pkl":
        raise ValueError("input must be an extracted SAFER .pkl file")
    destination = args.output.resolve()
    cap = args.max_per_class_per_split or None
    summary = write_safer_posec3d_annotations(
        source,
        destination,
        window_size=args.window_size,
        stride=args.stride,
        minimum_purity=args.minimum_purity,
        validation_fraction=args.validation_fraction,
        max_per_class_per_split=cap,
        seed=args.seed,
    )
    report = asdict(summary)
    report["input"] = str(source)
    report["output"] = str(destination)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
