import ctypes
import errno
import os
import resource
from pathlib import Path

from phoenix_eval.tree import MAX_FILE_BYTES

TARGET_UID = 19704
TARGET_GID = 19704

_SCMP_ACT_ALLOW = 0x7FFF0000
_SCMP_ACT_ERRNO = 0x00050000
_SCMP_CMP_MASKED_EQ = 7
_CLONE_THREAD = 0x00010000


class _Comparison(ctypes.Structure):
    _fields_ = [
        ("arg", ctypes.c_uint),
        ("op", ctypes.c_int),
        ("datum_a", ctypes.c_uint64),
        ("datum_b", ctypes.c_uint64),
    ]


class ProcessFilter:
    def __init__(self) -> None:
        seccomp = ctypes.CDLL("libseccomp.so.2")
        seccomp.seccomp_init.argtypes = [ctypes.c_uint32]
        seccomp.seccomp_init.restype = ctypes.c_void_p
        seccomp.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
        seccomp.seccomp_rule_add_array.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.POINTER(_Comparison),
        ]
        seccomp.seccomp_load.argtypes = [ctypes.c_void_p]
        seccomp.seccomp_release.argtypes = [ctypes.c_void_p]
        self._seccomp = seccomp

    def apply(self) -> None:
        seccomp = self._seccomp
        context = seccomp.seccomp_init(_SCMP_ACT_ALLOW)
        if not context:
            raise OSError("Cannot initialize the target process filter.")
        try:
            for name, error in (
                (b"fork", errno.EPERM),
                (b"vfork", errno.EPERM),
                (b"clone3", errno.ENOSYS),
            ):
                syscall = seccomp.seccomp_syscall_resolve_name(name)
                status = seccomp.seccomp_rule_add_array(
                    context, _SCMP_ACT_ERRNO | error, syscall, 0, None
                )
                if status != 0:
                    raise OSError(-status, f"Cannot restrict {name.decode()}.")
            clone = seccomp.seccomp_syscall_resolve_name(b"clone")
            comparison = _Comparison(0, _SCMP_CMP_MASKED_EQ, _CLONE_THREAD, 0)
            status = seccomp.seccomp_rule_add_array(
                context,
                _SCMP_ACT_ERRNO | errno.EPERM,
                clone,
                1,
                ctypes.byref(comparison),
            )
            if status != 0:
                raise OSError(-status, "Cannot restrict clone.")
            status = seccomp.seccomp_load(context)
            if status != 0:
                raise OSError(-status, "Cannot load the target process filter.")
        finally:
            seccomp.seccomp_release(context)


def enter(root: Path, process_filter: ProcessFilter) -> None:
    os.chroot(root)
    os.chdir("/work")
    os.umask(0o022)
    os.setgroups([])
    os.setgid(TARGET_GID)
    os.setuid(TARGET_UID)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (5, 6))
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FILE_BYTES, MAX_FILE_BYTES))
    process_filter.apply()
