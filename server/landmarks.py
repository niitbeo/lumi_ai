import cv2
import MNN
import numpy as np
import math

INPUT_SIZE = 192

class LandmarkDetector:
    def __init__(self, model_path):
        self.interpreter = MNN.Interpreter(str(model_path))
        self.session = self.interpreter.createSession({"backend": "CPU"})

    def detect(self, bgr_image, face_box, keypoints=None, pad=0.0):
        # Fallback to face_box if no keypoints
        if keypoints is None or len(keypoints) < 5:
            height, width = bgr_image.shape[:2]
            x1, y1, x2, y2 = face_box
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            side = max(x2 - x1, y2 - y1) * (1 + pad)
            angle = 0.0
        else:
            kp = np.array(keypoints, dtype=np.float32)
            left_eye = kp[0]
            right_eye = kp[1]
            eye_dist = np.linalg.norm(right_eye - left_eye)
            
            # The ideal crop Lp.onnx was trained on is perfectly centered 
            # on the geometric mean of the 5 keypoints, shifted slightly up.
            cx = np.mean(kp[:, 0])
            cy = np.mean(kp[:, 1]) - 0.25 * eye_dist
            side = 3.0 * eye_dist * (1 + pad)
            
            angle = math.degrees(math.atan2(right_eye[1] - left_eye[1], right_eye[0] - left_eye[0]))
            
        M = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
        M[0, 2] += (side / 2) - cx
        M[1, 2] += (side / 2) - cy
        
        crop = cv2.warpAffine(bgr_image, M, (int(side), int(side)), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0,0,0))
        if crop.size == 0:
            return None
            
        resized = cv2.resize(crop, (INPUT_SIZE, INPUT_SIZE))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32)
        chw = np.transpose(rgb, (2, 0, 1))[None].copy()

        tensor = self.interpreter.getSessionInputAll(self.session)["data"]
        tensor.copyFrom(MNN.Tensor((1, 3, INPUT_SIZE, INPUT_SIZE), MNN.Halide_Type_Float, chw, MNN.Tensor_DimensionType_Caffe))
        self.interpreter.runSession(self.session)

        out = self.interpreter.getSessionOutputAll(self.session)["fc1"]
        host = MNN.Tensor((1, 212), MNN.Halide_Type_Float, np.zeros((1, 212), np.float32), MNN.Tensor_DimensionType_Caffe)
        out.copyToHostTensor(host)
        raw = np.array(host.getData()).reshape(106, 2)

        crop_w, crop_h = int(side), int(side)
        crop_pts = np.stack([
            (raw[:, 0] + 1) / 2 * crop_w,
            (raw[:, 1] + 1) / 2 * crop_h,
        ], axis=1)
        
        M_inv = cv2.invertAffineTransform(M)
        points = cv2.transform(np.array([crop_pts]), M_inv)[0]
        return points

    @staticmethod
    def polygon_mask(shape, points, indices, dilate=0):
        mask = np.zeros(shape[:2], dtype=np.uint8)
        poly = np.array([points[indices]], dtype=np.int32)
        cv2.fillPoly(mask, poly, 255)
        if dilate > 0:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate*2+1, dilate*2+1))
            mask = cv2.dilate(mask, kernel)
        return mask

GROUPS = {
    "left_eye": list(range(33, 43)),
    "right_eye": list(range(87, 97)),
    "left_brow": list(range(43, 52)),
    "right_brow": list(range(97, 106)),
    "nose": list(range(72, 87)),
    "mouth_outer": list(range(52, 64)),
    "mouth_inner": list(range(64, 72)),
    "contour": list(range(0, 33)),
}
