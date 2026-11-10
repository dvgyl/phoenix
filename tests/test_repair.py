from phoenix.repair import _output_differences
from phoenix_eval.outcome import Exited, Outcome, TreeSnapshot


def test_feedback_exposes_difference_positions_and_lengths() -> None:
    original = Outcome(b"prefix-original answer", b"", Exited(0), TreeSnapshot())
    rebuilt = Outcome(b"prefix-other", b"", Exited(0), TreeSnapshot())
    result = _output_differences(original, rebuilt)
    assert "stdout first differs at byte 8" in result
    assert "original has 22 bytes" in result
    assert "rebuild has 12 bytes" in result
    assert "original answer" not in result
