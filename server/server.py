#!/usr/bin/env python3
"""Local portrait-beauty API backed by the recovered independent ONNX models."""

from __future__ import annotations
from eye_segment import EyeSegmenter

import io
import base64
import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
from typing import Optional

import cv2
import MNN
import numpy as np
import onnxruntime as ort
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "models" / "independent"
DECRYPTED_MODEL_DIR = ROOT / "models" / "decrypted"
COREML_MODEL_DIR = ROOT / "models" / "coreml" / "effect_models"

from face_detect import FaceDetector  # noqa: E402
from gender_age import GenderAgeClassifier, PROFILE_LABELS  # noqa: E402
from landmarks import GROUPS as LANDMARK_GROUPS, LandmarkDetector  # noqa: E402

SKINTONE_MODEL = MODEL_DIR / "skintone_0411_384_epoch_850_2.onnx"
FACE_CONTOUR_MODEL = MODEL_DIR / "PhotoFaceContour.onnx"
FACE_DETECT_MODEL = DECRYPTED_MODEL_DIR / "Fd.onnx"
FACE_LANDMARK_MODEL = DECRYPTED_MODEL_DIR / "Lp.onnx"
GENDER_AGE_MODEL = DECRYPTED_MODEL_DIR / "Ga2.onnx"
HEAD_MATTE_MODEL = DECRYPTED_MODEL_DIR / "Het.onnx"
HUMAN_PARSE_MODEL = DECRYPTED_MODEL_DIR / "ChpsJy.onnx"
HAIR_SEAMER_MODEL = MODEL_DIR / "hairSeamer_full.onnx"
BLEMISH_MASK_MODEL = MODEL_DIR / "Expelliarmus.onnx"
FACIAL_SMOOTH_MODEL = (
    COREML_MODEL_DIR / "facialsmooth_0529_192_384_epoch_1050.manisa.mlmodel"
)
BLEMISH_HEAL_MODEL = COREML_MODEL_DIR / "fuxiCreator_20251225.manisa.mlmodel"
BLEMISH_MODEL_WIDTH = 960
BLEMISH_MODEL_HEIGHT = 960
BLEMISH_MASK_MODEL_WIDTH = 1024
BLEMISH_MASK_MODEL_HEIGHT = 1024
NATIVE_BLEMISH_MODEL_CONTRACT = (
    "GPUImageBlackHeadCleanFilter:Expelliarmus.mask + fuxiCreator_20251225.res"
)
WHITE_SKIN_LUT = ROOT / "models" / "face_color" / "white_lookup_table.png"
KUMO_LIPSTICK_PRESETS: dict[str, dict[str, object]] = {
    "luozhuang": {
        "label": "Lõa trang",
        "texture": ROOT / "materials" / "lipstick" / "luozhuang" / "res" / "arp" / "lip-7.png",
        "rectangle": (351, 793, 318, 133),
        "material_alpha": 0.80,
    },
    "jiaotang": {
        "label": "Caramel",
        "texture": ROOT / "materials" / "lipstick" / "jiaotang" / "res" / "arp" / "lip-12.png",
        "rectangle": (339, 787, 336, 141),
        "material_alpha": 0.80,
    },
    "yingtao": {
        "label": "Cherry",
        "texture": ROOT / "materials" / "lipstick" / "yingtao" / "res" / "arp" / "lip-22.png",
        "rectangle": (348, 787, 326, 141),
        "material_alpha": 1.00,
    },
}
KUMO_HAIR_THUMB_DIR = ROOT / "assets" / "haircolor"
KUMO_MAKEUP_DIR = ROOT / "assets" / "makeup"
KUMO_MAKEUP_LIBRARY = KUMO_MAKEUP_DIR / "makeup.json"
KUMO_PRESET_MATERIAL_LIBRARY = KUMO_MAKEUP_DIR / "preset-materials.json"
KUMO_FACE_GUIDE_DIR = ROOT / "assets" / "faceguide"
KUMO_PHOTOBOOTH_LIBRARY = (
    ROOT / "assets" / "presets" / "presets.json"
)
KUMO_PHOTOBOOTH_COVER_DIR = (
    ROOT / "assets" / "preset_covers"
)
KUMO_FILTERS_LIBRARY = ROOT / "assets" / "filters" / "filters.json"
KUMO_COLOR_REF_PACKS = ROOT / "assets" / "color_ref" / "packs.json"
KUMO_COLOR_REF_DIR = ROOT / "assets" / "color_ref"
KUMO_FACE_LIFT_REGIONS: dict[str, dict[str, str]] = {
    "forehead": {"label": "Trán", "parameter": "fore_head_smooth", "thumbnail": "liftForehead.jpg"},
    "eyes": {"label": "Mắt", "parameter": "periorbital_smooth", "thumbnail": "liftEye.jpg"},
    "midface": {"label": "Giữa mặt", "parameter": "malars_smooth", "thumbnail": "liftMidface.jpg"},
    "mouth": {"label": "Miệng", "parameter": "perioral_smooth", "thumbnail": "liftMouth.jpg"},
}
KUMO_FACE_FILL_REGIONS: dict[str, dict[str, str]] = {
    "forehead": {"label": "Trán", "parameter": "fore_head_fillers", "thumbnail": "fullForehead.jpg"},
    "tear_trough": {"label": "Rãnh lệ", "parameter": "tear_trough", "thumbnail": "fullTearTrough.jpg"},
    "apple_cheek": {"label": "Gò má", "parameter": "apple_cheek_fillers", "thumbnail": "fullAppleCheek.jpg"},
    # Kumo's public label is 面颊 (cheek); the recovered request key is jowl_fill.
    "cheek": {"label": "Má", "parameter": "jowl_fill", "thumbnail": "fullCheek.jpg"},
    "nose_base": {"label": "Gốc mũi", "parameter": "nose_fillers", "thumbnail": "fullNoseBase.jpg"},
    "aegyosal": {"label": "Bọng mắt", "parameter": "aegyosal_fill", "thumbnail": "fullAegyosal.jpg"},
    "eye_socket": {"label": "Hốc mắt", "parameter": "eye_socket_fillers", "thumbnail": "fullEyeSocket.jpg"},
    "brow_arch": {"label": "Khung mày", "parameter": "brow_arch_fill", "thumbnail": "fullBrowArch.jpg"},
    "chin": {"label": "Cằm", "parameter": "chin_fillers", "thumbnail": "fullChin.jpg"},
    "mouth_corner": {"label": "Khóe miệng", "parameter": "angulus_oris_fill", "thumbnail": "fullMouthCorner.jpg"},
}
KUMO_HAIR_CONFIG_DIR = ROOT / "materials" / "haircolor"
# The standalone bundle does not contain native PhotoHair.manis; ChpsJy's hair
# class is the closest local segmentation output.  Native 0/45/100 captures on
# the same source show its soft matte amplitude is 0.75 of the raw ChpsJy/Hair-
# Seamer result (0.750 at 45 and 0.736 at 100), so keep that measured matte
# calibration separate from the user-controlled material strength.
PHOTO_HAIR_FALLBACK_SCALE = 0.75
KUMO_HAIR_PRESETS: dict[str, dict[str, object]] = {
    "01": {
        "label": "Hắc trà",
        "source_name": "黑茶",
        "folder": "heicha",
        "material": "material.png",
        "default_alpha": 0.50,
        "max_alpha_ratio": 0.50,
    },
    "02": {
        "label": "Đỏ mâm xôi",
        "source_name": "树莓红",
        "folder": "shumeihong",
        "material": "material1.png",
        "default_alpha": 0.60,
        "max_alpha_ratio": 0.80,
    },
    "03": {
        "label": "Đỏ Hải Vương",
        "source_name": "海王红",
        "folder": "haiwanghong",
        "material": "material1.png",
        "default_alpha": 0.63,
        "max_alpha_ratio": 1.00,
    },
    "04": {
        "label": "Nâu xám lạnh",
        "source_name": "灰棕",
        "folder": "huizong",
        "material": "material.png",
        "default_alpha": 0.80,
        "max_alpha_ratio": 1.00,
    },
    "05": {
        "label": "Cam cháy",
        "source_name": "脏橘",
        "folder": "zangju",
        "material": "material1.png",
        "default_alpha": 0.60,
        "max_alpha_ratio": 0.80,
    },
    "06": {
        "label": "Đen tự nhiên",
        "source_name": "自然黑",
        "folder": "ziranhei",
        "material": "material1.png",
        "default_alpha": 0.63,
        "max_alpha_ratio": 0.85,
    },
    "07": {
        "label": "Xanh tím",
        "source_name": "蓝紫",
        "folder": "lanzi",
        "material": "material1.png",
        "default_alpha": 0.70,
        "max_alpha_ratio": 0.88,
    },
    "08": {
        "label": "Nâu chocolate",
        "source_name": "黑巧",
        "folder": "heiqiao",
        "material": "material1.png",
        "default_alpha": 0.65,
        "max_alpha_ratio": 0.85,
    },
}
COREML_RUNNER_SOURCE = Path(__file__).with_name("coreml_predict.mm")
COREML_RUNNER = Path(__file__).resolve().parents[1] / ".run" / "coreml_predict"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
API_PORT = int(os.environ.get("PORTRAIT_API_PORT", "8417"))

# Kumo's checked-in "Gốc" portrait preset. The array order in
# local_preset.json is man, woman, child, oldwoman, oldman. Public controls are
# percentages of each detected face's own source values.
DEFAULT_CONTROL_STRENGTH = 100
PRESET_PROFILE_INDEX = {
    "man": 0,
    "woman": 1,
    "child": 2,
    "oldwoman": 3,
    "oldman": 4,
}
KUMO_GOC_PROFILES: dict[str, dict[str, float]] = {
    "man": {
        "skin_fleck_clean_flag": 1,
        "flaw_clean_alpha": 90,
        "smooth_face_skin_alpha": 0,
        "skin_tone_face_alpha": 0,
        "skin_white_alpha": 0,
        "lipstick_alpha": 0,
    },
    "woman": {
        "skin_fleck_clean_flag": 100,
        "flaw_clean_alpha": 100,
        "smooth_face_skin_alpha": 55,
        "skin_tone_face_alpha": 16,
        "skin_white_alpha": 10,
        # PhotoBooth product layer requested by the user; Kumo Gốc itself has
        # no mouth material. It is kept separate from the source preset.
        "lipstick_alpha": 30,
    },
    "child": {
        "skin_fleck_clean_flag": 100,
        "flaw_clean_alpha": 90,
        "smooth_face_skin_alpha": 0,
        "skin_tone_face_alpha": 0,
        "skin_white_alpha": 0,
        "lipstick_alpha": 0,
    },
    "oldwoman": {
        "skin_fleck_clean_flag": 100,
        "flaw_clean_alpha": 100,
        "smooth_face_skin_alpha": 29,
        "skin_tone_face_alpha": 12,
        "skin_white_alpha": 0,
        "lipstick_alpha": 15,
    },
    "oldman": {
        "skin_fleck_clean_flag": 100,
        "flaw_clean_alpha": 100,
        "smooth_face_skin_alpha": 29,
        "skin_tone_face_alpha": 12,
        "skin_white_alpha": 0,
        "lipstick_alpha": 0,
    },
}
LIPSTICK_PRESET_ALPHA = 0.30

app = FastAPI(title="Lumi Portrait ONNX API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4417",
        "http://127.0.0.1:4417",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=[
        "X-Processing-Ms",
        "X-Face-Coverage",
        "X-Face-Count",
        "X-Face-Profiles",
        "X-Lipstick-Alpha",
        "X-Lipstick-Preset",
        "X-Hair-Color-Strength",
        "X-Hair-Color-Preset",
        "X-Hair-Color-Effective",
        "X-Hair-Mask-Coverage",
        "X-Face-Lift-Region",
        "X-Face-Lift-Strength",
        "X-Face-Fill-Region",
        "X-Face-Fill-Strength",
        "X-Portrait-Base-Cache",
        "X-Hair-Mask-Cache",
        "X-Base-Stage-Ms",
        "X-Hair-Mask-Stage-Ms",
        "X-Material-Stage-Ms",
        "X-Kumo-Effective-Smooth",
        "X-Kumo-Effective-Blemish",
        "X-Kumo-Effective-Skin-Tone",
        "X-Kumo-Effective-Body-Tone",
        "X-Kumo-Effective-Skin-White",
        "X-Kumoo-Pipeline",
    ],
)

_session_lock = threading.Lock()
_detector_lock = threading.Lock()
_landmark_lock = threading.Lock()
_coreml_lock = threading.Lock()
_head_matte_lock = threading.Lock()
_human_parse_lock = threading.Lock()
_portrait_cache_lock = threading.Lock()
_portrait_analysis_cache: OrderedDict[str, tuple[object, ...]] = OrderedDict()
_portrait_base_cache: OrderedDict[str, tuple[object, ...]] = OrderedDict()
_portrait_hair_mask_cache: OrderedDict[str, np.ndarray] = OrderedDict()
# The editor has one active source image. Keeping a second decoded 4K float
# frame can cost hundreds of MB without improving the interactive workflow.
_PORTRAIT_CACHE_LIMIT = 1
_timing_log = logging.getLogger("uvicorn.error")


def _session(path: Path) -> ort.InferenceSession:
    options = ort.SessionOptions()
    options.log_severity_level = 3
    options.intra_op_num_threads = max(1, min(4, (ort.get_available_providers() and 4) or 1))
    return ort.InferenceSession(
        str(path),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )


@lru_cache(maxsize=1)
def skin_session() -> ort.InferenceSession:
    return _session(SKINTONE_MODEL)


@lru_cache(maxsize=1)
def contour_session() -> ort.InferenceSession:
    return _session(FACE_CONTOUR_MODEL)


@lru_cache(maxsize=1)
def hair_seamer_session() -> ort.InferenceSession:
    return _session(HAIR_SEAMER_MODEL)


@lru_cache(maxsize=1)
def blemish_mask_session() -> ort.InferenceSession:
    return _session(BLEMISH_MASK_MODEL)


@lru_cache(maxsize=1)
def head_matte_runtime() -> tuple[object, object]:
    interpreter = MNN.Interpreter(str(HEAD_MATTE_MODEL))
    session = interpreter.createSession({"backend": "CPU"})
    input_tensor = next(iter(interpreter.getSessionInputAll(session).values()))
    interpreter.resizeTensor(input_tensor, (1, 3, 512, 512))
    interpreter.resizeSession(session)
    return interpreter, session


@lru_cache(maxsize=1)
def human_parse_runtime() -> tuple[object, object]:
    """Load Kumo ChpsJy, whose six classes include a dedicated hair plane."""

    interpreter = MNN.Interpreter(str(HUMAN_PARSE_MODEL))
    session = interpreter.createSession({"backend": "CPU"})
    input_tensor = next(iter(interpreter.getSessionInputAll(session).values()))
    interpreter.resizeTensor(input_tensor, (1, 3, 512, 512))
    interpreter.resizeSession(session)
    return interpreter, session


def _mnn_copy_input(tensor: object, array: np.ndarray, shape: tuple[int, ...]) -> None:
    wrapped = MNN.Tensor(
        shape,
        MNN.Halide_Type_Float,
        np.ascontiguousarray(array, dtype=np.float32),
        MNN.Tensor_DimensionType_Caffe,
    )
    tensor.copyFrom(wrapped)


def _mnn_copy_output(tensor: object) -> np.ndarray:
    shape = tuple(tensor.getShape())
    host = MNN.Tensor(
        shape,
        MNN.Halide_Type_Float,
        MNN.Tensor_DimensionType_Caffe,
    )
    tensor.copyToHostTensor(host)
    # MNN owns the host tensor storage; detach before the temporary host is
    # destroyed or later model calls can silently reuse the same memory.
    return np.asarray(host.getNumpyData(), dtype=np.float32).copy()


def decode_image(payload: bytes) -> np.ndarray:
    if not payload or len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Ảnh trống hoặc lớn hơn 20 MB.")
    try:
        image = Image.open(io.BytesIO(payload))
        image = ImageOps.exif_transpose(image).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=415, detail="Không đọc được định dạng ảnh này.") from exc
    if image.width < 96 or image.height < 96:
        raise HTTPException(status_code=422, detail="Ảnh cần có kích thước tối thiểu 96×96.")
    if image.width * image.height > 40_000_000:
        raise HTTPException(status_code=413, detail="Ảnh có độ phân giải quá lớn.")
    return np.asarray(image, dtype=np.uint8)


def _predict_contour(rgb: np.ndarray) -> np.ndarray:
    model_rgb = cv2.resize(rgb, (320, 480), interpolation=cv2.INTER_AREA)
    tensor = model_rgb.astype(np.float32).transpose(2, 0, 1)[None]
    session = contour_session()
    with _session_lock:
        logits = session.run(None, {session.get_inputs()[0].name: tensor})[0][0]
    mask = np.clip(logits[1], 0.0, 1.0)
    return np.clip(mask, 0.0, 1.0).astype(np.float32)


@lru_cache(maxsize=1)
def face_detector() -> FaceDetector:
    """Load Kumoo's recovered Fd model, not a generic detector fallback."""

    return FaceDetector(FACE_DETECT_MODEL)


@lru_cache(maxsize=1)
def landmark_detector() -> LandmarkDetector:
    """Load Kumo's recovered 106-point face landmark model."""

    return LandmarkDetector(FACE_LANDMARK_MODEL)


@lru_cache(maxsize=1)
def gender_age_classifier() -> GenderAgeClassifier:
    """Load Kumoo's recovered Ga2 demographic-slot classifier."""

    return GenderAgeClassifier(GENDER_AGE_MODEL)


def _face_detections(rgb: np.ndarray) -> list[dict[str, object]]:
    height, width = rgb.shape[:2]
    with _detector_lock:
        detected = face_detector().detect(
            cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), threshold=0.35, max_faces=8
        )

    detections: list[dict[str, object]] = []
    for face in detected:
        x1, y1, x2, y2 = face["box"]
        x1 = int(np.clip(round(x1), 0, width - 1))
        y1 = int(np.clip(round(y1), 0, height - 1))
        x2 = int(np.clip(round(x2), x1 + 1, width))
        y2 = int(np.clip(round(y2), y1 + 1, height))
        detections.append(
            {
                "box": (x1, y1, x2 - x1, y2 - y1),
                "keypoints": face.get("keypoints"),
                "score": face.get("score"),
            }
        )
    detections.sort(key=lambda item: (item["box"][0], item["box"][1]))
    return detections


def _face_boxes(rgb: np.ndarray) -> list[tuple[int, int, int, int]]:
    return [tuple(item["box"]) for item in _face_detections(rgb)]


def _face_thumbnail(rgb: np.ndarray, box: tuple[int, int, int, int]) -> str:
    """Return a compact round-avatar source for matching a row to a person."""

    x, y, width, height = box
    center_x = x + width * 0.5
    center_y = y + height * 0.48
    side = max(width, height) * 1.28
    x1 = max(0, int(round(center_x - side * 0.5)))
    y1 = max(0, int(round(center_y - side * 0.5)))
    x2 = min(rgb.shape[1], int(round(center_x + side * 0.5)))
    y2 = min(rgb.shape[0], int(round(center_y + side * 0.5)))
    crop = rgb[y1:y2, x1:x2]
    if crop.size == 0:
        return ""
    avatar = Image.fromarray(crop).resize((96, 96), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    avatar.save(buffer, format="JPEG", quality=82, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def analyze_faces(
    rgb: np.ndarray,
    boxes: list[tuple[int, int, int, int]] | None = None,
    detections: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    """Classify every Fd face into one of Kumo's five preset slots."""

    if detections is None:
        if boxes is None:
            detections = _face_detections(rgb)
        else:
            detections = [{"box": box, "keypoints": None} for box in boxes]
    boxes = [tuple(item["box"]) for item in detections]
    if not boxes:
        raise HTTPException(
            status_code=422,
            detail="Fd.onnx không phát hiện được khuôn mặt trong ảnh.",
        )
    faces: list[dict[str, object]] = []
    for index, (box, detection) in enumerate(zip(boxes, detections)):
        try:
            prediction = gender_age_classifier().classify(
                rgb,
                box,
                detection.get("keypoints"),
            )
        except (OSError, RuntimeError, ValueError) as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Ga2.onnx không phân loại được khuôn mặt {index + 1}.",
            ) from exc
        profile_key = str(prediction["profile"])
        faces.append(
            {
                "id": index,
                "box": list(box),
                "thumbnail": _face_thumbnail(rgb, box),
                "profile": profile_key,
                "label": PROFILE_LABELS[profile_key],
                "confidence": prediction["confidence"],
                "age_group": prediction["age_group"],
                "demographic_class": prediction["demographic_class"],
                "aligned": prediction["aligned"],
                "review_required": float(prediction["confidence"]) < 0.8,
                "preset": KUMO_GOC_PROFILES[profile_key],
            }
        )
    return faces


def face_landmark_sets(
    rgb: np.ndarray, detections: list[dict]
) -> list[np.ndarray]:
    """Run Kumo Lp once per Fd box and keep original-image coordinates."""

    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    landmark_sets: list[np.ndarray] = []
    for index, item in enumerate(detections):
        x, y, w, h = item["box"]
        x, y, box_width, box_height = int(x), int(y), int(w), int(h)
        keypoints = item.get("keypoints")
        with _landmark_lock:
            points = landmark_detector().detect(
                bgr, [x, y, x + box_width, y + box_height], keypoints=keypoints
            )
        if points is None or points.shape != (106, 2) or not np.all(np.isfinite(points)):
            raise HTTPException(
                status_code=422,
                detail=f"Lp.onnx không lấy đủ 106 điểm cho khuôn mặt {index + 1}.",
            )
        landmark_sets.append(points.astype(np.float32))
    return landmark_sets


def _expanded_face_crop(
    box: tuple[int, int, int, int], image_width: int, image_height: int
) -> tuple[int, int, int, int]:
    x, y, width, height = box
    center_x = x + width * 0.5
    center_y = y + height * 0.58
    crop_width = width * 2.7
    crop_height = max(height * 3.4, crop_width * 1.5)
    crop_width = max(crop_width, crop_height * (2.0 / 3.0))

    x1 = max(0, int(round(center_x - crop_width * 0.5)))
    y1 = max(0, int(round(center_y - crop_height * 0.5)))
    x2 = min(image_width, int(round(center_x + crop_width * 0.5)))
    y2 = min(image_height, int(round(center_y + crop_height * 0.5)))
    return x1, y1, x2, y2


def _photo_face_contour_crop(
    box: tuple[int, int, int, int], image_width: int, image_height: int
) -> tuple[int, int, int, int]:
    """Keep one Fd face large and isolated in PhotoFaceContour's 2:3 input."""

    x, y, width, height = box
    center_x = x + width * 0.5
    center_y = y + height * 0.52
    crop_height = max(height * 1.45, width * 2.025)
    crop_width = max(width * 1.35, crop_height * (2.0 / 3.0))
    crop_height = max(crop_height, crop_width * 1.5)

    x1 = max(0, int(round(center_x - crop_width * 0.5)))
    y1 = max(0, int(round(center_y - crop_height * 0.5)))
    x2 = min(image_width, int(round(center_x + crop_width * 0.5)))
    y2 = min(image_height, int(round(center_y + crop_height * 0.5)))
    return x1, y1, x2, y2


def _landmark_contour_fallback(
    image_shape: tuple[int, int],
    points: np.ndarray,
    box: tuple[int, int, int, int],
) -> np.ndarray:
    """Build a conservative face-skin contour from Kumo Lp106 landmarks.

    PhotoFaceContour occasionally returns an empty plane for a small or partly
    occluded member of a group photo. Lp106 has already localized that same
    face, so use its verified jaw/temple geometry to keep the failure local to
    that face instead of rejecting every other person in the image.
    """

    height, width = image_shape
    contour = points[LANDMARK_GROUPS["contour"]].astype(np.float32)
    left_eye = points[LANDMARK_GROUPS["left_eye"]].mean(axis=0)
    right_eye = points[LANDMARK_GROUPS["right_eye"]].mean(axis=0)
    eye_span = max(float(np.linalg.norm(right_eye - left_eye)), 1.0)
    center_x = float((left_eye[0] + right_eye[0]) * 0.5)
    brow_y = float(
        min(
            points[LANDMARK_GROUPS["left_brow"], 1].min(),
            points[LANDMARK_GROUPS["right_brow"], 1].min(),
        )
    )
    top_y = brow_y - eye_span * 0.88
    half_width = max(
        center_x - float(contour[:, 0].min()),
        float(contour[:, 0].max()) - center_x,
        float(box[2]) * 0.46,
    )
    forehead = np.array(
        [
            [center_x - half_width * 0.98, brow_y - eye_span * 0.25],
            [center_x - half_width * 0.88, top_y + eye_span * 0.12],
            [center_x - half_width * 0.50, top_y + eye_span * 0.02],
            [center_x, top_y],
            [center_x + half_width * 0.50, top_y + eye_span * 0.02],
            [center_x + half_width * 0.88, top_y + eye_span * 0.12],
            [center_x + half_width * 0.98, brow_y - eye_span * 0.25],
        ],
        dtype=np.float32,
    )
    hull_points = np.concatenate([contour, forehead], axis=0)
    hull_points[:, 0] = np.clip(hull_points[:, 0], 0, width - 1)
    hull_points[:, 1] = np.clip(hull_points[:, 1], 0, height - 1)

    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.fillConvexPoly(mask, cv2.convexHull(hull_points.astype(np.int32)), 255)
    sigma = max(1.2, eye_span * 0.018)
    mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=sigma, sigmaY=sigma)
    return mask.astype(np.float32) / 255.0


def _ensure_coreml_runner() -> bool:
    """Build the independent Apple CoreML CPU bridge when needed."""

    if sys.platform != "darwin" or not COREML_RUNNER_SOURCE.is_file():
        return False
    with _coreml_lock:
        if (
            COREML_RUNNER.is_file()
            and COREML_RUNNER.stat().st_mtime >= COREML_RUNNER_SOURCE.stat().st_mtime
        ):
            return True
        COREML_RUNNER.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                [
                    "xcrun",
                    "clang++",
                    "-std=c++17",
                    "-fobjc-arc",
                    "-framework",
                    "Foundation",
                    "-framework",
                    "CoreML",
                    str(COREML_RUNNER_SOURCE),
                    "-o",
                    str(COREML_RUNNER),
                ],
                check=True,
                capture_output=True,
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError):
            return False
    return COREML_RUNNER.is_file()


def _coreml_image_prediction(
    rgb: np.ndarray,
    model_path: Path,
    model_width: int,
    model_height: int,
    output_channels: int,
) -> np.ndarray:
    """Run a recovered Kumo CoreML image-to-image graph with its RGB 0..1 contract."""

    if not _ensure_coreml_runner():
        raise HTTPException(
            status_code=503,
            detail="Apple CoreML CPU runner chưa sẵn sàng trên máy này.",
        )
    resized = cv2.resize(
        rgb, (model_width, model_height), interpolation=cv2.INTER_AREA
    ).astype(np.float32)
    tensor = np.ascontiguousarray((resized / 255.0).transpose(2, 0, 1)[None])
    with tempfile.TemporaryDirectory(prefix="lumi-coreml-") as temp_dir:
        input_path = Path(temp_dir) / "input.raw"
        output_path = Path(temp_dir) / "output.raw"
        tensor.tofile(input_path)
        try:
            with _coreml_lock:
                completed = subprocess.run(
                    [
                        str(COREML_RUNNER),
                        str(model_path),
                        str(input_path),
                        str(output_path),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=90,
                )
        except (OSError, subprocess.SubprocessError) as exc:
            detail = getattr(exc, "stderr", b"")
            if isinstance(detail, bytes):
                detail = detail.decode("utf-8", errors="replace")
            raise HTTPException(
                status_code=500,
                detail=f"CoreML không chạy được {model_path.name}: {str(detail).strip()}",
            ) from exc
        if completed.returncode != 0 or not output_path.is_file():
            raise HTTPException(status_code=500, detail="CoreML không xuất kết quả.")
        output = np.fromfile(output_path, dtype=np.float32)

    expected = output_channels * model_height * model_width
    if output.size != expected or not np.all(np.isfinite(output)):
        raise HTTPException(
            status_code=500,
            detail=f"Output {model_path.name} không đúng contract {output_channels}×{model_height}×{model_width}.",
        )
    output = output.reshape(output_channels, model_height, model_width)
    return output.transpose(1, 2, 0)


def face_contour_masks(
    rgb: np.ndarray,
    boxes: list[tuple[int, int, int, int]] | None = None,
    landmark_sets: list[np.ndarray] | None = None,
) -> list[np.ndarray]:
    """Return one PhotoFaceContour mask for every localized Fd face."""

    height, width = rgb.shape[:2]
    boxes = boxes if boxes is not None else _face_boxes(rgb)
    if not boxes:
        raise HTTPException(
            status_code=422,
            detail="Fd.onnx không phát hiện được khuôn mặt trong ảnh.",
        )

    if landmark_sets is not None and len(landmark_sets) != len(boxes):
        raise HTTPException(
            status_code=422,
            detail="Lp.onnx không lấy đủ 106 điểm cho mọi khuôn mặt.",
        )

    masks: list[np.ndarray] = []
    fallback_landmarks = landmark_sets
    for index, box in enumerate(boxes):
        face_mask = np.zeros((height, width), dtype=np.float32)
        x1, y1, x2, y2 = _photo_face_contour_crop(box, width, height)
        coverage = 0.0
        if x2 - x1 >= 64 and y2 - y1 >= 64:
            crop_mask = _predict_contour(rgb[y1:y2, x1:x2])
            coverage = float(np.mean(crop_mask > 0.35))
            if float(crop_mask.max()) >= 0.35 and coverage >= 0.006:
                crop_mask = cv2.resize(
                    crop_mask, (x2 - x1, y2 - y1), interpolation=cv2.INTER_LINEAR
                )
                face_mask[y1:y2, x1:x2] = crop_mask

        if float(face_mask.max()) < 0.35:
            if fallback_landmarks is None:
                fallback_landmarks = face_landmark_sets(rgb, boxes)
            face_mask = _landmark_contour_fallback(
                (height, width), fallback_landmarks[index], box
            )
            _timing_log.warning(
                "PhotoFaceContour face %d/%d was empty (crop=%dx%d, coverage=%.5f); "
                "using the same face's Kumo Lp106 contour.",
                index + 1,
                len(boxes),
                x2 - x1,
                y2 - y1,
                coverage,
            )
        else:
            if fallback_landmarks is None and landmark_sets is not None:
                fallback_landmarks = landmark_sets
            elif fallback_landmarks is None:
                fallback_landmarks = face_landmark_sets(rgb, boxes)
            landmark_mask = _landmark_contour_fallback(
                (height, width), fallback_landmarks[index], box
            )
            # Clip neural segmentation to the localized face hull so it does not spill over to adjacent people/clothes/hair
            clipped = face_mask * (landmark_mask > 0.05).astype(np.float32)
            face_mask = clipped if float(clipped.max()) >= 0.35 else landmark_mask
        masks.append(face_mask)

    if len(masks) != len(boxes) or any(float(mask.max()) < 0.35 for mask in masks):
        raise HTTPException(
            status_code=422,
            detail="Kumo không tạo được vùng da an toàn cho mọi khuôn mặt.",
        )

    return masks


def face_contour_mask(
    rgb: np.ndarray, boxes: list[tuple[int, int, int, int]] | None = None
) -> np.ndarray:
    """Return the union of all per-face PhotoFaceContour masks."""

    masks = face_contour_masks(rgb, boxes)
    return np.maximum.reduce(masks).astype(np.float32)


def landmark_skin_masks(
    rgb: np.ndarray,
    contours: list[np.ndarray],
    boxes: list[tuple[int, int, int, int]],
    landmark_sets: list[np.ndarray] | None = None,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Build one landmark-protected skin mask for each detected face."""

    height, width = rgb.shape[:2]
    skin_masks: list[np.ndarray] = []
    landmark_sets = landmark_sets or face_landmark_sets(rgb, boxes)

    try:
        hair_prob, _ = _hair_parse_planes(rgb)
        hair_exclusion = np.clip(1.0 - hair_prob * 1.6, 0.0, 1.0)
    except Exception:
        hair_exclusion = np.ones((height, width), dtype=np.float32)

    for contour, points in zip(contours, landmark_sets):
        protected = np.zeros((height, width), dtype=np.uint8)
        left_eye = points[LANDMARK_GROUPS["left_eye"]].mean(axis=0)
        right_eye = points[LANDMARK_GROUPS["right_eye"]].mean(axis=0)
        eye_span = max(float(np.linalg.norm(right_eye - left_eye)), 1.0)
        grow = max(3, int(round(eye_span * 0.10)))
        if grow % 2 == 0:
            grow += 1
        for group in (
            "left_eye",
            "right_eye",
            "left_brow",
            "right_brow",
            "nose",
            "mouth_outer",
            "mouth_inner",
        ):
            protected = np.maximum(
                protected,
                LandmarkDetector.polygon_mask(
                    (height, width),
                    points,
                    LANDMARK_GROUPS[group],
                    dilate=grow,
                ),
            )

        protected = cv2.GaussianBlur(protected, (0, 0), sigmaX=2.5, sigmaY=2.5)
        skin = contour * (1.0 - protected.astype(np.float32) / 255.0) * hair_exclusion
        skin_masks.append(np.clip(skin, 0.0, 1.0).astype(np.float32))

    if len(landmark_sets) != len(boxes) or len(skin_masks) != len(boxes):
        raise HTTPException(
            status_code=422,
            detail="Lp.onnx không lấy đủ 106 điểm mắt, mũi, môi cho mọi khuôn mặt.",
        )

    return skin_masks, landmark_sets


def landmark_skin_mask(
    rgb: np.ndarray,
    contour: np.ndarray,
    boxes: list[tuple[int, int, int, int]],
) -> tuple[np.ndarray, list[np.ndarray]]:
    """Compatibility wrapper returning a combined landmark-safe mask."""

    contours = [contour for _ in boxes]
    masks, landmarks = landmark_skin_masks(rgb, contours, boxes)
    return np.maximum.reduce(masks).astype(np.float32), landmarks


@lru_cache(maxsize=1)
def _white_skin_lut() -> np.ndarray:
    return np.asarray(Image.open(WHITE_SKIN_LUT).convert("RGB"), dtype=np.float32) / 255.0


def _apply_64_cube_lut(rgb: np.ndarray, lut: np.ndarray) -> np.ndarray:
    """CPU equivalent of Kumo shader_506.glsl / GPUImageLookupFilter 512x512, 64³ LUT sampler."""

    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    blue_index = blue * 63.0
    lower = np.floor(blue_index)
    upper = np.clip(lower + 1.0, 0.0, 63.0)
    fraction = blue_index - lower

    def sample(index: np.ndarray) -> np.ndarray:
        tile_y = np.floor(index / 8.0)
        tile_x = index - tile_y * 8.0
        # GPUImageLookupFilter pixel center alignment: (quad * 64.0 + 0.5 + c * 63.0)
        map_x = np.ascontiguousarray(tile_x * 64.0 + 0.5 + red * 63.0, dtype=np.float32)
        map_y = np.ascontiguousarray(tile_y * 64.0 + 0.5 + green * 63.0, dtype=np.float32)
        return cv2.remap(
            lut,
            map_x,
            map_y,
            cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )

    return sample(lower) * (1.0 - fraction[..., None]) + sample(upper) * fraction[..., None]


@lru_cache(maxsize=10)
def _skin_color_lut(preset_name: str) -> np.ndarray | None:
    lut_file = ROOT / "assets" / "materials" / "skinlut" / f"{preset_name}.png"
    if not lut_file.is_file():
        return None
    lut_bgr = cv2.imread(str(lut_file))
    if lut_bgr is None:
        return None
    return cv2.cvtColor(lut_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0


def _apply_16_cube_lut(rgb_f: np.ndarray, lut_rgb_f: np.ndarray) -> np.ndarray:
    """Apply Kumo 16³ 3D LUT (64x64 grid arranged as 4x4 tiles of 16x16)."""
    lut_size = 16
    r = np.clip(rgb_f[..., 0] * (lut_size - 1), 0.0, lut_size - 1)
    g = np.clip(rgb_f[..., 1] * (lut_size - 1), 0.0, lut_size - 1)
    b = np.clip(rgb_f[..., 2] * (lut_size - 1), 0.0, lut_size - 1)

    b_idx0 = np.clip(np.floor(b).astype(np.int32), 0, lut_size - 1)
    b_idx1 = np.clip(b_idx0 + 1, 0, lut_size - 1)
    b_frac = (b - b_idx0)[..., None]

    tile0_y = (b_idx0 // 4) * lut_size
    tile0_x = (b_idx0 % 4) * lut_size
    tile1_y = (b_idx1 // 4) * lut_size
    tile1_x = (b_idx1 % 4) * lut_size

    map_x0 = np.ascontiguousarray(tile0_x + r, dtype=np.float32)
    map_y0 = np.ascontiguousarray(tile0_y + g, dtype=np.float32)
    map_x1 = np.ascontiguousarray(tile1_x + r, dtype=np.float32)
    map_y1 = np.ascontiguousarray(tile1_y + g, dtype=np.float32)

    sample0 = cv2.remap(lut_rgb_f, map_x0, map_y0, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    sample1 = cv2.remap(lut_rgb_f, map_x1, map_y1, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    return sample0 * (1.0 - b_frac) + sample1 * b_frac


def _apply_kumo_whitening(
    rgb: np.ndarray,
    skin_mask: np.ndarray,
    white_skin_alpha: float,
) -> np.ndarray:
    """Apply Kumo's whiteColorTexture operator only to landmark-safe skin."""

    if white_skin_alpha <= 0:
        return rgb

    whitened = _apply_64_cube_lut(rgb, _white_skin_lut())
    # Scale Kumo's 0.10 base demographic strength to a vibrant, natural 0..0.55 luminous glow
    effective_strength = min(1.0, float(white_skin_alpha) * 5.5)
    alpha = skin_mask[..., None] * effective_strength
    return np.clip(rgb * (1.0 - alpha) + whitened * alpha, 0.0, 1.0)


def _apply_kumo_group_skin_tone(
    rgb_f: np.ndarray,
    skin_mask: np.ndarray,
    alpha: float,
) -> np.ndarray:
    """Harmonize skin chrominance across face and group, eliminating blotchiness."""
    if alpha <= 0:
        return rgb_f

    rgb_u8 = np.clip(rgb_f * 255.0, 0, 255).astype(np.uint8)
    ycrcb = cv2.cvtColor(rgb_u8, cv2.COLOR_RGB2YCrCb).astype(np.float32)
    y = ycrcb[..., 0]
    cr = ycrcb[..., 1]
    cb = ycrcb[..., 2]

    skin_pixels = skin_mask > 0.30
    if not np.any(skin_pixels):
        return rgb_f

    target_cr = float(np.median(cr[skin_pixels]))
    target_cb = float(np.median(cb[skin_pixels]))

    # Smooth chrominance to eliminate blotchy redness/yellowing
    smooth_cr = cv2.GaussianBlur(cr, (0, 0), sigmaX=11.0, sigmaY=11.0)
    smooth_cb = cv2.GaussianBlur(cb, (0, 0), sigmaX=11.0, sigmaY=11.0)

    # Harmonize towards target anchor
    unified_cr = smooth_cr * 0.35 + target_cr * 0.65
    unified_cb = smooth_cb * 0.35 + target_cb * 0.65

    effective_cr = cr * (1.0 - alpha) + unified_cr * alpha
    effective_cb = cb * (1.0 - alpha) + unified_cb * alpha

    merged_ycrcb = np.dstack([y, effective_cr, effective_cb])
    merged_rgb = cv2.cvtColor(np.clip(merged_ycrcb, 0, 255).astype(np.uint8), cv2.COLOR_YCrCb2RGB).astype(np.float32) / 255.0

    m = skin_mask[..., None] * alpha
    return np.clip(rgb_f * (1.0 - m) + merged_rgb * m, 0.0, 1.0)


def _apply_kumo_body_skin_balance(rgb: np.ndarray) -> np.ndarray:
    """Restore Kumo's chroma-only body skin-tone stage without green shift."""

    source = np.clip(rgb.astype(np.float32), 0.0, 1.0)
    red = source[..., 0]
    green = source[..., 1]
    blue = source[..., 2]
    chroma = np.max(source, axis=2) - np.min(source, axis=2)
    warmth = np.clip(red - np.maximum(green, blue), 0.0, 1.0)
    gate = np.clip(warmth * 8.0, 0.0, 1.0) * np.clip(chroma * 4.0, 0.0, 1.0)

    balanced = source.copy()
    # Lift blue slightly to make skin porcelain and reduce yellow/red discoloration, without adding green
    balanced[..., 2] += (red - blue) * (0.08 * gate)
    return np.clip(balanced, 0.0, 1.0).astype(np.float32)


@lru_cache(maxsize=len(KUMO_LIPSTICK_PRESETS))
def _lipstick_texture(preset_key: str) -> np.ndarray:
    preset = KUMO_LIPSTICK_PRESETS[preset_key]
    return np.asarray(Image.open(preset["texture"]).convert("RGBA"), dtype=np.float32) / 255.0


def _apply_kumo_lipstick(
    rgb: np.ndarray,
    landmark_sets: list[np.ndarray],
    preset_alphas: list[float] | None = None,
    preset_key: str = "luozhuang",
) -> np.ndarray:
    """Recreate Kumo MPLIPSTICKV2 material with its original BlendMultiply contract."""

    if preset_key not in KUMO_LIPSTICK_PRESETS or (preset_alphas is not None and all(a <= 0 for a in preset_alphas)):
        return rgb

    height, width = rgb.shape[:2]
    result = rgb.copy()
    preset = KUMO_LIPSTICK_PRESETS[preset_key]
    texture = _lipstick_texture(preset_key)
    rectangle = preset["rectangle"]
    material_alpha = float(preset["material_alpha"])
    source_quad = np.array(
        [
            [0, 0],
            [texture.shape[1] - 1, 0],
            [texture.shape[1] - 1, texture.shape[0] - 1],
            [0, texture.shape[0] - 1],
        ],
        dtype=np.float32,
    )

    preset_alphas = preset_alphas or [LIPSTICK_PRESET_ALPHA] * len(landmark_sets)
    for points, preset_alpha in zip(landmark_sets, preset_alphas):
        if preset_alpha <= 0:
            continue
        outer = points[LANDMARK_GROUPS["mouth_outer"]].astype(np.float32)
        center = outer.mean(axis=0)
        _, eigenvectors = np.linalg.eigh(np.cov((outer - center).T))
        axis_x = eigenvectors[:, -1].astype(np.float32)
        if axis_x[0] < 0:
            axis_x = -axis_x
        axis_y = np.array([-axis_x[1], axis_x[0]], dtype=np.float32)
        if axis_y[1] < 0:
            axis_y = -axis_y

        projected = (outer - center) @ axis_x
        material_width = max(float(projected.max() - projected.min()) * 1.08, 4.0)
        # Exact aspect ratio from each Kumo MakeupConfigure Rectangle.
        material_height = material_width * (float(rectangle[3]) / float(rectangle[2]))
        destination_quad = np.array(
            [
                center - axis_x * material_width / 2 - axis_y * material_height / 2,
                center + axis_x * material_width / 2 - axis_y * material_height / 2,
                center + axis_x * material_width / 2 + axis_y * material_height / 2,
                center - axis_x * material_width / 2 + axis_y * material_height / 2,
            ],
            dtype=np.float32,
        )
        bounds = cv2.boundingRect(destination_quad.astype(np.float32))
        roi_x = max(0, bounds[0] - 3)
        roi_y = max(0, bounds[1] - 3)
        roi_x2 = min(width, bounds[0] + bounds[2] + 3)
        roi_y2 = min(height, bounds[1] + bounds[3] + 3)
        if roi_x2 <= roi_x or roi_y2 <= roi_y:
            continue
        local_quad = destination_quad - np.array([roi_x, roi_y], dtype=np.float32)
        transform = cv2.getPerspectiveTransform(source_quad, local_quad)
        material = cv2.warpPerspective(
            texture,
            transform,
            (roi_x2 - roi_x, roi_y2 - roi_y),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
        )

        lip_mask = np.zeros((roi_y2 - roi_y, roi_x2 - roi_x), dtype=np.uint8)
        local_outer = outer - np.array([roi_x, roi_y], dtype=np.float32)
        cv2.fillConvexPoly(lip_mask, cv2.convexHull(local_outer.astype(np.int32)), 255)
        inner = (
            points[LANDMARK_GROUPS["mouth_inner"]]
            - np.array([roi_x, roi_y], dtype=np.float32)
        ).astype(np.int32)
        cv2.fillConvexPoly(lip_mask, cv2.convexHull(inner), 0)
        lip_mask = cv2.GaussianBlur(lip_mask, (0, 0), sigmaX=1.2, sigmaY=1.2)
        alpha = (
            material[..., 3]
            * (lip_mask.astype(np.float32) / 255.0)
            * material_alpha
            * preset_alpha
        )
        target = result[roi_y:roi_y2, roi_x:roi_x2]
        # Kumoo rich lipstick tint: combines soft-light luminance with vivid pigment
        tint = np.clip(target * material[..., :3] * 1.5 + material[..., :3] * 0.4, 0.0, 1.0)
        result[roi_y:roi_y2, roi_x:roi_x2] = (
            target * (1.0 - alpha[..., None]) + tint * alpha[..., None]
        )

    return np.clip(result, 0.0, 1.0)


def _blemish_skin_mask_from_landmarks(
    image_shape: tuple[int, int],
    crop_origin: tuple[int, int],
    face_contour: np.ndarray,
    landmark_points: np.ndarray | None,
) -> np.ndarray:
    """Approximate Kumoo's FleckFlaw skin parsing mask for the face crop.

    The smoothing/tone mask protects the nose as an organ landmark, which leaves
    the exact "Acne (Face)" control visibly under-applied on the nose bridge and
    central cheeks.  Native `GPUImageFleckFlawCleanFilter` gates with a parsing
    skin texture instead: eyes, brows and lips are protected, but nose skin still
    receives the defect-clean pass.
    """

    height, width = image_shape
    mask = np.clip(face_contour, 0.0, 1.0).astype(np.float32)
    if landmark_points is None or landmark_points.shape[0] < 3:
        return mask

    x0, y0 = crop_origin
    points = np.asarray(landmark_points, dtype=np.float32).copy()
    points[:, 0] -= float(x0)
    points[:, 1] -= float(y0)
    valid = (
        (points[:, 0] >= -width * 0.10)
        & (points[:, 0] <= width * 1.10)
        & (points[:, 1] >= -height * 0.10)
        & (points[:, 1] <= height * 1.10)
    )
    if int(np.count_nonzero(valid)) < 16:
        return mask

    left_eye = points[LANDMARK_GROUPS["left_eye"]].mean(axis=0)
    right_eye = points[LANDMARK_GROUPS["right_eye"]].mean(axis=0)
    eye_span = max(float(np.linalg.norm(right_eye - left_eye)), 1.0)
    grow = max(3, int(round(eye_span * 0.11)))
    if grow % 2 == 0:
        grow += 1
    protected = np.zeros((height, width), dtype=np.uint8)
    for group in (
        "left_eye",
        "right_eye",
        "left_brow",
        "right_brow",
        "mouth_outer",
        "mouth_inner",
    ):
        protected = np.maximum(
            protected,
            LandmarkDetector.polygon_mask(
                (height, width),
                points,
                LANDMARK_GROUPS[group],
                dilate=grow,
            ),
        )

    protected = cv2.GaussianBlur(protected, (0, 0), sigmaX=2.2, sigmaY=2.2)
    return np.clip(mask * (1.0 - protected.astype(np.float32) / 255.0), 0.0, 1.0)


def _sigmoid(values: np.ndarray) -> np.ndarray:
    values = np.clip(values, -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-values))


def _kumo_blemish_mask_prediction(crop_u8: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Run Kumoo's recovered mask detector for flaw and nevus textures.

    `Expelliarmus` is the missing 1024×1024 two-channel graph used before the
    final BlackHead/FleckFlaw shader.  Channel 0 is the flaw/freckle confidence
    texture; channel 1 is the nevus keep texture used when mole removal is off.
    """

    source = Image.fromarray(crop_u8).resize(
        (BLEMISH_MASK_MODEL_WIDTH, BLEMISH_MASK_MODEL_HEIGHT),
        Image.Resampling.BILINEAR,
    )
    tensor = np.asarray(source, dtype=np.float32) / 255.0
    tensor = np.transpose(tensor, (2, 0, 1))[None, ...]
    session = blemish_mask_session()
    output = session.run(None, {session.get_inputs()[0].name: tensor})[0][0]
    
    # Native calibration: Expelliarmus logits center around ~0.0 (prob ~0.50).
    # Flaw spots have logits > 0.15 (prob > 0.537), while clear skin is <= 0.50.
    sig0 = _sigmoid(output[0]).astype(np.float32)
    sig1 = _sigmoid(output[1]).astype(np.float32)
    
    # Statistical calibration for Expelliarmus:
    # Spots, acne, marks and blemishes live in sig0 > 0.50.
    flaw_mask = np.clip((sig0 - 0.495) / 0.12, 0.0, 1.0)
    nevus_mask = np.clip((sig1 - 0.52) / 0.12, 0.0, 1.0)
    return flaw_mask, nevus_mask


def _kumo_fleck_flaw_weight(
    current: np.ndarray,
    healed: np.ndarray,
    fuxi_validity: np.ndarray,
    flaw_mask_texture: np.ndarray | None,
    nevus_mask_texture: np.ndarray | None,
    blemish_skin: np.ndarray,
    face_contour: np.ndarray,
    blemish_alpha: float,
) -> np.ndarray:
    """Recover Kumoo's FleckFlaw shader gating as far as local assets allow.

    Native `GPUImageBlackHeadCleanFilter` shader:
        weight = fleckmask * skinMask * (1.0 - deepSmooth.b) * deepSmooth.r
    """

    skin = np.clip(blemish_skin, 0.0, 1.0).astype(np.float32)
    contour = np.clip(face_contour, 0.0, 1.0).astype(np.float32)

    h, w = current.shape[:2]
    if h < 2 or w < 2:
        return np.zeros((h, w, 1), dtype=np.float32)

    if flaw_mask_texture is not None:
        raw_flaw = np.clip(flaw_mask_texture, 0.0, 1.0).astype(np.float32)
        if raw_flaw.ndim == 2:
            raw_flaw = raw_flaw[..., None]
        flaw_mask = raw_flaw
    else:
        flaw_mask = np.zeros((h, w, 1), dtype=np.float32)

    # Direct native BlackHead clean weighting
    # flaw_mask drives defect spots, skin confines to face skin plate, blemish_alpha controls strength
    flaw_weight = np.clip(flaw_mask * 1.6, 0.0, 1.0)
    weight = flaw_weight * skin * blemish_alpha
    if nevus_mask_texture is not None:
        nevus_keep = np.clip(nevus_mask_texture * contour * 1.2, 0.0, 1.0)
        if nevus_keep.ndim == 2:
            nevus_keep = nevus_keep[..., None]
        weight = weight * (1.0 - nevus_keep)

    return np.clip(weight, 0.0, 1.0)


def _kumo_texture_preserved_res_color(
    current: np.ndarray,
    res_color: np.ndarray,
) -> np.ndarray:
    """Apply Kumoo's recovered low-pass residual compositor for clean skin.

    Several recovered face-clean/blackhead shaders use:

        color = oriColor.rgb + (resColor - lowPassTexture.rgb)

    instead of displaying the neural/restored RGB directly.  That preserves the
    source high-frequency skin texture while replacing the low-frequency defect
    plate produced by the model.
    """

    h, w = current.shape[:2]
    low_sigma = max(2.0, min(h, w) / 42.0)
    low_color = cv2.GaussianBlur(
        current,
        (0, 0),
        sigmaX=low_sigma,
        sigmaY=low_sigma,
    )
    return np.clip(current + (res_color - low_color), 0.0, 1.0)


def _apply_coreml_face_models(
    rgb_u8: np.ndarray,
    skin_masks: list[np.ndarray],
    face_contours: list[np.ndarray],
    boxes: list[tuple[int, int, int, int]],
    smooth_alphas: list[float],
    blemish_alphas: list[float],
    smooth_texture_alphas: list[float] | None = None,
    landmark_sets: list[np.ndarray] | None = None,
) -> np.ndarray:
    """Apply Kumo's facial smoothing and blemish-healing graphs to face crops."""

    height, width = rgb_u8.shape[:2]
    result = rgb_u8.astype(np.float32) / 255.0
    landmark_sets = landmark_sets or [None] * len(boxes)
    smooth_texture_alphas = smooth_texture_alphas or [0.0] * len(boxes)
    for box, skin_mask, face_contour, smooth_alpha, blemish_alpha, smooth_texture_alpha, points in zip(
        boxes,
        skin_masks,
        face_contours,
        smooth_alphas,
        blemish_alphas,
        smooth_texture_alphas,
        landmark_sets,
    ):
        if smooth_alpha <= 0.0 and blemish_alpha <= 0.0 and smooth_texture_alpha <= 0.0:
            continue
        x1, y1, x2, y2 = _expanded_face_crop(box, width, height)
        if x2 - x1 < 64 or y2 - y1 < 64:
            continue
        crop_skin_mask = np.clip(skin_mask[y1:y2, x1:x2], 0.0, 1.0)[..., None]
        crop_face_contour = np.clip(
            face_contour[y1:y2, x1:x2], 0.0, 1.0
        )[..., None]
        if float(crop_face_contour.max()) < 0.35:
            continue
        crop_blemish_skin = _blemish_skin_mask_from_landmarks(
            (y2 - y1, x2 - x1),
            (x1, y1),
            crop_face_contour[..., 0],
            points,
        )[..., None]

        current = result[y1:y2, x1:x2]
        if smooth_alpha > 0.0 or smooth_texture_alpha > 0.0:
            crop_u8 = np.clip(current * 255.0, 0, 255).astype(np.uint8)
            h_c, w_c = current.shape[:2]
            
            # Kumoo GPUImageSkinSmoothHDFilter + Neutral Gray Smooth:
            # 1. Edge-preserving surface smoothing on Luminance to prevent artificial brightening
            ycrcb = cv2.cvtColor(crop_u8, cv2.COLOR_RGB2YCrCb)
            y_plane = ycrcb[..., 0].astype(np.float32) / 255.0
            cr_plane = ycrcb[..., 1].astype(np.float32) / 255.0
            cb_plane = ycrcb[..., 2].astype(np.float32) / 255.0

            # 1. Native Neural model for subtle chromatic and surface gradient leveling
            smooth_pred = _coreml_image_prediction(
                crop_u8, FACIAL_SMOOTH_MODEL, 384, 384, 3
            )[..., :3]
            res_color = cv2.resize(
                np.clip(smooth_pred, 0.0, 1.0),
                (w_c, h_c),
                interpolation=cv2.INTER_CUBIC,
            )
            ycrcb_neural = cv2.cvtColor((res_color * 255).astype(np.uint8), cv2.COLOR_RGB2YCrCb).astype(np.float32) / 255.0
            
            # Smooth Y from Kumoo neural model
            smooth_y = ycrcb_neural[..., 0]
            low_sigma = max(3.5, min(h_c, w_c) / 44.0)
            low_y_ori = cv2.GaussianBlur(y_plane, (0, 0), sigmaX=low_sigma, sigmaY=low_sigma)
            low_y_smooth = cv2.GaussianBlur(smooth_y, (0, 0), sigmaX=low_sigma, sigmaY=low_sigma)

            # High-frequency texture (micro pore grain) with soft-coring threshold
            # Coring isolates fine pore variations (|h| <= 0.035) while suppressing
            # large blotches, brown freckles, and acne defects (|h| > 0.045).
            high_texture = y_plane - low_y_ori
            coring_factor = np.exp(-np.square(high_texture / 0.038))
            pore_texture = high_texture * coring_factor

            tex_alpha = float(np.clip(smooth_texture_alpha, 0.0, 1.0))
            nat_alpha = float(np.clip(smooth_alpha, 0.0, 1.0))

            # Texture-preserved smooth: smoothed skin base + crisp micro pores
            # Natural smooth: deeper silky porcelain smooth with softer pores
            if tex_alpha > 0.0 and nat_alpha > 0.0:
                tex_weight = tex_alpha / (tex_alpha + nat_alpha)
                pore_scale = 1.15 * tex_weight + 0.30 * (1.0 - tex_weight)
                target_y = smooth_y + pore_texture * pore_scale
                total_alpha = max(tex_alpha, nat_alpha)
                final_y = np.clip(y_plane * (1.0 - total_alpha) + target_y * total_alpha, 0.0, 1.0)
            elif tex_alpha > 0.0:
                # 100% texture preservation (pores crystal clear, blotchiness & roughness eliminated)
                target_y = smooth_y + pore_texture * 1.15
                final_y = np.clip(y_plane * (1.0 - tex_alpha) + target_y * tex_alpha, 0.0, 1.0)
                total_alpha = tex_alpha
            else:
                # Natural smooth (silky porcelain, natural tone)
                target_y = smooth_y + pore_texture * 0.30
                final_y = np.clip(y_plane * (1.0 - nat_alpha) + target_y * nat_alpha, 0.0, 1.0)
                total_alpha = nat_alpha

            # Chrominance smoothing (smooths redness, blotchy patches without shifting color tone)
            smooth_cr = cv2.GaussianBlur(cr_plane, (0, 0), sigmaX=max(2.0, low_sigma / 2.0))
            smooth_cb = cv2.GaussianBlur(cb_plane, (0, 0), sigmaX=max(2.0, low_sigma / 2.0))
            cr_blend = cr_plane * (1.0 - total_alpha * 0.85) + smooth_cr * (total_alpha * 0.85)
            cb_blend = cb_plane * (1.0 - total_alpha * 0.85) + smooth_cb * (total_alpha * 0.85)

            final_ycrcb = np.stack([
                (final_y * 255.0).astype(np.uint8),
                (cr_blend * 255.0).astype(np.uint8),
                (cb_blend * 255.0).astype(np.uint8),
            ], axis=-1)
            target_smooth = cv2.cvtColor(final_ycrcb, cv2.COLOR_YCrCb2RGB).astype(np.float32) / 255.0
            
            smooth_mask = crop_blemish_skin * total_alpha
            current = current * (1.0 - smooth_mask) + target_smooth * smooth_mask

        effective_blemish = max(float(blemish_alpha), float(smooth_texture_alpha) * 0.85)
        if effective_blemish <= 0.0:
            result[y1:y2, x1:x2] = current
            continue

        blemish_input_u8 = np.clip(current * 255.0, 0, 255).astype(np.uint8)
        flaw_mask_texture, nevus_mask_texture = _kumo_blemish_mask_prediction(
            blemish_input_u8
        )
        flaw_mask_texture = cv2.resize(
            flaw_mask_texture,
            (x2 - x1, y2 - y1),
            interpolation=cv2.INTER_LINEAR,
        )[..., None]
        nevus_mask_texture = cv2.resize(
            nevus_mask_texture,
            (x2 - x1, y2 - y1),
            interpolation=cv2.INTER_LINEAR,
        )[..., None]
        healed_prediction = _coreml_image_prediction(
            blemish_input_u8,
            BLEMISH_HEAL_MODEL,
            BLEMISH_MODEL_WIDTH,
            BLEMISH_MODEL_HEIGHT,
            4,
        )
        # Recovered Kumoo/Cubeo-AI path: Expelliarmus emits native
        # flawMask/nevusMask textures, while fuxiCreator emits native resColor (RGB).
        # Native GPUImageBlackHeadCleanFilter does:
        # color = mix(iColor.rgb, resColor, weight)
        healed = cv2.resize(
            np.clip(healed_prediction[..., :3], 0.0, 1.0),
            (x2 - x1, y2 - y1),
            interpolation=cv2.INTER_CUBIC,
        )
        healing_validity = np.clip(
            (healed_prediction[..., 3] + 1.0) * 0.5,
            0.0,
            1.0,
        )
        healing_validity = cv2.resize(
            healing_validity,
            (x2 - x1, y2 - y1),
            interpolation=cv2.INTER_LINEAR,
        )[..., None]
        healing_mask = _kumo_fleck_flaw_weight(
            current,
            healed,
            healing_validity,
            flaw_mask_texture,
            nevus_mask_texture,
            crop_blemish_skin,
            crop_face_contour,
            effective_blemish,
        )
        result[y1:y2, x1:x2] = current * (1.0 - healing_mask) + healed * healing_mask

    return np.clip(result, 0.0, 1.0)


def _representative_skin_rgb(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Recover the per-face colour anchor used by SkinToneBodyAPI.

    The original filter builds a luminance histogram from high-confidence skin
    pixels, discards the darkest/lightest 30 percent, then averages the centre.
    This single-face implementation follows that recovered contract and has a
    conservative fallback for very dark, backlit, or heavily made-up portraits.
    """

    pixels = rgb.reshape(-1, 3).astype(np.float32)
    confidence = mask.reshape(-1)
    high_confidence = confidence >= (241.0 / 255.0)

    red = pixels[:, 0]
    green = pixels[:, 1]
    blue = pixels[:, 2]
    skin_order = (red > green) & (red > blue) & (np.max(pixels, axis=1) <= 239.0)
    candidates = pixels[high_confidence & skin_order]
    if len(candidates) < 64:
        candidates = pixels[confidence >= 0.35]
    if len(candidates) == 0:
        raise HTTPException(
            status_code=422,
            detail="PhotoFaceContour.onnx không tạo đủ điểm da để chạy skintone.",
        )

    luminance = (
        candidates[:, 0] * 0.299
        + candidates[:, 1] * 0.587
        + candidates[:, 2] * 0.114
    )
    low, high = np.quantile(luminance, (0.30, 0.70))
    central = candidates[(luminance >= low) & (luminance <= high)]
    if len(central) < 16:
        central = candidates
    return np.mean(central, axis=0, dtype=np.float32)


def skin_tone_layer(rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Run Kumo skintone with its recovered residual colour protocol."""

    height, width = rgb.shape[:2]
    source = cv2.resize(rgb, (384, 384), interpolation=cv2.INTER_AREA).astype(np.float32)
    model_mask = cv2.resize(mask, (384, 384), interpolation=cv2.INTER_LINEAR)
    anchor = _representative_skin_rgb(rgb, mask)

    # Recovered from GPUImageSkinToneBodyAPIFilter.cpp in the Kumoo arm64
    # binary. Pixels outside the face are neutral, while face pixels encode
    # their colour delta around 127.5 before inference.
    encoded = np.full_like(source, 127.0, dtype=np.float32)
    selected = model_mask >= (2.0 / 255.0)
    encoded[selected] = np.clip(
        (source[selected] - anchor[None, :]) * 0.5 + 127.5,
        0.0,
        255.0,
    )
    tensor = (encoded / 255.0).transpose(2, 0, 1)[None]
    session = skin_session()
    with _session_lock:
        prediction = session.run(None, {session.get_inputs()[0].name: tensor})[0][0]
    prediction = prediction.transpose(1, 2, 0) * 255.0

    # The graph returns the encoded colour delta, not a displayable RGB image.
    # Kumo decodes it around 126 and restores the per-face colour anchor.
    decoded = np.clip(
        (prediction - 126.0) * 2.0 + anchor[None, None, :],
        0.0,
        255.0,
    )
    corrected = cv2.resize(decoded / 255.0, (width, height), interpolation=cv2.INTER_CUBIC)
    return corrected.astype(np.float32)


def _head_matte(rgb_u8: np.ndarray) -> np.ndarray:
    """Run Kumo Het through its original MNN NCHW 512px contract."""

    height, width = rgb_u8.shape[:2]
    tensor = (
        cv2.resize(rgb_u8, (512, 512), interpolation=cv2.INTER_LINEAR)
        .astype(np.float32)
        .transpose(2, 0, 1)[None]
        / 255.0
    )
    interpreter, session = head_matte_runtime()
    with _head_matte_lock:
        input_tensor = next(iter(interpreter.getSessionInputAll(session).values()))
        _mnn_copy_input(input_tensor, tensor, (1, 3, 512, 512))
        interpreter.runSession(session)
        output_tensor = next(iter(interpreter.getSessionOutputAll(session).values()))
        matte = _mnn_copy_output(output_tensor)[0, 0]
    matte = np.nan_to_num(matte, nan=0.0, posinf=1.0, neginf=0.0)
    return cv2.resize(
        np.clip(matte, 0.0, 1.0),
        (width, height),
        interpolation=cv2.INTER_CUBIC,
    ).astype(np.float32)


def _hair_parse_planes(rgb_u8: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return Kumo ChpsJy hair probability and foreground-occluder probability.

    ChpsJy classes are background, hair, face, neck, clothes and unused. The
    explicit non-hair foreground plane is important for hands, glasses, hats
    and clothes crossing the head silhouette: Het alone cannot distinguish
    those objects from hair because it predicts the whole head matte.
    """

    height, width = rgb_u8.shape[:2]
    size = 512
    scale = size / max(height, width)
    resized_width = max(1, round(width * scale))
    resized_height = max(1, round(height * scale))
    resized = cv2.resize(
        rgb_u8,
        (resized_width, resized_height),
        interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR,
    )
    top = (size - resized_height) // 2
    left = (size - resized_width) // 2
    square = cv2.copyMakeBorder(
        resized,
        top,
        size - resized_height - top,
        left,
        size - resized_width - left,
        cv2.BORDER_REPLICATE,
    )
    # ChpsJy follows Kumo's human/hair parsing contract: RGB float in [0, 1].
    # Feeding the parser [-1, 1] suppresses the soft lower-lock probabilities
    # and is the reason dark tips survived after the rest of the hair changed.
    tensor = (square.astype(np.float32) / 255.0).transpose(2, 0, 1)[None]

    interpreter, session = human_parse_runtime()
    with _human_parse_lock:
        input_tensor = next(iter(interpreter.getSessionInputAll(session).values()))
        _mnn_copy_input(input_tensor, tensor, (1, 3, size, size))
        interpreter.runSession(session)
        output_tensor = next(iter(interpreter.getSessionOutputAll(session).values()))
        logits = _mnn_copy_output(output_tensor)[0]

    logits = np.nan_to_num(logits, nan=-20.0, posinf=20.0, neginf=-20.0)
    exponent = np.exp(logits - np.max(logits, axis=0, keepdims=True))
    probabilities = exponent / np.maximum(
        np.sum(exponent, axis=0, keepdims=True),
        1e-8,
    )
    if probabilities.shape[0] < 5:
        raise RuntimeError("ChpsJy không trả đủ 6 lớp parsing Kumo.")

    crop = probabilities[:, top : top + resized_height, left : left + resized_width]
    hair = cv2.resize(crop[1], (width, height), interpolation=cv2.INTER_LINEAR)
    # Face, neck and clothes cover skin, hands, glasses/props attached to the
    # face and garments. A real foreground occluder overrides soft hair nearby.
    occluder = cv2.resize(
        np.max(crop[2:5], axis=0),
        (width, height),
        interpolation=cv2.INTER_LINEAR,
    )
    return (
        np.clip(hair, 0.0, 1.0).astype(np.float32),
        np.clip(occluder, 0.0, 1.0).astype(np.float32),
    )


def _skin_occluder_plane(
    rgb_u8: np.ndarray,
    skin_reference: np.ndarray,
    face_source: np.ndarray,
    head_candidate: np.ndarray,
    hair_probability: np.ndarray,
) -> np.ndarray:
    """Protect a hand crossing the hair using the portrait's real skin colour.

    ChpsJy has no dedicated hand class. Kumo's compositing contract therefore
    needs a foreground skin operator in addition to its semantic classes. The
    colour model is learned per image from PhotoFaceContour/Lp skin pixels and
    is only accepted inside the Het head candidate near a detected face. This
    prevents a generic skin heuristic from erasing similarly coloured hair.
    """

    height, width = rgb_u8.shape[:2]
    reference = np.clip(skin_reference, 0.0, 1.0) > 0.58
    if int(np.count_nonzero(reference)) < 96:
        return np.zeros((height, width), dtype=np.float32)

    lab = cv2.cvtColor(rgb_u8, cv2.COLOR_RGB2LAB).astype(np.float32)
    ycrcb = cv2.cvtColor(rgb_u8, cv2.COLOR_RGB2YCrCb).astype(np.float32)
    samples = lab[reference]
    center = np.median(samples, axis=0)
    mad = np.median(np.abs(samples - center), axis=0) * 1.4826
    # Illumination may differ between face and hand, so L is intentionally
    # broader than the two chroma axes.
    scale = np.maximum(mad, np.array([20.0, 7.0, 8.0], dtype=np.float32))
    normalized = (lab - center) / scale
    distance = np.sqrt(
        normalized[..., 0] ** 2 * 0.38
        + normalized[..., 1] ** 2
        + normalized[..., 2] ** 2
    )
    likeness = np.clip((3.15 - distance) / 1.15, 0.0, 1.0)

    luminance, red_chroma, blue_chroma = (
        ycrcb[..., 0],
        ycrcb[..., 1],
        ycrcb[..., 2],
    )
    generic_skin = (
        (luminance > 38.0)
        & (red_chroma > 122.0)
        & (red_chroma < 184.0)
        & (blue_chroma > 72.0)
        & (blue_chroma < 142.0)
    )
    # Hair presets themselves are red/brown and can share face chroma, but a
    # raised hand in this portrait is still close to the face's lightness.
    # This per-image luminance band prevents a red or warm hair lock from being
    # mistaken for skin on a later preview run.
    skin_luminance_band = (
        (lab[..., 0] >= center[0] - 38.0)
        & (lab[..., 0] <= center[0] + 46.0)
    )
    # Kumo's hair parser is the first authority here. Exclude pixels already
    # recognised as hair *before* morphology/component selection; doing this
    # afterwards lets warm brown hair join a nearby hand component and punches
    # dark holes into the final dye mask.
    non_hair_gate = np.clip((0.50 - hair_probability) / 0.20, 0.0, 1.0)
    raw = (
        likeness
        * generic_skin.astype(np.float32)
        * skin_luminance_band.astype(np.float32)
        * (head_candidate > 0.035).astype(np.float32)
        * non_hair_gate
    )

    # Join fingers and fingernails before component selection. Only components
    # close to the known face are valid foreground skin occluders; isolated
    # warm highlights in the hair are rejected.
    join_radius = max(2, int(round(min(width, height) * 0.008)))
    joined = cv2.morphologyEx(
        (raw > 0.28).astype(np.uint8),
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (join_radius * 2 + 1, join_radius * 2 + 1),
        ),
    )
    near_radius = max(8, int(round(min(width, height) * 0.115)))
    # A distance transform is linear in the number of pixels.  The equivalent
    # giant elliptical dilation becomes disproportionately expensive on large
    # uploads while producing the same "near the face" gate.
    distance_from_face = cv2.distanceTransform(
        (face_source <= 0.16).astype(np.uint8),
        cv2.DIST_L2,
        5,
    )
    near_face = distance_from_face <= float(near_radius)
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(
        joined,
        connectivity=8,
    )
    minimum_pixels = max(8, int(round(width * height * 0.000015)))
    nearby_labels = np.unique(labels[near_face])
    valid_labels = nearby_labels[
        (nearby_labels > 0)
        & (nearby_labels < count)
        & (stats[nearby_labels, cv2.CC_STAT_AREA] >= minimum_pixels)
    ]
    selected = np.isin(labels, valid_labels).astype(np.uint8)

    edge_radius = max(2, int(round(min(width, height) * 0.006)))
    selected = cv2.dilate(
        selected,
        cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (edge_radius * 2 + 1, edge_radius * 2 + 1),
        ),
    ).astype(np.float32)
    selected = cv2.GaussianBlur(
        selected,
        (0, 0),
        sigmaX=max(0.8, edge_radius / 2.0),
    )
    # Closing/dilation is allowed to join the fingers, but it must not spread
    # the skin component back across neighbouring pixels which ChpsJy already
    # classified as hair. Reapply the untouched semantic plane after all
    # morphology so this operator removes the hand itself, not a halo of real
    # hair around it. The dedicated ear plane below still protects a brightly
    # lit ear if ChpsJy happens to mislabel that anatomical region as hair.
    hair_protection = np.clip(
        (np.asarray(hair_probability, dtype=np.float32) - 0.50) / 0.18,
        0.0,
        1.0,
    )
    selected *= 1.0 - hair_protection
    return np.clip(selected, 0.0, 1.0).astype(np.float32)


def _ear_skin_exclusion_plane(
    rgb_u8: np.ndarray,
    skin_reference: np.ndarray,
    landmark_sets: list[np.ndarray],
    hair_probability: np.ndarray,
) -> np.ndarray:
    """Protect visible ears even when the hair parser labels them as hair."""

    height, width = rgb_u8.shape[:2]
    reference = np.clip(skin_reference, 0.0, 1.0) > 0.58
    if int(np.count_nonzero(reference)) < 96 or not landmark_sets:
        return np.zeros((height, width), dtype=np.float32)

    lab = cv2.cvtColor(rgb_u8, cv2.COLOR_RGB2LAB).astype(np.float32)
    ycrcb = cv2.cvtColor(rgb_u8, cv2.COLOR_RGB2YCrCb).astype(np.float32)
    samples = lab[reference]
    center = np.median(samples, axis=0)
    mad = np.median(np.abs(samples - center), axis=0) * 1.4826
    scale = np.maximum(mad, np.array([20.0, 7.0, 8.0], dtype=np.float32))
    normalized = (lab - center) / scale
    distance = np.sqrt(
        normalized[..., 0] ** 2 * 0.38
        + normalized[..., 1] ** 2
        + normalized[..., 2] ** 2
    )
    chroma_distance = np.sqrt(
        normalized[..., 1] ** 2 + normalized[..., 2] ** 2
    )
    skin_chroma = (
        (ycrcb[..., 1] > 122.0)
        & (ycrcb[..., 1] < 184.0)
        & (ycrcb[..., 2] > 72.0)
        & (ycrcb[..., 2] < 142.0)
    )
    generic_skin = (ycrcb[..., 0] > 38.0) & skin_chroma
    skin_luminance_band = (
        (lab[..., 0] >= center[0] - 42.0)
        & (lab[..., 0] <= center[0] + 48.0)
    )

    # Lp106 does not outline the ear itself, but its lateral face bounds give
    # a stable, narrow anatomical search area. Restricting the colour test to
    # these two ellipses prevents similarly coloured hair elsewhere from being
    # removed while allowing skin evidence to override a false ChpsJy hair
    # label on the visible pinna.
    ear_search = np.zeros((height, width), dtype=np.uint8)
    for points in landmark_sets:
        points = np.asarray(points, dtype=np.float32)
        if points.ndim != 2 or points.shape[0] < 3 or points.shape[1] != 2:
            continue
        x_min, y_min = np.min(points, axis=0)
        x_max, y_max = np.max(points, axis=0)
        face_width = max(1.0, float(x_max - x_min))
        face_height = max(1.0, float(y_max - y_min))
        center_y = float(y_min) + face_height * 0.34
        radius_x = max(4, int(round(face_width * 0.105)))
        radius_y = max(6, int(round(face_height * 0.24)))
        for center_x in (
            float(x_min) - face_width * 0.015,
            float(x_max) + face_width * 0.015,
        ):
            cv2.ellipse(
                ear_search,
                (int(round(center_x)), int(round(center_y))),
                (radius_x, radius_y),
                0,
                0,
                360,
                1,
                -1,
            )

    normal_skin = generic_skin & skin_luminance_band & (distance < 2.65)
    # The helix and concha are often much darker than the face reference. They
    # still retain skin chroma, and ChpsJy normally marks them non-hair. This
    # shadow branch recovers those pixels without accepting dark brown hair:
    # a high hair probability vetoes it, while the normal branch above can
    # still protect a brightly lit ear that ChpsJy mislabeled as hair.
    shadow_skin = (
        (ycrcb[..., 0] > 10.0)
        & skin_chroma
        & (lab[..., 0] >= center[0] - 145.0)
        & (lab[..., 0] <= center[0] + 48.0)
        & (chroma_distance < 2.35)
        & (np.asarray(hair_probability, dtype=np.float32) < 0.42)
    )
    selected = ((ear_search > 0) & (normal_skin | shadow_skin)).astype(np.uint8)
    if not np.any(selected):
        return np.zeros((height, width), dtype=np.float32)

    close_radius = max(1, int(round(min(width, height) * 0.003)))
    selected = cv2.morphologyEx(
        selected,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (close_radius * 2 + 1, close_radius * 2 + 1),
        ),
    )
    # The dark concha can have almost no recoverable skin colour. Once its
    # surrounding helix is confirmed, fill only enclosed holes in that skin
    # component so the ear canal cannot survive as a tiny island of hair.
    padded = cv2.copyMakeBorder(
        selected,
        1,
        1,
        1,
        1,
        cv2.BORDER_CONSTANT,
        value=0,
    )
    outside = padded.copy()
    cv2.floodFill(outside, None, (0, 0), 1)
    enclosed = (outside[1:-1, 1:-1] == 0).astype(np.uint8)
    selected = np.maximum(selected, enclosed)
    edge_radius = max(1, int(round(min(width, height) * 0.002)))
    selected = cv2.dilate(
        selected,
        cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (edge_radius * 2 + 1, edge_radius * 2 + 1),
        ),
    ).astype(np.float32)
    selected = cv2.GaussianBlur(
        selected,
        (0, 0),
        sigmaX=max(0.8, edge_radius / 2.0),
    )
    return np.clip(selected, 0.0, 1.0).astype(np.float32)


def _hair_mask(
    rgb_u8: np.ndarray,
    skin_mask: np.ndarray,
    landmark_sets: list[np.ndarray],
    active_flags: list[bool] | None = None,
) -> np.ndarray:
    """Build a hair-only matte from Kumo's hair parser and HairSeamer."""

    height, width = rgb_u8.shape[:2]
    # Kumo's neural stages themselves work at 512px / 513x385.  Running the
    # following morphology and connected-component operations on a 4K upload
    # adds seconds without exposing more information to those models.  Build a
    # generous 1280px working matte once, then upsample only the soft alpha to
    # the original image for the final full-resolution material composite.
    max_working_edge = 1280
    if max(height, width) > max_working_edge:
        scale = max_working_edge / float(max(height, width))
        working_width = max(1, int(round(width * scale)))
        working_height = max(1, int(round(height * scale)))
        working_rgb = cv2.resize(
            rgb_u8,
            (working_width, working_height),
            interpolation=cv2.INTER_AREA,
        )
        working_skin = cv2.resize(
            np.asarray(skin_mask, dtype=np.float32),
            (working_width, working_height),
            interpolation=cv2.INTER_AREA,
        )
        landmark_scale = np.array(
            [working_width / float(width), working_height / float(height)],
            dtype=np.float32,
        )
        working_landmarks = [
            np.asarray(points, dtype=np.float32) * landmark_scale
            for points in landmark_sets
        ]
        working_mask = _hair_mask(
            working_rgb,
            working_skin,
            working_landmarks,
            active_flags=active_flags,
        )
        return np.clip(
            cv2.resize(
                working_mask,
                (width, height),
                interpolation=cv2.INTER_CUBIC,
            ),
            0.0,
            1.0,
        ).astype(np.float32)

    head = _head_matte(rgb_u8)
    parse_hair, _parse_occluder = _hair_parse_planes(rgb_u8)
    radius = max(3, int(round(min(width, height) * 0.007)))
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (radius * 2 + 1, radius * 2 + 1),
    )
    face_features = np.zeros((height, width), dtype=np.uint8)
    for points in landmark_sets:
        cv2.fillConvexPoly(
            face_features,
            cv2.convexHull(points.astype(np.int32)),
            255,
        )
    face_source = np.maximum(
        (np.clip(skin_mask, 0.0, 1.0) * 255.0).astype(np.uint8),
        face_features,
    )
    raw_face_exclusion = cv2.dilate(
        face_source,
        kernel,
    ).astype(np.float32) / 255.0
    # Kumo exposes PhotoHair/HairSegment separately from PhotoHead/Het.  The
    # dedicated hair probability is therefore the silhouette authority; Het
    # must not clip parser-confirmed lower locks merely because they extend
    # beyond the whole-head matte.
    hair_gate = np.clip((parse_hair - 0.12) / 0.48, 0.0, 1.0)
    # Fill internal parse holes caused by shine or a previously coloured lock;
    # the occluder plane is applied afterwards, so this cannot paint back over
    # a detected hand/glove/garment.
    close_radius = max(2, int(round(min(width, height) * 0.020)))
    closed_hair = cv2.morphologyEx(
        (hair_gate > 0.35).astype(np.uint8),
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (close_radius * 2 + 1, close_radius * 2 + 1),
        ),
    ).astype(np.float32)
    closed_hair = cv2.GaussianBlur(
        closed_hair,
        (0, 0),
        sigmaX=max(0.8, close_radius / 3.0),
    )
    hair_gate = np.maximum(hair_gate, closed_hair)
    # The landmark hull includes the forehead, so subtracting it verbatim cuts
    # away real fringe/hairline pixels before HairSeamer can refine them.  The
    # original Kumo stages already expose a dedicated ChpsJy hair plane: let a
    # high-confidence hair classification override only that overlapping part
    # of the face exclusion.  Keep this authority on the raw parser plane (not
    # the morphologically closed gate) so a filled parse hole can never open a
    # route into the middle of the face.
    parser_hair_authority = np.clip((parse_hair - 0.42) / 0.28, 0.0, 1.0)
    parser_hair_authority = cv2.GaussianBlur(
        parser_hair_authority,
        (0, 0),
        sigmaX=max(0.55, min(width, height) / 1600.0),
    )
    face_exclusion = np.clip(
        raw_face_exclusion * (1.0 - parser_hair_authority),
        0.0,
        1.0,
    )
    hair_candidate = np.clip(parse_hair * (1.0 - face_exclusion), 0.0, 1.0)
    skin_occluder = _skin_occluder_plane(
        rgb_u8,
        skin_mask,
        face_source.astype(np.float32) / 255.0,
        hair_candidate,
        parse_hair,
    )
    ear_occluder = _ear_skin_exclusion_plane(
        rgb_u8,
        skin_mask,
        landmark_sets,
        parse_hair,
    )
    # ChpsJy has no hand class.  Keep the per-image skin and ear planes as
    # explicit foreground protection instead of treating Het as a hair mask.
    occluder_gate = np.maximum(skin_occluder, ear_occluder)
    # Reconstruct every connected soft-hair component touched by a confident
    # seed. This preserves long locks and translucent tips without admitting a
    # disconnected parser mistake elsewhere in the frame.
    # Native PhotoHair keeps low-confidence tips as translucent alpha, but it
    # does not let very faint parser noise open a whole connected component.
    candidate_binary = (hair_candidate > 0.075).astype(np.uint8)
    # Het is used only as a conservative seed saying which connected parsing
    # component belongs to the photographed head. It is never multiplied into
    # the final silhouette, so a connected tail may extend beyond Het exactly
    # as it does in native Kumo.
    seed_binary = (
        (hair_gate > 0.20)
        & (np.asarray(head, dtype=np.float32) > 0.08)
    ).astype(np.uint8)
    component_count, component_labels = cv2.connectedComponents(
        candidate_binary,
        connectivity=8,
    )
    minimum_seed_pixels = max(4, int(round(width * height * 0.00002)))
    
    seed_counts = np.bincount(
        component_labels[seed_binary > 0].ravel(),
        minlength=component_count,
    )
    supported_labels = seed_counts >= minimum_seed_pixels

    supported_labels[0] = False
    connected_support = supported_labels[component_labels].astype(np.float32)
    if not np.any(connected_support):
        support_radius = max(5, int(round(min(width, height) * 0.080)))
        connected_support = cv2.dilate(
            seed_binary,
            cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (support_radius * 2 + 1, support_radius * 2 + 1),
            ),
        ).astype(np.float32)
    connected_support = cv2.GaussianBlur(
        connected_support,
        (0, 0),
        sigmaX=max(0.8, min(width, height) / 900.0),
    )
    hair_candidate *= connected_support
    parse_gate = np.maximum(
        hair_gate * connected_support,
        hair_candidate,
    )
    coarse = np.clip(
        hair_candidate * parse_gate * (1.0 - occluder_gate),
        0.0,
        1.0,
    )

    model_width, model_height = 513, 385
    model_rgb = cv2.resize(
        rgb_u8,
        (model_width, model_height),
        interpolation=cv2.INTER_AREA,
    ).astype(np.float32)
    model_rgb = model_rgb / 127.5 - 1.0
    model_coarse = cv2.resize(
        coarse,
        (model_width, model_height),
        interpolation=cv2.INTER_LINEAR,
    )
    model_support_gate = cv2.resize(
        np.maximum(parse_gate, coarse),
        (model_width, model_height),
        interpolation=cv2.INTER_LINEAR,
    )
    model_parse_hair = cv2.resize(
        parse_hair,
        (model_width, model_height),
        interpolation=cv2.INTER_LINEAR,
    )
    model_occluder = cv2.resize(
        occluder_gate,
        (model_width, model_height),
        interpolation=cv2.INTER_LINEAR,
    )
    model_head_gate = cv2.resize(
        hair_candidate,
        (model_width, model_height),
        interpolation=cv2.INTER_LINEAR,
    )
    # HairSeamer may restore boundary pixels, but remains bounded by the
    # parser-derived support and the foreground occluder planes.
    model_head_gate = cv2.dilate(
        (model_head_gate * 255.0).astype(np.uint8),
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)),
    ).astype(np.float32) / 255.0
    tensor = np.concatenate(
        (model_rgb.transpose(2, 0, 1), model_coarse[None]),
        axis=0,
    )[None].astype(np.float32)
    session = hair_seamer_session()
    with _session_lock:
        outputs = session.run(None, {session.get_inputs()[0].name: tensor})
    seam = np.clip(outputs[1][0, 0], 0.0, 1.0)

    support = cv2.dilate(
        (model_support_gate * 255.0).astype(np.uint8),
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
    ).astype(np.float32) / 255.0
    tip_confidence = np.clip((model_parse_hair - 0.045) / 0.36, 0.0, 1.0)
    refined = np.maximum(model_coarse, seam * support * tip_confidence)
    refined *= model_head_gate * (1.0 - model_occluder)
    refined = cv2.resize(refined, (width, height), interpolation=cv2.INTER_CUBIC)
    refined *= 1.0 - face_exclusion
    
    if active_flags is not None and len(active_flags) > 0:
        if not any(active_flags):
            return np.zeros((height, width), dtype=np.float32)
        if not all(active_flags) and len(landmark_sets) == len(active_flags):
            face_centers = []
            eye_dists = []
            for points in landmark_sets:
                cx, cy = np.mean(points[:, 0]), np.mean(points[:, 1])
                left_eye = points[33:43].mean(axis=0)
                right_eye = points[87:97].mean(axis=0)
                eye_dist = max(float(np.linalg.norm(left_eye - right_eye)), 10.0)
                face_centers.append((float(cx), float(cy - eye_dist * 0.4)))
                eye_dists.append(eye_dist)

            scale = 0.25
            small_w, small_h = max(1, int(width * scale)), max(1, int(height * scale))
            y_grid, x_grid = np.mgrid[0:small_h, 0:small_w].astype(np.float32)
            x_orig = x_grid / scale
            y_orig = y_grid / scale

            dist_fields = []
            for (cx, cy), ed in zip(face_centers, eye_dists):
                d = np.sqrt((x_orig - cx)**2 + (y_orig - cy)**2) / ed
                dist_fields.append(d)

            dist_stack = np.stack(dist_fields, axis=0)
            closest_idx = np.argmin(dist_stack, axis=0)

            active_lut = np.array(active_flags, dtype=np.float32)
            small_selector = active_lut[closest_idx]
            small_selector = cv2.GaussianBlur(small_selector, (0, 0), sigmaX=max(1.5, small_w / 40.0))

            selector = cv2.resize(small_selector, (width, height), interpolation=cv2.INTER_LINEAR)
            refined *= selector
        
    sigma = max(0.8, min(width, height) / 900.0)
    refined = cv2.GaussianBlur(refined, (0, 0), sigmaX=sigma, sigmaY=sigma)
    return np.clip(
        refined * PHOTO_HAIR_FALLBACK_SCALE,
        0.0,
        1.0,
    ).astype(np.float32)


@lru_cache(maxsize=len(KUMO_HAIR_PRESETS))
def _hair_material_rgb(preset_key: str) -> np.ndarray:
    preset = KUMO_HAIR_PRESETS[preset_key]
    material_path = (
        KUMO_HAIR_CONFIG_DIR
        / str(preset["folder"])
        / str(preset["material"])
    )
    material = np.asarray(Image.open(material_path).convert("RGB"), dtype=np.float32)
    return np.mean(material.reshape(-1, 3), axis=0) / 255.0


def _lum(color: np.ndarray) -> np.ndarray:
    return np.sum(color * np.array([0.30, 0.59, 0.11], dtype=np.float32), axis=-1)


def _clip_color(color: np.ndarray) -> np.ndarray:
    """Exact ClipColor helper recovered from Kumo's embedded blend shader."""

    clipped = color.copy()
    luminance = _lum(clipped)
    minimum = np.min(clipped, axis=-1)
    maximum = np.max(clipped, axis=-1)

    low = minimum < 0.0
    if np.any(low):
        denominator = np.maximum(luminance[low] - minimum[low], 1e-6)
        clipped[low] = luminance[low, None] + (
            (clipped[low] - luminance[low, None])
            * luminance[low, None]
            / denominator[:, None]
        )

    luminance = _lum(clipped)
    maximum = np.max(clipped, axis=-1)
    high = maximum > 1.0
    if np.any(high):
        denominator = np.maximum(maximum[high] - luminance[high], 1e-6)
        clipped[high] = luminance[high, None] + (
            (clipped[high] - luminance[high, None])
            * (1.0 - luminance[high, None])
            / denominator[:, None]
        )
    return np.clip(clipped, 0.0, 1.0)


def _apply_kumo_hair_color(
    rgb: np.ndarray,
    mask: np.ndarray,
    preset_key: str,
    strength: int,
) -> tuple[np.ndarray, float]:
    """Apply Kumo HairColorFilter blendType=3 (SetLum/Color blend mode)."""

    if preset_key == "none" or strength <= 0:
        return rgb, 0.0
    preset = KUMO_HAIR_PRESETS[preset_key]
    # defaultAlpha is Kumo's initial slider position when a material is chosen,
    # not a second multiplier. Once the user sets 45, native Kumo applies 45%
    # directly (subject only to the material's maxAlphaRatio).
    effective_alpha = min(
        strength / 100.0,
        float(preset["max_alpha_ratio"]),
    )
    material = _hair_material_rgb(preset_key)
    active = np.asarray(mask) > 0.002
    if not np.any(active):
        return rgb, effective_alpha
    result = rgb.copy()
    # Work only on pixels touched by the soft matte.  A hair bounding box can
    # still contain millions of background/face pixels on a 4K portrait.
    # Boolean gather keeps the shader math identical while reducing work to
    # the true hair coverage.
    target = rgb[active]
    target_mask = mask[active]
    source_luminance = _lum(target)
    material_luminance = float(_lum(material))
    colored = _clip_color(material[None, None, :] + source_luminance[..., None] - material_luminance)
    alpha = np.clip(target_mask * effective_alpha, 0.0, 1.0)[..., None]
    result[active] = np.clip(
        target * (1.0 - alpha) + colored * alpha,
        0.0,
        1.0,
    )
    return result, effective_alpha


def _resolve_face_profiles(
    faces: list[dict[str, object]],
    profile_overrides: list[str] | None,
) -> list[str]:
    if profile_overrides is None:
        return [str(face["profile"]) for face in faces]
    
    resolved = []
    for i, face in enumerate(faces):
        if i < len(profile_overrides) and profile_overrides[i] in KUMO_GOC_PROFILES:
            resolved.append(profile_overrides[i])
        else:
            resolved.append(str(face["profile"]))
    return resolved


def _preset_profile_number(
    params: dict[str, object],
    key: str,
    profile: str,
    fallback: float = 0.0,
) -> float:
    """Read Kumoo's man/woman/child/oldwoman/oldman parameter arrays."""

    value = params.get(key, fallback)
    if isinstance(value, list):
        index = PRESET_PROFILE_INDEX[profile]
        if index >= len(value):
            return fallback
        value = value[index]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return fallback


PHOTOBOOTH_BASE_PARAMETER_KEYS = (
    "skin_fleck_clean_flag",
    "flaw_clean_alpha",
    "smooth_face_skin_alpha",
    "skin_tone_flag",
    "skin_tone_face_alpha",
    "skin_tone_body_alpha",
    "skin_white_alpha",
)
PORTRAIT_BASE_CACHE_VERSION = 3


def _portrait_base_cache_key(
    payload: bytes,
    skin_fleck_clean_flag: int = DEFAULT_CONTROL_STRENGTH,
    smooth_face_skin_alpha: int = DEFAULT_CONTROL_STRENGTH,
    skin_tone_face_alpha: int = DEFAULT_CONTROL_STRENGTH,
    skin_white_alpha: int = DEFAULT_CONTROL_STRENGTH,
    profile_overrides: list[str] | None = None,
    preset_params: dict[str, object] | None = None,
    preset_strength: int = 100,
    smooth_texture_skin_alpha: int = 0,
    skin_color_lut_preset: str = "none",
    skin_color_lut_alpha: int = 0,
    skin_tone_multiple_alpha: int = 0,
) -> str:
    """Key the expensive Kumo analysis/retouch pass, excluding live materials."""

    if preset_params is None:
        base_contract: dict[str, object] = {
            "mode": "manual",
            "skin_fleck": skin_fleck_clean_flag / 100.0,
            "smooth": smooth_face_skin_alpha / 100.0,
            "smooth_texture": smooth_texture_skin_alpha / 100.0,
            "tone": skin_tone_face_alpha / 100.0,
            "white": skin_white_alpha / 100.0,
            "skin_color_preset": skin_color_lut_preset,
            "skin_color_alpha": skin_color_lut_alpha / 100.0,
            "skin_tone_multiple": skin_tone_multiple_alpha / 100.0,
            "overrides": profile_overrides,
        }
    else:
        # A PhotoBooth preset is a complete Kumo contract. Global colour,
        # material and unresolved metadata never affect the model/base cache.
        base_contract = {
            "mode": "photobooth",
            "skin": {
                key: preset_params.get(key)
                for key in PHOTOBOOTH_BASE_PARAMETER_KEYS
            },
            "preset_strength": preset_strength,
            "overrides": profile_overrides,
        }
    
    digest = hashlib.sha256()
    digest.update(payload)
    digest.update(
        json.dumps(
            {
                "version": PORTRAIT_BASE_CACHE_VERSION,
                "contract": base_contract,
                "overrides": profile_overrides or [],
            },
            sort_keys=True,
        ).encode("utf-8")
    )
    return digest.hexdigest()


def _cache_get(
    cache: OrderedDict[str, object],
    key: str,
) -> object | None:
    with _portrait_cache_lock:
        value = cache.get(key)
        if value is not None:
            cache.move_to_end(key)
        return value


def _cache_put(
    cache: OrderedDict[str, object],
    key: str,
    value: object,
) -> None:
    with _portrait_cache_lock:
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > _PORTRAIT_CACHE_LIMIT:
            cache.popitem(last=False)


def _clear_portrait_cache() -> None:
    with _portrait_cache_lock:
        _portrait_analysis_cache.clear()
        _portrait_base_cache.clear()
        _portrait_hair_mask_cache.clear()


def _portrait_analysis(
    rgb_u8: np.ndarray,
    source_key: str | None = None,
) -> tuple[
    list[dict[str, object]],
    list[tuple[int, int, int, int]],
    list[dict[str, object]],
    list[np.ndarray],
    list[np.ndarray],
    list[np.ndarray],
    np.ndarray,
    float,
]:
    """Analyze one source image independently from its retouch contract."""

    image_key = source_key or hashlib.sha256(rgb_u8.tobytes()).hexdigest()
    height, width = rgb_u8.shape[:2]
    cache_key = f"{image_key}:{width}x{height}"
    cached = _cache_get(_portrait_analysis_cache, cache_key)
    if cached is not None:
        _timing_log.info("Portrait face analysis cache HIT")
        return cached  # type: ignore[return-value]

    detections = _face_detections(rgb_u8)
    boxes = [tuple(int(value) for value in item["box"]) for item in detections]
    faces = analyze_faces(rgb_u8, detections=detections)
    landmark_sets = face_landmark_sets(rgb_u8, detections)
    contours = face_contour_masks(rgb_u8, boxes, landmark_sets)
    masks, landmark_sets = landmark_skin_masks(
        rgb_u8, contours, boxes, landmark_sets
    )
    combined_mask = np.maximum.reduce(masks)
    coverage = float(np.mean(combined_mask > 0.35))
    if coverage < 0.0002 or float(combined_mask.max()) < 0.35:
        raise HTTPException(
            status_code=422,
            detail="Model không tìm thấy khuôn mặt đủ rõ. Hãy dùng ảnh chân dung chính diện hơn.",
        )

    analyzed = (
        detections,
        boxes,
        faces,
        landmark_sets,
        contours,
        masks,
        combined_mask,
        coverage,
    )
    _cache_put(_portrait_analysis_cache, cache_key, analyzed)
    return analyzed


def _prepare_beauty_base(
    rgb_u8: np.ndarray,
    skin_fleck_clean_flag: int = DEFAULT_CONTROL_STRENGTH,
    smooth_face_skin_alpha: int = DEFAULT_CONTROL_STRENGTH,
    smooth_texture_skin_alpha: int = 0,
    skin_tone_face_alpha: int = DEFAULT_CONTROL_STRENGTH,
    skin_white_alpha: int = DEFAULT_CONTROL_STRENGTH,
    profile_overrides: list[str] | None = None,
    preset_params: dict[str, object] | None = None,
    preset_strength: int = 100,
    analysis_cache_key: str | None = None,
    skin_color_lut_preset: str = "none",
    skin_color_lut_alpha: int = 0,
    skin_tone_multiple_alpha: int = 0,
) -> tuple[
    np.ndarray,
    float,
    list[dict[str, object]],
    np.ndarray,
    list[np.ndarray],
]:
    height, width = rgb_u8.shape[:2]
    # All recovered neural contracts are 224..512px.  Kumo feeds them through
    # fixed-size GPU textures; it does not run CPU masks and a 64-cube LUT over
    # every pixel of a 20MP upload.  Reproduce that contract at a generous
    # 1600px working edge, then composite only the face-safe mask back onto the
    # untouched full-resolution source.
    max_working_edge = 1600
    if max(height, width) > max_working_edge:
        scale = max_working_edge / float(max(height, width))
        working_width = max(1, int(round(width * scale)))
        working_height = max(1, int(round(height * scale)))
        working_rgb = cv2.resize(
            rgb_u8,
            (working_width, working_height),
            interpolation=cv2.INTER_AREA,
        )
        (
            working_result,
            _working_coverage,
            effective_profiles,
            working_mask,
            working_landmarks,
        ) = _prepare_beauty_base(
            working_rgb,
            skin_fleck_clean_flag,
            smooth_face_skin_alpha,
            smooth_texture_skin_alpha,
            skin_tone_face_alpha,
            skin_white_alpha,
            profile_overrides,
            preset_params,
            preset_strength,
            analysis_cache_key,
            skin_color_lut_preset=skin_color_lut_preset,
            skin_color_lut_alpha=skin_color_lut_alpha,
            skin_tone_multiple_alpha=skin_tone_multiple_alpha,
        )
        full_mask = cv2.resize(
            working_mask,
            (width, height),
            interpolation=cv2.INTER_CUBIC,
        )
        full_mask = np.clip(full_mask, 0.0, 1.0).astype(np.float32)
        corrected = cv2.resize(
            working_result,
            (width, height),
            interpolation=cv2.INTER_CUBIC,
        )
        working_src = cv2.resize(
            working_rgb.astype(np.float32) / 255.0,
            (width, height),
            interpolation=cv2.INTER_CUBIC,
        )
        original = rgb_u8.astype(np.float32) / 255.0
        detail = original - working_src
        result = np.clip(corrected + detail * 0.4, 0.0, 1.0)
        coordinate_scale = np.array(
            [width / float(working_width), height / float(working_height)],
            dtype=np.float32,
        )
        full_landmarks = [
            np.asarray(points, dtype=np.float32) * coordinate_scale
            for points in working_landmarks
        ]
        for face in effective_profiles:
            box = face.get("box")
            if isinstance(box, list) and len(box) == 4:
                face["box"] = [
                    int(round(box[0] * coordinate_scale[0])),
                    int(round(box[1] * coordinate_scale[1])),
                    int(round(box[2] * coordinate_scale[0])),
                    int(round(box[3] * coordinate_scale[1])),
                ]
        coverage = float(np.mean(full_mask > 0.35))
        return (
            np.clip(result, 0.0, 1.0).astype(np.float32),
            coverage,
            effective_profiles,
            full_mask,
            full_landmarks,
        )

    (
        _detections,
        boxes,
        faces,
        landmark_sets,
        contours,
        masks,
        combined_mask,
        coverage,
    ) = _portrait_analysis(rgb_u8, analysis_cache_key)
    profile_keys = _resolve_face_profiles(faces, profile_overrides)

    if preset_params is None:
        profiles = [KUMO_GOC_PROFILES[key] for key in profile_keys]
        blemish_alphas = [
            skin_fleck_clean_flag / 100.0
            * profile["skin_fleck_clean_flag"] / 100.0
            * profile["flaw_clean_alpha"] / 100.0
            for profile in profiles
        ]
        smooth_alphas = [
            smooth_face_skin_alpha / 100.0
            * profile["smooth_face_skin_alpha"] / 100.0
            for profile in profiles
        ]
        smooth_texture_alphas = [smooth_texture_skin_alpha / 100.0 for _ in profiles]
        tone_alphas = [
            skin_tone_face_alpha / 100.0
            * profile["skin_tone_face_alpha"] / 100.0
            for profile in profiles
        ]
        body_tone_alphas = [0.0 for _ in profiles]
        white_alphas = [
            skin_white_alpha / 100.0
            * profile["skin_white_alpha"] / 100.0
            for profile in profiles
        ]
    else:
        profiles = [
            {
                "skin_fleck_clean_flag": _preset_profile_number(
                    preset_params, "skin_fleck_clean_flag", key
                ),
                "flaw_clean_alpha": _preset_profile_number(
                    preset_params, "flaw_clean_alpha", key, 100.0
                ),
                "smooth_face_skin_alpha": _preset_profile_number(
                    preset_params, "smooth_face_skin_alpha", key
                ),
                "skin_tone_flag": _preset_profile_number(
                    preset_params, "skin_tone_flag", key
                ),
                "skin_tone_face_alpha": _preset_profile_number(
                    preset_params, "skin_tone_face_alpha", key
                ),
                "skin_tone_body_alpha": _preset_profile_number(
                    preset_params, "skin_tone_body_alpha", key
                ),
                "skin_white_alpha": _preset_profile_number(
                    preset_params, "skin_white_alpha", key
                ),
            }
            for key in profile_keys
        ]
        preset_scale = preset_strength / 100.0
        blemish_alphas = [
            preset_scale
            * profile["skin_fleck_clean_flag"] / 100.0
            * profile["flaw_clean_alpha"] / 100.0
            for profile in profiles
        ]
        smooth_alphas = [
            preset_scale * profile["smooth_face_skin_alpha"] / 100.0
            for profile in profiles
        ]
        smooth_texture_alphas = [0.0 for _ in profiles]
        tone_alphas = [
            preset_scale * profile["skin_tone_face_alpha"] / 100.0
            if profile["skin_tone_flag"] > 0 or profile["skin_tone_face_alpha"] > 0
            else 0.0
            for profile in profiles
        ]
        body_tone_alphas = [
            preset_scale * profile["skin_tone_body_alpha"] / 100.0
            for profile in profiles
        ]
        white_alphas = [
            preset_scale * profile["skin_white_alpha"] / 100.0
            for profile in profiles
        ]
    recovered = _apply_coreml_face_models(
        rgb_u8,
        masks,
        contours,
        boxes,
        smooth_alphas,
        blemish_alphas,
        smooth_texture_alphas,
        landmark_sets,
    )
    result = recovered
    effective_profiles: list[dict[str, object]] = []
    for (
        face,
        profile_key,
        mask,
        smooth_alpha,
        blemish_alpha,
        tone_alpha,
        body_tone_alpha,
        white_alpha,
    ) in zip(
        faces,
        profile_keys,
        masks,
        smooth_alphas,
        blemish_alphas,
        tone_alphas,
        body_tone_alphas,
        white_alphas,
    ):
        if tone_alpha > 0:
            model_result = skin_tone_layer(
                np.clip(result * 255.0, 0, 255).astype(np.uint8), mask
            )
            tone_mask = mask[..., None] * tone_alpha
            result = result * (1.0 - tone_mask) + model_result * tone_mask

        if body_tone_alpha > 0:
            balanced = _apply_kumo_body_skin_balance(result)
            body_mask = mask[..., None] * body_tone_alpha
            result = result * (1.0 - body_mask) + balanced * body_mask

        if white_alpha > 0:
            result = _apply_kumo_whitening(result, mask, white_alpha)

        lut_alpha_val = int(skin_color_lut_alpha) if isinstance(skin_color_lut_alpha, (int, float, str)) and str(skin_color_lut_alpha).isdigit() else 0
        if skin_color_lut_preset != "none" and lut_alpha_val > 0:
            skin_lut = _skin_color_lut(skin_color_lut_preset)
            if skin_lut is not None:
                color_lut_res = _apply_16_cube_lut(result, skin_lut)
                lut_mask = mask[..., None] * (float(lut_alpha_val) / 100.0)
                result = np.clip(result * (1.0 - lut_mask) + color_lut_res * lut_mask, 0.0, 1.0)

        group_tone_val = int(skin_tone_multiple_alpha) if isinstance(skin_tone_multiple_alpha, (int, float, str)) and str(skin_tone_multiple_alpha).isdigit() else 0
        if group_tone_val > 0:
            result = _apply_kumo_group_skin_tone(
                result, mask, float(group_tone_val) / 100.0
            )

        effective = dict(face)
        effective.update(
            {
                "profile": profile_key,
                "label": PROFILE_LABELS[profile_key],
                "overridden": profile_key != face["profile"],
                "effective": {
                    "blemish": round(blemish_alpha * 100.0, 2),
                    "smooth": round(smooth_alpha * 100.0, 2),
                    "skin_tone": round(tone_alpha * 100.0, 2),
                    "body_tone": round(body_tone_alpha * 100.0, 2),
                    "skin_white": round(white_alpha * 100.0, 2),
                },
            }
        )
        effective_profiles.append(effective)

    output_mask = combined_mask
    if blemish_alphas:
        blemish_mask = np.maximum.reduce(
            [
                contour * float(alpha)
                for contour, alpha in zip(contours, blemish_alphas)
            ]
        )
        output_mask = np.maximum(output_mask, blemish_mask)

    return result, coverage, effective_profiles, output_mask, landmark_sets


def _face_operator_anchors(
    points: np.ndarray,
    box: tuple[int, int, int, int],
    region: str,
    operator: str,
) -> list[tuple[tuple[float, float], tuple[float, float], tuple[float, float]]]:
    """Map Kumo's region keys to Lp106 anchors, radii and lift vectors."""

    x, y, width, height = [float(value) for value in box]
    left_eye = points[LANDMARK_GROUPS["left_eye"]].mean(axis=0)
    right_eye = points[LANDMARK_GROUPS["right_eye"]].mean(axis=0)
    left_brow = points[LANDMARK_GROUPS["left_brow"]].mean(axis=0)
    right_brow = points[LANDMARK_GROUPS["right_brow"]].mean(axis=0)
    mouth = points[LANDMARK_GROUPS["mouth_outer"]]
    mouth_center = mouth.mean(axis=0)
    nose = points[LANDMARK_GROUPS["nose"]]
    eye_center = (left_eye + right_eye) * 0.5
    face_center_x = x + width * 0.5

    def anchor(
        center: np.ndarray | tuple[float, float],
        radius_x: float,
        radius_y: float,
        move_x: float = 0.0,
        move_y: float = 0.0,
    ) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
        return (
            (float(center[0]), float(center[1])),
            (max(width * radius_x, 8.0), max(height * radius_y, 8.0)),
            (width * move_x, height * move_y),
        )

    if operator == "lift":
        if region == "forehead":
            brow_y = min(float(left_brow[1]), float(right_brow[1]))
            return [anchor((face_center_x, brow_y - height * 0.12), 0.42, 0.24, 0.0, -0.026)]
        if region == "eyes":
            return [
                anchor(left_eye, 0.24, 0.15, -0.004, -0.018),
                anchor(right_eye, 0.24, 0.15, 0.004, -0.018),
            ]
        if region == "midface":
            center = eye_center * 0.48 + mouth_center * 0.52
            return [anchor(center, 0.46, 0.27, 0.0, -0.025)]
        if region == "mouth":
            return [anchor(mouth_center, 0.38, 0.19, 0.0, -0.018)]
        return []

    if region == "forehead":
        brow_y = min(float(left_brow[1]), float(right_brow[1]))
        return [anchor((face_center_x, brow_y - height * 0.13), 0.34, 0.20)]
    if region == "tear_trough":
        return [
            anchor(left_eye + (0.0, height * 0.065), 0.18, 0.10),
            anchor(right_eye + (0.0, height * 0.065), 0.18, 0.10),
        ]
    if region == "apple_cheek":
        return [
            anchor(left_eye + (-width * 0.035, height * 0.18), 0.22, 0.16),
            anchor(right_eye + (width * 0.035, height * 0.18), 0.22, 0.16),
        ]
    if region == "cheek":
        return [
            anchor(left_eye + (-width * 0.11, height * 0.25), 0.25, 0.22),
            anchor(right_eye + (width * 0.11, height * 0.25), 0.25, 0.22),
        ]
    if region == "nose_base":
        center = nose[np.argmax(nose[:, 1])]
        return [anchor(center, 0.19, 0.13)]
    if region == "aegyosal":
        return [
            anchor(left_eye + (0.0, height * 0.038), 0.16, 0.072),
            anchor(right_eye + (0.0, height * 0.038), 0.16, 0.072),
        ]
    if region == "eye_socket":
        return [anchor(left_eye, 0.20, 0.13), anchor(right_eye, 0.20, 0.13)]
    if region == "brow_arch":
        return [anchor(left_brow, 0.20, 0.12), anchor(right_brow, 0.20, 0.12)]
    if region == "chin":
        contour = points[LANDMARK_GROUPS["contour"]]
        center = contour[np.argmax(contour[:, 1])]
        return [anchor(center, 0.25, 0.16)]
    if region == "mouth_corner":
        return [
            anchor(mouth[np.argmin(mouth[:, 0])], 0.16, 0.11),
            anchor(mouth[np.argmax(mouth[:, 0])], 0.16, 0.11),
        ]
    return []


def _localized_face_warp(
    rgb: np.ndarray,
    face_mask: np.ndarray,
    center: tuple[float, float],
    radii: tuple[float, float],
    move: tuple[float, float],
    strength: float,
    operator: str,
) -> None:
    """Apply one feathered Kumo-style regional warp in-place."""

    image_height, image_width = rgb.shape[:2]
    center_x, center_y = center
    radius_x, radius_y = radii
    x1 = max(0, int(np.floor(center_x - radius_x * 1.15)))
    y1 = max(0, int(np.floor(center_y - radius_y * 1.15)))
    x2 = min(image_width, int(np.ceil(center_x + radius_x * 1.15)) + 1)
    y2 = min(image_height, int(np.ceil(center_y + radius_y * 1.15)) + 1)
    if x2 - x1 < 4 or y2 - y1 < 4:
        return

    local_x, local_y = np.meshgrid(
        np.arange(x2 - x1, dtype=np.float32),
        np.arange(y2 - y1, dtype=np.float32),
    )
    local_center_x = center_x - x1
    local_center_y = center_y - y1
    norm_x = (local_x - local_center_x) / radius_x
    norm_y = (local_y - local_center_y) / radius_y
    distance = norm_x * norm_x + norm_y * norm_y
    falloff = np.square(np.clip(1.0 - distance, 0.0, 1.0)).astype(np.float32)
    gate = np.clip(face_mask[y1:y2, x1:x2], 0.0, 1.0)
    alpha = np.clip(falloff * gate, 0.0, 1.0)
    if float(alpha.max()) < 0.01:
        return

    if operator == "lift":
        map_x = local_x - float(move[0]) * strength * falloff
        map_y = local_y - float(move[1]) * strength * falloff
    else:
        # Inverse radial map: pulling source coordinates toward the anchor
        # expands the target area while retaining the original skin texture.
        expansion = 0.075 * strength * falloff
        map_x = local_center_x + (local_x - local_center_x) * (1.0 - expansion)
        map_y = local_center_y + (local_y - local_center_y) * (1.0 - expansion)

    source = rgb[y1:y2, x1:x2].copy()
    warped = cv2.remap(
        source,
        map_x,
        map_y,
        interpolation=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REFLECT_101,
    )
    if operator == "lift":
        # Kumo "Làm mịn & Nâng cơ" (fore_head_smooth, periorbital_smooth, malars_smooth, perioral_smooth)
        # combines geometric lifting with gentle localized wrinkle smoothing.
        smooth_local = cv2.GaussianBlur(warped, (0, 0), sigmaX=1.6, sigmaY=1.6)
        smooth_gain = np.clip(0.35 * strength * falloff, 0.0, 0.50)[..., None]
        warped = warped * (1.0 - smooth_gain) + smooth_local * smooth_gain
    elif operator == "fill":
        # The recovered filler operator combines geometry with a restrained
        # soft-light pass. Keep this luminance-only so hue and skin texture do
        # not change when a user selects a facial volume region.
        light = (0.018 * strength * falloff)[..., None]
        warped = np.clip(warped + light * (1.0 - warped), 0.0, 1.0)
    rgb[y1:y2, x1:x2] = source * (1.0 - alpha[..., None]) + warped * alpha[..., None]


def _apply_kumo_face_volume(
    rgb: np.ndarray,
    face_mask: np.ndarray,
    faces: list[dict[str, object]],
    landmark_sets: list[np.ndarray],
    lift_region: str,
    lift_strength: int,
    fill_region: str,
    fill_strength: int,
) -> np.ndarray:
    """Run Kumo's lift/fullness region contract against every detected face."""

    if (lift_region == "none" or lift_strength <= 0) and (
        fill_region == "none" or fill_strength <= 0
    ):
        return rgb
    result = rgb.copy()
    for face, points in zip(faces, landmark_sets):
        raw_box = face.get("box")
        if not isinstance(raw_box, list) or len(raw_box) != 4:
            continue
        box = tuple(int(value) for value in raw_box)
        if lift_region != "none" and lift_strength > 0:
            for center, radii, move in _face_operator_anchors(points, box, lift_region, "lift"):
                _localized_face_warp(
                    result,
                    face_mask,
                    center,
                    radii,
                    move,
                    lift_strength / 100.0,
                    "lift",
                )
        if fill_region != "none" and fill_strength > 0:
            for center, radii, move in _face_operator_anchors(points, box, fill_region, "fill"):
                _localized_face_warp(
                    result,
                    face_mask,
                    center,
                    radii,
                    move,
                    fill_strength / 100.0,
                    "fill",
                )
    return np.clip(result, 0.0, 1.0)


@lru_cache(maxsize=64)
def _load_kumo_filter_package(filter_id: str) -> tuple[np.ndarray | None, np.ndarray | None, float]:
    """Load Kumoo filter LUTs following the plist specification.

    Returns (scene_lut, skin_lut, default_alpha).

    Pipeline order per ``configuration_filter.plist``:
    - **Type 1017** (scene/background LUT): applied everywhere; when hasSkinMask=1
      it is only applied on non-skin areas.
    - **Type 1018** (skin LUT): dedicated skin LUT applied only on skin mask.
    - **DefaultAlpha**: overall filter strength from plist (0.0–1.0).

    For simple filters (no package / single-step), uses the pre-baked
    ``lut/{filter_id}.png`` tile (same asset as shader_506.glsl).
    """
    scene_lut = None
    skin_lut = None
    default_alpha = 1.0

    # ── 1. Try package plist (authoritative source for dual-LUT filters) ──
    pkg_dir = ROOT / "assets" / "filters" / "packages" / filter_id / "filter"
    if pkg_dir.is_dir():
        plist_file = pkg_dir / "configuration_filter.plist"
        if plist_file.is_file():
            try:
                import plistlib
                with open(plist_file, "rb") as f:
                    pl = plistlib.load(f)
                for part in pl.get("FilterPart", []):
                    try:
                        default_alpha = float(part.get("DefaultAlpha", "1"))
                    except (ValueError, TypeError):
                        default_alpha = 1.0
                    for step in part.get("Step", []):
                        stype = str(step.get("Type", ""))
                        spath = step.get("Path")
                        if spath:
                            candidates = [
                                pkg_dir / "res" / spath,
                                pkg_dir / "res" / f"{spath}.png",
                                pkg_dir / "res" / f"{spath}.jpg",
                            ]
                            lut_p = next((p for p in candidates if p.is_file()), None)
                            if lut_p is not None:
                                img = cv2.imread(str(lut_p))
                                if img is not None:
                                    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
                                    if stype in ("1017", "1007") and scene_lut is None:
                                        scene_lut = rgb
                                    elif stype in ("1018", "1008") and skin_lut is None:
                                        skin_lut = rgb
            except Exception:
                pass

    # ── 2. Fallback: pre-baked tile from lut/ directory ──────────────────
    if scene_lut is None:
        lut_file = ROOT / "assets" / "filters" / "lut" / f"{filter_id}.png"
        if lut_file.is_file():
            img = cv2.imread(str(lut_file))
            if img is not None:
                scene_lut = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0

    return scene_lut, skin_lut, default_alpha


def _apply_kumo_preset_tone_adjustments(rgb: np.ndarray, params: dict | None, strength: float) -> np.ndarray:
    """Apply Kumoo's global preset color parameters (temperature, contrast, highlight, shadow, exposure, HSL skin glow)."""
    if not params or strength <= 0:
        return rgb

    import math
    scale = float(strength) / 100.0
    result = rgb.copy()

    # 1. Exposure
    exposure = float(params.get("exposure", 0) or 0) * scale
    if exposure != 0:
        exp_gain = math.pow(2.0, exposure / 100.0)
        result = result * exp_gain

    # 2. Temperature (warm / cool shift)
    temperature = float(params.get("temperature", 0) or params.get("hue", 0) or 0) * scale
    if temperature != 0:
        temp_shift = temperature / 100.0 * 0.08
        result[..., 0] = result[..., 0] * (1.0 + temp_shift)
        result[..., 2] = result[..., 2] * (1.0 - temp_shift)

    # 3. Contrast
    contrast = float(params.get("contrast", 0) or params.get("constrast", 0) or 0) * scale
    if contrast != 0:
        c_factor = 1.0 + contrast / 100.0
        result = (result - 0.5) * c_factor + 0.5

    # 4. Highlight & Shadow
    highlight = float(params.get("highlight", 0) or 0) * scale
    shadow = float(params.get("shadow", 0) or 0) * scale
    if highlight != 0 or shadow != 0:
        lum = result[..., 0] * 0.299 + result[..., 1] * 0.587 + result[..., 2] * 0.114
        lum = np.clip(lum, 0.0, 1.0)
        if highlight != 0:
            hi_weight = np.clip((lum - 0.5) * 2.0, 0.0, 1.0)[..., None]
            result = result + (1.0 - result) * (highlight / 100.0 * 0.3) * hi_weight
        if shadow != 0:
            sh_weight = np.clip((0.5 - lum) * 2.0, 0.0, 1.0)[..., None]
            result = result + (1.0 - result) * (shadow / 100.0 * 0.3) * sh_weight

    # 5. HSL Skin Luminance / Saturation (Orange & Red) and Overall Whiteness
    luma_orange = float(params.get("hsl_luma_orange", 0) or 0) * scale
    sat_orange = float(params.get("hsl_sat_orange", 0) or 0) * scale
    whiteness = float(params.get("whiteness", 0) or 0) * scale
    if luma_orange != 0 or sat_orange != 0 or whiteness != 0:
        hsv = cv2.cvtColor(np.clip(result * 255.0, 0, 255).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
        h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
        # Skin hue range in OpenCV (H: 5..25)
        orange_w = np.clip(1.0 - np.abs(h - 15.0) / 12.0, 0.0, 1.0) * (s / 255.0)

        if luma_orange != 0:
            v = np.clip(v + (luma_orange / 100.0 * 45.0) * orange_w, 0.0, 255.0)
        if sat_orange != 0:
            s = np.clip(s + (sat_orange / 100.0 * 50.0) * orange_w, 0.0, 255.0)
        if whiteness != 0:
            v = np.clip(v + (whiteness / 100.0 * 20.0), 0.0, 255.0)

        hsv_adj = np.stack([h, s, v], axis=-1)
        result = cv2.cvtColor(hsv_adj.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32) / 255.0

    return np.clip(result, 0.0, 1.0)


def _finish_beauty(
    prepared: tuple[
        np.ndarray,
        float,
        list[dict[str, object]],
        np.ndarray,
        list[np.ndarray],
    ],
    lipstick_alpha: int,
    lipstick_preset: str,
    hair_color_strength: int,
    hair_color_preset: str,
    hair_mask: np.ndarray | None = None,
    face_lift_region: str = "none",
    face_lift_strength: int = 50,
    face_fill_region: str = "none",
    face_fill_strength: int = 50,
    filter_id: str = "none",
    filter_strength: int = 100,
    preset_params: dict | None = None,
    photo_preset_strength: int = 100,
) -> tuple[np.ndarray, float, list[dict[str, object]], float, float]:
    result, coverage, effective_profiles, combined_mask, landmark_sets = prepared
    profiles = [KUMO_GOC_PROFILES[str(face["profile"])] for face in effective_profiles]

    result = _apply_kumo_face_volume(
        result,
        combined_mask,
        effective_profiles,
        landmark_sets,
        face_lift_region,
        face_lift_strength,
        face_fill_region,
        face_fill_strength,
    )

    hair_coverage = 0.0
    hair_effective_alpha = 0.0
    if hair_color_preset != "none" and hair_color_strength > 0:
        if hair_mask is None:
            active_flags = [str(face["profile"]) in ("woman", "oldwoman") for face in effective_profiles]
            hair_mask = _hair_mask(
                np.clip(result * 255.0, 0, 255).astype(np.uint8),
                combined_mask,
                landmark_sets,
                active_flags=active_flags,
            )
        hair_coverage = float(np.mean(hair_mask > 0.15))
        result, hair_effective_alpha = _apply_kumo_hair_color(
            result,
            hair_mask,
            hair_color_preset,
            hair_color_strength,
        )

    lipstick_alphas = [
        lipstick_alpha / 100.0 * profile["lipstick_alpha"] / 100.0
        for profile in profiles
    ]
    result = _apply_kumo_lipstick(
        result,
        landmark_sets,
        lipstick_alphas,
        lipstick_preset,
    )

    # Apply preset global tone adjustments (temperature, contrast, highlight, shadow, exposure)
    if preset_params and photo_preset_strength > 0:
        result = _apply_kumo_preset_tone_adjustments(result, preset_params, photo_preset_strength)

    print(f"Filter check: filter_id='{filter_id}' filter_strength={filter_strength}", flush=True)
    if filter_id != "none" and filter_strength > 0:
        scene_lut, skin_lut, plist_alpha = _load_kumo_filter_package(filter_id)
        blend = float(np.clip(filter_strength / 100.0 * plist_alpha, 0.0, 1.0))
        
        if scene_lut is not None and skin_lut is not None:
            # Dual-LUT: scene_lut for scene + skin_lut for skin mask
            filtered_scene = _apply_64_cube_lut(result, scene_lut)
            filtered_skin = _apply_64_cube_lut(result, skin_lut)
            s_mask = np.clip(combined_mask[..., None], 0.0, 1.0)
            filtered = filtered_scene * (1.0 - s_mask) + filtered_skin * s_mask
            result = result * (1.0 - blend) + filtered * blend
            print(f"Filter {filter_id}: DUAL-LUT blend={blend:.2f} plistAlpha={plist_alpha:.2f}", flush=True)
        elif scene_lut is not None:
            filtered = _apply_64_cube_lut(result, scene_lut)
            result = result * (1.0 - blend) + filtered * blend
            print(f"Filter {filter_id}: SCENE-LUT blend={blend:.2f} plistAlpha={plist_alpha:.2f}", flush=True)
        elif skin_lut is not None:
            filtered = _apply_64_cube_lut(result, skin_lut)
            result = result * (1.0 - blend) + filtered * blend
            print(f"Filter {filter_id}: SKIN-LUT blend={blend:.2f} plistAlpha={plist_alpha:.2f}", flush=True)

    return (
        np.clip(result * 255.0, 0, 255).astype(np.uint8),
        coverage,
        effective_profiles,
        hair_coverage,
        hair_effective_alpha,
    )


def beautify(
    rgb_u8: np.ndarray,
    skin_fleck_clean_flag: int = DEFAULT_CONTROL_STRENGTH,
    smooth_face_skin_alpha: int = DEFAULT_CONTROL_STRENGTH,
    skin_tone_face_alpha: int = DEFAULT_CONTROL_STRENGTH,
    skin_white_alpha: int = DEFAULT_CONTROL_STRENGTH,
    lipstick_alpha: int = DEFAULT_CONTROL_STRENGTH,
    lipstick_preset: str = "luozhuang",
    hair_color_strength: int = DEFAULT_CONTROL_STRENGTH,
    hair_color_preset: str = "none",
    face_lift_region: str = "none",
    face_lift_strength: int = 50,
    face_fill_region: str = "none",
    face_fill_strength: int = 50,
    profile_overrides: list[str] | None = None,
) -> tuple[np.ndarray, float, list[dict[str, object]], float, float]:
    prepared = _prepare_beauty_base(
        rgb_u8,
        skin_fleck_clean_flag,
        smooth_face_skin_alpha,
        skin_tone_face_alpha,
        skin_white_alpha,
        profile_overrides,
    )
    return _finish_beauty(
        prepared,
        lipstick_alpha,
        lipstick_preset,
        hair_color_strength,
        hair_color_preset,
        face_lift_region=face_lift_region,
        face_lift_strength=face_lift_strength,
        face_fill_region=face_fill_region,
        face_fill_strength=face_fill_strength,
    )


@app.get("/api/health")
def health() -> dict[str, object]:
    makeup_catalog = _load_makeup_library()
    makeup_group_count, makeup_material_count, makeup_theme_count = _makeup_library_stats(
        makeup_catalog
    )
    model_state = {
        "Fd": FACE_DETECT_MODEL.is_file(),
        "Ga2": GENDER_AGE_MODEL.is_file(),
        "Lp": FACE_LANDMARK_MODEL.is_file(),
        "PhotoFaceContour": FACE_CONTOUR_MODEL.is_file(),
        "skintone_0411_384_epoch_850_2": SKINTONE_MODEL.is_file(),
        "facialsmooth_0529_192_384_epoch_1050": FACIAL_SMOOTH_MODEL.is_file(),
        "Expelliarmus": BLEMISH_MASK_MODEL.is_file(),
        "fuxiCreator_20251225": BLEMISH_HEAL_MODEL.is_file(),
        "Het": HEAD_MATTE_MODEL.is_file(),
        "ChpsJy": HUMAN_PARSE_MODEL.is_file(),
        "hairSeamer_full": HAIR_SEAMER_MODEL.is_file(),
        "coreml_runner": _ensure_coreml_runner(),
    }
    asset_state = {
        "white_lookup_table": WHITE_SKIN_LUT.is_file(),
        "makeup_library": KUMO_MAKEUP_LIBRARY.is_file(),
        "preset_material_library": KUMO_PRESET_MATERIAL_LIBRARY.is_file(),
        "makeup_material_assets": _makeup_assets_valid(makeup_catalog),
        "makeup_face_oval": (KUMO_MAKEUP_DIR / "face_oval.png").is_file(),
        **{
            f"faceguide_lift_{key}": (
                KUMO_FACE_GUIDE_DIR / str(region["thumbnail"])
            ).is_file()
            for key, region in KUMO_FACE_LIFT_REGIONS.items()
        },
        **{
            f"faceguide_fill_{key}": (
                KUMO_FACE_GUIDE_DIR / str(region["thumbnail"])
            ).is_file()
            for key, region in KUMO_FACE_FILL_REGIONS.items()
        },
        **{
            f"{key}_lip_material": Path(preset["texture"]).is_file()
            for key, preset in KUMO_LIPSTICK_PRESETS.items()
        },
        **{
            f"hair_{key}_thumbnail": (KUMO_HAIR_THUMB_DIR / f"{key}.jpg").is_file()
            for key in KUMO_HAIR_PRESETS
        },
        **{
            f"hair_{key}_config": (
                KUMO_HAIR_CONFIG_DIR / str(preset["folder"]) / "config.json"
            ).is_file()
            for key, preset in KUMO_HAIR_PRESETS.items()
        },
        **{
            f"hair_{key}_material": (
                KUMO_HAIR_CONFIG_DIR
                / str(preset["folder"])
                / str(preset["material"])
            ).is_file()
            for key, preset in KUMO_HAIR_PRESETS.items()
        },
    }
    return {
        "ok": all(model_state.values()) and all(asset_state.values()),
        "runtime": "MNN CPU + ONNX Runtime CPU + Apple CoreML CPU",
        "uses_mizar": False,
        "fallback_models": False,
        "pipeline": [
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
            f"KumoMakeupARP:{makeup_group_count}-groups|{makeup_material_count}-materials|{makeup_theme_count}-themes",
            "KumoFaceLift:4-regions",
            "KumoFaceFill:10-regions",
        ],
        "skintone_contract": "kumo-residual-rgb-v1",
        "blemish_healing_contract": "Kumoo BlackHead/FleckFlaw Expelliarmus flaw+nevus mask, fuxiCreator RGB, low-pass residual compositor",
        "native_blemish_contract": NATIVE_BLEMISH_MODEL_CONTRACT,
        "gender_age_contract": "Fd five-point aligned face -> Ga2 RGB 224x224 ImageNet -> one 9-class demographic head",
        "preset": "Gốc (Kumo five demographic slots)",
        "preset_strengths": {
            "smooth_face_skin_alpha": KUMO_GOC_PROFILES["woman"]["smooth_face_skin_alpha"],
            "skin_fleck_clean_flag": KUMO_GOC_PROFILES["woman"]["skin_fleck_clean_flag"],
            "nevus_removal_flag": 0,
            "body_fleck_clean_flag": 0,
            "skin_tone_face_alpha": KUMO_GOC_PROFILES["woman"]["skin_tone_face_alpha"],
            "skin_white_alpha": KUMO_GOC_PROFILES["woman"]["skin_white_alpha"],
            "lipstick_alpha": 30,
        },
        "preset_profiles": KUMO_GOC_PROFILES,
        "source_preset_reference_only": {
            "smooth_face_skin_low_alpha": 64,
            "smooth_face_skin_hight_alpha": -33,
            "neutral_gray_smooth_alpha": 60,
            "neutral_gray_enhance_alpha": 30,
        },
        "control_semantics": "0..100 percent of each Ga2 face's Kumo Gốc slot",
        "operators": {
            "face_acne_freckle": "Kumoo GPUImageBlackHeadCleanFilter Expelliarmus flaw/nevus mask + fuxiCreator_20251225 RGB + deepSmooth/low-pass residual gate, with protected eyes/brows/lips",
            "skin_whitening": "shader_506.glsl + white_lookup_table.png",
            "lipstick": "MPLIPSTICKV2 + 3 Kumo materials + BlendMultiply",
            "hair_color": "ChpsJy RGB[0,1] HairSegment fallback + Het connected-component seed + foreground skin/ear occlusion + hairSeamer_full + HairColorFilter blendType=3 SetLum",
            "makeup": "Lp106 affine + Kumo ARP Rectangle/ORGBA/BlendMode/HeadMaskPath compositor",
            "face_lift": "Lp106 regional remap + face_flat_lift_switch + 4 recovered region parameters",
            "face_fill": "Lp106 regional remap + face_full_switch + 10 recovered region parameters",
        },
        "face_volume_contract": {
            "lift_switch": "face_flat_lift_switch",
            "fill_switch": "face_full_switch",
            "lift_regions": KUMO_FACE_LIFT_REGIONS,
            "fill_regions": KUMO_FACE_FILL_REGIONS,
        },
        "makeup_contract": f"{makeup_material_count} Kumo ARP materials + {makeup_theme_count} original themes",
        "lipstick_presets": {
            key: {
                "label": preset["label"],
                "rectangle": preset["rectangle"],
                "material_alpha": preset["material_alpha"],
            }
            for key, preset in KUMO_LIPSTICK_PRESETS.items()
        },
        "hair_color_contract": "Kumo HairColorFilter blendType=3 / SetLum / ClipColor",
        "hair_color_presets": {
            key: {
                "label": preset["label"],
                "source_name": preset["source_name"],
                "default_alpha": preset["default_alpha"],
                "max_alpha_ratio": preset["max_alpha_ratio"],
                "thumbnail": f"/api/assets/haircolor/{key}.jpg",
            }
            for key, preset in KUMO_HAIR_PRESETS.items()
        },
        "extra_filters": False,
        "models": model_state,
        "assets": asset_state,
    }


@app.get("/api/assets/haircolor/{preset_id}.jpg")
def hair_color_thumbnail(preset_id: str) -> FileResponse:
    if preset_id not in KUMO_HAIR_PRESETS:
        raise HTTPException(status_code=404, detail="Không có thumbnail màu tóc Kumo này.")
    return FileResponse(
        KUMO_HAIR_THUMB_DIR / f"{preset_id}.jpg",
        media_type="image/jpeg",
        filename=f"kumo-hair-{preset_id}.jpg",
    )


@app.get("/api/face-volume/library")
def face_volume_library() -> dict[str, object]:
    def public_regions(regions: dict[str, dict[str, str]]) -> list[dict[str, str]]:
        return [
            {
                "key": key,
                "label": region["label"],
                "parameter": region["parameter"],
                "thumbnail": f"/api/assets/faceguide/{region['thumbnail']}",
            }
            for key, region in regions.items()
        ]

    return {
        "lift_switch": "face_flat_lift_switch",
        "fill_switch": "face_full_switch",
        "lift": public_regions(KUMO_FACE_LIFT_REGIONS),
        "fill": public_regions(KUMO_FACE_FILL_REGIONS),
        "landmarks": "Lp106",
        "control_semantics": "0..100 regional operator strength",
    }


@app.get("/api/assets/faceguide/{asset_name}")
def face_guide_asset(asset_name: str) -> FileResponse:
    allowed = {
        str(region["thumbnail"])
        for region in (*KUMO_FACE_LIFT_REGIONS.values(), *KUMO_FACE_FILL_REGIONS.values())
    }
    if asset_name not in allowed:
        raise HTTPException(status_code=404, detail="Không có thumbnail vùng mặt Kumo này.")
    return FileResponse(KUMO_FACE_GUIDE_DIR / asset_name, media_type="image/jpeg")


@app.get("/api/makeup/library")
def makeup_library() -> dict[str, object]:
    return _load_makeup_library()


@app.get("/api/assets/makeup/{asset_path:path}")
def makeup_asset(asset_path: str) -> FileResponse:
    root = KUMO_MAKEUP_DIR.resolve()
    candidate = (root / asset_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Đường dẫn vật liệu không hợp lệ.") from exc
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Không có vật liệu trang điểm Kumo này.")
    return FileResponse(candidate)


@app.get("/api/photobooth/library")
def photobooth_library() -> dict[str, object]:
    """Serve the recovered PhotoBooth catalog with API-backed cover URLs."""
    if not KUMO_PHOTOBOOTH_LIBRARY.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy thư viện PhotoBooth Kumo.")
    payload = json.loads(KUMO_PHOTOBOOTH_LIBRARY.read_text(encoding="utf-8"))
    for preset in payload.get("presets", []):
        preset["cover"] = f"/api/assets/presets/{preset['cover']}"
    return payload


@app.get("/api/assets/presets/{asset_name}")
def photobooth_cover(asset_name: str) -> FileResponse:
    root = KUMO_PHOTOBOOTH_COVER_DIR.resolve()
    candidate = (root / asset_name).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Đường dẫn cover PhotoBooth không hợp lệ.") from exc
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Không có cover PhotoBooth này.")
    return FileResponse(candidate)


@app.get("/api/filters/library")
def filters_library() -> dict[str, object]:
    """Serve the Kumo 3D LUT filters library catalog."""
    if not KUMO_FILTERS_LIBRARY.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy thư viện bộ lọc Kumo.")
    return json.loads(KUMO_FILTERS_LIBRARY.read_text(encoding="utf-8"))


@app.get("/api/color_ref/packs")
def color_ref_packs() -> list[dict[str, object]]:
    """Serve the Kumo AI color transfer reference packs."""
    if not KUMO_COLOR_REF_PACKS.is_file():
        return []
    return json.loads(KUMO_COLOR_REF_PACKS.read_text(encoding="utf-8"))


@app.get("/assets/color_ref/{asset_name:path}")
@app.get("/api/assets/color_ref/{asset_name:path}")
def color_ref_asset(asset_name: str) -> FileResponse:
    root = KUMO_COLOR_REF_DIR.resolve()
    candidate = (root / asset_name).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Đường dẫn ảnh mẫu không hợp lệ.") from exc
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh mẫu này.")
    return FileResponse(candidate)


@app.post("/api/portrait/analyze")
async def portrait_analyze(image: UploadFile = File(...)) -> dict[str, object]:
    started = time.perf_counter()
    payload = await image.read()
    rgb = decode_image(payload)
    source_key = hashlib.sha256(payload).hexdigest()
    _, _, cached_faces, landmarks, _, _, _, _ = _portrait_analysis(rgb, source_key)
    es = EyeSegmenter.get_instance()
    faces = [dict(face) for face in cached_faces]
    for face, points in zip(faces, landmarks):
        face["landmarks"] = np.round(points, 3).tolist()
        if es:
            try:
                left_segs = es.segment(rgb, points, True)
                right_segs = es.segment(rgb, points, False)
                face["eye_segments"] = {
                    "left_curve": left_segs.get("upper", []),
                    "left_lower": left_segs.get("lower", []),
                    "right_curve": right_segs.get("upper", []),
                    "right_lower": right_segs.get("lower", [])
                }
            except Exception as e:
                print("EyeSegmenter error:", e)
                face["eye_segments"] = None
    return {
        "face_count": len(faces),
        "faces": faces,
        "image_width": rgb.shape[1],
        "image_height": rgb.shape[0],
        "preset": "Gốc",
        "model": "Ga2",
        "landmark_model": "Lp106",
        "notice": "Nhóm xử lý là ước lượng theo diện mạo; có thể sửa tay cho từng mặt.",
        "processing_ms": round((time.perf_counter() - started) * 1000.0, 1),
    }


# ================= PhotoBooth shaping backed by recovered face operators =================

def _apply_preset_shaping(rgb: np.ndarray, face_mask: np.ndarray, faces: list, landmark_sets: list, params: dict, strength: float):
    # Presets in Kumoo PhotoBooth represent pure Color, Lighting, Retouch & Makeup styles.
    # 2D radial warps pinch dark pixels (nostrils, eyelashes) into artificial black dots.
    return rgb


@lru_cache(maxsize=1)
def _load_makeup_library() -> dict[str, object]:
    """Merge the core ARP catalog with preset-only materials by part key."""

    if not KUMO_MAKEUP_LIBRARY.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy thư viện trang điểm Kumo.")
    library = json.loads(KUMO_MAKEUP_LIBRARY.read_text(encoding="utf-8"))
    if not KUMO_PRESET_MATERIAL_LIBRARY.is_file():
        return library

    supplement = json.loads(KUMO_PRESET_MATERIAL_LIBRARY.read_text(encoding="utf-8"))
    parts_by_key = {part["key"]: part for part in library.get("parts", [])}
    for extra_part in supplement.get("parts", []):
        target = parts_by_key.get(extra_part.get("key"))
        if target is None:
            library.setdefault("parts", []).append(extra_part)
            parts_by_key[extra_part["key"]] = extra_part
            continue
        known_dirs = {material.get("dir") for material in target.get("materials", [])}
        target.setdefault("materials", []).extend(
            material
            for material in extra_part.get("materials", [])
            if material.get("dir") not in known_dirs
        )
    return library


def _makeup_library_stats(library: dict[str, object]) -> tuple[int, int, int]:
    parts = library.get("parts", [])
    themes = library.get("themes", [])
    return (
        len(parts),
        sum(len(part.get("materials", [])) for part in parts),
        len(themes),
    )


def _makeup_assets_valid(library: dict[str, object]) -> bool:
    for part in library.get("parts", []):
        for material in part.get("materials", []):
            urls = [material.get("thumb")]
            for layer in material.get("layers", []):
                urls.extend((layer.get("tex"), layer.get("maskTex"), layer.get("clip")))
            for url in urls:
                if not url:
                    continue
                relative = str(url).removeprefix("/assets/makeup/")
                if not (KUMO_MAKEUP_DIR / relative).is_file():
                    return False
    return True



@app.post("/api/portrait/beautify")
async def portrait_beautify(
    image: UploadFile = File(...),
    skin_fleck_clean_flag: int = Form(
        DEFAULT_CONTROL_STRENGTH,
        ge=0,
        le=100,
    ),
    smooth_face_skin_alpha: int = Form(
        DEFAULT_CONTROL_STRENGTH,
        ge=0,
        le=100,
    ),
    smooth_texture_skin_alpha: int = Form(
        0,
        ge=0,
        le=100,
    ),
    skin_tone_face_alpha: int = Form(
        DEFAULT_CONTROL_STRENGTH,
        ge=0,
        le=100,
    ),
    skin_white_alpha: int = Form(
        DEFAULT_CONTROL_STRENGTH,
        ge=0,
        le=100,
    ),
    lipstick_alpha: int = Form(
        DEFAULT_CONTROL_STRENGTH,
        ge=0,
        le=100,
    ),
    lipstick_preset: str = Form("luozhuang"),
    hair_color_strength: int = Form(
        DEFAULT_CONTROL_STRENGTH,
        ge=0,
        le=100,
    ),
    hair_color_preset: str = Form("none"),
    face_lift_region: str = Form("none"),
    face_lift_strength: int = Form(50, ge=0, le=100),
    face_fill_region: str = Form("none"),
    face_fill_strength: int = Form(50, ge=0, le=100),
    profile_overrides: Optional[str] = Form(None),
    photo_preset_params: Optional[str] = Form(None),
    photo_preset_strength: int = Form(100, ge=0, le=100),
    skin_color_lut_preset: str = Form("none"),
    skin_color_lut_alpha: int = Form(0, ge=0, le=100),
    skin_tone_multiple_alpha: int = Form(0, ge=0, le=100),
    filter_id: str = Form("none"),
    filter_strength: int = Form(100, ge=0, le=100),
) -> Response:
    started = time.perf_counter()
    payload = await image.read()
    rgb = decode_image(payload)
    analysis_cache_key = hashlib.sha256(payload).hexdigest()
    overrides: list[str] | None = None
    preset_params: dict[str, object] | None = None
    if profile_overrides:
        try:
            decoded_overrides = json.loads(profile_overrides)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="profile_overrides phải là JSON.") from exc
        if not isinstance(decoded_overrides, list) or not all(
            isinstance(item, str) for item in decoded_overrides
        ):
            raise HTTPException(status_code=422, detail="profile_overrides phải là mảng tên profile.")
        overrides = decoded_overrides

    if photo_preset_params:
        try:
            decoded_preset = json.loads(photo_preset_params)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=422,
                detail="photo_preset_params phải là JSON.",
            ) from exc
        if not isinstance(decoded_preset, dict):
            raise HTTPException(
                status_code=422,
                detail="photo_preset_params phải là object all_params của Kumo.",
            )
        preset_params = decoded_preset

    if lipstick_preset not in KUMO_LIPSTICK_PRESETS:
        raise HTTPException(
            status_code=422,
            detail="lipstick_preset không thuộc bộ vật liệu Kumo đã xác nhận.",
        )

    if hair_color_preset != "none" and hair_color_preset not in KUMO_HAIR_PRESETS:
        raise HTTPException(
            status_code=422,
            detail="hair_color_preset không thuộc 8 màu tóc Kumo gốc.",
        )

    if face_lift_region != "none" and face_lift_region not in KUMO_FACE_LIFT_REGIONS:
        raise HTTPException(
            status_code=422,
            detail="face_lift_region không thuộc 4 vùng nâng cơ Kumo gốc.",
        )
    if face_fill_region != "none" and face_fill_region not in KUMO_FACE_FILL_REGIONS:
        raise HTTPException(
            status_code=422,
            detail="face_fill_region không thuộc 10 vùng đầy đặn Kumo gốc.",
        )

    cache_key = _portrait_base_cache_key(
        payload,
        skin_fleck_clean_flag,
        smooth_face_skin_alpha,
        skin_tone_face_alpha,
        skin_white_alpha,
        overrides,
        preset_params,
        photo_preset_strength,
        smooth_texture_skin_alpha=smooth_texture_skin_alpha,
        skin_color_lut_preset=skin_color_lut_preset,
        skin_color_lut_alpha=skin_color_lut_alpha,
        skin_tone_multiple_alpha=skin_tone_multiple_alpha,
    )

    base_started = time.perf_counter()
    prepared = _cache_get(_portrait_base_cache, cache_key)
    base_cache_status = "HIT"
    if prepared is None:
        base_cache_status = "MISS"
        prepared = _prepare_beauty_base(
            rgb,
            skin_fleck_clean_flag,
            smooth_face_skin_alpha,
            smooth_texture_skin_alpha,
            skin_tone_face_alpha,
            skin_white_alpha,
            overrides,
            preset_params,
            photo_preset_strength,
            analysis_cache_key,
            skin_color_lut_preset=skin_color_lut_preset,
            skin_color_lut_alpha=skin_color_lut_alpha,
            skin_tone_multiple_alpha=skin_tone_multiple_alpha,
        )
        _cache_put(_portrait_base_cache, cache_key, prepared)
    base_ms = (time.perf_counter() - base_started) * 1000.0

    hair_started = time.perf_counter()
    hair_cache_key = f"{cache_key}:overrides={overrides}"
    hair_mask = _cache_get(_portrait_hair_mask_cache, hair_cache_key)
    hair_cache_status = "HIT"
    if hair_mask is None:
        hair_cache_status = "MISS"
        base_result, _, faces, combined_mask, landmark_sets = prepared
        profile_keys = _resolve_face_profiles(faces, overrides)
        active_flags = [key in ("woman", "oldwoman") for key in profile_keys]
        hair_mask = _hair_mask(
            np.clip(base_result * 255.0, 0, 255).astype(np.uint8),
            combined_mask,
            landmark_sets,
            active_flags=active_flags,
        )
        _cache_put(_portrait_hair_mask_cache, hair_cache_key, hair_mask)
    hair_mask_ms = (time.perf_counter() - hair_started) * 1000.0

    material_started = time.perf_counter()
    effective_filter_id = filter_id
    effective_filter_strength = filter_strength
    effective_lipstick_preset = lipstick_preset
    effective_lipstick_alpha = lipstick_alpha

    if preset_params and photo_preset_strength > 0:
        # Extract preset 3D LUT filter
        preset_filter = preset_params.get("filter")
        if isinstance(preset_filter, dict):
            fid = preset_filter.get("filter_id", "none")
            fal = preset_filter.get("filters_lut_alpha", 0)
            if fid and fid != "none" and fal > 0:
                effective_filter_id = str(fid)
                effective_filter_strength = int(fal * (photo_preset_strength / 100.0))

        # Extract preset lipstick
        preset_mouth = preset_params.get("mouth")
        if isinstance(preset_mouth, list):
            slot_idx = 1
            if slot_idx < len(preset_mouth) and isinstance(preset_mouth[slot_idx], dict):
                m_info = preset_mouth[slot_idx]
                m_id = m_info.get("id")
                m_alpha = m_info.get("alpha", 0)
                if m_id and m_id in KUMO_LIPSTICK_PRESETS and m_alpha > 0:
                    effective_lipstick_preset = str(m_id)
                    effective_lipstick_alpha = int(m_alpha * (photo_preset_strength / 100.0))

    output, coverage, faces, hair_coverage, hair_effective_alpha = _finish_beauty(
        prepared,
        effective_lipstick_alpha,
        effective_lipstick_preset,
        hair_color_strength,
        hair_color_preset,
        hair_mask,
        face_lift_region,
        face_lift_strength,
        face_fill_region,
        face_fill_strength,
        filter_id=effective_filter_id,
        filter_strength=effective_filter_strength,
        preset_params=preset_params,
        photo_preset_strength=photo_preset_strength,
    )
        

    material_ms = (time.perf_counter() - material_started) * 1000.0
    encoded = io.BytesIO()
    Image.fromarray(output).save(encoded, format="JPEG", quality=95, optimize=True)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    _timing_log.info(
        "Kumo portrait %.1f ms | base=%s %.1f | hair-mask=%s %.1f | materials %.1f",
        elapsed_ms,
        base_cache_status,
        base_ms,
        hair_cache_status,
        hair_mask_ms,
        material_ms,
    )
    first_effective = faces[0]["effective"]
    return Response(
        content=encoded.getvalue(),
        media_type="image/jpeg",
        headers={
            "Content-Disposition": 'inline; filename="portrait-beautified.jpg"',
            "X-Processing-Ms": f"{elapsed_ms:.1f}",
            "X-Face-Coverage": f"{coverage:.5f}",
            "X-Face-Count": str(len(faces)),
            "X-Face-Profiles": ",".join(str(face["profile"]) for face in faces),
            "X-Skin-Fleck-Clean": str(skin_fleck_clean_flag),
            "X-Smooth-Face-Skin": str(smooth_face_skin_alpha),
            "X-Skin-Tone-Face": str(skin_tone_face_alpha),
            "X-Skin-White": str(skin_white_alpha),
            "X-Lipstick-Alpha": str(lipstick_alpha),
            "X-Lipstick-Preset": lipstick_preset,
            "X-Hair-Color-Strength": str(hair_color_strength),
            "X-Hair-Color-Preset": hair_color_preset,
            "X-Hair-Color-Effective": f"{hair_effective_alpha:.4f}",
            "X-Face-Lift-Region": face_lift_region,
            "X-Face-Lift-Strength": str(face_lift_strength),
            "X-Face-Fill-Region": face_fill_region,
            "X-Face-Fill-Strength": str(face_fill_strength),
            "X-Hair-Mask-Coverage": f"{hair_coverage:.5f}",
            "X-Portrait-Base-Cache": base_cache_status,
            "X-Hair-Mask-Cache": hair_cache_status,
            "X-Base-Stage-Ms": f"{base_ms:.1f}",
            "X-Hair-Mask-Stage-Ms": f"{hair_mask_ms:.1f}",
            "X-Material-Stage-Ms": f"{material_ms:.1f}",
            "X-Kumo-Effective-Smooth": f"{first_effective['smooth']:.2f}",
            "X-Kumo-Effective-Blemish": f"{first_effective['blemish']:.2f}",
            "X-Kumo-Effective-Skin-Tone": f"{first_effective['skin_tone']:.2f}",
            "X-Kumo-Effective-Body-Tone": f"{first_effective['body_tone']:.2f}",
            "X-Kumo-Effective-Skin-White": f"{first_effective['skin_white']:.2f}",
            "X-Kumoo-Pipeline": "Fd,Ga2,Lp,PhotoFaceContour,facialsmooth_0529,Expelliarmus,fuxiCreator_20251225,skintone_0411,SkinWhiteningLUT,KumoFaceLift,KumoFaceFill,ChpsJyHairSegmentFallback,HetComponentSeed,ForegroundSkinOcclusion,hairSeamer_full,HairColorFilter,MPLIPSTICKV2",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=API_PORT, reload=False)
