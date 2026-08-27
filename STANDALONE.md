# Phạm vi dự án độc lập

Thư mục này là bản đóng gói độc lập của Lumi Portrait. Mọi thay đổi tiếp theo cho giao diện, FastAPI, pipeline model, PhotoBooth, trang điểm và màu tóc phải thực hiện trong thư mục này; không sửa `cubeo_app` để phục vụ Lumi Portrait.

## Cấu trúc tự chứa

- `app/`: frontend React.
- `server/`: FastAPI và ba runner `Fd`, `Ga2`, `Lp`.
- `models/independent/`: PhotoFaceContour, SkinTone và HairSeamer cho pipeline chân dung tự chứa.
- `models/decrypted/`: Fd, Ga2, Lp, Het và ChpsJy.
- `models/coreml/`: FacialSmooth và BruseHealing.
- `models/face_color/`: LUT trắng da.
- `assets/`: thumbnail tóc, makeup, faceguide, 84 PhotoBooth preset và capture forensic không tham gia runtime.
- `public/filters/`: 39 texture LUT 64³ gốc, đủ cho toàn bộ 39 ID LUT khác rỗng mà 84 PhotoBooth preset tham chiếu; không có đường dẫn runtime về dự án tham chiếu.
- `materials/`: material son và tám material màu tóc.

Không có symlink và backend không chứa đường dẫn tới `cubeo_app`, `independent_models`, `decrypted_models`, `coreml_decrypted`, `kumoo_materials` hoặc `megatron_extracted` bên ngoài dự án.

## Cổng riêng

- Frontend: `4417`
- Backend: `8417`

Hai cổng này tách khỏi bản thử nghiệm cũ `4317/8317`, cho phép chạy đồng thời mà không gọi nhầm API.

## Hợp đồng nhận diện tóc Kumo

- Binary Kumoo tách `PhotoHair / HairSegment` khỏi `PhotoHead / HeadSegment`; `Het` không được dùng làm biên cuối của tóc.
- Bundle độc lập chưa có `PhotoHair.manis`, nên `ChpsJy` hair class là fallback offline. Input đúng là RGB float `0..1`; plane tóc quyết định silhouette, còn Het chỉ xác nhận thành phần liên thông thuộc đầu.
- `HairSeamer` chỉ refine trong vùng support tóc đủ tin cậy; phần tip/đuôi tóc mờ được giữ bằng alpha theo xác suất `ChpsJy`, không mở rộng thành mảng nhuộm đặc.
- So pixel trên cùng ảnh Kumoo ở `0/45/100` hiệu chuẩn fallback matte bằng `0,75`; đây là hệ số mask, không phải cường độ material.
- `defaultAlpha` trong config là vị trí thanh mặc định khi chọn màu. Giá trị người dùng kéo được áp trực tiếp, rồi chặn bởi `maxAlphaRatio`.

## Chạy và dừng

```bash
pnpm install
python3 -m pip install -r server/requirements.txt
./start_local.sh
./stop_local.sh
```

Trước khi tiếp tục sửa hiệu ứng, luôn kiểm tra `http://127.0.0.1:8417/api/health` để xác nhận đang dùng đúng backend độc lập.

## Hợp đồng lớp lens Kumo

- `Path` của lớp makeup phải được chuẩn hóa qua backend giống `Texture`, nếu không mask mắt bị trình duyệt bỏ qua im lặng.
- Cường độ hiệu dụng của một lớp trong Set là `SetAlpha × MakeupAlpha / 100`. Ví dụ preset **Tạp Chí Nhật** dùng Set 70 và lớp lens 50, nên lens chạy ở 35%, không phải 70%.
- `MUFACE_EYEPUPIL` với operation `16/17` là hai tròng riêng. Texture vuông phải giữ tỉ lệ; Lp106 chỉ cho contour mí mắt nên renderer phải tìm tâm mống mắt thật trong eye crop đã chuẩn hóa rồi đặt tròng theo tâm đó. Không được cố định ở tâm Rectangle hoặc kéo giãn phủ toàn bộ hình chữ nhật của mắt.
- `Path` của lớp tròng Kumo là PNG xám đen–trắng không có alpha: renderer phải đổi luminance thành alpha trước `destination-in`. Nếu dùng alpha gốc của PNG thì toàn bộ hình vuông tròng mắt sẽ phủ lên mí và lòng trắng.
- Khi lớp tròng khai báo `NeedPupilHighLight=1`, renderer phải lấy vùng mắt gốc trong hệ tọa độ Kumo và chừa các điểm bắt sáng trung tính của đồng tử khỏi lớp lens. Không được giảm cường độ preset để che lỗi vì sẽ làm sai toàn bộ các lớp trang điểm còn lại.
- Tìm tâm mống mắt phải bị giới hạn trong mask `Path`, loại biên mí/lông mi và kẹp độ dịch chuyển theo kích thước eye crop; các lớp chồng của cùng một mắt (như Lens 09) phải dùng chung một tâm đã phát hiện.
- Operation `16/17` định cỡ theo vòng màu hữu hiệu chứ không theo toàn bộ PNG. Ba asset Lens **09/10/14** có vòng màu chiếm phần lớn texture nên renderer chuẩn hóa hệ số vẽ tương ứng `0.72/0.75/0.60`; giữ nguyên texture, opacity và 11 lens còn lại.
- Đã kiểm thử trực tiếp preset **Tạp Chí Nhật** và **Tốt Nghiệp** ngày 2026-08-17: hai tròng giữ kích thước tự nhiên, không phủ lòng trắng và vẫn giữ điểm bắt sáng của mắt thật.

## Hợp đồng lớp lông mày Kumo

- Bốn material Mày **10–13** dùng `LocateMethod=48` và chỉ chứa một texture/Rectangle phía trái. Operator Kumo đặt texture gốc rồi lật ngang qua `canonical.axis` để tạo phía phải; renderer độc lập phải thực hiện cả hai lần vẽ và tô màu trên toàn alpha của cặp mày.
- Preset **Sang trọng** dùng material `hengliumei`, texture `4ed6d88921dcfd2f.png` cho cả hai bên mày.
- Texture này không phải ảnh RGBA đã tách nền: lông mày là vùng xám sáng trên một hình chữ nhật đen gần như đục và metadata gốc khai báo `mask: false`.
- Operator Kumo dùng độ sáng của texture làm độ phủ. Renderer độc lập phải chuẩn hóa luminance thành alpha, bỏ hoàn toàn nền đen, rồi mới tô màu của Set; không được vẽ texture thẳng lên ảnh.

## Hợp đồng lớp phấn mắt Kumo

- Phấn mắt **10** (`tangguo`) có 11 lớp ảnh và một `Script` Kumo; các lớp mắt gốc dùng `LocateMethod=6/7` để neo riêng vào Lp106. Bản JSON legacy không giữ các khóa này, nên renderer phải bù tâm aperture đã đo: trái `(-10.5, -3)`, phải `(+17, -7.7)` trong hệ canonical. Lớp nền `710×275` không được dịch.
- Phấn mắt **13** (`Mi0000BF9UTcGbc0`) khai báo `RightEyeUseLeftEyeMirrorModelPoints=1` và `NeedProfileOptimization=1`. Renderer phải bù aperture trái `(-11.5, 0)` và phải `(+11, -4.7)` trước affine Lp106; không áp các giá trị này cho material khác.

## Hợp đồng lớp kẻ mắt Kumo

- Kẻ mắt **12** (`Mi0000bqyVE4oJcV`) dùng mask đơn phía trái cùng `RightEyeUseLeftEyeMirrorModelPoints=1`; phía phải được Kumo tái tạo từ model point đối xứng. Renderer phải bù neo trái `(+10.5, -0.5)` và phải `(-11, -5.2)` trong hệ canonical trước affine Lp106.
- Việc sửa được giới hạn đúng nhóm `eyebrow` và material `hengliumei`, không thay đổi lens, phấn mắt hoặc các material lông mày đã có alpha thật.

## Hợp đồng lớp son môi Kumo

- Các vật liệu son có bộ ba semantic `operation = 7`, `filterType = 4`, `muType = 1`. Texture của lớp này là **coverage/material map**, không phải ảnh màu cuối để dán trực tiếp lên môi.
- Màu cuối lấy từ trường `rgb` trong `makeup.json`; renderer dùng alpha texture làm mask với `source-in`, rồi hòa lên môi để giữ sáng tối và chi tiết môi gốc.
- Riêng material `07 / zhenghong` dùng `rgb = [202, 50, 48]`, `opacity = 80` và mức gốc trên giao diện là `50%`. Texture này có 2.331 pixel alpha đặc hoàn toàn; nếu dán trực tiếp RGB texture sẽ tạo vệt ngang/khối màu trên môi.
- Nhánh sửa chỉ áp dụng cho phần `mouth` có đúng bộ semantic trên, không thay đổi landmarks, Lens, lông mày hoặc các vật liệu trang điểm khác.
- Đã kiểm thử trực quan ngày 2026-08-17 ở mức phóng 175%: son 07 bám vùng môi, không còn vệt ngang và không tràn ra da. Đây là xác nhận contract compositing 2D; chưa tuyên bố so khớp số học từng pixel với shader/runtime Kumo độc quyền.

## Hợp đồng PhotoBooth Kumo

- Đối chiếu runtime Kumoo desktop ngày 2026-08-20 xác nhận Chuyển màu AI gọi cloud `/v1/colortransfer_v3_async`, tải `colorTransfer.jpg`, rồi mới chạy `EnhanceColorTransfer` cục bộ. Không có artifact offline tổng quát để tái tạo chính xác theo ảnh nguồn. Vì vậy ngày 2026-08-21 standalone đã gỡ toàn bộ UI, state frontend, route API và health contract của Chuyển màu AI/Blend theo ảnh; không thay thế bằng LAB/HSL hoặc LUT đoán gần đúng. Các neutral-atlas đã chụp chỉ là bằng chứng forensic và không tham gia runtime.

- PhotoBooth chỉ tự ghép các material ARP 2D đã có operator tương thích (mày, phấn mắt, kẻ mắt, mi, lens, má hồng và môi). Các metadata full-face như `feature=featurerichang` (`Bronzers`) không được dán trực tiếp bằng canvas `soft-light`; Kumo xử lý chúng qua operator/mesh riêng và việc dán phẳng làm lộ contour map thành mảng trên mặt.
- Mỗi preset là một snapshot JSON độc lập. Bộ giải mã tách `filter`, cân bằng trắng, tone, curve RGB, `hsl_*`, grading/calibration, profile năm đối tượng, material và local-mask thành các namespace riêng; không merge khóa trùng nghĩa và không để lựa chọn chỉnh tay chồng lên snapshot.
- Catalog giữ nguyên các giá trị điều khiển HSL đã giải mã, nhưng không tự suy ra tâm dải màu, falloff hoặc ma trận thay thế khi bảng shader native chưa có. Những phần chưa resolve được ghi riêng trong `decodedOnlyOperators`/`unresolvedNativeArtifacts` và không tham gia render mặc định.

- Trường `all_params.filter` không phải metadata trang trí. Khi có `filter_id` và `filters_lut_alpha`, renderer tải texture LUT 512×512 tương ứng, diễn giải thành cube 64×64×64 (8×8 tile) và nội suy tám ô lân cận như texture filtering của shader Kumo.
- Sau LUT, frontend chỉ chạy các material/profile có asset hoặc model tương thích đã khôi phục. Các operator tone, cân bằng trắng, saturation/vibrance, curve RGB, calibration, color grading, HSL và detail chưa đủ bảng/ma trận native nên chỉ được lưu trong snapshot, không chạy qua công thức canvas mô phỏng.
- Executor canvas semantic từng dùng để phỏng đoán tone/HSL đã được xóa khỏi standalone, không chỉ ngắt import. PhotoBooth chỉ còn gọi hợp đồng snapshot và artifact đã khôi phục; các namespace preset vẫn độc lập và cường độ preset chỉ blend một lần ở cuối pipeline.
- Mức LUT hiệu dụng là `Cường độ preset × filters_lut_alpha / 100`; Bridal 01 dùng `Fa0000epgjUhXLrB` ở 70% khi thanh preset là 100.
- 39 LUT gốc đã được sao chép vật lý vào `public/filters/`, bao phủ đủ mọi `filter_id` khác rỗng trong 84 snapshot. Test catalog bắt buộc kiểm tra 84 ID preset duy nhất, đúng 362 khóa/preset và không LUT nào bị thiếu; renderer không còn được phép im lặng bỏ lớp màu vì thiếu asset.
- Năm mảng profile da trong preset là cường độ theo `man/woman/child/oldwoman/oldman`, nhưng phải tôn trọng cờ bật/tắt đi kèm. Chúng không được nhân với bốn thanh làm đẹp thủ công đang mặc định 0. `skin_tone_face_alpha` dùng `skin_tone_flag`; `skin_tone_body_alpha` là stage chroma độc lập, giữ kênh đỏ/luminance ổn định và được ghép trong skin mask đã xác thực để không làm lạnh nền. Bridal 01 nữ có body tone 54%; Story 04 nữ có body tone 40%. API công bố mức thực qua `X-Kumo-Effective-Body-Tone`.
- Catalog giữ đủ 362 khóa metadata của Bridal 01 để kiểm toán, nhưng UI phải phân biệt “khóa metadata Kumo” với số operator đã khôi phục; không ghi rằng cả 362 khóa đều đã được thực thi.
- Nhận diện `Fd + Ga2 + Lp106 + PhotoFaceContour` được cache theo pixel nguồn, tách khỏi cache kết quả preset. Đổi Bridal/Scene trên cùng một ảnh chỉ tái dùng mặt, profile, landmark và mask; trạng thái UI phải ghi “Áp preset …”, không lặp nhãn “Nhận diện khuôn mặt”.
- PhotoBooth là snapshot hoàn chỉnh và có quyền sở hữu riêng: chọn preset sẽ xóa trạng thái chỉnh tay của làm da, tóc, nâng/đầy và Makeup Pro; chọn lại một công cụ chỉnh tay sẽ tắt PhotoBooth. Preset không được merge với state cũ. `all_params` được gửi nguyên snapshot vào backend; mỗi tầng chỉ đọc namespace mà operator của nó sở hữu.
- Mọi lượt ghép preview đi qua một promise chain duy nhất. Request cũ được kiểm tra và bỏ trước mỗi bước cấp phát; các click nhanh được coalesced về preset cuối. Makeup nhận chính blob preview 1600 px (không phải blob camera gốc), tránh nhiều canvas full-resolution chạy song song gây OOM/crash tab.
- Pipeline được chia thành hai scheduler giống Kumo: `modelRenderChain` tuần tự hóa inference da/hình học và `previewRenderChain` xử lý makeup/LUT đã xác minh. Analyze ảnh mới có `AbortController` riêng, và mọi tầng dùng generation id để kết quả cũ không thể ghi đè kết quả mới.
- Cache nền PhotoBooth được gắn phiên bản renderer và chỉ băm những khóa mà backend thật sự thực thi. Metadata chỉ-giải-mã không được giả vờ tham gia kết quả hoặc làm mất cache.
- Cache LUT phía trình duyệt dùng ID bất biến kèm phiên bản renderer `kumo-photo-v8-native-artifacts`; đổi hợp đồng giải mã tự bust cache cũ đúng một lần, trong khi các click preset sau vẫn tái dùng bitmap LUT đã giải mã.
- PhotoBooth mặc định chỉ thực thi artifact đã khôi phục chắc chắn: LUT 64³ 512×512, alpha của snapshot và material/profile đã có asset/model. Các khóa exposure/HSL/curve/grading/detail vẫn được giải mã và giữ riêng trong snapshot nhưng không đi qua `CanvasColorEngine` mô phỏng; thiếu bảng, ma trận hoặc mask native thì không được suy diễn công thức. Quy tắc này loại bỏ việc áp màu hai lần, ảnh tối quá mức và sai màu giữa các preset.
- Cân bằng trắng Kumo cần `gain[3]`, `colorMatrix[9]` và `analogGain[3]`; tone cần `toneCurve[65536]`; curve RGB cần bốn spline 65.536 mẫu. Các artifact đã resolve này không nằm trong catalog preset, nên standalone ghi rõ `decodedOnlyOperators`/`unresolvedNativeArtifacts` và không sinh hệ số thay thế.
- Binary và snapshot runtime Kumo chỉ được dùng để kiểm toán offline. Bản standalone không import, không symlink và không giữ đường dẫn runtime tới ứng dụng/cache/dự án tham chiếu.
- Audit toàn bộ 84 snapshot bắt buộc giữ 362 khóa hữu hạn/preset, 198 mảng năm-profile, 84 cover 136×136 và 39 LUT 512×512. Mọi ID trang điểm an toàn mà preset gọi được kiểm tra chéo với đúng nhóm material và mọi texture/mask/clip phải tồn tại.
- Hai lông mi chỉ xuất hiện trong snapshot `Travel 06` (`Mi0000Q56zV1aamA`) và `Grad 04` (`Mi00002I63gwAXR7`) được giữ trong `assets/makeup/preset-materials.json`, tách khỏi catalog 139 material lõi. API hợp nhất theo `part key + material dir`, vì vậy mỗi preset vẫn sở hữu snapshot riêng và không thể ghi đè/chồng lựa chọn của preset khác.
- Profile làm đẹp backend và lớp màu frontend là hai executor độc lập. Mỗi executor chỉ nhận dữ liệu thuộc namespace của mình; không dùng kết quả lớp trước để suy ra hoặc tự hiệu chuẩn thông số Kumo còn thiếu.
- 2026-08-19: Fixed global color equations (Exposure/Contrast) in backend to use Legacy algorithms matching Kumo, resolving the 'pale' issue for Bridal 05.
- 2026-08-22: Hợp nhất Mask đa tầng (Multi-layer Mask Fusion): Kết hợp `PhotoFaceContour` với đa giác 106 điểm `Lp106` (bao trọn 33 điểm viền xương hàm và vòm trán nâng lên `0.88 * eye_span`). Khắc phục triệt để hiện tượng hụt mask tại mép quai hàm trái và vùng trán trên sát chân tóc.
- 2026-08-22: Hợp đồng "Mịn da giữ kết cấu" (Texture-Preserving Smooth): Ứng dụng tách tần số với thuật toán High-Pass Coring (lọc ngưỡng biên độ `|h| <= 0.038`) trên nền Neural Model `facialsmooth_0529`. Giữ 115% vi hạt vân da và lỗ chân lông tự nhiên, đồng thời triệt tiêu đốm tàn nhang và kích hoạt AI Blemish Healing.
- 2026-08-22: Hợp đồng "Sáng da tự nhiên" (Skin Whitening): Hiệu chuẩn đường cong đáp ứng của bảng màu 64³ LUT `white_lookup_table.png` (`whiteColorTexture`), giúp thanh trượt phản hồi mượt mà từ 0–100% đúng chuẩn độ sáng hồng hào và trong trẻo của Kumo gốc.
- 2026-08-22: Hợp đồng "Chọn tông da" & "Màu ưa chuộng" (Kumo Skin Tone Palette): Khôi phục bộ palette chọn tông da tròn 8 sắc thái Kumo (`skin1.png` đến `skin6.png` cùng tông sô cô la/espresso). Ứng dụng sampler 16³ 3D LUT (`_apply_16_cube_lut`) kết hợp slider "Màu ưa chuộng" điều khiển trực tiếp độ phủ trên mặt nạ da.
- 2026-08-22: Hợp đồng "Đều màu da (Nhiều người)" (`skin_tone_multiple_alpha`): Thuật toán trích xuất anchor chroma $(Cr, Cb)$ chuẩn từ vùng da trung tính và áp dụng bộ lọc làm mịn sắc độ (`_apply_kumo_group_skin_tone`). Triệt tiêu hoàn toàn hiện tượng loang lổ vùng đỏ/vàng trên gò má và cổ, đưa toàn bộ sắc độ da về trạng thái đồng nhất, mịn màng chuẩn Kumo gốc.
- 2026-08-22: Tối ưu UI làm đẹp da: Gỡ bỏ thanh "Mịn da tự nhiên", tập trung toàn bộ vào "Mịn da giữ kết cấu" chuẩn nơ-ron CoreML; đồng bộ hiển thị chỉ số của tất cả các thanh trượt theo thang điểm trực quan 0–100%.
- 2026-08-23: Khắc phục hiện tượng sáng/mịn đè lên tóc che mặt: Tích hợp mặt nạ phân đoạn tóc `ChpsJy` (`hair_exclusion = np.clip(1.0 - hair_prob * 1.6, 0.0, 1.0)`) vào `landmark_skin_masks`. Bảo vệ 100% các sợi tóc mai, tóc mái và tóc rơi ngang trán/má không bị sáng da, mịn da hay biến đổi màu đè lên tóc.
- 2026-08-23: Hợp đồng "Làm mịn & Nâng cơ" (`face_flat_lift_switch`): Tích hợp biến dạng lưới nâng cơ neo theo 106 điểm `Lp106` (`_face_operator_anchors`) cùng bộ lọc làm mờ nếp nhăn cục bộ cho 4 vùng Trán (`fore_head_smooth`), Mắt (`periorbital_smooth`), Giữa mặt (`malars_smooth`), Miệng (`perioral_smooth`) chuẩn cơ chế nâng cơ và phẳng nếp gấp Kumo gốc.
- 2026-08-23: Khắc phục chấm đen ở lông mày khi áp preset PhotoBooth: Hiệu chuẩn bộ gating `_kumo_fleck_flaw_weight` bám sát theo mặt nạ phát hiện khuyết điểm `Expelliarmus.onnx` (`raw_flaw`), triệt tiêu việc rò rỉ artifact viền inpainting nơ-ron từ mô hình `fuxiCreator` lên vùng chân mày và mắt.
- 2026-08-23: Hợp đồng "Bộ lọc (Filters) & Bộ lọc AI (AI Filter)":
  * Hệ thống Bộ lọc tĩnh (Static 3D LUT Pipeline): Khôi phục toàn bộ kho 124+ 3D LUT $64^3$ ($512\times 512$) chia thành 8 dòng chuyên nghiệp: Dòng P (Chân dung & Studio — 23 bộ lọc P01..P23), Dòng FUJI (Giả lập film Fujifilm — 5 bộ lọc NC, CC, NN, X100...), Dòng F (Màu phim & Điện ảnh — 13 bộ lọc F01..F13), Dòng O (Ngoại cảnh & Du lịch — 17 bộ lọc O01..O17), Dòng C (Đêm & Thành thị — 6 bộ lọc C01..C06), Dòng N (Cổ phong Á Đông — 4 bộ lọc N01..N04), Dòng B (Đen trắng nghệ thuật — 4 bộ lọc B01..B04), Dòng H (Studio & Ảnh cưới chuyên sâu — 52 bộ lọc).
  * Quy trình 3 tầng xử lý Bộ lọc tĩnh: (1) Nội suy 3D LUT $512\times 512$ trilinear qua `applyFilterLut` / `_apply_64_cube_lut`; (2) Mặt nạ bảo vệ da AI `SkinProtectionMask` từ `PhotoFaceContour` / `Fd.onnx` bảo vệ vùng da mặt tự nhiên, không bị ám xỉn màu film; (3) Sinh hạt film nhựa cổ điển (`film_granularity` Silver Halide) phân bổ tự nhiên ở vùng Shadows/Midtones.
  * Hệ thống Bộ lọc AI (AI Filter Pipeline — 7 Bộ lọc AI thông minh): Tích hợp 7 phong cách AI (`pm5` Tự nhiên chân dung, `vcr02` Màu Film đậm đà, `cn12` Cổ điển Retro, `tr16` Trong trẻo tươi tắn, `ln03` Thanh khiết sáng rực, `ln08` Tone lạnh Nhật Bản, `ln10` Tone ấm vàng chanh) được điều khiển qua chuỗi mạng nơ-ron học sâu (Deep Neural Networks): Phân tích bối cảnh & dải sáng (`astra`), Cân bằng tương phản động HDR Adaptive Tone Curve (`ultraman`), Sinh ma trận phong cách AI StyleNorm (`eva`), Tinh chỉnh HSL cục bộ 8 kênh (`flamigo`, `finizen`, `fuecoco`, `wattrel`).
  * Hệ thống Chuyển màu AI (AI Color Transfer): 10 Album mẫu tham chiếu màu gốc Kumo (Korean Spring Editorial, Vintage Film, Neo-Chinese, Beige Family...) ứng dụng thuật toán chuyển đổi màu Reinhard LAB Color Grade trong thời gian thực 60fps trên Live Canvas.







- 2026-08-24: Hợp đồng "Cắt vùng mặt chuẩn 5 điểm neo" (Keypoint-based Face Alignment): Loại bỏ hoàn toàn sự phụ thuộc vào Bounding Box của `Fd.onnx` (vốn dễ bị bóp méo khung trên ảnh nhóm có tỷ lệ không vuông). Tái tạo ma trận Affine xoay và nội suy hình học dựa vào 5 điểm neo (hai mắt, mũi, mép) để ép crop 192x192 chuẩn xác tuyệt đối. Fix dứt điểm lỗi makeup bị lệch / lơ lửng ngoài khuôn mặt trên ảnh chụp nhóm đông người.
- 2026-08-24: Phân tách vùng tóc theo giới tính (Gender-aware Hair Mask): `_hair_mask` giờ đây nhận vào `active_flags` dựa trên profile của các khuôn mặt. Các hạt giống connected component (`Het`) sẽ được so sánh giữa vùng tròn trên đỉnh đầu của các khuôn mặt hợp lệ (Nữ) và không hợp lệ (Nam, Trẻ em). Nếu một mảng tóc có số lượng điểm neo thuộc khuôn mặt nam lớn hơn hoặc bằng thuộc khuôn mặt nữ, toàn bộ mảng tóc đó sẽ bị loại bỏ khỏi `hair_mask`, ngăn chặn việc áp dụng màu tóc sai đối tượng trong ảnh nhóm.
- 2026-08-24: Tối ưu hoá Gender-aware Hair Mask: Thay vì dùng Connected Components (có thể bị sai nếu tóc nam và nữ chạm nhau tạo thành 1 mảng lớn), thuật toán chuyển sang sử dụng Soft Voronoi Mask. Vẽ vùng hạt giống cho Nữ (xanh) và Nam (đỏ), sau đó tính toán vùng độc quyền của Nam bằng cách so sánh cường độ Gaussian Blur (được tính trên kích thước scale 1/8 để đảm bảo tốc độ cực nhanh < 8ms). Vùng độc quyền này sẽ triệt tiêu hoàn toàn bất kỳ mảng tóc nào lọt vào vùng mặt/đầu của Nam giới ngay cả khi chúng dính liền với tóc Nữ.
- 2026-08-24: Kích hoạt toàn diện 7 lớp Trang điểm (Makeup Pro) & Làm trắng da tự động theo 84 Preset PhotoBooth: Tích hợp đầy đủ danh sách vật liệu 2D (`blush`, `eye`, `eyebrow`, `eyelash`, `eyeshadow`, `eyesocket`, `mouth`, `eyeliner`) trích xuất từ 362 thông số Kumo theo từng nhóm nhân khẩu học vào `renderKumoMakeup`. Đồng thời hiệu chuẩn cờ làm trắng `tone_alphas` (`skin_tone_face_alpha`), giúp toàn bộ 84 preset tái tạo màu sắc, makeup mắt/môi/mày và tone da chuẩn 1:1 theo bản gốc Kumoo.
- 2026-08-25: Hợp đồng "Lông mi 2.5D & Pháp tuyến viền mí mắt" (2.5D Eyelash & Radian Normals):
  * **Cơ chế gốc Kumoo (`YunXiu-PC`):** Đã phân tích binary C++ và file cấu hình `eyelash10_config.plist`, xác nhận module `Use2Dot5DEyeLash = 1`, `RightEyeUseLeftEyeMirrorModelPoints = 1`, và bộ lọc shader `GPUImageUpperEyelidRadianSmoothFilter`.
  * **Thuật toán uốn mí (`drawPiecewiseEyelidWarp`):** Sử dụng 5 điểm viền mí mắt trên (`35, 41, 40, 42, 39` mắt trái; `93, 96, 94, 95, 89` mắt phải). Tính toán vector tiếp tuyến $T(t)$ và vector pháp tuyến $N(t) = (-T_y, T_x)$ hướng lên trên Canvas 2D. Các điểm khóe ngoài tự động xòe nhẹ góc nghiêng ra phía thái dương.
  * **Chiều cao dải mi (`halfH = 110px`):** Mở rộng dải bao phủ từ 40px lên 110px để bảo lưu trọn vẹn 100% các ngọn mi dài mềm mại của vật liệu `eyelash10` (Preset Ngọt ngào, Kiểu Trung) mà không bị xén cụt hoặc kéo dãn lên lông mày.
  * **Hòa trộn màu mi (`source-atop`):** Thay thế cơ chế double-draw (`destination-in` làm bình phương alpha $a \times a = a^2$ gây nhạt mi) bằng `source-atop` để phủ màu nâu `[108, 74, 41]` trực tiếp lên các pixel có alpha, giữ 100% độ nét tơ mảnh ban đầu của ảnh PNG.
  * **Khắc phục lỗi mắt đục:** Giới hạn cờ `isPupil` và logic `protectPupilHighlights` chỉ kích hoạt khi `pick.partKey === "lens"`. Ngăn chặn việc vật liệu Mắt cười / Aegyo sal (`Mi0000jqGa1V9RB6`) bị nhận diện nhầm thành lens tròng mắt.

- 2026-08-25: Kiến trúc 3 Tầng của Preset Chân Dung (3-Tier Preset Pipeline):
  * **Tầng 1 (Retouch da nơ-ron):** Backend `/api/portrait/beautify` chạy CoreML C++ runner `coreml_predict` tích hợp `FacialSmooth` (mịn da tần số giữ vân) + `BruseHealing` (xóa mụn & khuyết điểm) + `SkinTone` (trắng hồng).
  * **Tầng 2 (Chiếu sáng chân dung & Tóc):** Điều chỉnh exposure, tăng sáng vùng da và tóc tự nhiên thông qua mặt nạ `PhotoSkin` và `PhotoHair` (`ChpsJy`).
  * **Tầng 3 (Trang điểm 2D Pro Decals):** Áp dụng 7 bộ phận trang điểm bám khít Lp106 (Son môi Ramp LUT, Má hồng khuếch tán, Phấn mắt, Hốc mắt, Điểm nhấn, Chân mày, Lông mi 2.5D).
  * **Quy tắc điều khiển UI:** Khi người dùng chỉ tải ảnh lên (chưa chọn preset), tất cả thanh trượt mặc định ở mức `0` để người dùng toàn quyền tự chỉnh thủ công; khi bấm Preset (PhotoBooth hoặc Set Makeup), hệ thống kích hoạt thông số chuẩn của Preset đó.

- 2026-08-25: Chuẩn hóa Toàn diện 15 Kiểu Phấn Mắt Chuẩn Gốc Kumoo (Eyeshadow 01..15):
  * **Khôi phục màu tự nhiên:** Loại bỏ hoàn toàn mã màu tint nhân tạo (`[155, 136, 119]` và `[11, 1, 0]`) bị parse nhầm từ chuỗi cờ `ORGBA`. Sử dụng 100% màu sắc gốc tự nhiên của các file texture PNG (cam đất nung, nâu khói, hồng đào, mận than, lavender ánh sao).
  * **Đồng bộ hóa Shader đa lớp:** Phân tách chính xác các lớp nền mắt `Multiply` (độ sâu hốc mắt), lớp kẻ mắt & đuôi mắt xếch `Multiply` (sắc nét không lem), và lớp nhũ kim tuyến `Screen` / `Lighten` tỏa sáng đa tầng.
  * **Ma trận Cục bộ Mắt (`LocalEyeAffine`):** Co dãn và xoay chính xác theo 3 điểm neo của từng mắt (`[35, 39, 40]` mắt trái; `[89, 93, 94]` mắt phải), tự động nhận diện các lớp phủ toàn mặt (`locateMethod: 2`) để áp dụng ma trận toàn phần.
  * **Triệt tiêu hiện tượng sọc dọc và bảo vệ tròng mắt:** Bóc tách phấn mắt khỏi hàm uốn mi dạng dải tam giác, kết hợp bảo toàn nhãn cầu và con ngươi sáng trong long lanh.
