#!/usr/bin/env python3
"""Validate all independently translated Mizar models with ONNX Runtime.

The validator deliberately imports no Kumoo, Manis, or Mizar component.  It
loads every self-contained ONNX file, runs a deterministic non-constant tensor, checks
declared output shapes, and rejects NaN/Inf results.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort


MODEL_NAMES = (
    "20260203_440epoch_sim_remove_expend_modify",
    "365",
    "Expelliarmus",
    "MTCheek_model",
    "MTJaw_model",
    "PhotoFaceContour",
    "eye_segment",
    "hairSeamer_full",
    "haircut_1104_1024_epoch_740_1624_new4",
    "restoreteeth",
    "skintone_0411_384_epoch_850_2",
)


def tensor_shape(value) -> list[int]:
    return [int(item) for item in value.shape]


def validate(path: Path) -> dict[str, object]:
    model = onnx.load_model(path, load_external_data=False)
    external = [
        tensor.name
        for tensor in model.graph.initializer
        if tensor.data_location == onnx.TensorProto.EXTERNAL
    ]
    if external:
        raise ValueError(f"external tensor data is not self-contained: {external[:5]}")

    started = time.perf_counter()
    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    inputs = session.get_inputs()
    if len(inputs) != 1 or any(not isinstance(dim, int) for dim in inputs[0].shape):
        raise ValueError(f"expected one static input, found {[item.shape for item in inputs]}")
    input_meta = inputs[0]
    input_value = np.random.Generator(np.random.PCG64(20260815)).uniform(
        -1.0, 1.0, size=input_meta.shape
    ).astype(np.float32)
    outputs = session.run(
        None,
        {input_meta.name: input_value},
    )
    output_meta = session.get_outputs()
    details: list[dict[str, object]] = []
    for metadata, value in zip(output_meta, outputs):
        if not np.isfinite(value).all():
            raise ValueError(f"non-finite output: {metadata.name}")
        declared = [int(dim) for dim in metadata.shape]
        actual = tensor_shape(value)
        if declared != actual:
            raise ValueError(f"output {metadata.name}: declared {declared}, actual {actual}")
        details.append(
            {
                "name": metadata.name,
                "shape": actual,
                "min": float(value.min()),
                "max": float(value.max()),
                "mean": float(value.mean()),
            }
        )
    return {
        "model": path.stem,
        "path": str(path),
        "input": {"name": input_meta.name, "shape": list(input_meta.shape)},
        "outputs": details,
        "seconds": round(time.perf_counter() - started, 4),
        "self_contained": True,
        "provider": "CPUExecutionProvider",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("independent_models"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report: dict[str, object] = {"models": [], "summary": {}}
    failures: list[dict[str, str]] = []
    for name in MODEL_NAMES:
        path = args.root / f"{name}.onnx"
        try:
            report["models"].append(validate(path))
            print(f"PASS {name}")
        except Exception as error:  # keep validating the rest of the catalog
            failures.append({"model": name, "error": str(error)})
            print(f"FAIL {name}: {error}")
    report["summary"] = {
        "expected": len(MODEL_NAMES),
        "passed": len(report["models"]),
        "failed": len(failures),
        "no_manis_runtime": True,
    }
    report["failures"] = failures
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
