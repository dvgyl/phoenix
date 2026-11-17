"""Generate image and record codec cases with independent packet encoding."""

import base64
import binascii

from generate_cases import case


def image_record_cases(name, rng):
    out = []

    def add(data="", args=(), files=None):
        out.append(case(args, data.encode() if isinstance(data, str) else data, files))

    for args in [["-?"], ["absent"], ["a", "b"]]:
        add(args=args)
    if name == "chromapath":
        base = "C3 2 2 255 0 0 0 255 0 0 0 255 128 128 128\n"
        for data in [
            "",
            "bad",
            "C3 x",
            "C3 0 1",
            "C3 33 1",
            "C3 1 0",
            "C3 1 33",
            "C3 1 1 -1 0 0",
            "C3 1 1 0 256 0",
            "C3 1 1 0 0 -1",
            "C3 1 1 0 0 256",
            "C3 1 1 0 -1 0",
            "C3 1 1 256 0 0",
            "C3 1 1 0 0",
            "C1 1 1 x",
            "C1 1 1 -1",
            "C1 1 1 256",
            "CP 1 1 0",
            "CP 1 1 17",
            "CP 1 1 1 0 0 x",
            "CP 1 1 1 0 0 0 -1",
            "CP 1 1 1 0 0 0 1",
            "CP 1 1 1 0 0 0 0",
        ]:
            add(data)
        errors = [
            "bad",
            "dot",
            "dot -65 0 0 0 0",
            "dot 0 65 0 0 0",
            "line 0 0",
            "circle 0 0 -1 0 0 0",
            "disk 0 0 65 0 0 0",
            "dot 0 0 0 -1 0",
            "blend",
            "blend 0 0 0 -1",
            "blend 0 0 0 256",
            "replace 0 0 0 0 0 0 -1",
            "replace 0 0 0 0 0 0 766",
            "gradient 0 0 0 1 1 1 2",
            "mosaic 0",
            "mosaic 33",
            "paste",
            "paste absent 0 0",
            "crop",
            "crop -1 0 1 1",
            "crop 0 -1 1 1",
            "crop 0 0 0 1",
            "crop 0 0 1 0",
            "crop 1 0 2 1",
            "crop 0 1 1 2",
            "resize",
            "resize 0 1",
            "resize 1 0",
            "resize 33 1",
            "resize 1 33",
            "mirror -1",
            "mirror 2",
            "turn",
            "kernel x",
            "kernel -1",
            "kernel 8",
            "quantize 1",
            "quantize 257",
            "cluster 0",
            "cluster 17",
            "gamma 0",
            "hue nan",
            "gamma -1",
            "save",
            "load",
            "save absent/out",
            "load absent",
            "bounds -1",
            "bounds 256",
        ]
        for error in errors:
            add(base + error)
        add(base, args=["-o", "missing/out"])
        add(base + "stats " * 4097)
        commands = [
            "invert",
            "gray",
            "sepia",
            "cycle",
            "red",
            "green",
            "blue",
            "solar",
            "chroma",
            "stats",
            "histogram",
            "dither",
            "palette",
            "autolevel",
            "bounds 0",
            "bounds 255",
            "dot -1 -1 0 0 0",
            "dot 0 0 255 0 0",
            "line 0 0 6 5 255 255 0",
            "line 5 5 -2 2 0 255 255",
            "rect 4 5 0 0 255 0 255",
            "box -1 -1 1 1 0 0 0",
            "circle 2 2 0 255 0 0",
            "circle 2 2 3 255 255 0",
            "disk 1 1 2 0 255 0",
            "flood 0 0 255 0 0",
            "flood -1 0 0 0 0",
            "blend 128 64 32 128",
            "replace 0 0 0 255 255 255 765",
            "replace 0 0 0 255 255 255 0",
            "gradient 0 0 0 255 128 64 0",
            "gradient 255 0 0 0 0 255 1",
            "mosaic 3",
            "paste other -1 1",
            "crop 0 0 1 1",
            "resize 8 6",
            "mirror 0",
            "mirror 1",
            "turn -1",
            "turn 4",
            "quantize 4",
            "cluster 3",
            "hue -90",
            "hue 120",
            "saturation 0",
            "saturation 2",
            "value 0.5",
            "bias -300",
            "contrast -1",
            "gamma 2",
            "save result load result",
            "load other",
        ]
        for k in range(8):
            add(base + f"kernel {k}")
        for hue in range(0, 360, 30):
            add(base + f"hue {hue}")
        for i in range(410):
            w = rng.randrange(1, 8)
            h = rng.randrange(1, 8)
            palette = [
                (255, 0, 0),
                (0, 255, 0),
                (0, 0, 255),
                (0, 0, 0),
                (255, 255, 255),
                (128, 128, 128),
                (12, 23, 34),
            ]
            colors = [rng.choice(palette) for _ in range(w * h)]
            data = (
                f"C3 {w} {h} "
                + " ".join(str(c) for color in colors for c in color)
                + "\n"
                + commands[i % len(commands)]
            )
            args = (
                (["-q"] if i % 3 else [])
                + (["-r"] if i % 5 == 0 else [])
                + (["-g"] if i % 7 == 0 else [])
            )
            if i % 13 == 0:
                args += ["-o", "result"]
            files = {"other": b"C1 2 2 0 255 128 64"}
            if i % 11 == 0:
                files["input"] = data.encode()
                add(args=args + ["input"], files=files)
            else:
                add(data, args=args, files=files)
        add("C1 2 2 0 0 0 0 flood 0 0 0 0 0 flood 0 0 255 255 255")
        add("C1 2 2 0 0 0 0 bounds 255 autolevel palette")
        add("C1 32 1 " + " ".join(map(str, range(32))))
        add("CP 2 1 2 10 20 30 40 50 60 0 1")
        add("C3 1 1 12 34 56 blend 100 110 120 0")
        add("C1 3 1 0 0 0 gradient 10 20 60 40 50 20 0")
        add("C3 1 1 10 20 30 bias 2")
        add("C1 4 2 " + "111 " * 8 + "dither")
        add("C1 3 4 " + "100 " * 12 + "dither")
        add("C3 1 1 255 0 255 hue 0")
        add("C3 1 1 251 0 0", args=["-g"])
    elif name == "recordloom":
        base = (
            'put key_a 10 3 " Ab c " put key_b -5 128 "a\\nb" put key_c 10 3 " Ab c "\n'
        )
        for data in [
            "",
            "# comment\n",
            "bad",
            '"unclosed',
            '"\\x0Z"',
            '"\\xZ0"',
            '"\\x00"',
            '"\\z"',
            '"' + "x" * 256 + '"',
        ]:
            add(data)
        for escaped in [
            r"\n",
            r"\t",
            r"\r",
            r"\s",
            r"\"",
            r"\\",
            r"\#",
            r"\x01",
            r"\xFF",
            r"\xAb",
        ]:
            add('put a 1 0 "x' + escaped + 'y"')
        errors = [
            "put",
            "put ? 0 0 x",
            "put a x 0 x",
            "put a 1000001 0 x",
            "put a 0 -1 x",
            "put a 0 256 x",
            "put a 0 0 " + "x" * 128,
            "get absent",
            "get",
            "drop absent",
            "add key_a x",
            "add key_a 1000000",
            "multiply key_a 1000000",
            "rename key_a ?",
            "rename key_a key_b",
            "rename absent a",
            "filter 1 -1",
            "flags -1 0",
            "flags 0 256",
            "sort wrong",
            "restore",
            "pack",
            "pack out -1",
            "pack out 3",
            "pack out 0 -1",
            "pack out 0 2",
            "pack missing/out 0 0",
            "unpack absent 0",
            "load absent",
            "save missing/out",
            "split existing",
            "prefix " + "x" * 127,
            'replace "" x',
            'replace a "' + "x" * 127 + '"',
            "histogram 0 0",
            "group 256",
            "rotate x",
        ]
        for error in errors:
            add(base + error, files={"existing": None})
        add(" ".join(f"put k{i} 1 0 x" for i in range(65)))
        add("clear " * 4097)
        add("put a 1 0 x", args=["-l", "absent"])
        add("load input", files={"input": b"a 1 0 x\na 2 1 y\n"})
        for content in [
            b"a",
            b"a x 0 x",
            b"? 1 0 x",
            b"a 0 -1 x",
            b"a 0 256 x",
            b'"unclosed',
            b'a 1 0 "\\z"',
        ]:
            add("load input", files={"input": content})
        commands = [
            "get key_a",
            "drop key_b",
            "add key_a -20",
            "multiply key_b -2",
            "rename key_c new",
            "filter -10 0",
            "filter 100 200",
            "flags 255 0",
            "flags 128 128",
            "prefix PRE",
            "trim",
            "dedup",
            "upper",
            "lower",
            "reverse",
            "sort key",
            "sort number",
            "sort length",
            "snapshot clear restore",
            "stats",
            "show",
            "split parts",
            "save rows clear load rows",
            "save rows clear merge rows",
            "replace a xy",
            "replace absent x",
            'replace a ""',
            "histogram -5 2",
            "group 3",
            "rotate -1",
            "rotate 4",
            "clear rotate 1",
        ]
        for i in range(360):
            text = base + commands[i % len(commands)]
            if i % 4 == 0:
                encoding = i % 3
                text += (
                    f" pack packet {encoding} {i % 2}"
                    f" clear unpack packet {encoding} stats"
                )
            args = (["-q"] if i % 3 else []) + (["-r"] if i % 5 else [])
            if i % 11 == 0:
                add(args=args + ["input"], files={"input": text.encode()})
            else:
                add(text, args=args)

        def varint(value):
            result = bytearray()
            while value > 127:
                result.append((value & 127) | 128)
                value >>= 7
            result.append(value)
            return bytes(result)

        def packed(rows, delta):
            packet = b"RL\1" + bytes([delta, len(rows)])
            old_key = b""
            old_text = b""
            old_number = 0
            for key, number, flags, text in rows:
                for current, previous, is_key in [
                    (key, old_key, True),
                    (text, old_text, False),
                ]:
                    prefix = 0
                    while (
                        prefix < min(len(current), len(previous))
                        and current[prefix] == previous[prefix]
                    ):
                        prefix += 1
                    packet += bytes([prefix, len(current) - prefix]) + current[prefix:]
                    if is_key:
                        value = number - old_number if delta else number
                        packet += varint(
                            value * 2 if value >= 0 else -value * 2 - 1
                        ) + bytes([flags])
                old_key, old_number, old_text = key, number, text
            return packet

        def with_crc(packet):
            return packet + binascii.crc_hqx(packet, 0xFFFF).to_bytes(2, "big")

        def packet_case(packet, encoding):
            if encoding == 1:
                packet = packet.hex().upper().encode() + b"\n \t"
            elif encoding == 2:
                packet = base64.urlsafe_b64encode(packet).rstrip(b"=")
            add(f"unpack input {encoding} stats", files={"input": packet})

        for i in range(100):
            rows = [
                (
                    f"key_{j}".encode(),
                    rng.randrange(-1000000, 1000001),
                    rng.randrange(256),
                    rng.choice([b"", b"x", b"prefix_a", b"prefix_b", b'\xff\x01\\"\n']),
                )
                for j in range(rng.randrange(12))
            ]
            packet_case(with_crc(packed(rows, i % 2)), i % 3)
        valid = packed([(b"a", 1, 2, b"text")], 1)
        # Recompute the checksum to test the packet parser after each change.
        for index, values in [
            (0, [0]),
            (1, [0]),
            (2, [0, 2]),
            (3, [2]),
            (4, [65]),
            (5, [1]),
            (6, [32]),
            (7, [0, 63]),
            (8, [255]),
            (10, [1]),
            (11, [128]),
            (12, [0]),
        ]:
            for value in values:
                broken = bytearray(valid)
                broken[index] = value
                packet_case(with_crc(bytes(broken)), 0)
        for length in range(len(valid)):
            packet_case(with_crc(valid[:length]), 0)
        packet_case(with_crc(valid + b"x"), 0)
        packet_case(with_crc(packed([(b"a", 1, 0, b""), (b"a", 2, 0, b"")], 0)), 0)
        for encoding, data in [
            (0, b"x" * 16385),
            (1, b"00" * 16385),
            (1, b"0"),
            (1, b"gg"),
            (2, b"A"),
            (2, b"AB"),
            (2, b"!"),
            (2, b"\0"),
            (2, b"A" * 22000),
        ]:
            add(f"unpack input {encoding}", files={"input": data})
        packet_case(b"bad", 0)
        packet_case(with_crc(valid)[:-1] + b"x", 0)
    else:
        raise ValueError(name)
    return out
