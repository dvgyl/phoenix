"""Define the fixed M2 scope and its numerical result."""

from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal, cast

from phoenix_eval.build import PROJECT_CMAKE
from phoenix_eval.corpus import Tier, Variant, _unique_fields, manifest_variants
from phoenix_eval.model_ledger import read_identity
from phoenix_eval.submission import Method, _seconds

METHODS: tuple[Method, ...] = ("phoenix", "ghidra-raw")
type ReportKind = Literal["m1", "m2"]


@dataclass(frozen=True, slots=True)
class Batch:
    tier: Tier
    variants: tuple[Variant, ...]
    manifest_sha256: str
    source_sha256: str
    inputs_sha256: str

    def record(self) -> dict[str, object]:
        return {
            "tier": self.tier,
            "flags": list(self.tier.flags),
            "manifest_sha256": self.manifest_sha256,
            "source_archive_sha256": self.source_sha256,
            "heldout_archive_sha256": self.inputs_sha256,
            "variants": [
                {
                    "name": v.name,
                    "tier": self.tier,
                    "compiler": v.compiler,
                    "flags": [v.flag],
                    "sha256": v.sha256,
                    "category": v.category,
                }
                for v in self.variants
            ],
        }


@dataclass(frozen=True, slots=True)
class Scope:
    batches: tuple[Batch, ...]

    def record(self) -> dict[str, object]:
        return {
            "schema": 1,
            "batches": [batch.record() for batch in self.batches],
            "methods": list(METHODS),
            "task_keys": [
                f"{batch.tier.lower()}-{variant.key}-{method}"
                for batch in self.batches
                for variant in batch.variants
                for method in METHODS
            ],
            "rebuilds": [
                {"architecture": arch, "compiler": compiler}
                for arch in ("amd64", "arm64")
                for compiler in ("gcc", "clang")
            ],
            "project_cmake": PROJECT_CMAKE,
        }

    @classmethod
    def parse(cls, value: object) -> Scope:
        try:
            if not isinstance(value, dict) or type(value.get("schema")) is not int:
                raise ValueError
            batches = []
            for data, tier in zip(value["batches"], Tier, strict=True):
                if data["tier"] != tier:
                    raise ValueError
                hashes = tuple(
                    data[key]
                    for key in (
                        "manifest_sha256",
                        "source_archive_sha256",
                        "heldout_archive_sha256",
                    )
                )
                if any(
                    not isinstance(digest, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", digest)
                    for digest in hashes
                ):
                    raise ValueError
                variants = manifest_variants(
                    json.dumps(data["variants"]).encode("utf-8"), tier
                )
                batches.append(Batch(tier, variants, *hashes))
            scope = cls(tuple(batches))
            if scope.record() != value:
                raise ValueError
            return scope
        except (KeyError, TypeError, ValueError):
            raise ValueError("The M2 scope is invalid or incomplete.") from None


def architecture_passed(record: dict[str, object], architecture: str) -> bool:
    behavior = record.get("behavior")
    if not isinstance(behavior, dict):
        return False
    eligible = behavior.get("eligible_cases")
    if (
        type(eligible) is not int
        or eligible <= 0
        or behavior.get("original_error_categories") != {}
    ):
        return False
    builds = behavior.get("builds")
    if not isinstance(builds, (list, tuple)):
        return False
    selected = [
        b
        for b in builds
        if isinstance(b, dict) and b.get("architecture") == architecture
    ]
    return (
        len(selected) == 2
        and {b["compiler"] for b in selected} == {"gcc", "clang"}
        and all(
            b["compiled"] is True
            and b["matched_cases"] == eligible
            and b["evaluation_errors"] == 0
            for b in selected
        )
    )


def summarize(records: list[dict[str, object]], scope: Scope) -> dict[str, object]:
    expected = [
        {
            **asdict(variant),
            "tier": batch.tier,
            "method": method,
            "variant_key": f"{batch.tier.lower()}-{variant.key}",
            "task_key": f"{batch.tier.lower()}-{variant.key}-{method}",
        }
        for batch in scope.batches
        for variant in batch.variants
        for method in METHODS
    ]
    if len(records) != len(expected) or any(
        not isinstance(record, dict)
        or any(record.get(key) != value for key, value in identity.items())
        or type(record.get("fully_successful")) is not bool
        for record, identity in zip(records, expected, strict=True)
    ):
        raise ValueError("The M2 result roster does not match its scope.")
    for record in records:
        source = record.get("source_sha256")
        if "source_sha256" not in record or (
            source is not None
            and (
                not isinstance(source, str) or not re.fullmatch(r"[0-9a-f]{64}", source)
            )
        ):
            raise ValueError("The M2 result has no valid source identity.")
        if record["fully_successful"] is True:
            integrity = record.get("integrity")
            behavior = record.get("behavior")
            if (
                source is None
                or not isinstance(integrity, dict)
                or integrity.get("passed") is not True
                or not isinstance(behavior, dict)
                or behavior.get("evaluation_errors") != 0
                or not all(
                    architecture_passed(record, arch) for arch in ("amd64", "arm64")
                )
            ):
                raise ValueError("The M2 success claim lacks passing evidence.")
        _seconds(record.get("reconstruction_seconds"))
        model = record.get("model")
        if not isinstance(model, dict) or set(model) != {
            "calls",
            "usage",
            "cost_nanodollars",
            "unknown_cost_reservations",
        }:
            raise ValueError("The M2 result has no model summary.")
    groups = []
    thresholds = {
        ("T0", "-O0"): 16,
        ("T0", "-O2"): 16,
        ("T1", "-O0"): 18,
        ("T1", "-O2"): 12,
    }
    numerical = True
    portability = True
    arm_only: list[str] = []
    for tier in Tier:
        for flag in tier.flags:
            for method in METHODS:
                selected = [
                    r
                    for r in records
                    if (r["tier"], r["flag"], r["method"]) == (tier, flag, method)
                ]
                count = tier.programs * 2
                if len(selected) != count:
                    raise ValueError("The M2 results omit a required variant.")
                success = sum(r["fully_successful"] is True for r in selected)
                architectures = {}
                passed_keys = {}
                for arch in ("amd64", "arm64"):
                    keys = {
                        str(r["variant_key"])
                        for r in selected
                        if architecture_passed(r, arch)
                    }
                    passed_keys[arch] = keys
                    architectures[arch] = {
                        "behavior_successful": len(keys),
                        "variants": count,
                        "behavior_success_rate": len(keys) / count,
                    }
                group: dict[str, object] = {
                    "tier": tier,
                    "flag": flag,
                    "method": method,
                    "fully_successful": success,
                    "variants": count,
                    "architectures": architectures,
                }
                if method == "phoenix":
                    threshold = thresholds.get((tier, flag))
                    group["required_fully_successful"] = threshold
                    if threshold is not None:
                        numerical &= success >= threshold
                    within = (
                        abs(len(passed_keys["amd64"]) - len(passed_keys["arm64"])) * 100
                        <= 5 * count
                    )
                    only = sorted(passed_keys["amd64"] - passed_keys["arm64"])
                    group["within_five_percentage_points"] = within
                    group["arm_only_failure_categories"] = {
                        key: "arm_only_behavior_failure" for key in only
                    }
                    portability &= within
                    arm_only.extend(only)
                groups.append(group)
    return {
        "groups": groups,
        "numerical_thresholds_met": numerical,
        "portability_bound_met": portability,
        "arm_only_failure_categories": {
            key: "arm_only_behavior_failure" for key in sorted(arm_only)
        },
        "root_cause_gate": "required" if arm_only else "no_arm_only_failures",
        "accepted": numerical and portability and not arm_only,
    }


def _fields(value: object, names: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != set(names.split()):
        raise ValueError
    return value


def _count(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError
    return value


def _digest(value: object) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError


def _categories(value: object) -> dict[str, int]:
    if not isinstance(value, dict) or any(
        not isinstance(key, str)
        or not re.fullmatch(r"[a-z_]+", key)
        or _count(count) == 0
        for key, count in value.items()
    ):
        raise ValueError
    return value


def _validate_model(value: object) -> None:
    model = _fields(value, "calls usage cost_nanodollars unknown_cost_reservations")
    calls, cost, _ = (
        _count(model[key])
        for key in ("calls", "cost_nanodollars", "unknown_cost_reservations")
    )
    usage = _fields(model["usage"], "input_tokens cached_input_tokens output_tokens")
    inputs, cached, outputs = (
        _count(usage[key])
        for key in ("input_tokens", "cached_input_tokens", "output_tokens")
    )
    if (
        cached > inputs
        or (calls == 0 and (inputs or outputs))
        or bool(cost) != bool(inputs or outputs)
    ):
        raise ValueError


def _validate_behavior(value: object) -> tuple[bool, int]:
    behavior = _fields(
        value,
        "total_cases eligible_cases emulator_disagreements evaluation_errors "
        "original_error_categories recovered_blocks covered_blocks builds "
        "behavior_passed",
    )
    total, eligible, disagreements, errors, recovered, covered = (
        _count(behavior[key])
        for key in (
            "total_cases",
            "eligible_cases",
            "emulator_disagreements",
            "evaluation_errors",
            "recovered_blocks",
            "covered_blocks",
        )
    )
    original_errors = _categories(behavior["original_error_categories"])
    if (
        total != eligible + disagreements + sum(original_errors.values())
        or covered > recovered
        or (eligible == 0 and covered != 0)
        or (eligible > 0 and covered == 0)
    ):
        raise ValueError
    builds = behavior["builds"]
    if not isinstance(builds, list) or len(builds) != 4:
        raise ValueError
    configurations = set()
    tested = 0
    build_errors = 0
    passed = eligible > 0
    for value in builds:
        build = _fields(
            value,
            "architecture compiler compiled warnings matched_cases evaluation_errors "
            "failure_categories executable_sha256",
        )
        arch, compiler = build["architecture"], build["compiler"]
        if arch not in ("amd64", "arm64") or compiler not in ("gcc", "clang"):
            raise ValueError
        configurations.add((arch, compiler))
        compiled = build["compiled"]
        if type(compiled) is not bool:
            raise ValueError
        _count(build["warnings"])
        matched, failed = (
            _count(build["matched_cases"]),
            _count(build["evaluation_errors"]),
        )
        categories = _categories(build["failure_categories"])
        digest = build["executable_sha256"]
        if digest is not None:
            _digest(digest)
            tested += 1
        if not compiled:
            if (
                digest is not None
                or matched != 0
                or (
                    (failed, categories)
                    not in ((0, {"build_failed": 1}), (1, {"build_error": 1}))
                )
            ):
                raise ValueError
        elif categories == {"build_error": 1}:
            if digest is not None or matched != 0 or failed != 1:
                raise ValueError
        elif (
            (digest is not None) != (eligible > 0)
            or matched + failed > eligible
            or any(count > eligible - matched for count in categories.values())
            or sum(categories.values()) < eligible - matched
            or failed
            != sum(
                categories.get(key, 0) for key in ("worker_error", "malformed_result")
            )
            or "build_error" in categories
            or "build_failed" in categories
        ):
            raise ValueError
        build_errors += failed
        passed &= compiled and matched == eligible and not categories
    passed &= errors == 0
    if (
        len(configurations) != 4
        or errors != sum(original_errors.values()) + build_errors
        or type(behavior["behavior_passed"]) is not bool
        or behavior["behavior_passed"] != passed
    ):
        raise ValueError
    return passed, tested


def _validate_integrity(value: object, tested: int) -> bool:
    if not isinstance(value, dict) or type(value.get("passed")) is not bool:
        raise ValueError
    categories = _categories(value.get("categories"))
    if set(value) == {"passed", "categories"}:
        if value["passed"] or len(categories) != 1 or sum(categories.values()) != 1:
            raise ValueError
        return False
    integrity = _fields(
        value,
        "passed categories checked_storage_records checked_executables "
        "targets clang_versions justifications",
    )
    storage = _count(integrity["checked_storage_records"])
    if _count(integrity["checked_executables"]) != tested:
        raise ValueError
    targets, versions = integrity["targets"], integrity["clang_versions"]
    supported = {"x86_64-linux-gnu", "aarch64-linux-gnu"}
    if (
        not isinstance(targets, list)
        or any(
            not isinstance(target, str) or target not in supported for target in targets
        )
        or len(set(targets)) != len(targets)
        or not isinstance(versions, list)
        or len(versions) != len(targets)
        or any(not isinstance(version, str) or not version for version in versions)
        or value["passed"] != (not categories)
        or (not categories and (set(targets) != supported or tested != 4))
    ):
        raise ValueError
    justifications = integrity["justifications"]
    if not isinstance(justifications, list) or len(justifications) > storage:
        raise ValueError
    for item in justifications:
        blob = _fields(item, "target artifact offset sha256 size reason")
        if (
            blob["target"] not in targets
            or any(
                not isinstance(blob[key], str) or not blob[key]
                for key in ("artifact", "reason")
            )
            or _count(blob["size"]) <= 4096
        ):
            raise ValueError
        _count(blob["offset"])
        _digest(blob["sha256"])
    return value["passed"] is True


def _validate_saved_result(record: dict[str, object]) -> None:
    base = (
        "name compiler flag sha256 category tier method variant_key task_key "
        "source_sha256 fully_successful model reconstruction_seconds"
    )
    _validate_model(record.get("model"))
    _seconds(record.get("reconstruction_seconds"))
    if record.get("source_sha256") is None:
        _fields(record, base + " failure_category")
        if record["fully_successful"] or record["failure_category"] not in (
            "pipeline-failed",
            "invalid-project",
        ):
            raise ValueError
    else:
        _fields(record, base + " behavior integrity")
        _digest(record["source_sha256"])
        behavior, tested = _validate_behavior(record["behavior"])
        integrity = _validate_integrity(record["integrity"], tested)
        if record["fully_successful"] != (behavior and integrity):
            raise ValueError


@dataclass(frozen=True, slots=True)
class RecordedReport:
    kind: ReportKind
    document: dict[str, object]
    sha256: str


def _report_kind(directory: Path) -> ReportKind:
    present = [
        path.stem
        for path in directory.glob("m*.json")
        if re.fullmatch(r"m[0-9]+", path.stem)
    ]
    if len(present) != 1 or present[0] not in ("m1", "m2"):
        raise ValueError("Select one supported recorded evaluation report.")
    return cast(ReportKind, present[0])


def _report_bytes(path: Path) -> bytes:
    if os.path.realpath(path, strict=True) != str(path):
        raise ValueError
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError
    limit = 32 * 1024 * 1024
    with os.fdopen(descriptor, "rb") as stream:
        content = stream.read(limit + 1)
    if len(content) > limit:
        raise ValueError
    return content


def read_recorded_report(directory: Path) -> RecordedReport:
    kind = _report_kind(directory)
    try:
        content = _report_bytes(directory / f"{kind}.json")
        data = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_fields)
        config = data["configuration"]
        if (
            data["run_id"] != directory.name
            or type(config["schema"]) is not int
            or config["schema"] != (1 if kind == "m1" else 2)
            or not isinstance(data["results"], list)
            or any(
                not isinstance(record, dict)
                or record.get("method") not in METHODS
                or type(record.get("fully_successful")) is not bool
                for record in data["results"]
            )
            or not isinstance(data["scores"], dict)
            or type(data["accepted"]) is not bool
            or (kind == "m1" and ("scope" in config or "report_kind" in data))
            or (kind == "m2" and data.get("report_kind") != "m2")
        ):
            raise ValueError
        if kind == "m2":
            scope = Scope.parse(config["scope"])
            if (
                data["corpus"] != "agent-sealed"
                or data["coverage_kind"] != "recovered_block_entries"
                or data["source_adequacy"] != "separate_author_evidence"
                or (data["replay_of"] is None and data["reproduced"] is not None)
                or (
                    data["replay_of"] is not None
                    and (
                        not isinstance(data["replay_of"], str)
                        or not re.fullmatch(
                            r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}", data["replay_of"]
                        )
                        or type(data["reproduced"]) is not bool
                    )
                )
            ):
                raise ValueError
            for record in data["results"]:
                _validate_saved_result(record)
            if json.dumps(data["model_ledger"], sort_keys=True) != json.dumps(
                read_identity(directory / "model-ledger.json"), sort_keys=True
            ):
                raise ValueError
            if set(data) != {
                "run_id",
                "replay_of",
                "reproduced",
                "configuration",
                "corpus",
                "coverage_kind",
                "model_ledger",
                "scores",
                "results",
                "accepted",
                "report_kind",
                "source_adequacy",
            } or json.dumps(data["scores"], sort_keys=True) != json.dumps(
                summarize(data["results"], scope), sort_keys=True
            ):
                raise ValueError
            if data["accepted"] != data["scores"]["accepted"]:
                raise ValueError
        return RecordedReport(kind, data, sha256(content).hexdigest())
    except (OSError, KeyError, TypeError, ValueError, RecursionError):
        raise ValueError("The recorded evaluation report is invalid.") from None


def recorded_kind(directory: Path) -> ReportKind:
    return read_recorded_report(directory).kind


def verify_m2_report(directory: Path, expected: str) -> None:
    try:
        if (
            _report_kind(directory) != "m2"
            or sha256(_report_bytes(directory / "m2.json")).hexdigest() != expected
        ):
            raise ValueError
    except (OSError, ValueError):
        raise ValueError("An ancestor report changed after replay began.") from None
