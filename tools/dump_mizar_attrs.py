#!/usr/bin/env python3
"""Dump every FlatBuffer field of selected Mizar operator attributes.

This is a schema-recovery aid.  It deliberately prints both scalar and
relative interpretations because an attribute payload can be a scalar, a
vector, a byte blob, or a nested table depending on its serialized type.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from mizar_flatbuffer_probe import Buffer
from mizar_schema_recovery import field_address, field_target, table_vector, u32_vector


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("--op-type", type=int, action="append", default=[])
    parser.add_argument("--op-name", type=int, action="append", default=[])
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    buf = Buffer(args.model.read_bytes())
    root = buf.table(buf.u32(0))
    if root is None:
        raise SystemExit("invalid root")
    selected = set(args.op_type)
    selected_names = set(args.op_name)
    emitted = 0
    for graph in table_vector(buf, field_target(buf, root, 1)):
        for op in table_vector(buf, field_target(buf, graph, 1)):
            type_at = field_address(op, 0)
            name_at = field_address(op, 1)
            if type_at is None or name_at is None:
                continue
            type_id = buf.u32(type_at)
            if selected and type_id not in selected:
                continue
            name_id = buf.u32(name_at)
            if selected_names and name_id not in selected_names:
                continue
            print(f"op type={type_id} name={name_id}")
            for attr in table_vector(buf, field_target(buf, op, 5)):
                key_at = field_address(attr, 0)
                key = buf.u32(key_at) if key_at is not None else None
                print(
                    f"  attr key={key} table=0x{attr.address:x} "
                    f"vsize={attr.vtable_size} osize={attr.object_size} "
                    f"offsets={attr.field_offsets}"
                )
                for index, offset in enumerate(attr.field_offsets):
                    if not offset:
                        print(f"    field[{index}]: absent")
                        continue
                    address = attr.address + offset
                    raw = buf.u32(address)
                    as_float = struct.unpack("<f", struct.pack("<I", raw))[0]
                    target = buf.relative_target(address)
                    details = ""
                    if target is not None:
                        length = buf.vector_length(target)
                        if length is not None and buf.in_bounds(target + 4, length):
                            byte_preview = buf.data[target + 4 : target + 4 + min(length, 32)].hex()
                            details = f" target=0x{target:x} len={length} bytes={byte_preview}"
                    print(f"    field[{index}] u32={raw} f32={as_float!r}{details}")
                values = u32_vector(buf, field_target(buf, attr, 2))
                if values:
                    print(f"    parsed_u32_values={values[:16]}")
            emitted += 1
            if emitted >= args.limit:
                return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
