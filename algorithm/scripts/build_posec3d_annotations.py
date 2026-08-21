from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from fall_risk.contracts import Split
from fall_risk.datasets import ManifestRecord, load_manifest
from fall_risk.posec3d import write_mmaction_pose_annotations


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert normalized skeleton NPZ windows to MMAction2 PoseDataset annotations."
    )
    parser.add_argument("manifest", type=Path, help="A0 JSONL manifest with assigned splits")
    parser.add_argument("output", type=Path, help="Destination .pkl annotation file")
    parser.add_argument(
        "--data-root",
        type=Path,
        help="Base directory for relative skeleton paths; defaults to the manifest directory",
    )
    parser.add_argument("--num-keypoints", type=int, default=17)
    parser.add_argument(
        "--max-per-split",
        type=int,
        help="Deterministically keep the first N records from each split for an A1 smoke run",
    )
    return parser.parse_args()


def limit_per_split(
    records: list[ManifestRecord], max_per_split: int | None
) -> list[ManifestRecord]:
    if max_per_split is None:
        return records
    if max_per_split <= 0:
        raise ValueError("--max-per-split must be positive")
    counts: Counter[Split] = Counter()
    selected: list[ManifestRecord] = []
    for record in records:
        if record.split is None:
            raise ValueError("every record must have an assigned split before limiting")
        if counts[record.split] < max_per_split:
            selected.append(record)
            counts[record.split] += 1
    return selected


def main() -> None:
    args = parse_args()
    records = limit_per_split(load_manifest(args.manifest), args.max_per_split)
    data_root = args.data_root or args.manifest.resolve().parent
    summary = write_mmaction_pose_annotations(
        records,
        args.output,
        data_root=data_root,
        expected_num_keypoints=args.num_keypoints,
    )
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "sample_count": summary.sample_count,
                "split_counts": summary.split_counts,
                "class_counts": summary.class_counts,
                "num_keypoints": summary.num_keypoints,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
