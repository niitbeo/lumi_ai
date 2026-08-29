#!/usr/bin/env python3
"""Export the 11 Mizar-only models to self-contained ONNX files."""

from __future__ import annotations

import argparse
from pathlib import Path

import onnx

from mizar_to_onnx import convert_graph, parse_mizar_graph


MODELS = {
    "20260203_440epoch_sim_remove_expend_modify": "EffectCore/MTBeautyCoreHD.bundle/20260203_440epoch_sim_remove_expend_modify.manis.decoded",
    "365": "AIBeauty/365.manis.decoded",
    "Expelliarmus": "PhotoEffect/mtphotoeffect.bundle/effect_models/Expelliarmus.manis.decoded",
    "MTCheek_model": "libmtai/FaceDetectModel/MTCheek_model.manis.decoded",
    "MTJaw_model": "libmtai/FaceDetectModel/MTJaw_model.manis.decoded",
    "PhotoFaceContour": "libmtai/SegmentDetectModel/PhotoFaceContour.manis.decoded",
    "eye_segment": "libmtai/EyeSegmentModel/eye_segment.manis.decoded",
    "hairSeamer_full": "libmtai/HairSeamerModel/hairSeamer_full.manis.decoded",
    "haircut_1104_1024_epoch_740_1624_new4": "PhotoEffect/mtphotoeffect.bundle/effect_models/haircut_1104_1024_epoch_740_1624_new4.manis.decoded",
    "restoreteeth": "libmtai/RestoreTeethModel/model/restoreteeth.manis.decoded",
    "skintone_0411_384_epoch_850_2": "PhotoEffect/mtphotoeffect.bundle/effect_models/skintone_0411_384_epoch_850_2.manis.decoded",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path("manis_decrypted"))
    parser.add_argument("--output-root", type=Path, default=Path("independent_models"))
    args = parser.parse_args()

    args.output_root.mkdir(parents=True, exist_ok=True)
    for name, relative in MODELS.items():
        source = args.source_root / relative
        destination = args.output_root / f"{name}.onnx"
        graph = parse_mizar_graph(source)
        model = convert_graph(graph, name)
        onnx.save_model(model, destination)
        print(
            f"PASS {name}: nodes={len(model.graph.node)} "
            f"initializers={len(model.graph.initializer)} -> {destination}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
