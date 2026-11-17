"""Check repository rules and the R0 acceptance conditions."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

PROCESS_TERMS = ("HOLD", "fresh complete review")
REPORT_TERMS = ("equivalent", "any program", "first")
DELETED = (
    "phoenix.observe",
    "phoenix.public_checks",
    "phoenix.lift.byte_",
    "phoenix.lift.mapping",
    "phoenix.lift.index",
    "phoenix.lift.evidence",
    "phoenix.generate.checked_switch",
    "phoenix.generate.protected_switch",
    "phoenix.generate.switch_binding",
    "phoenix.generate.switch_plan",
    "phoenix.generate.switch_source",
    "phoenix.recover.addresses",
    "phoenix.recover.imports",
    "phoenix.recover.plan",
    "phoenix.recover.switches",
    "phoenix.recover.transfers",
    "phoenix_eval.project_profile",
    "phoenix_eval.m1",
    "phoenix_eval.m2",
    "phoenix_eval.capture_binding",
    "ExportMapping",
    "ExportSwitchGraphs",
    "OrdinaryByteEvidence",
    "OrdinarySwitchEvidence",
    "scripts/check-m2-public",
    "tests.test_checked_switch_emission",
    "tests.test_ordinary_switch_evidence",
    "tests.test_protected_switch",
    "tests.test_recovery_switches",
    "tests.test_recovery_u1",
    "tests.test_switch_artifacts",
    "tests.test_switch_binding",
    "tests.test_switch_pipeline",
    "tests.test_switch_source",
    "tests.test_switch_source_generation",
    "tests.test_lift_evidence",
    "tests.test_m1",
    "tests.test_m2",
    "tests.test_m2_capture_binding",
    "tests.test_m2_replay_validation",
    "tests.test_capture_rejection",
    "tests.test_evaluation_freeze",
)
LIMITS = {
    "phoenix/cli.py": 80,
    "phoenix/pipeline.py": 200,
    "phoenix/llm/ledger.py": 250,
    "phoenix_eval/run.py": 400,
    "phoenix/lift/imports.py": 200,
}
EXECUTORS = {
    "__import__",
    "import_module",
    "load_module",
    "exec_module",
    "spec_from_file_location",
    "run_module",
    "run_path",
    "exec",
    "eval",
    "run",
    "Popen",
    "call",
    "check_call",
    "check_output",
    "system",
    "popen",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def obj(value: object) -> dict[str, object]:
    require(isinstance(value, dict), "Expected a JSON object.")
    return cast(dict[str, object], value)


def content(path: Path) -> bytes:
    require(path.resolve() == path, f"Use a physical file: {path}")
    return path.read_bytes()


def text(path: Path) -> str:
    return content(path).decode("utf-8")


def read(path: Path) -> dict[str, object]:
    return obj(json.loads(content(path)))


def run(root: Path, command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        env={
            key: value
            for key, value in os.environ.items()
            if not key.startswith("GIT_")
        },
    )
    require(
        result.returncode == 0,
        f"{' '.join(command)} failed:\n{result.stdout}{result.stderr}",
    )
    return result.stdout


def git(root: Path, *args: str) -> str:
    return run(root, ["git", *args]).strip()


def lines(path: Path) -> int:
    return sum(bool(line.strip()) for line in text(path).splitlines())


def source_lines(root: Path) -> int:
    return sum(
        lines(path)
        for name in ("phoenix", "phoenix_eval")
        for path in (root / name).rglob("*.py")
    )


@dataclass(frozen=True)
class Enabling:
    name: str
    paths: tuple[str, ...]
    acceptance: tuple[str, ...]
    last_commit: str | None

    def contains(self, path: str) -> bool:
        return any(
            path == scope.rstrip("/") or path.startswith(scope.rstrip("/") + "/")
            for scope in self.paths
        )


def enabling(root: Path) -> tuple[Enabling, ...]:
    path = root / "docs/plans/enabling.json"
    if not path.exists():
        return ()
    data = json.loads(content(path))
    require(
        isinstance(data, list) and len(data) <= 2,
        "At most two enabling items can be active.",
    )
    items = []
    for value in data:
        record = obj(value)
        require(
            set(record) == {"name", "paths", "acceptance", "last_acceptance_commit"},
            "Invalid enabling item fields.",
        )
        name, scopes, command, commit = (
            record[key]
            for key in ("name", "paths", "acceptance", "last_acceptance_commit")
        )
        require(isinstance(name, str) and bool(name), "An enabling item needs a name.")
        require(
            isinstance(scopes, list) and bool(scopes), "An enabling item needs paths."
        )
        for scope in cast(list[object], scopes):
            require(
                isinstance(scope, str)
                and bool(scope)
                and not Path(scope).is_absolute()
                and ".." not in Path(scope).parts
                and not any(c in scope for c in "*?["),
                "Use relative enabling paths.",
            )
        if isinstance(command, str):
            command = shlex.split(command)
        require(
            isinstance(command, list)
            and bool(command)
            and all(isinstance(x, str) and x for x in command),
            "Use an acceptance command with arguments.",
        )
        require(
            commit is None
            or isinstance(commit, str)
            and bool(re.fullmatch(r"[0-9a-f]{40}", commit)),
            "Use a full acceptance commit or null.",
        )
        items.append(
            Enabling(
                cast(str, name),
                tuple(cast(list[str], scopes)),
                tuple(cast(list[str], command)),
                cast(str | None, commit),
            )
        )
    require(
        len({item.name for item in items}) == len(items),
        "Enabling item names must be distinct.",
    )
    return tuple(items)


def rows(root: Path) -> list[list[str]]:
    path = root / "docs/SCOREBOARD.md"
    if not path.exists():
        return []
    result = []
    for line in text(path).splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[0].isdigit():
            require(
                line.startswith("|") and len(cells) == 23, "Invalid scoreboard row."
            )
            result.append(cells)
    return result


def distance(root: Path, revision: str, staged: bool) -> int:
    require(
        bool(re.fullmatch(r"[0-9a-f]{7,40}", revision)), "Invalid measurement commit."
    )
    commit = git(root, "rev-parse", "--verify", f"{revision}^{{commit}}")
    git(root, "merge-base", "--is-ancestor", commit, "HEAD")
    return int(git(root, "rev-list", "--count", f"{commit}..HEAD")) + int(staged)


def stale(root: Path) -> None:
    items = enabling(root)
    staged_files = git(
        root, "diff", "--cached", "--name-only", "--no-renames", "-z"
    ).split("\0")
    staged_files = [name for name in staged_files if name]
    staged = bool(staged_files)
    changed = (
        staged_files
        if staged
        else git(
            root,
            "diff-tree",
            "--root",
            "--no-commit-id",
            "--name-only",
            "--no-renames",
            "-r",
            "-z",
            "HEAD",
        ).split("\0")
    )
    changed = [name for name in changed if name]
    if staged_files:
        require(
            not git(root, "diff", "--name-only", "--", *staged_files),
            "Staged files must match their working files during checks.",
        )
    if not any(name.startswith("phoenix/") for name in changed):
        return
    candidates = [row[2] for row in rows(root) if row[5] in ("full", "quick")]
    commits = candidates[-1:]
    for item in items:
        if item.last_commit and all(item.contains(name) for name in changed):
            commits.append(item.last_commit)
    require(
        bool(commits), "A pipeline change needs a loop row or an enabling acceptance."
    )
    require(
        min(distance(root, commit, staged) for commit in commits) <= 10,
        "The measurement is more than 10 commits old.",
    )


def code_size(root: Path) -> None:
    require(
        source_lines(root) < 15000, "Source must have fewer than 15000 nonblank lines."
    )
    for name, limit in LIMITS.items():
        path = root / name
        require(
            not path.exists() or lines(path) <= limit,
            f"{name} exceeds {limit} nonblank lines.",
        )


def status_length(root: Path) -> None:
    require(
        len(text(root / "docs/STATUS.md").splitlines()) <= 60,
        "STATUS.md exceeds 60 lines.",
    )


def banned_terms(root: Path) -> None:
    for path in [root / "README.md", *(root / "docs").rglob("*")]:
        if path.is_file():
            data = text(path)
            for term in PROCESS_TERMS:
                require(
                    re.search(r"\b" + re.escape(term) + r"\b", data) is None,
                    f"Banned process term in {path.relative_to(root)}.",
                )
    path = root / "docs/REPORT.md"
    if path.exists():
        for term in REPORT_TERMS:
            require(
                re.search(r"\b" + re.escape(term) + r"\b", text(path), re.I) is None,
                "Banned report term in docs/REPORT.md.",
            )


def program_names(root: Path) -> None:
    forbidden = set()
    for program in (root / "corpus_dev").iterdir():
        if not program.is_dir():
            continue
        require(
            program.resolve() == program, "Use a physical corpus program directory."
        )
        require(
            (program / "src").resolve() == program / "src",
            "Use a physical corpus source directory.",
        )
        forbidden.add(program.name)
        for path in (program / "src").rglob("*"):
            if not path.is_file():
                continue
            tokens = re.findall(
                r'//[^\n]*|/\*.*?\*/|(?:u8|[uUL])?"(?:\\.|[^"\\])*"|[^\s]',
                text(path),
                re.S,
            )
            combined = ""
            for token in [*tokens, ";"]:
                if token.startswith(("//", "/*")):
                    continue
                if '"' in token and token.endswith('"'):
                    literal = token[token.index('"') :]
                    try:
                        decoded = ast.literal_eval(literal)
                    except (ValueError, SyntaxError):
                        decoded = literal[1:-1]
                    combined += str(decoded)
                else:
                    if len(combined) >= 12:
                        forbidden.add(combined)
                    combined = ""
    for path in (root / "phoenix").rglob("*"):
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix not in (".pyc", ".pyo")
        ):
            data = text(path)
            require(
                not any(term in data for term in forbidden),
                f"Corpus program text in {path.relative_to(root)}.",
            )


def bindings(tree: ast.AST) -> tuple[dict[str, str], dict[str, str]]:
    values: dict[str, str] = {}
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in EXECUTORS:
                    aliases[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    values[target.id] = constant(node.value, values)
                    name = call_name(node.value, aliases)
                    if name in EXECUTORS:
                        aliases[target.id] = name
    return values, aliases


def call_name(node: ast.AST, aliases: dict[str, str]) -> str:
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    return node.attr if isinstance(node, ast.Attribute) else ""


def imports(path: Path, tree: ast.AST, root: Path) -> list[str]:
    result: list[str] = []
    package = list(path.relative_to(root).parts[:-1])
    values, aliases = bindings(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                base = ".".join(
                    [
                        *package[: len(package) - node.level + 1],
                        *([base] if base else []),
                    ]
                )
            result.extend([base, *(f"{base}.{alias.name}" for alias in node.names)])
        elif (
            isinstance(node, ast.Call)
            and node.args
            and call_name(node.func, aliases)
            in ("__import__", "import_module", "run_module")
        ):
            name = constant(node.args[0], values)
            if name.startswith(".") and len(node.args) > 1:
                parent = constant(node.args[1], values)
                level = len(name) - len(name.lstrip("."))
                name = ".".join(
                    [
                        *parent.split(".")[: len(parent.split(".")) - level + 1],
                        name.lstrip("."),
                    ]
                )
            result.append(name)
    return result


def import_direction(root: Path) -> None:
    for directory, forbidden in (("phoenix_eval", "phoenix"), ("phoenix", "tools")):
        for path in (root / directory).rglob("*.py"):
            for name in imports(path, ast.parse(text(path)), root):
                require(
                    name != forbidden and not name.startswith(forbidden + "."),
                    f"Invalid import direction in {path.relative_to(root)}: {name}",
                )


def deleted_match(text: str) -> bool:
    normalized = text.replace("/", ".").replace("\\", ".")
    return any(
        re.search(
            r"(?<![\w])"
            + re.escape(name.replace("/", "."))
            + (r"\w*" if name.endswith("_") else r"(?![\w])"),
            normalized,
        )
        for name in DELETED
    )


def constant(node: ast.AST, values: dict[str, str]) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return values.get(node.id, "")
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return constant(node.left, values) + constant(node.right, values)
    if isinstance(node, ast.JoinedStr):
        return "".join(
            constant(
                item.value if isinstance(item, ast.FormattedValue) else item, values
            )
            for item in node.values
        )
    return ""


def deleted_modules(root: Path) -> None:
    for directory in ("phoenix", "phoenix_eval", "scripts", "tests"):
        for path in (root / directory).rglob("*"):
            if (
                not path.is_file()
                or "__pycache__" in path.parts
                or path.suffix in (".pyc", ".pyo")
            ):
                continue
            data = text(path)
            if path.suffix != ".py":
                require(
                    not deleted_match(data),
                    f"Deleted executable reference: {path.relative_to(root)}",
                )
                continue
            tree = ast.parse(data)
            require(
                not any(deleted_match(name) for name in imports(path, tree, root)),
                f"Deleted import in {path.relative_to(root)}.",
            )
            values, aliases = bindings(tree)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    name = call_name(node.func, aliases)
                    if name in EXECUTORS:
                        require(
                            not any(
                                deleted_match(constant(item, values))
                                for arg in node.args
                                for item in ast.walk(arg)
                            ),
                            f"Deleted executable reference: {path.relative_to(root)}",
                        )
            if directory != "tests":
                for node in tree.body:
                    if (
                        path == root / "scripts/check_gates.py"
                        and isinstance(node, ast.Assign)
                        and any(
                            isinstance(target, ast.Name) and target.id == "DELETED"
                            for target in node.targets
                        )
                    ):
                        continue
                    require(
                        not any(
                            deleted_match(constant(item, values))
                            for item in ast.walk(node)
                        ),
                        f"Deleted module reference in {path.relative_to(root)}.",
                    )


MECHANICAL = (
    ("stale row and enabling items", stale),
    ("code size", code_size),
    ("status length", status_length),
    ("banned terms", banned_terms),
    ("program names", program_names),
    ("import direction", import_direction),
    ("deleted modules", deleted_modules),
)


def check(label: str, action: Callable[[], str | None]) -> bool:
    try:
        detail = action()
        print(f"[pass] {detail or label}")
        return True
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        SyntaxError,
        ImportError,
        AttributeError,
        IndexError,
        subprocess.SubprocessError,
    ) as error:
        print(f"[fail] {label}: {error}")
        return False


def mechanical(root: Path) -> bool:
    results = []
    for label, action in MECHANICAL:
        results.append(check(label, lambda: action(root)))
    return all(results)


def accept_enabling(root: Path, name: str) -> None:
    items = enabling(root)
    item = next((item for item in items if item.name == name), None)
    require(item is not None, "Unknown enabling item.")
    assert item is not None
    paths = list(item.paths)
    require(
        not git(root, "status", "--porcelain", "--untracked-files=all", "--", *paths),
        "Commit the enabling item before acceptance.",
    )
    commit = git(root, "rev-parse", "HEAD")
    run(root, list(item.acceptance))
    require(
        git(root, "rev-parse", "HEAD") == commit
        and not git(
            root, "status", "--porcelain", "--untracked-files=all", "--", *paths
        ),
        "The enabling source changed during acceptance.",
    )
    path = root / "docs/plans/enabling.json"
    records = json.loads(content(path))
    require(enabling(root) == items, "The enabling registry changed during acceptance.")
    for record in records:
        if record["name"] == name:
            record["last_acceptance_commit"] = commit
    path.write_text(json.dumps(records, indent=2) + "\n")


@dataclass
class Gate:
    root: Path
    workspace: Path

    def command(self, *command: str, root: Path | None = None) -> str:
        return run(root or self.root, list(command))

    def tests(self, *names: str, root: Path | None = None) -> None:
        self.command("uv", "run", "--locked", "pytest", "-q", *names, root=root)

    def protection(self) -> None:
        main = self.workspace / "phoenix"
        workers = [
            Path(line[9:])
            for line in git(main, "worktree", "list", "--porcelain").splitlines()
            if line.startswith("worktree ")
            and Path(line[9:]).is_relative_to(self.workspace / "worktrees")
        ]
        require(bool(workers), "A worker checkout is required for protection tests.")
        self.tests("tests/test_protection.py", root=main)
        self.tests(
            "tests/test_protection.py",
            root=self.root if self.root in workers else workers[0],
        )

    def probe(self) -> str:
        output = self.command("uv", "run", "--locked", "phoenix-eval", "probe")
        checks = [line for line in output.splitlines() if "denied=" in line]
        require(
            bool(checks) and all(line.endswith("denied=true") for line in checks),
            "The protection probe has missing or failed checks.",
        )
        return f"phoenix-eval probe: {len(checks)} checks, each denied=true"

    def main_documents(self) -> None:
        for name in (
            "AGENTS.md",
            "SPEC.md",
            "docs/ARCHITECTURE.md",
            "docs/ROADMAP.md",
            "docs/plans/R0-reset.md",
            "phoenix_eval/protection.py",
            "scripts/launch-role",
        ):
            require(
                git(self.workspace / "phoenix", "show", f"main:{name}")
                == text(self.root / name).strip(),
                f"Current {name} is not on main.",
            )

    def salvage(self) -> None:
        self.command(
            "uv",
            "run",
            "--locked",
            "python",
            "-c",
            "import phoenix.pipeline, phoenix.__main__, phoenix_eval.__main__",
        )
        deleted_modules(self.root)
        self.command("./scripts/check")

    def corpus(self) -> str:
        helper = importlib.import_module("phoenix_eval.dev_corpus")
        plan = importlib.import_module("phoenix_eval.run_plan")
        records = importlib.import_module("phoenix_eval.run_records")
        binaries = helper.read_manifest(self.workspace / "dev_bin/manifest.json")
        corpus = self.root / "corpus_dev"
        names = {path.name for path in corpus.iterdir() if path.is_dir()}
        require(
            len(names) == 22
            and len(binaries) == 176
            and {binary.name for binary in binaries} == names,
            "The corpus needs 22 programs and 176 binaries.",
        )
        tiers: list[str] = []
        for name in sorted(names):
            meta = read(corpus / name / "meta.json")
            require(
                meta.get("name") == name and meta.get("tier") in ("D0", "D1"),
                "Invalid program metadata.",
            )
            tiers.append(str(meta["tier"]))
            selected = [binary for binary in binaries if binary.name == name]
            require(
                len(selected) == 8
                and {(x.compiler, x.level) for x in selected}
                == {
                    (cc, level)
                    for cc in ("gcc", "clang")
                    for level in ("O0", "O2", "Os", "O3")
                },
                "Each program needs eight builds.",
            )
            for binary in selected:
                require(
                    binary.tier == meta["tier"],
                    "The metadata and manifest tiers differ.",
                )
                helper.load_validated_cases(corpus, self.workspace, binary)
                original = helper.binary_path(self.workspace, binary)
                twin = original.with_name(original.name + ".twin")
                require(twin.resolve() == twin and twin.is_file(), "A twin is missing.")
                elf = importlib.import_module("phoenix_eval.elf")
                require(
                    (
                        elf.elf_sections(content(original), ".text")[".text"].data
                        == elf.elf_sections(content(twin), ".text")[".text"].data
                    )
                    == binary.twin_valid,
                    "The recorded twin validity differs from its bytes.",
                )
        require(
            tiers.count("D0") == 10 and tiers.count("D1") == 12,
            "The corpus needs 10 D0 and 12 D1 programs.",
        )
        require(
            (corpus / "accepted.json").is_file(),
            "The corpus acceptance record is missing.",
        )
        plan._selection(self.workspace, records.Selection())
        self.command(
            "uv", "run", "--locked", "python", "tools/adequacy.py", "--summary"
        )
        invalid = sum(not binary.twin_valid for binary in binaries)
        return (
            f"corpus_dev 22 programs: meta, held-out validation, 8 builds, "
            f"twins ({invalid} invalid), adequacy"
        )

    def evidence(
        self, row: list[str], *, current: bool = True
    ) -> tuple[dict[str, object], dict[str, object]]:
        loop = importlib.import_module("phoenix_eval.loop")
        records = importlib.import_module("phoenix_eval.run_records")
        planning = importlib.import_module("phoenix_eval.run_plan")
        evaluation = importlib.import_module("phoenix_eval.run")
        path = records.directory(self.workspace, row[1])
        document = read(path / "scoreboard.json")
        plan = read(path / "plan.json")
        require(
            document.get("milestone") == "R0" and document.get("loop") == row[5],
            "The evidence has a different milestone or loop kind.",
        )
        require(
            document.get("run_state") in ("complete", "stopped"),
            "The evidence run state is invalid.",
        )
        require(
            loop.format_row(document).strip() == "| " + " | ".join(row) + " |",
            "The row differs from its run artifact.",
        )
        config = obj(plan["configuration"])
        if current:
            current_config = obj(planning._configuration(self.workspace))
            require(
                all(
                    config.get(key) == value
                    for key, value in current_config.items()
                    if key != "revision"
                ),
                "The evidence source or tool configuration is stale.",
            )
        revision = str(document["commit"])
        distance(self.root, revision, False)
        self.provenance(config, revision, current=current)
        if row[5] == "noise":
            children = []
            refs = obj(document["result_refs"])
            require(len(refs) == 2, "Noise needs two child runs.")
            for child, expected in refs.items():
                child_path = records.directory(self.workspace, child)
                require(
                    hashlib.sha256(content(child_path / "scoreboard.json")).hexdigest()
                    == expected,
                    "A noise child changed.",
                )
                child_doc = read(child_path / "scoreboard.json")
                child_plan = read(child_path / "plan.json")
                loop.validate_score(child_doc, child_plan, child_path)
                require(
                    child_doc["run_state"] == "complete",
                    "A noise child did not complete.",
                )
                records.verify_ledger(self.workspace, child_path)
                evaluation.publish(
                    self.workspace,
                    child_path,
                    records.RunPlan.load(child_path / "plan.json"),
                )
                self.provenance(
                    obj(child_plan["configuration"]), revision, current=False
                )
                children.append(child_doc)
            regenerated = obj(
                loop.noise_document(
                    row[1], children, obj(document["configuration_identity"])
                )
            )
            require(
                all(
                    document.get(key) == value
                    for key, value in regenerated.items()
                    if key != "result_refs"
                ),
                "The noise aggregate changed.",
            )
        else:
            loop.validate_score(document, plan, path)
            evaluation.publish(
                self.workspace, path, records.RunPlan.load(path / "plan.json")
            )
        selection = records.RunPlan.load(path / "plan.json").selection
        selected, corpus_hash, heldout_hash = planning._selection(
            self.workspace, selection
        )
        require(
            document["corpus_hash"] == corpus_hash
            and document["heldout_hash"] == heldout_hash,
            "The evidence corpus is stale.",
        )
        require(
            plan["binaries"]
            == [
                cast(dict[str, object], json.loads(json.dumps(vars(binary))))
                for binary in selected
            ],
            "The evidence selection is stale.",
        )
        return document, plan

    def provenance(
        self, config: dict[str, object], revision: str, *, current: bool
    ) -> None:
        require(
            config.get("revision") == revision,
            "The source commit differs from its evidence.",
        )
        paths = git(self.root, "ls-tree", "-r", "--name-only", revision).splitlines()
        worker = {
            ".dockerignore",
            "tools.lock",
            "scripts/build-worker",
            "containers/Dockerfile",
        }
        checker = {
            "tools.lock",
            "containers/c-integrity.cc",
            "containers/Dockerfile.integrity",
            "scripts/build-integrity",
        }
        pipeline = {"schemas/lift.schema.json", "pyproject.toml", "tools.lock"}
        for name in paths:
            path = Path(name)
            if (
                path.parent == Path("containers")
                and path.suffix in (".c", ".sh")
                or path.parent == Path("phoenix_eval")
                and path.suffix == ".py"
            ):
                worker.add(name)
            if (
                path.parts[0] in ("phoenix", "ghidra_scripts")
                and not any(
                    part.startswith(".") or part == "__pycache__" for part in path.parts
                )
                and path.suffix not in (".pyc", ".pyo", ".class")
            ):
                pipeline.add(name)
        for key, selected in (
            ("worker_source_sha256", worker),
            ("checker_source_sha256", checker),
            ("pipeline_source_sha256", pipeline),
        ):
            digest = hashlib.sha256()
            for name in sorted(selected):
                data = subprocess.run(
                    ["git", "show", f"{revision}:{name}"],
                    cwd=self.root,
                    capture_output=True,
                    check=True,
                    env={
                        key: value
                        for key, value in os.environ.items()
                        if not key.startswith("GIT_")
                    },
                ).stdout
                digest.update(name.encode())
                digest.update(b"\0")
                digest.update(hashlib.sha256(data).digest())
                if current:
                    require(
                        content(self.root / name) == data,
                        "Performance or result evidence has stale source.",
                    )
            require(
                config.get(key) == digest.hexdigest(),
                f"Source provenance mismatch: {key}",
            )
        if current:
            recorded_python = {
                name
                for name in paths
                if Path(name).parts[0] in ("phoenix", "phoenix_eval")
                and name.endswith(".py")
            }
            actual_python = {
                path.relative_to(self.root).as_posix()
                for directory in ("phoenix", "phoenix_eval")
                for path in (self.root / directory).rglob("*.py")
            }
            require(
                recorded_python == actual_python,
                "Performance or result evidence has stale source inventory.",
            )
            for name in recorded_python:
                if name.startswith("phoenix_eval/") and len(Path(name).parts) > 2:
                    require(
                        git(self.root, "show", f"{revision}:{name}")
                        == text(self.root / name).strip(),
                        "Performance or result evidence has stale source.",
                    )
            provenance = importlib.import_module("phoenix_eval.provenance")
            for key, function in (
                ("worker_source_sha256", "worker_source_digest"),
                ("checker_source_sha256", "checker_source_digest"),
                ("pipeline_source_sha256", "pipeline_source_digest"),
            ):
                require(
                    config.get(key) == getattr(provenance, function)(self.root),
                    "Performance or result evidence has stale source inventory.",
                )
            for name in ("scripts/loop",):
                require(
                    git(self.root, "show", f"{revision}:{name}")
                    == text(self.root / name).strip(),
                    "The loop command changed after measurement.",
                )

    def newest(self, kind: str) -> list[str]:
        found = [row for row in rows(self.root) if row[5] == kind and row[7] == "R0"]
        require(bool(found), f"Missing R0 {kind} row.")
        return found[-1]

    def smoke(self) -> None:
        smoke = read(self.workspace / "runs/r0-smoke.json")
        require(
            smoke.get("dev_pass_rate") == 1.0
            and smoke.get("replay_identical") is True
            and smoke.get("integrity_passed") is True,
            "The smoke summary did not pass.",
        )
        records = importlib.import_module("phoenix_eval.run_records")
        reports = []
        for key in ("run_id", "replay_id"):
            run_path = records.directory(self.workspace, smoke[key])
            projects = list(run_path.glob("*/package/out/*"))
            require(len(projects) == 1, "The smoke needs one packaged project.")
            project = projects[0]
            actual = {
                path.relative_to(project).as_posix(): hashlib.sha256(
                    content(path)
                ).hexdigest()
                for path in project.rglob("*")
                if path.is_file()
            }
            require(
                actual == smoke.get("project_files"),
                "The smoke project or replay bytes changed.",
            )
            report = read(project / "phoenix_report.json")
            require(
                report.get("development_behavior_passed") is True
                and obj(report["development_integrity"]).get("passed") is True
                and type(report.get("dev_cases")) is int
                and cast(int, report["dev_cases"]) > 0
                and report.get("dev_cases_matched_on_all_builds")
                == report["dev_cases"],
                "The smoke report did not pass all development checks.",
            )
            builds = report.get("builds")
            require(
                isinstance(builds, list)
                and len(builds) == 4
                and {
                    (obj(item)["architecture"], obj(item)["compiler"])
                    for item in builds
                }
                == {
                    (arch, cc) for arch in ("amd64", "arm64") for cc in ("gcc", "clang")
                }
                and all(
                    obj(item).get("built") is True
                    and obj(item).get("dev_cases_matched") == report["dev_cases"]
                    and obj(item).get("dev_differences") == []
                    for item in builds
                ),
                "The smoke needs four passing builds.",
            )
            config = read(project.parents[2] / "run.json")
            revision = str(config["revision"])
            distance(self.root, revision, False)
            require(
                revision.startswith(str(smoke["commit"])),
                "The smoke source commit changed.",
            )
            self.provenance(config, revision, current=False)
            reports.append(report)
        require(reports[0] == reports[1], "The smoke replay report changed.")

    def bootstrap(self) -> bool:
        def loop_check() -> None:
            self.evidence(self.newest("probe"))
            self.tests("tests/test_run.py")

        conditions: list[tuple[str, Callable[[], str | None]]] = [
            ("protection tests (main checkout and worker checkout)", self.protection),
            ("phoenix-eval probe", self.probe),
            ("instruction documents and protection on main", self.main_documents),
            ("salvage: imports, reference grep, scripts/check", self.salvage),
            ("M1 smoke run: dev pass 1.0, replay identical", self.smoke),
            (
                "corpus: 176 binaries, held-out validation, "
                "22 programs at the adequacy thresholds, accepted.json",
                lambda: self.corpus() and None,
            ),
            ("evaluation loop: probe row, tests/test_run.py", loop_check),
        ]
        passed = all([check(label, action) for label, action in conditions])
        print("R0-bootstrap: " + ("PASS" if passed else "FAIL"))
        return passed

    def r0(self) -> bool:
        def metric() -> str:
            document, _ = self.evidence(self.newest("full"))
            pair = obj(obj(document["success"])["D0"])["O0"]
            require(
                isinstance(pair, list)
                and len(pair) == 2
                and type(pair[0]) is int
                and type(pair[1]) is int
                and 0 <= pair[0] <= pair[1]
                and pair[1] > 0,
                "Invalid main metric counts.",
            )
            counts = cast(list[int], pair)
            value = counts[0] / counts[1]
            detail = f"1 main metric: success D0 O0 = {value:.3f} (gate 0.80)"
            if value < 0.8:
                experiments = [
                    row
                    for row in rows(self.root)
                    if row[5] == "full" and row[7] == "R0"
                ]
                require(
                    len(experiments) == 3 and document.get("experiment") == [3, 3],
                    detail,
                )
                for index, row in enumerate(experiments, 1):
                    measured, _ = self.evidence(row, current=False)
                    require(
                        measured.get("experiment") == [index, 3],
                        "The experiment budget evidence is invalid.",
                    )
                detail += f"; budget 3/3 used, gap {(0.8 - value) * 100:.2f} points"
            return detail

        def coverage() -> None:
            document, _ = self.evidence(self.newest("full"))
            success = obj(document["success"])
            require(
                all(
                    isinstance(obj(success[tier]).get(level), list)
                    and cast(list[int], obj(success[tier])[level])[1] > 0
                    for tier in ("D0", "D1")
                    for level in ("O0", "O2", "Os")
                ),
                "Missing required full-loop cells.",
            )

        def noise() -> None:
            document, _ = self.evidence(self.newest("noise"), current=False)
            require(
                git(self.root, "show", f"{document['commit']}:phoenix/config.py")
                == text(self.root / "phoenix/config.py").strip(),
                "Noise model or effort settings changed.",
            )
            require(
                document.get("quick_set") == 1
                and document.get("cache") == "cold"
                and document.get("run_state") == "complete"
                and bool(document.get("noise")),
                "Noise needs cold quick set 1.",
            )
            first = [
                row for row in rows(self.root) if row[5] == "full" and row[7] == "R0"
            ][0]
            require(
                str(document["commit"]).startswith(first[2]),
                "R0 noise must use the baseline commit.",
            )

        def check_time() -> str:
            start = time.monotonic()
            self.command("./scripts/check")
            minutes = (time.monotonic() - start) / 60
            require(minutes < 5, "scripts/check exceeds 5 minutes.")
            return f"4 scripts/check exit 0 in {minutes:.2f} min (limit 5)"

        def performance() -> str:
            values = []
            for quick, limit in ((False, 30), (True, 20)):
                candidates = []
                records = importlib.import_module("phoenix_eval.run_records")
                for row in rows(self.root):
                    if row[5] != "probe" or row[7] != "R0":
                        continue
                    path = records.directory(self.workspace, row[1])
                    selection = obj(read(path / "plan.json")["selection"])
                    if selection.get("quick") is quick and (
                        selection.get("tiers") == (["D0", "D1"] if quick else ["D0"])
                        and selection.get("levels")
                        == (["O0", "O2", "Os"] if quick else ["O0"])
                    ):
                        candidates.append(row)
                require(bool(candidates), "Missing performance probe evidence.")
                document, _ = self.evidence(candidates[-1])
                minutes = document.get("loop_minutes")
                require(
                    document.get("cache") == "warm"
                    and document.get("run_state") == "complete"
                    and isinstance(minutes, (int, float))
                    and not isinstance(minutes, bool)
                    and math.isfinite(minutes)
                    and 0 < minutes < limit,
                    "Warm probe performance evidence failed.",
                )
                values.append(cast(float, minutes))
            return (
                f"5 probe loop D0 O0 warm in {values[0]:.2f} min (limit 30); "
                f"probe quick loop {values[1]:.2f} min (limit 20)"
            )

        def tests() -> None:
            self.tests("tests/test_protection.py", "tests/test_integrity.py")

        def storage() -> str:
            free = shutil.disk_usage(self.workspace).free / 2**30
            status = read(self.workspace / "runs/r0-resize.json").get("status")
            require(
                free >= 15 and status in ("dry_run_ok", "ok", "blocked_on_owner"),
                "Free storage or resize evidence failed.",
            )
            return f"7 free {free:.2f} GiB (limit 15); resize record {status}"

        def size() -> str:
            count = source_lines(self.root)
            require(
                count < 9000,
                f"R0 source has {count} lines; it must have fewer than 9000.",
            )
            deleted_modules(self.root)
            return (
                f"8 source lines {count} (limit 9000); no reference to a deleted module"
            )

        conditions: list[tuple[str, Callable[[], str | None]]] = [
            ("1 main metric", metric),
            ("2 newest full-loop row covers D0 and D1 at O0, O2, Os", coverage),
            ("3 noise row for quick set 1", noise),
            ("4 scripts/check exit 0 in less than 5 min", check_time),
            ("5 warm probe loop performance", performance),
            ("6 protection and integrity tests", tests),
            ("7 free storage and resize record", storage),
            ("8 source lines and deleted modules", size),
            ("9 corpus_dev acceptance", lambda: "9 " + self.corpus()),
        ]
        passed = all([check(label, action) for label, action in conditions])
        print("R0 gate: " + ("PASS" if passed else "FAIL"))
        return passed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", choices=("R0-bootstrap", "R0"))
    parser.add_argument("--enabling")
    args = parser.parse_args(argv)
    if args.gate and args.enabling:
        parser.error("Select one gate target.")
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    try:
        if args.enabling:
            passed = check(
                f"enabling {args.enabling}",
                lambda: accept_enabling(root, args.enabling),
            )
        elif args.gate:
            gate = Gate(root, Path(os.environ["PHOENIX_ROOT"]))
            passed = gate.bootstrap() if args.gate == "R0-bootstrap" else gate.r0()
        else:
            passed = mechanical(root)
        return 0 if passed else 1
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as error:
        print(f"[fail] gate: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
