import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from phoenix_eval.case import CaseFailure, FailureKind, Invocation
from phoenix_eval.outcome import (
    EntryKind,
    Exited,
    Outcome,
    Signaled,
    TreeEntry,
    TreeSnapshot,
)
from phoenix_eval.wire import (
    decode_invocation,
    decode_result,
    encode_invocation,
    encode_result,
)

arguments = st.text(alphabet=st.characters(exclude_characters="\0"))
binary_trees = st.builds(
    TreeSnapshot,
    root_mode=st.integers(0, 0o7777),
    entries=st.tuples(
        st.builds(
            TreeEntry,
            path=st.sampled_from(["file", "\udc80", "file with spaces"]),
            kind=st.just(EntryKind.FILE),
            mode=st.integers(0, 0o7777),
            data=st.binary(),
        )
    ),
)


@given(st.lists(arguments).map(tuple), st.binary(), binary_trees, arguments)
def test_invocation_round_trip(
    args: tuple[str, ...], stdin: bytes, tree: TreeSnapshot, env: str
) -> None:
    invocation = Invocation(args, stdin, tree, (("PHOENIX_TEST", env),))
    assert decode_invocation(encode_invocation(invocation)) == invocation
    assert invocation.environment()["PHOENIX_TEST"] == env
    assert invocation.environment()["HOME"] == "/nonexistent"


@given(
    st.binary(),
    st.binary(),
    st.one_of(
        st.builds(Exited, st.integers(0, 255)), st.builds(Signaled, st.integers(1, 64))
    ),
    binary_trees,
)
def test_result_round_trip(
    stdout: bytes, stderr: bytes, termination: Exited | Signaled, tree: TreeSnapshot
) -> None:
    outcome = Outcome(stdout, stderr, termination, tree)
    assert decode_result(encode_result(outcome)) == outcome


def test_failure_is_separate_from_program_exit() -> None:
    failure = CaseFailure(FailureKind.LAUNCH, "Exec failed.")
    assert decode_result(encode_result(failure)) == failure


@pytest.mark.parametrize(
    "name", ["HOME", "LANG", "TZ", "LD_PRELOAD", "QEMU_LD_PREFIX", "", "a=b", "a\0b"]
)
def test_overlay_rejects_runtime_controls_and_invalid_names(name: str) -> None:
    with pytest.raises(ValueError, match="environment entry"):
        Invocation(overlay=((name, "value"),))


def test_args_reject_nul() -> None:
    with pytest.raises(ValueError, match="NUL"):
        Invocation(args=("foo\0bar",))


@pytest.mark.parametrize("exit_code, signal", [(None, None), (1, 1), (True, None)])
def test_invalid_termination_cannot_be_decoded(
    exit_code: object, signal: object
) -> None:
    with pytest.raises(ValueError):
        decode_result(
            json.dumps(
                {"exit": exit_code, "signal": signal, "stdout": "", "stderr": ""}
            )
        )
