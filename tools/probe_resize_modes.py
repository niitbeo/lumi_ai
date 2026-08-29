#!/usr/bin/env python3
"""Measure ONNX Resize mode variants against dumped float tensors."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from onnx import TensorProto, helper, numpy_helper


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("reference", type=Path)
    parser.add_argument("--input-shape", required=True)
    parser.add_argument("--output-shape", required=True)
    args = parser.parse_args()
    input_shape = [int(value) for value in args.input_shape.split(",")]
    output_shape = [int(value) for value in args.output_shape.split(",")]
    source = np.fromfile(args.input, dtype=np.float32).reshape(input_shape)
    reference = np.fromfile(args.reference, dtype=np.float32).reshape(output_shape)
    coordinates = ["half_pixel", "pytorch_half_pixel", "align_corners", "asymmetric"]
    cases = [("linear", coordinate, None) for coordinate in coordinates]
    for coordinate in [*coordinates, "tf_half_pixel_for_nn"]:
        for nearest in ["round_prefer_floor", "round_prefer_ceil", "floor", "ceil"]:
            cases.append(("nearest", coordinate, nearest))

    with tempfile.TemporaryDirectory(prefix="resize-modes-") as temp_text:
        for index, (mode, coordinate, nearest) in enumerate(cases):
            kwargs: dict[str, object] = {
                "mode": mode,
                "coordinate_transformation_mode": coordinate,
            }
            if nearest is not None:
                kwargs["nearest_mode"] = nearest
            graph = helper.make_graph(
                [helper.make_node("Resize", ["x", "roi", "scales", "sizes"], ["y"], **kwargs)],
                "resize_probe",
                [helper.make_tensor_value_info("x", TensorProto.FLOAT, input_shape)],
                [helper.make_tensor_value_info("y", TensorProto.FLOAT, output_shape)],
                initializer=[
                    numpy_helper.from_array(np.asarray([], dtype=np.float32), "roi"),
                    numpy_helper.from_array(np.asarray([], dtype=np.float32), "scales"),
                    numpy_helper.from_array(np.asarray(output_shape, dtype=np.int64), "sizes"),
                ],
            )
            model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
            model.ir_version = 9
            path = Path(temp_text) / f"{index}.onnx"
            onnx.save(model, path)
            try:
                actual = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"]).run(
                    None, {"x": source}
                )[0]
            except Exception as error:
                print(f"{mode:7s} {coordinate:20s} {nearest or '-':18s} ERROR {error}")
                continue
            delta = np.abs(actual - reference)
            print(
                f"{mode:7s} {coordinate:20s} {nearest or '-':18s} "
                f"max={delta.max():.9g} mean={delta.mean():.9g}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
