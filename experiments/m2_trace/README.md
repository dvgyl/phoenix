# Public M2 trace calibration

This is a disposable calibration experiment. It is development-only.
It is never Phoenix-Bench. Production code does not import it. It does
not affect M1, recovery, repair, or the separate evaluator.

The decision is whether a separate QEMU 9.2.0 observer can record correct
call and stdio observations under the existing sandbox. The fixed public
calibration passed on 2026-11-10. Additional runtime controls remain open.
Keep the QEMU 8.2.2 and Rosetta oracle pair unchanged.

`PhoenixPublicTraceV1` is defined in [FORMAT.md](FORMAT.md). The plugin
uses API 4 register names and checks eight-byte widths in read-enabled
callbacks. It captures pre-call values, next-PC transfers, program return
attempts, and return values before caller continuations. It samples only
bounded guest buffers. A PLT transfer confirms entry to that stub. It does
not prove entry to a particular libc implementation. The public plan uses
objdump symbol labels and instruction bytes from the same compiled file.
It does not resolve arbitrary imports.

The fixture has two stack nodes and an eight-byte input buffer. `walk`
receives a runtime-selected increment or XOR function. Its translation
unit cannot see the caller. Builds use no LTO. The case lengths are
0, 1, 2, 7, 8, and 9 for each operation. Every nonempty case includes NUL.
Length 9 tests the input cap. The hash manifest fixes all sources and cases
before runtime experiments. Compiler optimization can still remove a
mechanism. Plan construction rejects a build without the required calls.
The parent must also inspect both compilers at O0 and O2.

Run these commands from this worktree.
Use an arm64 Docker host with the existing external-drive storage.
The commands create only the separate observer tag. They do not build,
update, or retag worker or integrity images.

```sh
source "/Volumes/Extreme Pro/Phoenix/env.sh"
trace_work="$PHOENIX_ROOT/tmp/m2-public-calibration"
mkdir -p "$trace_work/context/opt"
trace_oracle_amd64=$(docker image inspect --format '{{.Id}}' phoenix-worker:amd64)
trace_oracle_arm64=$(docker image inspect --format '{{.Id}}' phoenix-worker:arm64)
printf '%s\n' "$trace_oracle_amd64" > "$trace_work/oracle-amd64.id"
printf '%s\n' "$trace_oracle_arm64" > "$trace_work/oracle-arm64.id"
trace_context_container=$(docker create --platform linux/arm64 \
  --entrypoint /bin/true "$trace_oracle_arm64")
docker cp "$trace_context_container:/opt/launch-target" "$trace_work/context/opt/"
docker cp "$trace_context_container:/opt/phoenix-qemu-root" "$trace_work/context/opt/"
docker rm "$trace_context_container"
printf '%s\n' "$trace_oracle_arm64" > "$trace_work/context/accepted-image-id"
docker buildx build --load --platform linux/arm64 \
  --build-context "accepted=$trace_work/context" \
  -f experiments/m2_trace/Dockerfile \
  -t phoenix-m2-trace:arm64-qemu9.2.0-v1 .
trace_observer=$(docker image inspect --format '{{.Id}}' \
  phoenix-m2-trace:arm64-qemu9.2.0-v1)
printf '%s\n' "$trace_observer" > "$trace_work/observer.id"
sh experiments/m2_trace/build-fixtures "$trace_oracle_amd64" "$trace_work/fixtures"
```

The `accepted` context contains the exact accepted guest runtime and launcher.
`Dockerfile.dockerignore` limits the default context to the observer source,
recipe, licenses, and Python modules needed by the worker. It uses exact file
paths. It does not include fixtures, private data, caches, or other pipeline
modules. The production `.dockerignore` is unchanged. The
observer replaces its own QEMU copy and adds its own plugin. It preserves
the x86 guest libraries and locale. The image records their hashes, the
accepted image ID, observer hashes, and installed package versions under
`/opt/source`. It retains the official archive, GPL text, plugin source,
header, notices, and recipe. See [ADR 0018](../../docs/adr/0018-public-trace-prototype.md).
Source availability and attribution duties still apply to distribution.

The build script compiles original, unchanged, wrong-target, and
wrong-count variants for both compilers and optimization levels. It writes
stripped binaries, matching disassemblies, a package list, and a hash
commitment. It streams the fixed source archive to the Linux worker.
Compiler temporary files use its writable `/work` directory.
It executes no fixture. Before any runtime experiment, review
and preserve that commitment. Run this host-only static check first:

```sh
uv run --locked python - "$trace_work/fixtures" <<'PY'
import sys
from pathlib import Path
from experiments.m2_trace.plan import make_plan
root = Path(sys.argv[1])
for compiler in ("gcc", "clang"):
    for level in ("O0", "O2"):
        for variant in ("original", "unchanged", "wrong-target", "wrong-count"):
            binary = root / f"{compiler}-{level}.{variant}"
            plan, symbols = make_plan(binary, Path(str(binary) + ".dis").read_text())
            print(binary.name, plan.binary, plan.sha256, symbols["walk"])
PY
```

Then run the sandboxed public experiment. Use a fresh report directory.

```sh
uv run --locked python -m experiments.m2_trace.driver \
  "$trace_work/fixtures" "$trace_work/observation-1" \
  --oracle-amd64 "$trace_oracle_amd64" \
  --oracle-arm64 "$trace_oracle_arm64" --observer "$trace_observer"
```

Run the plugin rejection controls after the positive calibration.
Use this command when no sealed measurement or replay uses the VM.
It builds two separate control images. It preserves the accepted tags.

```sh
uv run --locked python -m experiments.m2_trace.negative_controls \
  "$trace_work/fixtures" "$trace_work/observation-1/report.json" \
  "$trace_work/negative-controls-1"
```

The output directory must be new. The command binds each modified source,
compiled plugin, image, invocation, outcome, and trace by hash.
A wrong API version must stop before target execution. A missing register
must retain the original outcome and emit the exact register-gap record.
Both traces must be rejected. The command records partial evidence if
a control fails. Its final report sets `negative_controls_passed` to true
only after both controls pass.

The driver checks commitments before execution. It obtains normal
untraced outcomes with the unchanged dual-emulator oracle. Each observation
uses the same `Invocation`, fresh tree, environment, launcher, resource
limits, and outer Docker sandbox. Full `Outcome` equality includes streams,
termination, file bytes, paths, and modes. An observer mismatch rejects trace
evidence and retains the original oracle agreement record. It cannot
remove the case from oracle accounting.

The driver requires three matching comparable repetitions for each original
and unchanged rebuild. It checks the physical targets of `walk`, `fread@plt`, `fwrite@plt`, and
indirect calls. Disassembly must contain all five target symbol labels.
The comparable signature includes each destination after load-bias removal.
The driver requires one fread, one walk, and one fwrite, in that order.
Each byte operation must start and return inside walk. This includes zero
byte operations for empty input. The driver then checks each byte argument
and result, fread output, fwrite input, and stdio requests and returns.
It ignores raw pointer equality between executions. It requires observable
oracle differences for both mutants and a rejected source-contract check
for their otherwise valid observations. Truncated trace controls must fail.
Reports include exact invocations, outcomes, hashes, plans, and raw evidence.
Positive observations and mutant controls use the same record constructor.
Each observation saves its full outcome, trace filename, trace hash, and plan
hash before parsing or calibration. Rejection does not erase that evidence.
They contain public development data only. No repair channel is created.

Host checks need no Docker or target execution:

```sh
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv run --locked mypy --explicit-package-bases experiments/m2_trace
uv run --locked python -m pytest tests/test_m2_trace.py \
  tests/test_m2_calibration.py tests/test_m2_build_context.py
scripts/check
```

The image build and fixed public calibration passed on 2026-11-10.
The first build failed because a multi-file `ldd` heading entered the
library list. Separate `ldd` calls corrected that recipe error.
The accepted oracle image IDs stayed unchanged. The observer guest-runtime
hash check passed. All 96 positive cases passed three repetitions.
All eight mutant trace controls failed calibration as required.
The parent checked all 296 saved trace hashes. It also parsed each trace
again and checked its plan and outcome against both oracle outcomes.

The public report is under
`$PHOENIX_ROOT/tmp/m2-public-calibration/observation-1/report.json`.
Its SHA-256 is
`d982848be0620ac8e838cf621b500235eb3966a601de23ce307bbae457700a64`.
Parent checks and build logs are under
`$PHOENIX_ROOT/audit/continue-v1/observer-*`.
The later wrong-API and missing-register Linux controls also rejected their
traces. The missing-register control retained the agreed oracle outcome.
These results are under `$PHOENIX_ROOT/tmp/m2-observer-negative-controls`.
Use the new command to repeat those controls. Its host tests and checks of
the saved outcomes passed. A fresh independent Sol review passed the command
and saved evidence. A fresh command run remains pending while M1 uses the VM.
Independent Sol review passed the initial recipe and calibration evidence.
These public checks do not establish production recovery or M2 acceptance.

The observer covers only planned calls and program returns. It has no
allocation tracker, shared-library map, type solver, localization, schema-2
Ghidra export, tail-call model, or production trace hierarchy. Register
values and memory samples are observations. They do not establish C types,
object capacity, equivalence, integrity, or milestone acceptance.
