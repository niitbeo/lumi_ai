import cv2
import numpy as np
import onnxruntime as ort
import os

class EyeSegmenter:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            model_path = os.path.join(os.path.dirname(__file__), '../models/independent/eye_segment.onnx')
            if os.path.exists(model_path):
                cls._instance = cls(model_path)
            else:
                return None
        return cls._instance

    def __init__(self, model_path):
        self.session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name
        
    def _crop_eye(self, img, pts, is_left):
        pt_in = pts[35] if is_left else pts[89]
        pt_out = pts[39] if is_left else pts[93]
        
        eye_w = np.linalg.norm(pt_out - pt_in)
        cx = (pt_in[0] + pt_out[0]) / 2.0
        cy = (pt_in[1] + pt_out[1]) / 2.0
        
        # Empirical crop size for 64x128 eye_segment model
        half_w = eye_w * 1.2
        half_h = half_w * 0.5
        
        src_pts = np.float32([
            [cx - half_w, cy - half_h],
            [cx + half_w, cy - half_h],
            [cx - half_w, cy + half_h]
        ])
        dst_pts = np.float32([
            [0, 0],
            [128, 0],
            [0, 64]
        ])
        M = cv2.getAffineTransform(src_pts, dst_pts)
        M_inv = cv2.getAffineTransform(dst_pts, src_pts)
        
        crop = cv2.warpAffine(img, M, (128, 64))
        return crop, M_inv

    def segment(self, img, pts, is_left):
        crop, M_inv = self._crop_eye(img, pts, is_left)
        
        input_tensor = crop.astype(np.float32) / 255.0
        input_tensor = np.expand_dims(np.transpose(input_tensor, (2, 0, 1)), axis=0)
        
        out = self.session.run(None, {self.input_name: input_tensor})[0][0]
        
        # Output is (3, 64, 128)
        # Channel 0 is the eyeball; its top edge is the true lash line
        mask = out[0]
        mask_bin = (mask > 0.3).astype(np.uint8) * 255
        
        # Extract the upper edge of the mask at every column to form a dense curve
        curve_pts = []
        for x in range(0, 128, 2):
            col = mask_bin[:, x]
            y_indices = np.where(col > 0)[0]
            if len(y_indices) > 0:
                y = y_indices[0]
                curve_pts.append([float(x), float(y)])
                
        if len(curve_pts) == 0:
            return []
            
        curve_pts = np.array(curve_pts, dtype=np.float32)
        curve_pts_pad = np.column_stack((curve_pts, np.ones(len(curve_pts))))
        orig_pts = np.dot(M_inv, curve_pts_pad.T).T
        
        return orig_pts.tolist()
