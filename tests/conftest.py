"""Shared test settings.

Hypothesis property tests have no time limit. A test result must not
depend on the speed or the load of the host.
"""

from pathlib import Path

import pytest
from hypothesis import settings

settings.register_profile("phoenix", deadline=None)
settings.load_profile("phoenix")


@pytest.fixture(autouse=True)
def isolated_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHOENIX_ROOT", str(tmp_path))
