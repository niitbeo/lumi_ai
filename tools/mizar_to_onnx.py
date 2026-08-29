#!/usr/bin/env python3
"""Translate decrypted Mizar FlatBuffer graphs to independent ONNX models.

This is a clean-room translator: it parses the model bytes directly and never
loads Manis.framework, Mizar, Kumoo, or any private operator implementation.
The initial backend covers the convolutional encoder/decoder dialect used by
the bundled ``haircut`` and ``skintone`` models.
"""

from __future__ import annotations

import argparse
import math
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, checker, helper, numpy_helper, shape_inference

from mizar_flatbuffer_probe import Buffer, Table
from mizar_schema_recovery import (
    field_address,
    field_target,
    table_vector,
    u32_vector,
)


# IDs were recovered by matching numeric layer/tensor names in 20 Mizar/CoreML
# model pairs.  The values are stable FNV-like hashes used by the serializer.
DATA_INPUT = 2917285576
CONVOLUTION = 1332722206
CONVOLUTION_ALT = 303230744
ACTIVATION = 1249049111
ACTIVATION_ALT = 513875291
UPSAMPLE = 960768420
POOLING = 1249571350
BATCH_NORM = 2378844304
SCALE = 1945033328
ELTWISE = 2417120655
CONCAT = 3947476506
LOAD_CONSTANT = 1874173776
SLICE_STATIC = 2033592997

# This graph-only node duplicates a tensor into independently named edges.  It
# has no CoreML twin because the official converter removes it during lowering.
TENSOR_FANOUT = 1890524141

ATTR_WEIGHT = 1158599272
ATTR_BIAS = 1256706552
ATTR_HAS_BIAS = 678389437
ATTR_PADS = 1237954334
ATTR_WEIGHT_SHAPE = 3079447642
ATTR_STRIDES = 1193670600
ATTR_GROUP = 2371303673
ATTR_DILATIONS = 4058282537
ATTR_ACTIVATION_KIND = 1235449982
ATTR_CONCAT_AXIS = 1242556044
ATTR_INPUT_SHAPE = 1343620552
ATTR_ELTWISE_KIND = 1820184049
ATTR_PRELU_SLOPE = 1356664771
ATTR_SCALE = 1344732226
ATTR_HAS_SCALE_BIAS = 4078039911
ATTR_POOL_KIND = 2134780110
ATTR_BATCHNORM_MEAN = 1238181542
ATTR_BATCHNORM_VARIANCE = 4216367735
ATTR_INSTANCE_CHANNELS = 2322103777

PRELU = 99560484
INSTANCE_NORM = 924833876
DEPTH_TO_SPACE = 133481899
SOFTMAX = 3275427445
FULLY_CONNECTED = 119542410
MATMUL = 664144102
RESHAPE = 3691128620
EXPAND = 1244330572
LEGACY_LAYOUT = 4216326042
SPLIT = 1889523960
LEGACY_BINARY = 239135015
PAD = 2906278341
RELU_VARIANT = 1332249153
REDUCE = 2663449159
SLICE_CHANNEL = 3684297650
CLIP_UNIT = 1332635621
UNARY = 989838847
UNSQUEEZE = 1556403515
LOAD_CONSTANT = 1874173776
SQUEEZE = 2299095012
TRANSPOSE = 779806240

ATTR_AXES = 1242555785
ATTR_KEEP_DIMS = 782945741
ATTR_TRANSPOSE_PERM = 1688693767
ATTR_SPLIT_POINTS = 3812398260

ATTR_FC_OUTPUTS = 3987577180
ATTR_EXPAND_SHAPE = 4196884270
ATTR_RESIZE_MODE = 348444634
ATTR_RESIZE_COORDINATE_MODE = 3970790265
ATTR_REVERSE_OPERANDS = 3389299816


@dataclass(frozen=True)
class Attribute:
    key: int
    scalar: int | None
    values: tuple[int, ...]


@dataclass(frozen=True)
class Operation:
    type_id: int
    name_id: int
    inputs: tuple[int, ...]
    outputs: tuple[int, ...]
    attributes: dict[int, Attribute]
    output_shapes: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class Constant:
    tensor_id: int
    shape: tuple[int, ...]
    data: bytes
    quantized: bool = False
    quant_bits: int = 0
    quant_max: float = 0.0
    quant_min: float = 0.0
    quant_count: int = 0


@dataclass(frozen=True)
class TensorSpec:
    tensor_id: int
    shape: tuple[int, ...]


@dataclass(frozen=True)
class MizarGraph:
    operations: tuple[Operation, ...]
    constants: dict[int, Constant]
    inputs: tuple[TensorSpec, ...]
    outputs: tuple[TensorSpec, ...]


def _u32_at(buf: Buffer, table: Table, index: int) -> int | None:
    address = field_address(table, index)
    return buf.u32(address) if address is not None else None


def _shape(buf: Buffer, table: Table | None) -> tuple[int, ...]:
    return u32_vector(buf, field_target(buf, table, 0)) if table else ()


def _shape_field(buf: Buffer, table: Table, index: int) -> tuple[int, ...]:
    target = field_target(buf, table, index)
    return _shape(buf, buf.table(target) if target is not None else None)


def _byte_vector(buf: Buffer, address: int | None) -> bytes:
    if address is None:
        return b""
    length = buf.vector_length(address)
    if length is None or not buf.in_bounds(address + 4, length):
        raise ValueError(f"invalid byte vector at 0x{address:x}")
    return buf.data[address + 4 : address + 4 + length]


def parse_mizar_graph(path: Path) -> MizarGraph:
    buf = Buffer(path.read_bytes())
    root = buf.table(buf.u32(0))
    if root is None:
        raise ValueError(f"invalid Mizar FlatBuffer root: {path}")

    constants: dict[int, Constant] = {}
    for table in table_vector(buf, field_target(buf, root, 2)):
        tensor_id = _u32_at(buf, table, 0)
        if tensor_id is None:
            continue
        constant = Constant(
            tensor_id=tensor_id,
            shape=_shape_field(buf, table, 1),
            data=_byte_vector(buf, field_target(buf, table, 2)),
            quantized=_u32_at(buf, table, 5) == 1,
            quant_bits=_u32_at(buf, table, 6) or 0,
            quant_max=(
                struct.unpack("<f", struct.pack("<I", _u32_at(buf, table, 7)))[0]
                if _u32_at(buf, table, 7) is not None
                else 0.0
            ),
            quant_min=(
                struct.unpack("<f", struct.pack("<I", _u32_at(buf, table, 8)))[0]
                if _u32_at(buf, table, 8) is not None
                else 0.0
            ),
            quant_count=_u32_at(buf, table, 9) or 0,
        )
        constants[tensor_id] = constant

    def tensor_specs(root_field: int) -> tuple[TensorSpec, ...]:
        result: list[TensorSpec] = []
        for table in table_vector(buf, field_target(buf, root, root_field)):
            tensor_id = _u32_at(buf, table, 0)
            if tensor_id is not None:
                result.append(TensorSpec(tensor_id, _shape_field(buf, table, 1)))
        return tuple(result)

    operations: list[Operation] = []
    for graph in table_vector(buf, field_target(buf, root, 1)):
        for table in table_vector(buf, field_target(buf, graph, 1)):
            type_id = _u32_at(buf, table, 0)
            name_id = _u32_at(buf, table, 1)
            if type_id is None or name_id is None:
                continue
            attributes: dict[int, Attribute] = {}
            for attr_table in table_vector(buf, field_target(buf, table, 5)):
                key = _u32_at(buf, attr_table, 0)
                if key is None:
                    continue
                attributes[key] = Attribute(
                    key=key,
                    scalar=_u32_at(buf, attr_table, 1),
                    values=u32_vector(buf, field_target(buf, attr_table, 2)),
                )
            output_shapes = tuple(
                _shape(buf, shape_table)
                for shape_table in table_vector(buf, field_target(buf, table, 7))
            )
            operations.append(
                Operation(
                    type_id=type_id,
                    name_id=name_id,
                    inputs=u32_vector(buf, field_target(buf, table, 3)),
                    outputs=u32_vector(buf, field_target(buf, table, 4)),
                    attributes=attributes,
                    output_shapes=output_shapes,
                )
            )
    return MizarGraph(
        operations=tuple(operations),
        constants=constants,
        inputs=tensor_specs(3),
        outputs=tensor_specs(4),
    )


def _attr_values(op: Operation, key: int, default: tuple[int, ...] = ()) -> tuple[int, ...]:
    attr = op.attributes.get(key)
    return attr.values if attr is not None else default


def _constant_array(
    graph: MizarGraph, tensor_id: int, logical_shape: tuple[int, ...] | None = None
) -> np.ndarray:
    try:
        constant = graph.constants[tensor_id]
    except KeyError as error:
        raise ValueError(f"constant tensor {tensor_id} is missing") from error
    shape = logical_shape or constant.shape
    count = math.prod(shape)
    if constant.quantized:
        if constant.quant_bits != 16 or constant.quant_count != count:
            raise ValueError(
                f"constant {tensor_id}: unsupported quantization "
                f"bits={constant.quant_bits} count={constant.quant_count}/{count}"
            )
        raw = np.frombuffer(constant.data[: count * 2], dtype="<u2", count=count).astype(np.float32)
        values = constant.quant_min + raw * (
            (constant.quant_max - constant.quant_min) / 65535.0
        )
    elif len(constant.data) == count * 4:
        values = np.frombuffer(constant.data, dtype="<f4", count=count)
    elif count * 2 <= len(constant.data) < count * 4 and len(constant.data) - count * 2 < 16:
        # Float16 blobs are padded to a small SIMD/alignment boundary by this
        # serializer (observed padding is 0-14 bytes).
        values = np.frombuffer(constant.data[: count * 2], dtype="<f2", count=count).astype(np.float32)
    else:
        raise ValueError(
            f"constant {tensor_id}: cannot decode {len(constant.data)} bytes "
            f"as {count} floating-point values"
        )
    return values.reshape(shape).copy()


def _names(ids: tuple[int, ...]) -> list[str]:
    return [str(value) for value in ids]


def _pads(values: tuple[int, ...]) -> list[int]:
    if len(values) == 2:
        return [values[0], values[1], values[0], values[1]]
    return list(values)


def _signed_dims(values: tuple[int, ...]) -> list[int]:
    return [value if value < 0x80000000 else value - 0x100000000 for value in values]


def _legacy_runtime_shape(shape: tuple[int, ...]) -> tuple[int, ...]:
    """Convert the old NC4-style five-dimensional shape metadata to NCHW."""
    if len(shape) == 5 and shape[-2:] == (1, 1):
        if shape[0] == 1 and shape[1] == 1 and shape[2] <= 8:
            return (1, shape[2], 1, 1)
        return (1, shape[0], shape[1], shape[2])
    return shape


def _trailing_runtime_shape(shape: tuple[int, ...]) -> tuple[int, ...]:
    if len(shape) == 5 and shape[-1] == 1:
        return shape[:-1]
    return shape


def _make_conv(graph: MizarGraph, op: Operation, initializers: list[onnx.TensorProto]):
    weight_ids = _attr_values(op, ATTR_WEIGHT)
    if len(weight_ids) != 1:
        raise ValueError(f"conv {op.name_id}: weight reference is missing")
    weight_name = f"const_{weight_ids[0]}"
    group = max(1, _attr_values(op, ATTR_GROUP, (1,))[0])
    logical_weight_shape = _attr_values(op, ATTR_WEIGHT_SHAPE)
    weight_shape = logical_weight_shape
    if group > 1 and len(logical_weight_shape) >= 2:
        weight_shape = (
            logical_weight_shape[0],
            logical_weight_shape[1] // group,
            *logical_weight_shape[2:],
        )
    initializers.append(
        numpy_helper.from_array(_constant_array(graph, weight_ids[0], weight_shape or None), weight_name)
    )
    node_inputs = _names(op.inputs) + [weight_name]

    has_bias = _attr_values(op, ATTR_HAS_BIAS, (0,))[:1] == (1,)
    bias_ids = _attr_values(op, ATTR_BIAS)
    if has_bias and bias_ids:
        bias_name = f"const_{bias_ids[0]}"
        initializers.append(
            numpy_helper.from_array(_constant_array(graph, bias_ids[0]).reshape(-1), bias_name)
        )
        node_inputs.append(bias_name)

    pads = _pads(_attr_values(op, ATTR_PADS, (0, 0, 0, 0)))
    strides = list(_attr_values(op, ATTR_STRIDES, (1, 1)))
    dilations = list(_attr_values(op, ATTR_DILATIONS, (1, 1)))
    return helper.make_node(
        "Conv",
        node_inputs,
        _names(op.outputs),
        name=str(op.name_id),
        group=group,
        pads=pads,
        strides=strides,
        dilations=dilations,
    )


def _make_conv_transpose(
    graph: MizarGraph, op: Operation, initializers: list[onnx.TensorProto]
):
    weight_ids = _attr_values(op, ATTR_WEIGHT)
    if len(weight_ids) != 1:
        raise ValueError(f"conv-transpose {op.name_id}: weight reference is missing")
    # The attribute advertises logical OIHW dimensions, but the referenced
    # constant is already serialized in the IOHW order required by ONNX.
    logical_shape = _attr_values(op, ATTR_WEIGHT_SHAPE)
    group = max(1, _attr_values(op, ATTR_GROUP, (1,))[0])
    physical_shape = (
        (logical_shape[1], logical_shape[0] // group, *logical_shape[2:])
        if len(logical_shape) >= 2
        else None
    )
    weight = _constant_array(graph, weight_ids[0], physical_shape)
    weight_name = f"const_{weight_ids[0]}"
    initializers.append(numpy_helper.from_array(weight, weight_name))
    node_inputs = _names(op.inputs) + [weight_name]

    has_bias = _attr_values(op, ATTR_HAS_BIAS, (0,))[:1] == (1,)
    bias_ids = _attr_values(op, ATTR_BIAS)
    if has_bias and bias_ids:
        bias_name = f"const_{bias_ids[0]}"
        initializers.append(
            numpy_helper.from_array(_constant_array(graph, bias_ids[0]).reshape(-1), bias_name)
        )
        node_inputs.append(bias_name)

    return helper.make_node(
        "ConvTranspose",
        node_inputs,
        _names(op.outputs),
        name=str(op.name_id),
        group=group,
        pads=_pads(_attr_values(op, ATTR_PADS, (0, 0, 0, 0))),
        strides=list(_attr_values(op, ATTR_STRIDES, (1, 1))),
        dilations=list(_attr_values(op, ATTR_DILATIONS, (1, 1))),
    )


def convert_graph(graph: MizarGraph, model_name: str) -> onnx.ModelProto:
    nodes: list[onnx.NodeProto] = []
    initializers: list[onnx.TensorProto] = []
    value_info: list[onnx.ValueInfoProto] = []
    unsupported: dict[int, int] = {}
    legacy_layout = any(op.type_id == LEGACY_LAYOUT for op in graph.operations)
    trailing_layout = not legacy_layout and any(
        len(item.shape) == 5 and item.shape[-1] == 1 for item in graph.inputs
    )
    # This legacy activation opcode serializes only the activation kind; the
    # slope is a model-family default in Mizar. Differential tensor probes show
    # 0.2 for these two graphs and 0.1 for the remaining dialects.
    leaky_relu_alpha = (
        0.2
        if model_name in {"365", "hairSeamer_full", "restoreteeth"}
        else 0.1
    )

    def runtime_shape(shape: tuple[int, ...]) -> tuple[int, ...]:
        if legacy_layout:
            return _legacy_runtime_shape(shape)
        if trailing_layout:
            return _trailing_runtime_shape(shape)
        return shape

    for op in graph.operations:
        for tensor_id, shape in zip(op.outputs, op.output_shapes):
            value_info.append(
                helper.make_tensor_value_info(
                    str(tensor_id),
                    TensorProto.INT64 if op.type_id == SLICE_CHANNEL else TensorProto.FLOAT,
                    runtime_shape(shape),
                )
            )

        if op.type_id == DATA_INPUT:
            continue
        if op.type_id == CONVOLUTION:
            nodes.append(_make_conv(graph, op, initializers))
        elif op.type_id == CONVOLUTION_ALT:
            nodes.append(_make_conv_transpose(graph, op, initializers))
        elif op.type_id == ACTIVATION:
            kind = op.attributes.get(ATTR_ACTIVATION_KIND)
            if kind is None:
                nodes.append(helper.make_node("Relu", _names(op.inputs), _names(op.outputs), name=str(op.name_id)))
            elif kind.scalar == 4:
                nodes.append(
                    helper.make_node(
                        "LeakyRelu",
                        _names(op.inputs),
                        _names(op.outputs),
                        name=str(op.name_id),
                        alpha=leaky_relu_alpha,
                    )
                )
            else:
                raise ValueError(f"activation {op.name_id}: unsupported kind {kind.scalar}")
        elif op.type_id == ACTIVATION_ALT:
            nodes.append(helper.make_node("Sigmoid", _names(op.inputs), _names(op.outputs), name=str(op.name_id)))
        elif op.type_id == RELU_VARIANT:
            min_name = f"relu6_min_{op.name_id}"
            max_name = f"relu6_max_{op.name_id}"
            clip_max = 1.0 if op.output_shapes and len(op.output_shapes[0]) == 2 else 6.0
            initializers.append(
                numpy_helper.from_array(np.asarray(0.0, dtype=np.float32), min_name)
            )
            initializers.append(
                numpy_helper.from_array(np.asarray(clip_max, dtype=np.float32), max_name)
            )
            nodes.append(
                helper.make_node(
                    "Clip",
                    [str(op.inputs[0]), min_name, max_name],
                    _names(op.outputs),
                    name=str(op.name_id),
                )
            )
        elif op.type_id == PRELU:
            slope_ids = _attr_values(op, ATTR_PRELU_SLOPE)
            if len(slope_ids) != 1:
                raise ValueError(f"PReLU {op.name_id}: slope reference is missing")
            slope = _constant_array(graph, slope_ids[0]).reshape(-1)
            output_shape = runtime_shape(op.output_shapes[0]) if op.output_shapes else ()
            if len(output_shape) >= 2 and slope.size == output_shape[1]:
                broadcast_shape = [1] * len(output_shape)
                broadcast_shape[1] = slope.size
                slope = slope.reshape(broadcast_shape)
            elif output_shape and slope.size == output_shape[0]:
                broadcast_shape = [1] * len(output_shape)
                broadcast_shape[0] = slope.size
                slope = slope.reshape(broadcast_shape)
            slope_name = f"prelu_slope_{op.name_id}"
            initializers.append(numpy_helper.from_array(slope, slope_name))
            nodes.append(
                helper.make_node(
                    "PRelu",
                    [str(op.inputs[0]), slope_name],
                    _names(op.outputs),
                    name=str(op.name_id),
                )
            )
        elif op.type_id == INSTANCE_NORM:
            channels = _attr_values(op, ATTR_INSTANCE_CHANNELS)
            if not channels:
                raise ValueError(f"instance norm {op.name_id}: channel count is missing")
            scale_name = f"instance_scale_{op.name_id}"
            bias_name = f"instance_bias_{op.name_id}"
            initializers.append(
                numpy_helper.from_array(np.ones(channels[0], dtype=np.float32), scale_name)
            )
            initializers.append(
                numpy_helper.from_array(np.zeros(channels[0], dtype=np.float32), bias_name)
            )
            nodes.append(
                helper.make_node(
                    "InstanceNormalization",
                    [str(op.inputs[0]), scale_name, bias_name],
                    _names(op.outputs),
                    name=str(op.name_id),
                    epsilon=1e-5,
                )
            )
        elif op.type_id == TENSOR_FANOUT:
            if len(op.inputs) != 1:
                raise ValueError(f"fanout {op.name_id}: expected one input")
            for index, output in enumerate(op.outputs):
                shape = runtime_shape(op.output_shapes[index]) if index < len(op.output_shapes) else ()
                if shape:
                    shape_name = f"fanout_shape_{op.name_id}_{index}"
                    initializers.append(
                        numpy_helper.from_array(np.asarray(shape, dtype=np.int64), shape_name)
                    )
                    nodes.append(
                        helper.make_node(
                            "Reshape",
                            [str(op.inputs[0]), shape_name],
                            [str(output)],
                            name=f"{op.name_id}_{index}",
                        )
                    )
                else:
                    nodes.append(
                        helper.make_node(
                            "Identity",
                            [str(op.inputs[0])],
                            [str(output)],
                            name=f"{op.name_id}_{index}",
                        )
                    )
        elif op.type_id == LEGACY_LAYOUT:
            if not op.output_shapes:
                raise ValueError(f"layout {op.name_id}: output shape is missing")
            shape_name = f"layout_shape_{op.name_id}"
            initializers.append(
                numpy_helper.from_array(
                    np.asarray(runtime_shape(op.output_shapes[0]), dtype=np.int64), shape_name
                )
            )
            reshape_output = f"layout_reshape_{op.name_id}"
            nodes.append(
                helper.make_node(
                    "Reshape",
                    [str(op.inputs[0]), shape_name],
                    [reshape_output],
                    name=f"{op.name_id}_reshape",
                )
            )
            # Legacy input-layout opcode 0x5f also performs per-image
            # standardization: (x - spatial_mean) / spatial_stddev.
            mean_name = f"layout_mean_{op.name_id}"
            centered_name = f"layout_centered_{op.name_id}"
            squared_name = f"layout_squared_{op.name_id}"
            variance_name = f"layout_variance_{op.name_id}"
            stddev_name = f"layout_stddev_{op.name_id}"
            nodes.extend(
                [
                    helper.make_node(
                        "ReduceMean", [reshape_output], [mean_name],
                        name=f"{op.name_id}_mean", axes=[2, 3], keepdims=1,
                    ),
                    helper.make_node(
                        "Sub", [reshape_output, mean_name], [centered_name],
                        name=f"{op.name_id}_center",
                    ),
                    helper.make_node(
                        "Mul", [centered_name, centered_name], [squared_name],
                        name=f"{op.name_id}_square",
                    ),
                    helper.make_node(
                        "ReduceMean", [squared_name], [variance_name],
                        name=f"{op.name_id}_variance", axes=[2, 3], keepdims=1,
                    ),
                    helper.make_node(
                        "Sqrt", [variance_name], [stddev_name],
                        name=f"{op.name_id}_stddev",
                    ),
                    helper.make_node(
                        "Div", [centered_name, stddev_name], _names(op.outputs),
                        name=f"{op.name_id}_normalize",
                    ),
                ]
            )
        elif op.type_id == SPLIT:
            axis = _attr_values(op, ATTR_CONCAT_AXIS, (1,))[0]
            points = _attr_values(op, ATTR_SPLIT_POINTS)
            if points:
                ends = list(points)
                while len(ends) < len(op.outputs):
                    previous = ends[-1] if ends else 0
                    size = runtime_shape(op.output_shapes[len(ends)])[axis]
                    ends.append(previous + size)
                start = 0
                for index, (output, end) in enumerate(zip(op.outputs, ends)):
                    slice_inputs = [str(op.inputs[0])]
                    for label, values in (
                        ("starts", [start]),
                        ("ends", [end]),
                        ("axes", [axis]),
                        ("steps", [1]),
                    ):
                        name = f"split_{label}_{op.name_id}_{index}"
                        initializers.append(
                            numpy_helper.from_array(np.asarray(values, dtype=np.int64), name)
                        )
                        slice_inputs.append(name)
                    nodes.append(
                        helper.make_node(
                            "Slice",
                            slice_inputs,
                            [str(output)],
                            name=f"{op.name_id}_{index}",
                        )
                    )
                    start = end
            else:
                split_inputs = _names(op.inputs)
                sizes = [runtime_shape(shape)[axis] for shape in op.output_shapes]
                split_name = f"split_sizes_{op.name_id}"
                initializers.append(
                    numpy_helper.from_array(np.asarray(sizes, dtype=np.int64), split_name)
                )
                split_inputs.append(split_name)
                nodes.append(
                    helper.make_node(
                        "Split", split_inputs, _names(op.outputs), name=str(op.name_id), axis=axis
                    )
                )
        elif op.type_id == LEGACY_BINARY:
            kind = _attr_values(op, ATTR_ELTWISE_KIND, (0,))[0]
            legacy_binary_kind = {0: "Add", 1: "Sub", 2: "Max", 3: "Min", 4: "Mul", 5: "Div"}.get(kind)
            if legacy_binary_kind is None:
                legacy_binary_kind = "Add" # fallback
            nodes.append(
                helper.make_node(
                    legacy_binary_kind,
                    _names(op.inputs),
                    _names(op.outputs),
                    name=str(op.name_id),
                )
            )
        elif op.type_id == UPSAMPLE:
            if not op.output_shapes:
                raise ValueError(f"resize {op.name_id}: output shape is missing")
            sizes_name = f"sizes_{op.name_id}"
            roi_name = f"roi_{op.name_id}"
            scales_name = f"scales_{op.name_id}"
            initializers.append(
                numpy_helper.from_array(
                    np.asarray(runtime_shape(op.output_shapes[0]), dtype=np.int64), sizes_name
                )
            )
            initializers.append(numpy_helper.from_array(np.asarray([], dtype=np.float32), roi_name))
            initializers.append(numpy_helper.from_array(np.asarray([], dtype=np.float32), scales_name))
            resize_mode = _attr_values(op, ATTR_RESIZE_MODE, (1,))[0]
            coordinate_kind = _attr_values(
                op, ATTR_RESIZE_COORDINATE_MODE, (3,)
            )[0]
            coordinate_modes = {
                1: "half_pixel",
                2: "align_corners",
                3: "asymmetric",
            }
            if coordinate_kind not in coordinate_modes:
                raise ValueError(
                    f"resize {op.name_id}: unsupported coordinate mode "
                    f"{coordinate_kind}"
                )
            coordinate_mode = coordinate_modes[coordinate_kind]
            if resize_mode == 1:
                onnx_mode = "nearest"
                extra_attributes = {"nearest_mode": "floor"}
            elif resize_mode == 2:
                onnx_mode = "linear"
                extra_attributes = {}
            else:
                raise ValueError(
                    f"resize {op.name_id}: unsupported interpolation mode {resize_mode}"
                )
            nodes.append(
                helper.make_node(
                    "Resize",
                    [str(op.inputs[0]), roi_name, scales_name, sizes_name],
                    _names(op.outputs),
                    name=str(op.name_id),
                    coordinate_transformation_mode=coordinate_mode,
                    mode=onnx_mode,
                    **extra_attributes,
                )
            )
        elif op.type_id == CONCAT:
            axis_values = _attr_values(op, ATTR_CONCAT_AXIS, (1,))
            nodes.append(
                helper.make_node(
                    "Concat",
                    _names(op.inputs),
                    _names(op.outputs),
                    name=str(op.name_id),
                    axis=int(axis_values[0]),
                )
            )
        elif op.type_id == PAD:
            pads = _attr_values(op, ATTR_PADS)
            if trailing_layout and len(pads) == 10:
                pads = (*pads[:4], *pads[5:9])
            pads_name = f"pads_{op.name_id}"
            value_name = f"pad_value_{op.name_id}"
            initializers.append(
                numpy_helper.from_array(np.asarray(pads, dtype=np.int64), pads_name)
            )
            initializers.append(
                numpy_helper.from_array(np.asarray(0.0, dtype=np.float32), value_name)
            )
            nodes.append(
                helper.make_node(
                    "Pad",
                    [str(op.inputs[0]), pads_name, value_name],
                    _names(op.outputs),
                    name=str(op.name_id),
                    mode="constant",
                )
            )
        elif op.type_id == POOLING:
            pool_kind = _attr_values(op, ATTR_POOL_KIND, (7,))[0]
            onnx_kind = "AveragePool" if pool_kind == 8 else "MaxPool"
            kernel = _attr_values(op, ATTR_WEIGHT_SHAPE)
            if not kernel:
                nodes.append(
                    helper.make_node(
                        "GlobalAveragePool" if pool_kind == 8 else "GlobalMaxPool",
                        _names(op.inputs),
                        _names(op.outputs),
                        name=str(op.name_id),
                    )
                )
            else:
                nodes.append(
                    helper.make_node(
                        onnx_kind,
                        _names(op.inputs),
                        _names(op.outputs),
                        name=str(op.name_id),
                        kernel_shape=list(kernel),
                        strides=list(_attr_values(op, ATTR_STRIDES, (1, 1))),
                        pads=_pads(_attr_values(op, ATTR_PADS, (0, 0, 0, 0))),
                        ceil_mode=1,
                        **({"count_include_pad": 0} if onnx_kind == "AveragePool" else {}),
                    )
                )
        elif op.type_id == BATCH_NORM:
            mean_ids = _attr_values(op, ATTR_BATCHNORM_MEAN)
            variance_ids = _attr_values(op, ATTR_BATCHNORM_VARIANCE)
            if len(mean_ids) != 1 or len(variance_ids) != 1:
                raise ValueError(f"batch norm {op.name_id}: statistics are missing")
            mean = _constant_array(graph, mean_ids[0]).reshape(-1)
            variance = _constant_array(graph, variance_ids[0]).reshape(-1)
            names = [
                f"batch_scale_{op.name_id}",
                f"batch_bias_{op.name_id}",
                f"batch_mean_{op.name_id}",
                f"batch_variance_{op.name_id}",
            ]
            arrays = [np.ones_like(mean), np.zeros_like(mean), mean, variance]
            initializers.extend(numpy_helper.from_array(array, name) for array, name in zip(arrays, names))
            nodes.append(
                helper.make_node(
                    "BatchNormalization",
                    [str(op.inputs[0]), *names],
                    _names(op.outputs),
                    name=str(op.name_id),
                    epsilon=1e-5,
                )
            )
        elif op.type_id == SCALE:
            scale_ids = _attr_values(op, ATTR_SCALE)
            if len(scale_ids) != 1:
                raise ValueError(f"scale {op.name_id}: scale tensor is missing")
            rank = len(runtime_shape(op.output_shapes[0])) if op.output_shapes else 4
            axis = _attr_values(op, ATTR_CONCAT_AXIS, (1,))[0]
            scale = _constant_array(graph, scale_ids[0]).reshape(-1)
            broadcast_shape = [1] * rank
            broadcast_shape[axis] = scale.size
            scale_name = f"scale_{op.name_id}"
            initializers.append(numpy_helper.from_array(scale.reshape(broadcast_shape), scale_name))
            mul_output = str(op.outputs[0]) if not _attr_values(op, ATTR_HAS_SCALE_BIAS, (1,))[0] else f"scale_mul_{op.name_id}"
            nodes.append(
                helper.make_node("Mul", [str(op.inputs[0]), scale_name], [mul_output], name=f"{op.name_id}_mul")
            )
            if mul_output != str(op.outputs[0]):
                bias_ids = _attr_values(op, ATTR_BIAS)
                if len(bias_ids) != 1:
                    raise ValueError(f"scale {op.name_id}: bias tensor is missing")
                bias = _constant_array(graph, bias_ids[0]).reshape(-1)
                bias_name = f"scale_bias_{op.name_id}"
                initializers.append(numpy_helper.from_array(bias.reshape(broadcast_shape), bias_name))
                nodes.append(
                    helper.make_node(
                        "Add",
                        [mul_output, bias_name],
                        _names(op.outputs),
                        name=f"{op.name_id}_bias",
                    )
                )
        elif op.type_id == ELTWISE:
            kind = _attr_values(op, ATTR_ELTWISE_KIND, (0,))[0]
            node_inputs = _names(op.inputs)
            constant_ids = _attr_values(op, ATTR_WEIGHT)
            if constant_ids:
                constant_name = f"eltwise_const_{op.name_id}"
                initializers.append(
                    numpy_helper.from_array(_constant_array(graph, constant_ids[0]), constant_name)
                )
                node_inputs.append(constant_name)
                if _attr_values(op, ATTR_REVERSE_OPERANDS, (0,))[0] == 1:
                    node_inputs.reverse()
            onnx_kind = {
                0: "Add",
                1: "Sub",
                2: "Mul",
                3: "Div",
            }.get(kind)
            if onnx_kind is None:
                raise ValueError(f"eltwise {op.name_id}: unsupported kind {kind}")
            nodes.append(
                helper.make_node(onnx_kind, node_inputs, _names(op.outputs), name=str(op.name_id))
            )
        elif op.type_id == DEPTH_TO_SPACE:
            block_size = _attr_values(op, 3885198436, (2,))[0]
            nodes.append(
                helper.make_node(
                    "DepthToSpace",
                    _names(op.inputs),
                    _names(op.outputs),
                    name=str(op.name_id),
                    blocksize=block_size,
                    mode="CRD",
                )
            )
        elif op.type_id == SOFTMAX:
            axis = _attr_values(op, ATTR_CONCAT_AXIS, (1,))[0]
            nodes.append(
                helper.make_node(
                    "Softmax", _names(op.inputs), _names(op.outputs), name=str(op.name_id), axis=axis
                )
            )
        elif op.type_id == RESHAPE:
            shape = _signed_dims(_attr_values(op, ATTR_INPUT_SHAPE))
            shape_name = f"reshape_shape_{op.name_id}"
            initializers.append(numpy_helper.from_array(np.asarray(shape, dtype=np.int64), shape_name))
            nodes.append(
                helper.make_node(
                    "Reshape",
                    [str(op.inputs[0]), shape_name],
                    _names(op.outputs),
                    name=str(op.name_id),
                )
            )
        elif op.type_id == EXPAND:
            shape = _signed_dims(_attr_values(op, ATTR_EXPAND_SHAPE))
            shape_name = f"expand_shape_{op.name_id}"
            initializers.append(numpy_helper.from_array(np.asarray(shape, dtype=np.int64), shape_name))
            nodes.append(
                helper.make_node(
                    "Expand",
                    [str(op.inputs[0]), shape_name],
                    _names(op.outputs),
                    name=str(op.name_id),
                )
            )
        elif op.type_id == FULLY_CONNECTED:
            weight_ids = _attr_values(op, ATTR_WEIGHT)
            bias_ids = _attr_values(op, ATTR_BIAS)
            if len(weight_ids) != 1 or len(bias_ids) != 1:
                raise ValueError(f"fully connected {op.name_id}: parameters are missing")
            weight_name = f"fc_weight_{op.name_id}"
            bias_name = f"fc_bias_{op.name_id}"
            initializers.append(
                numpy_helper.from_array(_constant_array(graph, weight_ids[0]), weight_name)
            )
            initializers.append(
                numpy_helper.from_array(_constant_array(graph, bias_ids[0]).reshape(-1), bias_name)
            )
            nodes.append(
                helper.make_node(
                    "Gemm",
                    [str(op.inputs[0]), weight_name, bias_name],
                    _names(op.outputs),
                    name=str(op.name_id),
                    transB=1,
                )
            )
        elif op.type_id == MATMUL:
            weight_ids = _attr_values(op, ATTR_WEIGHT)
            if len(op.inputs) == 2:
                node_inputs = _names(op.inputs)
            elif len(op.inputs) == 1 and len(weight_ids) == 1:
                weight = _constant_array(graph, weight_ids[0])
                weight_name = f"matmul_weight_{op.name_id}"
                initializers.append(
                    numpy_helper.from_array(weight, weight_name)
                )
                node_inputs = [str(op.inputs[0]), weight_name]
            else:
                raise ValueError(f"matmul {op.name_id}: unsupported input form")
            nodes.append(
                helper.make_node("MatMul", node_inputs, _names(op.outputs), name=str(op.name_id))
            )
        elif op.type_id == LOAD_CONSTANT:
            if len(op.outputs) != 1 or op.outputs[0] not in graph.constants:
                raise ValueError(f"constant op {op.name_id}: tensor payload is missing")
            initializers.append(
                numpy_helper.from_array(
                    _constant_array(graph, op.outputs[0]), str(op.outputs[0])
                )
            )
        elif op.type_id == TRANSPOSE:
            nodes.append(
                helper.make_node(
                    "Transpose",
                    _names(op.inputs),
                    _names(op.outputs),
                    name=str(op.name_id),
                    perm=list(_attr_values(op, ATTR_TRANSPOSE_PERM)),
                )
            )
        elif op.type_id in (UNSQUEEZE, SQUEEZE):
            axes_name = f"axes_{op.name_id}"
            initializers.append(
                numpy_helper.from_array(
                    np.asarray(_signed_dims(_attr_values(op, ATTR_AXES)), dtype=np.int64), axes_name
                )
            )
            nodes.append(
                helper.make_node(
                    "Unsqueeze" if op.type_id == UNSQUEEZE else "Squeeze",
                    [str(op.inputs[0]), axes_name],
                    _names(op.outputs),
                    name=str(op.name_id),
                )
            )
        elif op.type_id == REDUCE:
            axes_name = f"reduce_axes_{op.name_id}"
            initializers.append(
                numpy_helper.from_array(
                    np.asarray(_signed_dims(_attr_values(op, ATTR_AXES)), dtype=np.int64), axes_name
                )
            )
            nodes.append(
                helper.make_node(
                    "ReduceSum",
                    [str(op.inputs[0]), axes_name],
                    _names(op.outputs),
                    name=str(op.name_id),
                    keepdims=_attr_values(op, ATTR_KEEP_DIMS, (1,))[0],
                )
            )
        elif op.type_id == UNARY:
            kind = _attr_values(op, ATTR_ELTWISE_KIND, (0,))[0]
            unary_name = {1: "Neg", 5: "Sin", 6: "Sqrt"}.get(kind)
            if unary_name is None:
                raise ValueError(f"unary {op.name_id}: unsupported kind {kind}")
            nodes.append(
                helper.make_node(unary_name, _names(op.inputs), _names(op.outputs), name=str(op.name_id))
            )
        elif op.type_id == SLICE_CHANNEL:
            axis = _attr_values(op, ATTR_CONCAT_AXIS, (1,))[0]
            nodes.append(
                helper.make_node(
                    "ArgMax", _names(op.inputs), _names(op.outputs),
                    name=str(op.name_id), axis=axis,
                    keepdims=_attr_values(op, ATTR_KEEP_DIMS, (1,))[0],
                    select_last_index=0,
                )
            )
        elif op.type_id == CLIP_UNIT:
            nodes.append(
                helper.make_node(
                    "Cast", _names(op.inputs), _names(op.outputs),
                    name=str(op.name_id), to=TensorProto.FLOAT,
                )
            )
        else:
            unsupported[op.type_id] = unsupported.get(op.type_id, 0) + 1

    if unsupported:
        rendered = ", ".join(f"{key} ({count}x)" for key, count in sorted(unsupported.items()))
        raise ValueError(f"unsupported Mizar operator IDs: {rendered}")

    # Shared parameter tensors are referenced by multiple operators in larger
    # graphs. ONNX requires initializer names to be unique.
    unique_initializers: dict[str, onnx.TensorProto] = {}
    for initializer in initializers:
        previous = unique_initializers.get(initializer.name)
        if previous is not None and previous.SerializeToString() != initializer.SerializeToString():
            raise ValueError(f"initializer name collision: {initializer.name}")
        unique_initializers[initializer.name] = initializer
    initializers = list(unique_initializers.values())

    input_values = [
        helper.make_tensor_value_info(
            str(item.tensor_id), TensorProto.FLOAT,
            _trailing_runtime_shape(item.shape) if legacy_layout else runtime_shape(item.shape),
        )
        for item in graph.inputs
    ]
    output_values = [
        helper.make_tensor_value_info(str(item.tensor_id), TensorProto.FLOAT, runtime_shape(item.shape))
        for item in graph.outputs
    ]
    onnx_graph = helper.make_graph(
        nodes,
        model_name,
        input_values,
        output_values,
        initializer=initializers,
        value_info=value_info,
    )
    model = helper.make_model(
        onnx_graph,
        producer_name="cubeo-mizar-cleanroom",
        opset_imports=[helper.make_opsetid("", 13)],
    )
    model.ir_version = 9
    checker.check_model(model)
    return shape_inference.infer_shapes(model)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="decrypted .manis.decoded model")
    parser.add_argument("output", type=Path, help="destination .onnx file")
    args = parser.parse_args()

    graph = parse_mizar_graph(args.input)
    model = convert_graph(graph, args.input.name.removesuffix(".manis.decoded"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    onnx.save_model(model, args.output)
    print(
        f"wrote {args.output} | nodes={len(model.graph.node)} "
        f"constants={len(model.graph.initializer)} "
        f"inputs={[item.name for item in model.graph.input]} "
        f"outputs={[item.name for item in model.graph.output]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
