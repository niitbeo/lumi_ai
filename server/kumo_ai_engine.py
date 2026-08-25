import os
import cv2
import numpy as np

# Try to import MNN
try:
    import MNN
    HAS_MNN = True
except ImportError:
    HAS_MNN = False

class KumoAIToneEngine:
    def __init__(self, models_dir):
        self.models_dir = models_dir
        self.feat_interp = None
        self.sess_feat = None
        self.sub_models = {}
        self.is_loaded = False
        
        # Mappings from JSON param key to model index (0-12)
        # Note: 08 is vibrance, 09 is saturation, 10 is clarity, 11 is dehaze
        self.param_map = {
            'exposure': 0,
            'constrast': 1,      # typo in JSON
            'contrast': 1,
            'highlight': 2,
            'shadow': 3,
            'whiteness': 4,
            'blackness': 5,
            'temperature': 6,
            'tint': 7,
            'vibrance': 8,
            'saturability': 9,   # JSON key
            'saturation': 9,
            'clarity': 10,
            'dehaze': 11,
            'deHaze': 11,
            # 12 could be AWB or sharpen, usually skipped in standard presets unless specified
        }

    def load_models(self):
        if not HAS_MNN:
            print("[KumoAIToneEngine] MNN not installed, AI Tone disabled.")
            return False
            
        feat_path = os.path.join(self.models_dir, "Tcv5s.onnx")
        if not os.path.exists(feat_path):
            print(f"[KumoAIToneEngine] Feature extractor not found: {feat_path}")
            return False
            
        try:
            self.feat_interp = MNN.Interpreter(feat_path)
            self.sess_feat = self.feat_interp.createSession()
        except Exception as e:
            print(f"[KumoAIToneEngine] Error loading Tcv5s.onnx: {e}")
            return False

        for i in range(13):
            m_path = os.path.join(self.models_dir, f"Tcv5s{i:02d}.onnx")
            if os.path.exists(m_path):
                try:
                    interp = MNN.Interpreter(m_path)
                    sess = interp.createSession()
                    self.sub_models[i] = (interp, sess)
                except Exception as e:
                    print(f"[KumoAIToneEngine] Error loading Tcv5s{i:02d}.onnx: {e}")
                    
        self.is_loaded = True
        return True

    def process_tone(self, img_f: np.ndarray, params: dict, amount: float = 1.0) -> np.ndarray:
        """
        img_f: float32 [H, W, 3] RGB image (0..1)
        params: dict of preset parameters
        amount: strength 0..1
        """
        if not self.is_loaded:
            return img_f

        # Extract sliders that have corresponding AI models
        active_sliders = {}
        for k, v in params.items():
            if k in self.param_map:
                idx = self.param_map[k]
                val = float(v) * amount
                if abs(val) > 1e-4:
                    # Accumulate if multiple keys map to same idx (e.g. constrast/contrast)
                    active_sliders[idx] = active_sliders.get(idx, 0.0) + val

        if not active_sliders:
            return img_f

        H, W = img_f.shape[:2]
        
        # Inference resolution: Kumo typically uses 512x512 for Tone PS to balance speed and spatial context
        infer_h, infer_w = 512, 512
        img_rs = cv2.resize(img_f, (infer_w, infer_h), interpolation=cv2.INTER_LINEAR)
        img_nchw = np.transpose(img_rs, (2, 0, 1))[np.newaxis, ...]

        # 1. Run Feature Extractor
        input_t = self.feat_interp.getSessionInput(self.sess_feat, "input0")
        self.feat_interp.resizeTensor(input_t, (1, 3, infer_h, infer_w))
        self.feat_interp.resizeSession(self.sess_feat)
        
        tmp_in = MNN.Tensor((1, 3, infer_h, infer_w), MNN.Halide_Type_Float, img_nchw, MNN.Tensor_DimensionType_Caffe)
        input_t.copyFrom(tmp_in)
        self.feat_interp.runSession(self.sess_feat)
        
        # In Kumo, output1 is the primary high-response feature map for sliders
        out_t = self.feat_interp.getSessionOutput(self.sess_feat, "output1")
        out_host = MNN.Tensor((1, 16, infer_h, infer_w), MNN.Halide_Type_Float, np.zeros((1, 16, infer_h, infer_w), dtype=np.float32), MNN.Tensor_DimensionType_Caffe)
        out_t.copyToHostTensor(out_host)
        feat1 = np.array(out_host.getData(), dtype=np.float32).reshape(1, 16, infer_h, infer_w)

        # 2. Accumulate Deltas
        total_delta = np.zeros((infer_h, infer_w, 3), dtype=np.float32)
        
        for idx, val in active_sliders.items():
            if idx not in self.sub_models:
                continue
            interp, sess = self.sub_models[idx]
            
            in_t = interp.getSessionInput(sess, "input0")
            interp.resizeTensor(in_t, (1, 16, infer_h, infer_w))
            interp.resizeSession(sess)
            
            tmp_feat = MNN.Tensor((1, 16, infer_h, infer_w), MNN.Halide_Type_Float, feat1, MNN.Tensor_DimensionType_Caffe)
            in_t.copyFrom(tmp_feat)
            interp.runSession(sess)
            
            res_t = interp.getSessionOutput(sess, "output0")
            res_host = MNN.Tensor((1, 3, infer_h, infer_w), MNN.Halide_Type_Float, np.zeros((1, 3, infer_h, infer_w), dtype=np.float32), MNN.Tensor_DimensionType_Caffe)
            res_t.copyToHostTensor(res_host)
            
            delta_nchw = np.array(res_host.getData(), dtype=np.float32).reshape(1, 3, infer_h, infer_w)
            delta_hwc = np.transpose(delta_nchw[0], (1, 2, 0)) # H, W, 3
            
            # The models output the +100 delta, so we multiply by (slider / 100)
            total_delta += delta_hwc * (val / 100.0)

        # 3. Upscale delta back to original resolution and apply
        if (H, W) != (infer_h, infer_w):
            total_delta = cv2.resize(total_delta, (W, H), interpolation=cv2.INTER_LINEAR)
            
        final_img = img_f + total_delta
        return np.clip(final_img, 0.0, 1.0)

# Global singleton
_KUMO_ENGINE = None

def get_kumo_ai_engine():
    global _KUMO_ENGINE
    if _KUMO_ENGINE is None:
        # Hardcoded to Kumo's decrypted models directory as discovered
        models_dir = "/Users/nguyenletruong/cubeo-ai/decrypted_models"
        _KUMO_ENGINE = KumoAIToneEngine(models_dir)
        _KUMO_ENGINE.load_models()
    return _KUMO_ENGINE
