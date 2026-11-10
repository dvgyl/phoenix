import ctypes
import errno
from pathlib import Path
from unittest.mock import Mock

import pytest

from phoenix_eval import isolation


def test_process_filter_can_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    library = Mock()
    library.seccomp_init.return_value = 1
    library.seccomp_syscall_resolve_name.return_value = 2
    library.seccomp_rule_add_array.return_value = 0
    library.seccomp_load.return_value = -errno.EPERM
    monkeypatch.setattr(ctypes, "CDLL", lambda _: library)

    policy = isolation.ProcessFilter()
    with pytest.raises(OSError, match="Cannot load"):
        policy.apply()
    library.seccomp_release.assert_called_once_with(1)


def test_enter_applies_the_filter_after_dropping_privileges(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    operating_system = Mock()
    process_filter = Mock()
    policy = Mock()
    monkeypatch.setattr(isolation, "os", operating_system)
    monkeypatch.setattr(isolation, "resource", policy)
    isolation.enter(tmp_path, process_filter)
    operating_system.chroot.assert_called_once_with(tmp_path)
    operating_system.chdir.assert_called_once_with("/work")
    operating_system.setuid.assert_called_once_with(isolation.TARGET_UID)
    policy.setrlimit.assert_any_call(policy.RLIMIT_AS, (1024**3, 1024**3))
    process_filter.apply.assert_called_once()
