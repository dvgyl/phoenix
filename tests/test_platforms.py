import platform
import subprocess
from unittest.mock import Mock

import pytest

from phoenix_eval import platforms


def test_native_mode_matches_daemon_architecture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        subprocess,
        "run",
        Mock(return_value=subprocess.CompletedProcess([], 0, "linux aarch64 29.5\n")),
    )
    assert platforms.verify_runtime("native-arm64").arm64_engine == "native"
    with pytest.raises(ValueError, match="does not match"):
        platforms.verify_runtime("native-amd64")


def test_apple_mode_requires_rosetta_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")
    monkeypatch.setenv("COLIMA_HOME", "/colima")
    monkeypatch.setenv("DOCKER_HOST", "unix:///colima/default/docker.sock")
    daemon = subprocess.CompletedProcess([], 0, "linux arm64 29.5\n")
    rosetta = subprocess.CompletedProcess(
        [], 0, "enabled\ninterpreter /mnt/lima-rosetta/rosetta\n"
    )
    inactive = subprocess.CompletedProcess([], 0, "disabled\n")
    monkeypatch.setattr(
        subprocess, "run", Mock(side_effect=[daemon, rosetta, daemon, inactive])
    )
    assert platforms.verify_runtime("apple-silicon").amd64_engine == "rosetta"
    with pytest.raises(ValueError, match="Rosetta registration"):
        platforms.verify_runtime("apple-silicon")
