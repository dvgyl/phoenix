"""Create development cases from source behavior with fixed seeds."""

import base64
import json
import random
from pathlib import Path


def case(args=(), data=b"", files=None):
    entries = []
    for path, content in sorted((files or {}).items()):
        entries.append(
            {
                "path": path,
                "kind": "file" if content is not None else "directory",
                "mode": 420 if content is not None else 493,
                "data": base64.b64encode(content or b"").decode(),
            }
        )
    return {
        "args": list(args),
        "stdin": base64.b64encode(data).decode(),
        "tree": {"mode": 493, "entries": entries},
        "environment": {},
    }


def d0_cases(name, rng):
    out = []

    def add(args=(), data=b"", files=None):
        out.append(case(args, data, files))

    if name == "niblace":
        add()
        add(["bad"])
        add(["encode", "missing"])
        add(["encode", "input"], files={"input": b"abc\0\xff"})
        add(["decode", "input"], files={"input": b"aapp"})
        add(["encode", "a", "b"])
        for data in [b"", bytes(range(256)), b"\0", b"abc", b"\xff"]:
            add(["encode"], data)
        for data in [b"", b"ap", b"aa pp\n", b"a", b"z", b"\0", b"a\nz"]:
            add(["decode"], data)
        for _ in range(140):
            data = rng.randbytes(rng.randrange(100))
            add(["encode"], data)
            encoded = bytes(97 + nibble for b in data for nibble in (b >> 4, b & 15))
            add(["decode"], encoded)
    elif name == "weighbit":
        for args in [
            [],
            ["0"],
            ["32"],
            ["-1"],
            ["x"],
            ["1", "absent"],
            ["1", "a", "b"],
        ]:
            add(args)
        for _ in range(160):
            data = rng.randbytes(rng.randrange(300))
            rotation = str(rng.randrange(1, 32))
            add([rotation], data)
            add([rotation, "input"], files={"input": data})
    elif name == "runepack":
        for args in [[], ["bad"], ["encode", "absent"], ["encode", "a", "b"]]:
            add(args)
        for data in [
            b"gg:1;",
            b"00x1;",
            b"00:;",
            b"00:0;",
            b"00:256;",
            b"00:1x",
            b"0",
            b"00:1",
            b"\xff",
            b" \t\r\n",
        ]:
            add(["decode"], data)
        for _ in range(140):
            data = b"".join(
                bytes([rng.randrange(256)]) * rng.randrange(300)
                for _ in range(rng.randrange(8))
            )
            add(["encode"], data)
            encoded = b"".join(
                f"{b:02x}:{rng.randrange(1, 256)};".encode()
                for b in rng.randbytes(rng.randrange(8))
            )
            add(["decode", "input"], files={"input": encoded})
    elif name == "pairfold":
        for args in [
            ["-?"],
            ["-w"],
            ["-p"],
            ["-w", "0"],
            ["-w", "4097"],
            ["-p", "65522"],
            ["-p", "x"],
            ["absent"],
            ["a", "b"],
        ]:
            add(args)
        for _ in range(220):
            args = [
                "-w",
                str(rng.choice([1, 2, 7, 16, 31])),
                "-p",
                str(rng.choice([1, 2, 251, 65521])),
            ]
            if rng.randrange(2):
                args.append("-c")
            data = rng.randbytes(rng.randrange(100))
            if rng.randrange(2):
                add(args + ["input"], files={"input": data})
            else:
                add(args, data)
    elif name in {"driftstat", "spanrank", "gapmeter"}:
        for args in [["-?"], ["absent"], ["a", "b"]]:
            add(args)
        for data in [
            b"",
            b"x",
            b"nan",
            b"inf",
            b"1e20",
            b"1 0 -2 x",
            b"0",
            b"1 1 1",
            b"1 -1 1 0",
        ]:
            add(data=data)
        if name == "driftstat":
            for args in [["-m"], ["-m", "x"], ["-m", "nan"], ["-m", "1e20"]]:
                add(args)
            add(data=b"0 " * 10001)
            options = [
                [],
                ["-c"],
                ["-s"],
                ["-k"],
                ["-c", "-s", "-k"],
                ["-m", "-2"],
                ["-m", "0"],
            ]
        elif name == "spanrank":
            for args in [["-q"], ["-q", "x"], ["-q", "nan"], ["-q", "-1"], ["-q", "2"]]:
                add(args)
            add(data=b"0 " * 1025)
            options = [
                [],
                ["-r"],
                ["-s"],
                ["-q", "0"],
                ["-q", "1"],
                ["-q", "0.5"],
                ["-q", "0.23"],
            ]
        else:
            for args in [["-t"], ["-c"], ["-t", "x"], ["-t", "-1"], ["-c", "nan"]]:
                add(args)
            add(data=b"0 " * 2049)
            options = [
                [],
                ["-h"],
                ["-s"],
                ["-t", "0"],
                ["-t", "10", "-s"],
                ["-c", "0"],
                ["-c", "-2"],
            ]
            add(["-h"], b"0 " * 100)
        for i in range(250):
            values = [
                rng.choice([0, 0, -1, 1, -50, 50, rng.randrange(-200, 200) / 10])
                for _ in range(rng.randrange(1, 40))
            ]
            data = " ".join(map(str, values)).encode()
            args = options[i % len(options)]
            if i % 5 == 0:
                add(args + ["input"], files={"input": data})
            else:
                add(args, data)
        if name == "driftstat":
            add(["-k"], b"bad nan 1 2 junk")
            add(["-k"], b"bad")
    elif name == "wordweft":
        for args in [
            ["-?"],
            ["-w"],
            ["-w", "bad"],
            ["-w", "4097"],
            ["absent"],
            ["a", "b"],
        ]:
            add(args)
        for data in [b"~", b"~0", b"~zz", b"?", b"~00", b"~aF+ABC\r\n_-.~0a"]:
            add(["-d", "-l"], data)
        for i in range(240):
            data = rng.randbytes(rng.randrange(150))
            args = [[], ["-l"], ["-i"], ["-w", "1"], ["-w", "7", "-l"]][i % 5]
            add(args, data)
            if i % 4 == 0:
                add(
                    ["-d", "input"],
                    files={"input": b"".join(f"~{b:02X}".encode() for b in data)},
                )
    elif name == "tilehash":
        for args in [
            ["-?"],
            ["-w"],
            ["-w", "0"],
            ["-w", "65537"],
            ["-w", "bad"],
            ["absent"],
            ["a", "b"],
        ]:
            add(args)
        for data in [b"0", b"gg", b"00ff \n\t\rAA", b"", b"00aZ"]:
            add(["-x"], data)
        for i in range(250):
            data = rng.randbytes(rng.randrange(180))
            args = ["-w", str(rng.choice([1, 8, 17, 64]))]
            if i % 2:
                args.append("-d")
            if i % 3:
                args.append("-c")
            if i % 4 == 0:
                args.append("-x")
                data = data.hex().encode()
            if i % 7 == 0:
                args.append("-h")
            if i % 5 == 0:
                add(args + ["input"], files={"input": data})
            else:
                add(args, data)
    elif name == "tokenlace":
        for args in [
            ["-?"],
            ["-b"],
            ["-b", "0"],
            ["-b", "35"],
            ["-b", "bad"],
            ["absent"],
            ["a", "b"],
        ]:
            add(args)
        for data in [
            b"",
            b"!",
            b"!0000",
            b"00!0001",
            b"!gggg",
            b"!0000x",
            b"F",
            b"ZZ",
            b"I0",
            b"00\r\n ",
            b"FF",
        ]:
            add(["-d", "-c", "-s"], data)
            add(["-d"], data)
        alphabet = "0123456789ABCDEFGHJKLMNPQRSTUVWXYZ"
        for i in range(200):
            radix = rng.randrange(2, 35)
            width = 1
            while radix**width < 256:
                width += 1
            reverse = i % 2
            data = rng.randbytes(rng.randrange(60))
            args = ["-b", str(radix)] + (["-r"] if reverse else [])
            if i % 3 == 0:
                args.append("-c")
            if i % 7 == 0:
                args.append("-s")
            add(args + (["-i"] if i % 5 == 0 else []), data)
            encoded = ""
            total = 0
            for b in data:
                value = b
                digits = ""
                for _ in range(width):
                    digits += alphabet[value % radix]
                    value //= radix
                encoded += digits if reverse else digits[::-1]
                total = (total * 33 + b + 1) % 65521
            if "-c" in args:
                encoded += f"!{total:04x}"
            add(args + ["-d", "input"], files={"input": encoded.encode()})
    else:
        raise ValueError(name)
    return out


def generate(name, seed):
    root = Path(__file__).parent / name / "holdout"
    rng = random.Random(seed)
    if name in {"chromapath", "recordloom"}:
        from d1_image_record_cases import image_record_cases

        cases = image_record_cases(name, rng)
    elif name in {"patchpanel", "tariffgrid", "fernconf", "unitforge"}:
        from d1_large_cases import large_cases

        cases = large_cases(name, rng)
    elif name in {
        "knotconf",
        "prismcsv",
        "velocalc",
        "lumaquilt",
        "branchmark",
        "skeinwire",
    }:
        from d1_cases import d1_cases

        cases = d1_cases(name, rng)
    else:
        cases = d0_cases(name, rng)
    root.mkdir(parents=True, exist_ok=True)
    lines = dict.fromkeys(json.dumps(c, sort_keys=True) for c in cases)
    (root / "cases.jsonl").write_text("".join(line + "\n" for line in lines))
    return len(lines)
