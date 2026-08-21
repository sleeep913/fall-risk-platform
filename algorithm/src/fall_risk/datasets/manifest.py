from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from fall_risk.contracts.labels import FallState, Modality, Split


@dataclass(frozen=True)
class ManifestRecord:
    sample_id: str
    dataset: str
    subject_id: str
    trial_id: str
    start_time: float
    end_time: float
    state_label: FallState
    modalities: Mapping[str, str]
    split: Split | None = None
    fall_start: float | None = None
    fall_impact: float | None = None

    def __post_init__(self) -> None:
        required_strings = {
            "sample_id": self.sample_id,
            "dataset": self.dataset,
            "subject_id": self.subject_id,
            "trial_id": self.trial_id,
        }
        for name, value in required_strings.items():
            if not value or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if self.start_time < 0:
            raise ValueError("start_time must be non-negative")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be greater than start_time")
        if not self.modalities:
            raise ValueError("at least one modality path is required")
        valid_modalities = {item.value for item in Modality}
        unknown = set(self.modalities) - valid_modalities
        if unknown:
            raise ValueError(f"unknown modalities: {sorted(unknown)}")
        if any(not str(path).strip() for path in self.modalities.values()):
            raise ValueError("modality paths must be non-empty strings")
        if self.fall_start is not None and self.fall_start < 0:
            raise ValueError("fall_start must be non-negative")
        if self.fall_impact is not None:
            if self.fall_start is None:
                raise ValueError("fall_impact requires fall_start")
            if self.fall_impact < self.fall_start:
                raise ValueError("fall_impact must not precede fall_start")

    @property
    def subject_key(self) -> tuple[str, str]:
        return self.dataset, self.subject_id

    @property
    def trial_key(self) -> tuple[str, str, str]:
        return self.dataset, self.subject_id, self.trial_id

    def with_split(self, split: Split) -> ManifestRecord:
        return replace(self, split=split)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state_label"] = self.state_label.value
        payload["split"] = self.split.value if self.split is not None else None
        payload["modalities"] = dict(self.modalities)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ManifestRecord:
        required = {
            "sample_id",
            "dataset",
            "subject_id",
            "trial_id",
            "start_time",
            "end_time",
            "state_label",
            "modalities",
        }
        missing = required - set(payload)
        if missing:
            raise ValueError(f"manifest record is missing fields: {sorted(missing)}")
        split_value = payload.get("split")
        return cls(
            sample_id=str(payload["sample_id"]),
            dataset=str(payload["dataset"]),
            subject_id=str(payload["subject_id"]),
            trial_id=str(payload["trial_id"]),
            start_time=float(payload["start_time"]),
            end_time=float(payload["end_time"]),
            state_label=FallState(str(payload["state_label"])),
            modalities={str(key): str(value) for key, value in dict(payload["modalities"]).items()},
            split=Split(str(split_value)) if split_value is not None else None,
            fall_start=(
                float(payload["fall_start"]) if payload.get("fall_start") is not None else None
            ),
            fall_impact=(
                float(payload["fall_impact"])
                if payload.get("fall_impact") is not None
                else None
            ),
        )


def load_manifest(path: str | Path) -> list[ManifestRecord]:
    manifest_path = Path(path)
    records: list[ManifestRecord] = []
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
                records.append(ManifestRecord.from_dict(payload))
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid manifest line {line_number}: {exc}") from exc
    if not records:
        raise ValueError("manifest must contain at least one record")
    return records


def write_manifest(records: Iterable[ManifestRecord], path: str | Path) -> None:
    manifest_path = Path(path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(records)
    if not rows:
        raise ValueError("cannot write an empty manifest")
    with manifest_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in rows:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True))
            handle.write("\n")
