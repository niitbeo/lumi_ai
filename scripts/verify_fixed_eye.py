import cv2
import numpy as np
from PIL import Image, ImageOps
import json
import os
import sys

sys.path.append('/Users/nguyenletruong/lumi_portrait_standalone/server')
from server import face_detector, face_landmark_sets

# 1. Load User Image
img_path = '/Users/nguyenletruong/.gemini/antigravity/brain/f64627a2-78e1-4c0d-97b2-905392fb9354/.user_uploaded/media_1787650984641.jpg'
img_bgr = cv2.imread(img_path)
img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
h_img, w_img = img_rgb.shape[:2]

boxes = face_detector().detect(img_bgr)
landmarks = face_landmark_sets(img_rgb, boxes)[0]

CANONICAL = {
    'w': 1000,
    'h': 1500,
    'axis': 500,
    'leftEye': [305, 550],
    'rightEye': [695, 550],
    'mouth': [500, 800]
}

def centroid(pts, indices):
    group = [pts[i] for i in range(indices[0], indices[1])]
    return np.mean(group, axis=0)

src_pts = np.float32([CANONICAL['leftEye'], CANONICAL['rightEye'], CANONICAL['mouth']])
dst_pts = np.float32([
    centroid(landmarks, (33, 43)),
    centroid(landmarks, (87, 97)),
    centroid(landmarks, (52, 62))
])
M_global = cv2.getAffineTransform(src_pts, dst_pts)

def render_layer_clean(base_canvas, tex_path, rect, flip, opacity, blend_mode="source-over"):
    full_path = '/Users/nguyenletruong/lumi_portrait_standalone' + tex_path
    if not os.path.exists(full_path):
        return
    tex = Image.open(full_path).convert('RGBA')
    rx, ry, rw, rh = rect
    tex_resized = tex.resize((rw, rh), Image.Resampling.LANCZOS)
    if flip:
        tex_resized = ImageOps.mirror(tex_resized)
    
    stage = Image.new('RGBA', (1000, 1500), (0, 0, 0, 0))
    stage.paste(tex_resized, (rx, ry), tex_resized)
    stage_np = np.array(stage)

    # Warp into offscreen buffer first (source-over)
    warped = cv2.warpAffine(stage_np, M_global, (w_img, h_img), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    warped_rgba = warped.astype(float)
    alpha = (warped_rgba[:, :, 3] / 255.0) * (opacity / 100.0)

    if blend_mode == "multiply":
        for c in range(3):
            base_canvas[:, :, c] = base_canvas[:, :, c] * (1.0 - alpha) + (base_canvas[:, :, c] * warped_rgba[:, :, c] / 255.0) * alpha
    elif blend_mode == "soft-light":
        for c in range(3):
            d = base_canvas[:, :, c] / 255.0
            s = warped_rgba[:, :, c] / 255.0
            blended = (1.0 - 2.0 * s) * (d ** 2) + 2.0 * s * d
            base_canvas[:, :, c] = (base_canvas[:, :, c] * (1.0 - alpha) + (blended * 255.0) * alpha)
    else:
        for c in range(3):
            base_canvas[:, :, c] = base_canvas[:, :, c] * (1.0 - alpha) + warped_rgba[:, :, c] * alpha

canvas_rgb = img_rgb.copy().astype(float)

# Preset "Nhẹ" (Set 19) Eye Layers with clean native colors & soft blending:
# 1. Eyeshadow (luoxing - Native Peach-Pink Colors, NO muddy brown tint)
render_layer_clean(canvas_rgb, '/assets/makeup/tex/c9bf616ccc88191c.png', [194, 398, 300, 300], False, 45, blend_mode="multiply")
render_layer_clean(canvas_rgb, '/assets/makeup/tex/c9bf616ccc88191c.png', [516, 398, 300, 300], False, 25, blend_mode="multiply")

# 2. Eyesocket (eyesocketrichang - Soft light crease)
render_layer_clean(canvas_rgb, '/assets/makeup/tex/a90cf2538c7922e8.png', [274, 564, 163, 75], False, 25, blend_mode="soft-light")
render_layer_clean(canvas_rgb, '/assets/makeup/tex/4ce5eb9bcf7b3bc3.png', [575, 552, 163, 75], False, 25, blend_mode="soft-light")

# 3. Eyebrow (biaozhunmei)
render_layer_clean(canvas_rgb, '/assets/makeup/tex/1779e9770b6e6bd9m.png', [217, 427, 257, 97], False, 35, blend_mode="soft-light")
render_layer_clean(canvas_rgb, '/assets/makeup/tex/1779e9770b6e6bd9m.png', [536, 427, 257, 97], False, 35, blend_mode="soft-light")

# Crop Eye Region (Zoom 3X for crystal clear inspection)
y1, y2, x1, x2 = 370, 470, 430, 590
crop_raw = img_rgb[y1:y2, x1:x2]
crop_fixed = np.clip(canvas_rgb[y1:y2, x1:x2], 0, 255).astype(np.uint8)

scale_factor = 3
w_scaled = (x2 - x1) * scale_factor
h_scaled = (y2 - y1) * scale_factor

pil_raw = Image.fromarray(crop_raw).resize((w_scaled, h_scaled), Image.Resampling.LANCZOS)
pil_fixed = Image.fromarray(crop_fixed).resize((w_scaled, h_scaled), Image.Resampling.LANCZOS)

combined = Image.new('RGB', (w_scaled * 2 + 20, h_scaled), (245, 245, 245))
combined.paste(pil_raw, (0, 0))
combined.paste(pil_fixed, (w_scaled + 20, 0))

out_dir = '/Users/nguyenletruong/.gemini/antigravity/brain/f64627a2-78e1-4c0d-97b2-905392fb9354'
out_path = os.path.join(out_dir, 'fixed_nhe_eye_verification.png')
combined.save(out_path, quality=95)
print('Saved fixed eye verification to:', out_path)
