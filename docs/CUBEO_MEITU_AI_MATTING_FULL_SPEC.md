# 🤖 HỒ SƠ & BỘ MÃ CHẠY AI TÁCH NỀN C++ MEITU CUBEO (APOLLO-WS PIPELINE)

## 1. 📂 Các Tệp Mã Nguồn & Pipeline Đã Lưu Trữ
- **Script Pipeline Python C++ AI Matting**: [cubeo_meitu_matting_engine.py](file:///Users/nguyenletruong/Cubeo_AI_Analysis/cubeo_meitu_matting_engine.py)
- **Ảnh Kết Quả Tách Nền Mẫu (PNG Transparency)**: [cubeo_meitu_segmented_result.png](file:///Users/nguyenletruong/Cubeo_AI_Analysis/cubeo_meitu_segmented_result.png)

---

## 2. 🏛 Kiến Trúc Pipeline C++ Native Gốc Trích Xuất Từ Binary (`apollo-ws`)
- **Dịch vụ Tách Mask Ảnh**: `/Users/meitu/apollo-ws/core/service/mask/image_segment_mask_service.cpp`
- **Tiến trình Bất Đồng Bộ**: `/Users/meitu/apollo-ws/core/service/mask/image_segment_mask_async.cpp`
- **Thuật toán Lọc Viền Tóc (`MTHairSeamer`)**: `/Users/meitu/apollo-ws/build_script/libmtai/demo/3rdparty/MTHairSeamer/src/polyline/thinning.cpp`
- **Thuật toán Mịn Mép Alpha (`image_segment_mask_refining.h`)**: Tách tóc tơ (`fluffy_hair`) và viền vai áo (`body_optimization`).

---

## 🚀 Hướng Dẫn Kích Hoạt Chạy Tách Nền AI
```bash
python3 /Users/nguyenletruong/Cubeo_AI_Analysis/cubeo_meitu_matting_engine.py
```
