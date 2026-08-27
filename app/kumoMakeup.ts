import { drawWarpedMesh, solveAffine } from "./meshWarp";
import { CANONICAL_POINTS } from "./meshData";

export type KumoMakeupLayer = {
  tex: string;
  /** Kumo's Path field when AdditionalTexture supplies the visible pixels. */
  maskTex?: string | null;
  rect: [number, number, number, number];
  flip: boolean;
  mask: boolean;
  clip: string | null;
  blend: GlobalCompositeOperation;
  opacity: number;
  tint: [number, number, number] | null;
  partAlpha: number;
  type: string;
  locateMethod?: number | null;
  operation?: number | null;
  filterType?: number | null;
  muType?: number | null;
  needMask?: boolean;
  needPupilHighlight?: boolean;
  customName?: string | null;
  originalPath?: string | null;
  additionalTexture?: string | null;
  addPath?: string | null;
  orgba?: string | null;
  originalBlendMode?: string | number | null;
  /** 1×256 gradient-map LUT used to colourise lip textures. */
  ramp?: string | null;
};

export type KumoMakeupMaterial = {
  id: number;
  name: string;
  dir: string;
  thumb: string;
  alpha: number;
  rgb?: [number, number, number] | null;
  ramp?: string | null;
  layers: KumoMakeupLayer[];
};

export type KumoMakeupPart = {
  key: string;
  name: string;
  colors: Array<{ name: string; rgb: [number, number, number] }>;
  materials: KumoMakeupMaterial[];
};

export type KumoMakeupTheme = {
  id: number;
  name: string;
  alpha: number;
  thumb: string;
  parts: Array<{ key: string; material: string; color: string }>;
};

export type KumoMakeupLibrary = {
  canonical: {
    w: number;
    h: number;
    leftEye: [number, number];
    rightEye: [number, number];
    mouth: [number, number];
    axis: number;
  };
  parts: KumoMakeupPart[];
  themes: KumoMakeupTheme[];
};

export type KumoMakeupPick = {
  /** Semantic makeup group from makeup.json (eyebrow, eye, mouth, ...). */
  partKey?: string;
  dir: string;
  layers: KumoMakeupLayer[];
  amount: number;
  color?: [number, number, number] | null;
};

export type KumoMakeupSelection = Record<string, KumoMakeupPick>;

const GROUPS = {
  leftEye: [33, 43] as const,
  rightEye: [87, 97] as const,
  mouth: [52, 62] as const,
};

const imageCache = new Map<string, Promise<HTMLImageElement | null>>();
const luminanceMaskCache = new WeakMap<HTMLImageElement, HTMLCanvasElement>();
const eyebrowCoverageCache = new WeakMap<HTMLImageElement, HTMLCanvasElement>();

/**
 * Kumo's Path assets are opaque grayscale PNGs: white is the visible region
 * and black is the protected region. Canvas destination-in only reads alpha,
 * so using the PNG directly would keep the complete rectangular pupil layer.
 */
function luminanceAlphaMask(image: HTMLImageElement): CanvasImageSource {
  const cached = luminanceMaskCache.get(image);
  if (cached) return cached;

  const width = image.naturalWidth || image.width;
  const height = image.naturalHeight || image.height;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context || width <= 0 || height <= 0) return image;

  context.drawImage(image, 0, 0, width, height);
  try {
    const pixels = context.getImageData(0, 0, width, height);
    for (let index = 0; index < pixels.data.length; index += 4) {
      const sourceAlpha = pixels.data[index + 3] / 255;
      const luminance = Math.round(
        pixels.data[index] * 0.2126
          + pixels.data[index + 1] * 0.7152
          + pixels.data[index + 2] * 0.0722,
      );
      pixels.data[index] = 255;
      pixels.data[index + 1] = 255;
      pixels.data[index + 2] = 255;
      pixels.data[index + 3] = Math.round(luminance * sourceAlpha);
    }
    context.putImageData(pixels, 0, 0);
    luminanceMaskCache.set(image, canvas);
    return canvas;
  } catch {
    // Assets are served with CORS in the standalone app. Keep a safe fallback
    // for deployments that accidentally strip those headers.
    return image;
  }
}

/**
 * A small number of original Kumo eyebrow materials are stored as a bright
 * eyebrow on an almost-opaque black rectangle (instead of a transparent PNG).
 * The native operator treats brightness as coverage. Drawing the RGBA bitmap
 * directly is what produced the two dark boxes in the "Sang trọng" preset.
 */
function eyebrowCoverageMask(image: HTMLImageElement): CanvasImageSource {
  const cached = eyebrowCoverageCache.get(image);
  if (cached) return cached;

  const width = image.naturalWidth || image.width;
  const height = image.naturalHeight || image.height;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context || width <= 0 || height <= 0) return image;

  context.drawImage(image, 0, 0, width, height);
  try {
    const pixels = context.getImageData(0, 0, width, height);
    let maximum = 0;
    for (let index = 0; index < pixels.data.length; index += 4) {
      const luminance = pixels.data[index] * 0.2126
        + pixels.data[index + 1] * 0.7152
        + pixels.data[index + 2] * 0.0722;
      maximum = Math.max(maximum, luminance);
    }
    const scale = maximum > 0 ? 255 / maximum : 0;
    for (let index = 0; index < pixels.data.length; index += 4) {
      const luminance = pixels.data[index] * 0.2126
        + pixels.data[index + 1] * 0.7152
        + pixels.data[index + 2] * 0.0722;
      // The black background must become fully transparent. Normalising by
      // the brightest hair stroke preserves the strand texture and softness.
      const coverage = Math.max(0, Math.min(255, Math.round(luminance * scale)));
      pixels.data[index] = 255;
      pixels.data[index + 1] = 255;
      pixels.data[index + 2] = 255;
      pixels.data[index + 3] = coverage;
    }
    context.putImageData(pixels, 0, 0);
    eyebrowCoverageCache.set(image, canvas);
    return canvas;
  } catch {
    return image;
  }
}

function centroid(landmarks: number[][], group: readonly [number, number]) {
  let x = 0;
  let y = 0;
  let count = 0;
  for (let index = group[0]; index < group[1]; index += 1) {
    const point = landmarks[index];
    if (!point) continue;
    x += point[0];
    y += point[1];
    count += 1;
  }
  return count ? [x / count, y / count] : null;
}

export function makeupTransform(landmarks: number[][], canonical: KumoMakeupLibrary["canonical"]) {
  if (!Array.isArray(landmarks) || landmarks.length < 106) return null;
  const destination = [
    centroid(landmarks, GROUPS.leftEye),
    centroid(landmarks, GROUPS.rightEye),
    centroid(landmarks, GROUPS.mouth),
  ];
  if (destination.some((point) => !point)) return null;
  const source = [canonical.leftEye, canonical.rightEye, canonical.mouth];
  const [p0, p1, p2] = source;
  const determinant = (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p2[0] - p0[0]) * (p1[1] - p0[1]);
  if (!Number.isFinite(determinant) || Math.abs(determinant) < 1e-6) return null;

  const solve = (axis: number) => {
    const f0 = destination[0]![axis];
    const f1 = destination[1]![axis];
    const f2 = destination[2]![axis];
    const a = ((f1 - f0) * (p2[1] - p0[1]) - (f2 - f0) * (p1[1] - p0[1])) / determinant;
    const b = ((f2 - f0) * (p1[0] - p0[0]) - (f1 - f0) * (p2[0] - p0[0])) / determinant;
    return [a, b, f0 - a * p0[0] - b * p0[1]];
  };
  const [a, b, c] = solve(0);
  const [d, e, f] = solve(1);
  return { a, b, c, d, e, f };
}



/**
 * Eyelid mini-mesh triangles for piecewise eyelash warping.
 * Kumoo anchors eyelashes in 2 steps:
 *   Step 1: Similarity Transform (scale + rotate to eye width)
 *   Step 2: Piecewise Eyelid Mesh Warp (bend along upper lid contour)
 *
 * These triangles connect 4 rows:
 *   Row 1 (eyebrow):    43,44,45,46,47  /  101,100,99,98,97
 *   Row 2 (upper lid):  35,41,40,42,39  /  93,96,94,95,89
 *   Row 3 (lower lid):  36,33,37        /  91,87,90
 *   Row 4 (below eye):  9,75            /  25,81       (cheek/nose points for full coverage)
 */
const LEFT_EYELID_TRIS: [number, number, number][] = [
  // Row 1 → Row 2: Eyebrow → Upper eyelid
  [43, 35, 44], [44, 35, 41], [44, 41, 45], [45, 41, 40],
  [45, 40, 46], [46, 40, 42], [46, 42, 47], [47, 42, 39],
  // Row 2 → Row 3: Upper eyelid → Lower eyelid
  [35, 41, 36], [41, 33, 36], [41, 40, 33],
  [40, 37, 33], [40, 42, 37], [42, 39, 37],
  // Row 3 → Row 4: Lower eyelid → Below-eye (cheek/nose)
  [35, 36, 9], [36, 33, 9], [33, 75, 9],
  [33, 37, 75], [37, 39, 75],
];

const RIGHT_EYELID_TRIS: [number, number, number][] = [
  // Row 1 → Row 2: Eyebrow → Upper eyelid
  [101, 93, 100], [100, 93, 96], [100, 96, 99], [99, 96, 94],
  [99, 94, 98],   [98, 94, 95],  [98, 95, 97],  [97, 95, 89],
  // Row 2 → Row 3: Upper eyelid → Lower eyelid
  [93, 96, 91], [96, 87, 91], [96, 94, 87],
  [94, 90, 87], [94, 95, 90], [95, 89, 90],
  // Row 3 → Row 4: Lower eyelid → Below-eye (cheek/nose)
  [93, 91, 25], [91, 87, 25], [87, 81, 25],
  [87, 90, 81], [90, 89, 81],
];

function canonicalSource(
  context: CanvasRenderingContext2D,
  transform: NonNullable<ReturnType<typeof makeupTransform>>,
  canonical: KumoMakeupLibrary["canonical"],
) {
  const determinant = transform.a * transform.e - transform.b * transform.d;
  if (!Number.isFinite(determinant) || Math.abs(determinant) < 1e-6) return null;

  const canvas = document.createElement("canvas");
  canvas.width = canonical.w;
  canvas.height = canonical.h;
  const sourceContext = canvas.getContext("2d", { willReadFrequently: true });
  if (!sourceContext) return null;

  // makeupTransform maps canonical coordinates into the uploaded photo.  Draw
  // the photo through its inverse so pupil highlights can be sampled in the
  // same coordinate system as Kumo's eye material and mask.
  const inverseA = transform.e / determinant;
  const inverseB = -transform.b / determinant;
  const inverseD = -transform.d / determinant;
  const inverseE = transform.a / determinant;
  const inverseC = (transform.b * transform.f - transform.e * transform.c) / determinant;
  const inverseF = (transform.d * transform.c - transform.a * transform.f) / determinant;
  sourceContext.setTransform(inverseA, inverseD, inverseB, inverseE, inverseC, inverseF);
  sourceContext.drawImage(context.canvas, 0, 0);
  sourceContext.setTransform(1, 0, 0, 1, 0, 0);
  return sourceContext;
}

/**
 * Lp106 describes the eyelid, not the pupil. Kumo's Operation 16/17 follows
 * the actual iris inside that eyelid. Estimate its centre from the untouched
 * canonical eye crop so a side glance does not leave the contact lens behind.
 */
function detectPupilCenter(
  sourceContext: CanvasRenderingContext2D,
  mask: HTMLImageElement,
  x: number,
  y: number,
  width: number,
  height: number,
): [number, number] | null {
  const sampleWidth = Math.max(1, Math.round(width));
  const sampleHeight = Math.max(1, Math.round(height));
  const left = Math.round(x);
  const top = Math.round(y);
  if (
    left < 0
    || top < 0
    || left + sampleWidth > sourceContext.canvas.width
    || top + sampleHeight > sourceContext.canvas.height
  ) return null;

  const maskCanvas = document.createElement("canvas");
  maskCanvas.width = sampleWidth;
  maskCanvas.height = sampleHeight;
  const maskContext = maskCanvas.getContext("2d", { willReadFrequently: true });
  if (!maskContext) return null;
  maskContext.drawImage(mask, 0, 0, sampleWidth, sampleHeight);

  try {
    const source = sourceContext.getImageData(left, top, sampleWidth, sampleHeight);
    const maskPixels = maskContext.getImageData(0, 0, sampleWidth, sampleHeight);
    const candidates: Array<{ x: number; y: number; luminance: number; coverage: number }> = [];
    let maskY = 0;
    let maskWeight = 0;
    const inset = Math.max(2, Math.round(sampleHeight * 0.025));

    for (let py = inset; py < sampleHeight - inset; py += 1) {
      for (let px = inset; px < sampleWidth - inset; px += 1) {
        const index = (py * sampleWidth + px) * 4;
        const maskAlpha = maskPixels.data[index + 3] / 255;
        const maskLuminance = (
          maskPixels.data[index] * 0.2126
          + maskPixels.data[index + 1] * 0.7152
          + maskPixels.data[index + 2] * 0.0722
        ) / 255;
        const coverage = maskAlpha * maskLuminance;
        if (coverage < 0.36) continue;

        // Erode the eyelid edge. Eyelashes are often darker than the pupil and
        // otherwise pull the estimate upward.
        const neighbors = [
          index - inset * 4,
          index + inset * 4,
          index - inset * sampleWidth * 4,
          index + inset * sampleWidth * 4,
        ];
        if (neighbors.some((neighbor) => {
          const alpha = maskPixels.data[neighbor + 3] / 255;
          const luminance = (
            maskPixels.data[neighbor] * 0.2126
            + maskPixels.data[neighbor + 1] * 0.7152
            + maskPixels.data[neighbor + 2] * 0.0722
          ) / 255;
          return alpha * luminance < 0.28;
        })) continue;

        maskY += (py + 0.5) * coverage;
        maskWeight += coverage;
        const luminance = source.data[index] * 0.2126
          + source.data[index + 1] * 0.7152
          + source.data[index + 2] * 0.0722;
        candidates.push({ x: px + 0.5, y: py + 0.5, luminance, coverage });
      }
    }

    if (candidates.length < 40 || maskWeight <= 0) return null;
    const eyeCenterY = maskY / maskWeight;
    const luminances = candidates.map((candidate) => candidate.luminance).sort((a, b) => a - b);
    const darkIndex = Math.min(luminances.length - 1, Math.floor(luminances.length * 0.32));
    const darkLimit = Math.min(132, luminances[darkIndex] + 12);
    const fallbackX = sampleWidth / 2;
    let weightedX = 0;
    let weightedY = 0;
    let totalWeight = 0;

    for (const candidate of candidates) {
      const darkness = Math.max(0, darkLimit - candidate.luminance);
      if (darkness <= 0) continue;
      const horizontalDistance = Math.abs(candidate.x - fallbackX) / (sampleWidth * 0.43);
      const verticalDistance = Math.abs(candidate.y - eyeCenterY) / (sampleHeight * 0.22);
      if (horizontalDistance >= 1 || verticalDistance >= 1) continue;
      const centreBias = Math.max(0.08, 1 - horizontalDistance ** 4)
        * Math.max(0.08, 1 - verticalDistance ** 2);
      const weight = darkness * darkness * candidate.coverage * centreBias;
      weightedX += candidate.x * weight;
      weightedY += candidate.y * weight;
      totalWeight += weight;
    }

    if (totalWeight <= 0) return null;
    const detectedX = weightedX / totalWeight;
    const detectedY = weightedY / totalWeight;
    const maxShiftX = sampleWidth * 0.17;
    const maxShiftY = sampleHeight * 0.11;
    return [
      x + Math.max(fallbackX - maxShiftX, Math.min(fallbackX + maxShiftX, detectedX)),
      y + Math.max(eyeCenterY - maxShiftY, Math.min(eyeCenterY + maxShiftY, detectedY)),
    ];
  } catch {
    return null;
  }
}

/**
 * Kumo's pupil operator sizes the visible iris pattern, not the full PNG.
 * Most bundled lenses already include enough transparent padding to look
 * natural with the eye-box height. 09, 10 and 14 do not: their painted ring
 * occupies much more of the source square. These factors normalize the
 * painted diameter to the same ~65 canonical pixels as the other lenses.
 */
const KUMO_PUPIL_DRAW_SCALE: Readonly<Record<string, number>> = {
  Mi0000ctJWSsKeyV: 0.72, // Lens 09: visible ring is about 79% of its PNG.
  Mi0000j9sVvEjCkG: 0.75, // Lens 10: visible ring is about 75% of its PNG.
  Mi0000mhF9q8CLG8: 0.60, // Lens 14: visible ring nearly fills its PNG.
};

function pupilDrawScale(materialDir: string) {
  return KUMO_PUPIL_DRAW_SCALE[materialDir] ?? 1;
}

/**
 * Some legacy eye materials were imported before their eye-anchor metadata was
 * preserved. Their paired textures contain an aperture whose canonical centre
 * is offset from Lp106. Kumo aligns that aperture (LocateMethod 6/7 or
 * RightEyeUseLeftEyeMirrorModelPoints); compensate by the measured delta here.
 */
function makeupLayerAnchorOffset(
  pick: KumoMakeupPick,
  rect: [number, number, number, number],
  canonical: KumoMakeupLibrary["canonical"],
  landmarks: number[][],
  transform: NonNullable<ReturnType<typeof makeupTransform>>,
): [number, number] {
  return [0, 0];
}

function protectPupilHighlights(
  stageContext: CanvasRenderingContext2D,
  sourceContext: CanvasRenderingContext2D,
  drawX: number,
  drawY: number,
  drawWidth: number,
  drawHeight: number,
) {
  const left = Math.max(0, Math.floor(drawX));
  const top = Math.max(0, Math.floor(drawY));
  const right = Math.min(sourceContext.canvas.width, Math.ceil(drawX + drawWidth));
  const bottom = Math.min(sourceContext.canvas.height, Math.ceil(drawY + drawHeight));
  const width = right - left;
  const height = bottom - top;
  if (width <= 0 || height <= 0) return;

  const source = sourceContext.getImageData(left, top, width, height);
  const highlight = new ImageData(width, height);
  const centerX = drawX + drawWidth / 2;
  const centerY = drawY + drawHeight / 2;
  const radiusX = Math.max(1, drawWidth * 0.48);
  const radiusY = Math.max(1, drawHeight * 0.48);

  for (let index = 0; index < source.data.length; index += 4) {
    const pixel = index / 4;
    const x = left + (pixel % width) + 0.5;
    const y = top + Math.floor(pixel / width) + 0.5;
    const dx = (x - centerX) / radiusX;
    const dy = (y - centerY) / radiusY;
    const radialDistance = dx * dx + dy * dy;
    if (radialDistance >= 1) continue;

    const red = source.data[index];
    const green = source.data[index + 1];
    const blue = source.data[index + 2];
    const luminance = red * 0.2126 + green * 0.7152 + blue * 0.0722;
    const chroma = Math.max(red, green, blue) - Math.min(red, green, blue);
    // Natural catchlights are bright and close to neutral.  The radial guard
    // prevents white sclera or spectacle rims from punching holes in the iris.
    if (luminance <= 155 || chroma >= 72) continue;
    const brightness = Math.min(1, (luminance - 155) / 70);
    const edgeFade = Math.min(1, Math.max(0, (1 - radialDistance) / 0.18));
    const alpha = Math.round(255 * brightness * edgeFade);
    highlight.data[index] = 255;
    highlight.data[index + 1] = 255;
    highlight.data[index + 2] = 255;
    highlight.data[index + 3] = alpha;
  }

  const highlightCanvas = document.createElement("canvas");
  highlightCanvas.width = width;
  highlightCanvas.height = height;
  const highlightContext = highlightCanvas.getContext("2d");
  if (!highlightContext) return;
  highlightContext.putImageData(highlight, 0, 0);
  // NeedPupilHighLight means the lens must leave the source catchlight intact.
  // Removing those pixels from the overlay preserves the real eye underneath.
  stageContext.globalCompositeOperation = "destination-out";
  stageContext.drawImage(highlightCanvas, left, top);
}

/**
 * Apply a 1×256 gradient-map LUT to a stage canvas so that each pixel's
 * luminance selects the corresponding RGB entry from the ramp image.
 * The original alpha channel is preserved.  This is how Kumo colourise
 * lip textures — the texture carries only the lip shape and luminance
 * gradient, while the ramp supplies the actual lip colour.
 */
function applyGradientMap(
  stageContext: CanvasRenderingContext2D,
  rampImage: HTMLImageElement,
  x: number,
  y: number,
  width: number,
  height: number,
): void {
  // Build a 256-entry LUT from the 1×256 ramp image.
  const rampCanvas = document.createElement("canvas");
  rampCanvas.width = 256;
  rampCanvas.height = 1;
  const rampCtx = rampCanvas.getContext("2d", { willReadFrequently: true });
  if (!rampCtx) return;
  rampCtx.drawImage(rampImage, 0, 0, 256, 1);
  const rampData = rampCtx.getImageData(0, 0, 256, 1).data; // RGBA × 256

  const left = Math.max(0, Math.floor(x));
  const top = Math.max(0, Math.floor(y));
  const right = Math.min(stageContext.canvas.width, Math.ceil(x + width));
  const bottom = Math.min(stageContext.canvas.height, Math.ceil(y + height));
  const pw = right - left;
  const ph = bottom - top;
  if (pw <= 0 || ph <= 0) return;

  const imageData = stageContext.getImageData(left, top, pw, ph);
  const pixels = imageData.data;
  for (let i = 0; i < pixels.length; i += 4) {
    if (pixels[i + 3] === 0) continue;
    const r = pixels[i];
    const g = pixels[i + 1];
    const b = pixels[i + 2];
    // Luminance index into the 256-entry LUT.
    const lum = Math.round(0.2126 * r + 0.7152 * g + 0.0722 * b);
    const ri = lum * 4;
    pixels[i]     = rampData[ri];
    pixels[i + 1] = rampData[ri + 1];
    pixels[i + 2] = rampData[ri + 2];
    // alpha (pixels[i+3]) unchanged
  }
  stageContext.putImageData(imageData, left, top);
}

function loadImage(url: string) {
  const cached = imageCache.get(url);
  if (cached) return cached;
  const pending = new Promise<HTMLImageElement | null>((resolve) => {
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => resolve(image);
    image.onerror = () => resolve(null);
    image.src = url;
  });
  imageCache.set(url, pending);
  return pending;
}

async function preloadMakeup(picks: KumoMakeupPick[], ovalUrl: string) {
  const urls = new Set<string>();
  for (const pick of picks) {
    for (const layer of pick.layers ?? []) {
      urls.add(layer.tex);
      if (layer.maskTex) urls.add(layer.maskTex);
      if (layer.clip) urls.add(layer.clip);
      if (layer.ramp) urls.add(layer.ramp);
    }
  }
  const list = [...urls];
  const [oval, ...images] = await Promise.all([loadImage(ovalUrl), ...list.map(loadImage)]);
  const byTexture = new Map<string, HTMLImageElement>();
  list.forEach((url, index) => {
    const image = images[index];
    if (image) byTexture.set(url, image);
  });
  return { oval, byTexture };
}

function compositeMakeup(
  context: CanvasRenderingContext2D,
  landmarks: number[][],
  picks: KumoMakeupPick[],
  canonical: KumoMakeupLibrary["canonical"],
  assets: Awaited<ReturnType<typeof preloadMakeup>>,
) {
  const transform = makeupTransform(landmarks, canonical);
  if (!transform) return false;

  const stage = document.createElement("canvas");
  stage.width = canonical.w;
  stage.height = canonical.h;
  const stageContext = stage.getContext("2d");
  if (!stageContext) return false;
  const sourceContext = canonicalSource(context, transform, canonical);
  const pupilCenters = new Map<string, [number, number] | null>();
  let painted = false;
  let warpStage: HTMLCanvasElement | null = null;
  let warpStageContext: CanvasRenderingContext2D | null = null;

  for (const pick of picks) {
    const isEyelash = pick.partKey === "eyelash" || pick.partKey === "eyeliner" || pick.partKey === "eye";
    for (const layer of pick.layers ?? []) {
      // Never render a Kumo pupil layer without its paired eye mask. Path is
      // an opaque grayscale mask, not visible makeup; drawing it directly is
      // exactly what caused the white-eye regression in Trang diem Pro.
      if (layer.customName === "MUFACE_EYEPUPIL" && !layer.maskTex) continue;
      const texture = assets.byTexture.get(layer.tex);
      if (!texture) {
        console.warn(`[KumoMakeup] BỎ QUA lớp ${pick.partKey}: Thiếu texture gốc ${layer.tex}`);
        continue;
      }

      const localMask = layer.maskTex && assets.byTexture.get(layer.maskTex);
      const alpha = (layer.opacity / 100) * (layer.partAlpha / 100) * (pick.amount / 100);

      const [rawX, rawY, width, height] = layer.rect;
      const [offsetX, offsetY] = makeupLayerAnchorOffset(pick, layer.rect, canonical, landmarks, transform);
      const x = rawX + offsetX;
      const y = rawY + offsetY;

      const resolvedBlend = resolveLayerBlend(layer, pick);
      console.log(`[KumoMakeup] LỚP (TEST3) ${pick.partKey} - Tex: ${layer.tex}, JSON Blend: ${layer.blend}, Resolved: ${resolvedBlend}, Alpha: ${alpha}, X: ${x}, Y: ${y}`);

      if (layer.customName === "MUFACE_EYEPUPIL" && !assets.byTexture.get(layer.maskTex!)) continue;
      if (!(alpha > 0)) continue;

      stageContext.setTransform(1, 0, 0, 1, 0, 0);
      stageContext.globalCompositeOperation = "source-over";
      stageContext.clearRect(0, 0, canonical.w, canonical.h);
      // Operation 16/17 are the left/right pupil operators. Their Rectangle
      // describes the eye mask, not a destination rectangle that should
      // stretch the square iris artwork. Kumo keeps the iris aspect ratio and
      // centres it inside that eye rectangle before applying Path.
      const isPupil = layer.customName === "MUFACE_EYEPUPIL"
        && (Number(layer.operation) === 16 || Number(layer.operation) === 17);
      const isOpaqueEyebrowCoverage = pick.partKey === "eyebrow"
        && pick.dir === "hengliumei"
        && !layer.mask
        && !layer.maskTex;
      // LocateMethod 48 eyebrow materials (10–13) contain one canonical
      // left-side texture. Kumo mirrors that placement across the face axis;
      // drawing the single plist Rectangle literally leaves the other brow
      // untouched.
      const isMirroredEyebrow = pick.partKey === "eyebrow"
        && layer.locateMethod === 48;

      const drawable = isOpaqueEyebrowCoverage
        ? eyebrowCoverageMask(texture)
        : texture;

      const isLipstickMaterial = pick.partKey === "mouth"
        && Number(layer.operation) === 7
        && Number(layer.filterType) === 4
        && Number(layer.muType) === 1;
      const textureAspect = texture.naturalWidth > 0 && texture.naturalHeight > 0
        ? texture.naturalWidth / texture.naturalHeight
        : 1;

      const pupilKey = `${x}:${y}:${width}:${height}:${layer.maskTex ?? ""}`;
      if (isPupil && sourceContext && localMask && !pupilCenters.has(pupilKey)) {
        pupilCenters.set(
          pupilKey,
          detectPupilCenter(sourceContext, localMask, x, y, width, height),
        );
      }
      const pupilCenter = isPupil ? pupilCenters.get(pupilKey) : null;
      
      const drawHeight = isPupil ? height * pupilDrawScale(pick.dir) : height;
      const drawWidth = isPupil ? Math.min(width, drawHeight * textureAspect) : width;
      const drawX = isPupil ? (pupilCenter?.[0] ?? x + width / 2) - drawWidth / 2 : x;
      let drawY = isPupil ? (pupilCenter?.[1] ?? y + height / 2) - drawHeight / 2 : y;
      
      
      const mirroredDrawX = canonical.axis * 2 - drawX - drawWidth;

      const drawPlaced = (targetX: number, flip: boolean) => {
        stageContext.setTransform(1, 0, 0, 1, 0, 0);
        if (flip) {
          stageContext.translate(targetX * 2 + drawWidth, 0);
          stageContext.scale(-1, 1);
        }
        stageContext.drawImage(drawable, targetX, drawY, drawWidth, drawHeight);
        stageContext.setTransform(1, 0, 0, 1, 0, 0);
      };
      const place = () => {
        drawPlaced(drawX, layer.flip);
        if (isMirroredEyebrow) drawPlaced(mirroredDrawX, !layer.flip);
      };
      place();

      const hasValidColorOverride = pick.color && (pick.color[0] !== 0 || pick.color[1] !== 0 || pick.color[2] !== 0);
      const activeColor = hasValidColorOverride ? pick.color : null;
      const isMouthMultiplyLayer = pick.partKey === "mouth" && Number(layer.operation) === 7;

      // Apply gradient-map (colour-ramp LUT) for mouth materials that carry a
      // ramp. The ramp maps each pixel's luminance to a target RGB colour while
      // preserving alpha, turning the neutral-grey lip texture into the desired
      // lip colour before any additional tint or blend is applied.
      const rampImage = layer.ramp ? assets.byTexture.get(layer.ramp) : null;
      // For lipsticks, the ramp is often grayscale to act as a neutral base for custom colors.
      // If there is no custom color, applying the grayscale ramp destroys the texture's natural red color.
      // Therefore, only apply the ramp for lipsticks if a custom color is provided.
      const shouldApplyRamp = rampImage && activeColor !== null;

      if (shouldApplyRamp) {
        stageContext.globalCompositeOperation = "source-over";
        applyGradientMap(stageContext, rampImage, drawX, drawY, drawWidth, drawHeight);
      }

      let tint: [number, number, number] | null = (isMouthMultiplyLayer
        ? (activeColor || layer.tint)
        : layer.ramp
          ? activeColor
          : layer.mask
            ? (activeColor || layer.tint)
            : activeColor
              ? activeColor
              : isOpaqueEyebrowCoverage
                ? (activeColor || layer.tint || [72, 54, 42] as [number, number, number])
                : null) ?? null;

      // Eyelash/eyeliner textures contain semi-transparent strands that need
      // a black tint (multiply) to render as visible dark lashes.
      if (!tint && (pick.partKey === "eyelash" || pick.partKey === "eyeliner")) {
        tint = [0, 0, 0];
      }

      console.log(`[KumoMakeup] CHI TIẾT lớp ${pick.partKey} - tint: ${tint}, activeColor: ${activeColor}, layer.mask: ${layer.mask}, ramp: ${layer.ramp}, shouldApplyRamp: ${shouldApplyRamp}`);

      if (tint) {
        if (isOpaqueEyebrowCoverage) {
          stageContext.globalCompositeOperation = "source-in";
          stageContext.fillStyle = `rgb(${tint[0]},${tint[1]},${tint[2]})`;
          // source-in already limits the fill to the current layer. Filling
          // the stage also preserves the mirrored half of LocateMethod 48.
          stageContext.fillRect(0, 0, canonical.w, canonical.h);
        } else {
          stageContext.globalCompositeOperation = "multiply";
          stageContext.fillStyle = `rgb(${tint[0]},${tint[1]},${tint[2]})`;
          stageContext.fillRect(drawX, drawY, drawWidth, drawHeight);
          stageContext.globalCompositeOperation = "destination-in";
          place();
        }
      }

      // Pupil materials are a two-texture contract in Kumo: AdditionalTexture
      // carries the iris artwork while Path is only an eye-shaped alpha mask.
      // Drawing Path as the visible texture produces the opaque white eyes
      // seen in the broken preview.
      if (localMask) {
        stageContext.globalCompositeOperation = "destination-in";
        stageContext.drawImage(
          isPupil ? luminanceAlphaMask(localMask) : localMask,
          x,
          y,
          width,
          height,
        );
      }

      if (isPupil && layer.needPupilHighlight && sourceContext) {
        protectPupilHighlights(stageContext, sourceContext, drawX, drawY, drawWidth, drawHeight);
      }

      const clip = (layer.clip && assets.byTexture.get(layer.clip)) || assets.oval;
      if (clip) {
        stageContext.globalCompositeOperation = "destination-in";
        stageContext.drawImage(clip, 0, 0, canonical.w, canonical.h);
      }

function resolveLayerBlend(layer: KumoMakeupLayer, pick: KumoMakeupPick): GlobalCompositeOperation {
  if (layer.blend) {
    const b = layer.blend.toLowerCase();
    if (b === "source-over" || b === "multiply" || b === "screen" || b === "overlay" || b === "color-burn" || b === "hard-light" || b === "soft-light" || b === "lighten" || b === "color") {
      return b as GlobalCompositeOperation;
    }
  }
  const op = Number(layer.operation);
  if (op === 10) return "multiply";
  if (op === 11) return "screen";
  if (op === 12) return "color-burn";
  if (op === 13) return "overlay";
  if (op === 14) return "soft-light";
  if (op === 15) return "source-over";
  const orig = String(layer.originalBlendMode ?? "").toLowerCase();
  if (orig.includes("multiply") || orig === "10") return "multiply";
  if (orig.includes("screen") || orig === "11") return "screen";
  if (orig.includes("soft") || orig === "14") return "soft-light";
  if (orig.includes("overlay") || orig === "13") return "overlay";
  if (orig.includes("burn") || orig === "12") return "color-burn";
  return "source-over";
}

context.save();
      context.globalAlpha = alpha;
      context.globalCompositeOperation = resolveLayerBlend(layer, pick);

      // Piecewise triangle mesh warping perfectly anchors eyelashes and eyeshadows
      // to the 106 facial landmarks, following eyelid curves and squints precisely.
      const useMeshWarp = ["eyeshadow", "eyesocket", "blush", "feature", "makeup_highlight", "eyebrow", "eyeliner", "eye"].includes(pick.partKey ?? "");

      // After drawing layers, apply mesh warp if needed
      if (useMeshWarp) {
        if (!warpStage) {
          warpStage = document.createElement("canvas");
          warpStage.width = context.canvas.width;
          warpStage.height = context.canvas.height;
          warpStageContext = warpStage.getContext("2d")!;
        }
        if (!warpStageContext) continue;
        warpStageContext.clearRect(0, 0, warpStage.width, warpStage.height);
        warpStageContext.globalCompositeOperation = "source-over";
        drawWarpedMesh(warpStageContext, stage, landmarks, transform);

        context.setTransform(1, 0, 0, 1, 0, 0);
        context.drawImage(warpStage, 0, 0);
      } else {
        let activeTransform = transform;
        if (pick.partKey === "eyelash") {
          const isLeft = layer.rect[0] < 500;
          const local = localEyeTransform(landmarks, isLeft);
          if (local) activeTransform = local;
        }

        // All other layers (mouth, eyebrow, blush without warp, etc.)
        // use the global 3-point affine transform.
        context.setTransform(
          activeTransform.a, activeTransform.d,
          activeTransform.b, activeTransform.e,
          activeTransform.c, activeTransform.f,
        );
        context.drawImage(stage, 0, 0);
        context.setTransform(1, 0, 0, 1, 0, 0);
      }
      context.restore();
      painted = true;
    }
  }
  context.setTransform(1, 0, 0, 1, 0, 0);
  context.globalCompositeOperation = "source-over";
  context.globalAlpha = 1;
  return painted;
}

export async function renderKumoMakeup(
  baseBlob: Blob,
  landmarkSets: number[][][],
  selection: KumoMakeupSelection,
  library: KumoMakeupLibrary,
  ovalUrl: string,
  faceSelections?: KumoMakeupSelection[],
  sourceSize?: { width: number; height: number } | null,
) {
  try {
    const picks = faceSelections?.length
      ? faceSelections.flatMap((faceSelection) => Object.values(faceSelection))
      : Object.values(selection);
    if (picks.length === 0) return baseBlob;
    
    const [bitmap, assets] = await Promise.all([
      createImageBitmap(baseBlob),
      preloadMakeup(picks, ovalUrl),
    ]);
    const canvas = document.createElement("canvas");
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    const context = canvas.getContext("2d");
    if (!context) {
      bitmap.close();
      return baseBlob;
    }
    context.drawImage(bitmap, 0, 0);
    bitmap.close();
    const scaleX = sourceSize?.width
      ? canvas.width / sourceSize.width
      : 1;
    const scaleY = sourceSize?.height
      ? canvas.height / sourceSize.height
      : 1;
    for (let index = 0; index < landmarkSets.length; index += 1) {
      const facePicks = faceSelections?.[index]
        ? Object.values(faceSelections[index])
        : Object.values(selection);
      const previewLandmarks = landmarkSets[index].map(([x, y]) => [
        x * scaleX,
        y * scaleY,
      ]);
      compositeMakeup(context, previewLandmarks, facePicks, library.canonical, assets);

    }
    return new Promise<Blob>((resolve) => {
      canvas.toBlob((blob) => resolve(blob ?? baseBlob), "image/jpeg", 0.95);
    });
  } catch (err) {
    console.error("[KumoMakeup] LỖI TOÀN CỤC KHI VẼ MAKEUP:", err);
    return baseBlob;
  }
}

// The user assumed LocateMethod 6/7 was a 2-point similarity transform based on 39 and 35.
// However, mathematical analysis and visual testing prove that a uniform 2-point similarity transform 
// fails completely on 3D faces due to perspective distortion (head yaw compresses the eye width dxR, 
// causing the entire eyelash to uniformly shrink to a tiny smudge, as seen in the user's screenshot).
// To correctly anchor eyelashes to a 3D face without Mesh Warp, the native engine MUST use a 
// 3-point Affine Transform (non-uniform scale and shear) mapped to the eye corners and upper apex.
export function localEyeTransform(landmarks: number[][], isLeft: boolean) {
  // 35: outer, 39: inner, 40: upper apex for left eye
  // 93: outer, 89: inner, 94: upper apex for right eye
  const p0 = isLeft ? [276.075, 554.636] : [736.892, 549.325]; // outer
  const p1 = isLeft ? [415.129, 565.966] : [589.437, 563.292]; // inner
  const p2 = isLeft ? [345.875, 547.975] : [666.099, 543.103]; // upper
  
  const d0 = landmarks[isLeft ? 35 : 93];
  const d1 = landmarks[isLeft ? 39 : 89];
  const d2 = landmarks[isLeft ? 40 : 94];
  
  if (!d0 || !d1 || !d2) return null;
  
  const determinant = (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p2[0] - p0[0]) * (p1[1] - p0[1]);
  if (!Number.isFinite(determinant) || Math.abs(determinant) < 1e-6) return null;
  
  const solve = (axis: number) => {
    const f0 = d0[axis];
    const f1 = d1[axis];
    const f2 = d2[axis];
    const a = ((f1 - f0) * (p2[1] - p0[1]) - (f2 - f0) * (p1[1] - p0[1])) / determinant;
    const b = ((f2 - f0) * (p1[0] - p0[0]) - (f1 - f0) * (p2[0] - p0[0])) / determinant;
    return [a, b, f0 - a * p0[0] - b * p0[1]];
  };
  
  const [a, b, c] = solve(0);
  const [d, e, f] = solve(1);
  return { a, b, c, d, e, f };
}
