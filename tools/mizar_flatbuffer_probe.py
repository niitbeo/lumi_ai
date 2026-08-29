#!/usr/bin/env python3
"""Schema-free inspector for decrypted Mizar/Manis FlatBuffers.

This tool intentionally has no dependency on Manis.framework.  It validates
FlatBuffer tables using their vtables, shows root fields, follows table
references, and scans the payload for recurring table layouts.  The output is
used to recover the private Mizar schema before translating graphs to ONNX.
"""

from __future__ import annotations

import argparse
import collections
import struct
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Table:
    address: int
    vtable: int
    vtable_size: int
    object_size: int
    field_offsets: tuple[int, ...]


class Buffer:
    def __init__(self, data: bytes):
        self.data = data
        self.size = len(data)

    def u16(self, offset: int) -> int:
        return struct.unpack_from("<H", self.data, offset)[0]

    def u32(self, offset: int) -> int:
        return struct.unpack_from("<I", self.data, offset)[0]

    def i32(self, offset: int) -> int:
        return struct.unpack_from("<i", self.data, offset)[0]

    def in_bounds(self, offset: int, length: int = 1) -> bool:
        return 0 <= offset <= self.size - length

    def table(self, address: int) -> Table | None:
        if not self.in_bounds(address, 4):
            return None
        # FlatBuffers normally place a vtable before its object, but deduplicated
        # vtables may be shared and therefore appear after an object.  The first
        # word is signed for exactly that reason.
        distance = self.i32(address)
        if distance == 0:
            return None
        vtable = address - distance
        if not self.in_bounds(vtable, 4):
            return None
        vtable_size = self.u16(vtable)
        object_size = self.u16(vtable + 2)
        if vtable_size < 4 or vtable_size > 512 or vtable_size % 2:
            return None
        if object_size < 4 or object_size > 65535:
            return None
        if not self.in_bounds(vtable, vtable_size):
            return None
        if not self.in_bounds(address, object_size):
            return None
        offsets = tuple(
            self.u16(vtable + index)
            for index in range(4, vtable_size, 2)
        )
        if any(offset >= object_size for offset in offsets if offset):
            return None
        return Table(address, vtable, vtable_size, object_size, offsets)

    def relative_target(self, field_address: int) -> int | None:
        if not self.in_bounds(field_address, 4):
            return None
        relative = self.u32(field_address)
        if relative == 0:
            return None
        target = field_address + relative
        return target if self.in_bounds(target, 4) else None

    def printable_string(self, address: int) -> str | None:
        if not self.in_bounds(address, 5):
            return None
        length = self.u32(address)
        if length > 4096 or not self.in_bounds(address + 4, length + 1):
            return None
        raw = self.data[address + 4 : address + 4 + length]
        if self.data[address + 4 + length] != 0:
            return None
        if not raw or any(byte < 0x20 or byte > 0x7E for byte in raw):
            return None
        return raw.decode("ascii")

    def vector_length(self, address: int) -> int | None:
        if not self.in_bounds(address, 4):
            return None
        length = self.u32(address)
        if length > 10_000_000:
            return None
        return length


def vector_targets(buf: Buffer, address: int) -> tuple[int, list[tuple[int, int, Table | None, str | None]]] | None:
    length = buf.vector_length(address)
    if length is None or not buf.in_bounds(address + 4, length * 4):
        return None
    items: list[tuple[int, int, Table | None, str | None]] = []
    for index in range(length):
        element = address + 4 + index * 4
        relative = buf.u32(element)
        target = element + relative
        table = buf.table(target) if relative and buf.in_bounds(target, 4) else None
        text = buf.printable_string(target) if relative and buf.in_bounds(target, 4) else None
        items.append((relative, target, table, text))
    return length, items


def describe_target(buf: Buffer, address: int) -> str:
    table = buf.table(address)
    if table:
        return (
            f"table@0x{address:x}(fields={len(table.field_offsets)},"
            f" object={table.object_size}, vtable=0x{table.vtable:x})"
        )
    text = buf.printable_string(address)
    if text is not None:
        return f"string@0x{address:x}({text!r})"
    vector = vector_targets(buf, address)
    if vector is not None:
        length, items = vector
        table_refs = sum(item[2] is not None for item in items)
        string_refs = sum(item[3] is not None for item in items)
        if table_refs or string_refs:
            return (
                f"vector@0x{address:x}(length={length}, tables={table_refs}, "
                f"strings={string_refs})"
            )
        preview = ",".join(str(item[0]) for item in items[:6])
        suffix = ",..." if length > 6 else ""
        return f"vector@0x{address:x}(length={length}, u32=[{preview}{suffix}])"
    return f"data@0x{address:x}"


def dump_table(
    buf: Buffer,
    table: Table,
    depth: int,
    max_depth: int,
    visited: set[int],
    vector_items: int,
) -> None:
    indent = "  " * depth
    print(
        f"{indent}TABLE 0x{table.address:x}: vtable=0x{table.vtable:x} "
        f"vsize={table.vtable_size} osize={table.object_size} "
        f"fields={len(table.field_offsets)}"
    )
    if table.address in visited:
        print(f"{indent}  (already visited)")
        return
    visited.add(table.address)
    for index, offset in enumerate(table.field_offsets):
        if offset == 0:
            print(f"{indent}  [{index:02d}] absent")
            continue
        field = table.address + offset
        raw_u32 = buf.u32(field) if buf.in_bounds(field, 4) else 0
        raw_i32 = buf.i32(field) if buf.in_bounds(field, 4) else 0
        target = buf.relative_target(field)
        target_description = (
            " -> " + describe_target(buf, target) if target is not None else ""
        )
        print(
            f"{indent}  [{index:02d}] +0x{offset:02x} @0x{field:x} "
            f"u32={raw_u32} i32={raw_i32}{target_description}"
        )
        if depth < max_depth and target is not None:
            child = buf.table(target)
            if child:
                dump_table(
                    buf, child, depth + 1, max_depth, visited, vector_items
                )
            else:
                vector = vector_targets(buf, target)
                if vector is not None:
                    _, items = vector
                    followed = 0
                    for item_index, (_, _, item_table, _) in enumerate(items):
                        if item_table is None:
                            continue
                        print(
                            f"{indent}    vector[{item_index}] -> "
                            f"table@0x{item_table.address:x}"
                        )
                        dump_table(
                            buf,
                            item_table,
                            depth + 1,
                            max_depth,
                            visited,
                            vector_items,
                        )
                        followed += 1
                        if followed >= vector_items:
                            break


def scan_tables(buf: Buffer) -> list[Table]:
    tables: list[Table] = []
    seen: set[int] = set()
    for address in range(4, buf.size - 4, 4):
        table = buf.table(address)
        if table and table.address not in seen:
            seen.add(table.address)
            tables.append(table)
    return tables


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--vector-items", type=int, default=3)
    parser.add_argument(
        "--table",
        action="append",
        default=[],
        help="also dump a table at this decimal/hex offset (repeatable)",
    )
    args = parser.parse_args()

    data = args.model.read_bytes()
    buf = Buffer(data)
    if len(data) < 8:
        raise SystemExit("model is too small")
    root_address = buf.u32(0)
    root = buf.table(root_address)
    print(f"file={args.model} bytes={len(data)} root=0x{root_address:x}")
    if root is None:
        raise SystemExit("root is not a valid FlatBuffer table")
    dump_table(
        buf,
        root,
        0,
        max(args.depth, 0),
        set(),
        max(args.vector_items, 0),
    )
    for raw_address in args.table:
        address = int(raw_address, 0)
        extra = buf.table(address)
        print(f"\nEXTRA table=0x{address:x}")
        if extra is None:
            print("  not a valid table")
        else:
            dump_table(
                buf,
                extra,
                0,
                max(args.depth, 0),
                set(),
                max(args.vector_items, 0),
            )

    if args.scan:
        tables = scan_tables(buf)
        layouts = collections.Counter(
            (table.vtable_size, table.object_size, table.field_offsets)
            for table in tables
        )
        print(f"\nSCAN valid_aligned_tables={len(tables)} layouts={len(layouts)}")
        for (vsize, osize, offsets), count in layouts.most_common(args.top):
            rendered = ",".join(str(value) for value in offsets)
            print(
                f"  count={count:5d} vsize={vsize:3d} osize={osize:4d} "
                f"offsets=[{rendered}]"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
