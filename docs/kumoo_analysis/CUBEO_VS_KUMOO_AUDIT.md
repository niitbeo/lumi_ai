# 🔍 Audit: Code Cubeo AI đã đủ làm phần mềm giống Kumoo chưa?

> Cập nhật: 2026-08-09

---

## TL;DR — Đã có ~60% nền tảng, nhưng chỉ ~15% hoạt động end-to-end

| Hạng mục | Kumoo Desktop | Cubeo AI hiện tại | Trạng thái |
|---|---|---|---|
| **Tách nền AI** | ✅ Manis/Mizar engine | ✅ 6 model MNN pipeline + GrabCut | ✅ **Hoạt động** |
| **Retouch da mặt** (mịn da, xoá mụn, xoá quầng) | ✅ 22 model chuyên biệt | ⚠️ 22 model đã giải mã, UI slider có, **backend chưa nối** | ❌ Chưa chạy |
| **Chỉnh khuôn mặt** (bóp mặt, nâng mũi, to mắt) | ✅ 10 model warp | ⚠️ 10 model đã giải mã, **backend chưa nối** | ❌ Chưa chạy |
| **Trang điểm AI** (contour, blush, eyeliner, son) | ✅ 4 model makeup | ⚠️ 4 model đã giải mã, **chưa có code** | ❌ Chưa chạy |
| **Chỉnh màu / Color grading** | ✅ HSL + Curve + Tone + LUT | ⚠️ 16 model color đã giải mã, UI CSS filter giả, **backend chưa nối** | ❌ Chưa chạy |
| **Style Transfer / Tone Mimic** | ✅ Ttmscv1B | ✅ Script standalone `cubeo_style_pipeline.py` | ⚠️ CLI only |
| **Face Detection + Landmarks** | ✅ Fd + Lp | ⚠️ Model giải mã xong, test script có, **chưa nối vào app** | ❌ Chưa chạy |
| **Super-Resolution / Upscale** | ✅ 3 model SR | ⚠️ 3 model giải mã xong, **chưa có code** | ❌ Chưa chạy |
| **Xoá vật thể (Inpainting)** | ✅ IRv5A601D | ⚠️ Model giải mã xong, **chưa có code** | ❌ Chưa chạy |
| **Clothing retouch** (xoá nhăn, đổi màu) | ✅ Dlwh03B | ⚠️ Model giải mã xong, **chưa có code** | ❌ Chưa chạy |
| **Ảnh thẻ (ID Photo)** | ✅ Chuyên biệt | ⚠️ Model warp có, **chưa có code** | ❌ Chưa chạy |
| **Filter / Preset** (255+ bộ lọc) | ✅ 3D LUT PNG | ⚠️ Đã phân tích cấu trúc, **chưa extract LUT** | ❌ Chưa chạy |
| **Batch processing** | ✅ | ❌ | ❌ Chưa có |
| **UI chuyên nghiệp** | ✅ Qt Native | ⚠️ React mockup + Qt prototype | ⚠️ Mockup |

---

## ✅ Những gì ĐÃ CÓ và HOẠT ĐỘNG

### 1. Tách nền AI (Background Removal) — **HOÀN CHỈNH**
- Pipeline 6 model MNN: `Het` → `ChpsJy` → `HisJ` → `CssJy` → `Thmscv1` → `Hm4Cpv1`
- GrabCut refinement + edge decontamination + halo removal
- API endpoint: `POST /api/matting`
- 3 chế độ: ONNX standalone, `.istar` cache Kumoo, PNG export cache
- React UI kết nối backend đầy đủ

### 2. 100 Model AI đã giải mã
- 92 model MNN chạy được
- 8 container cnndata → transpile ONNX thành công
- Kiểm chứng số học correlation 1.000000 vs engine gốc

### 3. Công cụ Reverse Engineering
- 23 tool (dylib hook, C++ probe, Python WS, LLDB scripts)
- Decrypt engine cho cả AES-CTR và Fernet
- cnndata extractor + OpenVINO → ONNX transpiler
- `xcdl_read` để decrypt `.istar` mask

### 4. Native C++ Engine
- `cubeo_cpp_engine.cpp` — MNN matting binary (65KB compiled)
- `cubeo_official_server.cpp` — ONNXRuntime server với 5,145 symbol RE
- Qt Photo Editor prototype (`KumooNativePhotoEditor.app`)

### 5. Tài liệu & Specs
- 5,145+ symbol C++ reverse-engineered
- Qt UI specs JSON
- Model dictionary 100 model
- 20+ bài phân tích chức năng Meitu

---

## ❌ Những gì CHƯA LÀM (cần để giống Kumoo)

### Ưu tiên 1 — Cần backend pipeline cho từng feature

| Feature | Model sẵn | Cần làm |
|---|---|---|
| **Retouch da** | `F1sch3b/c1/c2`, `F3std1b/c1/c2`, `FskRv5A8Y*` (22 model) | Viết inference pipeline, nối pre/post-processing, kết nối API |
| **Reshape mặt** | `Dlwh07B~21A` (10 model) | Viết warp engine dùng landmarks + displacement field |
| **Color grading** | `Tcv5s*` (15 model), `Ctm`, `Ttbscv1A` | Viết slider → model inference → apply color transform |
| **Trang điểm** | `FmRv5A8Y402~405` (4 model) | Viết makeup pipeline với face segmentation mask |

### Ưu tiên 2 — Feature mới cần xây từ đầu

| Feature | Cần làm |
|---|---|
| **Xoá vật thể** | Inference `IRv5A601D` + brush mask UI + inpainting post-processing |
| **Super-Resolution** | Inference `FskRv5A8Y421` / `Tsrcv4` + tile-based upscale cho ảnh lớn |
| **Clothing retouch** | Inference `Dlwh03B` + garment mask `ChpsJy` |
| **255 Filter/LUT** | Extract 3D LUT PNG từ base.db + apply pipeline |
| **Batch processing** | Queue system + parallel inference |

### Ưu tiên 3 — UI/UX

| Hạng mục | Cần làm |
|---|---|
| **Editor chính** | Tổng hợp 5 file JSX mockup → 1 editor thống nhất kết nối backend |
| **Toolbar tools** | Tab chuyển đổi: Retouch / Color / Crop / Filter / Export |
| **Canvas** | Zoom/pan, brush mask, before/after compare slider |
| **Preset panel** | Load 33 preset từ base.db |

---

## 📊 Ước lượng khối lượng

```
Đã hoàn thành:
  ✅ Reverse engineering & decrypt     : 100%
  ✅ Model inventory & validation       : 100%
  ✅ Background removal pipeline        : 100%
  ✅ Architecture documentation         : 100%

Cần làm tiếp:
  🔧 Portrait retouch pipeline         : 0%  (model sẵn, cần viết code)
  🔧 Face reshape pipeline             : 0%  (model sẵn, cần viết code)
  🔧 Color grading pipeline            : 0%  (model sẵn, cần viết code)
  🔧 Makeup pipeline                   : 0%  (model sẵn, cần viết code)
  🔧 Object removal                    : 0%
  🔧 Super-resolution                  : 0%
  🔧 Filter/LUT system                 : 0%
  🔧 Unified Editor UI                 : 20% (mockup có, cần nối backend)
  🔧 Batch processing                  : 0%

Tổng ước lượng: ~15% end-to-end hoàn chỉnh
               ~60% nền tảng đã có (model + RE + kiến trúc)
```

---

## 🎯 Kết luận

**Có đủ "nguyên liệu" nhưng chưa có "món ăn".**

Phần khó nhất (reverse engineering, giải mã 100 model, xác minh số học) đã xong hoàn toàn. Nhưng để thành phần mềm giống Kumoo cần:

1. **Viết inference pipeline** cho từng nhóm model (retouch, reshape, color, makeup) — đây là phần code nhiều nhất
2. **Xây UI editor thống nhất** kết nối tất cả pipeline qua API
3. **Pre/post processing** cho từng feature (warp mesh, alpha blend, LUT apply...)

Ước tính cần thêm **2-4 tuần full-time** để có phiên bản feature-complete ngang Kumoo.
