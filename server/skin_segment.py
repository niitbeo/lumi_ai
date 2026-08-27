"""
Skin Segmentation Module — Kumoo Cis.onnx / PhotoSkin
Segments all visible human skin (face, neck, shoulders, arms, hands).

NOTE: Despite the .onnx extension, Cis.onnx is actually MNN FlatBuffers format.
This module uses MNN runtime (same as Het head matte model).

Input: (1, 3, H, W) RGB float32 [0, 1] — dynamic spatial dims, standard 512×512
Output: Soft probability mask of skin regions
"""

from __future__ import annotations

import cv2
import numpy as np

try:
    import MNN  # type: ignore
except ImportError:
    MNN = None  # type: ignore

# Standard Kumoo C-family model input size
CIS_INPUT_SIZE = 512


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -88.0, 88.0)))


def run_skin_segment(
    image_rgb: np.ndarray,
    interpreter: object,
    session: object,
    threshold: float = 0.40,
    blur_kernel: int = 5,
) -> np.ndarray:
    """
    Run full-body skin segmentation using MNN runtime.

    Args:
        image_rgb: Full image in RGB uint8 (H, W, 3)
        interpreter: MNN.Interpreter for Cis model
        session: MNN session
        threshold: Soft threshold for skin probability (default 0.40)
        blur_kernel: Gaussian blur kernel size for smoothing edges

    Returns:
        skin_mask: (H, W) float32 in [0, 1] — skin probability
    """
    if MNN is None:
        raise RuntimeError("MNN package not available")

    orig_h, orig_w = image_rgb.shape[:2]

    # Resize to model input size
    resized = cv2.resize(image_rgb, (CIS_INPUT_SIZE, CIS_INPUT_SIZE), interpolation=cv2.INTER_LINEAR)

    # Normalize to [0, 1] and convert to NCHW
    tensor_data = (resized.astype(np.float32) / 255.0).transpose(2, 0, 1)[None]  # (1, 3, 512, 512)

    # Set input — MNN needs explicit resize for dynamic-shaped models
    inp = interpreter.getSessionInput(session)
    interpreter.resizeTensor(inp, (1, 3, CIS_INPUT_SIZE, CIS_INPUT_SIZE))
    interpreter.resizeSession(session)
    inp_tensor = MNN.Tensor(
        (1, 3, CIS_INPUT_SIZE, CIS_INPUT_SIZE),
        MNN.Halide_Type_Float,
        tensor_data,
        MNN.Tensor_DimensionType_Caffe,
    )
    inp.copyFrom(inp_tensor)

    # Run inference
    interpreter.runSession(session)

    # Get output
    out = interpreter.getSessionOutput(session, "output0")
    out_host = MNN.Tensor(out.getShape(), MNN.Halide_Type_Float, MNN.Tensor_DimensionType_Caffe)
    out.copyToHostTensor(out_host)
    raw_output = np.array(out_host.getData()).reshape(out.getShape())  # (1, C, H, W)

    # Handle different output formats
    if raw_output.ndim == 4:
        if raw_output.shape[1] == 1:
            # Single-channel binary mask
            mask_512 = _sigmoid(raw_output[0, 0])
        elif raw_output.shape[1] == 2:
            # 2-class: softmax → take skin class (channel 1)
            exp = np.exp(raw_output[0] - raw_output[0].max(axis=0, keepdims=True))
            softmax = exp / exp.sum(axis=0, keepdims=True)
            mask_512 = softmax[1]  # Skin class
        else:
            # Multi-class: sigmoid on channel 0
            mask_512 = _sigmoid(raw_output[0, 0])
    else:
        mask_512 = _sigmoid(raw_output.squeeze())

    # Resize back to original image size
    mask_full = cv2.resize(mask_512, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)

    # Smooth edges
    if blur_kernel > 0:
        mask_full = cv2.GaussianBlur(mask_full, (blur_kernel, blur_kernel), 0)

    return np.clip(mask_full, 0.0, 1.0).astype(np.float32)


def representative_skin_rgb(
    image_rgb: np.ndarray,
    skin_mask: np.ndarray,
    min_threshold: float = 0.5,
) -> np.ndarray:
    """
    Calculate the representative skin color anchor from skin pixels.
    Kumoo uses this for residual color delta encoding in skintone model:
      encoded = clamp((source - skinRGB) * 0.5 + 127.5, 0, 255)

    Args:
        image_rgb: Full image RGB uint8 (H, W, 3)
        skin_mask: Skin probability mask (H, W) float32 [0,1]
        min_threshold: Minimum probability to consider as skin

    Returns:
        skinRGB: (3,) float32 representative skin color
    """
    valid = skin_mask > min_threshold
    if valid.sum() < 100:
        # Fallback: use center of image
        h, w = image_rgb.shape[:2]
        cx, cy = w // 2, h // 2
        patch = image_rgb[max(0, cy - 20):cy + 20, max(0, cx - 20):cx + 20]
        return patch.mean(axis=(0, 1)).astype(np.float32)

    skin_pixels = image_rgb[valid].astype(np.float32)

    # Luminance-based filtering: discard extreme 30% (too dark / too bright)
    lum = 0.299 * skin_pixels[:, 0] + 0.587 * skin_pixels[:, 1] + 0.114 * skin_pixels[:, 2]
    p_lo = np.percentile(lum, 30)
    p_hi = np.percentile(lum, 70)
    mid_band = (lum >= p_lo) & (lum <= p_hi)

    if mid_band.sum() < 50:
        return skin_pixels.mean(axis=0)

    return skin_pixels[mid_band].mean(axis=0)
