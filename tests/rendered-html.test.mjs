import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server-renders the portrait beauty lab", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>Lumi Portrait — AI Beauty Lab<\/title>/i);
  assert.match(html, /Làm đẹp chân dung/i);
  assert.match(html, /Fd \+ Ga2 \+ Lp106/i);
  assert.match(html, /profile riêng từng mặt/i);
  assert.match(html, /9 model \+ 3 operator Kumo/i);
  assert.match(html, /Đang tải catalog Kumo/i);
  assert.doesNotMatch(html, /Your site is taking shape|react-loading-skeleton/i);
});

test("frontend and API are wired to the independent ONNX models", async () => {
  const [page, makeup, photoBooth, photoContract, server, packageJson, bridalLut] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/kumoMakeup.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/photoBooth.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/kumoPhotoContract.ts", import.meta.url), "utf8"),
    readFile(new URL("../server/server.py", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
    readFile(new URL("../public/filters/Fa0000epgjUhXLrB.png", import.meta.url)),
  ]);

  assert.match(page, /127\.0\.0\.1:8417/);
  assert.match(page, /api\/portrait\/beautify/);
  assert.match(page, /api\/portrait\/analyze/);
  assert.match(page, /api\/makeup\/library/);
  assert.match(page, /api\/photobooth\/library/);
  assert.doesNotMatch(
    page,
    /api\/color-transfer|Blend theo ảnh|pickReference|referencePacks|transferSettings|ToneMimic/,
  );
  assert.match(page, /renderKumoMakeup/);
  assert.match(page, /renderPhotoBooth/);
  assert.match(page, /const makeupMaterialCount = makeupLibrary\?\.parts\.reduce/);
  assert.match(page, /makeupCatalogSummary/);
  assert.doesNotMatch(page, /141 vật liệu/);
  assert.match(page, /preparePhotoPreview/);
  assert.match(page, /previewRenderChain/);
  assert.match(page, /modelRenderChain/);
  assert.match(page, /queueProcessImage/);
  assert.match(page, /analysisAbort/);
  assert.doesNotMatch(page, /processingAbort\.current\?\.abort\(\);\s*const requestId = \+\+processingRequest\.current;/);
  assert.match(page, /renderKumoMakeup\(\s*rendered,/s);
  assert.match(page, /sourceImageSizeRef/);
  assert.match(page, /body\.append\("photo_preset_params", JSON\.stringify\(isolatedPreset\.all_params\)\)/);
  assert.match(page, /photoOptions\.preset \? \{\} : selection/);
  assert.match(page, /function activatePhotoPreset/);
  assert.match(page, /leavePhotoPreset\(\);\s*setSkinFleckClean/s);
  assert.match(page, /eyesocket: "Mắt cười"/);
  assert.match(page, /name: part\.key === "eyesocket" \? MAKEUP_TAB_LABELS\.eyesocket : part\.name/);
  assert.match(page, /profile_overrides/);
  assert.match(page, /Tải ảnh kết quả/);
  assert.match(page, /skin_fleck_clean_flag/);
  assert.match(page, /Xóa mụn &amp; tàn nhang \(Mặt\)/);
  assert.match(page, /onInput=.*setSkinFleckClean/);
  assert.match(page, /const \[skinFleckClean, setSkinFleckClean\] = useState\(0\)/);
  assert.match(page, /const \[smoothFaceSkin, setSmoothFaceSkin\] = useState\(0\)/);
  assert.match(page, /const \[skinToneFace, setSkinToneFace\] = useState\(0\)/);
  assert.match(page, /const \[skinWhite, setSkinWhite\] = useState\(0\)/);
  assert.match(page, /Mặc định 0, không tự làm đẹp/);
  assert.match(page, /effectiveSkinValues\(faces, "smooth", smoothFaceSkin\)/);
  assert.match(page, /smooth_face_skin_alpha/);
  assert.match(page, /skin_tone_face_alpha/);
  assert.match(page, /skin_white_alpha/);
  assert.match(page, /33: \{ preset: "yingtao", strength: 100 \}/);
  assert.match(page, /body\.append\("lipstick_alpha", String\(isolatedPreset \? 0 : makeupLipstickStrength\)\)/);
  assert.match(page, /body\.append\("lipstick_preset", makeupLipstickPreset\)/);
  assert.match(page, /const lipstick = KUMO_THEME_LIPSTICK\[theme\.id\]/);
  assert.match(makeup, /function luminanceAlphaMask/);
  assert.match(makeup, /pixels\.data\[index \+ 3\] = Math\.round\(luminance \* sourceAlpha\)/);
  assert.match(makeup, /isPupil \? luminanceAlphaMask\(localMask\) : localMask/);
  assert.match(makeup, /function detectPupilCenter/);
  assert.match(makeup, /pupilCenter\?\.\[0\].*x \+ width \/ 2/s);
  assert.match(makeup, /Mi0000ctJWSsKeyV: 0\.72/);
  assert.match(makeup, /Mi0000j9sVvEjCkG: 0\.75/);
  assert.match(makeup, /Mi0000mhF9q8CLG8: 0\.60/);
  assert.match(makeup, /height \* pupilDrawScale\(pick\.dir\)/);
  assert.match(makeup, /function makeupLayerAnchorOffset/);
  assert.match(makeup, /materialDir === "tangguo"/);
  assert.match(makeup, /\? \[-10\.5, -3\]/);
  assert.match(makeup, /: \[17, -7\.7\]/);
  assert.match(makeup, /materialDir === "Mi0000BF9UTcGbc0"/);
  assert.match(makeup, /\? \[-11\.5, 0\] : \[11, -4\.7\]/);
  assert.match(makeup, /materialDir === "Mi0000bqyVE4oJcV"/);
  assert.match(makeup, /\? \[10\.5, -0\.5\] : \[-11, -5\.2\]/);
  assert.match(makeup, /rawX \+ offsetX/);
  assert.match(makeup, /function eyebrowCoverageMask/);
  assert.match(makeup, /sourceSize\?: \{ width: number; height: number \}/);
  assert.match(makeup, /const scaleX = sourceSize\?\.width[\s\S]*?canvas\.width \/ sourceSize\.width/);
  assert.match(makeup, /const scaleY = sourceSize\?\.height[\s\S]*?canvas\.height \/ sourceSize\.height/);
  assert.match(makeup, /pick\.partKey === "eyebrow"/);
  assert.match(makeup, /pick\.dir === "hengliumei"/);
  assert.match(makeup, /layer\.locateMethod === 48/);
  assert.match(makeup, /canonical\.axis \* 2 - drawX - drawWidth/);
  assert.match(makeup, /drawPlaced\(mirroredDrawX, !layer\.flip\)/);
  assert.match(page, /partKey: entry\.key/);
  assert.match(page, /face_lift_region/);
  assert.match(page, /face_fill_region/);
  assert.match(page, /face_flat_lift_switch/);
  assert.match(page, /face_full_switch/);
  assert.match(page, /api\/assets\/faceguide/);
  assert.match(page, /Mịn da tự nhiên/);
  assert.match(page, /Đều màu da/);
  assert.match(page, /Sáng da tự nhiên/);
  assert.match(page, /Cường độ preset/);
  assert.match(page, /khóa metadata Kumo/);
  assert.match(page, /activatePhotoPreset\(preset\.id, `Áp preset \$\{preset\.name\}`\)/);
  assert.match(page, /PHOTO_PRESET_SAFE_MAKEUP_PARTS/);
  assert.match(page, /if \(!PHOTO_PRESET_SAFE_MAKEUP_PARTS\.has\(part\.key\)\) continue/);
  assert.doesNotMatch(page, /PHOTO_PRESET_SAFE_MAKEUP_PARTS = new Set\(\[[\s\S]*?"feature"/);
  assert.match(photoBooth, /function applyFilterLut/);
  assert.match(photoBooth, /FILTER_LUT_SIZE = 64/);
  assert.match(photoBooth, /MAX_PREVIEW_EDGE = 1600/);
  assert.match(photoBooth, /kumo-photo-v8-native-artifacts/);
  assert.match(photoBooth, /Exact CPU equivalent of Kumo's recovered 512x512 shader/);
  assert.match(photoBooth, /const offset111/);
  assert.match(photoBooth, /await loadFilterLut/);
  assert.match(photoBooth, /buildKumoPhotoExecutionPlan/);
  assert.doesNotMatch(
    photoBooth,
    /color-transfer|applyToneMimic|reference_asset|referenceUrl|ColorTransferSettings/,
  );
  assert.doesNotMatch(photoBooth, /applyColorTransfer|labStats|rgbToLab|Reinhard/);
  assert.doesNotMatch(photoBooth, /applyKumoPhotoAdjustments/);
  assert.doesNotMatch(photoBooth, /enableColorEngine|ColorEngine/);
  assert.match(photoContract, /filters_lut_alpha/);
  assert.match(photoContract, /export function decodeKumoPhotoSnapshot/);
  assert.match(photoContract, /export function buildKumoPhotoExecutionPlan/);
  assert.match(photoContract, /unresolvedNativeArtifacts/);
  assert.match(photoContract, /recoveredOperators/);
  assert.match(photoContract, /white-balance/);
  assert.match(photoContract, /global-tone/);
  assert.match(photoContract, /grading-calibration/);
  assert.match(photoContract, /local-adjustments/);
  assert.match(photoContract, /profile-operators/);
  assert.doesNotMatch(
    `${photoBooth}\n${photoContract}`,
    /KUMO_HSL_HUE_DEGREES_PER_UNIT|KUMO_TEMPERATURE_CHANNEL_GAIN|KUMO_TINT_(?:RED_BLUE|GREEN)_GAIN|bandNormalizer/,
  );
  assert.doesNotMatch(
    `${photoBooth}\n${photoContract}`,
    /Applications\/Kumoo|Library\/Caches\/com\.meitu\.kumoo|cubeo-ai/,
  );
  assert.ok(bridalLut.length > 100_000);
  assert.match(server, /PhotoFaceContour\.onnx/);
  assert.match(server, /skintone_0411_384_epoch_850_2\.onnx/);
  assert.match(server, /Fd\.onnx/);
  assert.match(server, /Ga2\.onnx/);
  assert.match(server, /Lp\.onnx/);
  assert.match(server, /facialsmooth_0529_192_384_epoch_1050\.manisa\.mlmodel/);
  assert.match(server, /Expelliarmus\.onnx/);
  assert.match(server, /fuxiCreator_20251225\.manisa\.mlmodel/);
  assert.match(server, /GPUImageBlackHeadCleanFilter:Expelliarmus\.mask \+ fuxiCreator_20251225\.res/);
  assert.match(server, /white_lookup_table\.png/);
  assert.match(server, /MPLIPSTICKV2/);
  assert.match(server, /_makeup_library_stats/);
  assert.match(server, /KumoMakeupARP:\{makeup_group_count\}-groups\|\{makeup_material_count\}-materials\|\{makeup_theme_count\}-themes/);
  assert.doesNotMatch(server, /139 Kumo ARP materials|139-materials/);
  assert.doesNotMatch(server, /apply_color_grading|_apply_hald_clut/);
  assert.match(server, /KumoFaceLift:4-regions/);
  assert.match(server, /KumoFaceFill:10-regions/);
  assert.doesNotMatch(server, /kumoo-colortransfer-v3-recovered-lut64-v1/);
  assert.doesNotMatch(server, /ColorTransfer:|\/v1\/colortransfer_v3_async|color_transfer_contract|tone_mimic/);
  assert.doesNotMatch(server, /tone_core_base_runtime|tone_mimic_runtime|tone_sr2_runtime/);
  assert.doesNotMatch(server, /_tone_mimic_semantic_mask/);
  assert.match(server, /A PhotoBooth preset is a complete Kumo contract/);
  assert.match(server, /profile\["skin_tone_flag"\] > 0/);
  assert.match(server, /_portrait_analysis_cache/);
  assert.match(server, /Portrait face analysis cache HIT/);
  assert.match(server, /luozhuang/);
  assert.match(server, /CPUExecutionProvider/);
  assert.match(server, /"uses_mizar": False/);
  assert.doesNotMatch(page, /setWarmth|body\.append\("(?:tone|smooth|warmth)"/i);
  assert.doesNotMatch(server, /bilateralFilter|tone: float/);
  assert.doesNotMatch(server, /import\s+(manis|mizar)|from\s+(manis|mizar)/i);
  assert.match(packageJson, /lumi-portrait-standalone/);
});
