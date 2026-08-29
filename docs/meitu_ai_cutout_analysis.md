# Phân Tích Kỹ Thuật Nhóm Mô Hình AI Tách Nền & Cắt Ảnh (AI Cutout & Matting) Của Cubeo

Tính năng tách nền, cắt ảnh chân dung (AI Cutout / Matting) của Cubeo (MagiMir) hoạt động hoàn toàn cục bộ (**Offline 100%**) thông qua nhân C++ native `magpie.node` kết hợp cùng các mô hình AI phân tách sâu đã giải mã.

Dưới đây là tài liệu phân tích kỹ thuật chi tiết về cấu trúc mô hình, mã nguồn JS gọi cầu nối C++ và cách trích xuất ảnh trong suốt (RGBA).

---

## 1. Bản Đồ Mô Hình & Khóa Giải Mã (Model & Decryption Keys)

Các tính năng tách nền trong menu **AI Cutout** được chia làm 6 mô hình chuyên biệt:

| Tính Năng Cutout | File Đĩa Cứng | Tên Model Trong DB | Khóa Giải Mã AES (Base64 URL-safe) | File ONNX/MNN Giải Mã |
| :--- | :--- | :--- | :--- | :--- |
| **Tách Nền Người (Human Matting)** | `Thmscv1.lib` | `humanMattingTone` | `t5YqRHVIgsv3rP1yZGbKiJ40ZdOQMKoeP6dsA8Cj79i=` | `Thmscv1.onnx` (~9.0 MB) |
| **Tách Đầu Chân Dung (Head Matting)** | `Het.lib` | `head_matting` | `8aHg8wNknc5FjbcPY30MSUPcFkl3s2FcW6mrUyf4ARU=` | `Het.onnx` (~35.7 MB) |
| **Tách Tóc Chi Tiết (Hair Matting)** | `F2sch1b.lib` | `UCAHairBase` | `a5m9_Ilfm_Ilf2wyBts03ts03vNvwTaTiSi7UyrPz5c=` | `F2sch1b.onnx` (~13.2 MB) |
| **Phân Tách Đồ Mặc (Human Parsing)** | `ChpsJy.lib` | `human_parse` | `hN5Cj9p4CfrMtiwdkK_Mtf71Bf_aL551U6mrCyrPztQ=` | `ChpsJy.onnx` (~41.9 MB) |
| **Tách Từng Cá Nhân (Instance Seg)** | `HisJ.lib` | `human_instance` | `t-yKj4CfyN_uCfrMAZ6LAUPcDkl3f6urW8mrUyrP38g=` | `HisJ.onnx` (~40.4 MB) |
| **Phân Loại Cảnh Vật (Semantic Seg)** | `CssJy.lib` | `semantic_segmentation` | `hN5Cj9p4CfrMtiwdkK_Mtf71Bf_aL551U6mrCyrPztQ=` | `CssJy.onnx` (~41.9 MB) |

---

## 2. Phân Tích Luồng Gọi Trong Mã Nguồn JavaScript (`magpie.js`)

Mã nguồn giao diện JavaScript gọi lõi xử lý C++ `magpie.node` để thực hiện tách nền chân dung và lấy về kết quả ảnh PNG có nền trong suốt (`effectPng`):

```javascript
{
  key: "getHumanMattingEffectResult",
  value: function() {
    try {
      // 1. Ghi nhận log khởi động tiến trình tách nền
      mt.info("magpie.getHumanMattingEffectResult start");
      
      # 2. Gọi hàm native từ thư viện C++ magpie.node
      var e = this.magpie.getHumanMattingEffectResult();
      
      # 3. Trích xuất thuộc tính "effectPng" chứa buffer ảnh RGBA trong suốt
      return mt.info("magpie.getHumanMattingEffectResult end", vt({}, ke()(e, "effectPng"))), e;
    } catch (e) {
      throw mt.error("magpie.getHumanMattingEffectResult error", e), e;
    }
  }
}
```

---

## 3. Cơ Chế Xử Lý Dưới Lõi C++ (`magpie.node`)

Khi hàm `getHumanMattingEffectResult` được gọi:
1.  **AI Inference (Chạy suy luận):** Lõi C++ nạp mô hình tách người `Thmscv1.lib` (đã giải mã bằng khóa AES tương ứng) và chạy suy luận trên ảnh nguồn.
2.  **Sinh Alpha Matte:** Đầu ra của mô hình tách nền là một **Alpha Matte** (ma trận 1 kênh màu trắng đen biểu thị độ trong suốt của từng điểm ảnh từ 0 đến 255).
3.  **Tạo Ảnh 4 Kênh (RGBA):** C++ sử dụng thư viện OpenCV để ghép ảnh gốc 3 kênh màu (BGR) với ma trận Alpha Matte (kênh thứ 4) để tạo thành ảnh 4 kênh màu RGBA.
4.  **Mã Hóa PNG:** Ảnh RGBA được nén thành định dạng PNG để giữ kênh alpha trong suốt (`effectPng`), trả ngược buffer nhị phân này lên lớp JavaScript dưới dạng Base64 hoặc Uint8Array.

---

## 4. Mã Nguồn Giả Lập Tách Nền & Tạo Ảnh PNG Trong Suốt (Python)

Quy trình dưới đây mô phỏng cách nạp mô hình `Thmscv1.onnx` bằng MNN, trích xuất ma trận Alpha Matte từ mô hình và ghép với ảnh gốc tạo file PNG trong suốt:

```python
import MNN
import cv2
import numpy as np
import os

MODEL_PATH = r"C:\Users\nltruong\magimir_extracted_windows\decrypted_models\Thmscv1.onnx"
INPUT_IMAGE_PATH = r"C:\Users\nltruong\input_face.jpg"
OUTPUT_PNG_PATH = r"C:\Users\nltruong\scratch\cutout_result.png"

def main():
    if not os.path.exists(MODEL_PATH) or not os.path.exists(INPUT_IMAGE_PATH):
        print("[-] Vui lòng kiểm tra lại đường dẫn file model hoặc ảnh đầu vào!")
        return

    # 1. Đọc ảnh gốc bằng OpenCV
    img = cv2.imread(INPUT_IMAGE_PATH) # Định dạng BGR (3 channels)
    h, w, _ = img.shape

    # 2. Khởi tạo mô hình AI tách nền (MNN)
    interpreter = MNN.Interpreter(MODEL_PATH)
    session = interpreter.createSession()
    inputs = interpreter.getSessionInputAll(session)
    
    # Giả sử mô hình yêu cầu kích thước chuẩn là 512x512
    target_w, target_h = 512, 512
    interpreter.resizeTensor(inputs['input0'], (1, 3, target_h, target_w))
    interpreter.resizeSession(session)

    # 3. Tiền xử lý ảnh nguồn nạp vào model
    img_resized = cv2.resize(img, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
    img_float = img_resized.astype(np.float32) / 255.0  # Chuẩn hóa về [0.0, 1.0]
    img_chw = np.transpose(img_float, (2, 0, 1))        # Chuyển về CHW
    img_tensor = np.expand_dims(img_chw, axis=0)        # Thêm chiều batch

    # Nạp dữ liệu vào input tensor của MNN
    t_in = MNN.Tensor((1, 3, target_h, target_w), MNN.Halide_Type_Float, img_tensor, MNN.Tensor_DimensionType_Caffe)
    inputs['input0'].copyFrom(t_in)

    # 4. Thực thi mô hình AI tách nền
    print("[*] Chạy suy luận mô hình tách nền Thmscv1...")
    interpreter.runSession(session)

    # 5. Trích xuất Alpha Matte (Mặt nạ độ trong suốt)
    outputs = interpreter.getSessionOutputAll(session)
    # Giả sử output đầu tiên là mặt nạ tách người
    output_key = list(outputs.keys())[0]
    out_tensor = outputs[output_key]
    
    # Copy dữ liệu ra Host
    host_tensor = MNN.Tensor(out_tensor.getShape(), out_tensor.getDataType(), MNN.Tensor_DimensionType_Caffe)
    out_tensor.copyToHostTensor(host_tensor)
    alpha_data = host_tensor.getNumpyData() # Shape: (1, 1, 512, 512)

    # 6. Hậu xử lý đưa mặt nạ về kích thước gốc của ảnh ban đầu
    alpha_matte = np.squeeze(alpha_data, axis=0) # Loại bỏ batch -> (1, 512, 512)
    alpha_matte = np.transpose(alpha_matte, (1, 2, 0)) # Chuyển sang HWC -> (512, 512, 1)
    alpha_matte = np.clip(alpha_matte * 255.0, 0, 255).astype(np.uint8)
    
    # Phóng to mask về kích thước gốc của ảnh nguồn ban đầu
    alpha_resized = cv2.resize(alpha_matte, (w, h), interpolation=cv2.INTER_LINEAR)
    if len(alpha_resized.shape) == 2:
        alpha_resized = np.expand_dims(alpha_resized, axis=2)

    # 7. Ghép ảnh gốc BGR với Alpha Matte thành ảnh 4 kênh màu RGBA
    # Tách các kênh màu của ảnh gốc
    b, g, r = cv2.split(img)
    # Ghép 4 kênh: B + G + R + Alpha -> tạo ảnh PNG trong suốt
    rgba_image = cv2.merge([b, g, r, alpha_resized])

    # 8. Ghi file PNG kết quả xuống đĩa
    cv2.imwrite(OUTPUT_PNG_PATH, rgba_image)
    print(f"[+] Tách nền thành công! Ảnh trong suốt lưu tại: {OUTPUT_PNG_PATH}")

if __name__ == "__main__":
    main()
```
