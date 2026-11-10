import platform
import subprocess
from unittest.mock import Mock

import pytest

from phoenix_eval import platforms

ROSETTA = """enabled

registration rosetta
enabled
interpreter /mnt/lima-rosetta/rosetta
flags: OCF
offset 0
magic 7f454c4602010100000000000000000002003e00
mask fffffffffffefe00fffffffffffffffffeffffff

registration qemu-x86_64
disabled
interpreter /usr/bin/qemu-x86_64
"""


def test_native_mode_matches_daemon_architecture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DOCKER_CONTEXT", raising=False)
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        subprocess,
        "run",
        Mock(return_value=subprocess.CompletedProcess([], 0, "linux aarch64 29.5\n")),
    )
    assert platforms.verify_runtime("native-arm64").arm64_engine == "native"
    with pytest.raises(ValueError, match="does not match"):
        platforms.verify_runtime("native-amd64")


def test_apple_mode_records_all_registrations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOCKER_CONTEXT", raising=False)
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")
    monkeypatch.setenv("COLIMA_HOME", "/colima")
    monkeypatch.setenv("DOCKER_HOST", "unix:///colima/default/docker.sock")
    daemon = subprocess.CompletedProcess([], 0, "linux arm64 29.5\n")
    rosetta = subprocess.CompletedProcess([], 0, ROSETTA)
    mock_run = Mock(side_effect=[daemon, rosetta])
    monkeypatch.setattr(subprocess, "run", mock_run)
    evidence = platforms.verify_runtime("apple-silicon")
    assert evidence.amd64_engine == "rosetta"
    assert evidence.binfmt_registrations == ROSETTA
    assert mock_run.call_args_list[0].args[0][:4] == (
        "docker",
        "--host",
        "unix:///colima/default/docker.sock",
        "info",
    )


def test_alternate_handler_name_cannot_mask_duplicate_x86_emulation() -> None:
    alias = (
        "\nregistration another-engine\nenabled\ninterpreter /usr/bin/qemu-x86_64\n"
        "flags: OCF\noffset 18\nmagic 3e00\nmask ffff\n"
    )
    with pytest.raises(ValueError, match="another-engine"):
        platforms.verify_binfmt(ROSETTA + alias)
    platforms.verify_binfmt(ROSETTA + alias.replace("magic 3e00", "magic b700"))


def test_runtime_rejects_context_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKER_CONTEXT", "different-context")
    with pytest.raises(ValueError, match="Docker context override"):
        platforms.verify_runtime("apple-silicon")


def test_runtime_requires_active_rosetta() -> None:
    with pytest.raises(ValueError, match="Rosetta registration"):
        platforms.verify_binfmt("enabled\n")
