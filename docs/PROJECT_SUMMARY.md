# Cubeo (MagiMir) — Tổng kết dự án giải mã & chạy model AI

Cập nhật: 2026-08-16

Mục tiêu: giải mã, tách và chạy lại các model AI của Cubeo (tên nội bộ **MagiMir**, engine **Megatron/Manis/mizar** của Meitu) bên ngoài app.

---

## 1. Trạng thái tổng quan

| Hạng mục | Trạng thái |
|---|---|
| Giải mã 100 model tải-về (`decrypted_models/`) | ✅ Xong |
| 92 model MNN nạp chạy trong MNN 3.0.0 | ✅ Xong |
| 8 container cnndata → tách trọng số + topology | ✅ Xong |
| Transpile 8/8 cnndata → ONNX chuẩn chạy được | ✅ Xong |
| Kiểm chứng số học vs engine gốc (corr 1.000000) | ✅ 4 model đa dạng |
| Chạy inference thật (matting, style, cutout) | ✅ Xong |
| Tách `megatron.vpk` / `megatron_conf.vpk` | ✅ 854/854 + 3481/3481, hash khớp |
| Giải mã model Megatron | ✅ 31 `.manis` + 35 `.manisa` |
| `.manisa` chạy độc lập bằng Apple CoreML | ✅ 35/35 |
| `.manis` chạy độc lập khỏi Mizar | ✅ 31/31: 20 CoreML twin + 11 ONNX clean-room |
| So khớp số học 11 ONNX vs Mizar CPU | ✅ 11/11 model, 15/15 output, 3 lượt seed |

---

## 2. Cơ chế mã hóa model

Hai scheme, script tự thử cả hai (`decrypt_models_v2.py`):

- **Cũ (bundled/tải qua base.db)**: **AES-256-CTR**, nonce = 16 byte 0, khóa = base64 URL-safe (32 byte). File giải ra là **MNN** (đuôi `.onnx` nhưng thực chất MNN FlatBuffer).
- **Mới (tải theo yêu cầu)**: **Fernet** (token `gAAAAAB…`), khóa Fernet 32 byte trong `base.db` bảng `modelFile`. File giải ra là **ONNX** thật (ir_version 7, producer pytorch).

Khóa nằm ở: `~/Library/Application Support/MagiMir/database/base.db` (app cũ) — bảng `model` (join theo `modelId`) + `modelFile` (key, fileName).

---

## 3. Định dạng container "cnndata" (`*_ov.xml`)

8 file `*_ov.xml` là container độc quyền Meitu. Đã đảo ngược hoàn toàn (`cnndata_extract.py`):

- Header = **3 cặp (offset:u64, size:u64)**:
  - sec0 = descriptor `<?xml><cnndata>` (tên output)
  - sec1 = **trọng số FP32** (= file `.bin` OpenVINO)
  - sec2 = **topology OpenVINO IR**, bị **XOR key 12 byte** `3060700204083f6f7274787f`
- Bất biến: `off1=48+size0`, `off2=off1+size1`, `off2+size2=EOF`; `max(offset+size)` các layer Const = đúng size sec1.

Lưu ý: topology là **IR đã biên dịch CPU-plugin** (`cpu_plugin_opset`) → `openvino.read_model` từ chối. Cần transpile (mục 4).

---

## 4. Transpile OpenVINO IR → ONNX chuẩn

`ov_ir_to_onnx.py` dựng lại graph ONNX, ánh xạ op plugin → op public:
`LeakyRelu`, `PowerStatic→Mul/Add/Pow`, `FullyConnected→Gemm/MatMul+bias`, `Convolution/ConvolutionBackpropData→Conv/ConvTranspose`, `Interpolate→Resize` (dựng lại sizes đủ rank), `MatMul(transpose_a/b)→+Transpose`, `ReduceMean` axes-attribute (opset13), ép `int32→int64` cho shape, **inline khối `Subgraph[SnippetsOpset]`** (attention), **phân rã Gelu**.

Kết quả: **8/8 transpile + chạy trong onnxruntime**.

Kiểm chứng (`validate_onnx_vs_mnn.py`, tự dò hoán vị input): **corr 1.000000** trên `Hm4Cpv1` (matting), `Tcv5s` (2 output), `Ttbscv1A` (segmentation), `Ttmscv1B` (attention). (3 model `F*sch` không cross-check được vì bản MNN twin tự lỗi shape-inference — không phải lỗi transpile.)

---

## 5. Chạy inference thật

- **Het** (`headMatting`, MNN) → mask đầu/tóc chuẩn.
- **`cubeo_style_pipeline.py`** — một lệnh: `Het (mask) → Ttmscv1B (style transfer)`.
  - `python3 cubeo_style_pipeline.py --input ảnh.jpg [--reference look.jpg] [--panel]`
  - Chuyển style/tông màu theo ảnh reference đã hoạt động rõ rệt.
- **Tách nền**: `humanInstance` (HisJ, YOLOv8-seg) → cutout người sạch, nền trong suốt.

Output demo trong `output/`.

---

## 6. `megatron.vpk` / Manis — trạng thái hiện tại

- Hai VPK đã được tách hoàn toàn bằng parser ChaCha20: `megatron.vpk` **854/854** entry và `megatron_conf.vpk` **3481/3481** entry; không thiếu file và không sai hash.
- Nhóm model trong archive gồm **31 `.manis`**, **35 `.manisa`**, **16 `.dtu`**, **87 `.bin`** ở VPK chính và **24 `.bin`** ở VPK cấu hình. `.dtu` là gói operator theo thiết bị, không phải graph chính.
- Con số **31/31** chỉ nói về nhóm `.manis`; không được hiểu là toàn bộ model/asset AI trong Kumoo. Đặc biệt 87 `.bin` còn chứa các họ như `mtface_parsing*.bin` (6 biến thể); các entry đã được tách khỏi VPK nhưng định dạng graph, trọng số và contract chạy độc lập của nhóm `.bin` chưa được xác nhận đầy đủ. Vì vậy tài liệu không tuyên bố “toàn bộ Kumo đã phân tích xong”.
- Cả **31/31 `.manis`** đã qua đúng decoder nội bộ của Manis và được xuất thành FlatBuffer Mizar plaintext trong `manis_decrypted/`. Schema graph, tensor, constant, lượng tử tuyến tính 16-bit và các operator cần thiết đã được phục dựng bằng clean-room correlation trong `tools/mizar_to_onnx.py`.
- Cả **35/35 `.manisa`** đã được xuất thành protobuf `.mlmodel` trong `coreml_decrypted/`. Trình kiểm tra độc lập chỉ liên kết `CoreML.framework`, không dùng `Manis.framework`, đã tạo asset và load CPU thành công **35/35**.
- Trong 31 model Mizar, **20 model** có CoreML twin chính thức và được route sang CoreML; **11 model còn lại** đã được chuyển thành ONNX tự chứa trong `independent_models/`. Validator ONNX Runtime CPU không import/link Manis hay Mizar đã chạy suy luận thành công **11/11**, gồm cả `PhotoFaceContour` và `restoreteeth` (3 output).
- `independent_models/manifest.json` là bảng route đủ **31/31**; `independent_models/validation_report.json` lưu smoke test tự chứa của 11 ONNX. `independent_models/numerical_parity_report.json` cùng hai báo cáo seed bổ sung xác nhận **11/11 model, 15/15 output tensor** đạt `allclose(atol=1e-4, rtol=1e-4)` so với Mizar CPU. Chi tiết operator và cách tái lập nằm trong `MIZAR_ONNX_NUMERICAL_PARITY.md`.
- Manifest đầy đủ gồm đường dẫn, kích thước và SHA-256 nằm ở `model_decryption_manifest.json`.

### 6.1. Chức năng của 11 model ONNX clean-room

Chức năng dưới đây được đối chiếu từ đường dẫn model, tên module/filter trong binary app gốc và hình dạng I/O của graph. Với hai bộ phân loại `MTCheek`/`MTJaw`, nhãn ý nghĩa chi tiết của từng class không nằm trong model nên chỉ ghi đúng chức năng đã xác nhận, không tự đặt tên class.

| Model ONNX | I/O công khai | Vai trò trong app |
|---|---|---|
| `20260203_440epoch_sim_remove_expend_modify` | RGB `1×3×192×192` → feature map `1×96×96×96` | Model đặc trưng của `MTAutoExposure`; cung cấp đặc trưng để pipeline tự động ước lượng/chỉnh phơi sáng. |
| `365` | RGB `1×3×256×512` → map `1×4×256×512` | Model của `AIBeautyGlassesFilter`; phân tích/xử lý vùng kính và sinh bản đồ 4 kênh cho bước lấy `GlassInfo`, mask và blend hiệu ứng kính. |
| `Expelliarmus` | RGB `1×3×1024×1024` → offset `1×2×1024×1024` | Model `cloth_outline` của `GPUImageClothOutlineOffsetFilter`; dự đoán trường dịch chuyển 2D để sửa/làm gọn đường viền quần áo hoặc cơ thể. |
| `MTCheek_model` | crop xám `1×1×123×123` → 2 score | Phân loại đặc trưng/hình dạng vùng má (`MTAIENGINE_MODEL_FACE_CHEEK`) cho phân tích khuôn mặt. |
| `MTJaw_model` | crop xám `1×1×219×219` → 3 score | Phân loại đặc trưng/hình dạng hàm (`MTAIENGINE_MODEL_FACE_JAW`) cho phân tích khuôn mặt. |
| `PhotoFaceContour` | RGB `1×3×480×320` → 2-class map `1×2×480×320` | Phân đoạn đường bao/toàn vùng khuôn mặt; mask được dùng để giới hạn các hiệu ứng làm đẹp trong vùng mặt. |
| `eye_segment` | RGB eye crop `1×3×64×128` → map `1×3×64×128` | Phân đoạn vùng mắt thành bản đồ 3 kênh; app yêu cầu crop được neo từ 130 điểm khuôn mặt. |
| `hairSeamer_full` | RGBA `1×4×385×513` → ba map `2/1/3` kênh | Phục hồi/tinh biên tóc (`MTHairSeamer`): cung cấp ba đầu ra cho hậu xử lý đường viền và sợi tóc bằng thinning/seaming. |
| `haircut_1104_1024_epoch_740_1624_new4` | RGBA `1×4×1024×1024` → RGB `1×3×1024×1024` | Sinh ảnh vùng tóc cho `GPUImageHairCutFilter`; dùng trong mô phỏng/chỉnh tóc (hair growth/haircut) rồi blend theo hair/instance/edge mask. |
| `restoreteeth` | RGB `1×3×256×256` → class `1×2`, mask `1×1×256×256`, RGB `1×3×256×256` | Phục hồi răng: phân loại trường hợp, sinh mask răng và ảnh RGB đã tái tạo để hậu xử lý/blend. |
| `skintone_0411_384_epoch_850_2` | RGB `1×3×384×384` → RGB `1×3×384×384` | Chỉnh/đồng đều tông da cơ thể (`MTSkinToneMapping`/`GPUImageSkinToneBodyAPIFilter`) trước khi blend bằng skin và instance mask. |

### 6.2. Phòng thử nghiệm làm đẹp chân dung

- `portrait_beauty_lab/` là ứng dụng React + FastAPI chạy cục bộ. Pipeline hiện dùng 10 model: `Fd`, `Ga2`, `Lp106`, `PhotoFaceContour`, `facialsmooth`, `bruse_healing`, `skintone`, `Het`, `ChpsJy`, `hairSeamer_full`; cộng operator LUT trắng da, `KumoFaceLift`, `KumoFaceFill`, `HairColorFilter` và material trang điểm Kumo.
- `Ga2.onnx` đã có runner MNN độc lập. Contract đã sửa ngày 2026-08-16: Fd lấy 5 điểm mắt–mũi–miệng, căn affine từng mặt về RGB `1×3×224×224`, chuẩn hóa ImageNet, rồi softmax **một đầu 9 lớp kết hợp**. Cách giải cũ BGR 112px và chia giả thành `2 + 7` đã bị loại vì gán cả nữ, trẻ em và nam thành nữ trên ảnh gia đình. Trên hai ảnh lỗi thực tế, contract mới trả lần lượt `woman, man` và `woman, child, man`. Server quy 9 lớp về 5 slot `man/woman/child/oldwoman/oldman` của preset Gốc, sắp mặt từ trái sang phải; UI hiển thị avatar tròn của từng crop, đánh dấu xác suất dưới 0,8 và vẫn cho sửa tay.
- Mỗi khuôn mặt có contour, landmark-safe mask và cường độ riêng. Bốn thanh UI là hệ số `0..100%` nhân với slot riêng, không còn lấy slot nữ áp cho toàn ảnh. Giá trị Gốc chính: nam `1/90,0,0,0`; nữ `100/100,55,16,10`; trẻ em `100/90,0,0,0`; nữ/nam lớn tuổi `100/100,29,12,0` (skin-fleck/flaw, smooth, tone, white).
- Sửa lỗi ảnh nhóm `PhotoFaceContour.onnx không tạo đủ mask riêng`: mỗi box Fd nay được crop riêng theo đúng tỷ lệ input `2:3`, tránh để mặt nhỏ lẫn người bên cạnh. Nếu contour của riêng một mặt vẫn rỗng, server dựng mask an toàn từ 106 điểm Lp của chính mặt đó và tiếp tục xử lý các mặt còn lại; không callback sang model khác. Log ghi số mặt, kích thước crop và coverage của lần fallback.
- Đường suy luận dùng MNN CPU, ONNX Runtime CPU và Apple CoreML CPU; không import/gọi Manis/Mizar và không callback sang detector/model thay thế.
- Không được coi output `skintone` là ảnh RGB trực tiếp. Contract `GPUImageSkinToneBodyAPIFilter` phục hồi từ binary gốc mã hóa `clamp((RGB-skinRGB)*0.5+127.5)` trước model và giải mã `clamp((modelRGB-126)*2+skinRGB)` sau model. Bỏ hai bước này từng làm kết quả chuyển xám; lỗi đã có regression test về độ bão hòa.
- Giao diện hỗ trợ chọn/kéo-thả/dán ảnh, so sánh trước/sau và tải ảnh kết quả. Ngày 2026-08-16, **Trang điểm Pro** được mở đầy đủ từ bộ Kumo gốc: 11 nhóm, 139 material, 25 set; gồm Set, lông mi, son bóng, khối, má hồng, mắt cười, lens, lông mày, kẻ mắt, tạo khối sáng, phấn mắt và điểm nhấn. UI dùng nguyên thumbnail/texture/config Kumo. Compositor TypeScript giữ đúng Rectangle, Flip, Mask, HeadMaskPath, ORGBA, opacity và BlendMode, rồi neo từng lớp bằng 106 landmark Lp trên từng khuôn mặt theo hệ chuẩn 1000×1500. Chọn set/material/màu/cường độ tự ghép lại cục bộ sau 80 ms, không gọi lại model và không cần nút chạy. Ba son MPLIPSTICKV2 cũ ở server bị tắt trong luồng UI để tránh chồng material.
- **PhotoBooth** đã mở đủ danh mục gốc: 84 preset thuộc 9 nhóm, dùng đúng cover trong `preset_covers/`, giữ `param_count` và toàn bộ `all_params` thay vì chỉ tám khóa màu cơ bản. Bridal 01 hiện đọc **362 khóa gốc** gồm màu, HSL, grading, da theo năm profile và vật liệu makeup. **Blend theo ảnh** nạp 11 bộ / 47 ảnh tham chiếu gốc, hỗ trợ thêm ảnh mẫu do người dùng tải lên và bốn thanh live cho cường độ, tông, màu, độ sáng. Lớp grade/makeup chạy live từ cache sau debounce 80 ms; backend chạy lại khi contract da theo preset thay đổi. Phần blend dùng implementation độc lập của LAB/Reinhard, không giả nhận là graph `Tcv5s` đã được giải mã chính xác. Các shader GPU độc quyền chưa thu được bytecode vẫn được ghi rõ là phép dựng tương đương, chưa phải so khớp số học từng pixel với Kumo gốc.
- Nhóm **Nâng cơ & Đầy đặn** đã mở đủ contract Kumo: 4 vùng nâng (`fore_head_smooth`, `periorbital_smooth`, `malars_smooth`, `perioral_smooth`) và 10 vùng đầy đặn (`fore_head_fillers`, `tear_trough`, `apple_cheek_fillers`, `jowl_fill`, `nose_fillers`, `aegyosal_fill`, `eye_socket_fillers`, `brow_arch_fill`, `chin_fillers`, `angulus_oris_fill`). UI dùng nguyên 14 thumbnail `faceguide` Kumo, mỗi nhóm có thanh 0..100 và tự chạy sau 120 ms. Operator `KumoFaceLift/KumoFaceFill` nắn cục bộ theo 106 landmark và mask riêng từng khuôn mặt; vùng ngoài mặt giữ nguyên. `MTCheek/MTJaw` được giữ đúng vai trò classifier, không giả làm operator morph.
- Màu tóc đã mở và chạy độc lập: `Het` tạo matte đầu 512px và giữ quyền tạo silhouette tóc/vật che nhìn thấy; các thành phần Het chạm seed tóc `ChpsJy` được phục hồi đầy đủ nên lọn tóc bên hông hoặc phía sau bàn tay không còn bị bỏ đen. `ChpsJy` chỉ có 6 lớp, không có nhãn bàn tay riêng và nay chỉ làm seed tóc; không còn lấy lớp mặt/cổ/quần áo của nó trừ khỏi Het vì phép trừ đó nhận nhầm các dải tóc tối, tạo lỗ đen. Operator CPU `ForegroundSkinOcclusion` lấy màu da đại diện từ `PhotoFaceContour + Lp` trên chính ảnh, loại pixel tóc trước khi nối thành phần và giới hạn độ sáng theo da thật, rồi loại tay/ngón tay trước khi ghép màu; đây là hậu xử lý nội bộ, không callback hay model thay thế. `hairSeamer_full` nhận RGB + matte thô `1×4×385×513`, nhưng output của nó luôn bị chặn lại bởi silhouette Het nên không thể tô trở lại lên tay/găng đã loại. Operator `HairColorFilter blendType=3` chạy đúng `SetLum + ClipColor` phục hồi từ shader Kumo. Vì vậy tóc phía sau vật che vẫn được nhuộm, còn bàn tay và vật tiền cảnh giữ nguyên pixel gốc; convex hull đủ 106 landmark vẫn bảo vệ mắt, mũi, chân mày và da mặt. `haircut` mô phỏng cắt/tạo kiểu vẫn là chức năng riêng chưa mở; `MTCheek/MTJaw` vẫn chỉ là classifier và body-shape vẫn cần pose/warp operator ngoài graph.
- UI màu tóc dùng trực tiếp tám thumbnail gốc `cubeo_app/public/assets/haircolor/01.jpg..08.jpg`, không tạo swatch thay thế. Thứ tự map là `heicha`, `shumeihong`, `haiwanghong`, `huizong`, `zangju`, `ziranhei`, `lanzi`, `heiqiao`; material/config đọc từ `megatron_extracted/megatron_conf/haircolor/`. Mức 100 trên thanh UI bằng `defaultAlpha` gốc từng preset và bị chặn bởi `maxAlphaRatio` gốc.
- Luồng thao tác đã chuyển sang auto-run: tải ảnh xong tự xử lý; model/profile da debounce 420 ms, còn material son và màu tóc debounce 120 ms. Nút chạy thủ công đã loại bỏ. Theo đúng kiến trúc editor Kumo, server cache riêng base retouch và `hairMask` của ảnh hiện hành; chọn preset/cường độ tiếp theo chỉ chạy shader/material, không suy luận lại Het/ChpsJy/HairSeamer. Ảnh lớn dùng texture phân tích 1600 px và matte tóc 1280 px (model thật chỉ nhận 224–513 px), sau đó ghép alpha/hiệu ứng trở lại ảnh nguyên kích thước nên nền và vùng ngoài mask vẫn giữ pixel gốc. UI kiểm tra health mỗi 2,5 giây và khi cửa sổ được focus để tự nối lại sau khi Python server restart; sequence ID ngăn response cũ ghi đè lựa chọn mới. Lỗi mask/model không còn làm UI gán nhầm trạng thái server offline.
- UI desktop dùng bố cục editor hai cột toàn viewport: live preview cố định bên trái và panel công cụ cuộn độc lập bên phải, không còn sidebar + tiêu đề + contract kỹ thuật chiếm ba cột. Panel có thanh nhảy nhanh giữa khuôn mặt, làm đẹp da, màu tóc, nâng/đầy, trang điểm và PhotoBooth; pipeline kỹ thuật nằm trong mục thu gọn. Breakpoint dưới 900 px chuyển thành bố cục dọc cho thiết bị nhỏ.
- Nghiệm thu cập nhật ngày 2026-08-16: build/lint và 22 kiểm thử API + 2 kiểm thử giao diện tự động thành công; gồm decoder 9 lớp Ga2, API phân tích lúc upload, ảnh ghép 3 khuôn mặt, fallback Lp106 khi một PhotoFaceContour trong nhóm rỗng, override profile thủ công, ảnh mặt nhỏ, bốn thanh da 0..100, ba material son, tám thumbnail tóc, 14 thumbnail `faceguide`, danh mục `9/84` PhotoBooth và thư viện `11/47` ảnh tham chiếu, hồi quy operator nâng/đầy đặn chỉ đổi vùng mặt được chọn, end-to-end Het + ChpsJy + HairSeamer + shader màu trên ảnh thật, hồi quy giữ nguyên vật che, nối lại tóc phía sau vật che, loại bàn tay màu da ngay cả khi ChpsJy không xuất lớp tay, không khoét tóc khi ChpsJy nhận sai các dải tóc thành vật che và xác nhận lần đổi material sau tái sử dụng cả base/matte. Log ảnh người dùng trước tối ưu từng ghi nhận 187,6 giây, trong đó riêng mask tóc là 180,3 giây. Benchmark có kiểm soát trên ảnh kiểm thử 4467×4800: lượt đầu giảm từ 13,25 xuống khoảng 3,26 giây; đổi màu sau khi cache giảm từ 4,42 xuống khoảng 1,31 giây (chưa tính 120 ms debounce UI). Health API xác nhận 10 model, `fallback_models=false`.

---

## 7. Danh mục công cụ

| File | Chức năng |
|---|---|
| `decrypt_models_v2.py` | Giải mã model từ base.db (Fernet + AES-CTR), tự nhận định dạng; `--scan` kiểm định thư mục đã giải mã |
| `cnndata_extract.py` | Tách container cnndata → OpenVINO `.xml` + `.bin` + descriptor |
| `ov_ir_to_onnx.py` | De-obfuscate + transpile OpenVINO IR → ONNX chuẩn (`--all`, `--run`) |
| `validate_onnx_vs_mnn.py` | So khớp số học ONNX vs MNN twin |
| `cubeo_style_pipeline.py` | Pipeline một lệnh Het → Ttmscv1B (+reference) |
| `tools/lldb_manis_unpack.py` | Bắt payload FlatBuffer sau decoder Manis |
| `tools/lldb_coreml_dump.py` | Xuất protobuf CoreML plaintext từ `.manisa` |
| `tools/manis_batch_probe.cpp` | Nạp và giải mã hàng loạt `.manis` |
| `tools/manis_coreml_batch_probe.cpp` | Nạp hàng loạt `.manisa` đúng backend CoreML |
| `tools/coreml_independent_validator.mm` | Kiểm tra `.mlmodel` không phụ thuộc Manis |
| `tools/mizar_flatbuffer_probe.py` | Đọc và kiểm tra FlatBuffer Mizar không cần schema/runtime độc quyền |
| `tools/mizar_schema_recovery.py` | Đối chiếu 20 cặp Mizar/CoreML để phục dựng operator ID |
| `tools/mizar_to_onnx.py` | Chuyển graph, constant, weight lượng tử và operator Mizar → ONNX |
| `tools/export_independent_mizar.py` | Xuất lại toàn bộ 11 model Mizar-only bằng một lệnh |
| `tools/validate_independent_mizar.py` | Chạy 11 ONNX bằng CPU và kiểm tra output hữu hạn/tự chứa |
| `tools/manis_oracle_runner.cpp` | Chạy Mizar CPU làm oracle kiểm thử và dump output/tensor ID |
| `tools/compare_mizar_onnx.py` | So khớp 15 output tensor của 11 ONNX với Mizar CPU |
| `tools/compare_mizar_intermediates.py` | Định vị operator lệch bằng tensor trung gian |
| `tools/dump_mizar_attrs.py` | Dump field/blob attribute để phục dựng schema có kiểu |
| `tools/build_independent_mizar_manifest.py` | Dựng bảng route độc lập đủ 31 model |
| `model_dictionary.md` | Danh mục 100 model + chức năng |

Thư mục dữ liệu:
- `decrypted_models/` — 100 model đã giải mã (92 MNN + 8 cnndata)
- `ov_models/` — OpenVINO IR tách từ cnndata
- `onnx_models/` — 8 ONNX transpile chạy được
- `freshly_decrypted/` — model mới giải mã từ Mac
- `manis_decrypted/` — 31 FlatBuffer Mizar plaintext
- `coreml_decrypted/` — 35 protobuf CoreML `.mlmodel` plaintext
- `independent_models/` — 11 ONNX từ model chỉ có Mizar + manifest/validation report
- `output/` — ảnh kết quả demo

---

## 8. Kết luận

Toàn bộ model đã đóng gói trong hai VPK đã được lấy ra. Trong 66 file model Manis/CoreML, **66/66 đã giải mã** và **35/35 `.manisa` đã load độc lập bằng CoreML**. Toàn bộ **31/31 `.manis`** hiện có đường chạy không dùng Manis/Mizar: 20 model route sang CoreML twin và 11 model chỉ có Mizar route sang ONNX clean-room. Nhóm 11 ONNX đã chạy CPU độc lập và đạt numerical parity **11/11 model, 15/15 output tensor, trên 3 lượt input** so với runtime Mizar CPU gốc. Mizar chỉ còn là oracle kiểm thử, không nằm trong đường chạy phát hành.
