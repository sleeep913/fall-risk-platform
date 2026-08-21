from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the A1 three-class PoseC3D baseline")
    parser.add_argument("--ann-file", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--load-from", type=Path, help="Trusted local pretrained checkpoint")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from work_dir/last_checkpoint",
    )
    parser.add_argument("--max-epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument(
        "--learning-rate",
        type=float,
        help="Override linear scaling from the official 0.2 learning rate at batch 128",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--amp", action="store_true")
    parser.add_argument("--test-after-train", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.max_epochs <= 0 or args.batch_size <= 0 or args.num_workers < 0:
        raise ValueError("epochs and batch size must be positive; workers must be non-negative")
    if args.learning_rate is not None and args.learning_rate <= 0:
        raise ValueError("--learning-rate must be positive")
    ann_file = args.ann_file.resolve()
    if not ann_file.is_file():
        raise ValueError(f"annotation file does not exist: {ann_file}")
    if ann_file.suffix.lower() != ".pkl":
        raise ValueError("--ann-file must point to the generated .pkl file")
    if args.load_from is not None and not args.load_from.resolve().is_file():
        raise ValueError(f"checkpoint does not exist: {args.load_from.resolve()}")

    from mmaction.utils import register_all_modules
    from mmengine.config import Config
    from mmengine.runner import Runner

    register_all_modules(init_default_scope=True)
    default_config = Path(__file__).resolve().parents[1] / "configs" / "posec3d"
    config_path = (args.config or default_config / "safer_posec3d_a1.py").resolve()
    cfg = Config.fromfile(config_path)
    cfg.work_dir = str(args.work_dir.resolve())
    cfg.train_cfg.max_epochs = args.max_epochs
    cfg.randomness = dict(seed=args.seed, deterministic=True)
    cfg.resume = args.resume
    cfg.load_from = str(args.load_from.resolve()) if args.load_from is not None else None
    cfg.optim_wrapper.optimizer.lr = (
        args.learning_rate if args.learning_rate is not None else 0.2 * args.batch_size / 128
    )

    for loader_name in ("train_dataloader", "val_dataloader", "test_dataloader"):
        loader = cfg[loader_name]
        loader.batch_size = args.batch_size
        loader.num_workers = args.num_workers
        loader.persistent_workers = args.num_workers > 0
        loader.dataset.ann_file = str(ann_file)

    cfg.param_scheduler[0].T_max = args.max_epochs
    if args.amp:
        cfg.optim_wrapper.type = "AmpOptimWrapper"
        cfg.optim_wrapper.loss_scale = "dynamic"

    args.work_dir.mkdir(parents=True, exist_ok=True)
    cfg.dump(args.work_dir / "effective_config.py")
    runner = Runner.from_cfg(cfg)
    runner.train()
    if args.test_after_train:
        runner.test()


if __name__ == "__main__":
    main()
