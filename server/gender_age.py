"""Independent runner for Kumoo's recovered Ga2 demographic classifier."""

from __future__ import annotations

import threading
from pathlib import Path

import cv2
import MNN
import numpy as np


PROFILE_LABELS = {
    "man": "Nam",
    "woman": "Nữ",
    "child": "Trẻ em",
    "oldwoman": "Nữ lớn tuổi",
    "oldman": "Nam lớn tuổi",
}

# Ga2 is one nine-way demographic classifier.  It is not two gender logits
# concatenated with seven age logits.  The paired classes retain sex for the
# adult presets while the first three youth classes all map to Kumo's shared
# child slot.  This mapping is also consistent with Kumo's five public
# ``people_type`` slots: man, woman, child, oldwoman, oldman.
CLASS_TO_PROFILE = {
    0: "child",      # baby / very young child
    1: "child",      # girl
    2: "child",      # boy
    3: "woman",      # young woman
    4: "man",        # young man
    5: "woman",      # adult woman
    6: "man",        # adult man
    7: "oldwoman",   # older woman
    8: "oldman",     # older man
}


class GenderAgeClassifier:
    """Run Ga2's nine combined demographic classes.

    The graph is an MNN FlatBuffer despite its recovered ``.onnx`` suffix.
    Its ResNet input contract is an RGB 224x224 five-point-aligned face with
    ImageNet normalization.  Treating the output as ``2 + 7`` independently
    caused the same family photo to be labelled female three times.
    """

    def __init__(self, model_path: str | Path) -> None:
        self.model_path = Path(model_path)
        self._net = MNN.Interpreter(str(self.model_path))
        self._session = self._net.createSession()
        self._input = self._net.getSessionInput(self._session)
        self._net.resizeTensor(self._input, (1, 3, 224, 224))
        self._net.resizeSession(self._session)
        self._output = self._net.getSessionOutput(self._session)
        self._lock = threading.Lock()

    @staticmethod
    def _crop(rgb: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
        height, width = rgb.shape[:2]
        x, y, box_width, box_height = box
        center_x = x + box_width * 0.5
        center_y = y + box_height * 0.5
        size = max(box_width, box_height) * 1.25
        x1 = max(0, int(round(center_x - size * 0.5)))
        y1 = max(0, int(round(center_y - size * 0.5)))
        x2 = min(width, int(round(center_x + size * 0.5)))
        y2 = min(height, int(round(center_y + size * 0.5)))
        return rgb[y1:y2, x1:x2]

    @staticmethod
    def _align(
        rgb: np.ndarray,
        keypoints: list[list[float]] | np.ndarray,
    ) -> np.ndarray:
        """Align Fd's eyes/nose/mouth points to Ga2's 224px face contract.

        Ga2 is a face classifier, so feeding a loose detector rectangle changes
        its logits substantially.  The five-point similarity transform keeps
        both eyes and both mouth corners in the same coordinates used by the
        training crop.
        """

        source = np.asarray(keypoints, dtype=np.float32)
        if source.shape != (5, 2) or not np.all(np.isfinite(source)):
            raise ValueError("Ga2 alignment requires five finite Fd keypoints")
        target = 2.0 * np.asarray(
            [
                [38.2946, 51.6963],
                [73.5318, 51.5014],
                [56.0252, 71.7366],
                [41.5493, 92.3655],
                [70.7299, 92.2041],
            ],
            dtype=np.float32,
        )
        matrix, _ = cv2.estimateAffinePartial2D(source, target, method=cv2.LMEDS)
        if matrix is None or not np.all(np.isfinite(matrix)):
            raise ValueError("Fd keypoints cannot be aligned for Ga2")
        return cv2.warpAffine(
            rgb,
            matrix,
            (224, 224),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )

    @staticmethod
    def _softmax(values: np.ndarray) -> np.ndarray:
        shifted = values - float(np.max(values))
        exponent = np.exp(shifted)
        return exponent / max(float(np.sum(exponent)), 1e-8)

    @classmethod
    def _decode_logits(cls, logits: np.ndarray) -> dict[str, object]:
        """Decode the single nine-way head into Kumo's five public slots."""

        if logits.size != 9 or not np.all(np.isfinite(logits)):
            raise ValueError(f"Ga2 output must contain 9 finite logits, got {logits.shape}")
        scores = cls._softmax(logits)
        class_index = int(np.argmax(scores))
        profile = CLASS_TO_PROFILE[class_index]
        if profile in {"man", "oldman"}:
            gender = "man"
        elif profile in {"woman", "oldwoman"}:
            gender = "woman"
        else:
            gender = "child"
        return {
            "profile": profile,
            "label": PROFILE_LABELS[profile],
            "gender": gender,
            "demographic_class": class_index,
            # Retained for API compatibility; it now names the actual combined
            # Ga2 class instead of pretending to be a separate age head.
            "age_group": class_index,
            "confidence": round(float(scores[class_index]), 4),
        }

    def classify(
        self,
        rgb: np.ndarray,
        box: tuple[int, int, int, int],
        keypoints: list[list[float]] | np.ndarray | None = None,
    ) -> dict[str, object]:
        crop = self._align(rgb, keypoints) if keypoints is not None else self._crop(rgb, box)
        if crop.size == 0:
            raise ValueError("empty Ga2 face crop")

        resized = cv2.resize(crop, (224, 224), interpolation=cv2.INTER_AREA)
        normalized = resized.astype(np.float32) / 255.0
        normalized = (normalized - np.asarray([0.485, 0.456, 0.406], np.float32)) / np.asarray(
            [0.229, 0.224, 0.225], np.float32
        )
        tensor_data = np.ascontiguousarray(normalized.transpose(2, 0, 1)[None])
        tensor = MNN.Tensor(
            tensor_data.shape,
            MNN.Halide_Type_Float,
            tensor_data,
            MNN.Tensor_DimensionType_Caffe,
        )

        with self._lock:
            self._input.copyFrom(tensor)
            self._net.runSession(self._session)
            host = MNN.Tensor(
                self._output.getShape(),
                MNN.Halide_Type_Float,
                np.zeros(self._output.getShape(), dtype=np.float32),
                MNN.Tensor_DimensionType_Caffe,
            )
            self._output.copyToHostTensor(host)
            logits = np.asarray(host.getData(), dtype=np.float32).reshape(-1)

        decoded = self._decode_logits(logits)
        decoded["aligned"] = keypoints is not None
        return decoded
