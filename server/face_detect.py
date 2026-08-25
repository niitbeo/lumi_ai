"""
Face detection with the app's own Fd.onnx (MNN FlatBuffer despite the suffix).

Reverse-engineered contract, verified by drawing the result over a photo:
  input   'input.1'  (1,3,S,S), RGB, (x - 127.5) / 128
  outputs three scales at strides 8 / 16 / 32, two anchors per cell, each
          (N,1) score  ·  (N,4) box  ·  (N,10) five keypoints

The box and keypoint heads are anchor-free and regress *distances in stride
units* from the cell centre — not RetinaFace-style deltas (all values come out
positive, and decoding them as deltas puts the box off-image). So:
    x1 = cx - l*stride     y1 = cy - t*stride
    x2 = cx + r*stride     y2 = cy + b*stride
    kp = (cx + dx*stride, cy + dy*stride)

Verified on test_face.jpg: box hugs the face and the five keypoints land on
left eye, right eye, nose tip, and both mouth corners.
"""

import numpy as np
import cv2
import MNN

INPUT_SIZE = 320
# (score, box, keypoint) output names per scale, with the scale's stride.
_HEADS = [("448", "451", "454", 8), ("471", "474", "477", 16), ("494", "497", "500", 32)]


class FaceDetector:
    def __init__(self, model_path):
        self.interpreter = MNN.Interpreter(str(model_path))
        self.session = self.interpreter.createSession({"backend": "CPU"})
        tensor = self.interpreter.getSessionInputAll(self.session)["input.1"]
        self.interpreter.resizeTensor(tensor, (1, 3, INPUT_SIZE, INPUT_SIZE))
        self.interpreter.resizeSession(self.session)

    def _forward(self, bgr_image):
        resized = cv2.resize(bgr_image, (INPUT_SIZE, INPUT_SIZE))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32)
        chw = np.transpose((rgb - 127.5) / 128.0, (2, 0, 1))[None].copy()

        tensor = self.interpreter.getSessionInputAll(self.session)["input.1"]
        tensor.copyFrom(
            MNN.Tensor((1, 3, INPUT_SIZE, INPUT_SIZE), MNN.Halide_Type_Float, chw,
                       MNN.Tensor_DimensionType_Caffe)
        )
        self.interpreter.runSession(self.session)

        out = {}
        for name, tensor in self.interpreter.getSessionOutputAll(self.session).items():
            shape = tuple(tensor.getShape())
            host = MNN.Tensor(shape, MNN.Halide_Type_Float,
                              np.zeros(shape, np.float32), MNN.Tensor_DimensionType_Caffe)
            tensor.copyToHostTensor(host)
            out[name] = np.array(host.getData()).reshape(shape)
        return out

    def detect(self, bgr_image, threshold=0.5, max_faces=10):
        """Returns faces sorted by score, in ORIGINAL image pixel coordinates."""
        height, width = bgr_image.shape[:2]
        scale_x, scale_y = width / INPUT_SIZE, height / INPUT_SIZE
        raw = self._forward(bgr_image)

        boxes, scores, keypoints = [], [], []
        for score_name, box_name, kp_name, stride in _HEADS:
            head_scores = raw[score_name][:, 0]
            head_boxes = raw[box_name]
            head_kps = raw[kp_name]
            grid = INPUT_SIZE // stride

            for i in np.where(head_scores >= threshold)[0]:
                cell = i // 2
                cx = (cell % grid + 0.5) * stride
                cy = (cell // grid + 0.5) * stride
                left, top, right, bottom = head_boxes[i]
                boxes.append([
                    (cx - left * stride) * scale_x, (cy - top * stride) * scale_y,
                    (cx + right * stride) * scale_x, (cy + bottom * stride) * scale_y,
                ])
                scores.append(float(head_scores[i]))
                keypoints.append([
                    [(cx + head_kps[i][k * 2] * stride) * scale_x,
                     (cy + head_kps[i][k * 2 + 1] * stride) * scale_y]
                    for k in range(5)
                ])

        if not boxes:
            return []

        keep = _nms(np.array(boxes, np.float32), np.array(scores, np.float32), 0.35)[:max_faces]
        return [
            {
                "box": [float(v) for v in boxes[i]],
                "score": scores[i],
                # left eye, right eye, nose, left mouth corner, right mouth corner
                "keypoints": [[float(x), float(y)] for x, y in keypoints[i]],
            }
            for i in keep
        ]


def _nms(boxes, scores, iou_threshold):
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-9)
        order = order[1:][iou <= iou_threshold]
    return keep
