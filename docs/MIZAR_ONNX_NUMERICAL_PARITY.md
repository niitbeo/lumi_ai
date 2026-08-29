# Kiểm chứng số học Mizar → ONNX (11/11)

Cập nhật: 2026-08-15

## Kết luận

Toàn bộ **11/11 ONNX clean-room**, tương ứng **15 tensor output công khai**, đã khớp runtime Mizar CPU gốc trên ba bộ input xác định khác nhau. Tổng cộng có **45/45 phép so sánh output tensor đạt** với `atol=1e-4`, `rtol=1e-4`.

Mizar/Manis chỉ được dùng làm **oracle trong kiểm thử vi sai**. Các file ONNX phát hành và đường inference bình thường chỉ cần ONNX Runtime CPU; không import, link hoặc nạp `Manis.framework`, Mizar hay operator riêng của Kumoo.

Phạm vi của phép parity này là **tensor input → tensor output của graph**. Một số model còn có contract ảnh ở wrapper C++ của ứng dụng. Ví dụ `skintone_0411` cần mã hóa residual quanh màu da đại diện trước graph và giải mã sau graph; output graph không phải ảnh RGB để hiển thị trực tiếp. Contract này đã được phục hồi riêng và ghi tại `kumoo_algorithms/ALGORITHM_BIBLE.md` cùng implementation thử nghiệm trong `portrait_beauty_lab/server/server.py`.

Ba báo cáo máy đọc được:

- `independent_models/numerical_parity_report.json` — seed gốc `20260815` (seed được tăng theo thứ tự model).
- `independent_models/numerical_parity_report_seed_7.json`.
- `independent_models/numerical_parity_report_seed_424242.json`.

## Kết quả lượt chuẩn

| Model | Số output | Max absolute error lớn nhất | Kết quả |
|---|---:|---:|---|
| `20260203_440epoch_sim_remove_expend_modify` | 1 | `9.59634781e-05` | PASS |
| `365` | 1 | `1.15096569e-04` | PASS |
| `Expelliarmus` | 1 | `8.62404704e-07` | PASS |
| `MTCheek_model` | 1 | `2.02655792e-06` | PASS |
| `MTJaw_model` | 1 | `4.69386578e-07` | PASS |
| `PhotoFaceContour` | 1 | `2.98023224e-07` | PASS |
| `eye_segment` | 1 | `1.23381615e-05` | PASS |
| `hairSeamer_full` | 3 | `2.30073929e-05` | PASS |
| `haircut_1104_1024_epoch_740_1624_new4` | 1 | `1.90734863e-06` | PASS |
| `restoreteeth` | 3 | `1.05500221e-05` | PASS |
| `skintone_0411_384_epoch_850_2` | 1 | `1.53481960e-06` | PASS |

`365` có max absolute error nhỉnh hơn `1e-4`, nhưng từng phần tử vẫn đạt điều kiện kết hợp `atol + rtol * abs(reference)` của `numpy.allclose`. Hai lượt seed bổ sung đều đạt 11/11; max error của `365` lần lượt là `5.29289246e-05` và `4.42862511e-05`.

## 11 ONNX dùng cho việc gì

| Model | Chức năng đã đối chiếu trong app gốc |
|---|---|
| `20260203_440epoch_sim_remove_expend_modify` | Trích đặc trưng cho `MTAutoExposure` (tự động phơi sáng). |
| `365` | `AIBeautyGlassesFilter`: phân tích/xử lý vùng kính, sinh map cho mask và blend. |
| `Expelliarmus` | `cloth_outline`: trường offset 2D để sửa/làm gọn viền quần áo/cơ thể. |
| `MTCheek_model` | Phân loại đặc trưng/hình dạng má, 2 score. |
| `MTJaw_model` | Phân loại đặc trưng/hình dạng hàm, 3 score. |
| `PhotoFaceContour` | Phân đoạn đường bao/toàn vùng mặt. |
| `eye_segment` | Phân đoạn vùng mắt thành map 3 kênh. |
| `hairSeamer_full` | Tinh biên và phục hồi sợi tóc, ba đầu ra phục vụ hậu xử lý seaming/thinning. |
| `haircut_1104_1024_epoch_740_1624_new4` | Sinh ảnh tóc để mô phỏng/chỉnh hair growth/haircut và blend theo mask. |
| `restoreteeth` | Phân loại, tạo mask và tái tạo RGB cho phục hồi răng. |
| `skintone_0411_384_epoch_850_2` | Chỉnh và đồng đều tông da cơ thể. |

Bảng I/O đầy đủ và mức chắc chắn của từng mô tả được lưu ở mục 6.1 của `PROJECT_SUMMARY.md`. Tên module/filter được lấy trực tiếp từ binary app; ý nghĩa chi tiết từng class của `MTCheek_model` và `MTJaw_model` chưa có nhãn trong graph nên không suy đoán thêm.

## Phương pháp kiểm chứng

1. `tools/manis_oracle_runner.cpp` nạp model `.manis` gốc bằng CPU, cấp đúng input float32 và dump tensor output. Runner dùng API index cho output công khai để không phụ thuộc tên trước-hash.
2. Với tensor trung gian, runner đi qua lớp wrapper đã phục dựng và bind trực tiếp **decimal tensor ID**. Cách này chỉ phục vụ chẩn đoán; không sửa file model và không đi vào runtime phát hành.
3. `tools/compare_mizar_onnx.py` sinh input PCG64 xác định trong `[-1, 1]`, chạy cùng input ở Mizar CPU và ONNX Runtime CPU, rồi đo shape, finite, max/mean absolute error, RMSE, relative error và cosine similarity.
4. `tools/compare_mizar_intermediates.py` tạm đưa output từng node ONNX ra ngoài theo lô, đối chiếu với tensor ID tương ứng của Mizar và tìm operator đầu tiên lệch.
5. `tools/validate_independent_mizar.py` chạy riêng 11 ONNX bằng input không hằng, kiểm tra dữ liệu trọng số tự chứa, shape khai báo, NaN/Inf và xác nhận không cần Manis/Mizar.

Lệnh tái lập:

```bash
python3 tools/export_independent_mizar.py
python3 tools/validate_independent_mizar.py --output independent_models/validation_report.json
python3 tools/compare_mizar_onnx.py --seed 20260815
python3 tools/compare_mizar_onnx.py --seed 7 --report independent_models/numerical_parity_report_seed_7.json
python3 tools/compare_mizar_onnx.py --seed 424242 --report independent_models/numerical_parity_report_seed_424242.json
python3 tools/build_independent_mizar_manifest.py
```

## Các vấn đề đã tìm và sửa

### 1. Attribute blob bị đọc nhầm thành scalar

Một số field FlatBuffer là relative offset tới blob có kiểu, không phải giá trị `u32` trực tiếp. Ví dụ hệ số resize `1.0` nằm trong blob float32 bốn byte; một số enum chỉ dài một byte. `tools/dump_mizar_attrs.py` được thêm để in toàn bộ field, raw float, target, chiều dài và byte payload. Việc này ngăn ánh xạ operator dựa trên giá trị offset giả (`4`).

### 2. `DepthToSpace` sai thứ tự kênh

`Expelliarmus` dùng thứ tự `CRD`, không phải `DCR`. Sau khi đổi, max error giảm từ khoảng `1.35e-1` xuống dưới `1e-6`.

### 3. `Resize` bỏ qua coordinate mode

Ánh xạ đúng được xác nhận bằng tensor trước/sau resize:

| Mizar coordinate kind | ONNX |
|---:|---|
| `1` | `half_pixel` |
| `2` | `align_corners` |
| `3` | `asymmetric` |

Interpolation kind `1` là nearest với `nearest_mode=floor`; kind `2` là linear. Sửa này làm `eye_segment`, `365` và `hairSeamer_full` khớp.

### 4. Hai biến thể clamp dùng chung opcode

Opcode trước đây bị coi là ReLU thường. Tensor probe cho thấy nhánh convolution là clamp `[0, 6]` (ReLU6), còn vector gate rank-2 trong `restoreteeth` là clamp `[0, 1]`. Converter hiện chọn giới hạn theo dialect/shape đã quan sát.

### 5. LeakyReLU có slope theo họ model

Opcode chỉ lưu activation kind; slope là mặc định của họ model trong runtime. Tensor âm xác nhận slope `0.1` cho các graph CoreML-twin/legacy, và `0.2` cho `365`, `hairSeamer_full`, `restoreteeth`.

### 6. `MatMul` bị transpose trọng số hai lần

Ở model `20260203...`, constant `(64,64)` đã đúng chiều cho `x @ W`. Bỏ `swapaxes` làm tensor MatMul và output cuối khớp.

### 7. Hai model legacy có shape input và chuẩn hóa động

`MTCheek_model` và `MTJaw_model` có metadata năm chiều với singleton cuối, nhưng runtime thực nhận NCHW bốn chiều. Opcode layout đầu mạng không chỉ reshape mà còn thực hiện per-image standardization:

```text
(x - mean_spatial) / sqrt(mean_spatial((x - mean_spatial)^2))
```

Converter hiện bỏ singleton metadata, tính mean/variance động theo H,W và không dùng hệ số hard-code phụ thuộc input.

### 8. `LegacyBinary(kind=2)` là maximum

Trong dialect face-detect, kind `2` là elementwise `Max`, không phải `Mul`. Sau khi sửa, mọi tensor trung gian của `MTCheek_model` và `MTJaw_model` đạt trên các seed thử nghiệm.

### 9. Thứ tự toán hạng của subtraction

`restoreteeth` dùng kind `1` cho `Sub`. Khi attribute reverse `3389299816=1` xuất hiện cùng constant, phép đúng là `constant - input` (ví dụ `1 - sigmoid`), không phải `input - constant`.

### 10. Opcode bị nhận nhầm là Slice/Clip

Chuỗi `3684297650 → 1332635621` thực chất là `ArgMax(axis=1, keepdims=1) → Cast(float32)`, không phải lấy một channel rồi clip. Tensor oracle cho thấy ArgMax trả nhãn lớp 0/1 và bước sau đổi kiểu để concat với ảnh float.

### 11. Unary kind `5` là `Sin`

Giá trị quan sát như `sin(5.2061405) = -0.880561` xác nhận kind `5` là `Sin`, không phải `Exp` hay `Tanh`. Kind `1` là `Neg`, kind `6` là `Sqrt`.

### 12. Smoke test dùng zero gây chia cho zero

Per-image standardization của hai model face-detect có độ lệch chuẩn bằng 0 trên input toàn zero. Validator độc lập được đổi sang input PCG64 không hằng; đây là dữ liệu hợp lệ hơn và vẫn hoàn toàn xác định.

## Ghi chú về tensor trung gian

Đối chiếu trung gian được dùng để định vị và chứng minh semantics operator. Với `restoreteeth`, tensor `a/(1-a)` có thể đạt hàng nghìn khi mẫu số gần 0, nên sai khác vài `1e-6` ở tensor trước đó bị khuếch đại thành vài đơn vị và không luôn đạt ngưỡng absolute của báo cáo trung gian. Nhánh sau dùng `ArgMax/Cast`, vì vậy sai khác đó không đổi output công khai. Cả ba output cuối của `restoreteeth` đều đạt trên cả ba lượt.

## Ranh giới xác nhận

- Đã xác nhận: giải mã 31/31 `.manis`, đường chạy độc lập 31/31, smoke inference độc lập 11/11 ONNX, và numerical parity 15/15 output tensor trên ba lượt.
- Không tuyên bố bit-for-bit: Mizar CPU và ONNX Runtime dùng kernel/reduction order khác nhau; tiêu chuẩn là `allclose(atol=1e-4, rtol=1e-4)`.
- Không có phụ thuộc phát hành vào Mizar: dependency oracle chỉ tồn tại trong các công cụ kiểm thử `manis_oracle_runner` và `compare_mizar_*`.
