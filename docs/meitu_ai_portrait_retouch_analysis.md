# Phân Tích Kỹ Thuật Nhóm Công Cụ Làm Đẹp Chân Dung (AI Portrait Retouch) Của Cubeo

Tính năng làm đẹp chân dung (AI Portrait Retouch) là lõi cốt lõi làm nên tên tuổi của hệ sinh thái Meitu (Cubeo, Wink, Evoto). Tất cả các chức năng chỉnh sửa da, mắt, răng, nắn xương mặt đều chạy hoàn toàn cục bộ (**Offline 100%**) tận dụng phần cứng GPU của người dùng.

Dưới đây là tài liệu phân tích kỹ thuật chi tiết về cấu trúc mô hình, bảng ánh xạ thanh trượt và giải pháp lập trình giả lập thuật toán mịn da.

---

## 1. Các Mô Hình Trụ Cột (Landmarks & Classification)

Để tất cả các thanh trượt hoạt động chính xác trên từng bộ phận khuôn mặt, hệ thống phải chạy 2 mô hình nền tảng trước tiên:

*   **Mô hình định vị 106 điểm mốc (`landmark106` - `Lp.onnx` ~4.7 MB):**
    *   *Khóa AES-256-CTR:* `k4uLysiZe88tdt0jXywdT6fhgLOcLV5uTOBz3V63_8g=`
    *   *Nhiệm vụ:* Phát hiện khuôn mặt và định vị chính xác 106 điểm mốc (mắt, mũi, môi, chân mày, viền hàm). Đây là mốc neo (anchor) để các thuật toán nắn bóp và trang điểm biết vị trí cần tác động.
*   **Mô hình nhận diện giới tính & độ tuổi (`gender_age` - `Ga2.onnx` ~3.2 MB):**
    *   *Khóa AES-256-CTR:* `-9PkZ0qd4sS54pV_HkgbRIFmGLsfaj1Wnvybcd8LbvI=`
    *   *Nhiệm vụ:* Phân loại xem đối tượng trong ảnh là Nam, Nữ, Trẻ em hay Người già để tự động giới hạn mức độ làm mịn da hoặc trang điểm, tránh việc nam giới hay trẻ em bị trang điểm quá đà mất tự nhiên.

---

## 2. Bảng Ánh Xạ Thanh Trượt UI sang Mô Hình AI Cục Bộ

Dưới đây là bảng ánh xạ chi tiết các thanh trượt trên giao diện phần mềm tới các file mô hình `.onnx` (đã giải mã từ file `.lib` gốc của Cubeo):

| Nhóm Thanh Trượt UI | Khóa Biến Trong Code | Tệp Mô Hình AI (.onnx) | Khóa Giải Mã AES | Cơ Chế Kỹ Thuật Xử Lý |
| :--- | :--- | :--- | :--- | :--- |
| **Mịn da tần số** | `skinHighFrequency`<br>`skinLowFrequency` | `F1sch3b.onnx`<br>`F1sch3c1.onnx` | `Created_by_F1sch3b_Key` | **Tách tần số da (Frequency Separation):** Tách ảnh da thành lớp tần số cao (vân da) và tần số thấp (màu da). Làm mịn độc lập rồi trộn lại để giữ vân lỗ chân lông tự nhiên. |
| **Xóa khuyết điểm / nhăn** | `blemishRemovalDegree`<br>`taiTouWenDegree` (trán)<br>`faLingWenDegree` (rãnh cười) | `F3std1b.onnx`<br>`F3std1c1.onnx` | `Created_by_F3std1b_Key` | **Local Inpainting:** Quét định vị khuyết điểm (mụn, nếp nhăn trán/khóe mắt) và chạy mô hình vẽ đè bằng vân da đẹp từ các vùng lân cận. |
| **Tạo khối 3D** | `neutralGrayWuGuan`<br>`neutralGrayLunkuo` | `F3std1b.onnx` (làm mốc neo) | - | **Đánh khối xám trung tính (Neutral Gray):** Tính toán nguồn sáng ảo trên mặt, phủ lớp xám trung tính lên mặt nạ (Overlay/Soft Light) để tạo bóng 3D cho mũi và gò má. |
| **Ủi phẳng tóc / Che hói** | `removeBrokenHairSlide`<br>`fillTheHairlineGap` | `F2sch1b.onnx`<br>`F2sch1c1.onnx` | `a5m9_Ilfm_Ilf2wy...` | **Hair Matting & Patching:** Tách vùng tóc con chỉa ra để xóa đè bằng phông nền sau, tô phủ mờ lớp màu tối vào vùng tóc thưa ở trán để che hói. |
| **Nắn bóp cằm & dáng vai** | `doubleChinDeform`<br>`luDingDeform` (sọ đầu)<br>`fuRuRemove` (nách) | `Dlwh10.onnx`<br>`Dlwh21A.onnx`<br>`Dlwh09.onnx` | - | **Lưới biến dạng điểm ảnh (Grid Warping):** Dựa trên tọa độ 106 landmarks, mô hình tính toán ma trận dịch chuyển pixel để co bóp nọng cằm, kéo cao đỉnh sọ đầu hoặc bóp vai. |
| **Khử lóa kính & Makeup** | `eyeglassReflect`<br>`makeupTheme` | `Eg.onnx`<br>`Cdu.onnx` | - | **Reflect Removal & GAN Makeup:** Nhận diện vùng phản chiếu ánh sáng trắng trên kính để phục hồi tròng mắt; phủ các lớp trang điểm (son, má hồng) bám khít landmarks. |

---

## 3. Thuật Toán Mịn Da Bằng Tách Tần Số (Frequency Separation)

Để da mịn màng mà không bị "bết sáp" (plasticky), mô hình `F1sch3b` áp dụng kỹ thuật **Tách tần số da (Frequency Separation)**:
1.  **Lớp tần số cao (High-Frequency Layer):** Chứa các chi tiết sắc nét của bề mặt da (lỗ chân lông, nếp nhăn nhỏ, sợi lông tơ).
2.  **Lớp tần số thấp (Low-Frequency Layer):** Chứa thông tin về màu sắc, sắc độ da và chuyển tiếp ánh sáng (không chứa chi tiết bề mặt).
3.  **Xử lý:** Bộ lọc AI lọc nhiễu nhẹ ở lớp tần số thấp để làm đều màu da, xóa mẩn đỏ, trong khi giữ nguyên lớp tần số cao. Sau đó cộng hai lớp lại để tạo ra làn da mịn màng nhưng vẫn rõ từng lỗ chân lông.

---

## 4. Mã Nguồn Giả Lập Tách Tần Số Làm Mịn Da (Python & OpenCV)

Dưới đây là mã nguồn Python minh họa cách tách một bức ảnh chân dung thành hai lớp tần số cao/thấp, làm mịn lớp tần số thấp bằng bộ lọc song phương (Bilateral Filter - bộ lọc làm mịn da giữ lại biên cạnh) và gộp lại để tạo làn da mịn tự nhiên:

```python
import cv2
import numpy as np

def frequency_separation_smoothing(image_path, output_path, smooth_strength=9, detail_preservation=5):
    """
    Giả lập thuật toán mịn da tần số của Meitu bằng OpenCV
    :param smooth_strength: Độ rộng của bộ lọc làm mịn (Bilateral Filter d)
    :param detail_preservation: Độ sắc nét của vân da giữ lại
    """
    # 1. Đọc ảnh gốc BGR
    img = cv2.imread(image_path)
    img_float = img.astype(np.float32)

    # 2. Tạo lớp Tần số thấp (Low Frequency - Làm mờ Gauss)
    # Lớp này chỉ chứa thông tin màu và khối sáng, không chứa chi tiết lỗ chân lông
    blur_kernel = (smooth_strength * 2 + 1, smooth_strength * 2 + 1)
    low_freq = cv2.GaussianBlur(img, blur_kernel, 0)
    low_freq_float = low_freq.astype(np.float32)

    # 3. Tạo lớp Tần số cao (High Frequency - Trừ ảnh)
    # High Frequency = Ảnh gốc - Ảnh làm mờ + 128 (để đưa giá trị xám về trung tính)
    high_freq = img_float - low_freq_float + 128.0
    high_freq = np.clip(high_freq, 0, 255).astype(np.uint8)

    # 4. Làm mịn lớp tần số thấp bằng Bilateral Filter
    # Bộ lọc song phương làm mịn màu da nhưng không làm nhòe viền mắt, mũi, miệng
    low_freq_smoothed = cv2.bilateralFilter(low_freq, smooth_strength, 75, 75)
    low_freq_smoothed_float = low_freq_smoothed.astype(np.float32)

    # 5. Tăng cường độ chi tiết lớp tần số cao (Vân da)
    # Nếu muốn giữ lại lỗ chân lông sắc nét hơn, chúng ta nhân hệ số tăng cường
    high_freq_float = high_freq.astype(np.float32)
    enhanced_high_freq = (high_freq_float - 128.0) * (detail_preservation / 5.0) + 128.0

    # 6. Gộp hai lớp lại (Recombination)
    # Ảnh kết quả = Lớp tần số thấp đã làm mịn + Lớp tần số cao đã tăng cường - 128
    result = low_freq_smoothed_float + enhanced_high_freq - 128.0
    result = np.clip(result, 0, 255).astype(np.uint8)

    # 7. Lưu ảnh
    cv2.imwrite(output_path, result)
    print(f"[+] Đã giả lập mịn da tần số thành công! Lưu tại: {output_path}")

# Chạy thử nghiệm trên ảnh mẫu của bạn
if __name__ == "__main__":
    src_img = r"C:\Users\nltruong\input_face.jpg"
    out_img = r"C:\Users\nltruong\scratch\portrait_smooth_result.jpg"
    frequency_separation_smoothing(src_img, out_img, smooth_strength=7, detail_preservation=5)
```
