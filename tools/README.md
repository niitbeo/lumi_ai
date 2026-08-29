# Kumoo & Meitu AI Model Decryption & Reverse Engineering Toolkit

Bộ công cụ mã nguồn C++ và Python dùng để trích xuất, giải mã và chuyển đổi toàn bộ hệ thống model AI từ ứng dụng **Kumoo / Meitu / Leien Photo AI** sang định dạng chuẩn ONNX.

---

## 🛠 Danh mục công cụ trong `tools/`

### 1. Giải mã bộ nhớ RAM & LLDB Hooks
- **`lldb_manis_unpack.py`**: Hook vào hàm `manis::Net::CreateNet` và `manis::CacheModel` của `Manis.framework` để chặn và trích xuất payload FlatBuffer decrypted (`.manis.decoded`).
- **`lldb_free_hook.py`**: Hook vào hàm `free()` trên macOS arm64 để bắt các buffer model trong heap (khi model không gọi trực tiếp qua các breakpoint thông thường hoặc bị cache).

### 2. Chuyển đổi Model (Mizar FlatBuffers -> ONNX)
- **`mizar_to_onnx.py`**: Trình dịch ngược và chuyển đổi từ định dạng FlatBuffers nội bộ của Meitu (`MZAR` / `.manis.decoded`) sang chuẩn **ONNX**. Tự động khôi phục cấu trúc đồ thị, tên tensor, trọng số (weights), thuộc tính (attributes) và khắc phục sai lệch kiểu dữ liệu (như ArgMax int64).
- **`mizar_schema_recovery.py`**: Tự động phục hồi schema FlatBuffers từ cấu trúc nhị phân của model.
- **`mizar_flatbuffer_probe.py`**: Công cụ thăm dò và phân tích cấu trúc trường (fields/vtable) của FlatBuffer.
- **`dump_mizar_attrs.py`**: Xuất các thuộc tính toán tử (OP attributes) của Mizar.

### 3. C++ Probes & Test Runnners
- **`manis_batch_probe.cpp`**: Nạp và kiểm tra hàng loạt file `.manis` thông qua `Manis.framework` trên các thiết bị khác nhau (Device 0: CPU, Device 1: Metal/GPU, Device 2: MPS, Device 3: OpenCL).
- **`manis_net_probe.cpp`**: Thăm dò trực tiếp interface `manis::Net`.
- **`manis_cache_probe.cpp`**: Thăm dò cơ chế cache model của Kumoo.
- **`manis_coreml_batch_probe.cpp`**: Kiểm tra các model CoreML backend.
- **`tiamat_model_dump_interpose.cpp`**: Thư viện dyld interpose để chèn vào tiến trình Kumoo (`YunXiu-PC`) và dump model tự động.

### 4. So sánh & Kiểm định Số học (Parity Validation)
- **`compare_mizar_onnx.py`**: So sánh đầu ra số học (numerical parity) giữa engine gốc của Meitu và ONNX Runtime để đảm bảo độ chính xác bit-by-bit.
- **`compare_mizar_intermediates.py`**: So sánh các lớp layer trung gian.

---

## 🚀 Quy trình trích xuất & giải mã Model chuẩn:

### Bước 1: Trích xuất file `.manis` / `.bin` gốc từ VPK
Các model mã hóa nằm trong gói `megatron.vpk` của Kumoo (`/Applications/Kumoo.app/Contents/Resources/megatron.vpk`).
Sử dụng công cụ giải nén VPK để lấy ra các file `.manis` và `.bin`.

### Bước 2: Chặn và giải mã trong RAM bằng LLDB
Chạy `manis_batch_probe` kết hợp với kịch bản LLDB để dump payload nhị phân phẳng:
```bash
# Biên dịch probe
clang++ -std=c++17 -o /tmp/manis_batch_probe tools/manis_batch_probe.cpp

# Chạy LLDB với kịch bản hook
CUBEO_MANIS_UNPACK_DIR=/tmp/dump_output lldb -s tools/lldb_manis_unpack.py -- /tmp/manis_batch_probe /path/to/encrypted_models /tmp/cache 1 0 0
```

### Bước 3: Chuyển đổi `.decoded` sang `.onnx`
Sử dụng `mizar_to_onnx.py` để tạo file ONNX:
```bash
python3 tools/mizar_to_onnx.py /tmp/dump_output/model_name.manis.decoded server/models/model_name.onnx
```

### Bước 4: Kiểm tra Tensor Shapes bằng ONNX Runtime
```bash
python3 -c "import onnx; m = onnx.load('server/models/model_name.onnx'); print([(i.name, [d.dim_value for d in i.type.tensor_type.shape.dim]) for i in m.graph.input]); print([(o.name, [d.dim_value for d in o.type.tensor_type.shape.dim]) for o in m.graph.output])"
```
