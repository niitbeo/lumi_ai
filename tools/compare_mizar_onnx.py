#!/usr/bin/env python3
"""Differentially compare clean-room ONNX exports with the original Mizar CPU runtime.

Mizar is used only as a test oracle. The generated ONNX files and their normal
inference path remain independent of Manis/Mizar.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "independent_models" / "manifest.json"
DEFAULT_ORACLE = ROOT / "tools" / "manis_oracle_runner"
DEFAULT_REPORT = ROOT / "independent_models" / "numerical_parity_report.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--oracle", type=Path, default=DEFAULT_ORACLE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--model", action="append", dest="models")
    parser.add_argument("--atol", type=float, default=1e-4)
    parser.add_argument("--rtol", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=20260815)
    return parser.parse_args()


def original_manis_path(source: str) -> Path:
    prefix = "manis_decrypted/"
    suffix = ".decoded"
    if not source.startswith(prefix) or not source.endswith(suffix):
        raise ValueError(f"unexpected decoded source path: {source}")
    relative = source[len(prefix) : -len(suffix)]
    return ROOT / "megatron_extracted" / "megatron" / relative


def concrete_shape(value_info: ort.NodeArg) -> list[int]:
    shape: list[int] = []
    for dim in value_info.shape:
        if not isinstance(dim, int) or dim <= 0:
            raise ValueError(
                f"dynamic or invalid dimension in {value_info.name}: {value_info.shape}"
            )
        shape.append(dim)
    return shape


def deterministic_input(shape: list[int], seed: int) -> np.ndarray:
    generator = np.random.Generator(np.random.PCG64(seed))
    return generator.uniform(-1.0, 1.0, size=shape).astype(np.float32)


def parse_oracle_json(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise RuntimeError(f"oracle did not emit JSON; stdout={stdout!r}")


def metrics(actual: np.ndarray, reference: np.ndarray) -> dict[str, Any]:
    shape_equal = list(actual.shape) == list(reference.shape)
    element_count_equal = actual.size == reference.size
    if not element_count_equal:
        return {
            "shape_equal": shape_equal,
            "element_count_equal": False,
            "onnx_shape": list(actual.shape),
            "mizar_shape": list(reference.shape),
        }

    actual_flat = actual.astype(np.float64, copy=False).reshape(-1)
    reference_flat = reference.astype(np.float64, copy=False).reshape(-1)
    delta = actual_flat - reference_flat
    absolute = np.abs(delta)
    denominator = np.maximum(np.abs(reference_flat), 1e-8)
    actual_norm = float(np.linalg.norm(actual_flat))
    reference_norm = float(np.linalg.norm(reference_flat))
    cosine = (
        float(np.dot(actual_flat, reference_flat) / (actual_norm * reference_norm))
        if actual_norm and reference_norm
        else (1.0 if actual_norm == reference_norm else 0.0)
    )
    return {
        "shape_equal": shape_equal,
        "element_count_equal": True,
        "onnx_shape": list(actual.shape),
        "mizar_shape": list(reference.shape),
        "finite_onnx": bool(np.isfinite(actual_flat).all()),
        "finite_mizar": bool(np.isfinite(reference_flat).all()),
        "max_abs": float(absolute.max(initial=0.0)),
        "mean_abs": float(absolute.mean()),
        "rmse": float(math.sqrt(float(np.mean(delta * delta)))),
        "max_rel": float(np.max(absolute / denominator, initial=0.0)),
        "cosine_similarity": cosine,
        "onnx_min": float(actual_flat.min(initial=0.0)),
        "onnx_max": float(actual_flat.max(initial=0.0)),
        "mizar_min": float(reference_flat.min(initial=0.0)),
        "mizar_max": float(reference_flat.max(initial=0.0)),
    }


def compare_model(
    entry: dict[str, Any], oracle: Path, seed: int, atol: float, rtol: float
) -> dict[str, Any]:
    name = entry["model"]
    onnx_path = ROOT / entry["independent_model"]
    manis_path = original_manis_path(entry["source"])
    session = ort.InferenceSession(
        str(onnx_path), providers=["CPUExecutionProvider"]
    )
    inputs = session.get_inputs()
    outputs = session.get_outputs()
    if len(inputs) != 1:
        raise ValueError(f"{name}: expected one input, found {len(inputs)}")
    input_shape = concrete_shape(inputs[0])
    input_array = deterministic_input(input_shape, seed)

    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix=f"mizar-parity-{name}-") as temp_text:
        temp = Path(temp_text)
        input_path = temp / "input.f32.bin"
        input_array.tofile(input_path)
        command = [
            str(oracle),
            str(manis_path),
            str(temp),
            inputs[0].name,
            ",".join(str(dim) for dim in input_shape),
            str(input_path),
            *(output.name for output in outputs),
        ]
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"{name}: oracle failed ({completed.returncode})\n"
                f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
            )
        oracle_result = parse_oracle_json(completed.stdout)
        onnx_outputs = session.run(None, {inputs[0].name: input_array})

        tensor_results: list[dict[str, Any]] = []
        for index, (output_arg, onnx_value, oracle_output) in enumerate(
            zip(outputs, onnx_outputs, oracle_result["outputs"])
        ):
            if oracle_output["dtype_enum"] != 1:
                raise ValueError(
                    f"{name}/{output_arg.name}: unsupported Mizar dtype enum "
                    f"{oracle_output['dtype_enum']}"
                )
            runtime_shape = oracle_output["shape"]
            reference = np.fromfile(oracle_output["path"], dtype=np.float32)
            reference = reference.reshape(runtime_shape)
            tensor_metrics = metrics(np.asarray(onnx_value), reference)
            values_close = bool(
                tensor_metrics.get("element_count_equal")
                and np.allclose(
                    np.asarray(onnx_value).reshape(-1),
                    reference.reshape(-1),
                    atol=atol,
                    rtol=rtol,
                    equal_nan=False,
                )
            )
            tensor_results.append(
                {
                    "index": index,
                    "name": output_arg.name,
                    "values_close": values_close,
                    **tensor_metrics,
                }
            )

    elapsed = time.perf_counter() - started
    passed = all(
        tensor["values_close"] and tensor["shape_equal"]
        for tensor in tensor_results
    )
    return {
        "model": name,
        "onnx": str(onnx_path.relative_to(ROOT)),
        "mizar": str(manis_path.relative_to(ROOT)),
        "input_name": inputs[0].name,
        "onnx_input_shape": input_shape,
        "mizar_input_shape": oracle_result["runtime_input_shape"],
        "input_shape_equal": input_shape == oracle_result["runtime_input_shape"],
        "seed": seed,
        "elapsed_seconds": elapsed,
        "passed": passed,
        "outputs": tensor_results,
    }


def main() -> int:
    args = parse_args()
    manifest = json.loads(args.manifest.read_text())
    entries = [item for item in manifest["models"] if item["backend"].startswith("ONNX")]
    if args.models:
        selected = set(args.models)
        entries = [item for item in entries if item["model"] in selected]
        missing = selected - {item["model"] for item in entries}
        if missing:
            raise SystemExit(f"unknown ONNX model(s): {', '.join(sorted(missing))}")

    results: list[dict[str, Any]] = []
    for index, entry in enumerate(entries, start=1):
        print(f"[{index}/{len(entries)}] compare {entry['model']}", flush=True)
        try:
            result = compare_model(
                entry,
                args.oracle.resolve(),
                args.seed + index - 1,
                args.atol,
                args.rtol,
            )
        except Exception as error:  # Keep the full batch diagnostic useful.
            result = {
                "model": entry["model"],
                "passed": False,
                "error": f"{type(error).__name__}: {error}",
            }
        results.append(result)
        if "error" in result:
            print(f"  ERROR {result['error']}", flush=True)
        else:
            worst = max(
                (output["max_abs"] for output in result["outputs"]), default=0.0
            )
            print(
                f"  passed={result['passed']} max_abs={worst:.9g} "
                f"time={result['elapsed_seconds']:.2f}s",
                flush=True,
            )

    pass_count = sum(bool(result.get("passed")) for result in results)
    report = {
        "schema_version": 1,
        "purpose": "Mizar CPU oracle versus independent ONNX Runtime CPU",
        "release_runtime_uses_mizar": False,
        "oracle_only_dependency": "Manis.framework from the installed Kumoo app",
        "tolerances": {"atol": args.atol, "rtol": args.rtol},
        "summary": {
            "total": len(results),
            "passed": pass_count,
            "failed": len(results) - pass_count,
        },
        "models": results,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(
        f"SUMMARY passed={pass_count}/{len(results)} report={args.report}",
        flush=True,
    )
    return 0 if pass_count == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
