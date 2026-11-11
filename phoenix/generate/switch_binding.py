from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

from phoenix.generate.switch_source import (
    FlatSwitch,
    Span,
    SwitchLimitError,
    SwitchSourceError,
    parse_flat_switch,
)
from phoenix.lift.mapping import GhidraVA
from phoenix.lift.switch_source import (
    OrdinarySourceObservation,
    SourceMarkerObservation,
)


class MarkerCorrespondenceError(SwitchSourceError):
    pass


@dataclass(frozen=True, slots=True)
class BoundSwitchSource:
    observation: OrdinarySourceObservation
    parsed: FlatSwitch
    source: bytes


def _at(
    marker: SourceMarkerObservation, span: Span, kind: str, value: int | None = None
) -> None:
    if (marker.kind, marker.start, marker.end, marker.value) != (
        kind,
        span.start,
        span.end,
        value,
    ):
        raise MarkerCorrespondenceError(
            "An ordinary marker conflicts with its parsed C role."
        )


def bind_switch_source(body: OrdinarySourceObservation) -> BoundSwitchSource:
    source = body.source
    if (
        len(source) != body.source_bytes
        or sha256(source).hexdigest() != body.source_sha256
    ):
        raise MarkerCorrespondenceError(
            "The ordinary source identity changed before binding."
        )
    parsed = parse_flat_switch(source)
    labels = [label for arm in parsed.arms for label in arm.labels]
    if len(body.markers) != len(labels) + 3:
        raise MarkerCorrespondenceError("The ordinary switch marker roster differs.")
    switch, parameter, *tail = body.markers
    *markers, finish = tail
    _at(switch, parsed.switch, "switch")
    _at(parameter, parsed.parameter_reference, "parameter")
    for marker, label in zip(markers, labels, strict=True):
        _at(
            marker,
            label.marker,
            "default" if label.value is None else "case",
            label.value,
        )
    _at(finish, parsed.return_keyword, "return")
    return BoundSwitchSource(body, parsed, source)


@dataclass(frozen=True, slots=True)
class SourceGap:
    function: GhidraVA
    reason: Literal["syntax_unsupported", "limit_exceeded"]
    detail: str


@dataclass(frozen=True, slots=True)
class SourceConflict:
    function: GhidraVA
    reason: Literal["marker_correspondence"]
    detail: str


type SourceAdmission = BoundSwitchSource | SourceGap | SourceConflict


def admit_switch_source(body: OrdinarySourceObservation) -> SourceAdmission:
    try:
        return bind_switch_source(body)
    except MarkerCorrespondenceError as error:
        return SourceConflict(body.function, "marker_correspondence", str(error))
    except SwitchLimitError as error:
        return SourceGap(body.function, "limit_exceeded", str(error))
    except SwitchSourceError as error:
        return SourceGap(body.function, "syntax_unsupported", str(error))
