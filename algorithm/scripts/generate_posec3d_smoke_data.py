from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from fall_risk.contracts import Split
from fall_risk.datasets import ManifestRecord, write_manifest
from fall_risk.posec3d import A1_STATE_ORDER, write_mmaction_pose_annotations


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate non-scientific synthetic data for the A1 engineering smoke test."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--train", type=int, default=10)
    parser.add_argument("--validation", type=int, default=5)
    parser.add_argument("--test", type=int, default=5)
    parser.add_argument("--frames", type=int, default=48)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def _pose_window(
    rng: np.random.Generator,
    *,
    frames: int,
    label_index: int,
) -> tuple[np.ndarray, np.ndarray]:
    keypoint = np.empty((1, frames, 17, 2), dtype=np.float32)
    base_x = np.linspace(92.0, 164.0, 17, dtype=np.float32)
    base_y = np.linspace(48.0, 208.0, 17, dtype=np.float32)
    temporal = np.linspace(0.0, 1.0, frames, dtype=np.float32)
    for frame_index, progress in enumerate(temporal):
        horizontal_shift = label_index * 3.0 * progress
        vertical_shift = label_index * 6.0 * progress
        keypoint[0, frame_index, :, 0] = base_x + horizontal_shift
        keypoint[0, frame_index, :, 1] = base_y + vertical_shift
    keypoint += rng.normal(0.0, 0.8, size=keypoint.shape).astype(np.float32)
    score = np.clip(
        rng.normal(0.95, 0.02, size=keypoint.shape[:3]), 0.0, 1.0
    ).astype(np.float32)
    return keypoint, score


def main() -> None:
    args = parse_args()
    if min(args.train, args.validation, args.test, args.frames) <= 0:
        raise ValueError("all split sizes and --frames must be positive")

    output_dir = args.output_dir.resolve()
    pose_dir = output_dir / "pose"
    pose_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)
    records: list[ManifestRecord] = []
    states = list(A1_STATE_ORDER)
    split_sizes = {
        Split.TRAIN: args.train,
        Split.VALIDATION: args.validation,
        Split.TEST: args.test,
    }

    for split, count in split_sizes.items():
        for index in range(count):
            state = states[index % len(states)]
            sample_id = f"a1-smoke-{split.value}-{index:04d}"
            artifact_path = pose_dir / f"{sample_id}.npz"
            keypoint, score = _pose_window(
                rng,
                frames=args.frames,
                label_index=states.index(state),
            )
            np.savez_compressed(
                artifact_path,
                keypoint=keypoint,
                keypoint_score=score,
                img_shape=np.asarray([256, 256], dtype=np.int32),
                original_shape=np.asarray([256, 256], dtype=np.int32),
            )
            records.append(
                ManifestRecord(
                    sample_id=sample_id,
                    dataset="A1_SYNTHETIC_SMOKE_ONLY",
                    subject_id=f"{split.value}-subject-{index:04d}",
                    trial_id=f"trial-{index:04d}",
                    start_time=0.0,
                    end_time=args.frames / 24.0,
                    state_label=state,
                    modalities={"skeleton": str(artifact_path.relative_to(output_dir))},
                    split=split,
                )
            )

    manifest_path = output_dir / "manifest.jsonl"
    annotation_path = output_dir / "posec3d_annotations.pkl"
    write_manifest(records, manifest_path)
    summary = write_mmaction_pose_annotations(
        records,
        annotation_path,
        data_root=output_dir,
    )
    print(f"manifest: {manifest_path}")
    print(f"annotations: {annotation_path}")
    print(f"samples: {summary.sample_count}; splits: {dict(summary.split_counts)}")
    print("warning: synthetic data validates engineering only and has no scientific value")


if __name__ == "__main__":
    main()
