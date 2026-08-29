#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("model_root", type=Path)
    parser.add_argument("manis_root", type=Path)
    parser.add_argument("coreml_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    records = []
    for source in sorted(args.model_root.rglob("*")):
        suffix = source.suffix.lower()
        if not source.is_file() or suffix not in {".manis", ".manisa"}:
            continue
        relative = source.relative_to(args.model_root)
        if suffix == ".manis":
            decoded = args.manis_root / relative
            decoded = decoded.with_suffix(decoded.suffix + ".decoded")
            backend = "Mizar FlatBuffer"
            independent_runtime = False
            validation = "Manis decoder returned success; open loader not yet available"
        else:
            decoded = args.coreml_root / relative
            decoded = decoded.with_suffix(decoded.suffix + ".mlmodel")
            backend = "Apple CoreML protobuf"
            independent_runtime = True
            validation = "Loaded by CoreML CPU-only validator without Manis"

        exists = decoded.is_file()
        records.append({
            "source": str(relative),
            "source_format": suffix[1:],
            "backend": backend,
            "source_size": source.stat().st_size,
            "source_sha256": sha256(source),
            "decoded": str(decoded.relative_to(args.output.parent))
                if exists else None,
            "decoded_size": decoded.stat().st_size if exists else None,
            "decoded_sha256": sha256(decoded) if exists else None,
            "decrypted": exists,
            "independent_runtime": independent_runtime and exists,
            "validation": validation if exists else "decoded output missing",
        })

    summary = {
        "total": len(records),
        "decrypted": sum(record["decrypted"] for record in records),
        "manis": sum(record["source_format"] == "manis" for record in records),
        "manisa": sum(record["source_format"] == "manisa" for record in records),
        "independent_runtime": sum(
            record["independent_runtime"] for record in records
        ),
    }
    payload = {"summary": summary, "models": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["decrypted"] == summary["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
