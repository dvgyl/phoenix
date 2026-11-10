# Prior art and dependencies

Phoenix measures whole-program behavior and portability within the
limits in [SPEC.md](../SPEC.md). The list below records the upstream
projects used in the workspace and the local quality checks.

| Project | Use in Phoenix | Upstream source |
| --- | --- | --- |
| Colima and Lima | Linux VM on macOS | [Colima](https://github.com/abiosoft/colima), [Lima](https://github.com/lima-vm/lima) |
| Docker CLI | Run isolated Linux containers | [Docker CLI](https://github.com/docker/cli) |
| Rosetta 2 | Independent x86-64 execution on Apple Silicon | [Apple Virtualization](https://developer.apple.com/documentation/virtualization/running-intel-binaries-in-linux-vms) |
| Python and uv | Orchestration and locked Python environments | [CPython](https://github.com/python/cpython), [uv](https://github.com/astral-sh/uv) |
| Ruff and mypy | Formatting, lint, and static type checks | [Ruff](https://github.com/astral-sh/ruff), [mypy](https://github.com/python/mypy) |
| pytest, Hypothesis, and pytest-cov | Test execution, generated test cases, and Python line coverage | [pytest](https://github.com/pytest-dev/pytest), [Hypothesis](https://github.com/HypothesisWorks/hypothesis), [pytest-cov](https://github.com/pytest-dev/pytest-cov) |
| pre-commit | Run the quality checks before a commit | [pre-commit](https://github.com/pre-commit/pre-commit) |

| Project | Use in Phoenix | Upstream source |
| --- | --- | --- |
| Ubuntu 24.04 | Pinned Linux image and package archive | [Ubuntu images](https://github.com/docker-library/official-images/blob/master/library/ubuntu), [Ubuntu Snapshot Service](https://snapshot.ubuntu.com/) |
| APT mirror transport | Fetch package files from an official Ubuntu pool if the snapshot cannot supply them | [Ubuntu APT mirror transport](https://manpages.ubuntu.com/manpages/noble/man1/apt-transport-mirror.1.html) |
| GnuPG 2.5.21 | Sign a synthetic repository for the package transport probe | [GnuPG](https://gnupg.org/), [license](https://gnupg.org/documentation/manuals/gnupg/Copying.html) |
| Docker Engine and Buildx | Isolated workers and architecture-specific images | [Moby](https://github.com/moby/moby), [Buildx](https://github.com/docker/buildx) |
| GCC, Clang, CMake, and GNU Binutils | Build and strip public test executables | [GCC](https://gcc.gnu.org/), [Clang](https://clang.llvm.org/), [CMake](https://cmake.org/), [GNU Binutils](https://www.gnu.org/software/binutils/) |
| Clang LibTooling and LLVM | Resolve C declarations and their stored data for integrity checks | [Clang LibTooling 18.1.3](https://github.com/llvm/llvm-project/blob/llvmorg-18.1.3/clang/docs/LibTooling.rst), [LLVM license](https://llvm.org/LICENSE.txt) |
| Linux seccomp | Restrict system calls in the test process | [Linux kernel documentation](https://kernel.org/doc/html/latest/userspace-api/seccomp_filter.html) |
| QEMU user mode | Independent execution of x86-64 programs | [QEMU](https://www.qemu.org/docs/master/user/main.html) |
| Bubblewrap | Design comparison for per-test isolation | [Bubblewrap](https://github.com/containers/bubblewrap) |
| GitHub Actions and Astral setup-uv | Native CI and public report comparison | [Checkout](https://github.com/actions/checkout), [Artifact upload](https://github.com/actions/upload-artifact), [Artifact download](https://github.com/actions/download-artifact), [Setup uv](https://github.com/astral-sh/setup-uv) |
| QEMU TCG plugin interface | Observe original instruction execution | [QEMU 8.2 plugin API](https://qemu.readthedocs.io/en/v8.2.10/devel/tcg-plugins.html) |
| Meson, Ninja, pkgconf, and GLib | Build the pinned QEMU release | [Meson](https://github.com/mesonbuild/meson), [Ninja](https://github.com/ninja-build/ninja), [pkgconf](https://github.com/pkgconf/pkgconf), [GLib](https://github.com/GNOME/glib) |
| Ghidra 12.2 | Export program evidence and decompiled C | [Release](https://github.com/NationalSecurityAgency/ghidra/releases/tag/Ghidra_12.2_build), [headless analyzer guide](https://github.com/NationalSecurityAgency/ghidra/blob/Ghidra_12.2_build/Ghidra/RuntimeScripts/support/analyzeHeadlessREADME.md) |
| Gson 2.13.2 | Write JSON in the headless exporter through the library bundled with Ghidra | [License](https://github.com/google/gson/blob/gson-parent-2.13.2/LICENSE) |
| Temurin 25.0.5+8 | Run the pinned Ghidra release | [Official release](https://github.com/adoptium/temurin25-binaries/releases/tag/jdk-25.0.5%2B8) |
| Codex CLI and OpenAI Responses API | Standard-tier reconstruction and repair requests | [Non-interactive Codex](https://learn.chatgpt.com/docs/non-interactive-mode), [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create) |
| ELF specification | Validate file structure and dynamic linkage | [Section headers](https://gabi.xinuos.com/v42/elf/03-sheader.html), [dynamic linking](https://gabi.xinuos.com/v42/elf/08-dynamic.html) |


## Surveyed candidates

This source survey was completed on 2026-11-10. Adoption requires a
separate ADR, a compatible license, attribution, and public integration
tests. The revisions identify inspected upstream sources. Release and
runtime compatibility checks are pending.

### Decompilation and type recovery

| Candidate | Possible use | License and evidence |
| --- | --- | --- |
| rev.ng, source `d05253474d82c10c5ab576c3a64d42affbe3a950` | Compare recompilable C archives and cross-function data-layout inference. Check helper portability before an experiment. | Upstream distinguishes MIT individual files from the GPLv2 combined project. A packaged release pin requires verification. [README](https://github.com/revng/revng/blob/d05253474d82c10c5ab576c3a64d42affbe3a950/README.md), [MIT terms](https://github.com/revng/revng/blob/d05253474d82c10c5ab576c3a64d42affbe3a950/LICENSE.mit), [project license](https://github.com/revng/revng/blob/d05253474d82c10c5ab576c3a64d42affbe3a950/LICENSE), [design](https://docs.rev.ng/what-is-revng/). |
| RetDec `v5.0` | Compare function recovery, instruction idioms, types, and C output with Ghidra. Its README reports limited maintenance. Whole-program portability needs a public test. | MIT for the project. Bundled components have separate terms. [Versioned README](https://github.com/avast/retdec/blob/v5.0/README.md), [license](https://github.com/avast/retdec/blob/v5.0/LICENSE). |
| angr, source `bbdd957c4e5ee9c3f6262f18350b2a13809bc4ad` | Study control-flow recovery, calling conventions, and Typehoon constraints. Typehoon describes an incomplete Retypd-style implementation. | BSD-2-Clause for angr. Dependency licenses need separate checks. A release pin requires verification. [License](https://github.com/angr/angr/blob/bbdd957c4e5ee9c3f6262f18350b2a13809bc4ad/LICENSE), [decompiler](https://docs.angr.io/en/latest/analyses/decompiler.html), [Typehoon](https://github.com/angr/angr/blob/bbdd957c4e5ee9c3f6262f18350b2a13809bc4ad/angr/analyses/typehoon/typehoon.py). |
| Retypd, source `8f7f72be9a567731bb82636cc91d70a3551050bf` | Study recursive type constraints, subtyping, and cross-call polymorphism. Phoenix would need a constraint exporter and evidence mapping. The upstream API can change. | GPLv3. A release pin requires verification. [README](https://github.com/GrammaTech/retypd/blob/8f7f72be9a567731bb82636cc91d70a3551050bf/README.md), [license](https://github.com/GrammaTech/retypd/blob/8f7f72be9a567731bb82636cc91d70a3551050bf/LICENSE.md), [algorithm](https://github.com/GrammaTech/retypd/blob/8f7f72be9a567731bb82636cc91d70a3551050bf/reference/type-recovery.rst), [paper](https://arxiv.org/abs/1603.05495v2). |
| LLM4Decompile, source `85b364bf093eb2ee4f3687cfe38a203fca89f23e` | Study function-level Ghidra refinement and evaluation adapters. Whole-program portability needs separate validation. | Code uses MIT. Model and dataset terms require artifact-specific checks. The repository contains DeepSeek License Agreement 1.0 with use restrictions. The `llm4decompile-6.7b-v2` model card says MIT. Applicable weight terms and the exact weight revision remain unresolved. [Paper](https://aclanthology.org/2024.emnlp-main.203/), [README](https://github.com/albertan017/LLM4Decompile/blob/85b364bf093eb2ee4f3687cfe38a203fca89f23e/README.md), [code license](https://github.com/albertan017/LLM4Decompile/blob/85b364bf093eb2ee4f3687cfe38a203fca89f23e/LICENSE), [model terms](https://github.com/albertan017/LLM4Decompile/blob/85b364bf093eb2ee4f3687cfe38a203fca89f23e/LICENSE-MODEL), [model card](https://huggingface.co/LLM4Binary/llm4decompile-6.7b-v2). |

### Differential tests and repair

| Candidate | Possible use | License and evidence |
| --- | --- | --- |
| Chisel, source `855acb07d0ee69b759d91895e8b5a846291db5a5` | Study counterexample replay, pointer-content comparisons, separate scoring, and best-candidate retention. The experiments use ExeBench functions on x86-64. The paper identifies false acceptance from incorrect recovered signatures. | The paper uses CC BY 4.0. Code reuse permission requires verification of a code license. [Paper](https://arxiv.org/html/2608.27981v1), [author-linked repository](https://github.com/VarunKohli18/chisel), [versioned README](https://github.com/VarunKohli18/chisel/blob/855acb07d0ee69b759d91895e8b5a846291db5a5/README.md). |
| AFL++ `v5.03c` | Test iterative edge feedback and comparison-guided input mutation on public originals. Its forkserver needs process creation and shared memory. Phoenix would need invocation and filesystem-reset adapters. | AFL++ uses AGPL-3.0-or-later as a whole, with Apache-2.0 on some files. qemuafl has separate GPLv2-based terms. The survey inspected qemuafl `c05ba961dbd3f1ce07a15e260dfa71b1cb05f75a`. Its relation to the release submodule pin needs verification. [Release](https://github.com/AFLplusplus/AFLplusplus/releases/tag/v5.03c), [QEMU mode](https://github.com/AFLplusplus/AFLplusplus/blob/v5.03c/qemu_mode/README.md), [licensing guide](https://github.com/AFLplusplus/AFLplusplus/blob/v5.03c/LICENSING.md), [qemuafl license](https://github.com/AFLplusplus/qemuafl/blob/c05ba961dbd3f1ce07a15e260dfa71b1cb05f75a/LICENSE). |
| QEMU `v9.2.0` | Prototype register and guest-memory observations in a separate public trace runner. Require its outcomes to match the current oracle. API 4 adds `qemu_plugin_read_memory_vaddr`. Values provide evidence for later type analysis. | The combined emulator uses GPLv2. The plugin header uses GPL-2.0-or-later. Runtime compatibility with Phoenix needs a public test. [Release](https://www.qemu.org/2024/12/11/qemu-9-2-0/), [plugin header](https://github.com/qemu/qemu/blob/v9.2.0/include/qemu/qemu-plugin.h), [license](https://github.com/qemu/qemu/blob/v9.2.0/LICENSE). |

### Qualifications to the specification's prior-art table

The rev.ng sources support recompilable archives and cross-function
structure inference. Its project organization and behavioral tests need
further inspection.

Chisel reports 79.8% re-executability across stripped and unstripped
function variants. Its stripped-only average is 72.9%. Its signature
limitations matter for Phoenix's design. LibFuzzer uses an in-process
target interface, so whole-program CLI testing requires an adapter.
These are upstream results. [Chisel paper](https://arxiv.org/html/2608.27981v1),
[libFuzzer interface](https://llvm.org/docs/LibFuzzer.html).

Recompilation Is Not Enough reports 91 of 104 Coreutils 9.5 binaries
passing its official-test and smoke-test gate. Nine failed to build,
and four failed that gate. Its section 4.1 distinguishes the gate from
the complete official suite. Its section 5 describes the narrow scope.
Artifact, code-license, and AArch64 evidence require further verification.
[Paper](https://arxiv.org/html/2609.07201v1).

Agent4Decompile explicitly studies single functions. Its full-text tables
assign 50.3% to the 157-item benchmark. The abstract and tables have
inconsistent rates. The specification's combined rate and denominator
need resolution before citation as a verified result.
[Paper](https://arxiv.org/html/2604.23940v2).

LLMSbt describes AArch64 assembly translation with snippet verification.
SK2Decompile separates structure and identifier recovery. Its ICLR 2026
acceptance and DecLLM's stated scope need further primary-source checks.
[LLMSbt](https://arxiv.org/abs/2610.05999v1),
[SK2Decompile](https://arxiv.org/abs/2509.22114v1).

### Evaluation boundary

Phoenix's proposed contribution is the conjunction in SPEC.md section 2.2.
It combines whole-program reconstruction, sealed post-cutoff evaluation,
AArch64 portability, and a behavioral oracle with hidden evaluation inputs.
A novelty claim requires further literature verification.

Phoenix-Bench uses fresh programs. Exclude HumanEval, ExeBench,
decompile-bench, Chisel's cached cases, and known Coreutils-style research
programs. Familiar programs have a contamination risk. Their results
apply to public experiments.

Run future optional tool experiments on public fixtures only. Compare
recovered signatures and structures with public source and exact process
outcomes across architectures. Check tool output as evidence under the
existing integrity rules.
