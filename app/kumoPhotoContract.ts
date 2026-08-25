/**
 * Standalone decoder for a Kumo PhotoBooth snapshot.
 *
 * The catalog is data only. This module deliberately keeps every operator
 * family separate so a renderer cannot accidentally flatten face-profile,
 * material, global colour and local-mask values into one colour pass.
 */

export type KumoPresetSnapshotInput = {
  all_params?: Record<string, unknown>;
  params?: {
    exposure?: number;
    contrast?: number;
    temperature?: number;
    vibrance?: number;
    blackness?: number;
    highlight?: number;
    whiteness?: number;
    shadow?: number;
  };
};

export type KumoMaterial = {
  id: string;
  alpha: number;
  color: string;
};

export type KumoFilterMaterial = {
  id: string;
  alpha: number;
  isBlack: boolean;
};

export type KumoCurvePoint = readonly [number, number];

export type KumoHslBand = {
  band: string;
  center: number;
  hue: number;
  saturation: number;
  lightness: number;
};

export type KumoLocalAdjustmentLayer = {
  order: number;
  visible: boolean;
  maskKey: string;
  maskType: number;
  reverse: boolean;
  params: Record<string, number | boolean>;
};

export type KumoPhotoSnapshot = {
  global: {
    whiteBalanceMode: number;
    temperature: number;
    tint: number;
    exposure: number;
    contrast: number;
    highlight: number;
    shadow: number;
    whiteness: number;
    blackness: number;
    vibrance: number;
    saturation: number;
    intelligentToneAdjustment: { enabled: boolean; amount: number };
    autoExposure: { enabled: boolean; normal: number; pure: number };
    dehaze: { intelligent: number; amount: number; body: number; background: number };
    sharpness: number;
    vignette: number;
    filmGrain: number;
  };
  filter: KumoFilterMaterial | null;
  curves: Record<"red" | "green" | "blue" | "gray", KumoCurvePoint[]>;
  hsl: KumoHslBand[];
  grading: Record<string, number | boolean>;
  calibration: Record<string, number>;
  profileNumbers: Record<string, number[]>;
  profileStrings: Record<string, string[]>;
  profileMaterials: Record<string, KumoMaterial[]>;
  localAdjustments: KumoLocalAdjustmentLayer[];
  unclassified: Record<string, unknown>;
  raw: Record<string, unknown>;
};

/**
 * Execution is deliberately narrower than decoding. Kumo's catalog stores
 * slider/control values, while its native runtime resolves several controls
 * into matrices or dense lookup tables before dispatching GPU kernels. A
 * standalone renderer may execute an operator only when that resolved
 * artifact is present locally; everything else remains decoded and isolated.
 */
export type KumoPhotoExecutionPlan = {
  filter: KumoFilterMaterial | null;
  exactOperators: string[];
  recoveredOperators: string[];
  decodedOnlyOperators: string[];
  unresolvedNativeArtifacts: Record<string, string[]>;
};

const HSL_BANDS = [
  ["red", 0], ["orange", 30], ["yellow", 60], ["green", 120],
  ["aqua", 180], ["blue", 240], ["violet", 280], ["magenta", 320],
] as const;

const GLOBAL_KEYS = new Set([
  "whitebalance_mode", "temperature", "hue", "exposure", "constrast",
  "highlight", "shadow", "whiteness", "blackness", "vibrance",
  "saturability", "exposure_flag", "exposure_alpha", "auto_exposure_flag",
  "exposure_norm_coef", "exposure_pure_coef", "intelligent_dehazing",
  "dehaze_coef", "highpass_body_coef", "highpass_background_coef",
  "sharpness", "vignette_adjustment", "film_granularity",
]);

const numberValue = (source: Record<string, unknown>, key: string): number => {
  const value = source[key];
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
};

const optionalNumberValue = (source: Record<string, unknown>, key: string): number | undefined => {
  const value = source[key];
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
};

const numberWithFallback = (
  source: Record<string, unknown>,
  key: string,
  fallback: unknown,
): number => {
  const value = optionalNumberValue(source, key);
  if (value !== undefined) return value;
  return typeof fallback === "number" && Number.isFinite(fallback) ? fallback : 0;
};

const booleanValue = (source: Record<string, unknown>, key: string): boolean => {
  const value = source[key];
  return value === true || value === 1;
};

function materialValue(value: unknown): KumoMaterial | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const candidate = value as Record<string, unknown>;
  const id = typeof candidate.id === "string" ? candidate.id : "";
  const alpha = Number(candidate.alpha ?? 0);
  const color = typeof candidate.color === "string" ? candidate.color : "0;0;0;0";
  if (!Number.isFinite(alpha)) return null;
  return { id, alpha, color };
}

function curvePoints(value: unknown): KumoCurvePoint[] {
  if (!Array.isArray(value) || value.length < 4 || value.length % 2 !== 0) return [];
  const points: KumoCurvePoint[] = [];
  for (let index = 0; index < value.length; index += 2) {
    const x = Number(value[index]);
    const y = Number(value[index + 1]);
    if (!Number.isFinite(x) || !Number.isFinite(y)) return [];
    points.push([x, y]);
  }
  return points;
}

function localAdjustmentLayers(value: unknown): KumoLocalAdjustmentLayer[] {
  if (!Array.isArray(value)) return [];
  const decoded: KumoLocalAdjustmentLayer[] = [];
  for (const entry of value) {
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) continue;
    const source = entry as Record<string, unknown>;
    const params: Record<string, number | boolean> = {};
    if (source.param && typeof source.param === "object" && !Array.isArray(source.param)) {
      for (const [key, raw] of Object.entries(source.param as Record<string, unknown>)) {
        if (typeof raw === "boolean" || (typeof raw === "number" && Number.isFinite(raw))) {
          params[key] = raw;
        }
      }
    }
    let visible = true;
    let maskKey = "";
    let reverse = false;
    if (typeof source.journey === "string" && source.journey) {
      try {
        const journey = JSON.parse(source.journey) as Record<string, unknown>;
        visible = journey.visible !== false;
        const layers = Array.isArray(journey.layers) ? journey.layers : [];
        const first = layers[0] as Record<string, unknown> | undefined;
        if (first) {
          maskKey = typeof first.mask_key === "string" ? first.mask_key : "";
          reverse = first.reverse === true;
          visible = visible && first.visible !== false;
        }
      } catch {
        // Preserve malformed or newer journey payloads in `raw`; never merge
        // their parameters into the global operator as a fallback.
      }
    }
    decoded.push({
      order: numberValue(source, "order"),
      visible,
      maskKey,
      maskType: numberValue(source, "mask_type"),
      reverse,
      params,
    });
  }
  return decoded.sort((left, right) => left.order - right.order);
}

/** Decode one immutable Kumo snapshot into independent operator namespaces. */
export function decodeKumoPhotoSnapshot(preset: KumoPresetSnapshotInput): KumoPhotoSnapshot {
  const raw = preset.all_params ?? {};
  const params = preset.params ?? {};
  const filterSource = raw.filter && typeof raw.filter === "object" && !Array.isArray(raw.filter)
    ? raw.filter as Record<string, unknown>
    : {};
  const filterId = typeof filterSource.filter_id === "string" ? filterSource.filter_id : "";
  const filterAlpha = numberValue(filterSource, "filters_lut_alpha");
  const filter = filterId && filterAlpha > 0
    ? { id: filterId, alpha: filterAlpha, isBlack: booleanValue(filterSource, "filter_is_black") }
    : null;

  const hsl = HSL_BANDS.map(([band, center]) => ({
    band,
    center,
    hue: numberValue(raw, `hsl_hue_${band}`),
    saturation: numberValue(raw, `hsl_sat_${band}`),
    lightness: numberValue(raw, `hsl_luma_${band}`),
  })).filter((entry) => entry.hue !== 0 || entry.saturation !== 0 || entry.lightness !== 0);

  const grading: Record<string, number | boolean> = {};
  const calibration: Record<string, number> = {};
  const profileNumbers: Record<string, number[]> = {};
  const profileStrings: Record<string, string[]> = {};
  const profileMaterials: Record<string, KumoMaterial[]> = {};
  const unclassified: Record<string, unknown> = {};

  for (const [key, value] of Object.entries(raw)) {
    if (key.startsWith("color_grading_")) {
      if (typeof value === "boolean" || (typeof value === "number" && Number.isFinite(value))) {
        grading[key] = value;
      }
      continue;
    }
    if (key.startsWith("color_calibration_") && typeof value === "number" && Number.isFinite(value)) {
      calibration[key] = value;
      continue;
    }
    if (Array.isArray(value) && value.length === 5 && value.every((item) => typeof item === "number" && Number.isFinite(item))) {
      profileNumbers[key] = value as number[];
      continue;
    }
    if (Array.isArray(value) && value.length === 5 && value.every((item) => typeof item === "string")) {
      profileStrings[key] = value as string[];
      continue;
    }
    if (Array.isArray(value) && value.length === 5) {
      const materials = value.map(materialValue);
      if (materials.every((item) => item !== null)) {
        profileMaterials[key] = materials as KumoMaterial[];
        continue;
      }
    }
    if (
      GLOBAL_KEYS.has(key)
      || key.startsWith("hsl_")
      || key.endsWith("_point")
      || key === "filter"
      || key === "part_color_adjust"
    ) continue;
    unclassified[key] = value;
  }

  return {
    global: {
      whiteBalanceMode: numberValue(raw, "whitebalance_mode"),
      temperature: numberWithFallback(raw, "temperature", params.temperature),
      tint: numberValue(raw, "hue"),
      exposure: numberWithFallback(raw, "exposure", params.exposure),
      contrast: numberWithFallback(raw, "constrast", params.contrast),
      highlight: numberWithFallback(raw, "highlight", params.highlight),
      shadow: numberWithFallback(raw, "shadow", params.shadow),
      whiteness: numberWithFallback(raw, "whiteness", params.whiteness),
      blackness: numberWithFallback(raw, "blackness", params.blackness),
      vibrance: numberWithFallback(raw, "vibrance", params.vibrance),
      saturation: numberValue(raw, "saturability"),
      // The names are decoded from the catalog only. Their resolved native
      // operator/table is not present in the extracted snapshot, so the
      // executor must not infer a tone formula from these values.
      intelligentToneAdjustment: {
        enabled: booleanValue(raw, "exposure_flag"),
        amount: numberValue(raw, "exposure_alpha"),
      },
      autoExposure: {
        enabled: booleanValue(raw, "auto_exposure_flag"),
        normal: numberValue(raw, "exposure_norm_coef"),
        pure: numberValue(raw, "exposure_pure_coef"),
      },
      dehaze: {
        intelligent: numberValue(raw, "intelligent_dehazing"),
        amount: numberValue(raw, "dehaze_coef"),
        body: numberValue(raw, "highpass_body_coef"),
        background: numberValue(raw, "highpass_background_coef"),
      },
      sharpness: numberValue(raw, "sharpness"),
      vignette: numberValue(raw, "vignette_adjustment"),
      filmGrain: numberValue(raw, "film_granularity"),
    },
    filter,
    curves: {
      red: curvePoints(raw.red_point),
      green: curvePoints(raw.green_point),
      blue: curvePoints(raw.blue_point),
      gray: curvePoints(raw.gray_point),
    },
    hsl,
    grading,
    calibration,
    profileNumbers,
    profileStrings,
    profileMaterials,
    localAdjustments: localAdjustmentLayers(raw.part_color_adjust),
    unclassified,
    raw,
  };
}

const anyNonZero = (values: Array<number | boolean>): boolean => values.some((value) => (
  typeof value === "boolean" ? value : value !== 0
));

/** Build a truthful, independent executor plan without inferred coefficients. */
export function buildKumoPhotoExecutionPlan(snapshot: KumoPhotoSnapshot): KumoPhotoExecutionPlan {
  const exactOperators: string[] = [];
  const recoveredOperators: string[] = [];
  const decodedOnlyOperators: string[] = [];
  const unresolvedNativeArtifacts: Record<string, string[]> = {};

  if (snapshot.filter) exactOperators.push("filter-lut-64");

  if (anyNonZero([
    snapshot.global.temperature,
    snapshot.global.tint,
    snapshot.global.whiteBalanceMode,
  ])) {
    decodedOnlyOperators.push("white-balance");
    unresolvedNativeArtifacts["white-balance"] = ["nativeWhiteBalanceMatrix"];
  }

  if (anyNonZero([
    snapshot.global.exposure,
    snapshot.global.contrast,
    snapshot.global.highlight,
    snapshot.global.shadow,
    snapshot.global.whiteness,
    snapshot.global.blackness,
    snapshot.global.vibrance,
    snapshot.global.saturation,
    snapshot.global.intelligentToneAdjustment.enabled,
    snapshot.global.intelligentToneAdjustment.amount,
    snapshot.global.autoExposure.enabled,
    snapshot.global.autoExposure.normal,
    snapshot.global.autoExposure.pure,
  ])) {
    decodedOnlyOperators.push("global-tone");
    unresolvedNativeArtifacts["global-tone"] = ["nativeToneTables", "imageAnalysisState"];
    if (
      snapshot.global.intelligentToneAdjustment.enabled
      || snapshot.global.autoExposure.enabled
    ) {
      decodedOnlyOperators.push("automatic-tone");
      unresolvedNativeArtifacts["automatic-tone"] = ["nativeImageAnalysis"];
    }
  }

  if (Object.values(snapshot.curves).some((points) => points.length > 0)) {
    decodedOnlyOperators.push("rgb-curves");
    unresolvedNativeArtifacts["rgb-curves"] = ["nativeCurveTable"];
  }

  if (snapshot.hsl.length > 0) {
    decodedOnlyOperators.push("hsl");
    unresolvedNativeArtifacts.hsl = ["nativeHslTable"];
  }

  if (Object.keys(snapshot.grading).length > 0 || Object.keys(snapshot.calibration).length > 0) {
    decodedOnlyOperators.push("grading-calibration");
    unresolvedNativeArtifacts["grading-calibration"] = ["nativeGradingMatrix"];
  }

  if (snapshot.localAdjustments.length > 0) {
    decodedOnlyOperators.push("local-adjustments");
    unresolvedNativeArtifacts["local-adjustments"] = ["resolvedMasks", "perLayerNativeTables"];
  }

  if (anyNonZero([
    snapshot.global.dehaze.intelligent,
    snapshot.global.dehaze.amount,
    snapshot.global.dehaze.body,
    snapshot.global.dehaze.background,
    snapshot.global.sharpness,
    snapshot.global.vignette,
    snapshot.global.filmGrain,
  ])) {
    decodedOnlyOperators.push("detail-effects");
    unresolvedNativeArtifacts["detail-effects"] = ["nativeDetailKernel", "portraitMasks"];
    if (
      snapshot.global.dehaze.intelligent !== 0
      || snapshot.global.dehaze.body !== 0
      || snapshot.global.dehaze.background !== 0
      || snapshot.global.filmGrain !== 0
    ) {
      decodedOnlyOperators.push("region-detail-effects");
      unresolvedNativeArtifacts["region-detail-effects"] = ["portraitMasks", "grainControls"];
    }
  }

  if (
    Object.keys(snapshot.profileNumbers).length > 0
    || Object.keys(snapshot.profileStrings).length > 0
    || Object.keys(snapshot.profileMaterials).length > 0
  ) {
    decodedOnlyOperators.push("profile-operators");
    unresolvedNativeArtifacts["profile-operators"] = ["faceProfileSelection", "operatorSpecificRuntime"];
  }

  return {
    filter: snapshot.filter,
    exactOperators,
    recoveredOperators,
    decodedOnlyOperators,
    unresolvedNativeArtifacts,
  };
}
