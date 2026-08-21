from __future__ import annotations

import argparse
import io
import json
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, BinaryIO

import numpy as np

from fall_risk.posec3d import load_numpy_pickle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely summarize the structure of an official SAFER annotation pickle."
    )
    parser.add_argument("path", type=Path, help="A .pkl file or SAFER .zip archive")
    parser.add_argument(
        "--entry",
        help="Pickle entry inside the ZIP; defaults to the smallest .pkl entry",
    )
    return parser.parse_args()


def _open_payload(path: Path, entry_name: str | None) -> tuple[BinaryIO, Any]:
    if path.suffix.lower() == ".pkl":
        return path.open("rb"), None
    if path.suffix.lower() != ".zip":
        raise ValueError("path must be an official .pkl file or .zip archive")

    archive = zipfile.ZipFile(path)
    pickle_entries = [item for item in archive.infolist() if item.filename.endswith(".pkl")]
    if not pickle_entries:
        archive.close()
        raise ValueError("ZIP archive does not contain any .pkl files")
    if entry_name is None:
        selected = min(pickle_entries, key=lambda item: item.file_size)
    else:
        matches = [item for item in pickle_entries if item.filename == entry_name]
        if not matches:
            archive.close()
            raise ValueError(f"ZIP entry does not exist: {entry_name}")
        selected = matches[0]
    stream = archive.open(selected)
    return stream, archive


def _array_summary(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, np.ndarray):
        return None
    return {
        "shape": list(value.shape),
        "dtype": str(value.dtype),
        "finite": bool(np.isfinite(value).all()) if np.issubdtype(value.dtype, np.number) else None,
    }


def summarize(payload: Any) -> dict[str, Any]:
    report: dict[str, Any] = {"root_type": type(payload).__name__}
    annotations: list[Any] | None = None
    if isinstance(payload, dict):
        report["root_keys"] = sorted(str(key) for key in payload)
        split = payload.get("split")
        if isinstance(split, dict):
            report["split_counts"] = {
                str(name): len(values) for name, values in sorted(split.items())
            }
        candidate = payload.get("annotations")
        if isinstance(candidate, list):
            annotations = candidate
    elif isinstance(payload, list):
        annotations = payload

    if annotations is None:
        return report
    report["annotation_count"] = len(annotations)
    label_counts = Counter(
        str(item.get("label")) for item in annotations if isinstance(item, dict)
    )
    report["label_counts"] = dict(sorted(label_counts.items()))
    frame_label_counts: dict[str, Counter[int]] = {
        "labels": Counter(),
        "full_labels": Counter(),
    }
    for item in annotations:
        if not isinstance(item, dict):
            continue
        for field_name, counts in frame_label_counts.items():
            values = item.get(field_name)
            if not isinstance(values, np.ndarray) or values.ndim != 1:
                continue
            unique, frequencies = np.unique(values, return_counts=True)
            counts.update(
                {
                    int(value): int(frequency)
                    for value, frequency in zip(unique, frequencies, strict=True)
                }
            )
    report["frame_label_counts"] = {
        field_name: {str(label): count for label, count in sorted(counts.items())}
        for field_name, counts in frame_label_counts.items()
    }
    first = next((item for item in annotations if isinstance(item, dict)), None)
    if first is not None:
        report["first_annotation_keys"] = sorted(str(key) for key in first)
        report["first_annotation_scalars"] = {
            str(key): value
            for key, value in first.items()
            if isinstance(value, (bool, int, float, str))
        }
        report["first_annotation_arrays"] = {
            str(key): summary
            for key, value in first.items()
            if (summary := _array_summary(value)) is not None
        }
    return report


def main() -> None:
    args = parse_args()
    path = args.path.resolve()
    if not path.is_file():
        raise ValueError(f"annotation file does not exist: {path}")
    stream, owner = _open_payload(path, args.entry)
    try:
        buffered = io.BufferedReader(stream)
        payload = load_numpy_pickle(buffered)
        print(json.dumps(summarize(payload), ensure_ascii=False, indent=2, sort_keys=True))
    finally:
        stream.close()
        if owner is not None:
            owner.close()


if __name__ == "__main__":
    main()
