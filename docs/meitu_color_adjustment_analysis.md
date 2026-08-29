# Phân Tích Kỹ Thuật Tính Năng Chỉnh Màu Thông Minh (AI Color & Tone Adjustments) Của Cubeo

Tính năng điều chỉnh màu sắc và ánh sáng (Color & Tone Adjustments) trong Cubeo (MagiMir) hoạt động hoàn toàn cục bộ (**Offline 100%**) thông qua nhân C++ `magpie.node`. Hệ thống hỗ trợ từ các thanh trượt màu cơ bản (Exposure, Contrast) đến các tính năng phân tích Histogram thông minh bằng AI (AI White Balance, AI Tonality, 3D LUT).

Dưới đây là tài liệu phân tích kỹ thuật chi tiết về cấu trúc mô hình, danh sách biến trong mã nguồn JS và giải pháp lập trình áp dụng bảng màu 3D LUT.

---

## 1. Bản Đồ Các Thanh Trượt Chỉnh Màu Trong Mã Nguồn

Trong mã nguồn JS (`157.js`), các biến thanh trượt được đồng bộ với bộ lọc màu gồm các nhóm chính sau:

| Nhóm Thanh Trượt | Biến Điều Khiển Trong Code | Cơ Chế Hoạt Động |
| :--- | :--- | :--- |
| **Cân bằng trắng AI** | `aiWhiteBalance` | Tự động phân tích ảnh để phát hiện độ ám màu của môi trường (ấm/lạnh) và hiệu chỉnh cân bằng. |
| **Tông màu AI** | `aiTonality` | Tự động cân bằng phân phối ánh sáng, cứu chi tiết vùng sáng lớn (Highlights) và vùng quá tối (Shadows). |
| **Nhiệt độ & Sắc độ** | `colorTemperature`<br>`hue` | Nhiệt độ màu (kéo Vàng - Xanh dương) và Sắc độ (kéo Xanh lá - Hồng tím). |
| **Phơi sáng & Ánh sáng** | `exposure`<br>`contrast`<br>`brightness`<br>`highlights`<br>`shadows`<br>`white`<br>`black` | Nhóm điều chỉnh độ phơi sáng, độ tương phản, tăng sáng vùng tối (shadows) và cứu cháy sáng (highlights). |
| **Chi tiết & Trong trẻo** | `clarity`<br>`dehaze` | `clarity` tăng độ tương phản cục bộ (Local Contrast) để làm nổi rõ vân khối; `dehaze` loại bỏ sương mù/lớp khói mờ. |
| **Độ bão hòa màu** | `vibrance`<br>`saturation` | `vibrance` tăng độ đậm màu một cách thông minh (bảo vệ màu da không bị cháy cam); `saturation` tăng/giam đồng loạt 100% màu. |
| **Đường cong nâng cao**| `tonePSCurve` | Điều chỉnh đồ thị cong (Tone Curve) 4 kênh (RGB, R, G, B) giống Photoshop. |
| **Chỉnh màu HSL** | `tonePSHSL` | Bảng điều chỉnh Hue, Saturation, Luminance cho 8 kênh màu độc lập giống Lightroom. |

---

## 2. Vai Trò Của Các Mô Hình AI Cục Bộ (Local AI Models)

Khi người dùng bật các tính năng AI tự động hoặc kéo các thanh trượt màu sắc chuyên sâu, lõi C++ sẽ nạp các mô hình sau vào RAM:

1.  **Mô hình phân tích ánh sáng (`Ttbscv1A.onnx` ~8.9 MB):**
    *   *Khóa AES-256-CTR:* `HxejoTPF0G01cqLjyrPv3mYaimSBclhhNvGckiPXBdp=`
    *   *Vai trò:* Khi kích hoạt `aiWhiteBalance` hoặc `aiTonality`, mô hình này nhận ảnh và phân tích biểu đồ phân phối sắc độ (Histogram). Nó dự đoán ra các tham số tối ưu nhất cho phơi sáng, cứu sáng và khử ám vàng, sau đó áp trực tiếp lên ảnh.
2.  **Mô hình ánh xạ màu (`Ctm.onnx` / `Tcv5s00_onnx.onnx` ~3.2 MB):**
    *   *Vai trò:* Chịu trách nhiệm cho tính năng chỉnh màu HSL, Curve và các bộ lọc màu nghệ thuật (LUTs). Mô hình AI thực hiện việc ánh xạ màu (**Color Tone Mapping**) bằng cách tính toán ma trận màu 3D LUT thích ứng theo thời gian thực (Real-time 3D LUT mapping), đảm bảo tốc độ phản hồi cực nhanh khi người dùng kéo thanh trượt HSL.

---

## 3. Mã Nguồn Giả Lập Áp Dụng Bảng Màu 3D LUT (Python & OpenCV)

Dưới đây là mã nguồn Python mô phỏng giải thuật C++ của model `Ctm.onnx`: nạp một bảng màu 3D LUT chuẩn dạng ảnh PNG phẳng (kích thước $512\times512$ pixel cho lưới màu $64\times64\times64$) và áp dụng ánh xạ màu lên bức ảnh gốc:

```python
import cv2
import numpy as np
import os

def apply_3d_lut(image_path, lut_path, output_path):
    """
    Áp dụng bảng màu 3D LUT (định dạng PNG 512x512) lên ảnh gốc
    :param lut_path: Đường dẫn ảnh PNG LUT 3D (Lưới 64x64x64)
    """
    if not os.path.exists(image_path) or not os.path.exists(lut_path):
        print("[-] Vui lòng kiểm tra lại đường dẫn ảnh gốc hoặc file LUT!")
        return

    # 1. Đọc ảnh gốc và ảnh LUT
    img = cv2.imread(image_path) # BGR
    lut = cv2.imread(lut_path)   # Ảnh LUT dạng 2D phẳng (Grid 8x8 của các khối 64x64)

    # Kích thước lưới LUT mặc định của Meitu là 64 (64^3)
    lut_size = 64
    
    # 2. Chuẩn hóa ảnh gốc về khoảng tọa độ của LUT [0, 63]
    # Chia cho 255 và nhân với 63 để đổi dải màu [0, 255] sang tọa độ 3D LUT
    img_lut_coords = (img.astype(np.float32) / 255.0) * (lut_size - 1)

    h, w, c = img.shape
    output_img = np.zeros_like(img)

    # 3. Duyệt qua từng pixel để thực hiện nội suy màu 3D (Nhanh bằng vector hóa)
    # Lấy tọa độ màu B, G, R
    b_coords = img_lut_coords[:, :, 0]
    g_coords = img_lut_coords[:, :, 1]
    r_coords = img_lut_coords[:, :, 2]

    # Tính toán chỉ số block LUT trong lưới 2D 8x8
    # Kênh Blue xác định block nào trong số 64 block (8x8)
    b_index = np.floor(b_coords).astype(np.int32)
    b_fract = b_coords - b_index

    # Block 1 và Block 2 liền kề để nội suy tuyến tính kênh Blue
    b_index1 = np.clip(b_index, 0, lut_size - 1)
    b_index2 = np.clip(b_index + 1, 0, lut_size - 1)

    # Lấy tọa độ pixel đích trong ảnh LUT 2D lớn (512x512)
    # Block 1
    cell1_y = (b_index1 // 8) * lut_size
    cell1_x = (b_index1 % 8) * lut_size
    
    # Block 2
    cell2_y = (b_index2 // 8) * lut_size
    cell2_x = (b_index2 % 8) * lut_size

    # Tọa độ X, Y trong từng block phụ thuộc vào kênh R (trục ngang) và G (trục dọc)
    r_index = np.clip(np.floor(r_coords).astype(np.int32), 0, lut_size - 1)
    g_index = np.clip(np.floor(g_coords).astype(np.int32), 0, lut_size - 1)

    # Tọa độ pixel 2D tương ứng trên ảnh LUT
    lut_y1 = cell1_y + g_index
    lut_x1 = cell1_x + r_index

    lut_y2 = cell2_y + g_index
    lut_x2 = cell2_x + r_index

    # 4. Trích xuất màu đã được biến đổi từ LUT
    lut_val1 = lut[lut_y1, lut_x1].astype(np.float32)
    lut_val2 = lut[lut_y2, lut_x2].astype(np.float32)

    # 5. Nội suy màu tuyến tính (Linear Interpolation) theo kênh Blue
    b_fract_3ch = cv2.merge([b_fract, b_fract, b_fract])
    output_img = (1.0 - b_fract_3ch) * lut_val1 + b_fract_3ch * lut_val2
    output_img = np.clip(output_img, 0, 255).astype(np.uint8)

    # 6. Ghi ảnh kết quả
    cv2.imwrite(output_path, output_img)
    print(f"[+] Áp dụng màu 3D LUT thành công! Lưu tại: {output_path}")

# Chạy thử nghiệm giả lập (Sử dụng tệp tin LUT 3D PNG 512x512 bất kỳ)
if __name__ == "__main__":
    src_img = r"C:\Users\nltruong\input_face.jpg"
    # Giả định bạn có một file LUT trong cache của Cubeo
    lut_file = r"C:\Users\nltruong\magimir_extracted_windows\resources\classic_lut.png"
    out_img = r"C:\Users\nltruong\scratch\color_lut_result.jpg"
    
    if os.path.exists(lut_file):
        apply_3d_lut(src_img, lut_file, out_img)
    else:
        print(f"[-] Vui lòng chuẩn bị tệp tin LUT tại: {lut_file} để chạy.")
```
