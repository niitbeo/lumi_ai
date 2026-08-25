import { buildKumoPhotoExecutionPlan, decodeKumoPhotoSnapshot } from "./kumoPhotoContract";

export type PhotoPresetParams = {
  exposure: number;
  contrast: number;
  temperature: number;
  vibrance: number;
  blackness: number;
  highlight: number;
  whiteness: number;
  shadow: number;
};

export type PhotoPreset = {
  id: number;
  category_id: number;
  category_name: string;
  name: string;
  cover: string;
  param_count: number;
  all_params: Record<string, unknown>;
  params: PhotoPresetParams;
};

export type PhotoPresetLibrary = {
  categories: Array<{ id: number; name: string }>;
  presets: PhotoPreset[];
};

export type PhotoBoothRenderOptions = {
  preset: PhotoPreset | null;
  presetStrength: number;
};

const FILTER_LUT_SIZE = 64;
const FILTER_LUT_TILES = 8;
const MAX_PREVIEW_EDGE = 1600;
const PHOTOBOOTH_RENDER_VERSION = "kumo-photo-v8-native-artifacts";
const filterLutCache = new Map<string, Promise<ImageData | null>>();
const previewBlobCache = new WeakMap<Blob, Promise<Blob>>();

const clamp01 = (value: number) => value < 0 ? 0 : value > 1 ? 1 : value;

async function sourceBlob(source: string | Blob): Promise<Blob> {
  if (source instanceof Blob) return source;
  const response = await fetch(source, { cache: "force-cache" });
  if (!response.ok) throw new Error("Không tải được tài nguyên PhotoBooth.");
  return response.blob();
}

async function decodeSource(source: string | Blob): Promise<ImageBitmap> {
  return createImageBitmap(await sourceBlob(source));
}

function canvasBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => blob ? resolve(blob) : reject(new Error("Không xuất được kết quả PhotoBooth.")),
      "image/jpeg",
      0.95,
    );
  });
}

/**
 * Kumo's live canvas never evaluates the full camera resolution. Keep one
 * 1600 px working copy per backend result; export can still use the untouched
 * server blob later, while preset clicks stay within an interactive budget.
 */
export function preparePhotoPreview(source: Blob): Promise<Blob> {
  const cached = previewBlobCache.get(source);
  if (cached) return cached;
  const pending = (async () => {
    const bitmap = await createImageBitmap(source);
    const scale = Math.min(1, MAX_PREVIEW_EDGE / Math.max(bitmap.width, bitmap.height));
    if (scale === 1) {
      bitmap.close();
      return source;
    }
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const context = canvas.getContext("2d");
    if (!context) {
      bitmap.close();
      throw new Error("Không tạo được canvas xem trước PhotoBooth.");
    }
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
    return canvasBlob(canvas);
  })();
  previewBlobCache.set(source, pending);
  return pending;
}

export async function loadFilterLut(filterId: string): Promise<ImageData | null> {
  const cacheKey = `${PHOTOBOOTH_RENDER_VERSION}:${filterId}`;
  const cached = filterLutCache.get(cacheKey);
  if (cached) return cached;
  const pending = (async () => {
    try {
      const response = await fetch(
        `/filters/${encodeURIComponent(filterId)}.png?v=${encodeURIComponent(PHOTOBOOTH_RENDER_VERSION)}`,
        { cache: "force-cache" },
      );
      if (!response.ok) return null;
      const bitmap = await createImageBitmap(await response.blob());
      if (bitmap.width !== 512 || bitmap.height !== 512) {
        bitmap.close();
        return null;
      }
      const canvas = document.createElement("canvas");
      canvas.width = bitmap.width;
      canvas.height = bitmap.height;
      const context = canvas.getContext("2d", { willReadFrequently: true });
      if (!context) {
        bitmap.close();
        return null;
      }
      context.drawImage(bitmap, 0, 0);
      bitmap.close();
      return context.getImageData(0, 0, canvas.width, canvas.height);
    } catch {
      return null;
    }
  })();
  filterLutCache.set(cacheKey, pending);
  return pending;
}

export function applyFilterLut(
  image: ImageData,
  lut: ImageData,
  amount: number,
): void {
  const blend = clamp01(amount);
  if (blend <= 0) return;
  const src = image.data;
  const table = lut.data;
  const maxCoord = 63 / 255;

  // Exact CPU equivalent of Kumo's recovered 512x512 shader: R/G address
  // one texel inside an 8x8 atlas tile, B selects the two adjacent tiles,
  // and linear sampling blends the eight surrounding texels.
  for (let index = 0; index < src.length; index += 4) {
    if (src[index + 3] === 0) continue;

    const r = src[index] * maxCoord;
    const g = src[index + 1] * maxCoord;
    const b = src[index + 2] * maxCoord;

    const r0 = r | 0, g0 = g | 0, b0 = b | 0;
    const r1 = r0 < 63 ? r0 + 1 : 63;
    const g1 = g0 < 63 ? g0 + 1 : 63;
    const b1 = b0 < 63 ? b0 + 1 : 63;

    const rMix = r - r0, gMix = g - g0, bMix = b - b0;

    const b0X = (b0 & 7) * 64;
    const b0Y = (b0 >> 3) * 64;
    const b1X = (b1 & 7) * 64;
    const b1Y = (b1 >> 3) * 64;

    const row00 = (b0Y + g0) * 512;
    const row01 = (b0Y + g1) * 512;
    const row10 = (b1Y + g0) * 512;
    const row11 = (b1Y + g1) * 512;

    const offset000 = (row00 + b0X + r0) << 2;
    const offset100 = (row00 + b0X + r1) << 2;
    const offset010 = (row01 + b0X + r0) << 2;
    const offset110 = (row01 + b0X + r1) << 2;
    const offset001 = (row10 + b1X + r0) << 2;
    const offset101 = (row10 + b1X + r1) << 2;
    const offset011 = (row11 + b1X + r0) << 2;
    const offset111 = (row11 + b1X + r1) << 2;

    // R channel
    const r00 = table[offset000] + (table[offset100] - table[offset000]) * rMix;
    const r10 = table[offset010] + (table[offset110] - table[offset010]) * rMix;
    const r01 = table[offset001] + (table[offset101] - table[offset001]) * rMix;
    const r11 = table[offset011] + (table[offset111] - table[offset011]) * rMix;
    const r0_ = r00 + (r10 - r00) * gMix;
    const r1_ = r01 + (r11 - r01) * gMix;
    src[index] += ((r0_ + (r1_ - r0_) * bMix) - src[index]) * blend;

    // G channel
    const g00 = table[offset000 + 1] + (table[offset100 + 1] - table[offset000 + 1]) * rMix;
    const g10 = table[offset010 + 1] + (table[offset110 + 1] - table[offset010 + 1]) * rMix;
    const g01 = table[offset001 + 1] + (table[offset101 + 1] - table[offset001 + 1]) * rMix;
    const g11 = table[offset011 + 1] + (table[offset111 + 1] - table[offset011 + 1]) * rMix;
    const g0_ = g00 + (g10 - g00) * gMix;
    const g1_ = g01 + (g11 - g01) * gMix;
    src[index + 1] += ((g0_ + (g1_ - g0_) * bMix) - src[index + 1]) * blend;

    // B channel
    const b00 = table[offset000 + 2] + (table[offset100 + 2] - table[offset000 + 2]) * rMix;
    const b10 = table[offset010 + 2] + (table[offset110 + 2] - table[offset010 + 2]) * rMix;
    const b01 = table[offset001 + 2] + (table[offset101 + 2] - table[offset001 + 2]) * rMix;
    const b11 = table[offset011 + 2] + (table[offset111 + 2] - table[offset011 + 2]) * rMix;
    const b0_ = b00 + (b10 - b00) * gMix;
    const b1_ = b01 + (b11 - b01) * gMix;
    src[index + 2] += ((b0_ + (b1_ - b0_) * bMix) - src[index + 2]) * blend;
  }
}

/**
 * Execute only operators backed by recovered native artifacts.
 *
 * The 64³ LUT and its alpha are exact assets from the snapshot.
 * Operators without a native artifact remain decoded but unresolved.
 * Preset strength is intentionally blended exactly once at the end.
 */
async function applyPhotoPreset(image: ImageData, preset: PhotoPreset, strength: number): Promise<void> {
  if (strength <= 0) return;
  const snapshot = decodeKumoPhotoSnapshot(preset);
  const plan = buildKumoPhotoExecutionPlan(snapshot);
  const amount = clamp01(strength / 100);
  const original = amount < 1 ? new Uint8ClampedArray(image.data) : null;
  
  if (plan.filter) {
    const lut = await loadFilterLut(plan.filter.id);
    if (lut) applyFilterLut(image, lut, plan.filter.alpha / 100);
  }

  if (original) {
    for (let index = 0; index < image.data.length; index += 4) {
      for (let channel = 0; channel < 3; channel += 1) {
        image.data[index + channel] = original[index + channel]
          + (image.data[index + channel] - original[index + channel]) * amount;
      }
    }
  }
}

/**
 * Render PhotoBooth from locally copied Kumo data and the recovered decoded
 * executor. Masked/local and native-model operators stay isolated rather than
 * being flattened into this global colour pass.
 */
export async function renderPhotoBooth(
  baseBlob: Blob,
  options: PhotoBoothRenderOptions,
): Promise<Blob> {
  const hasPreset = Boolean(options.preset && options.presetStrength > 0);
  if (!hasPreset) return baseBlob;

  const bitmap = await decodeSource(baseBlob);
  const canvas = document.createElement("canvas");
  canvas.width = bitmap.width;
  canvas.height = bitmap.height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) throw new Error("Trình duyệt không tạo được canvas PhotoBooth.");
  context.drawImage(bitmap, 0, 0);
  bitmap.close();
  const image = context.getImageData(0, 0, canvas.width, canvas.height);

  if (options.preset && options.presetStrength > 0) {
    await applyPhotoPreset(image, options.preset, options.presetStrength);
  }
  context.putImageData(image, 0, 0);
  return canvasBlob(canvas);
}

export function applyReferenceColorGrade(image: ImageData, refData: ImageData, strength: number): void {
  const blend = clamp01(strength / 100);
  if (blend <= 0) return;

  const src = image.data;
  const ref = refData.data;

  // Compute RGB means and stds for ref
  let refRSum = 0, refGSum = 0, refBSum = 0, refCount = 0;
  for (let i = 0; i < ref.length; i += 4) {
    if (ref[i + 3] === 0) continue;
    refRSum += ref[i];
    refGSum += ref[i + 1];
    refBSum += ref[i + 2];
    refCount += 1;
  }
  if (refCount === 0) return;
  const refRMean = refRSum / refCount;
  const refGMean = refGSum / refCount;
  const refBMean = refBSum / refCount;

  let refRVar = 0, refGVar = 0, refBVar = 0;
  for (let i = 0; i < ref.length; i += 4) {
    if (ref[i + 3] === 0) continue;
    refRVar += (ref[i] - refRMean) ** 2;
    refGVar += (ref[i + 1] - refGMean) ** 2;
    refBVar += (ref[i + 2] - refBMean) ** 2;
  }
  const refRStd = Math.sqrt(refRVar / refCount) + 1e-4;
  const refGStd = Math.sqrt(refGVar / refCount) + 1e-4;
  const refBStd = Math.sqrt(refBVar / refCount) + 1e-4;

  // Compute RGB means and stds for src
  let srcRSum = 0, srcGSum = 0, srcBSum = 0, srcCount = 0;
  for (let i = 0; i < src.length; i += 4) {
    if (src[i + 3] === 0) continue;
    srcRSum += src[i];
    srcGSum += src[i + 1];
    srcBSum += src[i + 2];
    srcCount += 1;
  }
  if (srcCount === 0) return;
  const srcRMean = srcRSum / srcCount;
  const srcGMean = srcGSum / srcCount;
  const srcBMean = srcBSum / srcCount;

  let srcRVar = 0, srcGVar = 0, srcBVar = 0;
  for (let i = 0; i < src.length; i += 4) {
    if (src[i + 3] === 0) continue;
    srcRVar += (src[i] - srcRMean) ** 2;
    srcGVar += (src[i + 1] - srcGMean) ** 2;
    srcBVar += (src[i + 2] - srcBMean) ** 2;
  }
  const srcRStd = Math.sqrt(srcRVar / srcCount) + 1e-4;
  const srcGStd = Math.sqrt(srcGVar / srcCount) + 1e-4;
  const srcBStd = Math.sqrt(srcBVar / srcCount) + 1e-4;

  const scaleR = refRStd / srcRStd;
  const scaleG = refGStd / srcGStd;
  const scaleB = refBStd / srcBStd;

  for (let i = 0; i < src.length; i += 4) {
    if (src[i + 3] === 0) continue;
    const rNew = (src[i] - srcRMean) * scaleR + refRMean;
    const gNew = (src[i + 1] - srcGMean) * scaleG + refGMean;
    const bNew = (src[i + 2] - srcBMean) * scaleB + refBMean;

    src[i] = Math.min(255, Math.max(0, Math.round(src[i] + (rNew - src[i]) * blend)));
    src[i + 1] = Math.min(255, Math.max(0, Math.round(src[i + 1] + (gNew - src[i + 1]) * blend)));
    src[i + 2] = Math.min(255, Math.max(0, Math.round(src[i + 2] + (bNew - src[i + 2]) * blend)));
  }
}
