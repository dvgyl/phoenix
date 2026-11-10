# PhoenixPublicTraceV1

This contract precedes the implementation. All files use ASCII and LF.
Fields use one tab. Empty fields are forbidden. Integers use 16 lowercase
hex digits, except sequence numbers and counts, which use canonical decimal.
Digests use 64 lowercase hex digits. Byte strings use lowercase hex or `-`
for zero bytes. Unknown fields, record kinds, and versions are rejected.

The plan starts with `M2PLAN<TAB>1<TAB>binary_sha256`. Each following line
has `S<TAB>kind<TAB>elf_va<TAB>instruction_bytes`. Kinds are `call`,
`indirect`, `fread`, `fwrite`, `ret`, and `continuation`. Addresses are
unique. Instructions contain 1 to 15 bytes. Calls require a witnessed
continuation at the next instruction. There are at most 128 sites and
16 KiB of plan bytes. The binary must pass the existing ELF ingest check.
Only executable, file-backed PT_LOAD ranges may contain sites. Witness
bytes must match the binary. The plan digest covers its exact bytes.
This calibration plan comes from the public fixture disassembly. It is
not a Ghidra exporter or a general instruction decoder.

The trace header has these fields in order:

```text
M2TRACE  1  binary_sha256  plan_sha256  runtime_start_code  runtime_end_code
```

The spaces above represent tabs. The start and end must match executable
PT_LOAD file bounds after one load bias. Each executed planned instruction
must match its byte witness. The interpreter entry is never a base anchor.
Addresses in event sites are ELF virtual addresses. Transfer destinations,
registers, and pointers are raw U64 observations. The parser supplies a
segment index and offset for destinations inside executable PT_LOADs.
Other destinations remain external and unknown.

Events have these exact fields:

```text
A  seq  site  rdi  rsi  rdx  rcx  rax  rsp
T  seq  attempt_seq  actual_next_pc
R  seq  site  expected_next_pc  rsp  rax
C  seq  call_seq  continuation_site  rax  rsp
B  seq  call_seq  phase  pointer  item_size  item_count  returned_items  status  bytes
G  seq  gap_code
END  event_count  sha256  status
```

`A` is a pre-instruction call attempt. `T` confirms the next executed PC
for an `A` or `R`. A call attempt alone is not a completed call. `R`
reads the stack return address through the guest-memory API. `C` captures
the return register before the caller continuation changes it. Calls and
returns use a bounded LIFO frame stack and check RSP. The prototype does
not claim libc internal return events. A continuation confirms a libc call.

`B` samples fwrite input at `entry` or fread output at `continuation`.
Returned items are zero at entry. Status is `ok`, `null`, `overflow`,
`unreadable`, or `limit`. `ok` captures the full observed span, up to
256 bytes. A larger span emits `limit`, no bytes, and a limit gap.
The fread span uses returned whole items.
An empty sample is valid only for a zero span. A failed read emits no
bytes and a gap. An over-limit span cannot produce a complete trace.
A sample is not a complete object or a capacity claim.
No FILE internals are read. Snapshots can contain stale writes under the
QEMU API contract. Store-then-sample runtime calibration is required.

Gap codes are `register`, `mapping`, `witness`, `stack`, `memory`, `pending`,
`limit`, and `vcpu`. Any gap prevents a complete trace. Sequence numbers
start at zero and are contiguous. References must point backward to the
correct event kind. A transfer must be the next event after its attempt,
except that a fwrite entry sample can intervene. A continuation must
match the top confirmed call and its witnessed instruction and RSP.

The footer digest covers the header and every event line, including LF.
It detects corruption, not authenticity. Status is `complete`, `limited`,
or `gap`. A complete trace has no gap, pending transfer, or open frame.
A limited prefix is diagnostic evidence only. Missing footers fail parsing.

Fixed limits are one vCPU, 10,000 events including gaps, 8 MiB wire bytes,
64 frames, 256 bytes per sample, 64 KiB sampled bytes, 1,000,000 executed
callbacks, and 1,000,000 translated instructions. The plugin stores only
the fixed plan and frame arrays. Callback userdata is the instruction PC.
It does not retain a translation-address map. Translation and execution
budgets stop collection with a gap. A scoreboard condition disables
execution callbacks after collection stops. Later translation callbacks
return without adding instrumentation. Existing sandbox CPU, address-space,
file-size, and wall-time limits remain in force.

The driver separately binds the exact invocation, full oracle outcomes,
image IDs, guest runtime manifest, and trace bytes in its public report.
No expected output enters repair. No runtime result is an evaluation score.

Calibration uses the fixed source contract after wire validation. The direct
calls occur once each, in the order fread, walk, fwrite. Each byte operation
starts and returns inside walk. Empty input has no byte operation calls.
Calibration rejects any extra, missing, reordered, or misplaced call before
it collects stdio values. It checks physical destinations against the public
`walk`, `fread@plt`, `fwrite@plt`, `increment`, and `exclusive_or` symbol labels.
Plan construction requires these labels. The comparable signature includes
transfer destinations after load-bias removal, including return transfers.

Positive observations and mutant controls share one report record shape.
Each record has `file`, `outcome`, `sha256`, and `plan` fields. The hashes
bind the exact trace bytes and plan bytes. The outcome includes both streams,
termination, and the final file tree. Records are saved before trace checks.
Oracle agreement remains independent of trace rejection.
