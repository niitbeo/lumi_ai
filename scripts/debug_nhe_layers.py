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

def render_layer(base_canvas, tex_path, rect, flip, opacity, blend_mode="source-over", tint=None):
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

    if tint is not None:
        r, g, b = tint
        stage_np = np.array(stage)
        alpha_mask = stage_np[:, :, 3] > 0
        stage_np[alpha_mask, 0] = r
        stage_np[alpha_mask, 1] = g
        stage_np[alpha_mask, 2] = b
        stage = Image.fromarray(stage_np)

    stage_np = np.array(stage)
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

def get_left_eye_crop(canvas):
    # Left eye box (Viewer Left): Y ~ 380..460, X ~ 430..510
    crop = np.clip(canvas[380:460, 430:510], 0, 255).astype(np.uint8)
    return Image.fromarray(crop).resize((240, 240), Image.Resampling.LANCZOS)

crops = []
labels = []

# 0. Raw Base
c0 = img_rgb.copy().astype(float)
crops.append(get_left_eye_crop(c0))
labels.append("Raw")

# 1. Eyebrow only
c1 = img_rgb.copy().astype(float)
render_layer(c1, '/assets/makeup/tex/1779e9770b6e6bd9m.png', [217, 427, 257, 97], False, 27, blend_mode="soft-light")
crops.append(get_left_eye_crop(c1))
labels.append("Eyebrow")

# 2. Eyeshadow only (luoxing)
c2 = img_rgb.copy().astype(float)
render_layer(c2, '/assets/makeup/tex/c9bf616ccc88191c.png', [194, 398, 300, 300], False, 49, blend_mode="multiply")
crops.append(get_left_eye_crop(c2))
labels.append("Eyeshadow")

# 3. Eyesocket only (eyesocketrichang)
c3 = img_rgb.copy().astype(float)
render_layer(c3, '/assets/makeup/tex/a90cf2538c7922e8.png', [274, 564, 163, 75], False, 25.5, blend_mode="soft-light")
render_layer(c3, '/assets/makeup/tex/37b9451f2cbaed10.png', [276, 551, 166, 87], False, 49, blend_mode="soft-light")
crops.append(get_left_eye_crop(c3))
labels.append("Eyesocket")

# 4. Feature only (featurerichang)
c4 = img_rgb.copy().astype(float)
render_layer(c4, '/assets/makeup/tex/5321f7de36cfe7e8.png', [0, 45, 1000, 1210], False, 35, blend_mode="soft-light")
crops.append(get_left_eye_crop(c4))
labels.append("Feature")

# 5. All Together
c5 = img_rgb.copy().astype(float)
render_layer(c5, '/assets/makeup/tex/1779e9770b6e6bd9m.png', [217, 427, 257, 97], False, 27, blend_mode="soft-light")
render_layer(c5, '/assets/makeup/tex/c9bf616ccc88191c.png', [194, 398, 300, 300], False, 49, blend_mode="multiply")
render_layer(c5, '/assets/makeup/tex/a90cf2538c7922e8.png', [274, 564, 163, 75], False, 25.5, blend_mode="soft-light")
render_layer(c5, '/assets/makeup/tex/37b9451f2cbaed10.png', [276, 551, 166, 87], False, 49, blend_mode="soft-light")
render_layer(c5, '/assets/makeup/tex/5321f7de36cfe7e8.png', [0, 45, 1000, 1210], False, 35, blend_mode="soft-light")
crops.append(get_left_eye_crop(c5))
labels.append("All Combined")

# Combine horizontally into a strip
total_w = 240 * len(crops) + 10 * (len(crops) - 1)
strip = Image.new('RGB', (total_w, 240), (240, 240, 240))
for i, crop in enumerate(crops):
    strip.paste(crop, (i * 250, 0))

out_dir = '/Users/nguyenletruong/.gemini/antigravity/brain/f64627a2-78e1-4c0d-97b2-905392fb9354'
out_path = os.path.join(out_dir, 'isolated_layers_strip.png')
strip.save(out_path)
print('Saved isolated layers strip to:', out_path)
