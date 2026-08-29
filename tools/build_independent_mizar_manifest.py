#!/usr/bin/env python3
"""Build the 31-model independent-runtime routing manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def stem(path: Path) -> str:
    for suffix in (".manis.decoded", ".manisa.mlmodel", ".onnx"):
        if path.name.endswith(suffix):
            return path.name[: -len(suffix)]
    return path.stem


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manis-root", type=Path, default=Path("manis_decrypted"))
    parser.add_argument("--coreml-root", type=Path, default=Path("coreml_decrypted"))
    parser.add_argument("--onnx-root", type=Path, default=Path("independent_models"))
    parser.add_argument(
        "--validation-report",
        type=Path,
        default=Path("independent_models/validation_report.json"),
    )
    parser.add_argument(
        "--parity-report",
        type=Path,
        default=Path("independent_models/numerical_parity_report.json"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("independent_models/manifest.json")
    )
    args = parser.parse_args()

    manis = {stem(path): path for path in args.manis_root.rglob("*.manis.decoded")}
    coreml = {stem(path): path for path in args.coreml_root.rglob("*.manisa.mlmodel")}
    onnx = {stem(path): path for path in args.onnx_root.glob("*.onnx")}
    validation = json.loads(args.validation_report.read_text())
    passed_onnx = {item["model"] for item in validation["models"]}
    parity = json.loads(args.parity_report.read_text())
    parity_onnx = {item["model"] for item in parity["models"] if item.get("passed")}

    records: list[dict[str, object]] = []
    missing: list[str] = []
    for name in sorted(manis):
        if name in coreml:
            records.append(
                {
                    "model": name,
                    "source": str(manis[name]),
                    "independent_model": str(coreml[name]),
                    "backend": "Apple CoreML",
                    "runtime_dependencies": ["CoreML.framework"],
                    "uses_manis_or_mizar": False,
                    "validation": "loaded CPU-only by coreml_independent_validator",
                }
            )
        elif name in onnx and name in passed_onnx and name in parity_onnx:
            records.append(
                {
                    "model": name,
                    "source": str(manis[name]),
                    "independent_model": str(onnx[name]),
                    "backend": "ONNX Runtime CPU",
                    "runtime_dependencies": ["onnxruntime"],
                    "uses_manis_or_mizar": False,
                    "validation": (
                        "self-contained finite-output smoke test and numerical "
                        "parity versus the Mizar CPU oracle (atol=rtol=1e-4)"
                    ),
                }
            )
        else:
            missing.append(name)

    result = {
        "summary": {
            "mizar_sources": len(manis),
            "independent": len(records),
            "coreml_routes": sum(item["backend"] == "Apple CoreML" for item in records),
            "onnx_routes": sum(item["backend"] == "ONNX Runtime CPU" for item in records),
            "missing": len(missing),
            "uses_manis_or_mizar": False,
        },
        "models": records,
        "missing_models": missing,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["summary"], sort_keys=True))
    return 1 if missing or len(records) != 31 else 0


if __name__ == "__main__":
    raise SystemExit(main())
