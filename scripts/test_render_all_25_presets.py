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
    return np.mean([pts[i] for i in range(indices[0], indices[1])], axis=0)

src_pts = np.float32([CANONICAL['leftEye'], CANONICAL['rightEye'], CANONICAL['mouth']])
dst_pts = np.float32([
    centroid(landmarks, (33, 43)),
    centroid(landmarks, (87, 97)),
    centroid(landmarks, (52, 62))
])
M_global = cv2.getAffineTransform(src_pts, dst_pts)

data = json.load(open('/Users/nguyenletruong/lumi_portrait_standalone/assets/makeup/makeup.json'))
parts_map = {p['key']: {m['dir']: m for m in p['materials']} for p in data['parts']}

def render_preset(theme):
    canvas = img_rgb.copy().astype(float)
    theme_alpha = theme.get('alpha', 70) / 100.0

    for pick in theme['parts']:
        key = pick['key']
        mat_dir = pick['material']
        if key not in parts_map or mat_dir not in parts_map[key]:
            continue
        mat = parts_map[key][mat_dir]
        mat_alpha = mat.get('alpha', 70) / 100.0

        for layer in mat.get('layers', []):
            tex_path = '/Users/nguyenletruong/lumi_portrait_standalone' + layer['tex']
            if not os.path.exists(tex_path):
                continue
            tex = Image.open(tex_path).convert('RGBA')
            rx, ry, rw, rh = layer['rect']
            tex_resized = tex.resize((rw, rh), Image.Resampling.LANCZOS)
            if layer.get('flip', False):
                tex_resized = ImageOps.mirror(tex_resized)

            stage = Image.new('RGBA', (1000, 1500), (0, 0, 0, 0))
            stage.paste(tex_resized, (rx, ry), tex_resized)

            # Tint if needed
            tint = None
            if pick.get('color'):
                try:
                    c_parts = [int(v) for v in pick['color'].split(';')]
                    if len(c_parts) >= 3 and any(v > 0 for v in c_parts[:3]):
                        tint = c_parts[:3]
                except Exception:
                    pass
            elif key == 'eyebrow':
                tint = layer.get('tint', [72, 54, 42])
            elif key == 'blush':
                tint = layer.get('tint', [255, 178, 179])

            if tint is not None:
                stage_np = np.array(stage)
                alpha_mask = stage_np[:, :, 3] > 0
                stage_np[alpha_mask, 0] = tint[0]
                stage_np[alpha_mask, 1] = tint[1]
                stage_np[alpha_mask, 2] = tint[2]
                stage = Image.fromarray(stage_np)

            stage_np = np.array(stage)
            warped = cv2.warpAffine(stage_np, M_global, (w_img, h_img), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
            warped_rgba = warped.astype(float)

            layer_opacity = layer.get('opacity', 100) / 100.0
            part_alpha = layer.get('partAlpha', 100) / 100.0
            effective_alpha = (warped_rgba[:, :, 3] / 255.0) * theme_alpha * mat_alpha * layer_opacity * part_alpha

            blend = layer.get('blend', 'source-over')
            if key == 'eyeshadow':
                blend = 'soft-light'

            if blend == 'multiply':
                for c in range(3):
                    canvas[:, :, c] = canvas[:, :, c] * (1.0 - effective_alpha) + (canvas[:, :, c] * warped_rgba[:, :, c] / 255.0) * effective_alpha
            elif blend == 'soft-light':
                for c in range(3):
                    d = canvas[:, :, c] / 255.0
                    s = warped_rgba[:, :, c] / 255.0
                    blended = (1.0 - 2.0 * s) * (d ** 2) + 2.0 * s * d
                    canvas[:, :, c] = (canvas[:, :, c] * (1.0 - effective_alpha) + (blended * 255.0) * effective_alpha)
            else:
                for c in range(3):
                    canvas[:, :, c] = canvas[:, :, c] * (1.0 - effective_alpha) + warped_rgba[:, :, c] * effective_alpha

    return np.clip(canvas, 0, 255).astype(np.uint8)

# Test render all 25 presets
out_dir = '/Users/nguyenletruong/.gemini/antigravity/brain/f64627a2-78e1-4c0d-97b2-905392fb9354/all_25_presets_test'
os.makedirs(out_dir, exist_ok=True)

success_count = 0
for idx, theme in enumerate(data.get('themes', [])):
    try:
        res = render_preset(theme)
        out_file = os.path.join(out_dir, f"theme_{theme['id']:02d}_{theme['name']}.jpg")
        Image.fromarray(res).save(out_file, quality=90)
        success_count += 1
        print(f"[{idx+1:2d}/25] Rendered Theme {theme['id']:2d} - {theme['name']}")
    except Exception as e:
        print(f"[{idx+1:2d}/25] Error rendering Theme {theme['id']}: {e}")

print(f"\nSuccessfully rendered {success_count}/25 presets to {out_dir}")
