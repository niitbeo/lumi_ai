#!/usr/bin/env python3
"""Restore the original Kumo FacePart contract in makeup.json.

The original plist contract uses AdditionalTexture for visible pupil artwork
and Path for the local alpha mask.  The first catalog export kept only Path,
which made eye masks render as white makeup.  This script also preserves the
per-layer LocateMethod/Operation/ORGBA metadata for auditing and future native
operator parity.  It is deterministic and updates the whole catalog, not one
preset by hand.
"""

from __future__ import annotations

import json
import plistlib
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT.parent / "kumoo_materials" / "makeups"
LIBRARY_PATH = ROOT / "assets" / "makeup" / "makeup.json"
OUTPUT_ROOT = ROOT / "assets" / "makeup" / "tex" / "kumo-additional"


def source_url(material_dir: str, filename: str) -> str:
    return f"/assets/makeup/tex/kumo-additional/{material_dir}/{filename}"


def copy_asset(material_dir: str, filename: str) -> str:
    source = SOURCE_ROOT / material_dir / "res" / filename
    if not source.is_file():
        raise FileNotFoundError(f"Missing Kumo asset: {source}")
    destination = OUTPUT_ROOT / material_dir / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return source_url(material_dir, filename)


def face_parts(material_dir: str) -> list[dict[str, object]]:
    plist_path = SOURCE_ROOT / material_dir / "configuration.plist"
    if not plist_path.is_file():
        return []
    with plist_path.open("rb") as stream:
        document = plistlib.load(stream)
    roots = document if isinstance(document, list) else [document]
    for root in roots:
        if isinstance(root, dict) and isinstance(root.get("FacePart"), list):
            return root["FacePart"]
    return []


def main() -> None:
    library = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    changed_materials = 0
    changed_layers = 0

    for part in library["parts"]:
        for material in part["materials"]:
            material_dir = material["dir"]
            originals = face_parts(material_dir)
            layers = material.get("layers", [])
            if not originals or len(originals) != len(layers):
                continue

            material_changed = False
            for layer, original in zip(layers, originals):
                # Preserve the source contract for every layer.  These values
                # explain which facial region Kumo anchors the texture to and
                # which compositor operation it expects.
                layer["originalPath"] = original.get("Path")
                layer["additionalTexture"] = original.get("AdditionalTexture")
                layer["addPath"] = original.get("AddPath")
                layer["locateMethod"] = original.get("LocateMethod")
                layer["operation"] = original.get("Operation")
                layer["filterType"] = original.get("FilterType")
                layer["muType"] = original.get("MUType")
                layer["needMask"] = bool(original.get("NeedMask", 0))
                layer["needPupilHighlight"] = bool(original.get("NeedPupilHighLight", 0))
                layer["customName"] = original.get("CustomName")
                layer["orgba"] = original.get("ORGBA")
                layer["originalBlendMode"] = original.get("BlendMode")
                material_changed = True

                additional = original.get("AdditionalTexture")
                if not additional:
                    continue
                mask_path = original.get("Path")
                if not mask_path:
                    raise ValueError(f"{material_dir}: AdditionalTexture has no Path mask")

                layer["tex"] = copy_asset(material_dir, str(additional))
                layer["maskTex"] = copy_asset(material_dir, str(mask_path))
                changed_layers += 1

            if material_changed:
                changed_materials += 1

    LIBRARY_PATH.write_text(
        json.dumps(library, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Synced {changed_layers} layers across {changed_materials} Kumo materials")


if __name__ == "__main__":
    main()
