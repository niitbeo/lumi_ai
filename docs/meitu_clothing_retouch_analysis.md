# Phân Tích Kỹ Thuật Tính Năng Làm Đẹp Áo Quần (AI Clothing Retouch) Của Cubeo

Tính năng làm đẹp áo quần (AI Clothing Retouch) giúp tự động ủi phẳng quần áo (xóa nếp nhăn) và làm sạch bụi bẩn, chỉ thừa trên vest, váy cưới. Tính năng này được thực thi hoàn toàn cục bộ (**Offline 100%**) thông qua các biến cấu hình `clothingSmoothnessDegree` và `inpaintClotheDegree`.

Dưới đây là tài liệu phân tích kỹ thuật chi tiết về cấu trúc mô hình, mã nguồn và giải pháp giả lập quy trình.

---

## 1. Cấu Trúc Các Mô Hình AI Chạy Cục Bộ

Tính năng này được chia thành 2 tác vụ chỉnh sửa chính sử dụng mô hình học sâu chuyên biệt:

### A. Làm Phẳng Quần Áo (`clothingSmoothnessDegree` / `clotheFlatten`)
*   **Mô hình chịu trách nhiệm:** `Dlwh03B.lib` (Sau giải mã là `Dlwh03B.onnx` ~15.3 MB).
*   **Khóa giải mã AES-256-CTR:** `1bX-o-yS901C9wyeaItEbe51EnBfEnCpd7PS2SQ3zuY=`
*   **Cơ chế hoạt động:** 
    *   Mô hình không cố gắng vẽ lại một tấm ảnh mới (vì sẽ làm mất vân vải tự nhiên). Thay vào đó, nó nhận đầu vào là ảnh gốc `input0` có kích thước `(1, 3, H, W)` và dự đoán ra một **Mạng lưới dịch chuyển pixel (Deformation Grid / Pixel Displacement Field)** có kích thước **`(1, 2, H/4, W/4)`**.
    *   **2 Kênh đầu ra** biểu thị vectơ dịch chuyển $(\text{dx}, \text{dy})$ của lưới điểm ảnh.
    *   Lõi C++ sẽ phóng to lưới này về kích thước gốc và thực hiện thuật toán **Warp/Remap** (sử dụng OpenCV hoặc Shader) để kéo dãn các nếp nhăn một cách vật lý, giữ lại độ sắc nét 100% của kết cấu vải.

### B. Làm Sạch Tì Vết Áo Quần (`inpaintClotheDegree` / `clotheInpaint`)
*   **Mô hình phân tách trợ lực:** `ChpsJy.lib` (`human_parse` / `ChpsJy.onnx` ~41.9 MB).
*   **Khóa giải mã AES-256-CTR:** `hN5Cj9p4CfrMtiwdkK_Mtf71Bf_aL551U6mrCyrPztQ=`
*   **Cơ chế hoạt động:**
    1.  **Bước 1 (Phân tách):** Chạy mô hình `human_parse` (`ChpsJy.onnx`) để cô lập vùng trang phục (nhận diện áo vest, sơ mi, váy, quần). Việc này ngăn chặn thuật toán làm sạch can thiệp nhầm vào vùng da, tóc của chủ thể.
    2.  **Bước 2 (Làm sạch):** Trên vùng mặt nạ quần áo đã chọn, lõi C++ áp dụng bộ lọc khử nhiễu tần số cao (High-frequency Filtering) kết hợp thuật toán inpainting cục bộ để tự động tẩy sạch các chi tiết rác nhỏ như vết bẩn, sợi chỉ thừa hay bụi bám trên vải.

---

## 2. Bản Đồ Giao Diện & IPC (React JS Code)

Trong mã nguồn JS (tệp `renderer.js` / `157.js`), các biến thanh trượt lưu trữ các giá trị chỉnh sửa gửi xuống C++:

```javascript
// Các giá trị lưu trữ trong simpleMagicValues gửi qua IPC xuống lõi AI
simpleMagicValues = {
  clothingSmoothnessDegree: 50, // Cường độ làm phẳng quần áo (0 - 100)
  inpaintClotheDegree: 30       // Cường độ làm sạch vải (0 - 100)
}
```

Tiến trình Native Bridge sẽ gọi hàm C++ thông qua tệp tin `magpie.node`:
```javascript
magpie.processEffectAsync(config);
```

---

## 3. Chương Trình Chạy Giả Lập Làm Phẳng Áo Quần (Python & OpenCV)

Quy trình dưới đây mô phỏng cách nạp mô hình mạng `Dlwh03B.onnx`, trích xuất mạng lưới dịch chuyển 2 kênh màu $(\text{dx}, \text{dy})$ và sử dụng hàm `cv2.remap` để ủi phẳng ảnh:

```python
import MNN
import cv2
import numpy as np
import os

MODEL_PATH = r"C:\Users\nltruong\magimir_extracted_windows\decrypted_models\Dlwh03B.onnx"
INPUT_IMAGE_PATH = r"C:\Users\nltruong\input_face.jpg"
OUTPUT_IMAGE_PATH = r"C:\Users\nltruong\scratch\clothe_smooth_result.jpg"

def main():
    if not os.path.exists(MODEL_PATH) or not os.path.exists(INPUT_IMAGE_PATH):
        print("[-] Vui lòng kiểm tra lại đường dẫn model hoặc ảnh gốc!")
        return

    # 1. Đọc ảnh gốc bằng OpenCV
    img = cv2.imread(INPUT_IMAGE_PATH)
    h, w, c = img.shape

    # 2. Khởi tạo mô hình MNN
    interpreter = MNN.Interpreter(MODEL_PATH)
    session = interpreter.createSession()
    inputs = interpreter.getSessionInputAll(session)
    
    # Thiết lập kích thước nạp vào mô hình (Ví dụ: 256x256)
    target_w, target_h = 256, 256
    interpreter.resizeTensor(inputs['input0'], (1, 3, target_h, target_w))
    interpreter.resizeSession(session)

    # 3. Tiền xử lý ảnh nguồn
    img_resized = cv2.resize(img, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
    img_float = img_resized.astype(np.float32) / 255.0  # Chuẩn hóa về [0, 1]
    img_chw = np.transpose(img_float, (2, 0, 1))        # Chuyển đổi CHW
    img_tensor = np.expand_dims(img_chw, axis=0)        # Thêm chiều batch

    t_in = MNN.Tensor((1, 3, target_h, target_w), MNN.Halide_Type_Float, img_tensor, MNN.Tensor_DimensionType_Caffe)
    inputs['input0'].copyFrom(t_in)

    # 4. Thực thi mô hình AI để tính toán lưới biến dạng (Deformation Grid)
    print("[*] Chạy suy luận mô hình tính toán lưới biến dạng Dlwh03B...")
    interpreter.runSession(session)

    # 5. Trích xuất lưới dịch chuyển 2 kênh (dx, dy)
    outputs = interpreter.getSessionOutputAll(session)
    out_tensor = outputs['output0']
    
    host_tensor = MNN.Tensor(out_tensor.getShape(), out_tensor.getDataType(), MNN.Tensor_DimensionType_Caffe)
    out_tensor.copyToHostTensor(host_tensor)
    grid_data = host_tensor.getNumpyData() # Shape: (1, 2, 64, 64)

    # Loại bỏ batch dimension -> (2, 64, 64)
    displacement_grid = np.squeeze(grid_data, axis=0)
    
    # Phóng to lưới (dx, dy) từ kích thước (64x64) về kích thước ảnh gốc (W x H)
    dx = cv2.resize(displacement_grid[0], (w, h), interpolation=cv2.INTER_LINEAR)
    dy = cv2.resize(displacement_grid[1], (w, h), interpolation=cv2.INTER_LINEAR)

    # 6. Tạo bản đồ tọa độ lưới để tiến hành Warp (Remapping)
    # Tạo bản đồ tọa độ pixel chuẩn (Identity map)
    map_x, map_y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))

    # Áp dụng gia số dịch chuyển của AI vào bản đồ tọa độ (độ lệch nhân thêm hệ số giãn cách)
    # dx và dy thường được chuẩn hóa, cần nhân tỉ lệ kích thước ảnh gốc
    remap_x = map_x + dx * w
    remap_y = map_y + dy * h

    # 7. Tiến hành Warp biến dạng làm phẳng quần áo
    smoothed_img = cv2.remap(img, remap_x, remap_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    # 8. Lưu kết quả
    cv2.imwrite(OUTPUT_IMAGE_PATH, smoothed_img)
    print(f"[+] Làm phẳng quần áo thành công! Kết quả lưu tại: {OUTPUT_IMAGE_PATH}")

if __name__ == "__main__":
    main()
```
