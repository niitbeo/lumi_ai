# Lumi Portrait Standalone — Kumo Beauty Lab

Dự án React + FastAPI độc lập cho **Làm đẹp chân dung**. Toàn bộ mã frontend, backend, model đang dùng và asset Kumo cần thiết nằm trong thư mục này. Runtime không đọc mã hoặc tài nguyên từ `cubeo_app`, nhờ vậy công việc tiếp theo trên Cubeo AI không thể ghi đè ứng dụng này. Inference chạy cục bộ bằng MNN CPU, ONNX Runtime CPU và Apple CoreML CPU, không nạp Manis/Mizar.

## Model đang dùng

- `Fd.onnx` (MNN FlatBuffer): model Kumoo định vị khuôn mặt/crop.
- `Ga2.onnx` (MNN FlatBuffer): phân nhóm xử lý theo diện mạo cho từng mặt. Fd căn từng mặt bằng 5 điểm mắt–mũi–miệng trước khi đưa vào Ga2; tensor sau căn là RGB `1×3×224×224`, chuẩn hóa ImageNet. Output là **một đầu softmax 9 lớp kết hợp**, không phải `2 giới tính + 7 tuổi`; lớp `0..2` quy về trẻ em, các cặp lớp trưởng thành quy về nam/nữ và hai lớp cuối quy về nữ/nam lớn tuổi. Contract cũ BGR 112px đã bị loại sau khi gán sai cả ba người trong ảnh gia đình.
- `Lp.onnx` (MNN FlatBuffer): lấy 106 landmark mắt, chân mày, mũi, môi và viền mặt.
- `PhotoFaceContour.onnx`: model Kumoo tạo mask khuôn mặt trên từng crop.
- `facialsmooth_0529_192_384_epoch_1050.manisa.mlmodel`: graph CoreML Kumo làm mịn da, input/output RGB `1×3×384×384`, miền `0..1`.
- `Expelliarmus.onnx`: graph ONNX Kumoo `1×3×1024×1024 → 1×2×1024×1024`, sinh `flawMaskTexture` và `nevusMaskTexture` cho `GPUImageBlackHeadCleanFilter`.
- `fuxiCreator_20251225.manisa.mlmodel`: graph CoreML đã phục hồi từ Kumoo cho `GPUImageBlackHeadCleanFilter`/`GPUImageFleckFlawCleanFilter`, input RGB `1×3×960×960`, output `1×4×960×960`. Đây là nguồn `resColor` native cho thanh `Xóa mụn & tàn nhang (Mặt)`.
- `skintone_0411_384_epoch_850_2.onnx`: model Kumoo xử lý residual màu da ở kích thước `384×384`.
- `Het.onnx` (MNN FlatBuffer): matte toàn đầu `512×512`; chỉ dùng để xác nhận thành phần parsing nào nối với đầu, không cắt silhouette tóc.
- `ChpsJy.onnx` (MNN FlatBuffer): fallback cục bộ cho `PhotoHair/HairSegment` native còn thiếu trong bundle. Model nhận RGB float `0..1`, trả parsing 6 lớp tóc/mặt/cổ/quần áo; lớp tóc giữ quyền tạo silhouette. Graph không có lớp bàn tay riêng nên pipeline ghép thêm `ForegroundSkinOcclusion`, lấy màu da đại diện từ `PhotoFaceContour + Lp` của chính ảnh để bảo vệ tay tiền cảnh.
- `hairSeamer_full.onnx`: nhận RGB + matte thô `1×4×385×513`, tinh biên và sợi tóc trước khi ghép màu.

Pipeline bắt buộc theo thứ tự: `Fd → Ga2 → Lp106 → PhotoFaceContour → FacialSmooth → Expelliarmus → fuxiCreator_20251225 → SkinTone → SkinWhiteningLUT → KumoFaceLift → KumoFaceFill → ChpsJyHairSegmentFallback → HetComponentSeed → ForegroundSkinOcclusion → hairSeamer_full → HairColorFilter → Kumo ARP Makeup`. Mỗi mặt có mask và profile riêng; mask của `Lp` khoét mắt, chân mày, mũi và môi khỏi vùng retouch để không làm nhòe ngũ quan. Nếu `Lp` không trả đủ 106 điểm cho mọi khuôn mặt, API báo lỗi và không xử lý mù.

Compositor đọc đúng thứ tự năm slot của preset Kumo **Gốc** đã phục hồi: `man`, `woman`, `child`, `oldwoman`, `oldman`. Các mức chính là:

| Slot | Skin fleck / flaw | Mịn mặt | Skin tone | Skin white |
| --- | ---: | ---: | ---: | ---: |
| Nam | `1 / 90` | `0` | `0` | `0` |
| Nữ | `100 / 100` | `55` | `16` | `10` |
| Trẻ em | `100 / 90` | `0` | `0` | `0` |
| Nữ lớn tuổi | `100 / 100` | `29` | `12` | `0` |
| Nam lớn tuổi | `100 / 100` | `29` | `12` | `0` |

Ga2 ước lượng slot cho từng khuôn mặt ngay khi tải ảnh; đây là ước lượng theo diện mạo, không phải xác nhận danh tính. Kết quả được sắp từ trái sang phải và mỗi dòng có avatar tròn cắt từ đúng box Fd để đối chiếu. Giao diện luôn cho sửa thủ công từng mặt trước khi chạy và đánh dấu `cần xác nhận` nếu xác suất softmax dưới 0,8. Nguồn Gốc còn khai báo low/high và neutral-gray nhưng các operator chưa phục hồi không bị giả lập bằng bộ lọc tự chế.

Nhóm **Điều chỉnh da · PhotoBot nhanh** giữ bốn thanh lõi Kumo nhưng luôn bắt đầu ở `0`, nên tải ảnh mới không tự làm đẹp. Ga2 vẫn chọn đúng profile nam/nữ/trẻ em/người lớn tuổi để đưa ra mức gợi ý riêng từng mặt. Thanh điều khiển là tỉ lệ `0..100%` của gợi ý đó, còn con số lớn trên giao diện là thông số Kumo thực đang được áp dụng (ví dụ Nữ kéo Mịn da hết thanh sẽ hiện `55`, không hiện `100`).

Server dùng mask `PhotoFaceContour`, ước lượng màu da đại diện theo histogram độ sáng của filter gốc, rồi thực hiện đúng giao thức residual đã phục hồi từ `GPUImageSkinToneBodyAPIFilter.cpp`:

```text
input  = clamp((RGB - skinRGB) × 0.5 + 127.5, 0, 255)
output = clamp((modelRGB - 126.0) × 2.0 + skinRGB, 0, 255)
```

Ngoài mask, pixel input SkinTone được đặt về mức trung tính 127. Không có bộ lọc mịn da/độ ấm tự chế, không có callback sang model khác và không có thanh thông số giả. Graph `skintone` chỉ có một input ảnh `1×3×384×384`; các trường `skinTone24`, `skinBrightLvl`, `skinHueDelta` thuộc contract C++ ngoài graph và không phải input trực tiếp của ONNX.

Thanh `Xóa mụn & tàn nhang (Mặt)` chạy theo contract đã phục hồi từ Cubeo AI/Kumoo: `GPUImageBlackHeadCleanFilter`/`GPUImageFleckFlawCleanFilter` lấy `flawMaskTexture` và `nevusMaskTexture` từ `Expelliarmus.onnx`, lấy RGB `resColor` từ `fuxiCreator_20251225.manisa.mlmodel`, rồi qua compositor tương đương shader gốc `flawMask * skinMask * deepSmooth`. `fuxiCreator` vẫn cung cấp kênh thứ tư dạng tanh validity matte (`[-1,1] → [0,1]`) làm floor phụ cùng kernel low-frequency `lowFrequencyImage - logImage`, nhưng không còn là nguồn mask chính. Trước khi blend, backend áp công thức residual của shader native `oriColor + (resColor - lowPassTexture)` để giữ vân da gốc; `nevusMaskTexture` bảo vệ nốt ruồi khi `NevusRemovalFlag` đang tắt như preset Gốc. Mask riêng cho blemish dùng `PhotoFaceContour` nhưng chỉ bảo vệ mắt, mày và môi; mũi/cheek/forehead vẫn được xử lý giống hướng `skinMaskTexture` của Kumoo hơn. Mức `0` bỏ qua graph phục hồi; mức `100` dùng alpha đầy đủ của slot/profile đang chọn, bao gồm `flaw_clean_alpha`. Hai model `Expelliarmus.onnx` và `fuxiCreator_20251225.manisa.mlmodel` đã được đóng gói nội bộ trong standalone.

`skin_white_alpha`/“trắng da” của Kumo là một LUT/operator ngoài graph, không phải model neural riêng. Server chạy CPU tương đương `shader_506.glsl`: nội suy LUT 64³ từ `faceColor/white_lookup_table.png`, rồi hòa tối đa ở mức Gốc 10 chỉ trong skin mask.

Nhóm **Nâng cơ & Đầy đặn** đã phục hồi theo đúng contract Kumo và chạy tự động trên từng mặt bằng 106 landmark `Lp` cùng mask mặt đã xác nhận. Bốn vùng nâng cơ map đúng các tham số `fore_head_smooth`, `periorbital_smooth`, `malars_smooth`, `perioral_smooth`; mười vùng đầy đặn map đúng `fore_head_fillers`, `tear_trough`, `apple_cheek_fillers`, `jowl_fill`, `nose_fillers`, `aegyosal_fill`, `eye_socket_fillers`, `brow_arch_fill`, `chin_fillers`, `angulus_oris_fill`. Mỗi nhóm có thanh cường độ `0..100`, chọn lại ô đang bật để tắt hiệu ứng. UI dùng nguyên 14 thumbnail Kumo đã đóng gói trong `assets/faceguide/`, không tạo hình minh họa thay thế. Operator chỉ nắn vùng cục bộ bên trong mặt tương ứng; `MTCheek/MTJaw` vẫn là classifier, không bị dùng giả làm model morph.

Nhóm **Trang điểm Pro** nạp thư viện ARP Kumo đã trích xuất: **11 nhóm, 141 material và 25 set gốc**. Trong đó 139 material nằm trong catalog lõi và hai material lông mi chỉ được các snapshot PhotoBooth `Travel 06`/`Grad 04` tham chiếu được giữ tách riêng ở `assets/makeup/preset-materials.json`; API hợp nhất theo `part key + material dir`, không ghi đè catalog lõi và không chồng state giữa các preset. Các tab gồm `Set`, lông mi, son bóng, khối, má hồng, mắt cười, lens, lông mày, kẻ mắt, tạo khối sáng, phấn mắt và điểm nhấn. UI dùng trực tiếp thumbnail/material Kumo; pipeline lấy đúng 106 điểm Lp106 theo các nhóm viền mặt, hai mắt, hai chân mày, mũi và hai vòng môi. Với material Lens, `AdditionalTexture` là ảnh màu nhìn thấy còn `Path` chỉ là alpha mask mắt; renderer bắt buộc đủ cặp này và sẽ bỏ qua lớp sai contract thay vì tô mảng trắng lên mắt. Vật liệu son Kumo có `operation=7`, `filterType=4`, `muType=1` dùng alpha texture làm coverage và trường `rgb` trong manifest làm màu son; không dán trực tiếp RGB texture vì riêng son 07 sẽ tạo vệt ngang. Catalog đồng thời lưu lại `Rectangle`, `LocateMethod`, `Operation`, `ORGBA`, `NeedMask`, opacity và `BlendMode` gốc của các lớp FacePart 2D để kiểm thử và truy vết.

Lưu ý phạm vi: đường 2D ARP đang chạy độc lập và đã được kiểm thử trực tiếp. Các material 3D dùng `Lua3DFA`/`LuaLip3d` cần mesh operator riêng; tài liệu không tuyên bố chúng khớp số học với runtime Kumo cho đến khi operator đó được đối chiếu riêng.

Compositor chạy cục bộ trong trình duyệt trên ảnh nền đã qua model. Nó dùng đủ 106 landmark của `Lp` để tính affine mắt–miệng từ hệ tọa độ chuẩn `1000×1500`, rồi áp texture lên **từng khuôn mặt**. Mỗi tab có lựa chọn “Không”, material, màu gốc và thanh cường độ riêng; chọn một trong 25 set sẽ gán đồng thời đúng danh sách material/màu của set đó. Thay set, material, màu hoặc thanh trượt được ghép lại sau debounce `80 ms`, không gọi lại server và không cần nút “Chạy model”. Son môi cũ phía server được đặt về 0 để không chồng hai lớp lên nhau.

Nhóm **PhotoBooth** nạp nguyên danh mục đã đóng gói trong `assets/presets/presets.json`: **84 preset thuộc 9 danh mục**, kèm đúng thumbnail trong `assets/preset_covers/`. Catalog giữ cả `param_count` và `all_params` thay vì chỉ tám khóa màu cơ bản; riêng Bridal 01 có **362 khóa gốc** gồm màu cơ bản, HSL, color grading, da theo năm profile và vật liệu trang điểm. Chọn danh mục, thumbnail hoặc kéo thanh cường độ đều dựng lại preview sau debounce `80 ms`; profile da lấy trực tiếp cờ/cường độ của snapshot, nhân cường độ preset đúng một lần và không phụ thuộc bốn slider chỉnh tay. Frontend chỉ dựng LUT 64³ có artifact gốc và material 2D an toàn từ cache; HSL/tone/grading thiếu bảng hoặc shader native vẫn được giải mã nhưng không chạy qua công thức mô phỏng. Metadata full-face như `Bronzers`/`ReconstructorV2p5D` không bị dán phẳng như ARP 2D vì Kumo chạy chúng bằng mesh/operator riêng; PhotoBooth bỏ qua các lớp đó cho tới khi operator tương ứng được phục hồi, tránh lộ bản đồ khối kỹ thuật trên da.

Chức năng **Chuyển màu AI / Blend theo ảnh** đã được gỡ khỏi standalone ngày 2026-08-21. Đối chiếu runtime Kumo cho thấy kết quả được tạo riêng cho từng ảnh nguồn qua dịch vụ cloud `/v1/colortransfer_v3_async`; dự án không có artifact offline tổng quát để tái tạo chính xác và không dùng công thức LAB/HSL gần đúng. Frontend không còn hiển thị mục này, backend không còn công bố route color-transfer. Các capture forensic còn nằm trong `assets/` chỉ dùng để đối chiếu, không tham gia runtime.

Với ảnh nhóm, `PhotoFaceContour` nhận crop `2:3` riêng quanh từng box Fd để mặt nhỏ không bị lẫn người bên cạnh. Nếu output contour của đúng một mặt rỗng/không đủ coverage, server không còn trả lỗi 422 cho toàn ảnh: mặt đó dùng vùng an toàn dựng từ chính 106 điểm `Lp` của nó (hàm dưới, thái dương và trán), còn các mặt có contour hợp lệ giữ nguyên output model. Đây là hậu xử lý hình học cùng pipeline Kumo, không gọi model thay thế; log ghi rõ số thứ tự mặt, kích thước crop và coverage khi nhánh an toàn được dùng.

Nhóm **Màu tóc** bám kiến trúc native đã kiểm tra trong binary Kumoo 7.9.3: `PhotoHair.manis / MTAIENGINE_MODEL_PHOTOSEG_HAIR → HairSegment → HairSeamer → HairColorFilter`; `HeadSegment/Het` là nhánh khác. Bundle standalone chưa có artifact `PhotoHair.manis`, vì vậy dùng lớp tóc của `ChpsJy` làm fallback cục bộ, với đúng contract RGB float `0..1`. Plane tóc này giữ quyền tạo silhouette; `Het` chỉ làm seed chọn thành phần liên thông thuộc đầu, nên hai lọn đuôi vẫn được giữ khi nằm ngoài matte Het. `ForegroundSkinOcclusion` và vùng tai suy từ `Lp106` bảo vệ tay/tai; `HairSeamer` tinh biên trong support tóc. Đối chiếu pixel cùng ảnh ở Kumoo `0/45/100` cho thấy fallback thô mạnh hơn matte native; hệ số mềm `0,75` được lưu riêng ở matte (đo được `0,750` tại mức 45 và `0,736` tại mức 100), không trộn vào thanh cường độ. Operator màu dùng shader `blendType=3`: `SetLum(material, Lum(source))`, `ClipColor`, rồi hòa qua matte. `defaultAlpha` là vị trí thanh mặc định khi chọn preset; kéo `45` gửi alpha `45%`, sau đó mới giới hạn bởi `maxAlphaRatio`.

| ID | Thumbnail gốc | Preset/config | Default / max |
| --- | --- | --- | ---: |
| `01` | `assets/haircolor/01.jpg` | `heicha` — 黑茶 | `50 / 50%` |
| `02` | `assets/haircolor/02.jpg` | `shumeihong` — 树莓红 | `60 / 80%` |
| `03` | `assets/haircolor/03.jpg` | `haiwanghong` — 海王红 | `63 / 100%` |
| `04` | `assets/haircolor/04.jpg` | `huizong` — 灰棕 | `80 / 100%` |
| `05` | `assets/haircolor/05.jpg` | `zangju` — 脏橘 | `60 / 80%` |
| `06` | `assets/haircolor/06.jpg` | `ziranhei` — 自然黑 | `63 / 85%` |
| `07` | `assets/haircolor/07.jpg` | `lanzi` — 蓝紫 | `70 / 88%` |
| `08` | `assets/haircolor/08.jpg` | `heiqiao` — 黑巧 | `65 / 85%` |

API phục vụ trực tiếp tám file JPEG trên tại `/api/assets/haircolor/01.jpg`…`08.jpg`; giao diện không tạo swatch/thumbnail thay thế. Material màu đã được đóng gói và đọc từ `materials/haircolor/<preset>/`.

Giao diện tự chạy sau khi Ga2 phân tích xong ảnh. Thay đổi model/profile da được debounce `420 ms`; riêng material son, màu tóc, nâng cơ hoặc đầy đặn dùng cache Kumo và debounce `120 ms`, hủy request cũ rồi gửi lượt mới; không có nút “Chạy model”. Server cache riêng face analysis theo byte ảnh nguồn, base retouch theo đúng contract da/profile và matte tóc theo base: đổi PhotoBooth preset không chạy lại `Fd/Ga2/Lp/PhotoFaceContour` nếu ảnh không đổi, còn LUT/HSL/material/metadata màu không làm mất base cache. Ảnh lớn được phân tích trên texture làm việc 1600 px, matte tóc 1280 px (đều cao hơn input model 224–513 px), rồi chỉ alpha/hiệu ứng được ghép lại lên ảnh gốc nguyên kích thước; nền và chi tiết ngoài mask không bị resize. UI thăm dò `/api/health` mỗi 2,5 giây và khi cửa sổ được focus, nên tự nối lại sau khi Python server khởi động lại mà không cần tải lại trang. Mỗi lượt xử lý có sequence riêng để response cũ không thể ghi đè màu vừa chọn. Lỗi model/mask được hiển thị riêng và không làm API đang trực tuyến bị báo nhầm là mất kết nối.

Ngày 2026-08-16, giao diện được chuyển sang bố cục editor hai cột toàn chiều cao: live preview cố định bên trái, bảng tính năng cuộn độc lập bên phải. Thanh điều hướng nhanh dẫn tới khuôn mặt, da, tóc, nâng/đầy, trang điểm và PhotoBooth; thông tin pipeline kỹ thuật được thu gọn để không chiếm vùng chỉnh ảnh. Trên màn hình nhỏ, hai cột tự xếp dọc và bỏ sticky để giữ thao tác cảm ứng tự nhiên.

Màu tóc và Nâng cơ & Đầy đặn đã hoàn thiện; riêng mô phỏng cắt/tạo kiểu bằng `haircut` vẫn là chức năng khác và chưa được mở. Chỉnh dáng toàn thân vẫn cần body pose + warp/operator ngoài graph. Các mục chưa phục hồi không bị giả lập bằng callback/bộ lọc khác.

## Chạy thử

Chuẩn bị một lần:

```bash
pnpm install
python3 -m pip install -r server/requirements.txt
```

Sau đó, từ thư mục này:

```bash
./run_dev.sh
```

Muốn ứng dụng tiếp tục chạy nền sau khi đóng terminal:

```bash
./start_local.sh
```

Dừng ứng dụng chạy nền:

```bash
./stop_local.sh
```

- React: `http://localhost:4417`
- API: `http://127.0.0.1:8417/api/health`

Model được đọc hoàn toàn từ `models/decrypted/`, `models/independent/` và `models/coreml/` bên trong dự án này. Asset phục vụ UI nằm trong `assets/`; material son và tóc nằm trong `materials/`. Khi chạy trên macOS, server tự biên dịch bridge `server/coreml_predict.mm` vào `.run/`; bridge chỉ dùng Apple CoreML CPU và không dùng runtime Mizar.

## API

- `GET /api/health`: kiểm tra ba runtime độc lập, mười model Kumoo, tám preset tóc, thư viện makeup 141/25, năm profile Gốc và bridge CoreML.
- `GET /api/assets/haircolor/{01..08}.jpg`: trả đúng byte thumbnail tóc Kumo gốc.
- `GET /api/face-volume/library`: trả contract 4 vùng nâng cơ và 10 vùng đầy đặn Kumo.
- `GET /api/assets/faceguide/{asset}.jpg`: trả đúng thumbnail `faceguide` Kumo gốc của từng vùng.
- `GET /api/makeup/library`: trả contract đầy đủ của 11 nhóm, 141 material và 25 set Kumo (139 lõi + 2 material chỉ dùng bởi PhotoBooth).
- `GET /api/assets/makeup/{path}`: trả thumbnail, texture, clip mask và oval mask gốc của Kumo.
- `GET /api/photobooth/library`: trả đủ 9 danh mục, 84 preset PhotoBooth, `param_count` và toàn bộ `all_params` của từng preset.
- `GET /api/assets/presets/{cover}`: trả thumbnail cover PhotoBooth gốc bằng đường dẫn đã kiểm tra an toàn.
- `POST /api/portrait/analyze`: chạy `Fd + Ga2 + Lp`, trả danh sách mặt, box, slot tự động, độ tin cậy, thông số Gốc và 106 landmark cho từng mặt.
- `POST /api/portrait/beautify`: nhận `image`, bốn hệ số da `0..100`, son, `hair_color_strength`, `hair_color_preset` (`none|01..08`), `face_lift_region`, `face_lift_strength`, `face_fill_region`, `face_fill_strength`, `profile_overrides` và tùy chọn snapshot PhotoBooth `photo_preset_params` + `photo_preset_strength`; trả ảnh JPEG giữ nguyên kích thước. Snapshot PhotoBooth là nhánh độc lập, không nhân/chồng với các thanh chỉnh tay.

## Tự kiểm thử

```bash
pnpm test
```

Bộ kiểm thử build giao diện, xác nhận wiring của các model và xác nhận toàn bộ route/UI Chuyển màu AI đã được gỡ. Nó kiểm tra đủ `11/141/25` makeup và `9/84` PhotoBooth, duyệt toàn bộ 84 cover 136×136, 39 LUT 512×512, 362 khóa hữu hạn và 198 mảng năm-profile của từng preset, đồng thời buộc mọi material mà preset gọi phải tồn tại đúng nhóm và đủ texture/mask/clip. Bộ test còn tải asset gốc, trả đủ 106 landmark, đối chiếu từng byte của tám thumbnail tóc và 14 thumbnail nâng/đầy đặn, chạy operator vùng mặt cục bộ, chạy màu tóc qua Het + ChpsJy + HairSeamer + shader Kumo trên ảnh thật, kiểm tra vật che tiền cảnh được giữ nguyên, kiểm tra Ga2 trên ảnh ghép nhiều khuôn mặt, xác nhận preset da không bị slider 0 triệt tiêu, body-tone đúng profile và đổi preset tái sử dụng face analysis.
