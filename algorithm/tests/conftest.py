from __future__ import annotations

import shutil
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def workspace_tmp_path() -> Iterator[Path]:
    """Create test files inside the ignored workspace tmp directory.

    Some Windows machines retain a pytest system-temp directory with an ACL owned by a
    different process. Keeping A0 artifacts inside the repository avoids depending on that
    global directory while still cleaning every test case after use.
    """

    repository_root = Path(__file__).resolve().parents[2]
    base_directory = repository_root / "tmp" / "algorithm-pytest"
    case_directory = base_directory / uuid.uuid4().hex
    case_directory.mkdir(parents=True, exist_ok=False)
    try:
        yield case_directory
    finally:
        shutil.rmtree(case_directory, ignore_errors=True)
        try:
            base_directory.rmdir()
        except OSError:
            pass
