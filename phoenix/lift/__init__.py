"""Lift a binary with Ghidra headless analysis."""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory


@dataclass(frozen=True)
class LiftResult:
    export_path: Path


class LiftError(RuntimeError):
    """Ghidra did not produce a complete lift export."""


def lift_binary(
    binary: Path,
    output: Path,
    installation: Path,
    java_home: Path,
    *,
    max_heap_mib: int | None = None,
) -> LiftResult:
    """Write a lift JSON file to output and return its absolute path."""
    if max_heap_mib is not None and (
        type(max_heap_mib) is not int or not 1 <= max_heap_mib <= 512
    ):
        raise ValueError("The optional Java heap limit must be from 1 to 512 MiB.")
    binary = binary.resolve()
    output = output.resolve()
    launcher = installation.resolve() / "support" / "analyzeHeadless"
    java_home = java_home.resolve()
    script_dir = Path(__file__).resolve().parents[2] / "ghidra_scripts"
    for path in (binary, launcher, java_home / "bin" / "java"):
        if not path.is_file():
            raise FileNotFoundError(path)
    if binary == output:
        raise ValueError("The output path must differ from the binary path.")

    output.parent.mkdir(parents=True, exist_ok=True)
    with (
        TemporaryDirectory(prefix="phoenix-lift-") as directory,
        TemporaryDirectory(prefix=".phoenix-lift-", dir=output.parent) as staging,
    ):
        work = Path(directory)
        staged = Path(staging) / "lift.json"
        # Ghidra's launcher and analyzers both need workspace-local Java paths.
        java_path = str(work).replace("\\", "\\\\").replace('"', '\\"')
        (work / "java.args").write_text(
            (f"-Xmx{max_heap_mib}m\n" if max_heap_mib is not None else "")
            + f'-Duser.home="{java_path}"\n'
            f'-Djava.io.tmpdir="{java_path}"\n'
            f'-Dapplication.settingsdir="{java_path}"\n'
            f'-Dapplication.cachedir="{java_path}"\n'
            f'-Dapplication.tempdir="{java_path}"\n',
            encoding="utf-8",
        )
        env = {
            **os.environ,
            "JAVA_HOME": str(java_home),
            "JDK_JAVA_OPTIONS": "@java.args",
            "PATH": f"{java_home / 'bin'}{os.pathsep}{os.defpath}",
            "XDG_CONFIG_HOME": str(work),
            "GHIDRA_JAVA_OPTIONS": "",
            "GHIDRA_HEADLESS_JAVA_OPTIONS": "",
            "JAVA_TOOL_OPTIONS": "",
            "_JAVA_OPTIONS": "",
        }
        if max_heap_mib is not None:
            env["GHIDRA_HEADLESS_MAXMEM"] = f"{max_heap_mib}M"
        process = subprocess.run(
            [
                str(launcher),
                str(work),
                "phoenix",
                "-import",
                str(binary),
                "-readOnly",
                "-scriptPath",
                str(script_dir),
                "-log",
                str(work / "analysis.log"),
                "-scriptlog",
                str(work / "script.log"),
                "-postScript",
                "ExportLift.java",
                str(staged),
            ],
            cwd=work,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if process.returncode != 0 or not staged.is_file():
            raise LiftError(
                f"Ghidra did not complete the lift (exit {process.returncode}).\n"
                f"{process.stdout[-12000:]}"
            )
        staged.replace(output)
    return LiftResult(export_path=output)
