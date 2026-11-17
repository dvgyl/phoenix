import fcntl
import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts import build_images

OLD = "sha256:" + "a" * 64
NEW = "sha256:" + "b" * 64


class ImageStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.refs = {"mutable": OLD}
        self.builds: list[tuple[str, str]] = []
        self.fail_build = False
        self.fail_listing = False
        self.lose_old = False

    def run(
        self, args: tuple[str, ...], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        if args[:3] == ("docker", "image", "ls"):
            if self.fail_listing:
                raise subprocess.CalledProcessError(1, args)
            return subprocess.CompletedProcess(args, 0, "\n".join(self.refs.values()))
        if args[:2] == ("docker", "tag"):
            assert args[2] in self.refs.values()
            self.refs[args[3]] = args[2]
            return subprocess.CompletedProcess(args, 0, "")
        self.builds.append((Path(args[0]).name, args[1]))
        for relative in (
            "slots/image-build.lock",
            "slots/compile/0.lock",
            "slots/execution/0.lock",
        ):
            with (self.root / relative).open("a+b") as stream:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.refs["mutable"] = NEW
        if self.lose_old:
            self.refs = {key: value for key, value in self.refs.items() if value != OLD}
        if self.fail_build:
            raise subprocess.CalledProcessError(1, args)
        return subprocess.CompletedProcess(args, 0, "")


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ImageStore:
    monkeypatch.setenv("PHOENIX_JOBS", "2")
    monkeypatch.setattr(build_images, "docker_cli", lambda: ("docker",))
    result = ImageStore(tmp_path)
    monkeypatch.setattr(subprocess, "run", result.run)
    return result


@pytest.mark.parametrize("kind", ["worker", "integrity"])
def test_replacing_a_build_tag_keeps_old_and_new_images(
    store: ImageStore, kind: str
) -> None:
    assert build_images.main([kind, "amd64"]) == 0
    assert store.builds == [(f"build-{kind}", "amd64")]
    retained = {
        value
        for key, value in store.refs.items()
        if key.startswith("phoenix-retained:")
    }
    assert retained == {OLD, NEW}


def test_failed_listing_prevents_the_build(store: ImageStore) -> None:
    store.fail_listing = True
    with pytest.raises(subprocess.CalledProcessError):
        build_images.main(["worker", "arm64"])
    assert not store.builds


def test_failed_build_still_retains_its_new_image(store: ImageStore) -> None:
    store.fail_build = True
    with pytest.raises(subprocess.CalledProcessError):
        build_images.main(["worker", "arm64"])
    assert set(store.refs.values()) == {OLD, NEW}


def test_a_lost_reference_stops_the_build_command(store: ImageStore) -> None:
    store.lose_old = True
    with pytest.raises(ValueError, match="lost a retained image"):
        build_images.main(["worker", "amd64"])
