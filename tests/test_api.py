from __future__ import annotations

import io
import json
import math
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
import numpy as np
from PIL import Image, ImageStat


PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = PROJECT_DIR
sys.path.insert(0, str(PROJECT_DIR / "server"))

import server as portrait_server  # noqa: E402
from gender_age import GenderAgeClassifier  # noqa: E402


class PortraitApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(portrait_server.app)

    def test_health_reports_independent_kumoo_models(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["uses_mizar"])
        self.assertFalse(payload["fallback_models"])
        self.assertEqual(
            payload["runtime"],
            "MNN CPU + ONNX Runtime CPU + Apple CoreML CPU",
        )
        self.assertEqual(
            payload["pipeline"],
            [
                "Fd",
                "Ga2",
                "Lp",
                "PhotoFaceContour",
                "facialsmooth_0529_192_384_epoch_1050",
                "Expelliarmus",
                "fuxiCreator_20251225",
                "skintone_0411_384_epoch_850_2",
                "SkinWhiteningLUT",
                "ChpsJyHairSegmentFallback",
                "HetComponentSeed",
                "ForegroundSkinOcclusion",
                "hairSeamer_full",
                "HairColorFilter:01|02|03|04|05|06|07|08",
                "MPLIPSTICKV2:luozhuang|jiaotang|yingtao",
                "KumoMakeupARP:11-groups|141-materials|25-themes",
                "KumoFaceLift:4-regions",
                "KumoFaceFill:10-regions",
            ],
        )
        self.assertEqual(payload["skintone_contract"], "kumo-residual-rgb-v1")
        self.assertEqual(
            payload["blemish_healing_contract"],
            "Kumoo BlackHead/FleckFlaw Expelliarmus flaw+nevus mask, fuxiCreator RGB, low-pass residual compositor",
        )
        self.assertEqual(
            payload["native_blemish_contract"],
            "GPUImageBlackHeadCleanFilter:Expelliarmus.mask + fuxiCreator_20251225.res",
        )
        self.assertEqual(payload["preset"], "Gốc (Kumo five demographic slots)")
        self.assertIn("one 9-class demographic head", payload["gender_age_contract"])
        self.assertEqual(set(payload["preset_profiles"]), {"man", "woman", "child", "oldwoman", "oldman"})
        self.assertEqual(payload["preset_profiles"]["man"]["smooth_face_skin_alpha"], 0)
        self.assertEqual(payload["preset_profiles"]["woman"]["smooth_face_skin_alpha"], 55)
        self.assertEqual(payload["preset_profiles"]["child"]["smooth_face_skin_alpha"], 0)
        self.assertEqual(payload["preset_profiles"]["oldwoman"]["smooth_face_skin_alpha"], 29)
        self.assertEqual(payload["preset_profiles"]["oldman"]["skin_tone_face_alpha"], 12)
        self.assertEqual(payload["preset_strengths"]["smooth_face_skin_alpha"], 55)
        self.assertEqual(payload["source_preset_reference_only"]["smooth_face_skin_low_alpha"], 64)
        self.assertEqual(payload["source_preset_reference_only"]["smooth_face_skin_hight_alpha"], -33)
        self.assertEqual(payload["source_preset_reference_only"]["neutral_gray_smooth_alpha"], 60)
        self.assertEqual(payload["source_preset_reference_only"]["neutral_gray_enhance_alpha"], 30)
        self.assertEqual(payload["preset_strengths"]["skin_fleck_clean_flag"], 100)
        self.assertEqual(payload["preset_strengths"]["nevus_removal_flag"], 0)
        self.assertEqual(payload["preset_strengths"]["body_fleck_clean_flag"], 0)
        self.assertEqual(payload["preset_strengths"]["skin_tone_face_alpha"], 16)
        self.assertEqual(payload["preset_strengths"]["skin_white_alpha"], 10)
        self.assertEqual(payload["preset_strengths"]["lipstick_alpha"], 30)
        self.assertEqual(
            set(payload["lipstick_presets"]),
            {"luozhuang", "jiaotang", "yingtao"},
        )
        self.assertEqual(set(payload["hair_color_presets"]), {f"{index:02d}" for index in range(1, 9)})
        self.assertEqual(
            payload["hair_color_contract"],
            "Kumo HairColorFilter blendType=3 / SetLum / ClipColor",
        )
        self.assertEqual(
            payload["makeup_contract"],
            "141 Kumo ARP materials + 25 original themes",
        )
        self.assertNotIn("tone_mimic", payload["operators"])
        self.assertNotIn("color_transfer_contract", payload)
        self.assertFalse(any(item.startswith("ColorTransfer:") for item in payload["pipeline"]))
        self.assertEqual(len(payload["face_volume_contract"]["lift_regions"]), 4)
        self.assertEqual(len(payload["face_volume_contract"]["fill_regions"]), 10)
        self.assertEqual(payload["face_volume_contract"]["lift_switch"], "face_flat_lift_switch")
        self.assertEqual(payload["face_volume_contract"]["fill_switch"], "face_full_switch")
        self.assertFalse(payload["extra_filters"])
        self.assertTrue(all(payload["models"].values()))
        self.assertTrue(all(payload["assets"].values()))

    def test_online_color_transfer_routes_are_not_exposed(self) -> None:
        self.assertEqual(self.client.get("/api/color-transfer/library").status_code, 404)
        self.assertEqual(self.client.get("/api/assets/color-ref/pk0_0.jpeg").status_code, 404)
        self.assertEqual(self.client.post("/api/color-transfer/apply").status_code, 404)

    def test_ga2_combined_class_decoder_maps_family_profiles(self) -> None:
        for class_index, profile in ((0, "child"), (5, "woman"), (6, "man")):
            logits = np.full(9, -20.0, dtype=np.float32)
            logits[class_index] = 20.0
            prediction = GenderAgeClassifier._decode_logits(logits)
            self.assertEqual(prediction["demographic_class"], class_index)
            self.assertEqual(prediction["profile"], profile)
            self.assertGreater(prediction["confidence"], 0.99)

    def test_body_skin_balance_is_chroma_only_and_preserves_neutral_pixels(self) -> None:
        source = np.array(
            [[[0.80, 0.60, 0.50], [0.40, 0.40, 0.40]]],
            dtype=np.float32,
        )

        balanced = portrait_server._apply_kumo_body_skin_balance(source)

        np.testing.assert_allclose(balanced[..., 0], source[..., 0], atol=1e-6)
        self.assertGreater(float(balanced[0, 0, 1]), float(source[0, 0, 1]))
        self.assertGreater(float(balanced[0, 0, 2]), float(source[0, 0, 2]))
        np.testing.assert_allclose(balanced[0, 1], source[0, 1], atol=1e-6)
        self.assertGreaterEqual(float(balanced.min()), 0.0)
        self.assertLessEqual(float(balanced.max()), 1.0)

    def test_real_portrait_runs_end_to_end_at_original_size(self) -> None:
        source_path = REPO_DIR / "test_face.jpg"
        with Image.open(source_path) as source_image:
            source_size = source_image.size
        response = self.client.post(
            "/api/portrait/beautify",
            files={"image": (source_path.name, source_path.read_bytes(), "image/jpeg")},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "image/jpeg")
        self.assertGreater(float(response.headers["x-processing-ms"]), 0)
        self.assertGreater(float(response.headers["x-face-coverage"]), 0.008)
        self.assertEqual(response.headers["x-skin-fleck-clean"], "100")
        self.assertEqual(response.headers["x-smooth-face-skin"], "100")
        self.assertEqual(response.headers["x-skin-tone-face"], "100")
        self.assertEqual(response.headers["x-skin-white"], "100")
        self.assertEqual(response.headers["x-lipstick-alpha"], "100")
        self.assertEqual(response.headers["x-lipstick-preset"], "luozhuang")
        self.assertEqual(response.headers["x-hair-color-strength"], "100")
        self.assertEqual(response.headers["x-hair-color-preset"], "none")
        self.assertEqual(response.headers["x-hair-color-effective"], "0.0000")
        self.assertEqual(response.headers["x-hair-mask-coverage"], "0.00000")
        self.assertEqual(response.headers["x-face-lift-region"], "none")
        self.assertEqual(response.headers["x-face-fill-region"], "none")
        self.assertEqual(response.headers["x-kumo-effective-smooth"], "55.00")
        self.assertEqual(response.headers["x-kumo-effective-skin-tone"], "16.00")
        self.assertEqual(response.headers["x-kumo-effective-skin-white"], "10.00")
        self.assertEqual(response.headers["x-face-count"], "1")
        self.assertEqual(response.headers["x-face-profiles"], "woman")
        self.assertIn("Fd,Ga2,Lp,PhotoFaceContour", response.headers["x-kumoo-pipeline"])
        self.assertIn("MPLIPSTICKV2", response.headers["x-kumoo-pipeline"])
        result = Image.open(io.BytesIO(response.content))
        self.assertEqual(result.size, source_size)
        self.assertEqual(result.mode, "RGB")

        # Regression guard for the old, incorrect direct-RGB interpretation of
        # skintone output: that path collapsed the face to a gray mask.
        with Image.open(source_path) as original:
            original_saturation = ImageStat.Stat(original.convert("HSV")).mean[1]
        result_saturation = ImageStat.Stat(result.convert("HSV")).mean[1]
        self.assertGreater(result_saturation, original_saturation * 0.65)

    def test_hair_material_changes_reuse_kumo_base_and_mask(self) -> None:
        source_path = REPO_DIR / "test_face.jpg"
        files = {"image": (source_path.name, source_path.read_bytes(), "image/jpeg")}
        portrait_server._clear_portrait_cache()

        prepared = self.client.post(
            "/api/portrait/beautify",
            files=files,
            data={"hair_color_preset": "none"},
        )
        recolored = self.client.post(
            "/api/portrait/beautify",
            files=files,
            data={"hair_color_preset": "03", "hair_color_strength": "100"},
        )

        self.assertEqual(prepared.status_code, 200, prepared.text)
        self.assertEqual(recolored.status_code, 200, recolored.text)
        self.assertEqual(prepared.headers["x-portrait-base-cache"], "MISS")
        self.assertEqual(prepared.headers["x-hair-mask-cache"], "MISS")
        self.assertEqual(recolored.headers["x-portrait-base-cache"], "HIT")
        self.assertEqual(recolored.headers["x-hair-mask-cache"], "HIT")
        self.assertLess(float(recolored.headers["x-hair-mask-stage-ms"]), 5.0)
        self.assertNotEqual(prepared.content, recolored.content)

    def test_photobooth_base_cache_uses_only_skin_contract(self) -> None:
        common = {
            "skin_fleck_clean_flag": [100, 100, 0, 0, 0],
            "smooth_face_skin_alpha": [10, 10, 10, 10, 10],
            "skin_tone_body_alpha": [0, 40, 0, 0, 0],
            "skin_white_alpha": [10, 10, 10, 10, 10],
        }
        first = portrait_server._portrait_base_cache_key(
            b"portrait", 0, 0, 0, 0, None,
            {**common, "hsl_hue_orange": -18, "filter": {"filter_id": "one"}},
            100,
        )
        same_skin = portrait_server._portrait_base_cache_key(
            b"portrait", 0, 0, 0, 0, None,
            {**common, "hsl_hue_orange": 30, "filter": {"filter_id": "two"}},
            100,
        )
        changed_skin = portrait_server._portrait_base_cache_key(
            b"portrait", 0, 0, 0, 0, None,
            {**common, "skin_white_alpha": [20, 20, 20, 20, 20]},
            100,
        )
        self.assertEqual(first, same_skin)
        self.assertNotEqual(first, changed_skin)

    def test_upload_analysis_runs_ga2_and_allows_manual_profile_override(self) -> None:
        source_path = REPO_DIR / "test_face.jpg"
        files = {"image": (source_path.name, source_path.read_bytes(), "image/jpeg")}
        analysis = self.client.post("/api/portrait/analyze", files=files)

        self.assertEqual(analysis.status_code, 200, analysis.text)
        payload = analysis.json()
        self.assertEqual(payload["model"], "Ga2")
        self.assertEqual(payload["landmark_model"], "Lp106")
        self.assertEqual(payload["face_count"], 1)
        self.assertEqual(payload["faces"][0]["profile"], "woman")
        self.assertEqual(payload["faces"][0]["preset"]["smooth_face_skin_alpha"], 55)
        self.assertEqual(len(payload["faces"][0]["landmarks"]), 106)
        self.assertTrue(all(len(point) == 2 for point in payload["faces"][0]["landmarks"]))

        overridden = self.client.post(
            "/api/portrait/beautify",
            files=files,
            data={"profile_overrides": '["man"]'},
        )
        self.assertEqual(overridden.status_code, 200, overridden.text)
        self.assertEqual(overridden.headers["x-face-profiles"], "man")
        self.assertEqual(overridden.headers["x-kumo-effective-smooth"], "0.00")
        self.assertEqual(overridden.headers["x-kumo-effective-skin-tone"], "0.00")
        self.assertEqual(overridden.headers["x-kumo-effective-skin-white"], "0.00")

    def test_original_kumo_makeup_library_and_assets_are_served(self) -> None:
        response = self.client.get("/api/makeup/library")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(len(payload["parts"]), 11)
        self.assertEqual(sum(len(part["materials"]) for part in payload["parts"]), 141)
        self.assertEqual(len(payload["themes"]), 25)

        layers = [
            layer
            for part in payload["parts"]
            for material in part["materials"]
            for layer in material["layers"]
        ]
        self.assertEqual(len(layers), 383)
        contract_layers = [layer for layer in layers if "originalPath" in layer]
        self.assertGreaterEqual(len(contract_layers), 200)
        for layer in contract_layers:
            self.assertIn("originalPath", layer)
            self.assertIn("orgba", layer)

        first = payload["parts"][0]["materials"][0]
        thumbnail_path = first["thumb"].removeprefix("/assets/makeup/")
        thumbnail = self.client.get(f"/api/assets/makeup/{thumbnail_path}")
        self.assertEqual(thumbnail.status_code, 200)
        self.assertTrue(thumbnail.headers["content-type"].startswith("image/"))

        traversal = self.client.get("/api/assets/makeup/../../makeup.json")
        self.assertEqual(traversal.status_code, 404)

        pupil_material = next(
            material
            for part in payload["parts"]
            for material in part["materials"]
            if material["dir"] == "Mi0000jqGa1V9RB6"
        )
        self.assertEqual(len(pupil_material["layers"]), 4)
        for layer in pupil_material["layers"]:
            self.assertIn("maskTex", layer)
            self.assertNotEqual(layer["tex"], layer["maskTex"])
            self.assertEqual(layer["customName"], "MUFACE_EYEPUPIL")
            self.assertIn(layer["locateMethod"], (6, 7))
            self.assertIn(layer["operation"], (16, 17))
            for asset_url in (layer["tex"], layer["maskTex"]):
                asset_path = asset_url.removeprefix("/assets/makeup/")
                asset = self.client.get(f"/api/assets/makeup/{asset_path}")
                self.assertEqual(asset.status_code, 200, asset_url)
                self.assertTrue(asset.headers["content-type"].startswith("image/"))

        magazine_pupil = next(
            material
            for part in payload["parts"]
            for material in part["materials"]
            if material["dir"] == "Mi0000j9sVvEjCkG"
        )
        self.assertEqual(len(magazine_pupil["layers"]), 2)
        self.assertEqual(
            {layer["operation"] for layer in magazine_pupil["layers"]},
            {16, 17},
        )
        for layer in magazine_pupil["layers"]:
            mask_path = layer["maskTex"].removeprefix("/assets/makeup/")
            mask_asset = self.client.get(f"/api/assets/makeup/{mask_path}")
            self.assertEqual(mask_asset.status_code, 200, layer["maskTex"])
            with Image.open(io.BytesIO(mask_asset.content)) as mask_image:
                # Kumo Path is an opaque grayscale mask. The browser renderer
                # must convert luminance to alpha before destination-in.
                self.assertNotIn("A", mask_image.getbands())
                low, high = mask_image.convert("L").getextrema()
                self.assertLess(low, 16)
                self.assertGreater(high, 240)

        mouth_layers = [layer for layer in layers if layer.get("customName") == "MUFACE_MOUTH"]
        self.assertGreaterEqual(len(mouth_layers), 10)
        self.assertTrue(all(layer["locateMethod"] == 2 for layer in mouth_layers))
        self.assertTrue(all(layer["operation"] == 7 for layer in mouth_layers))

    def test_photobooth_presets_are_served(self) -> None:
        presets = self.client.get("/api/photobooth/library")
        self.assertEqual(presets.status_code, 200, presets.text)
        catalog = presets.json()
        self.assertEqual(len(catalog["categories"]), 9)
        self.assertEqual(len(catalog["presets"]), 84)
        self.assertEqual(len({preset["id"] for preset in catalog["presets"]}), 84)
        self.assertEqual({preset["param_count"] for preset in catalog["presets"]}, {362})
        self.assertTrue(
            all(len(preset["all_params"]) == 362 for preset in catalog["presets"]),
            "Every PhotoBooth preset must retain its independent 362-key Kumo snapshot",
        )

        def assert_finite_tree(value: object, path: str) -> None:
            if isinstance(value, bool) or value is None or isinstance(value, str):
                return
            if isinstance(value, (int, float)):
                self.assertTrue(math.isfinite(value), path)
                return
            if isinstance(value, list):
                for index, item in enumerate(value):
                    assert_finite_tree(item, f"{path}[{index}]")
                return
            if isinstance(value, dict):
                for key, item in value.items():
                    assert_finite_tree(item, f"{path}.{key}")

        profile_parameter_keys = {
            key
            for key, value in catalog["presets"][0]["all_params"].items()
            if isinstance(value, list)
            and len(value) == 5
            and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value)
        }
        self.assertEqual(len(profile_parameter_keys), 198)
        for preset in catalog["presets"]:
            assert_finite_tree(preset["all_params"], preset["name"])
            self.assertTrue(
                all(
                    isinstance(preset["all_params"].get(key), list)
                    and len(preset["all_params"][key]) == 5
                    for key in profile_parameter_keys
                ),
                f"{preset['name']} contains a malformed five-profile parameter",
            )
        self.assertEqual(
            set(catalog["presets"][0]["params"]),
            {"exposure", "contrast", "temperature", "vibrance", "blackness", "highlight", "whiteness", "shadow"},
        )
        filter_ids = {
            preset["all_params"].get("filter", {}).get("filter_id")
            for preset in catalog["presets"]
        } - {None, ""}
        self.assertEqual(len(filter_ids), 39)
        self.assertEqual(
            [filter_id for filter_id in sorted(filter_ids) if not (REPO_DIR / "public/filters" / f"{filter_id}.png").is_file()],
            [],
            "A PhotoBooth snapshot must not silently lose its Kumo LUT layer",
        )
        for filter_id in filter_ids:
            with Image.open(REPO_DIR / "public/filters" / f"{filter_id}.png") as lut_image:
                self.assertEqual(lut_image.size, (512, 512), filter_id)

        covers = {preset["cover"] for preset in catalog["presets"]}
        self.assertEqual(len(covers), 84)
        for cover_path in covers:
            cover_response = self.client.get(cover_path)
            self.assertEqual(cover_response.status_code, 200, cover_path)
            self.assertTrue(cover_response.headers["content-type"].startswith("image/"), cover_path)
            with Image.open(io.BytesIO(cover_response.content)) as cover_image:
                self.assertEqual(cover_image.size, (136, 136), cover_path)

        makeup = self.client.get("/api/makeup/library").json()
        materials_by_part = {
            part["key"]: {material["dir"]: material for material in part["materials"]}
            for part in makeup["parts"]
        }
        preset_makeup_parts = ("eyebrow", "eyeshadow", "eyeliner", "eyelash", "eye", "blush", "mouth")
        active_materials: set[tuple[str, str]] = set()
        for preset in catalog["presets"]:
            for part_key in preset_makeup_parts:
                slots = preset["all_params"].get(part_key, [])
                self.assertEqual(len(slots), 5, f"{preset['name']}:{part_key}")
                for slot in slots:
                    material_id = slot.get("id", "")
                    if not material_id:
                        continue
                    active_materials.add((part_key, material_id))
                    self.assertIn(
                        material_id,
                        materials_by_part[part_key],
                        f"{preset['name']} references missing {part_key} material {material_id}",
                    )
        self.assertEqual(len(active_materials), 47)

        for part in makeup["parts"]:
            for material in part["materials"]:
                asset_urls = [material["thumb"]]
                for layer in material["layers"]:
                    asset_urls.extend(
                        asset_url
                        for asset_url in (layer.get("tex"), layer.get("maskTex"), layer.get("clip"))
                        if asset_url
                    )
                for asset_url in asset_urls:
                    asset_path = asset_url.removeprefix("/assets/makeup/")
                    self.assertTrue(
                        (REPO_DIR / "assets/makeup" / asset_path).is_file(),
                        f"Missing asset for {part['key']}:{material['dir']}: {asset_url}",
                    )
        story_04 = next(preset for preset in catalog["presets"] if preset["name"] == "Story 04")
        self.assertEqual(story_04["all_params"]["hue"], -15)
        self.assertEqual(story_04["all_params"]["filter"]["filters_lut_alpha"], 20)
        self.assertEqual(self.client.get("/api/assets/presets/not-found.jpg").status_code, 404)

    def test_photobooth_skin_contract_is_not_cancelled_by_zero_manual_controls(self) -> None:
        source_path = REPO_DIR / "test_face.jpg"
        catalog = json.loads((REPO_DIR / "assets/presets/presets.json").read_text())
        bridal = catalog["presets"][0]
        response = self.client.post(
            "/api/portrait/beautify",
            files={"image": (source_path.name, source_path.read_bytes(), "image/jpeg")},
            data={
                "skin_fleck_clean_flag": "0",
                "smooth_face_skin_alpha": "0",
                "skin_tone_face_alpha": "0",
                "skin_white_alpha": "0",
                "profile_overrides": json.dumps(["woman"]),
                "photo_preset_params": json.dumps(bridal["all_params"]),
                "photo_preset_strength": "100",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["x-kumo-effective-blemish"], "80.00")
        self.assertEqual(response.headers["x-kumo-effective-smooth"], "10.00")
        self.assertEqual(response.headers["x-kumo-effective-skin-tone"], "0.00")
        self.assertEqual(response.headers["x-kumo-effective-body-tone"], "54.00")
        self.assertEqual(response.headers["x-kumo-effective-skin-white"], "0.00")

    def test_switching_photobooth_presets_reuses_face_analysis(self) -> None:
        source_path = REPO_DIR / "test_face.jpg"
        catalog = json.loads((REPO_DIR / "assets/presets/presets.json").read_text())
        portrait_server._clear_portrait_cache()
        with patch.object(
            portrait_server,
            "_face_detections",
            wraps=portrait_server._face_detections,
        ) as detect:
            for preset in catalog["presets"][:2]:
                response = self.client.post(
                    "/api/portrait/beautify",
                    files={"image": (source_path.name, source_path.read_bytes(), "image/jpeg")},
                    data={
                        "profile_overrides": json.dumps(["woman"]),
                        "photo_preset_params": json.dumps(preset["all_params"]),
                        "photo_preset_strength": "100",
                    },
                )
                self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(detect.call_count, 1)

    def test_original_kumo_face_volume_contract_and_thumbnails_are_served(self) -> None:
        response = self.client.get("/api/face-volume/library")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["landmarks"], "Lp106")
        self.assertEqual(payload["lift_switch"], "face_flat_lift_switch")
        self.assertEqual(payload["fill_switch"], "face_full_switch")
        self.assertEqual(len(payload["lift"]), 4)
        self.assertEqual(len(payload["fill"]), 10)
        self.assertEqual(
            {item["parameter"] for item in payload["lift"]},
            {"fore_head_smooth", "periorbital_smooth", "malars_smooth", "perioral_smooth"},
        )
        self.assertIn("jowl_fill", {item["parameter"] for item in payload["fill"]})
        for item in payload["lift"] + payload["fill"]:
            thumbnail = self.client.get(item["thumbnail"])
            self.assertEqual(thumbnail.status_code, 200, item)
            self.assertEqual(thumbnail.headers["content-type"], "image/jpeg")

        missing = self.client.get("/api/assets/faceguide/not-a-kumo-region.jpg")
        self.assertEqual(missing.status_code, 404)

    def test_face_volume_operator_is_local_and_changes_selected_region(self) -> None:
        height, width = 120, 120
        x = np.linspace(0.05, 0.95, width, dtype=np.float32)
        y = np.linspace(0.05, 0.95, height, dtype=np.float32)
        xx, yy = np.meshgrid(x, y)
        rgb = np.stack([xx, yy, (xx + yy) * 0.5], axis=2)
        original = rgb.copy()
        mask = np.zeros((height, width), dtype=np.float32)
        mask[20:100, 20:100] = 1.0

        portrait_server._localized_face_warp(
            rgb,
            mask,
            (60.0, 60.0),
            (28.0, 24.0),
            (0.0, 0.0),
            1.0,
            "fill",
        )

        self.assertGreater(float(np.abs(rgb[40:80, 40:80] - original[40:80, 40:80]).mean()), 0.001)
        self.assertTrue(np.array_equal(rgb[:12], original[:12]))
        self.assertTrue(np.array_equal(rgb[:, :12], original[:, :12]))

    def test_three_faces_are_analyzed_independently(self) -> None:
        source_path = REPO_DIR / "test_face.jpg"
        with Image.open(source_path) as portrait:
            portrait = portrait.convert("RGB").resize((260, 260))
        scene = Image.new("RGB", (900, 360), (220, 220, 220))
        for index in range(3):
            scene.paste(portrait, (20 + index * 290, 45))
        scene_buffer = io.BytesIO()
        scene.save(scene_buffer, format="JPEG", quality=95)

        response = self.client.post(
            "/api/portrait/analyze",
            files={"image": ("three-faces.jpg", scene_buffer.getvalue(), "image/jpeg")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["face_count"], 3)
        self.assertEqual(len(payload["faces"]), 3)
        self.assertEqual([face["id"] for face in payload["faces"]], [0, 1, 2])
        self.assertTrue(all(face["profile"] in portrait_server.KUMO_GOC_PROFILES for face in payload["faces"]))

    def test_invalid_and_tiny_images_are_rejected(self) -> None:
        invalid = self.client.post(
            "/api/portrait/beautify",
            files={"image": ("bad.txt", b"not an image", "text/plain")},
        )
        self.assertEqual(invalid.status_code, 415)

        tiny_buffer = io.BytesIO()
        Image.new("RGB", (32, 32), "white").save(tiny_buffer, format="PNG")
        tiny = self.client.post(
            "/api/portrait/beautify",
            files={"image": ("tiny.png", tiny_buffer.getvalue(), "image/png")},
        )
        self.assertEqual(tiny.status_code, 422)

    def test_small_face_in_full_scene_uses_localized_contour(self) -> None:
        source_path = REPO_DIR / "test_face.jpg"
        with Image.open(source_path) as portrait:
            portrait = portrait.convert("RGB").resize((300, 300))
        scene = Image.new("RGB", (1024, 1024), (232, 224, 218))
        scene.paste(portrait, (362, 120))
        scene_buffer = io.BytesIO()
        scene.save(scene_buffer, format="JPEG", quality=94)

        response = self.client.post(
            "/api/portrait/beautify",
            files={"image": ("full-scene.jpg", scene_buffer.getvalue(), "image/jpeg")},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertGreater(float(response.headers["x-face-coverage"]), 0.0002)
        self.assertEqual(Image.open(io.BytesIO(response.content)).size, (1024, 1024))

    def test_empty_photo_contour_falls_back_per_face_without_rejecting_group(self) -> None:
        rgb = np.full((320, 640, 3), 160, dtype=np.uint8)
        boxes = [(90, 75, 120, 170), (420, 75, 120, 170)]

        def landmark_face(box: tuple[int, int, int, int]) -> np.ndarray:
            x, y, width, height = box
            points = np.tile(
                np.array([[x + width * 0.5, y + height * 0.55]], dtype=np.float32),
                (106, 1),
            )
            angles = np.linspace(np.pi, 0.0, 33, dtype=np.float32)
            points[:33, 0] = x + width * 0.5 + np.cos(angles) * width * 0.44
            points[:33, 1] = y + height * 0.52 + np.sin(angles) * height * 0.43
            points[portrait_server.LANDMARK_GROUPS["left_eye"]] = [
                x + width * 0.36,
                y + height * 0.42,
            ]
            points[portrait_server.LANDMARK_GROUPS["right_eye"]] = [
                x + width * 0.64,
                y + height * 0.42,
            ]
            points[portrait_server.LANDMARK_GROUPS["left_brow"]] = [
                x + width * 0.36,
                y + height * 0.34,
            ]
            points[portrait_server.LANDMARK_GROUPS["right_brow"]] = [
                x + width * 0.64,
                y + height * 0.34,
            ]
            return points

        landmarks = [landmark_face(box) for box in boxes]
        valid = np.ones((480, 320), dtype=np.float32)
        empty = np.zeros((480, 320), dtype=np.float32)
        with patch.object(
            portrait_server,
            "_predict_contour",
            side_effect=[valid, empty],
        ):
            masks = portrait_server.face_contour_masks(rgb, boxes, landmarks)

        self.assertEqual(len(masks), 2)
        self.assertGreater(float(masks[0].max()), 0.99)
        self.assertGreater(float(masks[1].max()), 0.99)
        self.assertGreater(float(masks[1][75:245, 420:540].mean()), 0.10)
        self.assertLess(float(masks[1][:, :300].max()), 0.01)

    def test_removed_fake_controls_do_not_change_model_result(self) -> None:
        source_path = REPO_DIR / "test_face.jpg"
        plain = self.client.post(
            "/api/portrait/beautify",
            files={"image": (source_path.name, source_path.read_bytes(), "image/jpeg")},
        )
        legacy_fields = self.client.post(
            "/api/portrait/beautify",
            files={"image": (source_path.name, source_path.read_bytes(), "image/jpeg")},
            data={"tone": "0", "smooth": "75", "warmth": "40"},
        )

        self.assertEqual(plain.status_code, 200, plain.text)
        self.assertEqual(legacy_fields.status_code, 200, legacy_fields.text)
        self.assertEqual(plain.content, legacy_fields.content)

    def test_face_acne_freckle_strength_is_an_adjustable_zero_to_100_control(self) -> None:
        source_path = REPO_DIR / "test_face.jpg"
        request_file = {
            "image": (source_path.name, source_path.read_bytes(), "image/jpeg")
        }
        disabled = self.client.post(
            "/api/portrait/beautify",
            files=request_file,
            data={"skin_fleck_clean_flag": "0"},
        )
        maximum = self.client.post(
            "/api/portrait/beautify",
            files=request_file,
            data={"skin_fleck_clean_flag": "100"},
        )

        self.assertEqual(disabled.status_code, 200, disabled.text)
        self.assertEqual(maximum.status_code, 200, maximum.text)
        self.assertEqual(disabled.headers["x-skin-fleck-clean"], "0")
        self.assertEqual(maximum.headers["x-skin-fleck-clean"], "100")
        self.assertEqual(disabled.headers["x-kumo-effective-blemish"], "0.00")
        self.assertEqual(maximum.headers["x-kumo-effective-blemish"], "100.00")
        self.assertNotEqual(disabled.content, maximum.content)

        custom_skin = self.client.post(
            "/api/portrait/beautify",
            files=request_file,
            data={
                "skin_fleck_clean_flag": "42",
                "smooth_face_skin_alpha": "35",
                "skin_tone_face_alpha": "20",
                "skin_white_alpha": "12",
            },
        )
        self.assertEqual(custom_skin.status_code, 200, custom_skin.text)
        self.assertEqual(custom_skin.headers["x-skin-fleck-clean"], "42")
        self.assertEqual(custom_skin.headers["x-smooth-face-skin"], "35")
        self.assertEqual(custom_skin.headers["x-skin-tone-face"], "20")
        self.assertEqual(custom_skin.headers["x-skin-white"], "12")
        self.assertEqual(custom_skin.headers["x-kumo-effective-smooth"], "19.25")
        self.assertEqual(custom_skin.headers["x-kumo-effective-skin-tone"], "3.20")
        self.assertEqual(custom_skin.headers["x-kumo-effective-skin-white"], "1.20")

        too_high = self.client.post(
            "/api/portrait/beautify",
            files=request_file,
            data={"skin_fleck_clean_flag": "101"},
        )
        self.assertEqual(too_high.status_code, 422)

    def test_blemish_model_uses_full_face_contour_not_smoothing_exclusions(self) -> None:
        rgb = np.zeros((96, 96, 3), dtype=np.uint8)
        skin_mask = np.zeros((96, 96), dtype=np.float32)
        skin_mask[15:81, 15:81] = 1.0
        skin_mask[35:61, 35:61] = 0.0
        face_contour = np.zeros((96, 96), dtype=np.float32)
        face_contour[15:81, 15:81] = 1.0
        prediction = np.ones(
            (
                portrait_server.BLEMISH_MODEL_HEIGHT,
                portrait_server.BLEMISH_MODEL_WIDTH,
                4,
            ),
            dtype=np.float32,
        )

        flaw_mask = np.ones(
            (
                portrait_server.BLEMISH_MASK_MODEL_HEIGHT,
                portrait_server.BLEMISH_MASK_MODEL_WIDTH,
            ),
            dtype=np.float32,
        )
        nevus_mask = np.zeros_like(flaw_mask)

        with patch.object(
            portrait_server,
            "_coreml_image_prediction",
            return_value=prediction,
        ), patch.object(
            portrait_server,
            "_kumo_blemish_mask_prediction",
            return_value=(flaw_mask, nevus_mask),
        ):
            result = portrait_server._apply_coreml_face_models(
                rgb,
                [skin_mask],
                [face_contour],
                [(24, 20, 48, 56)],
                [0.0],
                [1.0],
            )

        self.assertGreater(float(result[48, 48].mean()), 0.95)
        self.assertLess(float(result[5, 5].mean()), 0.01)

    def test_three_confirmed_kumo_lip_materials_and_strength_are_selectable(self) -> None:
        source_path = REPO_DIR / "test_face.jpg"

        outputs: dict[str, bytes] = {}
        for preset in ("luozhuang", "jiaotang", "yingtao"):
            response = self.client.post(
                "/api/portrait/beautify",
                files={"image": (source_path.name, source_path.read_bytes(), "image/jpeg")},
                data={"lipstick_alpha": "100", "lipstick_preset": preset},
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.headers["x-lipstick-alpha"], "100")
            self.assertEqual(response.headers["x-lipstick-preset"], preset)
            outputs[preset] = response.content

        self.assertEqual(len(set(outputs.values())), 3)

        disabled = self.client.post(
            "/api/portrait/beautify",
            files={"image": (source_path.name, source_path.read_bytes(), "image/jpeg")},
            data={"lipstick_alpha": "0", "lipstick_preset": "yingtao"},
        )
        self.assertEqual(disabled.status_code, 200, disabled.text)
        self.assertEqual(disabled.headers["x-lipstick-alpha"], "0")

        invalid = self.client.post(
            "/api/portrait/beautify",
            files={"image": (source_path.name, source_path.read_bytes(), "image/jpeg")},
            data={"lipstick_preset": "invented"},
        )
        self.assertEqual(invalid.status_code, 422)

    def test_eight_original_kumo_hair_thumbnails_are_served_byte_for_byte(self) -> None:
        source_dir = REPO_DIR / "assets" / "haircolor"
        for index in range(1, 9):
            preset = f"{index:02d}"
            response = self.client.get(f"/api/assets/haircolor/{preset}.jpg")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["content-type"], "image/jpeg")
            self.assertEqual(response.content, (source_dir / f"{preset}.jpg").read_bytes())

        missing = self.client.get("/api/assets/haircolor/09.jpg")
        self.assertEqual(missing.status_code, 404)

    def test_kumo_hair_color_runs_het_hairseamer_and_original_shader(self) -> None:
        source_path = REPO_DIR / "test_face.jpg"
        files = {"image": (source_path.name, source_path.read_bytes(), "image/jpeg")}
        original = self.client.post(
            "/api/portrait/beautify",
            files=files,
            data={"hair_color_preset": "none"},
        )
        colored = self.client.post(
            "/api/portrait/beautify",
            files=files,
            data={"hair_color_preset": "03", "hair_color_strength": "100"},
        )

        self.assertEqual(original.status_code, 200, original.text)
        self.assertEqual(colored.status_code, 200, colored.text)
        self.assertEqual(colored.headers["x-hair-color-preset"], "03")
        self.assertEqual(colored.headers["x-hair-color-strength"], "100")
        self.assertEqual(colored.headers["x-hair-color-effective"], "1.0000")
        self.assertGreater(float(colored.headers["x-hair-mask-coverage"]), 0.01)
        self.assertIn(
            "ChpsJyHairSegmentFallback,HetComponentSeed,ForegroundSkinOcclusion,hairSeamer_full,HairColorFilter",
            colored.headers["x-kumoo-pipeline"],
        )
        self.assertNotEqual(original.content, colored.content)

        invalid = self.client.post(
            "/api/portrait/beautify",
            files=files,
            data={"hair_color_preset": "invented"},
        )
        self.assertEqual(invalid.status_code, 422)

    def test_hair_mask_keeps_a_foreground_occluder_unchanged(self) -> None:
        height, width = 128, 128
        rgb = np.full((height, width, 3), 96, dtype=np.uint8)
        parse_hair = np.ones((height, width), dtype=np.float32)
        parse_occluder = np.zeros((height, width), dtype=np.float32)
        head_matte = np.ones((height, width), dtype=np.float32)
        parse_hair[38:90, 54:104] = 0.0
        parse_occluder[38:90, 54:104] = 1.0
        # The dedicated hair plane leaves this foreground prop empty. Het is
        # only a component seed and must not paint the hole back in.
        head_matte[38:90, 54:104] = 0.0

        class FakeInput:
            name = "input"

        class FakeHairSeamer:
            @staticmethod
            def get_inputs() -> list[FakeInput]:
                return [FakeInput()]

            @staticmethod
            def run(*_args: object, **_kwargs: object) -> list[np.ndarray]:
                return [
                    np.zeros((1, 2, 385, 513), dtype=np.float32),
                    np.ones((1, 1, 385, 513), dtype=np.float32),
                    np.zeros((1, 3, 385, 513), dtype=np.float32),
                ]

        with (
            patch.object(
                portrait_server,
                "_head_matte",
                return_value=head_matte,
            ),
            patch.object(
                portrait_server,
                "_hair_parse_planes",
                return_value=(parse_hair, parse_occluder),
            ),
            patch.object(
                portrait_server,
                "_skin_occluder_plane",
                return_value=parse_occluder,
            ),
            patch.object(
                portrait_server,
                "hair_seamer_session",
                return_value=FakeHairSeamer(),
            ),
        ):
            mask = portrait_server._hair_mask(
                rgb,
                np.zeros((height, width), dtype=np.float32),
                [],
            )

        self.assertGreater(float(mask[12:30, 12:30].mean()), 0.70)
        self.assertLess(float(mask[48:80, 64:94].mean()), 0.01)

    def test_hair_parser_uses_kumo_rgb_zero_to_one_contract(self) -> None:
        rgb = np.array(
            [
                [[0, 64, 255], [255, 128, 0]],
                [[32, 255, 96], [255, 255, 255]],
            ],
            dtype=np.uint8,
        )
        captured: dict[str, np.ndarray] = {}

        class FakeInterpreter:
            @staticmethod
            def getSessionInputAll(_session: object) -> dict[str, object]:
                return {"input": object()}

            @staticmethod
            def runSession(_session: object) -> None:
                return None

            @staticmethod
            def getSessionOutputAll(_session: object) -> dict[str, object]:
                return {"output": object()}

        def capture_input(
            _input: object,
            tensor: np.ndarray,
            _shape: tuple[int, ...],
        ) -> None:
            captured["tensor"] = tensor.copy()

        with (
            patch.object(
                portrait_server,
                "human_parse_runtime",
                return_value=(FakeInterpreter(), object()),
            ),
            patch.object(
                portrait_server,
                "_mnn_copy_input",
                side_effect=capture_input,
            ),
            patch.object(
                portrait_server,
                "_mnn_copy_output",
                return_value=np.zeros((1, 6, 512, 512), dtype=np.float32),
            ),
        ):
            portrait_server._hair_parse_planes(rgb)

        tensor = captured["tensor"]
        self.assertGreaterEqual(float(tensor.min()), 0.0)
        self.assertLessEqual(float(tensor.max()), 1.0)
        self.assertEqual(float(tensor.max()), 1.0)

    def test_hair_mask_keeps_confident_fringe_inside_face_landmark_hull(self) -> None:
        height, width = 160, 160
        rgb = np.full((height, width, 3), 48, dtype=np.uint8)
        head_matte = np.ones((height, width), dtype=np.float32)
        parse_hair = np.zeros((height, width), dtype=np.float32)
        parse_hair[10:62, 24:136] = 1.0
        parse_hair[20:144, 20:58] = 1.0
        parse_hair[20:144, 102:140] = 1.0
        # A front fringe crosses the forehead portion of the landmark hull.
        parse_hair[38:68, 55:105] = 1.0
        skin_mask = np.zeros((height, width), dtype=np.float32)
        skin_mask[40:126, 42:118] = 1.0
        landmarks = [
            np.array(
                [[48, 38], [112, 38], [122, 122], [38, 122]],
                dtype=np.float32,
            )
        ]

        class FakeInput:
            name = "input"

        class FakeHairSeamer:
            @staticmethod
            def get_inputs() -> list[FakeInput]:
                return [FakeInput()]

            @staticmethod
            def run(*_args: object, **_kwargs: object) -> list[np.ndarray]:
                return [
                    np.zeros((1, 2, 385, 513), dtype=np.float32),
                    np.ones((1, 1, 385, 513), dtype=np.float32),
                    np.zeros((1, 3, 385, 513), dtype=np.float32),
                ]

        with (
            patch.object(portrait_server, "_head_matte", return_value=head_matte),
            patch.object(
                portrait_server,
                "_hair_parse_planes",
                return_value=(parse_hair, np.zeros_like(parse_hair)),
            ),
            patch.object(
                portrait_server,
                "_skin_occluder_plane",
                return_value=np.zeros_like(parse_hair),
            ),
            patch.object(
                portrait_server,
                "hair_seamer_session",
                return_value=FakeHairSeamer(),
            ),
        ):
            mask = portrait_server._hair_mask(rgb, skin_mask, landmarks)

        self.assertGreater(float(mask[45:60, 62:98].mean()), 0.70)
        self.assertLess(float(mask[82:112, 62:98].mean()), 0.03)

    def test_hair_mask_keeps_a_parser_confirmed_side_lock_outside_het(self) -> None:
        height, width = 160, 160
        rgb = np.full((height, width, 3), 72, dtype=np.uint8)
        parse_hair = np.zeros((height, width), dtype=np.float32)
        parse_hair[15:138, 16:88] = 1.0
        # Native PhotoHair/HairSegment owns the silhouette. This lock is valid
        # parser hair even though Het's whole-head matte misses it.
        side_lock_region = (slice(34, 126), slice(96, 130))
        parse_hair[side_lock_region] = 1.0
        parse_hair[34:58, 86:100] = 1.0
        parse_occluder = np.zeros((height, width), dtype=np.float32)
        head_matte = np.ones((height, width), dtype=np.float32)
        head_matte[side_lock_region] = 0.0
        # The hand itself must still remain untouched.
        parse_occluder[58:106, 72:102] = 1.0
        head_matte[58:106, 72:102] = 0.0

        class FakeInput:
            name = "input"

        class FakeHairSeamer:
            @staticmethod
            def get_inputs() -> list[FakeInput]:
                return [FakeInput()]

            @staticmethod
            def run(*_args: object, **_kwargs: object) -> list[np.ndarray]:
                return [
                    np.zeros((1, 2, 385, 513), dtype=np.float32),
                    np.ones((1, 1, 385, 513), dtype=np.float32),
                    np.zeros((1, 3, 385, 513), dtype=np.float32),
                ]

        with (
            patch.object(
                portrait_server,
                "_head_matte",
                return_value=head_matte,
            ),
            patch.object(
                portrait_server,
                "_hair_parse_planes",
                return_value=(parse_hair, parse_occluder),
            ),
            patch.object(
                portrait_server,
                "_skin_occluder_plane",
                return_value=parse_occluder,
            ),
            patch.object(
                portrait_server,
                "hair_seamer_session",
                return_value=FakeHairSeamer(),
            ),
        ):
            mask = portrait_server._hair_mask(
                rgb,
                np.zeros((height, width), dtype=np.float32),
                [],
            )

        side_lock = mask[side_lock_region]
        self.assertGreater(float(side_lock[:, 18:].mean()), 0.68)
        self.assertLess(float(mask[66:98, 78:96].mean()), 0.02)

    def test_hair_mask_keeps_connected_parser_tails_beyond_het(self) -> None:
        height, width = 200, 200
        rgb = np.full((height, width, 3), 54, dtype=np.uint8)
        head_matte = np.zeros((height, width), dtype=np.float32)
        head_matte[30:120, 50:150] = 1.0
        # Het keeps only a soft fragment, while the dedicated hair parser sees
        # the complete connected lower lock.
        head_matte[112:170, 116:128] = 0.35
        parse_hair = np.zeros((height, width), dtype=np.float32)
        parse_hair[30:120, 50:150] = 1.0
        # These parser-only extensions touch the main hair component and must
        # remain colourable even though they extend outside Het.
        parse_hair[10:36, 88:102] = 1.0
        parse_hair[105:178, 82:106] = 1.0
        parse_hair[105:170, 116:128] = 1.0
        # A disconnected parser mistake must never become hair.
        parse_hair[132:174, 164:188] = 1.0

        class FakeInput:
            name = "input"

        class FakeHairSeamer:
            @staticmethod
            def get_inputs() -> list[FakeInput]:
                return [FakeInput()]

            @staticmethod
            def run(*_args: object, **_kwargs: object) -> list[np.ndarray]:
                return [
                    np.zeros((1, 2, 385, 513), dtype=np.float32),
                    np.zeros((1, 1, 385, 513), dtype=np.float32),
                    np.zeros((1, 3, 385, 513), dtype=np.float32),
                ]

        with (
            patch.object(
                portrait_server,
                "_head_matte",
                return_value=head_matte,
            ),
            patch.object(
                portrait_server,
                "_hair_parse_planes",
                return_value=(parse_hair, np.zeros_like(parse_hair)),
            ),
            patch.object(
                portrait_server,
                "hair_seamer_session",
                return_value=FakeHairSeamer(),
            ),
        ):
            mask = portrait_server._hair_mask(
                rgb,
                np.zeros((height, width), dtype=np.float32),
                [],
            )

        self.assertGreater(float(mask[14:26, 91:99].mean()), 0.68)
        self.assertGreater(float(mask[138:168, 87:101].mean()), 0.68)
        soft_tail = float(mask[130:160, 118:126].mean())
        self.assertGreater(soft_tail, 0.68)
        self.assertLess(soft_tail, 0.76)
        self.assertLess(float(mask[140:166, 168:184].mean()), 0.02)

    def test_hair_mask_protects_skin_coloured_hand_without_chpsjy_hand_class(self) -> None:
        height, width = 180, 180
        # Warm/red hair deliberately overlaps skin chroma; the per-image
        # lightness gate must preserve it while still excluding the hand.
        hair_rgb = np.array([118, 62, 48], dtype=np.uint8)
        skin_rgb = np.array([205, 151, 126], dtype=np.uint8)
        rgb = np.empty((height, width, 3), dtype=np.uint8)
        rgb[:] = hair_rgb
        skin_reference = np.zeros((height, width), dtype=np.float32)
        skin_reference[48:125, 42:96] = 1.0
        rgb[48:125, 42:96] = skin_rgb
        # Raised fingers cross the right side of the hair. ChpsJy deliberately
        # reports no occluder here, matching the real six-class limitation.
        rgb[42:122, 112:128] = skin_rgb
        rgb[48:128, 130:145] = skin_rgb
        parse_hair = np.ones((height, width), dtype=np.float32)
        parse_hair[42:122, 112:128] = 0.0
        parse_hair[48:128, 130:145] = 0.0
        parse_occluder = np.zeros((height, width), dtype=np.float32)

        class FakeInput:
            name = "input"

        class FakeHairSeamer:
            @staticmethod
            def get_inputs() -> list[FakeInput]:
                return [FakeInput()]

            @staticmethod
            def run(*_args: object, **_kwargs: object) -> list[np.ndarray]:
                return [
                    np.zeros((1, 2, 385, 513), dtype=np.float32),
                    np.ones((1, 1, 385, 513), dtype=np.float32),
                    np.zeros((1, 3, 385, 513), dtype=np.float32),
                ]

        with (
            patch.object(
                portrait_server,
                "_head_matte",
                return_value=np.ones((height, width), dtype=np.float32),
            ),
            patch.object(
                portrait_server,
                "_hair_parse_planes",
                return_value=(parse_hair, parse_occluder),
            ),
            patch.object(
                portrait_server,
                "hair_seamer_session",
                return_value=FakeHairSeamer(),
            ),
        ):
            mask = portrait_server._hair_mask(
                rgb,
                skin_reference,
                [],
            )

        self.assertGreater(float(mask[20:38, 20:38].mean()), 0.70)
        # Joining/dilating the hand must stop at the raw ChpsJy hair boundary.
        # Otherwise correctly recognised hair gains a black halo around every
        # finger even though both Het and ChpsJy agree that it is hair.
        self.assertGreater(float(mask[58:112, 106:111].mean()), 0.68)
        self.assertGreater(float(mask[62:116, 146:151].mean()), 0.68)
        self.assertLess(float(mask[58:112, 116:124].mean()), 0.03)
        self.assertLess(float(mask[62:116, 134:141].mean()), 0.03)

    def test_hair_mask_never_colours_skin_toned_ears_mislabeled_as_hair(self) -> None:
        height, width = 220, 220
        hair_rgb = np.array([118, 62, 48], dtype=np.uint8)
        skin_rgb = np.array([205, 151, 126], dtype=np.uint8)
        rgb = np.full((height, width, 3), hair_rgb, dtype=np.uint8)
        skin_reference = np.zeros((height, width), dtype=np.float32)
        skin_reference[82:172, 82:138] = 1.0
        rgb[82:172, 82:138] = skin_rgb
        landmarks = [
            np.array(
                [[70, 75], [150, 75], [150, 170], [70, 170]],
                dtype=np.float32,
            )
        ]
        rows, columns = np.ogrid[:height, :width]
        left_ear = ((columns - 69) / 9.0) ** 2 + ((rows - 107) / 22.0) ** 2 <= 1.0
        right_ear = ((columns - 151) / 9.0) ** 2 + ((rows - 107) / 22.0) ** 2 <= 1.0
        rgb[left_ear | right_ear] = skin_rgb
        left_ear_shadow = (
            ((columns - 67) / 5.0) ** 2 + ((rows - 107) / 15.0) ** 2 <= 1.0
        )
        rgb[left_ear_shadow] = np.array([73, 21, 7], dtype=np.uint8)
        left_ear_cavity = (
            ((columns - 67) / 2.0) ** 2 + ((rows - 107) / 8.0) ** 2 <= 1.0
        )
        rgb[left_ear_cavity] = np.array([15, 5, 2], dtype=np.uint8)

        class FakeInput:
            name = "input"

        class FakeHairSeamer:
            @staticmethod
            def get_inputs() -> list[FakeInput]:
                return [FakeInput()]

            @staticmethod
            def run(*_args: object, **_kwargs: object) -> list[np.ndarray]:
                return [
                    np.zeros((1, 2, 385, 513), dtype=np.float32),
                    np.ones((1, 1, 385, 513), dtype=np.float32),
                    np.zeros((1, 3, 385, 513), dtype=np.float32),
                ]

        parse_hair = np.ones((height, width), dtype=np.float32)
        # ChpsJy sees the shadowed left ear as non-hair, while deliberately
        # mislabeling the brightly lit right ear as hair.
        parse_hair[left_ear] = 0.05
        with (
            patch.object(
                portrait_server,
                "_head_matte",
                return_value=np.ones((height, width), dtype=np.float32),
            ),
            patch.object(
                portrait_server,
                "_hair_parse_planes",
                return_value=(parse_hair, np.zeros_like(parse_hair)),
            ),
            patch.object(
                portrait_server,
                "hair_seamer_session",
                return_value=FakeHairSeamer(),
            ),
        ):
            mask = portrait_server._hair_mask(rgb, skin_reference, landmarks)

        self.assertLess(float(mask[left_ear].mean()), 0.08)
        self.assertLess(float(mask[left_ear_shadow].mean()), 0.08)
        self.assertLess(float(mask[left_ear_cavity].mean()), 0.08)
        self.assertLess(float(mask[right_ear].mean()), 0.08)
        self.assertGreater(float(mask[20:55, 20:55].mean()), 0.70)
        self.assertGreater(float(mask[85:140, 175:205].mean()), 0.70)

    def test_hair_mask_does_not_restore_parser_gaps_from_het(self) -> None:
        height, width = 180, 180
        rgb = np.full((height, width, 3), [86, 47, 39], dtype=np.uint8)
        parse_hair = np.ones((height, width), dtype=np.float32)
        parse_occluder = np.zeros((height, width), dtype=np.float32)
        # Het is only a connected-component seed. It must not overwrite gaps
        # in the dedicated hair segmentation plane.
        false_streaks = [
            (slice(24, 92), slice(42, 55)),
            (slice(18, 76), slice(76, 87)),
            (slice(30, 104), slice(105, 119)),
        ]
        for rows, columns in false_streaks:
            parse_hair[rows, columns] = 0.0
            parse_occluder[rows, columns] = 1.0

        class FakeInput:
            name = "input"

        class FakeHairSeamer:
            @staticmethod
            def get_inputs() -> list[FakeInput]:
                return [FakeInput()]

            @staticmethod
            def run(*_args: object, **_kwargs: object) -> list[np.ndarray]:
                return [
                    np.zeros((1, 2, 385, 513), dtype=np.float32),
                    np.ones((1, 1, 385, 513), dtype=np.float32),
                    np.zeros((1, 3, 385, 513), dtype=np.float32),
                ]

        with (
            patch.object(
                portrait_server,
                "_head_matte",
                return_value=np.ones((height, width), dtype=np.float32),
            ),
            patch.object(
                portrait_server,
                "_hair_parse_planes",
                return_value=(parse_hair, parse_occluder),
            ),
            patch.object(
                portrait_server,
                "hair_seamer_session",
                return_value=FakeHairSeamer(),
            ),
        ):
            mask = portrait_server._hair_mask(
                rgb,
                np.zeros((height, width), dtype=np.float32),
                [],
            )

        for rows, columns in false_streaks:
            self.assertLess(float(mask[rows, columns].mean()), 0.25)


if __name__ == "__main__":
    unittest.main()
