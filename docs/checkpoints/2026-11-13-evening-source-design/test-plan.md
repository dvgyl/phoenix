The goal is to support Phoenix through every SPEC section 9 condition. This plan tests only the source schema 2 boundary defined in `api.md`. The frozen design base is `d43f604bfdb6ef63b2b9086352c440be3559b1d5`.

**PASS-to-implement is a design verdict.** These implementation tests have not run because Unit B does not exist. The completed independent design control is `boundary-probe.json`. Producer admission and production remain HOLD.

Use hand-written source bytes and explicit expected intervals. Keep the expected projection independent of the implementation. Do not use the new projector, producer, source serializer, or shared fixture transform to build both input and expected output. Small graph fixtures may use the existing graph parser after their literal expected fields are fixed. Do not import product tests to obtain the only positive control.

**Independent literal controls.**

Use these three distinct source inventories first.

| Literal bytes | Exact inventory and expected projection |
| --- | --- |
| `b""` | Zero lines, zero items, one global source-unbound gap, zero projection rows, zero tokens. |
| `b"\n"` | One line, zero indent, one empty syntax item at `[0,0)`, separator `[0,1)`. One row `(0,None)`, zero tokens. |
| `b"  A\xc3\xa9\n"` | One line with indent `[0,2)`. Items at `[2,2)`, `[2,3)`, `[3,3)`, `[3,5)`, `[5,5)`. Separator `[5,6)`. Rows `(0,None)`, `(1,0)`, `(2,None)`, `(3,1)`, `(4,None)`. Tokens cover `A` and `é` only. |

Give the third fixture's empty variable item an actual direct operation and a source-only value. Give another empty item a case operation and its exact item gap. The graph must contain the source-only value even though no operation uses it. Preserve every empty row and direct link in the source. The view hash must change if that empty link changes, even when positive tokens do not.

Use a separate literal with two equal-storage graph values. Link an item to the second value. The expected key is the second identity. It must not become the first matching storage value. Repeated symbol-storage pieces must remain repeated and ordered. Include one variable with a direct parameter symbol but no operation or value. Include one with a non-parameter symbol and nonempty storage. Include one direct variable whose value is unrelated to its direct operation operands. The reader must preserve that observation without inventing a relation.

Add an indented empty line with both indentation bytes and a spacer item that repeats the indentation text. Fix the expected bytes manually. Label it a structural fixture. A future pinned Java test must separately confirm actual printer behavior. Do not claim Java execution from a Python fixture.

**Call every public boundary independently.**

Each applicable negative case must run through `parse_byte_source_v2`, `project_positive_spans`, and `check_positive_span_view`. A parser-only pass does not establish the typed-source boundary. Construct typed negative objects directly with `dataclasses.replace` or controlled `object.__setattr__` in tests. Do not serialize them before sending them to the typed API. That could erase the defect under test.

| Control group | Required result |
| --- | --- |
| Exact parsed source | Parsing, projection, and checking succeed with literal expected values. |
| Valid independently constructed source | The same values pass full revalidation. No constructor certificate is required. |
| Direct `ByteGraphV2` in `graph_bytes` | Finite format refusal, even if originally parsed. No typed-graph overload exists. |
| Invalid graph bytes | Missing mandatory gap, broken reciprocal edge, wrong output identity, absent source-only value, wrong roster, or foreign pass refuses before a view is returned. |
| Changed graph bytes with stale source graph digest | Binding refusal. |
| Noncanonical but valid graph JSON | The source binds the accepted graph's canonical digest. A raw-input digest is refused when it differs. |
| Changed lift raw C | Graph binding refusal or raw C equality refusal. |
| Changed explicit raw C with unchanged lift | Binding refusal, including LF versus CRLF and two normalization forms. |
| Changed lift roster, selected entry, operation, or operand | The existing graph relation checks still run. No source path bypasses them. |
| Changed pass ordinal or pass function | Binding refusal. Boolean or float identity gets format refusal before equality. |
| Changed fixed Ghidra, JDK, language, timeout, or transformer field | Pin refusal, as classified by the graph parser. |
| Changed source or tool digest claim without graph rebinding | Binding refusal. |
| Coherently changed source and tool digest claims, pass IDs, graph hash, and source bindings | Structural acceptance can occur. No producer or semantic authority follows. This is a required positive authority-limit control. |
| Reduced graph limit on projection or checker | Same refusal as a fresh graph parse. Defaults must not replace the supplied limit. |
| Reduced source limit on a previously parsed source | Refusal under the current call. Prior acceptance does not persist. |

Keep the completed design counterexample as an independent regression rationale. It showed that `Location("ram", True)` in a typed graph serializes as the valid address `0x1`. The design rejects graph objects at this boundary. If a future convenience overload accepts them, that new overload must pass an exact nested type walk before encoding. Such an overload requires a new review.

Test the local lift container preflight with a list in a tuple field, a wrong record class, a malformed range pair, and a custom mapping. Use a custom mapping whose methods raise if called. Reject it without executing its methods. Accept ordinary parsed mapping proxies and built-in maps with valid records. Snapshot both in roster order. Malformed consumed scalar fields must retain the graph parser's existing refusal behavior. Do not assert semantic validation of unconsumed lift fields.

**Source partition and Unicode controls.**

For each line segment and item segment, move the start or end by one byte. Test gaps, overlaps, missing prefix, missing suffix, removed final separator, wrong separator, wrong indentation byte, incorrect indent length, and an out-of-range offset. Reject each contradiction. Retain empty indentation and multiple zero-width items at the same valid boundary.

Test two-byte and four-byte scalars, combining marks, both normalization forms, literal tabs, embedded newlines, LF, and CRLF. Use explicit expected byte arrays. Test a positive span that starts or ends inside a scalar. Also test an empty span inside a scalar. The latter can decode as empty text and must still refuse. Test isolated surrogate escapes in original text, rendered text, kind, space, and register fields. Test invalid raw UTF-8. No normalization or replacement-character recovery is permitted.

Delete or reorder a line, item, or empty item without repairing ordinals and partition. Expect refusal. Then construct a separate internally consistent empty-item deletion with all ordinals, hashes, and inventory counts repaired. The reader can accept that changed observation. Its source hash must differ. Checking an old supplied view against it must refuse. This control prevents the test suite from claiming that structural parsing authenticates the producer's complete inventory.

Test line number zero, skipped line number, Boolean line number, wrong first-item cursor, zero item count on a nonempty line inventory, item overrun, wrong line ordinal, wrong per-line ordinal, and unconsumed final items. A line with an embedded newline inside an item still follows the supplied API line inventory.

**Class, render, association, and storage controls.**

Use a literal 10-class by 11-syntax-type matrix. The five transformed classes use `illegal_char_cpp` except at syntax type 5. Every other pair uses identity. Unknown class names, unknown subclasses, `ClangBreak`, non-ASCII class names, wrong syntax type, and Boolean syntax types refuse. Identity rendering requires exact text equality. Transformation rendering retains a bounded original/rendered pair without a Python imitation of Java. Include a transformed pair that the pure reader cannot authenticate. Its structural acceptance must not be labeled proof of correct Java transformation.

Exercise every row of the association table in `api.md`. Test all forbidden non-null base-getter fields. For variable tokens, test each nullable direct observation separately. Do not infer a value from a symbol or operation. For field tokens, test a required operation with a non-null output, an operation with null output, a missing operation, and a different equal-storage value. Only exact output identity passes. For bit-field tokens, reject field association and field rendering. Preserve their optional operation with null value and symbol fields.

For each case token, require null value, null formal, empty storage, and the exact item-specific source-unbound gap. A global gap or a gap for a neighboring item must not replace it. Case operation may be null. No predecessor traversal occurs in the Python reader.

Storage tests cover sizes 1 and 8,192, zero and 8,193, unsigned interval end exactly `2**64`, and one-byte wrap. Cover register names of 256 UTF-8 bytes and 257 bytes. Cover empty register names and isolated surrogates. Cover signed stack offsets `-2**63`, `-1`, `0`, and `2**63-1`. Check an interval ending at zero, one crossing zero, an interval ending at `2**63`, and one beyond it. Test wrong modulo relation, stack register names, non-stack stack offsets, wrong integer types, and reordered or repeated pieces. Test formal 0, 127, 128, Boolean, float, null, and non-null formal with empty storage.

**All source gaps remain visible.**

Test every one of the 13 allowed gap codes. Test foreign block, raw operation, analyzed operation, value, and item keys. Raw operations are permitted in gaps but not in item operation links. Check block-operation ownership. Test duplicate gaps, noncanonical order, extra keys, missing keys, and missing mandatory empty-inventory or case gaps. An extra unrelated gap does not discharge a required gap. A valid additional gap must remain in the source canonical bytes and source hash. Graph gaps remain in the bound graph and must not be silently copied away or discarded.

**Candidate mutation controls.**

Create the candidate from an independent literal expected view. Mutate one field per case. Test source hash, row count, item ordinal, nullable positive ordinal, token count, token ordinal, both span endpoints, kind, text digest, operation function/domain/pass/sequence, value function/pass/local ID, formal ordinal, each storage address/size/register/stack offset, and storage order or multiplicity. Remove each empty row in turn. Remove a positive item. Add a token for indentation or a separator. Reorder equal-looking empty rows. All changed candidates must refuse against the unchanged complete source.

Use Boolean and float substitutions at every candidate integer field, especially ordinal 0 or 1. Use an integer subclass with an equality method that raises. The checker must refuse the type before equality. Use v1 key data classes with the same field values. They must refuse. Use a candidate subclass with a custom `record` method. It must refuse without invoking that method. A well-formed but unequal candidate gets binding refusal. A malformed candidate gets format refusal.

Check that the public computation always recomputes rather than reading candidate data, stored validation flags, or a global cache. Change graph and pass inputs between calls. Check that the old view cannot pass against a changed source. This is a behavior test, not a requirement for a specific private helper layout.

**Bounds and finite failures.**

For each of the nine source limit fields, test an exact reduced boundary and one over it. Test hard maxima where a valid complete record can fit the other caps. Report a combined-cap refusal honestly where the canonical byte cap is reached first. Do not call an unreachable full-count fixture a successful maximum test.

Test all nine fields with zero, negative, Boolean, float, string, null, and maximum-plus-one. Mutate a previously constructed frozen limit object to each invalid value. Repeat representative cases through all three public functions. Apply the same strategy to all 14 graph limit fields through source calls. Test crossed source-byte limits where each object is independently the smaller one.

Original text and rendered text need independent aggregate tests. Include many empty rendered items with nonempty original text under transformation rules. The original-text counter must still refuse excess input. Include a large unused value bank to confirm graph limits still apply even when source links do not use the values. Count every repeated storage piece. A candidate with too many rows must fail before expensive recomputation.

Test duplicate JSON keys at every nested object, missing and extra fields, NaN, infinities, integer floats, huge decimal integers, invalid hex, BOM, trailing content, invalid UTF-8, and excessive depth. Use independent hand-written malformed bytes for duplicate keys. A dictionary serializer cannot create that test.

Inject RuntimeError, ValueError, TypeError, and OSError at the hash call. These unexpected failures must propagate. They must not become source-format refusals or accepted unavailable values. Check that malformed input errors contain no source fragment, custom object representation, or process log.

**Property tests and implementation gates.**

Use bounded Hypothesis generators for valid complete partitions with empty items, multibyte scalars, repeated storage, and both separators. Assert canonical round trips, idempotent projection, exact full row coverage, positive token coverage, and checker acceptance. Mutate one selected relation and require the expected finite refusal. Keep the literal controls separate so a shared generator mistake cannot define the whole oracle.

Run the new source tests with the unchanged old source and both graph test suites. Confirm that schema 1 readers still reject schema 2 and preserve their existing bytes and behavior. Confirm v1 positive tokens still use their old key classes. Keep old export, mapping, Java, and publication files byte-exact. Run the required format, lint, strict typing, and relevant repository quality checks during implementation. A later independent reviewer must inspect Unit B at its exact source revision before root integration.

This design task ran no pytest collection, full repository check, compiler, Java, target, Ghidra, plugin, VM, or network job. Later pinned Java rendering and same-call object-identity controls are separate gates. Full capture remains OPEN after provider screening. No replacement review is authorized by this plan.

The root must retain all SPEC section 9 work. M4, T0 through T3 comparisons with every baseline, costs and failures, required publication, and headline replay remain required. Source-reader tests are not reconstruction scores.
