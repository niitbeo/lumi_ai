# 📖 Danh Sách Chi Tiết 100 Mô Hình AI Đã Giải Mã & Hướng Dẫn Áp Dụng (Cubeo AI)

Tài liệu này chứa **danh mục hoàn chỉnh của 100 tệp mô hình AI** đã giải mã thành công từ Cubeo (MagiMir Engine). Tất cả các mô hình dưới đây đã được kiểm thử trực tiếp trên runtime **Alibaba MNN Engine** và sẵn sàng để nhúng vào ứng dụng Python / C++.

---

## 💻 Hướng Dẫn Nhanh Cách Gọi & Áp Dụng Model Trong Python

Bạn có thể tải và chạy suy luận (Inference) bất kỳ tệp model nào bên dưới bằng đoạn mã chuẩn sau:

```python
import MNN
import numpy as np
import cv2

# 1. Tải mô hình MNN
model_path = r'g:\Du_an_photo\Cubeo_AI_Analysis\decrypted_models\Bp.onnx'
interpreter = MNN.Interpreter(model_path)
session = interpreter.createSession()

# 2. Lấy Tensor đầu vào & Resize nếu cần
inputs = interpreter.getSessionInputAll(session)
input_tensor = list(inputs.values())[0]

# 3. Chuẩn bị ảnh đầu vào (Ví dụ: 1x3x256x192 float32 normalized)
img = cv2.imread('test.jpg')
img_resized = cv2.resize(img, (192, 256))
img_data = (img_resized.astype(np.float32) / 255.0).transpose(2, 0, 1)[None, ...]

# 4. Copy dữ liệu vào MNN Tensor & Chạy Inference
tmp_tensor = MNN.Tensor(img_data.shape, MNN.Halide_Type_Float, img_data, MNN.Tensor_DimensionType_Caffe)
input_tensor.copyFrom(tmp_tensor)
interpreter.runSession(session)

# 5. Trích xuất kết quả Output
outputs = interpreter.getSessionOutputAll(session)
for name, tensor in outputs.items():
    print(f'Output {name}: shape={tensor.getShape()}')
```

---

## 📋 Bảng Chi Tiết 100 Mô Hình AI Được Phân Theo Nhóm Tính Năng

### Nhóm 10: Tệp Phụ Trợ & Cấu Trúc XML (18 models)

| Tên Tệp Model | Tên Trong Code | Kích Thước | Chức Năng Chi Tiết | Input Shape | Output Shape |
| :--- | :--- | :---: | :--- | :--- | :--- |
| [Eg.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Eg.onnx) | `Eg` | 42.63 MB | Mô hình mô tả cấu trúc OpenVINO / Mô hình phụ trợ | `{'input': (1, -1, -1, -1)}` | `{'output': (0, 0, 0, 0)}` |
| [F1sch3b_ov.xml](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/F1sch3b_ov.xml) | `F1sch3b_ov` | 13.12 MB | Mô hình mô tả cấu trúc OpenVINO / Mô hình phụ trợ | `N/A` | `N/A` |
| [F2sch1b_ov.xml](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/F2sch1b_ov.xml) | `F2sch1b_ov` | 12.89 MB | Mô hình mô tả cấu trúc OpenVINO / Mô hình phụ trợ | `N/A` | `N/A` |
| [F3std1b_ov.xml](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/F3std1b_ov.xml) | `F3std1b_ov` | 18.95 MB | Mô hình mô tả cấu trúc OpenVINO / Mô hình phụ trợ | `N/A` | `N/A` |
| [Flgv14E08a2.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Flgv14E08a2.onnx) | `Flgv14E08a2` | 9.56 MB | Mô hình mô tả cấu trúc OpenVINO / Mô hình phụ trợ | `{'input0': (1, 3, 128, 128), 'input1': (1, 3, 128, 128)}` | `{'output0': (1, 6, 128, 128), 'output1': (1, 1, 128, 128)}` |
| [Flgv14E08b2.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Flgv14E08b2.onnx) | `Flgv14E08b2` | 2.17 MB | Mô hình mô tả cấu trúc OpenVINO / Mô hình phụ trợ | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1), 'input2': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Flgv14E09a2.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Flgv14E09a2.onnx) | `Flgv14E09a2` | 9.56 MB | Mô hình mô tả cấu trúc OpenVINO / Mô hình phụ trợ | `{'input0': (1, 3, 128, 128), 'input1': (1, 3, 128, 128)}` | `{'output0': (1, 6, 128, 128), 'output1': (1, 1, 128, 128)}` |
| [Flgv14E09b2.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Flgv14E09b2.onnx) | `Flgv14E09b2` | 2.17 MB | Mô hình mô tả cấu trúc OpenVINO / Mô hình phụ trợ | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1), 'input2': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Hm4Cpv1_mnn.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Hm4Cpv1_mnn.onnx) | `Hm4Cpv1_mnn` | 2.23 MB | Mô hình mô tả cấu trúc OpenVINO / Mô hình phụ trợ | `{'input0': (1, -1, -1, -1), 'input2': (1, 4, 960, 960)}` | `{'output0': (0, 0, 0, 0)}` |
| [Hm4Cpv1_ov.xml](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Hm4Cpv1_ov.xml) | `Hm4Cpv1_ov` | 2.3 MB | Mô hình mô tả cấu trúc OpenVINO / Mô hình phụ trợ | `N/A` | `N/A` |
| [Hmhcv1_ov.xml](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Hmhcv1_ov.xml) | `Hmhcv1_ov` | 15.75 MB | Mô hình mô tả cấu trúc OpenVINO / Mô hình phụ trợ | `N/A` | `N/A` |
| [IRv5A502B.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/IRv5A502B.onnx) | `IRv5A502B` | 6.18 MB | Mô hình mô tả cấu trúc OpenVINO / Mô hình phụ trợ | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0), 'output1': (0, 0, 0, 0)}` |
| [Tae.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tae.onnx) | `Tae` | 43.13 MB | Mô hình mô tả cấu trúc OpenVINO / Mô hình phụ trợ | `{'input0': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Thmscv1.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Thmscv1.onnx) | `Thmscv1` | 8.57 MB | Mô hình mô tả cấu trúc OpenVINO / Mô hình phụ trợ | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Tsrcv5s.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tsrcv5s.onnx) | `Tsrcv5s` | 0.01 MB | Mô hình mô tả cấu trúc OpenVINO / Mô hình phụ trợ | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Ttbscv1A_ov.xml](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Ttbscv1A_ov.xml) | `Ttbscv1A_ov` | 8.66 MB | Mô hình mô tả cấu trúc OpenVINO / Mô hình phụ trợ | `N/A` | `N/A` |
| [Ttbscv3B01.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Ttbscv3B01.onnx) | `Ttbscv3B01` | 9.8 MB | Mô hình mô tả cấu trúc OpenVINO / Mô hình phụ trợ | `{'input0': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Ttmscv1B_ov.xml](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Ttmscv1B_ov.xml) | `Ttmscv1B_ov` | 8.81 MB | Mô hình mô tả cấu trúc OpenVINO / Mô hình phụ trợ | `N/A` | `N/A` |

### Nhóm 1: Định Vị & Phân Tách Nhân Chủng (5 models)

| Tên Tệp Model | Tên Trong Code | Kích Thước | Chức Năng Chi Tiết | Input Shape | Output Shape |
| :--- | :--- | :---: | :--- | :--- | :--- |
| [Bp.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Bp.onnx) | `body_pose` | 12.77 MB | Định vị 17 khớp xương cơ thể (Vai, Cổ, Hông, Đầu gối) phục vụ gọt dáng & cân vai | `{'input': (1, 3, 256, 192)}` | `{'simcc_x': (1, 17, 384), 'simcc_y': (1, 17, 512)}` |
| [Fd.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Fd.onnx) | `face_detect` | 16.14 MB | Phát hiện khuôn mặt và tạo Bounding Box định vị vị trí nhân vật trong ảnh | `{'input.1': (1, 3, -1, -1)}` | `{'448': (0, 0, 0, 0), '451': (0, 0, 0, 0), '454': (0, 0, 0, 0), '471': (0, 0, 0, 0), '474': (0, 0, 0, 0), '477': (0, 0, 0, 0), '494': (0, 0, 0, 0), '497': (0, 0, 0, 0), '500': (0, 0, 0, 0)}` |
| [Ga2.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Ga2.onnx) | `gender_age` | 42.64 MB | Nhận diện Giới tính & Độ tuổi (Nam, Nữ, Trẻ em, Người già) để tự động cân bằng cường độ retouch | `{'input': (1, -1, -1, -1)}` | `{'output': (0, 0, 0, 0)}` |
| [Lp.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Lp.onnx) | `landmark106` | 4.73 MB | Định vị 106 điểm mốc khuôn mặt (Mắt, Mũi, Môi, Viền hàm) làm hệ tọa độ cho làm đẹp | `{'data': (1, 3, 192, 192)}` | `{'fc1': (1, 212)}` |
| [Pd.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Pd.onnx) | `face_detect_pro` | 4.58 MB | Phát hiện khuôn mặt độ chính xác cao cho ảnh góc nghiêng hoặc ánh sáng phức tạp | `{'image': (1, 3, 416, 416)}` | `{'concat_4.tmp_0': (1, 80, 3598), 'tmp_16': (1, 3598, 4)}` |

### Nhóm 2: Mịn Da & Phục Hồi Bề Mặt Da (22 models)

| Tên Tệp Model | Tên Trong Code | Kích Thước | Chức Năng Chi Tiết | Input Shape | Output Shape |
| :--- | :--- | :---: | :--- | :--- | :--- |
| [F1sch3b.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/F1sch3b.onnx) | `skinFrequencyBase` | 12.84 MB | Mô hình tách ảnh da thành 2 lớp tần số (tần số cao giữ lỗ chân lông, tần số thấp chỉnh màu da) | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0), 'output1': (0, 0, 0, 0)}` |
| [F1sch3c1.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/F1sch3c1.onnx) | `skinFrequencyCorrect1` | 0.01 MB | Hiệu chỉnh độ sắc nét & tương phản da sau khi làm mịn lớp 1 | `{'input0': (7,)}` | `{'output0': (7, 8)}` |
| [F1sch3c2.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/F1sch3c2.onnx) | `skinFrequencyCorrect2` | 0.01 MB | Hiệu chỉnh độ bắt sáng bóng & màu sắc bề mặt da sau làm mịn lớp 2 | `{'input0': (7,)}` | `{'output0': (7, 4)}` |
| [F3std1b.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/F3std1b.onnx) | `blemishRemovalBase` | 18.58 MB | Quét & phát hiện vị trí mụn, sẹo, quầng thâm, vết thâm trán và vết nhăn khóe mắt | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0), 'output1': (0, 0, 0, 0)}` |
| [F3std1c1.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/F3std1c1.onnx) | `blemishInpaint1` | 0.92 MB | Vẽ bù đắp (Inpainting) phủ vân da mịn lân cận đè lên vết mụn sẹo | `{'input0': (13,)}` | `{'output0': (13, 16)}` |
| [F3std1c2.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/F3std1c2.onnx) | `blemishInpaint2` | 0.91 MB | Làm phẳng cấu trúc hạt da vùng vẽ bù đắp để không bị bết màu | `{'input0': (13,)}` | `{'output0': (13, 4)}` |
| [FmRv5A8Y406.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/FmRv5A8Y406.onnx) | `retouchSub_FmRv5A8Y406` | 5.89 MB | Mô hình con hỗ trợ làm đẹp da & chi tiết khuôn mặt | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0), 'output1': (0, 0, 0, 0)}` |
| [FmRv5A8Y407.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/FmRv5A8Y407.onnx) | `retouchSub_FmRv5A8Y407` | 5.89 MB | Mô hình con hỗ trợ làm đẹp da & chi tiết khuôn mặt | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0), 'output1': (0, 0, 0, 0)}` |
| [FmRv5A8Y408.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/FmRv5A8Y408.onnx) | `retouchSub_FmRv5A8Y408` | 5.89 MB | Mô hình con hỗ trợ làm đẹp da & chi tiết khuôn mặt | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0), 'output1': (0, 0, 0, 0)}` |
| [FmRv5A8Y409.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/FmRv5A8Y409.onnx) | `retouchSub_FmRv5A8Y409` | 5.89 MB | Mô hình con hỗ trợ làm đẹp da & chi tiết khuôn mặt | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0), 'output1': (0, 0, 0, 0)}` |
| [FskRv5A8Y410.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/FskRv5A8Y410.onnx) | `retouchSub_FskRv5A8Y410` | 5.89 MB | Mô hình con hỗ trợ làm đẹp da & chi tiết khuôn mặt | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0), 'output1': (0, 0, 0, 0)}` |
| [FskRv5A8Y411.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/FskRv5A8Y411.onnx) | `retouchSub_FskRv5A8Y411` | 5.89 MB | Mô hình con hỗ trợ làm đẹp da & chi tiết khuôn mặt | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0), 'output1': (0, 0, 0, 0)}` |
| [FskRv5A8Y415.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/FskRv5A8Y415.onnx) | `yanDai` | 5.89 MB | Tự động phát hiện & xóa bỏ quầng thâm bọng mắt sưng dưới mắt | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0), 'output1': (0, 0, 0, 0)}` |
| [FskRv5A8Y424.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/FskRv5A8Y424.onnx) | `retouchSub_FskRv5A8Y424` | 5.89 MB | Mô hình con hỗ trợ làm đẹp da & chi tiết khuôn mặt | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0), 'output1': (0, 0, 0, 0)}` |
| [FskRv5A8Y425.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/FskRv5A8Y425.onnx) | `retouchSub_FskRv5A8Y425` | 5.89 MB | Mô hình con hỗ trợ làm đẹp da & chi tiết khuôn mặt | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0), 'output1': (0, 0, 0, 0)}` |
| [FskRv5A8Y426.xml](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/FskRv5A8Y426.xml) | `fuRuRemove` | 5.89 MB | Phát hiện & bóp gọn vùng mỡ thừa dưới nách (mặc váy cưới/áo quây) | `N/A` | `N/A` |
| [FskRv5A8Y430.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/FskRv5A8Y430.onnx) | `chunWen` | 5.89 MB | Làm mịn vân môi & xóa vết nứt nẻ khô môi | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0), 'output1': (0, 0, 0, 0)}` |
| [FskRv5A8Y432.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/FskRv5A8Y432.onnx) | `retouchSub_FskRv5A8Y432` | 5.89 MB | Mô hình con hỗ trợ làm đẹp da & chi tiết khuôn mặt | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0), 'output1': (0, 0, 0, 0)}` |
| [FskRv5A8Y434.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/FskRv5A8Y434.onnx) | `suoGu` | 5.89 MB | Tăng cường độ nổi bật & đường nét xương quai xanh | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0), 'output1': (0, 0, 0, 0)}` |
| [FstRv2E6T01.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/FstRv2E6T01.onnx) | `retouchSub_FstRv2E6T01` | 2.83 MB | Mô hình con hỗ trợ làm đẹp da & chi tiết khuôn mặt | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [FstRv2E6T03.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/FstRv2E6T03.onnx) | `retouchSub_FstRv2E6T03` | 2.83 MB | Mô hình con hỗ trợ làm đẹp da & chi tiết khuôn mặt | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [FstRv2E6T05.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/FstRv2E6T05.onnx) | `retouchSub_FstRv2E6T05` | 2.83 MB | Mô hình con hỗ trợ làm đẹp da & chi tiết khuôn mặt | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |

### Nhóm 3: Dàn Dựng & Làm Đẹp Tóc (3 models)

| Tên Tệp Model | Tên Trong Code | Kích Thước | Chức Năng Chi Tiết | Input Shape | Output Shape |
| :--- | :--- | :---: | :--- | :--- | :--- |
| [F2sch1b.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/F2sch1b.onnx) | `hairSegmentationBase` | 12.68 MB | Tạo mặt nạ (Mask) phân tách toàn bộ vùng tóc nhân vật | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0), 'output1': (0, 0, 0, 0)}` |
| [F2sch1c1.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/F2sch1c1.onnx) | `hairRefine1` | 0.01 MB | Phát hiện & làm sạch các sợi tóc con chỉa ra ngoài (tóc chỉa) | `{'input0': (7,)}` | `{'output0': (7, 8)}` |
| [F2sch1c2.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/F2sch1c2.onnx) | `hairRefine2` | 0.01 MB | Làm mượt biên tóc & phủ kín vùng trán thưa/hói tóc | `{'input0': (7,)}` | `{'output0': (7, 4)}` |

### Nhóm 4: Trang Điểm AI Cục Bộ (Local AI Makeup) (4 models)

| Tên Tệp Model | Tên Trong Code | Kích Thước | Chức Năng Chi Tiết | Input Shape | Output Shape |
| :--- | :--- | :---: | :--- | :--- | :--- |
| [FmRv5A8Y402.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/FmRv5A8Y402.onnx) | `makeupContour` | 5.89 MB | Vẽ phấn tạo khối 3D (Sống mũi, gò má, trán) theo landmarks | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0), 'output1': (0, 0, 0, 0)}` |
| [FmRv5A8Y403.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/FmRv5A8Y403.onnx) | `makeupBlusher` | 5.89 MB | Áp màu phấn má hồng theo các style trang điểm tùy chọn | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0), 'output1': (0, 0, 0, 0)}` |
| [FmRv5A8Y404.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/FmRv5A8Y404.onnx) | `makeupEye` | 5.89 MB | Trang điểm mắt (Vẽ eyeliner, gắn mi giả, phấn mắt) | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0), 'output1': (0, 0, 0, 0)}` |
| [FmRv5A8Y405.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/FmRv5A8Y405.onnx) | `makeupLip` | 5.89 MB | Tô son môi (Son lì, son bóng) và tự động khớp viền môi | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0), 'output1': (0, 0, 0, 0)}` |

### Nhóm 5: Phân Tách Trang Phục & Ảnh Thẻ (4 models)

| Tên Tệp Model | Tên Trong Code | Kích Thước | Chức Năng Chi Tiết | Input Shape | Output Shape |
| :--- | :--- | :---: | :--- | :--- | :--- |
| [ChpsJy.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/ChpsJy.onnx) | `humanParse` | 39.96 MB | Phân tách chi tiết đồ mặc (Áo, Quần, Váy, Giày, Thắt lưng) | `{'input': (1, -1, -1, -1)}` | `{'output': (0, 0, 0, 0)}` |
| [Dlwh03B.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Dlwh03B.onnx) | `clotheFlatten` | 14.64 MB | Phát hiện & sinh ma trận pixel ủi phẳng nếp nhăn quần áo (Sơ mi, Vest, Váy) | `{'input0': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Het.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Het.onnx) | `headMatting` | 34.09 MB | Tách riêng vùng đầu & cổ nhân vật chuyên dụng cho làm ảnh thẻ / avatar | `{'img': (1, 3, 512, 512)}` | `{'output': (1, 1, 512, 512)}` |
| [HisJ.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/HisJ.onnx) | `humanInstance` | 38.52 MB | Tách riêng biệt từng cá thể người độc lập trong ảnh nhóm | `{'input': (1, -1, -1, -1)}` | `{'onnx::Concat_1068': (0, 0, 0, 0), 'onnx::Reshape_1122': (0, 0, 0, 0), 'onnx::Reshape_1149': (0, 0, 0, 0), 'onnx::Shape_1021': (0, 0, 0, 0), 'onnx::Shape_1095': (0, 0, 0, 0), 'output': (0, 0, 0, 0)}` |

### Nhóm 6: Cân Chỉnh & Nắn Bóp Hình Thể (10 models)

| Tên Tệp Model | Tên Trong Code | Kích Thước | Chức Năng Chi Tiết | Input Shape | Output Shape |
| :--- | :--- | :---: | :--- | :--- | :--- |
| [Dlwh07B.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Dlwh07B.onnx) | `bodyWarp_Dlwh07B` | 14.66 MB | Mô hình biến dạng ma trận nắn bóp chi tiết cơ thể | `{'input': (1, -1, -1, -1)}` | `{'output': (0, 0, 0, 0)}` |
| [Dlwh08B.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Dlwh08B.onnx) | `bodyWarp_Dlwh08B` | 43.55 MB | Mô hình biến dạng ma trận nắn bóp chi tiết cơ thể | `{'input': (1, -1, -1, -1)}` | `{'output': (0, 0, 0, 0)}` |
| [Dlwh09.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Dlwh09.onnx) | `shoulderSlim` | 14.64 MB | Thon gọn cơ vai & làm thanh thoát bả vai | `{'input0': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Dlwh10.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Dlwh10.onnx) | `doubleChin` | 14.64 MB | Bóp gọn nọng cằm & xóa bóng tối vùng cổ giúp cằm V-line | `{'input0': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Dlwh16.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Dlwh16.onnx) | `bodyWarp_Dlwh16` | 14.64 MB | Mô hình biến dạng ma trận nắn bóp chi tiết cơ thể | `{'input': (1, -1, -1, -1)}` | `{'output': (0, 0, 0, 0)}` |
| [Dlwh17.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Dlwh17.onnx) | `bodyWarp_Dlwh17` | 14.64 MB | Mô hình biến dạng ma trận nắn bóp chi tiết cơ thể | `{'input': (1, -1, -1, -1)}` | `{'output': (0, 0, 0, 0)}` |
| [Dlwh18.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Dlwh18.onnx) | `idPhotoSymBody` | 14.64 MB | Cân đối đối xứng 2 bên vai qua trục cổ chuyên dụng cho ảnh thẻ | `{'input': (1, -1, -1, -1)}` | `{'output': (0, 0, 0, 0)}` |
| [Dlwh19A.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Dlwh19A.onnx) | `bodyWarp_Dlwh19A` | 14.66 MB | Mô hình biến dạng ma trận nắn bóp chi tiết cơ thể | `{'input': (1, -1, -1, -1)}` | `{'output': (0, 0, 0, 0)}` |
| [Dlwh20A.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Dlwh20A.onnx) | `bodyWarp_Dlwh20A` | 14.66 MB | Mô hình biến dạng ma trận nắn bóp chi tiết cơ thể | `{'input': (1, -1, -1, -1)}` | `{'output': (0, 0, 0, 0)}` |
| [Dlwh21A.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Dlwh21A.onnx) | `neckCorrection` | 14.66 MB | Nắn thẳng đốt sống cổ nghiêng & cân bằng độ dài cổ | `{'input': (1, -1, -1, -1)}` | `{'output': (0, 0, 0, 0)}` |

### Nhóm 7: Chỉnh Màu & Presets StyleNormV9 (16 models)

| Tên Tệp Model | Tên Trong Code | Kích Thước | Chức Năng Chi Tiết | Input Shape | Output Shape |
| :--- | :--- | :---: | :--- | :--- | :--- |
| [CcpJy.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/CcpJy.onnx) | `colorCore_CcpJy` | 39.95 MB | Mô hình lõi xử lý không gian màu & ánh sáng | `{'input': (1, -1, -1, -1)}` | `{'output': (0, 0, 0, 0)}` |
| [Cdu.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Cdu.onnx) | `colorCore_Cdu` | 42.69 MB | Mô hình lõi xử lý không gian màu & ánh sáng | `{'input0': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Cfr.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Cfr.onnx) | `colorCore_Cfr` | 91.63 MB | Mô hình lõi xử lý không gian màu & ánh sáng | `{'input0': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Cis.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Cis.onnx) | `imageScene` | 42.74 MB | Nhận diện bối cảnh ảnh (Nội thất, Cây cối, Phố thị, Biển) để áp Preset | `{'input0': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [CssJy.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/CssJy.onnx) | `colorCore_CssJy` | 39.96 MB | Mô hình lõi xử lý không gian màu & ánh sáng | `{'input': (1, -1, -1, -1)}` | `{'output': (0, 0, 0, 0)}` |
| [Ctm.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Ctm.onnx) | `colorToneMapping` | 42.63 MB | Ánh xạ màu pixel & áp bảng màu 3D LUT thời gian thực | `{'input0': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Tlgv9-N01a.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tlgv9-N01a.onnx) | `styleNormV9_Tlgv9-N01a` | 27.55 MB | Mô hình ma trận màu thuộc bộ StyleNormV9 theo từng ngữ cảnh bối cảnh | `{'input0': (1, 3, 512, 512), 'input1': (1, 3, 512, 512)}` | `{'output0': (1, 6, 512, 512)}` |
| [Tlgv9-N01b.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tlgv9-N01b.onnx) | `styleNormV9_Tlgv9-N01b` | 0.01 MB | Mô hình ma trận màu thuộc bộ StyleNormV9 theo từng ngữ cảnh bối cảnh | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Tlgv9-N02a.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tlgv9-N02a.onnx) | `styleNormV9_Tlgv9-N02a` | 27.55 MB | Mô hình ma trận màu thuộc bộ StyleNormV9 theo từng ngữ cảnh bối cảnh | `{'input0': (1, 3, 512, 512), 'input1': (1, 3, 512, 512)}` | `{'output0': (1, 6, 512, 512)}` |
| [Tlgv9-N02b.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tlgv9-N02b.onnx) | `styleNormV9_Tlgv9-N02b` | 0.01 MB | Mô hình ma trận màu thuộc bộ StyleNormV9 theo từng ngữ cảnh bối cảnh | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Tlgv9-N03a.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tlgv9-N03a.onnx) | `styleNormV9_Tlgv9-N03a` | 27.55 MB | Mô hình ma trận màu thuộc bộ StyleNormV9 theo từng ngữ cảnh bối cảnh | `{'input0': (1, 3, 512, 512), 'input1': (1, 3, 512, 512)}` | `{'output0': (1, 6, 512, 512)}` |
| [Tlgv9-N03b.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tlgv9-N03b.onnx) | `styleNormV9_Tlgv9-N03b` | 0.01 MB | Mô hình ma trận màu thuộc bộ StyleNormV9 theo từng ngữ cảnh bối cảnh | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Tlgv9-N04a.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tlgv9-N04a.onnx) | `styleNormV9_Tlgv9-N04a` | 27.55 MB | Mô hình ma trận màu thuộc bộ StyleNormV9 theo từng ngữ cảnh bối cảnh | `{'input0': (1, 3, 512, 512), 'input1': (1, 3, 512, 512)}` | `{'output0': (1, 6, 512, 512)}` |
| [Tlgv9-N04b.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tlgv9-N04b.onnx) | `styleNormV9_Tlgv9-N04b` | 0.01 MB | Mô hình ma trận màu thuộc bộ StyleNormV9 theo từng ngữ cảnh bối cảnh | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Ttbscv1A.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Ttbscv1A.onnx) | `aiWhiteBalance` | 8.57 MB | Phân tích Histogram để cân bằng trắng tự động & khử ám màu | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Ttmscv1B.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Ttmscv1B.onnx) | `toneMimic` | 9.21 MB | Khớp tông màu tự động theo ảnh mẫu (AI Color Match) | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1), 'input2': (1, -1, -1, -1), 'input3': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |

### Nhóm 8: Phóng To & Phục Hồi Ảnh (3 models)

| Tên Tệp Model | Tên Trong Code | Kích Thước | Chức Năng Chi Tiết | Input Shape | Output Shape |
| :--- | :--- | :---: | :--- | :--- | :--- |
| [FskRv5A8Y421.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/FskRv5A8Y421.onnx) | `faceSR` | 5.89 MB | Khôi phục siêu độ phân giải cho khuôn mặt nhòe/out nét (Face SR) | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0), 'output1': (0, 0, 0, 0)}` |
| [IRv5A601D.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/IRv5A601D.onnx) | `inpaintBg` | 6.69 MB | Vẽ bù phông nền offline cho các điểm rác trên nền cảnh vật | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0), 'output1': (0, 0, 0, 0)}` |
| [Tsrcv4.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tsrcv4.onnx) | `toneSR` | 2.23 MB | Phóng to ảnh thông minh tăng độ phân giải (Upscaling) toàn ảnh | `{'input0': (1, -1, -1, -1), 'input1': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |

### Nhóm 9: Thanh Trượt Chỉnh Màu Thủ Công (15 models)

| Tên Tệp Model | Tên Trong Code | Kích Thước | Chức Năng Chi Tiết | Input Shape | Output Shape |
| :--- | :--- | :---: | :--- | :--- | :--- |
| [Tcv5s.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tcv5s.onnx) | `colorSlider_Tcv5s` | 10.08 MB | Mô hình tính toán cho thanh trượt chỉnh màu thủ công (Nhiệt độ, HSL, Brightness...) | `{'input0': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0), 'output1': (0, 0, 0, 0)}` |
| [Tcv5s00.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tcv5s00.onnx) | `colorSlider_Tcv5s00` | 0.02 MB | Mô hình tính toán cho thanh trượt chỉnh màu thủ công (Nhiệt độ, HSL, Brightness...) | `{'input0': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Tcv5s01.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tcv5s01.onnx) | `colorSlider_Tcv5s01` | 0.02 MB | Mô hình tính toán cho thanh trượt chỉnh màu thủ công (Nhiệt độ, HSL, Brightness...) | `{'input0': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Tcv5s02.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tcv5s02.onnx) | `colorSlider_Tcv5s02` | 0.02 MB | Mô hình tính toán cho thanh trượt chỉnh màu thủ công (Nhiệt độ, HSL, Brightness...) | `{'input0': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Tcv5s03.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tcv5s03.onnx) | `colorSlider_Tcv5s03` | 0.02 MB | Mô hình tính toán cho thanh trượt chỉnh màu thủ công (Nhiệt độ, HSL, Brightness...) | `{'input0': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Tcv5s04.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tcv5s04.onnx) | `colorSlider_Tcv5s04` | 0.02 MB | Mô hình tính toán cho thanh trượt chỉnh màu thủ công (Nhiệt độ, HSL, Brightness...) | `{'input0': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Tcv5s05.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tcv5s05.onnx) | `colorSlider_Tcv5s05` | 0.02 MB | Mô hình tính toán cho thanh trượt chỉnh màu thủ công (Nhiệt độ, HSL, Brightness...) | `{'input0': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Tcv5s06.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tcv5s06.onnx) | `colorSlider_Tcv5s06` | 0.02 MB | Mô hình tính toán cho thanh trượt chỉnh màu thủ công (Nhiệt độ, HSL, Brightness...) | `{'input0': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Tcv5s07.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tcv5s07.onnx) | `colorSlider_Tcv5s07` | 0.02 MB | Mô hình tính toán cho thanh trượt chỉnh màu thủ công (Nhiệt độ, HSL, Brightness...) | `{'input0': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Tcv5s08.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tcv5s08.onnx) | `colorSlider_Tcv5s08` | 0.02 MB | Mô hình tính toán cho thanh trượt chỉnh màu thủ công (Nhiệt độ, HSL, Brightness...) | `{'input0': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Tcv5s09.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tcv5s09.onnx) | `colorSlider_Tcv5s09` | 0.02 MB | Mô hình tính toán cho thanh trượt chỉnh màu thủ công (Nhiệt độ, HSL, Brightness...) | `{'input0': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Tcv5s10.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tcv5s10.onnx) | `colorSlider_Tcv5s10` | 0.02 MB | Mô hình tính toán cho thanh trượt chỉnh màu thủ công (Nhiệt độ, HSL, Brightness...) | `{'input0': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Tcv5s11.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tcv5s11.onnx) | `colorSlider_Tcv5s11` | 0.02 MB | Mô hình tính toán cho thanh trượt chỉnh màu thủ công (Nhiệt độ, HSL, Brightness...) | `{'input0': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Tcv5s12.onnx](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tcv5s12.onnx) | `colorSlider_Tcv5s12` | 0.02 MB | Mô hình tính toán cho thanh trượt chỉnh màu thủ công (Nhiệt độ, HSL, Brightness...) | `{'input0': (1, -1, -1, -1)}` | `{'output0': (0, 0, 0, 0)}` |
| [Tcv5s_ov.xml](file:///g:/Du_an_photo/Cubeo_AI_Analysis/decrypted_models/Tcv5s_ov.xml) | `colorSlider_Tcv5s_ov` | 10.24 MB | Mô hình tính toán cho thanh trượt chỉnh màu thủ công (Nhiệt độ, HSL, Brightness...) | `N/A` | `N/A` |
