#!/usr/bin/env python3
"""Recover Mizar operator IDs by correlating Manis graphs with CoreML twins.

Twenty bundled models exist in both formats.  Their layer names and tensor IDs
are preserved by the official conversion (``convert_from_manis=yes``), which
makes them a deterministic oracle for mapping private Mizar op IDs to public
CoreML layer types.  This script performs that correlation without loading
Manis.framework or CoreML.framework.
"""

from __future__ import annotations

import argparse
import collections
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from mizar_flatbuffer_probe import Buffer, Table, vector_targets


@dataclass(frozen=True)
class MizarOp:
    type_id: int
    name_id: int
    inputs: tuple[int, ...]
    outputs: tuple[int, ...]


@dataclass(frozen=True)
class CoreMLLayer:
    name_id: int
    inputs: tuple[int, ...]
    outputs: tuple[int, ...]
    layer_field: int


def field_address(table: Table, index: int) -> int | None:
    if index >= len(table.field_offsets):
        return None
    offset = table.field_offsets[index]
    return table.address + offset if offset else None


def field_target(buf: Buffer, table: Table, index: int) -> int | None:
    address = field_address(table, index)
    return buf.relative_target(address) if address is not None else None


def table_vector(buf: Buffer, address: int | None) -> list[Table]:
    if address is None:
        return []
    vector = vector_targets(buf, address)
    if vector is None:
        return []
    return [item[2] for item in vector[1] if item[2] is not None]


def u32_vector(buf: Buffer, address: int | None) -> tuple[int, ...]:
    if address is None:
        return ()
    length = buf.vector_length(address)
    if length is None or not buf.in_bounds(address + 4, length * 4):
        return ()
    return tuple(buf.u32(address + 4 + index * 4) for index in range(length))


def parse_mizar(path: Path) -> list[MizarOp]:
    buf = Buffer(path.read_bytes())
    root = buf.table(buf.u32(0))
    if root is None:
        raise ValueError(f"invalid Mizar root: {path}")
    graph_vector = field_target(buf, root, 1)
    operations: list[MizarOp] = []
    for graph in table_vector(buf, graph_vector):
        op_vector = field_target(buf, graph, 1)
        for op in table_vector(buf, op_vector):
            type_at = field_address(op, 0)
            name_at = field_address(op, 1)
            if type_at is None or name_at is None:
                continue
            operations.append(
                MizarOp(
                    type_id=buf.u32(type_at),
                    name_id=buf.u32(name_at),
                    inputs=u32_vector(buf, field_target(buf, op, 3)),
                    outputs=u32_vector(buf, field_target(buf, op, 4)),
                )
            )
    return operations


def read_varint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        if offset >= len(data) or shift >= 70:
            raise ValueError("invalid protobuf varint")
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, offset
        shift += 7


def protobuf_fields(data: bytes) -> Iterator[tuple[int, int, int | bytes]]:
    offset = 0
    while offset < len(data):
        key, offset = read_varint(data, offset)
        number, wire = key >> 3, key & 7
        if number == 0:
            raise ValueError("protobuf field number zero")
        if wire == 0:
            value, offset = read_varint(data, offset)
            yield number, wire, value
        elif wire == 1:
            end = offset + 8
            if end > len(data):
                raise ValueError("truncated fixed64")
            yield number, wire, data[offset:end]
            offset = end
        elif wire == 2:
            length, offset = read_varint(data, offset)
            end = offset + length
            if end > len(data):
                raise ValueError("truncated length-delimited field")
            yield number, wire, data[offset:end]
            offset = end
        elif wire == 5:
            end = offset + 4
            if end > len(data):
                raise ValueError("truncated fixed32")
            yield number, wire, data[offset:end]
            offset = end
        else:
            raise ValueError(f"unsupported protobuf wire type {wire}")


def decimal_id(raw: bytes) -> int | None:
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        return None
    return int(text) if text.isdecimal() else None


def parse_coreml(path: Path) -> list[CoreMLLayer]:
    top = list(protobuf_fields(path.read_bytes()))
    networks = [
        value
        for number, wire, value in top
        if number in (500, 501, 502) and wire == 2 and isinstance(value, bytes)
    ]
    if not networks:
        raise ValueError(f"CoreML neural network message not found: {path}")
    layers: list[CoreMLLayer] = []
    for network in networks:
        for number, wire, raw_layer in protobuf_fields(network):
            if number != 1 or wire != 2 or not isinstance(raw_layer, bytes):
                continue
            name: int | None = None
            inputs: list[int] = []
            outputs: list[int] = []
            layer_fields: list[int] = []
            try:
                fields = list(protobuf_fields(raw_layer))
            except ValueError:
                continue
            for layer_number, layer_wire, value in fields:
                if layer_wire == 2 and isinstance(value, bytes):
                    if layer_number == 1:
                        name = decimal_id(value)
                    elif layer_number == 2:
                        tensor = decimal_id(value)
                        if tensor is not None:
                            inputs.append(tensor)
                    elif layer_number == 3:
                        tensor = decimal_id(value)
                        if tensor is not None:
                            outputs.append(tensor)
                    elif layer_number >= 100:
                        layer_fields.append(layer_number)
            if name is not None and len(layer_fields) == 1:
                layers.append(
                    CoreMLLayer(
                        name_id=name,
                        inputs=tuple(inputs),
                        outputs=tuple(outputs),
                        layer_field=layer_fields[0],
                    )
                )
    return layers


def model_stem(path: Path) -> str:
    name = path.name
    for suffix in (".manis.decoded", ".manisa.mlmodel"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manis-root", type=Path, default=Path("manis_decrypted"))
    parser.add_argument("--coreml-root", type=Path, default=Path("coreml_decrypted"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    manis = {model_stem(path): path for path in args.manis_root.rglob("*.manis.decoded")}
    coreml = {model_stem(path): path for path in args.coreml_root.rglob("*.manisa.mlmodel")}
    paired = sorted(manis.keys() & coreml.keys())

    evidence: dict[int, collections.Counter[int]] = collections.defaultdict(collections.Counter)
    examples: dict[int, list[dict[str, object]]] = collections.defaultdict(list)
    report_models: list[dict[str, object]] = []
    for stem in paired:
        mizar_ops = parse_mizar(manis[stem])
        coreml_layers = parse_coreml(coreml[stem])
        by_name = {layer.name_id: layer for layer in coreml_layers}
        matched = 0
        io_matched = 0
        for op in mizar_ops:
            layer = by_name.get(op.name_id)
            if layer is None:
                continue
            matched += 1
            if op.inputs == layer.inputs and op.outputs == layer.outputs:
                io_matched += 1
            evidence[op.type_id][layer.layer_field] += 1
            if len(examples[op.type_id]) < 5:
                examples[op.type_id].append(
                    {
                        "model": stem,
                        "layer_name": op.name_id,
                        "coreml_field": layer.layer_field,
                        "io_equal": op.inputs == layer.inputs and op.outputs == layer.outputs,
                    }
                )
        report_models.append(
            {
                "model": stem,
                "mizar_ops": len(mizar_ops),
                "coreml_layers": len(coreml_layers),
                "matched_by_name": matched,
                "matched_io": io_matched,
            }
        )

    op_types: list[dict[str, object]] = []
    ambiguous = 0
    for type_id in sorted(evidence):
        counts = evidence[type_id]
        if len(counts) != 1:
            ambiguous += 1
        op_types.append(
            {
                "mizar_type_id": type_id,
                "coreml_fields": {str(key): value for key, value in sorted(counts.items())},
                "unambiguous": len(counts) == 1,
                "examples": examples[type_id],
            }
        )

    recovered_ids = set(evidence)
    mizar_only_details: list[dict[str, object]] = []
    for stem in sorted(manis.keys() - coreml.keys()):
        operations = parse_mizar(manis[stem])
        counts = collections.Counter(op.type_id for op in operations)
        known = sum(count for type_id, count in counts.items() if type_id in recovered_ids)
        mizar_only_details.append(
            {
                "model": stem,
                "operations": len(operations),
                "known_operations": known,
                "unknown_operations": len(operations) - known,
                "type_ids": {str(key): value for key, value in sorted(counts.items())},
                "unknown_type_ids": sorted(key for key in counts if key not in recovered_ids),
            }
        )

    result = {
        "summary": {
            "paired_models": len(paired),
            "mizar_only_models": len(manis.keys() - coreml.keys()),
            "recovered_type_ids": len(op_types),
            "ambiguous_type_ids": ambiguous,
            "matched_layers": sum(item["matched_by_name"] for item in report_models),
            "matched_io": sum(item["matched_io"] for item in report_models),
        },
        "models": report_models,
        "operator_types": op_types,
        "mizar_only": sorted(manis.keys() - coreml.keys()),
        "mizar_only_details": mizar_only_details,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
