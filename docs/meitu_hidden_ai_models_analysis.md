# Phân Tích Kỹ Thuật Các Tính Năng AI Chuyên Sâu Ẩn Của Cubeo

Bên cạnh các thanh trượt làm đẹp da và nắn mặt cơ bản hiển thị trực quan, Cubeo (MagiMir) sở hữu một hệ thống các mô hình AI chuyên sâu ẩn (**Hidden AI Models**) chạy ngầm để giải quyết các khuyết điểm rất nhỏ hoặc phức tạp trên khuôn mặt và cơ thể. Tất cả các tính năng này hoạt động **Offline 100%** qua nhân C++.

Dưới đây là tài liệu phân tích kỹ thuật chi tiết về cấu trúc mô hình, khóa giải mã và nguyên lý vận hành của các tính năng ẩn này.

---

## 1. Bản Đồ Ánh Xạ Mô Hình AI Chuyên Sâu Ẩn

Dưới đây là bảng trích xuất chi tiết các tệp tin mô hình nhị phân `.lib` gốc trên đĩa cứng, tệp `.onnx` sau giải mã, định danh trong mã nguồn và khóa giải mã đối xứng tương ứng:

| Nhóm Tính Năng AI | Khóa Biến Trong Code | Tệp Mô Hình Gốc | Khóa Giải Mã AES-256-CTR | Tệp ONNX Sau Giải Mã |
| :--- | :--- | :--- | :--- | :--- |
| **Làm nét mặt (Face SR)** | `faceSR` | `FskRv5A8Y421.lib` | `3naEQ2nCfrw1MEqfp6q_J_e7-CDrwKI-XguITaasUS3=` | `FskRv5A8Y421.onnx` (~12.8 MB) |
| **Tạo khối mặt** | `makeupContour` | `FmRv5A8Y402.lib` | `lXFSK1TvVIY9B10PTQzJCZeclVgyCulJ_MPE8_xa__O=` | `FmRv5A8Y402.onnx` (~4.5 MB) |
| **Tô má hồng** | `makeupBlusher` | `FmRv5A8Y403.lib` | `yOSOQpE9Y-kUKNA4Sf9rv2BLKHbaMP-DMZy8hAjgGcx=` | `FmRv5A8Y403.onnx` (~4.2 MB) |
| **Trang điểm mắt** | `makeupEye` | `FmRv5A8Y404.lib` | `On-4XM7Xs__we48dntGdFub_khvZJHh23N47UgWZsSt=` | `FmRv5A8Y404.onnx` (~6.1 MB) |
| **Tô son môi** | `makeupLip` | `FmRv5A8Y405.lib` | `ugQoF9_zmF1w5k8WGUnOxuM7ZO32zVQ9ZuT4wwHf7VS=` | `FmRv5A8Y405.onnx` (~3.9 MB) |
| **Sửa răng sứt mẻ** | `toothRepair_global`<br>`toothRepair_patch` | `Flgv14E08a2.lib`<br>`Flgv14E08b2.lib` | `3QpEnXsJiZq2ndV8SZKctwQ14yh6kV3ZmZBaN28f_dF=` | `Flgv14E08a2.onnx`<br>`Flgv14E08b2.onnx` |
| **Trắng răng** | `toothBeauty` | `FskRv5A8Y410.lib` | `0uz7nIQuHBPmYueYiu9QIu7I9u_2UTvjihWDZfxTXv4=` | `FskRv5A8Y410.onnx` (~5.2 MB) |
| **Xóa rạn da bụng** | `renShenWen` | `FskRv5A8Y424.lib` | `T03sVJxbb9YK8Is028krXcq-_9RosiAwokOX5SsfDcv=` | `FskRv5A8Y424.onnx` (~14.1 MB) |
| **Xóa mỡ nách** | `fuRuRemove` | `FskRv5A8Y426.lib` | `Mc4nN89HV06yL1rdrNHV91fMavjVoPnee5SVm-vjCuE=` | `FskRv5A8Y426.onnx` (~2.9 MB) |
| **Nổi xương quai xanh**| `suoGu` | `FskRv5A8Y434.lib` | `hRCfZN76JlmeBYqBMI6Yu6dIkx874CHkAGfPj_JtO0W=` | `FskRv5A8Y434.onnx` (~8.5 MB) |
| **Xóa nếp nhăn môi** | `chunWen` | `FskRv5A8Y430.lib` | `m_QKS_UM-MkU59chNOr5KobVt-0Fw1Day4LOweSwABr=` | `FskRv5A8Y430.onnx` (~5.4 MB) |
| **Xóa bọng mắt thâm** | `yanDai` | `FskRv5A8Y415.lib` | `BVmH2kZCTqh8_FReJSftT36zWkCNo6whP5uVUZ-HW1v=` | `FskRv5A8Y415.onnx` (~11.6 MB) |

---

## 2. Phân Tích Nguyên Lý Hoạt Động Các Tính Năng Tiêu Biểu

### 2.1. Phục Hồi Mặt Nhòe / Out Nét (`faceSR` - Face Super Resolution)
Khi người dùng import một bức ảnh có chân dung chụp ở xa hoặc bị rung tay out nét nhẹ, mô hình `FskRv5A8Y421.onnx` sẽ được gọi tự động để nâng cấp chi tiết khuôn mặt:
1.  **Cắt vùng mặt (Cropping):** C++ Core dựa vào tọa độ mắt/mũi trích xuất từ mô hình định vị Landmarks `Lp.onnx` để crop riêng vùng khuôn mặt bị nhòe ra làm một ma trận ảnh con độc lập.
2.  **Khôi phục chi tiết bằng AI:** Nạp ảnh con vào mô hình Super Resolution mạng CNN sâu. Mạng này được huấn luyện đặc biệt để tái tạo lại các tần số cao bị mất (như chi tiết sợi lông mày, lông mi, lòng đen con mắt và cấu trúc lỗ chân lông).
3.  **Trộn ảnh (Blending):** Thực hiện phép trộn alpha biên mờ (Feathered alpha blending) để ghép vùng mặt đã được làm sắc nét trở lại vị trí cũ trên ảnh gốc lớn mà không tạo ra vệt tiếp giáp.

### 2.2. Sửa Răng Sứt Mẻ (`toothRepair_global` & `toothRepair_patch`)
Đây là tính năng độc quyền cao cấp dành cho chụp ảnh chân dung cưới để sửa răng thưa, răng lệch hoặc sứt mẻ:
*   Mô hình được chia làm hai phần: mô hình **Global** để phân tích cấu trúc răng và nụ cười toàn diện, mô hình **Patch** để khoanh vùng và tái tạo từng chiếc răng cụ thể.
*   C++ sử dụng kỹ thuật Inpainting kết hợp thông tin cấu trúc đối xứng của các răng lành lặn lân cận để tự động đắp đầy phần răng bị mẻ hoặc che khít khoảng trống kẽ răng thưa một cách tự nhiên.

### 2.3. Xóa Rạn Da Bụng Bau (`renShenWen`) & Mỡ Nách (`fuRuRemove`)
*   **Xóa rạn da bụng bầu (`FskRv5A8Y424.onnx`):** Khi chụp ảnh nghệ thuật mẹ bầu, mô hình quét da bụng nhận dạng các vết rạn nứt màu đỏ/trắng, sau đó áp dụng inpainting bôi mịn các vết rạn theo hướng thớ da bụng.
*   **Xóa mỡ nách/phụ nhũ (`FskRv5A8Y426.onnx`):** Nhận diện vùng nách tiếp giáp với ngực khi nhân vật mặc váy cúp ngực. Áp dụng biến dạng lưới Warp nhẹ để co bóp phần mỡ thừa đẩy vào trong, tạo bờ vai nách thon gọn tự nhiên.
