"""Create cases for the larger development programs."""

from generate_cases import case


def large_cases(name, rng):
    out = []

    def add(data="", args=(), files=None):
        out.append(case(args, data.encode() if isinstance(data, str) else data, files))

    for args in [["-?"], ["absent"], ["a", "b"]]:
        add(args=args)
    if name == "patchpanel":
        base = "3 3 0 1 -2 0 3 4 1 1 2\n"
        for args in [["-p", "x"], ["-p", "-1"], ["-p", "10"], ["-p", ""]]:
            add(args=args)
        for data in [
            "",
            "x",
            "0 1",
            "33 1",
            "1 0",
            "1 17",
            "1 1 x",
            "1 1 nan",
            "1 1 1e20",
            "1 1",
        ]:
            add(data)
        errors = [
            "bad",
            "restore",
            "multiply",
            "append",
            "join",
            "scalar",
            "scalar xx",
            "scalar ? 0 2",
            "scalar / 0 0",
            "scalar + 0 x",
            "scalar + -1 2",
            "scalar + 16 2",
            "scalar * 0 1e9",
            "scalar ^ 2 100",
            "derive",
            "derive 0 1 xx",
            "derive 0 1 ?",
            "derive 1 0 /",
            "set",
            "set -1 0 2",
            "set 32 0 2",
            "set 0 16 2",
            "set 0 0 x",
            "sort -1",
            "sort 16",
            "rolling 0 0",
            "rolling 0 33",
            "rolling 0 x",
            "filter 0 2 1",
            "filter 0 100 200",
            "swap 0 16",
            "label 0",
            "csv",
            "csv missing/out",
            "load",
            "load absent",
            "save transpose append",
            "save transpose join",
            "save drop 0 multiply",
        ]
        for tail in errors:
            add(base + tail)
        for text in [
            "",
            "1,2\n3\n",
            "x\n",
            "nan\n",
            "1;2\n",
            "1,\n",
            ",".join("1" for _ in range(17)),
            "1\n" * 33,
            "1 \t\r\n2\n",
        ]:
            add(base + "load input", files={"input": text.encode()})
        add("17 1 " + "1 " * 17 + "transpose")
        add("1 16 " + "1 " * 16 + "derive 0 1 +")
        add("1 1 2 drop 0")
        add("20 1 " + "1 " * 20 + "save append")
        add("1 9 " + "1 " * 9 + "save join")
        for op in "+*/<>=^%?":
            for value in [-2, 0, 2]:
                add(base + f"scalar {op} 0 {value}")
        for op in "+-*/<>=!?":
            add(base + f"derive 1 2 {op}")
        cmds = [
            "sort 0",
            "normalize 0",
            "standardize 0",
            "accumulate 0",
            "difference 1",
            "rank 0",
            "rolling 0 2",
            "filter 0 -2 2",
            "drop 2",
            "swap 0 1",
            "correlate 0 1",
            "stats 0",
            "label 0 item",
            "save reverse restore",
            "save append",
            "save join",
            "save multiply",
            "group 0",
            "covariance",
            "unique",
            "transpose",
            "reverse",
            "show",
            "csv result",
            "load other",
        ]
        for i in range(330):
            rows = rng.randrange(1, 10)
            columns = 3
            values = [
                rng.choice([-2, -1, 0, 0, 1, 2, 4.5]) for _ in range(rows * columns)
            ]
            text = (
                f"{rows} {columns} "
                + " ".join(map(str, values))
                + "\n"
                + cmds[i % len(cmds)]
            )
            args = (
                ["-p", str(i % 10)]
                + (["-h"] if i % 2 else [])
                + (["-q"] if i % 3 else [])
            )
            files = {"other": b"1,2,3\n4,5,6\n"}
            if i % 11 == 0:
                files["input"] = text.encode()
                add(args=args + ["input"], files=files)
            else:
                add(text, args=args, files=files)
        add("2 2 1 2 3 4 save multiply")
        add("2 1 1 1 normalize 0 standardize 0 correlate 0 0")
    elif name == "tariffgrid":
        base = "item A 1.25 0 item B 2.40 1 tax 0 500 tax 1 2000 sale A 3 sale B 2\n"
        for args in [["-r", "x"], ["-r", "4"], ["-r", "-1"], ["-r", ""]]:
            add(args=args)
        bad = [
            "bad",
            "item",
            "item a? 2 0",
            "item " + "x" * 32 + " 1 0",
            "item A x 0",
            "item A -1 0",
            "item A 1 8",
            "item A 1. 0",
            "item A 1.234 0",
            "item A 1000001 0",
            "sale ? 1",
            "sale absent 1",
            "sale A 0",
            "sale A 10001",
            "band absent 1 2",
            "band A 0 2",
            "band A 1 -2",
            "unband A 0",
            "unband A 5",
            "quote A 0",
            "quote absent 1",
            "discount -1 2",
            "discount 127 2",
            "discount 0 -1",
            "discount 0 10001",
            "quantity 0 x",
            "price 0 -1",
            "tax 8 0",
            "tax 0 10001",
            "coupon",
            "coupon bad",
            "coupon amount -1",
            "coupon rate 10001",
            "shipping -1 1 1",
            "shipping 1 -1 1",
            "shipping 1 1 -1",
            "credit x",
            "currency a?",
            "currency " + "x" * 16,
            "round 4",
            "receipt",
            "receipt missing/out",
            "export",
            "export missing/out",
            "plan 0 0",
            "plan 1 10001",
            "settle -1",
            "cash 0",
            "cash 101",
            "reprice absent",
        ]
        for command in bad:
            add(base + command)
        add("restore")
        add(" ".join(f"item a{i} 1 0" for i in range(33)))
        add("item A 1 0 " + " ".join(f"band A {i + 1} 1" for i in range(9)))
        add("item A 1 0 " + "sale A 1 " * 129)
        add("clear " * 4097)
        add("item A 1 0 return A 2 plan 2 10")
        commands = [
            "band A 2 1.10 band A 2 1.05 quote A 2",
            "discount 0 500",
            "quantity 0 -2",
            "price 0 0",
            "drop 0",
            "coupon none",
            "coupon amount 1",
            "coupon amount 999",
            "coupon rate 500",
            "shipping 1 0.10 0",
            "shipping 1 0.10 3",
            "credit 1.5 fee -0.1",
            "currency TOK",
            "save clear restore",
            "save clear",
            "sort",
            "sale A 3 merge",
            "products",
            "catalog",
            "quote B 9",
            "receipt result",
            "band A 2 1 unband A 2",
            "item A 3 0 reprice A",
            "show",
            "taxes",
            "audit",
            "export result",
            "plan 3 100",
            "settle 0",
            "settle 100",
            "cash 5",
            "quantity 0 0 audit",
        ]
        for i in range(340):
            price = rng.choice(["0", "0.01", "1.25", "+2", "3.1", "1.00"])
            quantity = rng.randrange(1, 20)
            tax = i % 8
            rate = rng.choice([0, 500, 1750, 10000])
            text = (
                f"item A {price} {tax} item B 2.40 1 tax {tax} {rate}"
                f" tax 1 2000 sale A {quantity} sale B 2 "
            )
            if i % 5 == 0:
                text += "return A 1 "
            text += commands[i % len(commands)]
            args = ["-r", str(i % 4)] + (["-q"] if i % 3 else ["-d"])
            if i % 11 == 0:
                add(args=args + ["input"], files={"input": text.encode()})
            else:
                add(text, args=args)
        for rounding in range(4):
            for quantity in [1, 2, 3, 4, 5]:
                add(
                    f"item A 0.01 0 tax 0 5000 sale A {quantity} "
                    "coupon rate 5000 cash 2",
                    args=["-r", str(rounding)],
                )
    elif name == "fernconf":
        base = (
            'section /a section /b set /a/x "s:Ab c" set /a/n n:2 '
            "set /b/n n:3 set /a/t b:true set /b/f b:false set /a/z z:null\n"
        )
        for args in [["-p", "x"], ["-p", "-1"], ["-p", "10"], ["-p", ""]]:
            add(args=args)
        bad = [
            "bad",
            '"unclosed',
            '"\\x"',
            '"' + "x" * 256 + '"',
            "section",
            "section bad",
            "section /a//b",
            "section /a/",
            "section /" + "x" * 48,
            "section /a/n/sub",
            "set /a/x bad",
            "set /a/x q:1",
            "set /a/x n:",
            "set /a/x n:nan",
            "set /a/x n:1e20",
            "set /a/x b:bad",
            "set /a/x z:bad",
            "set / n:1",
            "print absent",
            "copy / /c",
            "copy /a /a/n",
            "copy /a bad",
            "copy /a /bad/child",
            "copy /a /a/self",
            "copy /a /b/bad?",
            "copy /a /b/" + "x" * 48,
            "copy /a /b/",
            "move /a /a/child",
            "scale /a x",
            "scale /a 1001",
            "find",
            "include absent",
            "export / out",
            "merge /a /a",
            "merge /a/n /b",
            "scale absent 1",
            "set /n n:1000000000 scale /n 1000",
        ]
        for command in bad:
            add(base + command, files={"out": None})
        add('set /a "s:' + "\0" + '"')
        add("section /" + "/".join("a" for _ in range(17)))
        add(" ".join(f"set /k{i} n:1" for i in range(128)))
        add("include loop", files={"loop": b"include loop"})
        add("include bad", files={"bad": b"wrong"})
        for escape in [r"\n", r"\t", r"\r", r"\s", r"\q", r"\\", r"\#", r"\/"]:
            add('set /a "s:a' + escape + 'b"')
        commands = [
            "print /",
            "flat /",
            "remove /a",
            "remove /",
            "stats /",
            "upper /",
            "lower /",
            "reverse /",
            "scale / 0",
            "scale / -2",
            "find x",
            "find absent",
            "toggle",
            "copy /a /b/copied",
            "move /a/x /b/moved",
            "sort",
            "order",
            "reset",
            "export / tree",
            "export /a/x text",
            "include more",
            "set /a s:replaced",
            "merge /a /b",
            "section /a/sub set /a/sub/x n:1 section /b/sub merge /a /b",
        ]
        for i in range(330):
            data = base + commands[i % len(commands)]
            args = (
                ["-p", str(i % 10)]
                + (["-f"] if i % 2 else [])
                + (["-s"] if i % 3 else [])
                + (["-q"] if i % 5 else [])
            )
            files = {"more": b"set /extra n:5\n# comment\n"}
            if i % 11 == 0:
                files["input"] = data.encode()
                add(args=args + ["input"], files=files)
            else:
                add(data, args=args, files=files)
        add("set /a s:x set /a s:y set /b n:-2 stats /")
    elif name == "unitforge":
        for args in [["-p", "x"], ["-p", "-1"], ["-p", "10"], ["-p", ""]]:
            add(args=args)
        errors = [
            "bad",
            "push",
            "push x m",
            "push nan m",
            "push 1e20 m",
            "push 1 bad",
            "push 1 " + "a" * 16,
            "push 1 m^9",
            "push 1 m^x",
            "push 1 C^2",
            "push 1 C*m",
            "push 1 m/C",
            "push 1 m!",
            "push 1 m^8*m^8*m",
            "push 1 m^16",
            "push 1 /m",
            "convert",
            "push 1 m convert bad",
            "push 1 m convert s",
            "push 1 m^8*m^8 convert mm^8*mm^8",
            "push 1e12 km",
            "push 1e12 1 push 1e12 1 *",
            "push 1 m push 1 s +",
            "push 1 m push 0 s /",
            "push 1 m push 0 m %",
            "push 1 m push 0.5 1 ^",
            "push 1 m push 9 1 ^",
            "push 1 m push 1 m ^",
            "push 1 m sin",
            "push 1 m sqrt",
            "push 1 m cbrt",
            "push -1 1 sqrt",
            "push 0 1 reciprocal",
            "store z",
            "load z",
            "load A",
            "store abc",
            "last",
            "swap",
            "push 1 m swap",
            "push 1 m push 1 m rot",
            "sum",
            "push 1 m push 1 s mean",
            "fit 1",
            "fit 2 1 1 1 2",
            "fit 2 1 x",
            "interpolate 0 0 0 1 2",
            "interpolate 1 x",
            "weighted 0",
            "weighted 1 1 -1",
            "weighted 1 1 0",
            "distance 0",
            "distance 2 1 x",
            "progression x",
            "progression 1 1 1 bad",
            "poly 17",
            "poly 1 2 x",
            "peval 2",
            "poly 0 1 padd",
            "poly 0 1 pmul",
            "poly 0 1 pdivide",
            "poly 0 0 psave pdivide",
            "poly 0 1 root -1 1",
            "poly 1 0 1 root 1 -1",
            "poly 1 0 1 root x",
            "poly 0 1 newton 0 2",
            "poly 1 0 1 newton 0 0",
            "poly 1 0 1 pshift 101",
            "poly 1 0 1 area x",
            "poly 1 0 1 grid x",
            "quadratic x",
            "lagrange 0",
            "lagrange 2 0 1 1 1 2",
            "lagrange 2 0 1 x",
        ]
        for text in errors:
            add(text)
        add("push 1 1 " * 65)
        add("progression 0 1 64 1 progression 0 1 1 1")
        add("depth " * 4097)
        add("poly 16 " + "1 " * 17 + "integrate")
        add("poly 9 " + "1 " * 10 + "psave pmul")
        add("poly 5 " + "1 " * 6 + "psave compose")
        add("poly 1 0 1000000000000 psave pmul")
        for operation in "+-*/^<>=!%":
            for a, b in [(-2, 2), (0, 1), (2, 0), (2, -2)]:
                unit = "1" if operation == "^" else "m"
                add(f"push {a} m push {b} {unit} {operation}")
        for operation in [
            "neg",
            "abs",
            "floor",
            "ceil",
            "round",
            "trunc",
            "sin",
            "cos",
            "tan",
            "asin",
            "acos",
            "atan",
            "exp",
            "log",
            "log10",
            "square",
            "cube",
            "sqrt",
            "cbrt",
            "reciprocal",
        ]:
            for value in [-1, 0, 1, 2]:
                add(f"push {value} 1 {operation}")
            add(operation)
        for op in ["sum", "mean", "sd", "minimum", "maximum", "range", "median"]:
            for count in [1, 2, 5, 6]:
                add(f"progression -1 2 {count} m {op}")
        for unit in [
            "1",
            "m",
            "cm",
            "mm",
            "km",
            "in",
            "ft",
            "kg",
            "g",
            "lb",
            "s",
            "ms",
            "min",
            "h",
            "K",
            "C",
            "F",
            "mol",
            "N",
            "J",
            "W",
            "Pa",
            "Hz",
            "L",
            "rad",
            "deg",
            "m/s^2",
            "kg*m/s^2",
            "m^0",
        ]:
            add(f"push 2 {unit} convert {unit}")
        commands = [
            "dup over swap rot all drop last show depth clear",
            "store a load a",
            "quadratic 1 0 -4",
            "quadratic 1 2 1",
            "quadratic 1 0 1",
            "quadratic 0 2 1",
            "quadratic 0 0 0",
            "quadratic 0 0 1",
            "fit 3 0 1 1 3 2 5",
            "interpolate 0 1 2 5 1",
            "weighted 3 1 1 2 2 3 1",
            "distance 2 0 3 0 4",
            "poly 2 -4 0 1 psave pshow peval 2 differentiate integrate pshow",
            "poly 2 -4 0 1 root 0 3",
            "poly 2 -4 0 1 root 2 3",
            "poly 2 -4 0 1 root 0 2",
            "poly 2 -2 0 1 newton 1 10",
            "poly 2 1 2 3 pshift 2 area -1 1 grid 0 1 4",
            "poly 1 1 1 psave poly 2 1 0 1 pdivide pshow",
            "poly 1 1 1 psave poly 2 1 0 1 compose pshow",
            "poly 1 1 1 psave padd",
            "lagrange 3 1.5 0 1 1 2 2 5",
            "push 4 m^2 sqrt",
            "push 8 m^3 cbrt",
            "push 2 m reciprocal",
        ]
        for i in range(290):
            text = (
                f"push {rng.randrange(-10, 11)} 1 push 2 1 push 3 1 "
                + commands[i % len(commands)]
            )
            args = (
                ["-p", str(i % 10)]
                + (["-t"] if i % 3 == 0 else [])
                + (["-q"] if i % 5 else [])
            )
            if i % 11 == 0:
                add(args=args + ["input"], files={"input": text.encode()})
            else:
                add(text, args=args)
    else:
        raise ValueError(name)
    if name == "unitforge":
        for text in [
            "+",
            "push 1 1 +",
            "store",
            "load {",
            "push 1",
            "convert m",
            'push "" m',
            "push 0 m convert cm",
            "push 1 m^-9",
            "push 1 m/bad",
            "push 1 m^-8*m^-8/m",
            "push 1 m^8*m^8 push 1 m *",
            "push 1 m^-8*m^-8 push 1 m /",
            "push 2 1 push 2 1 =",
            "push 2 1 push 2 1 !",
            "push 3 m push -1 m minimum",
            "poly 2 -2 0 1 root 0 2",
            "poly 2 -2 0 1 root 0 x",
            "poly 1 0 1 pshift x",
            "poly 2 1e12 1e12 1e12 pshift 100",
            "poly 1 0 0.000000000001 psave poly 1 0 1e12 pdivide",
            "poly 1 1e12 0.000001 psave poly 1 0 1000000 pdivide",
            "poly 1 0 1 psave poly 0 2 pdivide",
            "poly 1 0 1 compose",
            "poly 0 0 psave poly 1 1e12 1e12 compose",
            "poly 1 0 1 newton 0 2",
            "poly 1 1 1 peval x",
            "poly 1 0 1 progression 1e12 1e12 2 km",
            "poly 2 1 1 1 grid 1e12 1 1",
            "weighted x",
            "distance x",
            "push 2 m convert mm^8*mm^8/m^8/m^7",
        ]:
            add(text)
        for command, parameters in [
            ("interpolate", ["0", "1", "2", "3", "1"]),
            ("progression", ["0", "1", "2", "m"]),
            ("quadratic", ["1", "0", "-1"]),
            ("fit", ["2", "0", "0", "1", "1"]),
            ("weighted", ["1", "2", "1"]),
            ("distance", ["1", "0", "1"]),
            ("poly 1 1 1 area", ["0", "1"]),
            ("poly 1 1 1 grid", ["0", "1", "2"]),
            ("poly 1 1 1 newton", ["0", "2"]),
            ("lagrange", ["1", "0", "0", "1"]),
        ]:
            for count in range(len(parameters)):
                add(command + " " + " ".join(parameters[:count]))
    return out
