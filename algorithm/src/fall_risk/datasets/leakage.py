from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from fall_risk.contracts.labels import Split
from fall_risk.datasets.manifest import ManifestRecord


@dataclass(frozen=True)
class LeakageIssue:
    code: str
    message: str
    sample_ids: tuple[str, ...]


@dataclass(frozen=True)
class LeakageReport:
    issues: tuple[LeakageIssue, ...]

    @property
    def is_clean(self) -> bool:
        return not self.issues

    def raise_for_errors(self) -> None:
        if self.issues:
            details = "\n".join(f"- [{item.code}] {item.message}" for item in self.issues)
            raise ValueError(f"data leakage audit failed:\n{details}")


def _split_set(records: Iterable[ManifestRecord]) -> set[Split]:
    return {record.split for record in records if record.split is not None}


def audit_leakage(records: Iterable[ManifestRecord]) -> LeakageReport:
    rows = list(records)
    issues: list[LeakageIssue] = []
    sample_groups: dict[str, list[ManifestRecord]] = defaultdict(list)
    subject_groups: dict[tuple[str, str], list[ManifestRecord]] = defaultdict(list)
    trial_groups: dict[tuple[str, str, str], list[ManifestRecord]] = defaultdict(list)
    path_groups: dict[str, list[ManifestRecord]] = defaultdict(list)

    for record in rows:
        if record.split is None:
            issues.append(
                LeakageIssue(
                    code="MISSING_SPLIT",
                    message=f"sample {record.sample_id} has no split",
                    sample_ids=(record.sample_id,),
                )
            )
        sample_groups[record.sample_id].append(record)
        subject_groups[record.subject_key].append(record)
        trial_groups[record.trial_key].append(record)
        for path in record.modalities.values():
            path_groups[str(path)].append(record)

    for sample_id, group in sample_groups.items():
        if len(group) > 1:
            issues.append(
                LeakageIssue(
                    code="DUPLICATE_SAMPLE_ID",
                    message=f"sample_id {sample_id!r} occurs {len(group)} times",
                    sample_ids=tuple(record.sample_id for record in group),
                )
            )

    for subject_key, group in subject_groups.items():
        splits = _split_set(group)
        if len(splits) > 1:
            issues.append(
                LeakageIssue(
                    code="SUBJECT_CROSS_SPLIT",
                    message=(
                        f"subject {subject_key!r} appears in "
                        f"{sorted(item.value for item in splits)}"
                    ),
                    sample_ids=tuple(record.sample_id for record in group),
                )
            )

    for trial_key, group in trial_groups.items():
        splits = _split_set(group)
        if len(splits) > 1:
            issues.append(
                LeakageIssue(
                    code="TRIAL_CROSS_SPLIT",
                    message=(
                        f"trial {trial_key!r} appears in "
                        f"{sorted(item.value for item in splits)}"
                    ),
                    sample_ids=tuple(record.sample_id for record in group),
                )
            )
        ordered = sorted(group, key=lambda item: (item.start_time, item.end_time))
        for left_index, left in enumerate(ordered):
            for right in ordered[left_index + 1 :]:
                if right.start_time >= left.end_time:
                    break
                if left.split is not None and right.split is not None and left.split != right.split:
                    issues.append(
                        LeakageIssue(
                            code="OVERLAPPING_WINDOW_CROSS_SPLIT",
                            message=(
                                f"overlapping windows in trial {trial_key!r} cross "
                                f"{left.split.value}/{right.split.value}"
                            ),
                            sample_ids=(left.sample_id, right.sample_id),
                        )
                    )

    for path, group in path_groups.items():
        splits = _split_set(group)
        if len(splits) > 1:
            issues.append(
                LeakageIssue(
                    code="SOURCE_PATH_CROSS_SPLIT",
                    message=f"source path {path!r} appears in multiple splits",
                    sample_ids=tuple(record.sample_id for record in group),
                )
            )

    return LeakageReport(tuple(issues))
