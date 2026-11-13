from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from phoenix.observe import collector_layout as layout

PROFILES = ("linux-x86_64-lp64-le-rela-1", "linux-aarch64-lp64-le-rela-1")


def _types() -> tuple[tuple[int, str, int, int], ...]:
    result = []
    for line in _TYPE_EVIDENCE.splitlines():
        if line:
            front, size, alignment = line.rsplit(" ", 2)
            number, name = front.split(" ", 1)
            result.append((int(number), name, int(size), int(alignment)))
    return tuple(result)


def _members() -> tuple[tuple[int, int, str, int, int, int, int, int], ...]:
    return tuple(
        (int(a), int(b), c, int(d), int(e), int(f), int(g), int(h))
        for line in _MEMBER_EVIDENCE.splitlines()
        if line
        for a, b, c, d, e, f, g, h in (line.split(),)
    )


def _tables() -> tuple[tuple[int, str, int, int, str], ...]:
    return tuple(
        (int(a), b, int(c), int(d), e)
        for line in _TABLE_EVIDENCE.splitlines()
        if line
        for a, b, c, d, e in (line.split(),)
    )


def _fields() -> tuple[tuple[int, str, str, int, str], ...]:
    return tuple(
        (int(a), b, c, int(d), e)
        for line in _FIELD_EVIDENCE.replace("\\\n", "").splitlines()
        if line
        for a, b, c, d, e in (line.split(),)
    )


def _descriptor_text(value: layout.Descriptor) -> str:
    names = {tag: name for tag, name, _, _, _ in _tables()}
    match value:
        case layout.UInt64():
            return "u"
        case layout.Boolean64():
            return "b"
        case layout.ExactNumber(value=n):
            return f"n:{n}"
        case layout.EndFrom(prior_name=name):
            return "end:" + name
        case layout.Signed64():
            return "i"
        case layout.TextSlice(kind="literal", literals=choices):
            return "e:" + "|".join(choices)
        case layout.TextSlice(kind=kind):
            return {"text": "s", "digest": "h", "witness": "w"}[kind]
        case layout.TableSlice(target_tag=tag, mode=mode):
            return ("a:" if mode == "array" else "r:") + names[tag]
        case layout.Option(payload=payload):
            return "o:" + _descriptor_text(payload)
        case layout.Variant(nullable=nullable, target_tags=tags):
            return ("v0:" if nullable else "v:") + ",".join(names[t] for t in tags)
    raise AssertionError("Unknown descriptor.")


def _literal_witness(machine: int) -> tuple[int, ...]:
    words = [0x50484F454E49584C, 1, machine, 8, 8, 1, 100, 653, 47]
    for number, _, size, alignment in _types():
        words.extend((number, size, alignment))
    for number, owner, _, offset, size, alignment, code, extent in _members():
        words.extend((owner, number, offset, size, alignment, code, extent))
    sizes = {number: size for number, _, size, _ in _types()}
    for tag, _, element, _, _ in _tables():
        words.extend((tag, element, sizes[element]))
    return tuple(words)


@pytest.mark.parametrize("profile", PROFILES)
def test_complete_literal_inventory(profile: str) -> None:
    definition = layout._definition(profile)
    assert (
        tuple((t.id, t.name, t.bytes, t.alignment) for t in definition.types)
        == _types()
    )
    assert (
        tuple(
            (
                m.id,
                m.owner,
                m.path,
                m.offset,
                m.bytes,
                m.alignment,
                m.type_code,
                m.extent,
            )
            for m in definition.members
        )
        == _members()
    )
    assert (
        tuple(
            (t.tag, t.name, t.element_type, t.logical_element_bytes, t.record_kind)
            for t in definition.tables
        )
        == _tables()
    )
    assert (
        tuple(
            (
                tag,
                f.logical_name,
                f.native_name,
                f.offset,
                _descriptor_text(f.descriptor),
            )
            for tag, fields in enumerate(definition.field_specs, 1)
            for f in fields
        )
        == _fields()
    )
    assert tuple(
        (t.tag, f.logical_name, f.native_name, _descriptor_text(f.descriptor))
        for t in definition.tables
        for f in t.fields
    ) == tuple((a, b, c, e) for a, b, c, _, e in _fields())
    assert (len(_types()), len(_members()), len(_tables()), len(_fields())) == (
        100,
        653,
        47,
        214,
    )
    layout._validate_definition(definition)


@pytest.mark.parametrize(
    "profile,machine", tuple(zip(PROFILES, (62, 183), strict=True))
)
def test_every_witness_position(profile: str, machine: int) -> None:
    actual = layout._expected_witness(layout._definition(profile))
    expected = _literal_witness(machine)
    assert len(actual) == len(expected) == 5021
    for index, value in enumerate(expected):
        assert type(actual[index]) is int and 0 <= actual[index] < 1 << 64
        assert actual[index] == value, index
    raw = b"".join(word.to_bytes(8, "little") for word in actual)
    assert len(raw) == 40168
    assert raw == b"".join(word.to_bytes(8, "little") for word in expected)
    assert raw[:16] == bytes.fromhex("4c58494e454f48500100000000000000")


def test_machine_selection_is_distinct_and_test_only() -> None:
    first, second = (layout._definition(p) for p in PROFILES)
    assert first is layout._definition(PROFILES[0])
    assert first is not second
    assert first.machine == 62 and second.machine == 183
    assert first.id != second.id
    a, b = layout._expected_witness(first), layout._expected_witness(second)
    assert [i for i in range(5021) if a[i] != b[i]] == [2]
    assert a[:9] == (0x50484F454E49584C, 1, 62, 8, 8, 1, 100, 653, 47)
    assert b[:9] == (0x50484F454E49584C, 1, 183, 8, 8, 1, 100, 653, 47)
    assert not hasattr(layout, "LayoutProfile")
    assert not hasattr(layout, "inspect_compiled_data")
    assert not hasattr(first, "witness_source_sha256")
    assert not hasattr(first, "checks_source_sha256")
    assert not hasattr(first, "reader_source_manifest_sha256")
    assert not hasattr(first, "to_bytes")


def test_final_contract_fields_have_no_private_offset() -> None:
    assert tuple(f.name for f in dataclasses.fields(layout.TypeLayout)) == (
        "id",
        "name",
        "bytes",
        "alignment",
    )
    assert tuple(f.name for f in dataclasses.fields(layout.MemberLayout)) == (
        "id",
        "owner",
        "path",
        "offset",
        "bytes",
        "alignment",
        "type_code",
        "extent",
    )
    assert tuple(f.name for f in dataclasses.fields(layout.TableLayout)) == (
        "tag",
        "name",
        "element_type",
        "logical_element_bytes",
        "record_kind",
        "fields",
    )
    assert tuple(f.name for f in dataclasses.fields(layout.TableField)) == (
        "logical_name",
        "native_name",
        "descriptor",
    )
    assert "offset" in {f.name for f in dataclasses.fields(layout.FieldSpec)}
    kinds = {t.name: t.record_kind for t in layout._definition(PROFILES[0]).tables}
    assert kinds["bytes"] == "storage"
    assert {n for n, k in kinds.items() if k == "scalar"} == {"uints", "strings"}
    assert {n for n, k in kinds.items() if k == "pair"} == {
        "registers",
        "plan_gaps",
        "positions",
        "dispositions",
        "dynamic",
    }
    assert sum(k == "object" for k in kinds.values()) == 39


def test_literal_native_offsets_and_type_codes() -> None:
    definition = layout._definition(PROFILES[0])
    types = {t.id: (t.name, t.bytes, t.alignment) for t in definition.types}
    assert types[5] == ("phoenix_bytes_slice_v1", 8, 4)
    assert types[52] == ("phoenix_signed_v1", 16, 8)
    assert types[66] == ("phoenix_import_binding_v1", 152, 8)
    assert types[86] == ("phoenix_guard_instruction_v1", 88, 8)
    assert types[99] == ("phoenix_table_directory_entry_v1", 56, 8)
    assert types[100] == ("phoenix_data_directory_v1", 2728, 8)
    members = {
        (m.owner, m.path): (m.offset, m.bytes, m.alignment, m.type_code, m.extent)
        for m in definition.members
    }
    for owner in range(5, 52):
        assert members[owner, "offset"] == (0, 4, 4, 2, 1)
        assert members[owner, "count"] == (4, 4, 4, 2, 1)
    assert members[52, "negative"] == (0, 8, 8, 3, 1)
    assert members[52, "magnitude"] == (8, 8, 8, 3, 1)
    assert members[66, "f_identity"] == (48, 16, 8, 0, 1)
    assert members[66, "f_identity.payload"] == (56, 8, 4, 18, 1)
    assert members[66, "f_identity.payload.count"] == (60, 4, 4, 2, 1)
    assert members[66, "f_thunk_path"] == (144, 8, 4, 6, 1)
    assert members[86, "f_rule"] == (24, 56, 8, 0, 1)
    assert members[86, "f_rule.payload_planned_roles"] == (56, 8, 4, 36, 1)
    assert members[86, "f_witness_hex"] == (80, 8, 4, 5, 1)
    assert members[99, "table"] == (48, 8, 8, 4, 1)
    assert [
        members[100, n]
        for n in (
            "logical_data_sha256",
            "renderer_sha256",
            "native_source_sha256",
            "tables",
        )
    ] == [
        (0, 32, 1, 1, 32),
        (32, 32, 1, 1, 32),
        (64, 32, 1, 1, 32),
        (96, 2632, 8, 99, 47),
    ]
    assert sum(m.owner == 100 for m in definition.members) == 4


def _with_member(index: int, member: layout.MemberLayout) -> layout.LayoutDefinition:
    definition = layout._definition(PROFILES[0])
    return dataclasses.replace(
        definition,
        members=(*definition.members[:index], member, *definition.members[index + 1 :]),
    )


def _with_field(
    tag: int, index: int, field: layout.FieldSpec
) -> layout.LayoutDefinition:
    definition = layout._definition(PROFILES[0])
    fields = definition.field_specs[tag - 1]
    changed = (*fields[:index], field, *fields[index + 1 :])
    return dataclasses.replace(
        definition,
        field_specs=(
            *definition.field_specs[: tag - 1],
            changed,
            *definition.field_specs[tag:],
        ),
    )


@pytest.mark.parametrize("component", ("types", "members", "tables"))
@pytest.mark.parametrize("mutation", ("missing", "duplicate", "reordered"))
def test_invalid_inventory_ids(component: str, mutation: str) -> None:
    definition = layout._definition(PROFILES[0])

    def altered[T](rows: tuple[T, ...]) -> tuple[T, ...]:
        return (
            rows[:-1]
            if mutation == "missing"
            else (rows[0], *rows[:-1])
            if mutation == "duplicate"
            else (rows[1], rows[0], *rows[2:])
        )

    if component == "types":
        changed = dataclasses.replace(definition, types=altered(definition.types))
    elif component == "members":
        changed = dataclasses.replace(definition, members=altered(definition.members))
    else:
        changed = dataclasses.replace(definition, tables=altered(definition.tables))
    with pytest.raises(ValueError):
        layout._validate_definition(changed)


@pytest.mark.parametrize(
    "attribute", ("offset", "bytes", "alignment", "type_code", "extent", "id", "owner")
)
def test_each_member_numeric_mutation(attribute: str) -> None:
    definition = layout._definition(PROFILES[0])
    for index, member in enumerate(definition.members):
        changed = dataclasses.replace(
            member, **{attribute: getattr(member, attribute) + 1}
        )
        with pytest.raises(ValueError):
            layout._validate_definition(_with_member(index, changed))


def test_every_field_offset_is_fixed() -> None:
    definition = layout._definition(PROFILES[0])
    for tag, fields in enumerate(definition.field_specs, 1):
        for index, field in enumerate(fields):
            with pytest.raises(ValueError, match="field inventory"):
                layout._validate_definition(
                    _with_field(
                        tag, index, dataclasses.replace(field, offset=field.offset + 8)
                    )
                )


def test_parent_child_containment_and_sibling_disjointness() -> None:
    definition = layout._definition(PROFILES[0])
    layout._check_member_tree(definition)
    index = next(
        i
        for i, m in enumerate(definition.members)
        if (m.owner, m.path) == (66, "f_identity.payload")
    )
    parent_child_overlap = (
        definition.members[index - 2].offset == definition.members[index - 1].offset
    )
    assert parent_child_overlap
    with pytest.raises(ValueError, match="containment"):
        layout._check_member_tree(
            _with_member(
                index, dataclasses.replace(definition.members[index], offset=64)
            )
        )
    count = next(
        i for i, m in enumerate(definition.members) if (m.owner, m.path) == (5, "count")
    )
    with pytest.raises(ValueError, match="overlap"):
        layout._check_member_tree(
            _with_member(
                count, dataclasses.replace(definition.members[count], offset=0)
            )
        )
    with pytest.raises(ValueError, match="coverage|gap"):
        layout._check_member_tree(
            dataclasses.replace(
                definition,
                members=definition.members[:count] + definition.members[count + 1 :],
            )
        )


def test_same_width_wrong_slice_types() -> None:
    definition = layout._definition(PROFILES[0])
    index = next(
        i
        for i, m in enumerate(definition.members)
        if (m.owner, m.path) == (66, "f_identity.payload")
    )
    with pytest.raises(ValueError, match="expanded member"):
        layout._validate_definition(
            _with_member(
                index, dataclasses.replace(definition.members[index], type_code=19)
            )
        )
    field = definition.field_specs[14][4]
    with pytest.raises(ValueError, match="field inventory"):
        layout._validate_definition(
            _with_field(
                15,
                4,
                dataclasses.replace(
                    field, descriptor=layout.Option(layout.TableSlice(9, "record"))
                ),
            )
        )


@pytest.mark.parametrize(
    "descriptor",
    (
        layout.ExactNumber(True),
        layout.ExactNumber(-1),
        layout.ExactNumber(1 << 64),
        layout.EndFrom("missing"),
        layout.TextSlice("literal"),
        layout.TextSlice("text", ("extra",)),
        layout.TextSlice("literal", ("x", "x")),
        layout.TableSlice(1, "array"),
        layout.TableSlice(48, "record"),
        layout.TableSlice(True, "record"),
        layout.Variant(False, ()),
        layout.Variant(False, (2, 2)),
        layout.Variant(False, (1,)),
        layout.Variant(False, (True,)),
    ),
)
def test_invalid_descriptor_variants(descriptor: layout.Descriptor) -> None:
    field = layout._definition(PROFILES[0]).field_specs[1][0]
    with pytest.raises(ValueError):
        layout._validate_definition(
            _with_field(2, 0, dataclasses.replace(field, descriptor=descriptor))
        )


@pytest.mark.parametrize(
    "kind,value",
    (("text", "invalid"), ("slice", "invalid"), ("variant", 1), ("unknown", None)),
)
def test_invalid_exact_descriptor_types(kind: str, value: object) -> None:
    descriptors: dict[str, layout.Descriptor] = {
        "text": layout.TextSlice("text"),
        "slice": layout.TableSlice(2, "array"),
        "variant": layout.Variant(False, (2,)),
        "unknown": layout.UInt64(),
    }
    descriptor = descriptors[kind]
    if kind == "unknown":
        descriptor = cast(layout.Descriptor, value)
    else:
        object.__setattr__(
            descriptor,
            {"text": "kind", "slice": "mode", "variant": "nullable"}[kind],
            value,
        )
    field = layout._definition(PROFILES[0]).field_specs[1][0]
    with pytest.raises((ValueError, TypeError)):
        layout._validate_definition(
            _with_field(2, 0, dataclasses.replace(field, descriptor=descriptor))
        )


def test_descriptor_object_cycle() -> None:
    descriptor = layout.Option(layout.UInt64())
    object.__setattr__(descriptor, "payload", descriptor)
    field = layout._definition(PROFILES[0]).field_specs[1][0]
    with pytest.raises(ValueError, match="Descriptor cycle"):
        layout._validate_definition(
            _with_field(2, 0, dataclasses.replace(field, descriptor=descriptor))
        )


@pytest.mark.parametrize("indirect", (False, True))
def test_table_descriptor_cycle(indirect: bool) -> None:
    definition = layout._definition(PROFILES[0])
    field = definition.field_specs[1][0]
    changed = _with_field(
        2,
        0,
        dataclasses.replace(
            field, descriptor=layout.TableSlice(3 if indirect else 2, "array")
        ),
    )
    if indirect:
        third = dataclasses.replace(
            definition.field_specs[2][0], descriptor=layout.TableSlice(2, "array")
        )
        changed = dataclasses.replace(
            changed,
            field_specs=(*changed.field_specs[:2], (third,), *changed.field_specs[3:]),
        )
    with pytest.raises(ValueError, match="Table descriptor cycle"):
        layout._validate_definition(changed)


@pytest.mark.parametrize(
    "descriptor,cells",
    (
        (layout.UInt64(), ((0, 8),)),
        (layout.Boolean64(), ((0, 8),)),
        (layout.ExactNumber(2), ((0, 8),)),
        (layout.EndFrom("start"), ((0, 8),)),
        (layout.Signed64(), ((0, 8), (8, 8))),
        (layout.TextSlice("text"), ((0, 4), (4, 4))),
        (layout.TextSlice("digest"), ((0, 4), (4, 4))),
        (layout.TextSlice("witness"), ((0, 4), (4, 4))),
        (layout.TextSlice("literal", ("x",)), ((0, 4), (4, 4))),
        (layout.TableSlice(14, "record"), ((0, 4), (4, 4))),
        (layout.Option(layout.Signed64()), ((0, 8), (8, 8), (16, 8))),
        (layout.Option(layout.TextSlice("text")), ((0, 8), (8, 4), (12, 4))),
        (
            layout.Variant(True, (16, 17, 18)),
            ((0, 8), (8, 4), (12, 4), (16, 4), (20, 4), (24, 4), (28, 4)),
        ),
    ),
)
@given(base=st.integers(min_value=0, max_value=1 << 20))
@settings(max_examples=12, deadline=None)
def test_leaf_cells_with_bounded_bases(
    descriptor: layout.Descriptor, cells: tuple[tuple[int, int], ...], base: int
) -> None:
    assert layout._leaf_cells(descriptor, base) == tuple(
        (base + off, width) for off, width in cells
    )


def _nested_records(value: object) -> Iterator[object]:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        yield value
        for field in dataclasses.fields(value):
            yield from _nested_records(getattr(value, field.name))
    elif isinstance(value, tuple):
        for child in value:
            yield from _nested_records(child)
    else:
        assert type(value) in (str, int, bool)


def test_nested_results_are_immutable() -> None:
    for profile in PROFILES:
        definition = layout._definition(profile)
        for record in _nested_records(definition):
            assert dataclasses.is_dataclass(record) and not isinstance(record, type)
            for field in dataclasses.fields(record):
                with pytest.raises(dataclasses.FrozenInstanceError):
                    setattr(record, field.name, None)
        assert isinstance(layout._expected_witness(definition), tuple)
        assert isinstance(layout._leaf_cells(layout.UInt64(), 0), tuple)


@pytest.mark.parametrize("fault", (RuntimeError, AssertionError, TypeError, ValueError))
def test_programming_faults_remain_visible(
    monkeypatch: pytest.MonkeyPatch, fault: type[Exception]
) -> None:
    def broken(definition: layout.LayoutDefinition) -> tuple[layout.MemberLayout, ...]:
        raise fault("Injected programming fault.")

    monkeypatch.setattr(layout, "_expand_members", broken)
    with pytest.raises(fault, match="Injected programming fault"):
        layout._make_definition(62)


def test_lookup_does_not_revalidate_or_mutate(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(definition: layout.LayoutDefinition) -> None:
        raise AssertionError("Unexpected repeated validation.")

    monkeypatch.setattr(layout, "_validate_definition", broken)
    for profile in PROFILES:
        assert layout._definition(profile).id == profile
    with pytest.raises(ValueError, match="Unknown candidate"):
        layout._definition("submitted-profile")
    with pytest.raises(TypeError, match="exact string"):
        layout._definition(cast(str, 62))


def test_source_imports_are_standard_library_only() -> None:
    source = Path(layout.__file__).read_text()
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imports.append(node.module)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
    assert imports == ["__future__", "dataclasses", "typing"]
    assert not any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id in {"eval", "exec", "compile", "open", "__import__"}
        for n in ast.walk(tree)
    )


def test_actual_import_closure_without_bytecode(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    prefix = tmp_path / "absent-bytecode"
    assert not prefix.exists()
    script = r"""
import builtins, hashlib, importlib, importlib.util, json, pathlib, sys
seen = []
original = builtins.__import__
def checked(name, globals=None, locals=None, fromlist=(), level=0):
    if level:
        name_for_check = importlib.util.resolve_name('.' * level + name,
                                                     globals['__package__'])
    else:
        name_for_check = name
    seen.append(name_for_check)
    root = name_for_check.split('.')[0]
    allowed = {'phoenix', 'phoenix.observe', 'phoenix.observe.collector_layout'}
    if root not in sys.stdlib_module_names and name_for_check not in allowed:
        raise AssertionError('Forbidden import: ' + name)
    if name.split('.')[0] in {'ctypes', 'subprocess', 'socket'}:
        raise AssertionError('Forbidden dependency: ' + name)
    return original(name, globals, locals, fromlist, level)
builtins.__import__ = checked
module = importlib.import_module('phoenix.observe.collector_layout')
for profile in ('linux-x86_64-lp64-le-rela-1', 'linux-aarch64-lp64-le-rela-1'):
    assert len(module._expected_witness(module._definition(profile))) == 5021
closure = {}
for name, loaded in tuple(sys.modules.items()):
    if name == 'phoenix' or name.startswith('phoenix.'):
        path = pathlib.Path(loaded.__file__).resolve()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        closure[name] = {'path': str(path), 'sha256': digest}
print(json.dumps({'closure': closure, 'imports': seen}))
"""
    env = {
        "PYTHONPYCACHEPREFIX": str(prefix),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(root),
        "TMPDIR": str(tmp_path),
    }
    result = subprocess.run(
        [sys.executable, "-B", "-S", "-c", script],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert set(evidence["closure"]) == {
        "phoenix",
        "phoenix.observe",
        "phoenix.observe.collector_layout",
    }
    for name, entry in evidence["closure"].items():
        suffix = (
            "__init__.py"
            if name in {"phoenix", "phoenix.observe"}
            else "collector_layout.py"
        )
        parent = root.joinpath(
            *name.split(".") if suffix == "__init__.py" else name.split(".")[:-1]
        )
        expected = parent / suffix
        assert entry == {
            "path": str(expected),
            "sha256": hashlib.sha256(expected.read_bytes()).hexdigest(),
        }
    assert not prefix.exists()


_EVIDENCE_SOURCES = (
    (
        "docs/checkpoints/2026-11-13-pause/compiled-data-design/design.md",
        "08ce7356c8a54a45b5979db7ced54e08738990fcb00475cdecf8fb87a2cb9bb1",
    ),
    (
        "proposed-layout.json",
        "2afb7057b427333e0c6caea163bb16c513d9432dd1fae57284edb13367f70868",
    ),
)


def test_literal_fixture_provenance() -> None:
    root = Path(__file__).resolve().parents[1]
    path, digest = _EVIDENCE_SOURCES[0]
    assert hashlib.sha256((root / path).read_bytes()).hexdigest() == digest
    original = {
        "status": "proposed-not-Linux-validated",
        "types": [
            dict(zip(("id", "name", "bytes", "alignment"), row, strict=True))
            for row in _types()
        ],
        "members": [
            dict(
                zip(
                    (
                        "id",
                        "owner",
                        "path",
                        "offset",
                        "bytes",
                        "alignment",
                        "type_code",
                        "extent",
                    ),
                    row,
                    strict=True,
                )
            )
            for row in _members()
        ],
        "tables": [
            {"tag": tag, "name": name, "element_type": element}
            for tag, name, element, _, _ in _tables()
        ],
    }
    original_raw = (json.dumps(original, indent=2) + "\n").encode()
    assert hashlib.sha256(original_raw).hexdigest() == _EVIDENCE_SOURCES[1][1]


def test_all_field_leaves_match_literal_members() -> None:
    definition = layout._definition(PROFILES[0])
    members = _members()
    for tag, specs in enumerate(definition.field_specs, 1):
        for spec in specs:
            rows = [
                row
                for row in members
                if row[1] == tag + 51
                and (
                    row[2] == spec.native_name
                    or row[2].startswith(spec.native_name + ".")
                )
            ]
            leaves = [(row[3], row[4]) for row in rows if row[6] in (1, 2, 3, 4)]
            assert layout._leaf_cells(spec.descriptor, spec.offset) == tuple(leaves)


@pytest.mark.parametrize("attribute", ("id", "bytes", "alignment"))
def test_each_type_numeric_mutation(attribute: str) -> None:
    definition = layout._definition(PROFILES[0])
    for index, native_type in enumerate(definition.types):
        changed = dataclasses.replace(
            native_type, **{attribute: getattr(native_type, attribute) + 1}
        )
        with pytest.raises(ValueError):
            layout._validate_definition(
                dataclasses.replace(
                    definition,
                    types=(
                        *definition.types[:index],
                        changed,
                        *definition.types[index + 1 :],
                    ),
                )
            )


@pytest.mark.parametrize("attribute", ("tag", "element_type", "logical_element_bytes"))
def test_each_table_numeric_mutation(attribute: str) -> None:
    definition = layout._definition(PROFILES[0])
    for index, table in enumerate(definition.tables):
        changed = dataclasses.replace(
            table, **{attribute: getattr(table, attribute) + 1}
        )
        with pytest.raises(ValueError):
            layout._validate_definition(
                dataclasses.replace(
                    definition,
                    tables=(
                        *definition.tables[:index],
                        changed,
                        *definition.tables[index + 1 :],
                    ),
                )
            )


@pytest.mark.parametrize("component", ("type", "table", "member", "logical", "native"))
def test_duplicate_names(component: str) -> None:
    definition = layout._definition(PROFILES[0])
    if component == "type":
        rows = definition.types
        changed = dataclasses.replace(
            definition,
            types=(rows[0], dataclasses.replace(rows[1], name=rows[0].name), *rows[2:]),
        )
    elif component == "table":
        tables = definition.tables
        changed = dataclasses.replace(
            definition,
            tables=(
                tables[0],
                dataclasses.replace(tables[1], name=tables[0].name),
                *tables[2:],
            ),
        )
    elif component == "member":
        changed = _with_member(
            1, dataclasses.replace(definition.members[1], path="offset")
        )
    else:
        first, second = definition.field_specs[3]
        field = (
            dataclasses.replace(second, logical_name=first.logical_name)
            if component == "logical"
            else dataclasses.replace(second, native_name=first.native_name)
        )
        changed = _with_field(4, 1, field)
    with pytest.raises(ValueError):
        layout._validate_definition(changed)


@pytest.mark.parametrize("value", (True, 1.0))
def test_exact_integer_types_in_installed_rows(value: object) -> None:
    definition = layout._definition(PROFILES[0])
    number = cast(int, value)
    first = definition.types[0]
    changed = dataclasses.replace(
        definition, types=(dataclasses.replace(first, id=number), *definition.types[1:])
    )
    with pytest.raises(ValueError):
        layout._validate_definition(changed)
    with pytest.raises(ValueError):
        layout._validate_definition(
            _with_member(0, dataclasses.replace(definition.members[0], extent=number))
        )
    with pytest.raises(ValueError):
        layout._validate_definition(
            dataclasses.replace(
                definition,
                tables=(
                    dataclasses.replace(definition.tables[0], tag=number),
                    *definition.tables[1:],
                ),
            )
        )


def test_mutable_nested_inventory_refuses() -> None:
    definition = layout._definition(PROFILES[0])
    changed = dataclasses.replace(definition)
    object.__setattr__(changed, "field_specs", list(definition.field_specs))
    with pytest.raises(ValueError, match="inventory count"):
        layout._validate_definition(changed)
    text = layout.TextSlice("literal", ("value",))
    object.__setattr__(text, "literals", ["value"])
    with pytest.raises(ValueError, match="literals"):
        layout._check_descriptor(text, set())


def test_pure_operations_need_no_external_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import builtins
    import os
    import socket
    import time

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("External operation in the pure layout.")

    with monkeypatch.context() as guard:
        for target, name in (
            (builtins, "open"),
            (os, "getenv"),
            (os, "stat"),
            (time, "time"),
            (time, "monotonic"),
            (socket, "socket"),
            (subprocess, "Popen"),
        ):
            guard.setattr(target, name, forbidden)
        for profile in PROFILES:
            definition = layout._definition(profile)
            assert len(layout._expected_witness(definition)) == 5021
            assert layout._make_definition(definition.machine) == definition
            layout._validate_definition(definition)


_TYPE_EVIDENCE = """
1 uint8_t 1 1
2 uint32_t 4 4
3 uint64_t 8 8
4 const void * 8 8
5 phoenix_bytes_slice_v1 8 4
6 phoenix_uints_slice_v1 8 4
7 phoenix_strings_slice_v1 8 4
8 phoenix_registers_slice_v1 8 4
9 phoenix_plan_gaps_slice_v1 8 4
10 phoenix_positions_slice_v1 8 4
11 phoenix_dispositions_slice_v1 8 4
12 phoenix_dynamic_slice_v1 8 4
13 phoenix_original_slice_v1 8 4
14 phoenix_geometry_slice_v1 8 4
15 phoenix_transport_limits_slice_v1 8 4
16 phoenix_trace_limits_slice_v1 8 4
17 phoenix_capture_limits_slice_v1 8 4
18 phoenix_import_id_slice_v1 8 4
19 phoenix_import_binding_slice_v1 8 4
20 phoenix_call_slice_v1 8 4
21 phoenix_jump_slice_v1 8 4
22 phoenix_return_slice_v1 8 4
23 phoenix_trace_site_slice_v1 8 4
24 phoenix_trace_plan_slice_v1 8 4
25 phoenix_lift_main_slice_v1 8 4
26 phoenix_explicit_entry_slice_v1 8 4
27 phoenix_requested_scope_slice_v1 8 4
28 phoenix_user_slice_v1 8 4
29 phoenix_transit_slice_v1 8 4
30 phoenix_omitted_slice_v1 8 4
31 phoenix_omitted_site_slice_v1 8 4
32 phoenix_transit_route_slice_v1 8 4
33 phoenix_ordinary_slice_v1 8 4
34 phoenix_local_direct_slice_v1 8 4
35 phoenix_local_conditional_slice_v1 8 4
36 phoenix_planned_roles_slice_v1 8 4
37 phoenix_transit_instruction_slice_v1 8 4
38 phoenix_reject_slice_v1 8 4
39 phoenix_guard_instruction_slice_v1 8 4
40 phoenix_dormant_outside_window_slice_v1 8 4
41 phoenix_guard_reject_slice_v1 8 4
42 phoenix_local_branch_guard_slice_v1 8 4
43 phoenix_metadata_only_slice_v1 8 4
44 phoenix_gap_record_slice_v1 8 4
45 phoenix_exit_from_supported_bits_slice_v1 8 4
46 phoenix_exact_signal_slice_v1 8 4
47 phoenix_termination_contract_slice_v1 8 4
48 phoenix_scope_selection_slice_v1 8 4
49 phoenix_load_segment_slice_v1 8 4
50 phoenix_elf_image_slice_v1 8 4
51 phoenix_collector_data_slice_v1 8 4
52 phoenix_signed_v1 16 8
53 phoenix_uints_v1 8 8
54 phoenix_strings_v1 8 4
55 phoenix_registers_v1 16 8
56 phoenix_plan_gaps_v1 16 8
57 phoenix_positions_v1 16 8
58 phoenix_dispositions_v1 40 8
59 phoenix_dynamic_v1 24 8
60 phoenix_original_v1 16 8
61 phoenix_geometry_v1 32 8
62 phoenix_transport_limits_v1 88 8
63 phoenix_trace_limits_v1 48 8
64 phoenix_capture_limits_v1 112 8
65 phoenix_import_id_v1 48 8
66 phoenix_import_binding_v1 152 8
67 phoenix_call_v1 40 8
68 phoenix_jump_v1 8 4
69 phoenix_return_v1 8 4
70 phoenix_trace_site_v1 72 8
71 phoenix_trace_plan_v1 72 8
72 phoenix_lift_main_v1 24 8
73 phoenix_explicit_entry_v1 16 4
74 phoenix_requested_scope_v1 48 8
75 phoenix_user_v1 16 8
76 phoenix_transit_v1 16 4
77 phoenix_omitted_v1 16 4
78 phoenix_omitted_site_v1 40 8
79 phoenix_transit_route_v1 56 8
80 phoenix_ordinary_v1 16 8
81 phoenix_local_direct_v1 16 8
82 phoenix_local_conditional_v1 24 8
83 phoenix_planned_roles_v1 48 8
84 phoenix_transit_instruction_v1 16 4
85 phoenix_reject_v1 16 4
86 phoenix_guard_instruction_v1 88 8
87 phoenix_dormant_outside_window_v1 16 4
88 phoenix_guard_reject_v1 16 4
89 phoenix_local_branch_guard_v1 40 8
90 phoenix_metadata_only_v1 16 4
91 phoenix_gap_record_v1 88 8
92 phoenix_exit_from_supported_bits_v1 24 8
93 phoenix_exact_signal_v1 8 8
94 phoenix_termination_contract_v1 128 8
95 phoenix_scope_selection_v1 184 8
96 phoenix_load_segment_v1 56 8
97 phoenix_elf_image_v1 32 8
98 phoenix_collector_data_v1 112 4
99 phoenix_table_directory_entry_v1 56 8
100 phoenix_data_directory_v1 2728 8
"""

_MEMBER_EVIDENCE = """
1 5 offset 0 4 4 2 1
2 5 count 4 4 4 2 1
3 6 offset 0 4 4 2 1
4 6 count 4 4 4 2 1
5 7 offset 0 4 4 2 1
6 7 count 4 4 4 2 1
7 8 offset 0 4 4 2 1
8 8 count 4 4 4 2 1
9 9 offset 0 4 4 2 1
10 9 count 4 4 4 2 1
11 10 offset 0 4 4 2 1
12 10 count 4 4 4 2 1
13 11 offset 0 4 4 2 1
14 11 count 4 4 4 2 1
15 12 offset 0 4 4 2 1
16 12 count 4 4 4 2 1
17 13 offset 0 4 4 2 1
18 13 count 4 4 4 2 1
19 14 offset 0 4 4 2 1
20 14 count 4 4 4 2 1
21 15 offset 0 4 4 2 1
22 15 count 4 4 4 2 1
23 16 offset 0 4 4 2 1
24 16 count 4 4 4 2 1
25 17 offset 0 4 4 2 1
26 17 count 4 4 4 2 1
27 18 offset 0 4 4 2 1
28 18 count 4 4 4 2 1
29 19 offset 0 4 4 2 1
30 19 count 4 4 4 2 1
31 20 offset 0 4 4 2 1
32 20 count 4 4 4 2 1
33 21 offset 0 4 4 2 1
34 21 count 4 4 4 2 1
35 22 offset 0 4 4 2 1
36 22 count 4 4 4 2 1
37 23 offset 0 4 4 2 1
38 23 count 4 4 4 2 1
39 24 offset 0 4 4 2 1
40 24 count 4 4 4 2 1
41 25 offset 0 4 4 2 1
42 25 count 4 4 4 2 1
43 26 offset 0 4 4 2 1
44 26 count 4 4 4 2 1
45 27 offset 0 4 4 2 1
46 27 count 4 4 4 2 1
47 28 offset 0 4 4 2 1
48 28 count 4 4 4 2 1
49 29 offset 0 4 4 2 1
50 29 count 4 4 4 2 1
51 30 offset 0 4 4 2 1
52 30 count 4 4 4 2 1
53 31 offset 0 4 4 2 1
54 31 count 4 4 4 2 1
55 32 offset 0 4 4 2 1
56 32 count 4 4 4 2 1
57 33 offset 0 4 4 2 1
58 33 count 4 4 4 2 1
59 34 offset 0 4 4 2 1
60 34 count 4 4 4 2 1
61 35 offset 0 4 4 2 1
62 35 count 4 4 4 2 1
63 36 offset 0 4 4 2 1
64 36 count 4 4 4 2 1
65 37 offset 0 4 4 2 1
66 37 count 4 4 4 2 1
67 38 offset 0 4 4 2 1
68 38 count 4 4 4 2 1
69 39 offset 0 4 4 2 1
70 39 count 4 4 4 2 1
71 40 offset 0 4 4 2 1
72 40 count 4 4 4 2 1
73 41 offset 0 4 4 2 1
74 41 count 4 4 4 2 1
75 42 offset 0 4 4 2 1
76 42 count 4 4 4 2 1
77 43 offset 0 4 4 2 1
78 43 count 4 4 4 2 1
79 44 offset 0 4 4 2 1
80 44 count 4 4 4 2 1
81 45 offset 0 4 4 2 1
82 45 count 4 4 4 2 1
83 46 offset 0 4 4 2 1
84 46 count 4 4 4 2 1
85 47 offset 0 4 4 2 1
86 47 count 4 4 4 2 1
87 48 offset 0 4 4 2 1
88 48 count 4 4 4 2 1
89 49 offset 0 4 4 2 1
90 49 count 4 4 4 2 1
91 50 offset 0 4 4 2 1
92 50 count 4 4 4 2 1
93 51 offset 0 4 4 2 1
94 51 count 4 4 4 2 1
95 52 negative 0 8 8 3 1
96 52 magnitude 8 8 8 3 1
97 53 f_value 0 8 8 3 1
98 54 f_value 0 8 4 5 1
99 54 f_value.offset 0 4 4 2 1
100 54 f_value.count 4 4 4 2 1
101 55 f_name 0 8 4 5 1
102 55 f_name.offset 0 4 4 2 1
103 55 f_name.count 4 4 4 2 1
104 55 f_width 8 8 8 3 1
105 56 f_address 0 8 8 3 1
106 56 f_reason 8 8 4 5 1
107 56 f_reason.offset 8 4 4 2 1
108 56 f_reason.count 12 4 4 2 1
109 57 f_route_sha256 0 8 4 5 1
110 57 f_route_sha256.offset 0 4 4 2 1
111 57 f_route_sha256.count 4 4 4 2 1
112 57 f_position 8 8 8 3 1
113 58 f_address 0 8 8 3 1
114 58 f_disposition 8 32 8 0 1
115 58 f_disposition.tag 8 8 8 3 1
116 58 f_disposition.payload_user 16 8 4 28 1
117 58 f_disposition.payload_user.offset 16 4 4 2 1
118 58 f_disposition.payload_user.count 20 4 4 2 1
119 58 f_disposition.payload_transit 24 8 4 29 1
120 58 f_disposition.payload_transit.offset 24 4 4 2 1
121 58 f_disposition.payload_transit.count 28 4 4 2 1
122 58 f_disposition.payload_omitted 32 8 4 30 1
123 58 f_disposition.payload_omitted.offset 32 4 4 2 1
124 58 f_disposition.payload_omitted.count 36 4 4 2 1
125 59 f_tag 0 16 8 52 1
126 59 f_tag.negative 0 8 8 3 1
127 59 f_tag.magnitude 8 8 8 3 1
128 59 f_value 16 8 8 3 1
129 60 f_bytes 0 8 8 3 1
130 60 f_sha256 8 8 4 5 1
131 60 f_sha256.offset 8 4 4 2 1
132 60 f_sha256.count 12 4 4 2 1
133 61 f_executable_file_start 0 8 8 3 1
134 61 f_executable_file_size 8 8 8 3 1
135 61 f_load_memory_start 16 8 8 3 1
136 61 f_load_memory_size 24 8 8 3 1
137 62 f_data_bytes 0 8 8 3 1
138 62 f_elf_segments 8 8 8 3 1
139 62 f_gap_records 16 8 8 3 1
140 62 f_lift_bytes 24 8 8 3 1
141 62 f_mapping_bytes 32 8 8 3 1
142 62 f_omissions 40 8 8 3 1
143 62 f_original_bytes 48 8 8 3 1
144 62 f_route_memberships 56 8 8 3 1
145 62 f_route_path_positions 64 8 8 3 1
146 62 f_routes 72 8 8 3 1
147 62 f_users 80 8 8 3 1
148 63 f_events 0 8 8 3 1
149 63 f_execution_callbacks 8 8 8 3 1
150 63 f_frames 16 8 8 3 1
151 63 f_snapshot_bytes 24 8 8 3 1
152 63 f_translated_instructions 32 8 8 3 1
153 63 f_wire_bytes 40 8 8 3 1
154 64 f_events 0 8 8 3 1
155 64 f_execution_callbacks 8 8 8 3 1
156 64 f_frames 16 8 8 3 1
157 64 f_full_plan_bytes 24 8 8 3 1
158 64 f_full_plan_sites 32 8 8 3 1
159 64 f_guarded_instructions 40 8 8 3 1
160 64 f_receipt_bytes 48 8 8 3 1
161 64 f_route_entries 56 8 8 3 1
162 64 f_scope_bytes 64 8 8 3 1
163 64 f_snapshot_bytes 72 8 8 3 1
164 64 f_thunk_neutral_bytes 80 8 8 3 1
165 64 f_thunk_neutral_instructions 88 8 8 3 1
166 64 f_translated_instructions 96 8 8 3 1
167 64 f_wire_bytes 104 8 8 3 1
168 65 f_needed_library 0 16 8 0 1
169 65 f_needed_library.tag 0 8 8 3 1
170 65 f_needed_library.payload 8 8 4 5 1
171 65 f_needed_library.payload.offset 8 4 4 2 1
172 65 f_needed_library.payload.count 12 4 4 2 1
173 65 f_symbol 16 8 4 5 1
174 65 f_symbol.offset 16 4 4 2 1
175 65 f_symbol.count 20 4 4 2 1
176 65 f_version 24 16 8 0 1
177 65 f_version.tag 24 8 8 3 1
178 65 f_version.payload 32 8 4 5 1
179 65 f_version.payload.offset 32 4 4 2 1
180 65 f_version.payload.count 36 4 4 2 1
181 65 f_version_hidden 40 8 8 3 1
182 66 f_address_proof_sha256 0 8 4 5 1
183 66 f_address_proof_sha256.offset 0 4 4 2 1
184 66 f_address_proof_sha256.count 4 4 4 2 1
185 66 f_binary_sha256 8 8 4 5 1
186 66 f_binary_sha256.offset 8 4 4 2 1
187 66 f_binary_sha256.count 12 4 4 2 1
188 66 f_function 16 16 8 0 1
189 66 f_function.tag 16 8 8 3 1
190 66 f_function.payload 24 8 8 3 1
191 66 f_gap 32 16 8 0 1
192 66 f_gap.tag 32 8 8 3 1
193 66 f_gap.payload 40 8 4 5 1
194 66 f_gap.payload.offset 40 4 4 2 1
195 66 f_gap.payload.count 44 4 4 2 1
196 66 f_identity 48 16 8 0 1
197 66 f_identity.tag 48 8 8 3 1
198 66 f_identity.payload 56 8 4 18 1
199 66 f_identity.payload.offset 56 4 4 2 1
200 66 f_identity.payload.count 60 4 4 2 1
201 66 f_lift_sha256 64 8 4 5 1
202 66 f_lift_sha256.offset 64 4 4 2 1
203 66 f_lift_sha256.count 68 4 4 2 1
204 66 f_relocation_file_offset 72 16 8 0 1
205 66 f_relocation_file_offset.tag 72 8 8 3 1
206 66 f_relocation_file_offset.payload 80 8 8 3 1
207 66 f_relocation_kind 88 16 8 0 1
208 66 f_relocation_kind.tag 88 8 8 3 1
209 66 f_relocation_kind.payload 96 8 8 3 1
210 66 f_relocation_slot 104 16 8 0 1
211 66 f_relocation_slot.tag 104 8 8 3 1
212 66 f_relocation_slot.payload 112 8 8 3 1
213 66 f_site 120 8 8 3 1
214 66 f_symbol_index 128 16 8 0 1
215 66 f_symbol_index.tag 128 8 8 3 1
216 66 f_symbol_index.payload 136 8 8 3 1
217 66 f_thunk_path 144 8 4 6 1
218 66 f_thunk_path.offset 144 4 4 2 1
219 66 f_thunk_path.count 148 4 4 2 1
220 67 f_continuation 0 8 8 3 1
221 67 f_import_gaps 8 8 4 7 1
222 67 f_import_gaps.offset 8 4 4 2 1
223 67 f_import_gaps.count 12 4 4 2 1
224 67 f_imported 16 16 8 0 1
225 67 f_imported.tag 16 8 8 3 1
226 67 f_imported.payload 24 8 4 19 1
227 67 f_imported.payload.offset 24 4 4 2 1
228 67 f_imported.payload.count 28 4 4 2 1
229 67 f_kind 32 8 4 5 1
230 67 f_kind.offset 32 4 4 2 1
231 67 f_kind.count 36 4 4 2 1
232 68 f_kind 0 8 4 5 1
233 68 f_kind.offset 0 4 4 2 1
234 68 f_kind.count 4 4 4 2 1
235 69 f_kind 0 8 4 5 1
236 69 f_kind.offset 0 4 4 2 1
237 69 f_kind.count 4 4 4 2 1
238 70 f_address 0 8 8 3 1
239 70 f_continuation_of 8 8 4 6 1
240 70 f_continuation_of.offset 8 4 4 2 1
241 70 f_continuation_of.count 12 4 4 2 1
242 70 f_entry 16 8 8 3 1
243 70 f_owner 24 8 8 3 1
244 70 f_transfer 32 32 8 0 1
245 70 f_transfer.tag 32 8 8 3 1
246 70 f_transfer.payload_call 40 8 4 20 1
247 70 f_transfer.payload_call.offset 40 4 4 2 1
248 70 f_transfer.payload_call.count 44 4 4 2 1
249 70 f_transfer.payload_jump 48 8 4 21 1
250 70 f_transfer.payload_jump.offset 48 4 4 2 1
251 70 f_transfer.payload_jump.count 52 4 4 2 1
252 70 f_transfer.payload_return 56 8 4 22 1
253 70 f_transfer.payload_return.offset 56 4 4 2 1
254 70 f_transfer.payload_return.count 60 4 4 2 1
255 70 f_witness_hex 64 8 4 5 1
256 70 f_witness_hex.offset 64 4 4 2 1
257 70 f_witness_hex.count 68 4 4 2 1
258 71 f_address_proof_sha256 0 8 4 5 1
259 71 f_address_proof_sha256.offset 0 4 4 2 1
260 71 f_address_proof_sha256.count 4 4 4 2 1
261 71 f_binary_sha256 8 8 4 5 1
262 71 f_binary_sha256.offset 8 4 4 2 1
263 71 f_binary_sha256.count 12 4 4 2 1
264 71 f_gaps 16 8 4 9 1
265 71 f_gaps.offset 16 4 4 2 1
266 71 f_gaps.count 20 4 4 2 1
267 71 f_lift_sha256 24 8 4 5 1
268 71 f_lift_sha256.offset 24 4 4 2 1
269 71 f_lift_sha256.count 28 4 4 2 1
270 71 f_limits 32 8 4 16 1
271 71 f_limits.offset 32 4 4 2 1
272 71 f_limits.count 36 4 4 2 1
273 71 f_registers 40 8 4 8 1
274 71 f_registers.offset 40 4 4 2 1
275 71 f_registers.count 44 4 4 2 1
276 71 f_schema 48 8 8 3 1
277 71 f_scope 56 8 4 6 1
278 71 f_scope.offset 56 4 4 2 1
279 71 f_scope.count 60 4 4 2 1
280 71 f_sites 64 8 4 23 1
281 71 f_sites.offset 64 4 4 2 1
282 71 f_sites.count 68 4 4 2 1
283 72 f_kind 0 8 4 5 1
284 72 f_kind.offset 0 4 4 2 1
285 72 f_kind.count 4 4 4 2 1
286 72 f_lift_sha256 8 8 4 5 1
287 72 f_lift_sha256.offset 8 4 4 2 1
288 72 f_lift_sha256.count 12 4 4 2 1
289 72 f_main_elf 16 8 8 3 1
290 73 f_kind 0 8 4 5 1
291 73 f_kind.offset 0 4 4 2 1
292 73 f_kind.count 4 4 4 2 1
293 73 f_request_sha256 8 8 4 5 1
294 73 f_request_sha256.offset 8 4 4 2 1
295 73 f_request_sha256.count 12 4 4 2 1
296 74 f_policy 0 8 4 5 1
297 74 f_policy.offset 0 4 4 2 1
298 74 f_policy.count 4 4 4 2 1
299 74 f_root 8 8 8 3 1
300 74 f_root_evidence 16 24 8 0 1
301 74 f_root_evidence.tag 16 8 8 3 1
302 74 f_root_evidence.payload_lift_main 24 8 4 25 1
303 74 f_root_evidence.payload_lift_main.offset 24 4 4 2 1
304 74 f_root_evidence.payload_lift_main.count 28 4 4 2 1
305 74 f_root_evidence.payload_explicit_entry 32 8 4 26 1
306 74 f_root_evidence.payload_explicit_entry.offset 32 4 4 2 1
307 74 f_root_evidence.payload_explicit_entry.count 36 4 4 2 1
308 74 f_users 40 8 4 6 1
309 74 f_users.offset 40 4 4 2 1
310 74 f_users.count 44 4 4 2 1
311 75 f_kind 0 8 4 5 1
312 75 f_kind.offset 0 4 4 2 1
313 75 f_kind.count 4 4 4 2 1
314 75 f_owner 8 8 8 3 1
315 76 f_kind 0 8 4 5 1
316 76 f_kind.offset 0 4 4 2 1
317 76 f_kind.count 4 4 4 2 1
318 76 f_route_ids 8 8 4 7 1
319 76 f_route_ids.offset 8 4 4 2 1
320 76 f_route_ids.count 12 4 4 2 1
321 77 f_kind 0 8 4 5 1
322 77 f_kind.offset 0 4 4 2 1
323 77 f_kind.count 4 4 4 2 1
324 77 f_reason 8 8 4 5 1
325 77 f_reason.offset 8 4 4 2 1
326 77 f_reason.count 12 4 4 2 1
327 78 f_address 0 8 8 3 1
328 78 f_full_roles 8 8 4 7 1
329 78 f_full_roles.offset 8 4 4 2 1
330 78 f_full_roles.count 12 4 4 2 1
331 78 f_owner 16 8 8 3 1
332 78 f_reason 24 8 4 5 1
333 78 f_reason.offset 24 4 4 2 1
334 78 f_reason.count 28 4 4 2 1
335 78 f_witness_sha256 32 8 4 5 1
336 78 f_witness_sha256.offset 32 4 4 2 1
337 78 f_witness_sha256.count 36 4 4 2 1
338 79 f_binding_sha256 0 8 4 5 1
339 79 f_binding_sha256.offset 0 4 4 2 1
340 79 f_binding_sha256.count 4 4 4 2 1
341 79 f_call_site 8 8 8 3 1
342 79 f_entries 16 8 4 6 1
343 79 f_entries.offset 16 4 4 2 1
344 79 f_entries.count 20 4 4 2 1
345 79 f_instruction_path 24 8 4 6 1
346 79 f_instruction_path.offset 24 4 4 2 1
347 79 f_instruction_path.count 28 4 4 2 1
348 79 f_request 32 8 4 18 1
349 79 f_request.offset 32 4 4 2 1
350 79 f_request.count 36 4 4 2 1
351 79 f_slot 40 8 8 3 1
352 79 f_terminal 48 8 8 3 1
353 80 f_kind 0 8 4 5 1
354 80 f_kind.offset 0 4 4 2 1
355 80 f_kind.count 4 4 4 2 1
356 80 f_successor 8 8 8 3 1
357 81 f_destination 0 8 8 3 1
358 81 f_kind 8 8 4 5 1
359 81 f_kind.offset 8 4 4 2 1
360 81 f_kind.count 12 4 4 2 1
361 82 f_fallthrough 0 8 8 3 1
362 82 f_kind 8 8 4 5 1
363 82 f_kind.offset 8 4 4 2 1
364 82 f_kind.count 12 4 4 2 1
365 82 f_taken 16 8 8 3 1
366 83 f_continuation 0 16 8 0 1
367 83 f_continuation.tag 0 8 8 3 1
368 83 f_continuation.payload 8 8 8 3 1
369 83 f_destination 16 16 8 0 1
370 83 f_destination.tag 16 8 8 3 1
371 83 f_destination.payload 24 8 8 3 1
372 83 f_kind 32 8 4 5 1
373 83 f_kind.offset 32 4 4 2 1
374 83 f_kind.count 36 4 4 2 1
375 83 f_transfer_kind 40 8 4 5 1
376 83 f_transfer_kind.offset 40 4 4 2 1
377 83 f_transfer_kind.count 44 4 4 2 1
378 84 f_kind 0 8 4 5 1
379 84 f_kind.offset 0 4 4 2 1
380 84 f_kind.count 4 4 4 2 1
381 84 f_positions 8 8 4 10 1
382 84 f_positions.offset 8 4 4 2 1
383 84 f_positions.count 12 4 4 2 1
384 85 f_kind 0 8 4 5 1
385 85 f_kind.offset 0 4 4 2 1
386 85 f_kind.count 4 4 4 2 1
387 85 f_reason 8 8 4 5 1
388 85 f_reason.offset 8 4 4 2 1
389 85 f_reason.count 12 4 4 2 1
390 86 f_address 0 8 8 3 1
391 86 f_full_roles 8 8 4 7 1
392 86 f_full_roles.offset 8 4 4 2 1
393 86 f_full_roles.count 12 4 4 2 1
394 86 f_owner 16 8 8 3 1
395 86 f_rule 24 56 8 0 1
396 86 f_rule.tag 24 8 8 3 1
397 86 f_rule.payload_ordinary 32 8 4 33 1
398 86 f_rule.payload_ordinary.offset 32 4 4 2 1
399 86 f_rule.payload_ordinary.count 36 4 4 2 1
400 86 f_rule.payload_local_direct 40 8 4 34 1
401 86 f_rule.payload_local_direct.offset 40 4 4 2 1
402 86 f_rule.payload_local_direct.count 44 4 4 2 1
403 86 f_rule.payload_local_conditional 48 8 4 35 1
404 86 f_rule.payload_local_conditional.offset 48 4 4 2 1
405 86 f_rule.payload_local_conditional.count 52 4 4 2 1
406 86 f_rule.payload_planned_roles 56 8 4 36 1
407 86 f_rule.payload_planned_roles.offset 56 4 4 2 1
408 86 f_rule.payload_planned_roles.count 60 4 4 2 1
409 86 f_rule.payload_transit_instruction 64 8 4 37 1
410 86 f_rule.payload_transit_instruction.offset 64 4 4 2 1
411 86 f_rule.payload_transit_instruction.count 68 4 4 2 1
412 86 f_rule.payload_reject 72 8 4 38 1
413 86 f_rule.payload_reject.offset 72 4 4 2 1
414 86 f_rule.payload_reject.count 76 4 4 2 1
415 86 f_witness_hex 80 8 4 5 1
416 86 f_witness_hex.offset 80 4 4 2 1
417 86 f_witness_hex.count 84 4 4 2 1
418 87 f_kind 0 8 4 5 1
419 87 f_kind.offset 0 4 4 2 1
420 87 f_kind.count 4 4 4 2 1
421 87 f_reason 8 8 4 5 1
422 87 f_reason.offset 8 4 4 2 1
423 87 f_reason.count 12 4 4 2 1
424 88 f_kind 0 8 4 5 1
425 88 f_kind.offset 0 4 4 2 1
426 88 f_kind.count 4 4 4 2 1
427 88 f_reason 8 8 4 5 1
428 88 f_reason.offset 8 4 4 2 1
429 88 f_reason.count 12 4 4 2 1
430 89 f_destination 0 8 8 3 1
431 89 f_fallthrough 8 16 8 0 1
432 89 f_fallthrough.tag 8 8 8 3 1
433 89 f_fallthrough.payload 16 8 8 3 1
434 89 f_kind 24 8 4 5 1
435 89 f_kind.offset 24 4 4 2 1
436 89 f_kind.count 28 4 4 2 1
437 89 f_rule 32 8 4 5 1
438 89 f_rule.offset 32 4 4 2 1
439 89 f_rule.count 36 4 4 2 1
440 90 f_kind 0 8 4 5 1
441 90 f_kind.offset 0 4 4 2 1
442 90 f_kind.count 4 4 4 2 1
443 90 f_reason 8 8 4 5 1
444 90 f_reason.offset 8 4 4 2 1
445 90 f_reason.count 12 4 4 2 1
446 91 f_address 0 8 8 3 1
447 91 f_disposition 8 40 8 0 1
448 91 f_disposition.tag 8 8 8 3 1
449 91 f_disposition.payload_dormant_outside_window 16 8 4 40 1
450 91 f_disposition.payload_dormant_outside_window.offset 16 4 4 2 1
451 91 f_disposition.payload_dormant_outside_window.count 20 4 4 2 1
452 91 f_disposition.payload_guard_reject 24 8 4 41 1
453 91 f_disposition.payload_guard_reject.offset 24 4 4 2 1
454 91 f_disposition.payload_guard_reject.count 28 4 4 2 1
455 91 f_disposition.payload_local_branch_guard 32 8 4 42 1
456 91 f_disposition.payload_local_branch_guard.offset 32 4 4 2 1
457 91 f_disposition.payload_local_branch_guard.count 36 4 4 2 1
458 91 f_disposition.payload_metadata_only 40 8 4 43 1
459 91 f_disposition.payload_metadata_only.offset 40 4 4 2 1
460 91 f_disposition.payload_metadata_only.count 44 4 4 2 1
461 91 f_domain 48 8 4 5 1
462 91 f_domain.offset 48 4 4 2 1
463 91 f_domain.count 52 4 4 2 1
464 91 f_elf 56 16 8 0 1
465 91 f_elf.tag 56 8 8 3 1
466 91 f_elf.payload 64 8 8 3 1
467 91 f_index 72 8 8 3 1
468 91 f_reason 80 8 4 5 1
469 91 f_reason.offset 80 4 4 2 1
470 91 f_reason.count 84 4 4 2 1
471 92 f_register 0 8 4 5 1
472 92 f_register.offset 0 4 4 2 1
473 92 f_register.count 4 4 4 2 1
474 92 f_transform 8 8 4 5 1
475 92 f_transform.offset 8 4 4 2 1
476 92 f_transform.count 12 4 4 2 1
477 92 f_width 16 8 8 3 1
478 93 f_signal 0 8 8 3 1
479 94 f_behavior 0 8 4 5 1
480 94 f_behavior.offset 0 4 4 2 1
481 94 f_behavior.count 4 4 4 2 1
482 94 f_binary_sha256 8 8 4 5 1
483 94 f_binary_sha256.offset 8 4 4 2 1
484 94 f_binary_sha256.count 12 4 4 2 1
485 94 f_call_site 16 8 8 3 1
486 94 f_callbacks 24 8 4 5 1
487 94 f_callbacks.offset 24 4 4 2 1
488 94 f_callbacks.count 28 4 4 2 1
489 94 f_cleanup 32 8 4 5 1
490 94 f_cleanup.offset 32 4 4 2 1
491 94 f_cleanup.count 36 4 4 2 1
492 94 f_full_plan_sha256 40 8 4 5 1
493 94 f_full_plan_sha256.offset 40 4 4 2 1
494 94 f_full_plan_sha256.count 44 4 4 2 1
495 94 f_import_binding_sha256 48 16 8 0 1
496 94 f_import_binding_sha256.tag 48 8 8 3 1
497 94 f_import_binding_sha256.payload 56 8 4 5 1
498 94 f_import_binding_sha256.payload.offset 56 4 4 2 1
499 94 f_import_binding_sha256.payload.count 60 4 4 2 1
500 94 f_permitted_physical_route_sha256 64 8 4 5 1
501 94 f_permitted_physical_route_sha256.offset 64 4 4 2 1
502 94 f_permitted_physical_route_sha256.count 68 4 4 2 1
503 94 f_provider_evidence_sha256 72 8 4 5 1
504 94 f_provider_evidence_sha256.offset 72 4 4 2 1
505 94 f_provider_evidence_sha256.count 76 4 4 2 1
506 94 f_rule_sha256 80 8 4 5 1
507 94 f_rule_sha256.offset 80 4 4 2 1
508 94 f_rule_sha256.count 84 4 4 2 1
509 94 f_runtime_manifest_base_sha256 88 8 4 5 1
510 94 f_runtime_manifest_base_sha256.offset 88 4 4 2 1
511 94 f_runtime_manifest_base_sha256.count 92 4 4 2 1
512 94 f_schema 96 8 8 3 1
513 94 f_termination_rule 104 24 8 0 1
514 94 f_termination_rule.tag 104 8 8 3 1
515 94 f_termination_rule.payload_exit_from_supported_bits 112 8 4 45 1
516 94 f_termination_rule.payload_exit_from_supported_bits.offset 112 4 4 2 1
517 94 f_termination_rule.payload_exit_from_supported_bits.count 116 4 4 2 1
518 94 f_termination_rule.payload_exact_signal 120 8 4 46 1
519 94 f_termination_rule.payload_exact_signal.offset 120 4 4 2 1
520 94 f_termination_rule.payload_exact_signal.count 124 4 4 2 1
521 95 f_active_unlisted 0 8 4 5 1
522 95 f_active_unlisted.offset 0 4 4 2 1
523 95 f_active_unlisted.count 4 4 4 2 1
524 95 f_address_proof_sha256 8 8 4 5 1
525 95 f_address_proof_sha256.offset 8 4 4 2 1
526 95 f_address_proof_sha256.count 12 4 4 2 1
527 95 f_binary_sha256 16 8 4 5 1
528 95 f_binary_sha256.offset 16 4 4 2 1
529 95 f_binary_sha256.count 20 4 4 2 1
530 95 f_claim 24 8 4 5 1
531 95 f_claim.offset 24 4 4 2 1
532 95 f_claim.count 28 4 4 2 1
533 95 f_contracts 32 8 4 47 1
534 95 f_contracts.offset 32 4 4 2 1
535 95 f_contracts.count 36 4 4 2 1
536 95 f_dispositions 40 8 4 11 1
537 95 f_dispositions.offset 40 4 4 2 1
538 95 f_dispositions.count 44 4 4 2 1
539 95 f_full_plan_sha256 48 8 4 5 1
540 95 f_full_plan_sha256.offset 48 4 4 2 1
541 95 f_full_plan_sha256.count 52 4 4 2 1
542 95 f_gap_dispositions 56 8 4 44 1
543 95 f_gap_dispositions.offset 56 4 4 2 1
544 95 f_gap_dispositions.count 60 4 4 2 1
545 95 f_guard_instructions 64 8 4 39 1
546 95 f_guard_instructions.offset 64 4 4 2 1
547 95 f_guard_instructions.count 68 4 4 2 1
548 95 f_lazy_resolver 72 8 4 5 1
549 95 f_lazy_resolver.offset 72 4 4 2 1
550 95 f_lazy_resolver.count 76 4 4 2 1
551 95 f_lift_sha256 80 8 4 5 1
552 95 f_lift_sha256.offset 80 4 4 2 1
553 95 f_lift_sha256.count 84 4 4 2 1
554 95 f_limits 88 8 4 17 1
555 95 f_limits.offset 88 4 4 2 1
556 95 f_limits.count 92 4 4 2 1
557 95 f_omitted 96 8 4 31 1
558 95 f_omitted.offset 96 4 4 2 1
559 95 f_omitted.count 100 4 4 2 1
560 95 f_outside_window 104 8 4 5 1
561 95 f_outside_window.offset 104 4 4 2 1
562 95 f_outside_window.count 108 4 4 2 1
563 95 f_policy 112 8 4 5 1
564 95 f_policy.offset 112 4 4 2 1
565 95 f_policy.count 116 4 4 2 1
566 95 f_policy_implementation_sha256 120 8 4 5 1
567 95 f_policy_implementation_sha256.offset 120 4 4 2 1
568 95 f_policy_implementation_sha256.count 124 4 4 2 1
569 95 f_registers 128 8 4 8 1
570 95 f_registers.offset 128 4 4 2 1
571 95 f_registers.count 132 4 4 2 1
572 95 f_request 136 8 4 27 1
573 95 f_request.offset 136 4 4 2 1
574 95 f_request.count 140 4 4 2 1
575 95 f_root 144 8 8 3 1
576 95 f_routes 152 8 4 32 1
577 95 f_routes.offset 152 4 4 2 1
578 95 f_routes.count 156 4 4 2 1
579 95 f_schema 160 8 8 3 1
580 95 f_transit_profile 168 8 4 5 1
581 95 f_transit_profile.offset 168 4 4 2 1
582 95 f_transit_profile.count 172 4 4 2 1
583 95 f_users 176 8 4 6 1
584 95 f_users.offset 176 4 4 2 1
585 95 f_users.count 180 4 4 2 1
586 96 f_alignment 0 8 8 3 1
587 96 f_file_offset 8 8 8 3 1
588 96 f_file_size 16 8 8 3 1
589 96 f_flags 24 8 8 3 1
590 96 f_index 32 8 8 3 1
591 96 f_memory_size 40 8 8 3 1
592 96 f_va 48 8 8 3 1
593 97 f_dynamic 0 8 4 12 1
594 97 f_dynamic.offset 0 4 4 2 1
595 97 f_dynamic.count 4 4 4 2 1
596 97 f_entry 8 8 8 3 1
597 97 f_kind 16 8 8 3 1
598 97 f_segments 24 8 4 49 1
599 97 f_segments.offset 24 4 4 2 1
600 97 f_segments.count 28 4 4 2 1
601 98 f_address_proof_sha256 0 8 4 5 1
602 98 f_address_proof_sha256.offset 0 4 4 2 1
603 98 f_address_proof_sha256.count 4 4 4 2 1
604 98 f_c_data_schema 8 8 4 5 1
605 98 f_c_data_schema.offset 8 4 4 2 1
606 98 f_c_data_schema.count 12 4 4 2 1
607 98 f_full_plan 16 8 4 24 1
608 98 f_full_plan.offset 16 4 4 2 1
609 98 f_full_plan.count 20 4 4 2 1
610 98 f_full_plan_sha256 24 8 4 5 1
611 98 f_full_plan_sha256.offset 24 4 4 2 1
612 98 f_full_plan_sha256.count 28 4 4 2 1
613 98 f_geometry 32 8 4 14 1
614 98 f_geometry.offset 32 4 4 2 1
615 98 f_geometry.count 36 4 4 2 1
616 98 f_image 40 8 4 50 1
617 98 f_image.offset 40 4 4 2 1
618 98 f_image.count 44 4 4 2 1
619 98 f_lift_sha256 48 8 4 5 1
620 98 f_lift_sha256.offset 48 4 4 2 1
621 98 f_lift_sha256.count 52 4 4 2 1
622 98 f_original 56 8 4 13 1
623 98 f_original.offset 56 4 4 2 1
624 98 f_original.count 60 4 4 2 1
625 98 f_policy_implementation_sha256 64 8 4 5 1
626 98 f_policy_implementation_sha256.offset 64 4 4 2 1
627 98 f_policy_implementation_sha256.count 68 4 4 2 1
628 98 f_profile 72 8 4 5 1
629 98 f_profile.offset 72 4 4 2 1
630 98 f_profile.count 76 4 4 2 1
631 98 f_schema 80 8 4 5 1
632 98 f_schema.offset 80 4 4 2 1
633 98 f_schema.count 84 4 4 2 1
634 98 f_scope 88 8 4 48 1
635 98 f_scope.offset 88 4 4 2 1
636 98 f_scope.count 92 4 4 2 1
637 98 f_scope_sha256 96 8 4 5 1
638 98 f_scope_sha256.offset 96 4 4 2 1
639 98 f_scope_sha256.count 100 4 4 2 1
640 98 f_transport_limits 104 8 4 15 1
641 98 f_transport_limits.offset 104 4 4 2 1
642 98 f_transport_limits.count 108 4 4 2 1
643 99 tag 0 8 8 3 1
644 99 count 8 8 8 3 1
645 99 logical_element_bytes 16 8 8 3 1
646 99 logical_bytes 24 8 8 3 1
647 99 element_bytes 32 8 8 3 1
648 99 storage_bytes 40 8 8 3 1
649 99 table 48 8 8 4 1
650 100 logical_data_sha256 0 32 1 1 32
651 100 renderer_sha256 32 32 1 1 32
652 100 native_source_sha256 64 32 1 1 32
653 100 tables 96 2632 8 99 47
"""

_TABLE_EVIDENCE = """
1 bytes 1 1 storage
2 uints 53 8 scalar
3 strings 54 8 scalar
4 registers 55 16 pair
5 plan_gaps 56 16 pair
6 positions 57 16 pair
7 dispositions 58 40 pair
8 dynamic 59 24 pair
9 original 60 16 object
10 geometry 61 32 object
11 transport_limits 62 88 object
12 trace_limits 63 48 object
13 capture_limits 64 112 object
14 import_id 65 48 object
15 import_binding 66 152 object
16 call 67 40 object
17 jump 68 8 object
18 return 69 8 object
19 trace_site 70 72 object
20 trace_plan 71 72 object
21 lift_main 72 24 object
22 explicit_entry 73 16 object
23 requested_scope 74 48 object
24 user 75 16 object
25 transit 76 16 object
26 omitted 77 16 object
27 omitted_site 78 40 object
28 transit_route 79 56 object
29 ordinary 80 16 object
30 local_direct 81 16 object
31 local_conditional 82 24 object
32 planned_roles 83 48 object
33 transit_instruction 84 16 object
34 reject 85 16 object
35 guard_instruction 86 88 object
36 dormant_outside_window 87 16 object
37 guard_reject 88 16 object
38 local_branch_guard 89 40 object
39 metadata_only 90 16 object
40 gap_record 91 88 object
41 exit_from_supported_bits 92 24 object
42 exact_signal 93 8 object
43 termination_contract 94 128 object
44 scope_selection 95 184 object
45 load_segment 96 56 object
46 elf_image 97 32 object
47 collector_data 98 112 object
"""

_FIELD_EVIDENCE = """
2 value f_value 0 u
3 value f_value 0 s
4 name f_name 0 s
4 width f_width 8 u
5 address f_address 0 u
5 reason f_reason 8 s
6 route_sha256 f_route_sha256 0 h
6 position f_position 8 u
7 address f_address 0 u
7 disposition f_disposition 8 v:user,transit,omitted
8 tag f_tag 0 i
8 value f_value 16 u
9 bytes f_bytes 0 u
9 sha256 f_sha256 8 h
10 executable_file_start f_executable_file_start 0 u
10 executable_file_end_exclusive f_executable_file_size 8 end:executable_file_start
10 load_memory_start f_load_memory_start 16 u
10 load_memory_end_exclusive f_load_memory_size 24 end:load_memory_start
11 data_bytes f_data_bytes 0 u
11 elf_segments f_elf_segments 8 u
11 gap_records f_gap_records 16 u
11 lift_bytes f_lift_bytes 24 u
11 mapping_bytes f_mapping_bytes 32 u
11 omissions f_omissions 40 u
11 original_bytes f_original_bytes 48 u
11 route_memberships f_route_memberships 56 u
11 route_path_positions f_route_path_positions 64 u
11 routes f_routes 72 u
11 users f_users 80 u
12 events f_events 0 u
12 execution_callbacks f_execution_callbacks 8 u
12 frames f_frames 16 u
12 snapshot_bytes f_snapshot_bytes 24 u
12 translated_instructions f_translated_instructions 32 u
12 wire_bytes f_wire_bytes 40 u
13 events f_events 0 u
13 execution_callbacks f_execution_callbacks 8 u
13 frames f_frames 16 u
13 full_plan_bytes f_full_plan_bytes 24 u
13 full_plan_sites f_full_plan_sites 32 u
13 guarded_instructions f_guarded_instructions 40 u
13 receipt_bytes f_receipt_bytes 48 u
13 route_entries f_route_entries 56 u
13 scope_bytes f_scope_bytes 64 u
13 snapshot_bytes f_snapshot_bytes 72 u
13 thunk_neutral_bytes f_thunk_neutral_bytes 80 u
13 thunk_neutral_instructions f_thunk_neutral_instructions 88 u
13 translated_instructions f_translated_instructions 96 u
13 wire_bytes f_wire_bytes 104 u
14 needed_library f_needed_library 0 o:s
14 symbol f_symbol 16 s
14 version f_version 24 o:s
14 version_hidden f_version_hidden 40 b
15 address_proof_sha256 f_address_proof_sha256 0 h
15 binary_sha256 f_binary_sha256 8 h
15 function f_function 16 o:u
15 gap f_gap 32 o:s
15 identity f_identity 48 o:r:import_id
15 lift_sha256 f_lift_sha256 64 h
15 relocation_file_offset f_relocation_file_offset 72 o:u
15 relocation_kind f_relocation_kind 88 o:u
15 relocation_slot f_relocation_slot 104 o:u
15 site f_site 120 u
15 symbol_index f_symbol_index 128 o:u
15 thunk_path f_thunk_path 144 a:uints
16 continuation f_continuation 0 u
16 import_gaps f_import_gaps 8 a:strings
16 imported f_imported 16 o:r:import_binding
16 kind f_kind 32 e:direct_call|indirect_call
17 kind f_kind 0 e:indirect_jump
18 kind f_kind 0 e:return
19 address f_address 0 u
19 continuation_of f_continuation_of 8 a:uints
19 entry f_entry 16 b
19 owner f_owner 24 u
19 transfer f_transfer 32 v0:call,jump,return
19 witness_hex f_witness_hex 64 w
20 address_proof_sha256 f_address_proof_sha256 0 h
20 binary_sha256 f_binary_sha256 8 h
20 gaps f_gaps 16 a:plan_gaps
20 lift_sha256 f_lift_sha256 24 h
20 limits f_limits 32 r:trace_limits
20 registers f_registers 40 a:registers
20 schema f_schema 48 n:2
20 scope f_scope 56 a:uints
20 sites f_sites 64 a:trace_site
21 kind f_kind 0 e:lift_main
21 lift_sha256 f_lift_sha256 8 h
21 main_elf f_main_elf 16 u
22 kind f_kind 0 e:explicit_entry
22 request_sha256 f_request_sha256 8 h
23 policy f_policy 0 e:main-window-six-v1
23 root f_root 8 u
23 root_evidence f_root_evidence 16 v:lift_main,explicit_entry
23 users f_users 40 a:uints
24 kind f_kind 0 e:user
24 owner f_owner 8 u
25 kind f_kind 0 e:transit
25 route_ids f_route_ids 8 a:strings
26 kind f_kind 0 e:omitted
26 reason f_reason 8 e:outside_requested_users|runtime_lifecycle_outside_window
27 address f_address 0 u
27 full_roles f_full_roles 8 a:strings
27 owner f_owner 16 u
27 reason f_reason 24 e:outside_requested_users|runtime_lifecycle_outside_window
27 witness_sha256 f_witness_sha256 32 h
28 binding_sha256 f_binding_sha256 0 h
28 call_site f_call_site 8 u
28 entries f_entries 16 a:uints
28 instruction_path f_instruction_path 24 a:uints
28 request f_request 32 r:import_id
28 slot f_slot 40 u
28 terminal f_terminal 48 u
29 kind f_kind 0 e:ordinary
29 successor f_successor 8 u
30 destination f_destination 0 u
30 kind f_kind 8 e:local_direct
31 fallthrough f_fallthrough 0 u
31 kind f_kind 8 e:local_conditional
31 taken f_taken 16 u
32 continuation f_continuation 0 o:u
32 destination f_destination 16 o:u
32 kind f_kind 32 e:planned_roles
32 transfer_kind f_transfer_kind 40 e:direct_call|indirect_call|indirect_jump|return
33 kind f_kind 0 e:transit_instruction
33 positions f_positions 8 a:positions
34 kind f_kind 0 e:reject
34 reason f_reason 8 s
35 address f_address 0 u
35 full_roles f_full_roles 8 a:strings
35 owner f_owner 16 u
35 rule f_rule 24 v:ordinary,local_direct,local_conditional,planned_roles,\
transit_instruction,reject
35 witness_hex f_witness_hex 80 w
36 kind f_kind 0 e:dormant_outside_window
36 reason f_reason 8 s
37 kind f_kind 0 e:guard_reject
37 reason f_reason 8 s
38 destination f_destination 0 u
38 fallthrough f_fallthrough 8 o:u
38 kind f_kind 24 e:local_branch_guard
38 rule f_rule 32 e:local_direct|local_conditional
39 kind f_kind 0 e:metadata_only
39 reason f_reason 8 s
40 address f_address 0 u
40 disposition f_disposition 8 v:dormant_outside_window,guard_reject,\
local_branch_guard,metadata_only
40 domain f_domain 48 e:ghidra
40 elf f_elf 56 o:u
40 index f_index 72 u
40 reason f_reason 80 s
41 register f_register 0 s
41 transform f_transform 8 s
41 width f_width 16 u
42 signal f_signal 0 u
43 behavior f_behavior 0 e:process-termination
43 binary_sha256 f_binary_sha256 8 h
43 call_site f_call_site 16 u
43 callbacks f_callbacks 24 e:forbidden
43 cleanup f_cleanup 32 e:no-unobserved-main-reentry
43 full_plan_sha256 f_full_plan_sha256 40 h
43 import_binding_sha256 f_import_binding_sha256 48 o:h
43 permitted_physical_route_sha256 f_permitted_physical_route_sha256 64 h
43 provider_evidence_sha256 f_provider_evidence_sha256 72 h
43 rule_sha256 f_rule_sha256 80 h
43 runtime_manifest_base_sha256 f_runtime_manifest_base_sha256 88 h
43 schema f_schema 96 n:1
43 termination_rule f_termination_rule 104 v:exit_from_supported_bits,exact_signal
44 active_unlisted f_active_unlisted 0 e:reject
44 address_proof_sha256 f_address_proof_sha256 8 h
44 binary_sha256 f_binary_sha256 16 h
44 claim f_claim 24 e:requested-main-activation
44 contracts f_contracts 32 a:termination_contract
44 dispositions f_dispositions 40 a:dispositions
44 full_plan_sha256 f_full_plan_sha256 48 h
44 gap_dispositions f_gap_dispositions 56 a:gap_record
44 guard_instructions f_guard_instructions 64 a:guard_instruction
44 lazy_resolver f_lazy_resolver 72 e:unsupported
44 lift_sha256 f_lift_sha256 80 h
44 limits f_limits 88 r:capture_limits
44 omitted f_omitted 96 a:omitted_site
44 outside_window f_outside_window 104 e:all-sites-outside-frame-capture
44 policy f_policy 112 e:main-window-six-v1
44 policy_implementation_sha256 f_policy_implementation_sha256 120 h
44 registers f_registers 128 a:registers
44 request f_request 136 r:requested_scope
44 root f_root 144 u
44 routes f_routes 152 a:transit_route
44 schema f_schema 160 n:1
44 transit_profile f_transit_profile 168 e:eager-only
44 users f_users 176 a:uints
45 alignment f_alignment 0 u
45 file_offset f_file_offset 8 u
45 file_size f_file_size 16 u
45 flags f_flags 24 u
45 index f_index 32 u
45 memory_size f_memory_size 40 u
45 va f_va 48 u
46 dynamic f_dynamic 0 a:dynamic
46 entry f_entry 8 u
46 kind f_kind 16 u
46 segments f_segments 24 a:load_segment
47 address_proof_sha256 f_address_proof_sha256 0 h
47 c_data_schema f_c_data_schema 8 e:phoenix-eager-c-data-1
47 full_plan f_full_plan 16 r:trace_plan
47 full_plan_sha256 f_full_plan_sha256 24 h
47 geometry f_geometry 32 r:geometry
47 image f_image 40 r:elf_image
47 lift_sha256 f_lift_sha256 48 h
47 original f_original 56 r:original
47 policy_implementation_sha256 f_policy_implementation_sha256 64 h
47 profile f_profile 72 e:main-window-six-v1
47 schema f_schema 80 e:phoenix-eager-collector-data-1
47 scope f_scope 88 r:scope_selection
47 scope_sha256 f_scope_sha256 96 h
47 transport_limits f_transport_limits 104 r:transport_limits
"""


def test_independent_retained_limit_literals() -> None:
    assert layout.TRANSPORT_MAXIMA == (
        ("data_bytes", 16777216),
        ("elf_segments", 1024),
        ("gap_records", 65536),
        ("lift_bytes", 67108864),
        ("mapping_bytes", 67108864),
        ("omissions", 4096),
        ("original_bytes", 16777216),
        ("route_memberships", 1179648),
        ("route_path_positions", 1179648),
        ("routes", 4096),
        ("users", 4096),
    )
    assert layout.TRACE_MAXIMA == (
        ("events", 10000),
        ("execution_callbacks", 1000000),
        ("frames", 64),
        ("snapshot_bytes", 8),
        ("translated_instructions", 1000000),
        ("wire_bytes", 8388608),
    )
    assert layout.CAPTURE_MAXIMA == (
        ("events", 10000),
        ("execution_callbacks", 1000000),
        ("frames", 64),
        ("full_plan_bytes", 524288),
        ("full_plan_sites", 4096),
        ("guarded_instructions", 65536),
        ("receipt_bytes", 65536),
        ("route_entries", 32),
        ("scope_bytes", 8388608),
        ("snapshot_bytes", 8),
        ("thunk_neutral_bytes", 32),
        ("thunk_neutral_instructions", 8),
        ("translated_instructions", 1000000),
        ("wire_bytes", 8388608),
    )
    assert layout.IMAGE_DYNAMIC_MAXIMUM == 65536
