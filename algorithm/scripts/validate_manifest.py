from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(PROJECT_SRC))

from fall_risk.datasets import audit_leakage, load_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a fall-risk JSONL manifest")
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()

    try:
        records = load_manifest(args.manifest)
        report = audit_leakage(records)
        report.raise_for_errors()
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    subjects = {(record.dataset, record.subject_id) for record in records}
    trials = {record.trial_key for record in records}
    print(
        f"manifest valid: {len(records)} samples, "
        f"{len(subjects)} subjects, {len(trials)} trials"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
