#!/usr/bin/env python3
"""Compare every corresponding intermediate tensor in Mizar and ONNX.

The original runtime is an oracle only.  Tensor IDs recovered from the decoded
graph are bound through the runtime's internal decimal-ID API; the exported
ONNX model remains fully independent.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from onnx import TensorProto, helper

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from compare_mizar_onnx import deterministic_input, metrics, original_manis_path, parse_oracle_json
from mizar_to_onnx import DATA_INPUT, LOAD_CONSTANT, TENSOR_FANOUT, parse_mizar_graph


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model")
    parser.add_argument("--seed", type=int, default=20260815)
    parser.add_argument("--chunk-size", type=int, default=12)
    parser.add_argument("--atol", type=float, default=1e-4)
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    manifest = json.loads((ROOT / "independent_models/manifest.json").read_text())
    entry = next((item for item in manifest["models"] if item["model"] == args.model), None)
    if entry is None:
        raise SystemExit(f"model not found: {args.model}")
    decoded = ROOT / entry["source"]
    original = original_manis_path(entry["source"])
    onnx_path = ROOT / entry["independent_model"]
    graph = parse_mizar_graph(decoded)
    model = onnx.load(onnx_path)

    producer: dict[str, tuple[int, int, int]] = {}
    order = 0
    for op_index, op in enumerate(graph.operations):
        if op.type_id in {DATA_INPUT, LOAD_CONSTANT, TENSOR_FANOUT}:
            continue
        for output_index, tensor_id in enumerate(op.outputs):
            producer[str(tensor_id)] = (order, op_index, output_index)
            order += 1
    onnx_outputs = {name for node in model.graph.node for name in node.output}
    onnx_output_types = {
        name: (TensorProto.INT64 if node.op_type == "ArgMax" else TensorProto.FLOAT)
        for node in model.graph.node
        for name in node.output
    }
    tensor_names = sorted(onnx_outputs & producer.keys(), key=lambda name: producer[name][0])

    session_options = ort.SessionOptions()
    session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    base = ort.InferenceSession(
        str(onnx_path), sess_options=session_options,
        providers=["CPUExecutionProvider"],
    )
    input_arg = base.get_inputs()[0]
    input_shape = [int(dim) for dim in input_arg.shape]
    input_value = deterministic_input(input_shape, args.seed)

    results: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix=f"mizar-intermediate-{args.model}-") as temp_text:
        temp = Path(temp_text)
        input_file = temp / "input.f32.bin"
        input_value.tofile(input_file)
        for start in range(0, len(tensor_names), args.chunk_size):
            names = tensor_names[start : start + args.chunk_size]
            instrumented = onnx.ModelProto()
            instrumented.CopyFrom(model)
            del instrumented.graph.output[:]
            for name in names:
                instrumented.graph.output.append(
                    helper.make_tensor_value_info(name, onnx_output_types[name], None)
                )
            instrumented_path = temp / f"instrumented_{start}.onnx"
            onnx.save(instrumented, instrumented_path)
            session = ort.InferenceSession(
                str(instrumented_path), sess_options=session_options,
                providers=["CPUExecutionProvider"]
            )
            actuals = session.run(names, {input_arg.name: input_value})

            oracle_dir = temp / f"oracle_{start}"
            completed = subprocess.run(
                [
                    str(ROOT / "tools/manis_oracle_runner"),
                    str(original),
                    str(oracle_dir),
                    input_arg.name,
                    ",".join(str(dim) for dim in input_shape),
                    str(input_file),
                    *names,
                    "--output-by-id",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                raise RuntimeError(
                    f"oracle failed ({completed.returncode})\n"
                    f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
                )
            oracle = parse_oracle_json(completed.stdout)
            for name, actual, output in zip(names, actuals, oracle["outputs"]):
                reference = np.fromfile(output["path"], dtype=np.float32)
                measured = metrics(np.asarray(actual), reference)
                close = bool(
                    actual.size == reference.size
                    and np.allclose(
                        np.asarray(actual).reshape(-1), reference,
                        atol=args.atol, rtol=args.rtol,
                    )
                )
                _, op_index, output_index = producer[name]
                op = graph.operations[op_index]
                row = {
                    "tensor_id": int(name),
                    "op_index": op_index,
                    "op_type": op.type_id,
                    "op_name": op.name_id,
                    "output_index": output_index,
                    "close": close,
                    **measured,
                }
                results.append(row)
                print(
                    f"{op_index:4d} type={op.type_id:10d} tensor={name:>10s} "
                    f"close={str(close):5s} max={measured.get('max_abs', float('nan')):.8g} "
                    f"cos={measured.get('cosine_similarity', float('nan')):.8g}",
                    flush=True,
                )

    report = {
        "model": args.model,
        "seed": args.seed,
        "atol": args.atol,
        "rtol": args.rtol,
        "compared_tensors": len(results),
        "passed_tensors": sum(bool(row["close"]) for row in results),
        "first_mismatch": next((row for row in results if not row["close"]), None),
        "tensors": results,
    }
    report_path = args.report or ROOT / "independent_models" / f"{args.model}_intermediate_parity.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"report={report_path} pass={report['passed_tensors']}/{report['compared_tensors']}")
    return 0 if report["first_mismatch"] is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
