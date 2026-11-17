"""Source mutations and the restricted Linux instrumentation driver."""

import hashlib
import json
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory, TemporaryFile
from typing import Any

from phoenix_eval.case import CaseFailure, FailureKind, Invocation, WorkerRuntime
from phoenix_eval.outcome import Exited, Outcome, Signaled
from phoenix_eval.tree import MAX_FILE_BYTES, populate, snapshot
from phoenix_eval.wire import decode_invocation, encode_result
from phoenix_eval.worker import LAUNCHER, NATIVE_RUNTIME, TARGET_GID, TARGET_UID

OPERATORS = {
    "arithmetic": ("+", "-", "*", "/", "%"),
    "relational": ("<", "<=", ">", ">=", "==", "!="),
    "logical": ("&&", "||"),
}
FLAGS = (
    "-std=c11",
    "-O0",
    "-Iinclude",
    "-ffp-contract=off",
    "-fno-strict-aliasing",
    "-fwrapv",
    "-fsigned-char",
    "-fstack-protector-all",
    "-Wl,-z,relro,-z,now",
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Edit:
    file: str
    start: int
    end: int
    before: str
    after: str
    operator: str
    line: int
    column: int

    @property
    def id(self) -> str:
        return digest(json.dumps(asdict(self), sort_keys=True).encode())


def locate_files(ast: dict[str, Any], main_file: str) -> None:
    """Expand Clang's omitted file names before selecting source byte ranges."""
    current = main_file

    def visit(node: dict[str, Any]) -> None:
        nonlocal current
        for location in (node.get("loc", {}), node.get("range", {}).get("begin", {})):
            if "file" in location:
                current = os.path.relpath(location["file"])
        node["_file"] = current
        for child in node.get("inner", []):
            visit(child)

    visit(ast)


def mutations(ast: dict[str, Any], file: str, source: bytes) -> tuple[Edit, ...]:
    """Use Clang byte ranges, including macro spelling and expansion locations."""
    edits: dict[str, Edit] = {}

    def span(node: dict[str, Any]) -> tuple[int, int] | None:
        ends = node.get("range", {})
        raw = (ends.get("begin", {}), ends.get("end", {}))
        for form in ("spellingLoc", "expansionLoc"):
            begin, end = (x.get(form, x) for x in raw)
            default = node.get("_file", file)
            if all(form in x for x in raw):
                default = begin.get("file", end.get("file", default))
            if any("offset" not in x for x in (begin, end)):
                continue
            if any(
                os.path.relpath(x.get("file", default)) != file for x in (begin, end)
            ):
                continue
            start, stop = begin["offset"], end["offset"] + end["tokLen"]
            if 0 <= start < stop <= len(source):
                return start, stop
        return None

    def add(bounds: tuple[int, int] | None, after: str, operator: str) -> None:
        if bounds is None:
            return
        start, end = bounds
        before = source[start:end].decode()
        if before == after:
            return
        line = source.count(b"\n", 0, start) + 1
        column = start - source.rfind(b"\n", 0, start)
        edit = Edit(file, start, end, before, after, operator, line, column)
        edits[edit.id] = edit

    def visit(node: dict[str, Any], parent: str = "", index: int = 0) -> None:
        kind = node.get("kind", "")
        children = node.get("inner", [])
        bounds = span(node)
        if bounds:
            text = source[bounds[0] : bounds[1]].decode()
            opcode = node.get("opcode", "")
            if kind in ("BinaryOperator", "CompoundAssignOperator"):
                for family, choices in OPERATORS.items():
                    base = opcode[:-1] if kind == "CompoundAssignOperator" else opcode
                    if base not in choices or len(children) != 2:
                        continue
                    left, right = span(children[0]), span(children[1])
                    if left and right:
                        gap = source[left[1] : right[0]]
                        # Comments can contain operators. Match one operator token.
                        tokens = list(
                            re.finditer(
                                rb"/\*.*?\*/|//[^\n]*|\s+|&&|\|\||[+*/%-]=|<=|>=|==|!=|[+*/%<>=!-]",
                                gap,
                                re.S,
                            )
                        )
                        sites = [m for m in tokens if m.group().decode() == opcode]
                        if len(sites) == 1:
                            m = sites[0]
                            for replacement in choices:
                                add(
                                    (left[1] + m.start(), left[1] + m.end()),
                                    replacement
                                    + ("=" if kind == "CompoundAssignOperator" else ""),
                                    family,
                                )
            negative_constant = (
                kind == "UnaryOperator"
                and opcode == "-"
                and children
                and children[0].get("kind") in ("IntegerLiteral", "CharacterLiteral")
            )
            if kind in ("IntegerLiteral", "CharacterLiteral") or negative_constant:
                add(bounds, f"({text} + 1)", "integer_increment")
                add(bounds, "0", "integer_zero")
            if kind == "UnaryOperator" and opcode in ("++", "--", "+", "-"):
                start = bounds[1] - len(opcode) if node.get("isPostfix") else bounds[0]
                if source[start : start + len(opcode)].decode() == opcode:
                    add(
                        (start, start + len(opcode)),
                        {"++": "--", "--": "++", "+": "-", "-": "+"}[opcode],
                        "arithmetic",
                    )
            if kind == "ReturnStmt" and children:
                value = span(children[0])
                add(value, "0", "return_zero")
                add(value, "1", "return_one")
            call = node
            while call.get("kind") in ("ParenExpr", "CStyleCastExpr"):
                call = next(iter(call.get("inner", [])), {})
            if call.get("kind") == "CallExpr" and (
                parent == "CompoundStmt"
                or (parent == "IfStmt" and index > 0)
                or (parent in ("CaseStmt", "DefaultStmt", "LabelStmt") and index == -1)
                or (
                    parent in ("WhileStmt", "ForStmt", "DoStmt")
                    and index == (0 if parent == "DoStmt" else -1)
                )
            ):
                add(bounds, "((void)0)", "call_delete")
            condition = None
            if kind == "IfStmt":
                condition = children[0] if children else None
            elif kind in ("WhileStmt", "ConditionalOperator"):
                condition = children[0] if children else None
            elif kind == "DoStmt":
                condition = children[-1] if children else None
            elif kind == "ForStmt" and len(children) == 5:
                condition = children[2]
            if condition and (location := span(condition)):
                add(
                    location,
                    "!(" + source[location[0] : location[1]].decode() + ")",
                    "condition_negate",
                )
        for i, child in enumerate(children):
            if (
                kind == "UnaryOperator"
                and node.get("opcode") == "-"
                and child.get("kind") in ("IntegerLiteral", "CharacterLiteral")
            ):
                continue
            visit(child, kind, -1 if i == len(children) - 1 and kind != "IfStmt" else i)

    visit(ast)
    return tuple(sorted(edits.values(), key=lambda x: x.id))


def sample(candidates: tuple[Edit, ...], seed: int) -> tuple[Edit, ...]:
    ordered = sorted(candidates, key=lambda x: x.id)
    return tuple(random.Random(seed).sample(ordered, min(300, len(ordered))))


def apply(files: dict[str, bytes], edit: Edit) -> dict[str, bytes]:
    source = files[edit.file]
    if source[edit.start : edit.end] != edit.before.encode():
        raise ValueError("The edit does not match the source bytes.")
    return {
        **files,
        edit.file: source[: edit.start] + edit.after.encode() + source[edit.end :],
    }


def branches(texts: list[str]) -> dict[str, int]:
    counts = [
        int(m[1] or 0)
        for text in texts
        for m in re.finditer(
            r"^branch\s+\d+\s+(?:taken\s+(\d+)|never executed)(?:\s+\([^)]*\))*\s*$",
            text,
            re.M,
        )
    ]
    return {"covered": sum(x > 0 for x in counts), "total": len(counts)}


def classify(original: Outcome, result: Outcome | CaseFailure) -> str:
    if isinstance(result, CaseFailure):
        return "timed_out" if result.kind is FailureKind.TIMEOUT else "unresolved"
    return "survived" if original == result else "killed"


def compiler_state(returncode: int, diagnostics: str) -> str:
    if type(returncode) is not int or not isinstance(diagnostics, str):
        raise ValueError("The compiler result has invalid fields.")
    if returncode == 0:
        return "survived"
    infrastructure = (
        "internal compiler error",
        "Killed signal terminated program",
        "No space left on device",
        "Cannot allocate memory",
        "LLVM ERROR",
        "Segmentation fault",
        "error trying to exec",
    )
    if returncode < 0 or any(message in diagnostics for message in infrastructure):
        return "unresolved"
    return "uncompilable"


def execute(
    binary: bytes, case: Invocation, seconds: float, coverage: Path | None = None
) -> dict[str, Any]:
    """Run only in Linux. Keep the target inside the existing launcher sandbox."""
    if sys.platform != "linux" or not Path(LAUNCHER).is_file():
        raise RuntimeError("Target execution requires the Linux worker container.")
    started = 0
    with TemporaryDirectory(dir="/scratch") as name:
        root = Path(name)
        root.chmod(0o755)
        shutil.copytree(NATIVE_RUNTIME, root, dirs_exist_ok=True, symlinks=True)
        (root / "program").write_bytes(binary)
        (root / "program").chmod(0o555)
        populate(root / "work", case.tree, TARGET_UID, TARGET_GID)
        env = case.environment()
        if coverage is not None:
            shutil.copytree(coverage, root / "coverage")
            os.chown(root / "coverage", TARGET_UID, TARGET_GID)
            (root / "coverage").chmod(0o700)
            for path in (root / "coverage").iterdir():
                os.chown(path, TARGET_UID, TARGET_GID)
            env.update(GCOV_PREFIX="/coverage", GCOV_PREFIX_STRIP="2")
        with (
            TemporaryFile(dir="/scratch") as setup,
            TemporaryFile(dir="/scratch") as stdin,
            TemporaryFile(dir="/scratch") as stdout,
            TemporaryFile(dir="/scratch") as stderr,
        ):
            stdin.write(case.stdin)
            stdin.seek(0)
            try:
                started = time.monotonic_ns()
                with subprocess.Popen(
                    (
                        LAUNCHER,
                        WorkerRuntime.ROSETTA,
                        str(setup.fileno()),
                        str(TARGET_UID),
                        str(TARGET_GID),
                        str(root),
                        "/program",
                        *case.args,
                    ),
                    stdin=stdin,
                    stdout=stdout,
                    stderr=stderr,
                    env=env,
                    pass_fds=(setup.fileno(),),
                    start_new_session=True,
                ) as process:
                    try:
                        status = process.wait(timeout=seconds)
                    except subprocess.TimeoutExpired:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        process.wait()
                        raise
                elapsed = time.monotonic_ns() - started
                setup.seek(0)
                if diagnostic := setup.read(4096):
                    raise OSError(diagnostic.decode(errors="replace"))
                stdout.seek(0)
                stderr.seek(0)
                out, err = (
                    stdout.read(MAX_FILE_BYTES + 1),
                    stderr.read(MAX_FILE_BYTES + 1),
                )
                if max(len(out), len(err)) > MAX_FILE_BYTES or status in (
                    -signal.SIGXCPU,
                    -signal.SIGXFSZ,
                    -signal.SIGKILL,
                ):
                    result: Outcome | CaseFailure = CaseFailure(
                        FailureKind.LIMIT, "The output exceeds the byte limit."
                    )
                else:
                    result = Outcome(
                        out,
                        err,
                        Exited(status) if status >= 0 else Signaled(-status),
                        snapshot(root / "work"),
                    )
                if coverage is not None:
                    for path in (root / "coverage").glob("*.gcda"):
                        shutil.copyfile(path, coverage / path.name)
            except subprocess.TimeoutExpired:
                elapsed = time.monotonic_ns() - started
                result = CaseFailure(
                    FailureKind.TIMEOUT, "The case exceeded its limit."
                )
            except (OSError, ValueError) as exc:
                elapsed = time.monotonic_ns() - started
                result = CaseFailure(FailureKind.LAUNCH, str(exc))
    return {"result": json.loads(encode_result(result)), "runtime_ns": elapsed}


def driver(request: dict[str, Any]) -> dict[str, Any]:
    """Compile, instrument, and execute true source in one disposable container."""
    if sys.platform != "linux" or not Path(LAUNCHER).is_file():
        raise RuntimeError(
            "Source instrumentation requires the Linux worker container."
        )
    from base64 import b64decode

    from phoenix_eval.wire import decode_result

    build = Path("/scratch/build")
    build.mkdir()
    os.chdir(build)
    files = {name: b64decode(data) for name, data in request["files"].items()}
    cases = tuple(decode_invocation(json.dumps(x)) for x in request["cases"])
    sources = sorted(name for name in files if re.fullmatch(r"src/[^/]+\.c", name))

    def write(selected: dict[str, bytes]) -> None:
        for name, data in selected.items():
            path = Path(name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Source paths must stay inside the build directory.")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def command(args: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(args, capture_output=True, text=True, timeout=120)

    def compile_program(coverage: bool = False) -> subprocess.CompletedProcess[str]:
        return command(
            (
                "gcc",
                *FLAGS,
                *(("--coverage",) if coverage else ()),
                *sources,
                "-lm",
                "-o",
                "program",
            )
        )

    write(files)
    tools: dict[str, Any] = {
        name: command((name, "--version")).stdout for name in ("clang", "gcc", "gcov")
    }
    tools["executable_sha256"] = {
        name: digest(Path(shutil.which(name) or name).read_bytes())
        for name in ("clang", "gcc", "gcov", LAUNCHER)
    }
    mull = command(
        (
            "/bin/sh",
            "-c",
            "mull=$(command -v mull-runner-18 || command -v mull-runner || "
            'command -v mull); if [ -n "$mull" ]; then "$mull" --version; '
            "else echo 'mull-runner-18, mull-runner and mull are absent' >&2; "
            "exit 127; fi",
        )
    )
    tools["mull_attempt"] = {
        "returncode": mull.returncode,
        "stdout": mull.stdout,
        "stderr": mull.stderr,
    }
    if mull.returncode == 0:
        raise RuntimeError("Mull is available. Configure its pinned operator adapter.")
    if "18.1.3" not in tools["clang"]:
        raise RuntimeError("The Clang version differs from tools.lock.")
    asts = {}
    candidates: dict[str, Edit] = {}
    for file in sources:
        ast = command(
            ("clang", *FLAGS, "-Xclang", "-ast-dump=json", "-fsyntax-only", file)
        )
        if ast.returncode:
            raise ValueError(ast.stderr)
        asts[file] = json.loads(ast.stdout)
        locate_files(asts[file], file)
        for name, data in files.items():
            for edit in mutations(asts[file], name, data):
                candidates[edit.id] = edit
    selected = sample(tuple(candidates.values()), request["seed"])
    baseline_build = compile_program()
    if baseline_build.returncode:
        raise ValueError(baseline_build.stderr)
    baseline = [execute(Path("program").read_bytes(), case, 15) for case in cases]
    originals = [decode_result(json.dumps(x["result"])) for x in baseline]
    if not originals or any(not isinstance(x, Outcome) for x in originals):
        raise ValueError("The original failed. Adequacy cannot use these cases.")
    instrumentation = compile_program(True)
    if instrumentation.returncode:
        raise ValueError(instrumentation.stderr)
    coverage_dir = Path("/scratch/coverage")
    coverage_dir.mkdir()
    coverage_runs = [
        execute(Path("program").read_bytes(), case, 15, coverage_dir) for case in cases
    ]
    if any(
        x["result"] != original["result"]
        for x, original in zip(coverage_runs, baseline, strict=True)
    ):
        raise ValueError("An instrumented case differs from the original.")
    # GCC writes absolute gcda paths. GCOV_PREFIX_STRIP removes /scratch/build.
    for path in coverage_dir.glob("*.gcda"):
        shutil.copyfile(path, build / path.name)
    gcov = command(("gcov", "-b", "-c", "-p", *map(str, sorted(build.glob("*.gcno")))))
    if gcov.returncode:
        raise ValueError(gcov.stderr)
    gcov_files = {path.name: path.read_text() for path in build.glob("*.gcov")}
    if not gcov_files:
        raise ValueError("gcov produced no source records.")
    results = []
    for edit in selected:
        write(apply(files, edit))
        built = compile_program()
        row: dict[str, Any] = {
            "id": edit.id,
            "cases": [],
            "status": compiler_state(built.returncode, built.stderr),
            "compiler_stderr": built.stderr,
            "compiler_returncode": built.returncode,
        }
        if not built.returncode:
            binary = Path("program").read_bytes()
            for index, (case, original) in enumerate(
                zip(cases, originals, strict=True)
            ):
                assert isinstance(original, Outcome)
                limit_ns = baseline[index]["runtime_ns"] * 10
                observation = execute(binary, case, limit_ns / 1e9)
                observation["limit_ns"] = limit_ns
                observation["case"] = index
                row["cases"].append(observation)
                state = classify(
                    original, decode_result(json.dumps(observation["result"]))
                )
                if state in ("killed", "timed_out"):
                    row["status"] = state
                    break
                if state == "unresolved":
                    row["status"] = state
        results.append(row)
        write(files)
    return {
        "tools": tools,
        "mutator": "clang-ast-source-v1",
        "asts": asts,
        "candidates": [
            {"id": x.id, **asdict(x)}
            for x in sorted(candidates.values(), key=lambda x: x.id)
        ],
        "selected": [x.id for x in selected],
        "baseline": baseline,
        "coverage_runs": coverage_runs,
        "gcov": gcov_files,
        "gcov_stdout": gcov.stdout,
        "gcov_stderr": gcov.stderr,
        "branches": branches(list(gcov_files.values())),
        "results": results,
    }


if __name__ == "__main__":
    print(json.dumps(driver(json.load(sys.stdin))))
