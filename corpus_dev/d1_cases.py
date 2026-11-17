"""Create cases from the development source interfaces."""

import itertools
import struct

from generate_cases import case


def d1_cases(name, rng):
    out = []

    def add(args=(), data=b"", files=None):
        out.append(case(args, data, files))

    for args in [["-?"], ["-Z"], ["absent"], ["a", "b"]]:
        add(args)
    if name == "knotconf":
        for data in [
            b"",
            b"# test\n",
            b"?absent",
            b"-absent",
            b"bad",
            b"=x",
            b"a.b=x",
            b"x" * 64 + b"=a",
            b"k=" + b"x" * 256,
            b"x" * 512,
            b"@absent",
            b"!u",
            b"!u absent",
            b"a=x\n!z a",
        ]:
            add(data=data)
        add(["-s"], b"-missing")
        add(data=b"".join(f"k{i}=v\n".encode() for i in range(65)))
        add(data=b"@loop", files={"loop": b"@loop"})
        add(["-o", "x" * 241])
        add(["-o", "out"], b"a=b", {"out": None})
        add(["-o", "missing/child"], b"a=b")
        add(data=b"@bad", files={"bad": b"wrong"})
        for operation in "ulrt neds".replace(" ", ""):
            add(data=f"a= AbC 123 \n!{operation} a\n?a\n!sort\n".encode())
        for i in range(320):
            keys = [f"k{k}" for k in range(rng.randrange(1, 15))]
            lines = [
                f"{k}={rng.choice(['abc', 'Z9', '', 'Hello World', '123'])}"
                for k in keys
            ]
            for _ in range(rng.randrange(15)):
                key = rng.choice(keys)
                lines.append(f"!{rng.choice('ulrtneds')} {key}")
            lines.extend([f"?{keys[0]}", "!sort", f"-{keys[-1]}", f"{keys[0]}=last"])
            files = {"extra": b"included=yes\n"}
            if i % 3 == 0:
                lines.insert(0, "@extra")
            args = [[], ["-i"], ["-s"], ["-p", "k1"], ["-o", "out"]][i % 5]
            data = ("\n".join(lines) + "\n").encode()
            if i % 7 == 0:
                files["input"] = data
                add(args + ["input"], files=files)
            else:
                add(args, data, files)
    elif name == "prismcsv":
        add(["-t", "upper", "-t", "bad"])
        for args in [
            ["-d", ""],
            ["-d", "xx"],
            ["-d", '"'],
            ["-o", "\n"],
            ["-k", "16"],
            ["-k", "x"],
            ["-p", "nan"],
            ["-t", "bad"],
            ["-k"],
            ["-p", "x"],
        ]:
            add(args)
        for data in [
            b"",
            b'"unterminated',
            b'"a"x\n',
            b"," * 16,
            b"x" * 128,
            b'"a\nb","x""y"\r\n',
            b'""',
            b"a,b\rc",
            b"a,b",
        ]:
            add(data=data)
        add(["-k", "3"], b"a,b\n")
        for operation in "amnbfcsz?":
            for value in [-3, 0, 4.25]:
                add(["-x", operation, "-p", "2"], f"{value}\n".encode())
        add(["-x", "a"], b"x\n")
        transforms = ["upper", "lower", "reverse", "strip", "length", "slug"]
        for i in range(320):
            sep = rng.choice([",", ";", "|"])
            args = ["-d", sep, "-o", rng.choice([",", ";", "|"])]
            if i % 2:
                args += ["-r"]
            if i % 3:
                args += ["-t", transforms[i % len(transforms)]]
            count = rng.randrange(1, 12)
            if i % 5 == 0:
                args += ["-k", str(rng.randrange(count))]
            rows = []
            for _ in range(rng.randrange(1, 6)):
                cells = [
                    rng.choice(["", " A b ", 'a"b', "x\ny", "123", sep, "z", " "])
                    for _ in range(count)
                ]
                rows.append(
                    sep.join('"' + cell.replace('"', '""') + '"' for cell in cells)
                )
            data = ("\n".join(rows) + "\n").encode()
            if i % 7 == 0:
                add(args + ["input"], files={"input": data})
            else:
                add(args, data)
    elif name == "velocalc":
        for args in [
            ["-p", "-1"],
            ["-p", "10"],
            ["-p", "x"],
            ["-p", ""],
            ["-v", "a"],
            ["-v", "A=1"],
            ["-v", "a=nan"],
            ["-v", "a=1e20"],
            ["-v", "a=x"],
        ]:
            add(args)
        for expression in [
            "",
            "# comment",
            "()",
            "1+",
            "(",
            "1)",
            "unknown",
            "unknown(1)",
            "sqrt(-1)",
            "log(0)",
            "exp(1000)",
            "1/0",
            "1%0",
            "1e20",
            "2^100",
            "(1+2",
            "sin(1",
            "a:2\na*3",
            "-" * 40 + "1",
            "(" * 33 + "1" + ")" * 33,
            "!0",
            "!1",
        ]:
            add(data=(expression + "\n").encode())
        for op in "+-*/%^<>=&|":
            for a, b in itertools.product([-2, 0, 2], repeat=2):
                add(data=f"({a}){op}({b})\n".encode())
        funcs = ["abs", "floor", "ceil", "sin", "cos", "sqrt", "log", "exp"]
        for i in range(230):
            x = rng.randrange(1, 9) / 2
            fun = funcs[i % len(funcs)]
            expr = f"a:{x}\nb:{fun}(a)\n(b+2)*3-4/2\na<9&b>0|a=0\n"
            args = ["-p", str(i % 10)]
            if i % 2:
                args += ["-n"]
            if i % 7 == 0:
                add(args + ["input"], files={"input": expr.encode()})
            else:
                add(args + ["-v", "z=-3"], expr.encode())
    elif name == "lumaquilt":
        for args in [["-o"], ["-o", "missing/file"]]:
            add(args, b"1 1 2")
        for data in [
            b"",
            b"x",
            b"0 1",
            b"1 0",
            b"33 1",
            b"1 33",
            b"1 1 -1",
            b"1 1 256",
            b"1 1 x",
            b"1 1",
            b"1 1 2 bad",
            b"1 1 2 b",
            b"1 1 2 b x",
            b"1 1 2 p 1",
            b"1 1 2 p 257",
            b"1 1 2 components -1",
            b"1 1 2 components 256",
            b"1 1 2 tiles",
            b"1 1 2 crop",
            b"1 1 2 crop -1 0 1 1",
            b"1 1 2 crop 0 -1 1 1",
            b"1 1 2 crop 0 0 0 1",
            b"1 1 2 crop 0 0 1 0",
            b"1 1 2 crop 0 0 2 1",
            b"1 1 2 crop 0 0 1 2",
        ]:
            add(data=data)
        add(data=b"1 1 2 tiles out", files={"out": None})
        add(data=b"1 1 2 tiles missing/dir")
        filters = [
            "invert",
            "flipx",
            "flipy",
            "transpose",
            "rotate",
            "blur",
            "median",
            "erode",
            "dilate",
            "edges",
            "normalize",
            "equalize",
            "dither",
            "sharpen",
            "diagonal",
            "stats",
            "histogram",
            "components 0",
            "components 128",
            "components 255",
        ]
        for i in range(360):
            w = rng.randrange(1, 9)
            h = rng.randrange(1, 9)
            values = [
                rng.choice([0, 0, 255, 128, rng.randrange(256)]) for _ in range(w * h)
            ]
            commands = [filters[i % len(filters)]]
            if i % 2:
                commands += [
                    f"{rng.choice('btsfgvr')} {rng.choice([-300, -1, 0, 1, 128, 300])}"
                ]
            if i % 3:
                commands += [f"p {rng.choice([2, 3, 4, 16, 256])}"]
            if i % 5 == 0:
                commands += ["crop 0 0 1 1", "stats"]
            if i % 7 == 0:
                commands += ["tiles out"]
            data = (
                f"{w} {h} " + " ".join(map(str, values)) + "\n" + "\n".join(commands)
            ).encode()
            args = [[], ["-q"], ["-o", "result"]][i % 3]
            if i % 11 == 0:
                add(args + ["input"], files={"input": data})
            else:
                add(args, data)
        add(data=b"2 2 10 10 10 10 normalize stats components 255")
    elif name == "branchmark":
        add(["missing"])
        add(["-c", "absent", "tree"], files={"tree": None})
        add(["-f", "8", "tree"])
        add(["-f", "x", "tree"])
        add(["-g", "bad", "tree"], files={"tree": None})
        add(["x" * 241])
        for config in [
            "bad",
            "suffix x",
            "suffix .a bad",
            "suffix .a -1",
            "suffix .a 1001",
            "remove absent",
            "minimum x",
            "maximum 1000001",
            "depth 17",
            "depth x",
            "mode bad",
            "minimum 2\nmaximum 1",
            "exclude " + "x" * 128,
            "unknown x",
            "suffix " + "x" * 32 + " 1",
            "\n# comment\n",
        ]:
            add(
                ["-c", "config", "tree"],
                files={"config": config.encode(), "tree": None},
            )
        add(
            ["-c", "config", "tree"],
            files={
                "config": b"".join(f"suffix .x{i} 1\n".encode() for i in range(33)),
                "tree": None,
            },
        )
        for i in range(320):
            files = {
                "tree": None,
                "tree/sub": None,
                "tree/sub/deep": None,
                "tree/empty": b"",
            }
            for j in range(rng.randrange(1, 14)):
                sub = rng.choice(["", "sub/", "sub/deep/"])
                suffix = rng.choice([".txt", ".dat", "", '.q"'])
                files[f"tree/{sub}f{j}{suffix}"] = rng.choice(
                    [
                        b"a b\nc\n",
                        b"same",
                        b"\0\t\r\n\xff",
                        b"",
                        rng.randbytes(rng.randrange(40)),
                    ]
                )
            mode = ["bytes", "lines", "words", "density"][i % 4]
            config = (
                "suffix .txt 2\nsuffix .txt 3\nsuffix .dat 0\n"
                "suffix .gone 1\nremove .gone\n"
                f"mode {mode}\ndepth {i % 3}\n"
            )
            if i % 3 == 0:
                config += "exclude deep\n"
            if i % 5 == 0:
                config += "minimum 2\nmaximum 20\n"
            files["config"] = config.encode()
            args = ["-c", "config", "-f", str(i % 8)]
            if i % 2:
                args += ["-s", "-r"]
            if i % 3:
                args += ["-e"]
            args += [
                "-g",
                ["depth", "suffix", "duplicates", "distribution"][i % 4],
                "tree",
            ]
            add(args, files=files)
        for config, files in [
            ("suffix " + "x" * 31 + " 2\n", {"tree/" + "x" * 31: b"x"}),
            ("maximum 1000000\n", {"tree/limit": b"x"}),
            ("suffix .a 1000\n", {"tree/f.a": b"x"}),
            ("exclude " + "x" * 127 + "\n", {"tree/" + "x" * 127: b"x"}),
            (
                "suffix .a 2\nsuffix .b 3\nsuffix .c 5\n"
                "suffix .d 7\nsuffix .e 11\nremove .b\n",
                {f"tree/f.{suffix}": b"x" for suffix in "abcde"},
            ),
            (
                "suffix .a 2\nsuffix .b 3\nsuffix .b 7\n",
                {"tree/f.b": b"x"},
            ),
            ("suffix .dat 3\n", {"tree/.dat": b"x"}),
        ]:
            add(
                ["-c", "config", "tree"],
                files={"tree": None, "config": config.encode(), **files},
            )
        add(
            ["-g", "depth", "tree"],
            files={"tree": None, "tree/sub": None, "tree/sub/file": b"x"},
        )
        add(
            ["-e", "-g", "distribution", "tree"],
            files={"tree": None, "tree/empty": b"", "tree/one": b"x"},
        )
        for length in [254, 255]:
            parent = "tree/" + "a" * 200
            nested = parent + "/" + "b" * 55
            add(
                ["tree"],
                files={
                    "tree": None,
                    parent: None,
                    nested: None,
                    nested + "/" + "c" * length: b"x",
                },
            )
    elif name == "skeinwire":
        for args in [["-t", "0"], ["-t", "10"], ["-t", "x"], ["-t"]]:
            add(args)
        for line in [
            "",
            "# comment",
            "bad",
            "bad value",
            "integer x",
            "fixed x",
            "flag x",
            "bits 012",
            "bytes 0",
            "bytes gg",
            "list x",
            "delta ",
            "text " + "x" * 1025,
        ]:
            add(data=(line + "\n").encode())
        add(data=("text " + "x" * 1000 + "\n").encode() * 9)
        add(["-d"], b"00" * 8193)
        add(["-d", "-b"], b"\0" * 8193)
        malformed = [
            b"",
            b"\0\0",
            b"\1",
            b"\2\1\x80",
            b"\2\5\xff\xff\xff\xff\xff",
            b"\2\6\x80\x80\x80\x80\x80\x00",
            b"\4\0",
            b"\4\4\xff\xff\xff\x7f",
            b"\6\1\xff",
            b"\6\2\1\1",
            b"\7\2\0A",
            b"\7\1\1",
            b"\10\1\1",
            b"\11\1\2",
            b"\11\2\1\0",
            b"\1\xff\x7f",
        ]
        for data in malformed:
            for flags in [[], ["-q"], ["-e"]]:
                add(["-d", "-b", *flags], data)

        def varint(value):
            result = bytearray()
            while value > 127:
                result.append((value & 127) | 128)
                value >>= 7
            result.append(value)
            return bytes(result)

        def zz(value):
            return value * 2 if value >= 0 else -value * 2 - 1

        for i in range(240):
            types = []
            lines = []
            for t in range(1, 10):
                value = rng.randrange(-1000000, 1000001)
                if t == 1:
                    payload = rng.choice([b"abc", b"", b"A\\B\t", b"hello world"])
                    line = b"text " + payload
                elif t == 2:
                    payload = varint(zz(value))
                    line = f"integer {value}".encode()
                elif t == 3:
                    payload = rng.randbytes(rng.randrange(12))
                    line = b"bytes " + payload.hex().encode()
                elif t in [4, 5]:
                    values = [
                        rng.randrange(-100, 101) for _ in range(rng.randrange(1, 8))
                    ]
                    previous = 0
                    payload = b""
                    for v in values:
                        payload += varint(zz(v - previous if t == 5 else v))
                        previous = v
                    line = ("list " if t == 4 else "delta ").encode() + ",".join(
                        map(str, values)
                    ).encode()
                elif t == 6:
                    bits = "".join(rng.choice("01") for _ in range(rng.randrange(20)))
                    payload = varint(len(bits)) + bytes(
                        sum(int(c) << k for k, c in enumerate(bits[j : j + 8]))
                        for j in range(0, len(bits), 8)
                    )
                    line = b"bits " + bits.encode()
                elif t == 7:
                    count = rng.randrange(1, 256)
                    payload = bytes([count, 65])
                    line = b"runs " + b"A" * count
                elif t == 8:
                    payload = struct.pack("<I", zz(value))
                    line = f"fixed {value}".encode()
                else:
                    flag = rng.randrange(2)
                    payload = bytes([flag])
                    line = b"flag " + (b"true" if flag else b"false")
                types.append(bytes([t]) + varint(len(payload)) + payload)
                lines.append(line)
            data = b"\n".join(lines) + b"\n"
            args = (
                (["-e"] if i % 2 else [])
                + (["-S"] if i % 3 else [])
                + (["-b"] if i % 5 else ["-s"])
            )
            add(args, data)
            packet = b"".join(types)
            if "-e" in args:
                total = sum(b * (k + 1) for k, b in enumerate(packet)) % 65521
                packet = (
                    b"SW\1"
                    + struct.pack(
                        "<HHB", len(packet), total, (len(packet) ^ total) & 255
                    )
                    + packet
                )
            if i % 7 == 0:
                args += ["-q"]
            if i % 11 == 0:
                args += ["-t", str(i % 9 + 1)]
            add(["-d", *args], packet if "-b" in args else packet.hex().encode())
            if i < 8:
                broken = bytearray(packet)
                if not i % 2:
                    broken = bytearray(b"SW\1\0\0\0\0\0")
                if i < len(broken):
                    broken[i] ^= 255
                add(["-d", "-e", "-b"], bytes(broken))
    else:
        raise ValueError(name)
    return out
