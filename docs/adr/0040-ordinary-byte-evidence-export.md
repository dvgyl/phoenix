# ADR 0040. Unpublished ordinary byte evidence

Date: 2026-11-12.
Status: Diagnostic implementation. Complete producer admission remains HOLD.

This unit implements the first producer subunit of U5 step 2. It adds no
pipeline caller, generation option, publication version, or current selector.
Publication versions 1 through 3 and their selected file sets stay unchanged.
The graph and source readers stay unchanged.

## Same-call boundary

The explicit `ExportLift.java` argument is
`lift.json --byte-diagnostic byte-draft.json context.json`.
It is absent by default. The old one-argument and two-argument forms remain.
`OrdinaryByteEvidence.capture` receives the exact `DecompileResults` object
used by the ordinary exporter. The ordinary raw C, graph, and printer data
come from that object. No normalized switch graph or second decompile call
supplies byte evidence. Listing reads do not run another analysis pass.

The helper records every ordinary function in order. It checks the roster
before decompilation. A function has complete observations or an explicit
gap. A global limit refuses the whole job. A graph gap never contains a
partial graph. A printer gap can retain a complete graph and a source record
with `source_status=unavailable`. That source record retains the exact raw C
identity and an explicit `source_unbound` gap. It contains no partial tokens.

Block order, empty blocks, unreachable blocks, reciprocal edge slots, phi
input order, and conditional slots are retained where the profile can
represent the complete function. Operation keys use `SequenceNumber.getTime`.
Value keys use `VarnodeAST.getUniqueId`. An identity map checks actual object
identity. Equal storage does not merge objects or repeated operand slots.
The ordinary lift retains the full raw and analyzed operation banks. The
companion partitions the analyzed bank into block members and excluded
records. Excluded records require `isDead()` and no parent. An active value
cannot depend on an excluded definition.

A separate closed `facts` object retains actual input/free flags for every
active value and actual dead/parent fields for every analyzed operation.
Its frozen Python representation is canonical bytes. It is returned intact.
These fields do not change either graph or source schema.

Known volatile memory and unsupported operations remain evidence gaps.
`CALLOTHER` is unknown user-operation evidence. It does not, by itself,
prove a volatile access. Empty volatile inventories do not prove the absence
of erased source qualifiers. This unit supplies no ordinary-memory contract.

## Printer boundary

The pinned `PrettyPrinter` uses ordered lines, indentation, token text, and
`StringUtilities.LINE_SEPARATOR`. The helper compares each encoded segment
with the corresponding ordinary raw C bytes. Byte accounting is linear.
It never encodes the full preceding source for each token. UTF-8 conversion
rejects unpaired surrogates. Token spans and substring digests use byte
positions. No whitespace or Unicode normalization occurs.

Operation and value links use actual token methods and object membership.
Null links remain null. `getHighSymbol(null)` permits the API's direct
varnode and declaration links. It disables the storage-address lookup
fallback. Formal ordinals and all static storage fields remain proposals.
No address, name, equal storage, or prototype supplies a replacement link.

Three pinned API/profile obstacles remain explicit.

1. `PcodeSyntaxTree.decodeBasicBlock` inserts decoded operations into blocks.
   `PcodeBlockBasic.insertEnd` sets their parent but does not clear the Java
   operation bank's dead flag. Actual block-owned operations can report
   `isDead()=true`. The exporter retains the flag and operation. It adds a
   `cfg_unclosed` gap for each such conflict. It does not exclude the
   operation or claim a proved live/dead interpretation.
2. The existing graph reader requires the analyzed entry block start to equal
   the ordinary function entry. Some actual functions do not satisfy this
   requirement. They receive `entry_unrepresentable`. The exporter does not
   rewrite a block start or create an empty entry block.
3. The pinned printer can insert zero-length spacer tokens on empty lines.
   The existing source reader requires positive spans. The exporter reports
   `empty_printer_token`. It does not silently remove these tokens and claim
   a complete printer inventory.

A separately reviewed adapter must address these facts. It must distinguish
Java bank bookkeeping from native dead-operation evidence. It must bind the
function entry to the actual analyzed entry without changing observed
addresses. It must represent zero-length printer items or define and check
an explicit complete printer-trivia inventory. Changes to existing reader
contracts require their own design and review. This unit does not make them.

## Identity and conversion

The pass record retains the binary and function identities, ordinary call
ordinal, actual Ghidra version and revision, language ID, compiler
specification ID, simplification style, and timeout. The configured options
object is null because the ordinary launcher does not call `setOptions`.
Null means no explicit options object. It does not claim that every effective
native default was exported. Defaults remain bound to the installed tools.
A non-null options object refuses this profile rather than inventing settings.
The first profile requires `x86:LE:64:default`, `gcc`, and `decompile`.

The converter measures the source manifest from named installed repository
files. It includes the four exporter sources, launcher, converter, readers,
mapping/evidence modules, tool identity helper, and `tools.lock`. The tool
manifest uses the existing `lifting_tool_identity` function. It hashes the
listed Ghidra components, native decompilers, x86 language files, Java launcher,
and Java release file. It is that specific manifest, not a hash of every file
in either installation. Installed version properties must match `tools.lock`.
The Java helper checks its four actual staged source files and runtime version
and revision. The launcher checks original and staged inputs, exporter files,
and measured source/tool manifests again after the job.

Pass IDs hash canonical pass records. They identify retained configuration
and same-call context. They do not authenticate a process. A coherent forged
record is not made trustworthy by hashing or by structural parsing. The
public converter accepts no caller-selected source or tool digest. It
measures the installed files. The private pure converter supports synthetic
controls. Those controls prove the transaction contract only.

Draft graph and source objects omit only `lift_sha256`. After exact ordinary
lift bytes exist, the converter inserts their digest. It calls the unchanged
strict graph and source readers for every retained complete graph and source.
It checks the complete ordinary roster, mapping identity, pass identity, and
producer facts. A contradiction refuses the entire result.

All returned records are frozen. Children are tuples, frozen reader records,
or bytes. The result retains exact ordinary lift, mapping, raw draft, and
context bytes. Its canonical diagnostic bytes contain all finalized graph,
source, pass, and fact fields plus artifact identities. Canonical encoding
uses sorted keys, ASCII escapes, compact separators, and one final LF.
No record contains its own digest. Nothing is an admitted generation.

## Bounds and errors

The first profile permits at most 32 ordinary functions. This is a whole
roster limit, not a candidate filter. The binary is at most 16 MiB. The old
lift and mapping limits remain 64 MiB each. Draft and final companion bytes
are each at most 16 MiB. The total binary, lift, mapping, and one companion
representation is at most 160 MiB. This is an artifact-size bound. It does
not claim a 160 MiB process-memory bound. Both draft and final records can
exist in memory during conversion.

Each complete function has at most 32 analyzed and 32 listing blocks,
256 raw operations, 256 analyzed operations including excluded records,
and 256 raw instructions. The existing graph input, reference, value, and
gap bounds apply. Source is at most 1 MiB with 65,536 tokens, four storage
pieces per token, and 256 gaps. Every caller reduction remains effective.
Counts and byte limits are checked before corresponding record construction
where possible. JSON tree creation remains bounded by artifact bytes.
The old ordinary exporter and Ghidra still create their own analysis objects.
These new limits do not claim to bound those internal objects before capture.

The headless adapter uses one process group, one CPU, a 512 MiB Java heap,
a 120-second analysis limit, and a 300-second job limit. It bounds its captured
log and kills and waits for the process group on return or failure. Its
settings, caches, input, scripts, project, and temporary data use owned
external staging. It calls no publishing launcher and writes no selector.
It accepts exactly the lift, mapping, and draft output files.

`ByteExportError` has finite format, limit, identity, I/O, tool, headless,
and timeout categories. Expected parser errors have local conversions.
Unexpected programming failures are not converted by an outer broad handler.
No refusal returns a partial result. Staging is removed after the job.

## Verification and remaining gates

The assigned audit report retains exact commands, failed attempts, hashes,
Java compilation, synthetic controls, and static public-export results.
The actual public E1 binary is documented in the prior public static review.
It is not a compiled byte-loop positive. The private VM is not used.

Complete producer admission remains HOLD for the pinned API/profile obstacles
above. Fresh independent review, version 4 atomic publication,
`ByteLiftGeneration`, byte-loop recognition, complete source grammar,
interface and pointer proof, emission, protected generation, replay, and all
public compiled/live controls remain open. The separate full capture review
remains open after provider screening. M2 through M4 and every SPEC section 9
condition remain open. No commit, push, tag, or Git metadata write occurs.

## F1. Diagnostic filesystem errors

The first independent Sol review held this unit at `d1a1779`. Five routine
filesystem failures escaped as `OSError` subclasses. The corrected boundary
converts errors from explicit staging and log operations to
`ByteExportError` with code `io`. Hash and context calculations stay outside
that conversion. Process launch errors retain the `headless` category.

Five permanent controls failed before the correction and passed after it.
All 110 unchanged independent controls and 786 affected host tests passed.
Two optional live tests were skipped. A repeated public static job retained
the exact ordinary lift, mapping and inspection bytes. Its context identity
changed because the installed exporter source changed. The original HOLD
and failed logs remain. Fresh independent Sol review is required.

## F2. Python 3.12 path loops

Fresh Sol held `b252452` after the F1 correction. The six real loop
controls expose the Python 3.12 `Path.resolve` compatibility behavior.
It raises plain `RuntimeError` with an immediate `OSError(ELOOP)` context.
The original six failing controls and both independent HOLDs remain.

Required Astra advice selected a dedicated resolver at the six
caller-controlled sites. It retains `Path.resolve` and its strict mode.
The conversion requires the exact implicit legacy exception shape.
Explicit causes, suppressed context, subclasses and deeper chains remain
visible. `_io`, process cleanup, hash and context calculations stay
unchanged. No exception message is used to classify the error.

All 37 focused controls, 174 unchanged independent controls and 823
affected host tests passed. Two optional live tests were skipped.
Ruff and strict mypy passed. The public static job retained exact
ordinary lift, mapping and inspection bytes. Its new context binds the
changed source digest. An initial parent setup lacked the review label;
its failure remains. The final repeat verified a fresh bytecode path.

The advice itself ran no new runtime test. Its nested sandbox setup
failed before Python. Root validation supplies the measured controls.
The compatibility claim covers the inspected CPython 3.12.13 POSIX
behavior. It does not authenticate exception origin or prevent filesystem
races. Recheck behavior when Python changes. The full quality gate and
fresh independent Sol review remain required. Producer admission stays
on HOLD for its separate API and semantic gaps.
