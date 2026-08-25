"use client";

import {
  type PointerEvent as ReactPointerEvent,
  type WheelEvent as ReactWheelEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  KumoMakeupLibrary,
  KumoMakeupMaterial,
  KumoMakeupSelection,
  renderKumoMakeup,
} from "./kumoMakeup";
import {
  PhotoBoothRenderOptions,
  PhotoPreset,
  PhotoPresetLibrary,
  preparePhotoPreview,
  renderPhotoBooth,
} from "./photoBooth";

const API_URL = "http://127.0.0.1:8417";

export type FilterItem = {
  id: string;
  name: string;
  code?: string;
  detail: string;
  lut: string;
  thumbnail: string;
  default_alpha?: number;
  skin_protection?: number;
};

export type FilterSection = {
  id: string;
  name: string;
  filters: FilterItem[];
};

export type FiltersCatalog = {
  phobien: FilterSection[];
  ai: {
    themes: FilterItem[];
    filters: FilterItem[];
  };
  total_luts: number;
};

export type ColorRefPack = {
  id: string;
  name: string;
  items: string[];
  count: number;
  cover: string;
};

type RunState = "idle" | "analyzing" | "processing" | "done" | "error";
type EffectPhase = "idle" | "loading" | "done" | "error";
type ProfileKey = "man" | "woman" | "child" | "oldwoman" | "oldman";
type HairColorPreset = "none" | "01" | "02" | "03" | "04" | "05" | "06" | "07" | "08";
type LipstickPreset = "luozhuang" | "jiaotang" | "yingtao";
type FaceLiftRegion = "none" | "forehead" | "eyes" | "midface" | "mouth";
type FaceFillRegion = "none" | "forehead" | "tear_trough" | "apple_cheek" | "cheek" | "nose_base" | "aegyosal" | "eye_socket" | "brow_arch" | "chin" | "mouth_corner";
type SkinStrengthKey = "blemish" | "smooth" | "tone" | "white";
type FaceAnalysis = {
  id: number;
  profile: ProfileKey;
  selectedProfile: ProfileKey;
  label: string;
  confidence: number;
  age_group: number;
  demographic_class: number;
  aligned: boolean;
  review_required: boolean;
  thumbnail: string;
  landmarks: number[][];
};

const SKIN_TONE_SWATCHES = [
  { id: "none", label: "Tự nhiên / Gốc", color: "transparent" },
  { id: "skin1", label: "Trắng sứ", color: "#FFFFFF" },
  { id: "skin2", label: "Trắng hồng", color: "#F6E5E0" },
  { id: "skin3", label: "Tự nhiên", color: "#F2DCBA" },
  { id: "skin4", label: "Vàng sáng", color: "#F3E1D3" },
  { id: "skin5", label: "Mật ong", color: "#E4C7A8" },
  { id: "skin6", label: "Rám nắng", color: "#D9B48F" },
  { id: "skin7", label: "Nâu đồng", color: "#8C6547" },
  { id: "skin8", label: "Nâu sô cô la", color: "#5C3E28" },
];

const PROFILE_OPTIONS: Array<{ key: ProfileKey; label: string }> = [
  { key: "man", label: "Nam" },
  { key: "woman", label: "Nữ" },
  { key: "child", label: "Trẻ em" },
  { key: "oldwoman", label: "Nữ lớn tuổi" },
  { key: "oldman", label: "Nam lớn tuổi" },
];

const KUMO_THEME_LIPSTICK: Partial<Record<number, {
  preset: LipstickPreset;
  strength: number;
}>> = {
  // Set ARP “Đẹp Đỏ” không chứa lớp môi: Kumoo ghép son đỏ bằng pipeline
  // MPLIPSTICKV2 riêng. 100 ở đây là 100% mức son Cherry gốc của profile.
  33: { preset: "yingtao", strength: 100 },
};

const PROFILE_STRENGTHS: Record<ProfileKey, {
  fleck: number;
  blemish: number;
  smooth: number;
  tone: number;
  white: number;
}> = {
  man: { fleck: 1, blemish: 90, smooth: 0, tone: 0, white: 0 },
  woman: { fleck: 100, blemish: 100, smooth: 55, tone: 16, white: 10 },
  child: { fleck: 100, blemish: 90, smooth: 0, tone: 0, white: 0 },
  oldwoman: { fleck: 100, blemish: 100, smooth: 29, tone: 12, white: 0 },
  oldman: { fleck: 100, blemish: 100, smooth: 29, tone: 12, white: 0 },
};

const PROFILE_DEFAULTS: Record<ProfileKey, string> = Object.fromEntries(
  PROFILE_OPTIONS.map(({ key }) => {
    const value = PROFILE_STRENGTHS[key];
    return [key, `gợi ý: khuyết điểm ${value.fleck}/${value.blemish} · mịn ${value.smooth} · đều ${value.tone} · sáng ${value.white}`];
  }),
) as Record<ProfileKey, string>;

function effectiveSkinValue(profile: ProfileKey, key: SkinStrengthKey, percent: number) {
  return Math.round(PROFILE_STRENGTHS[profile][key] * Math.max(0, Math.min(100, percent)) / 100);
}

function effectiveSkinValues(faces: FaceAnalysis[], key: SkinStrengthKey, percent: number) {
  if (faces.length === 0 || percent === 0) return "0";
  const values = faces.map((face) => effectiveSkinValue(face.selectedProfile, key, percent));
  return [...new Set(values)].join(" / ");
}

function skinSuggestion(faces: FaceAnalysis[], key: SkinStrengthKey) {
  if (faces.length === 0) return "Chờ nhận diện khuôn mặt";
  return faces.map((face) => `Mặt ${face.id + 1}: ${PROFILE_STRENGTHS[face.selectedProfile][key]}`).join(" · ");
}

const PROFILE_INDEX: Record<ProfileKey, number> = {
  man: 0,
  woman: 1,
  child: 2,
  oldwoman: 3,
  oldman: 4,
};

const HAIR_COLOR_PRESETS: Array<{ key: HairColorPreset; label: string; source: string; detail: string; defaultStrength: number }> = [
  { key: "none", label: "Không", source: "", detail: "Giữ màu tóc gốc", defaultStrength: 0 },
  { key: "01", label: "Hắc trà", source: "黑茶", detail: "Gốc 50%", defaultStrength: 50 },
  { key: "02", label: "Đỏ mâm xôi", source: "树莓红", detail: "Gốc 60%", defaultStrength: 60 },
  { key: "03", label: "Đỏ Hải Vương", source: "海王红", detail: "Gốc 63%", defaultStrength: 63 },
  { key: "04", label: "Nâu xám lạnh", source: "灰棕", detail: "Gốc 80%", defaultStrength: 80 },
  { key: "05", label: "Cam cháy", source: "脏橘", detail: "Gốc 60%", defaultStrength: 60 },
  { key: "06", label: "Đen tự nhiên", source: "自然黑", detail: "Gốc 63%", defaultStrength: 63 },
  { key: "07", label: "Xanh tím", source: "蓝紫", detail: "Gốc 70%", defaultStrength: 70 },
  { key: "08", label: "Nâu chocolate", source: "黑巧", detail: "Gốc 65%", defaultStrength: 65 },
];

const FACE_LIFT_REGIONS: Array<{ key: Exclude<FaceLiftRegion, "none">; label: string; parameter: string; thumbnail: string }> = [
  { key: "forehead", label: "Trán", parameter: "fore_head_smooth", thumbnail: "liftForehead.jpg" },
  { key: "eyes", label: "Mắt", parameter: "periorbital_smooth", thumbnail: "liftEye.jpg" },
  { key: "midface", label: "Giữa mặt", parameter: "malars_smooth", thumbnail: "liftMidface.jpg" },
  { key: "mouth", label: "Miệng", parameter: "perioral_smooth", thumbnail: "liftMouth.jpg" },
];

const FACE_FILL_REGIONS: Array<{ key: Exclude<FaceFillRegion, "none">; label: string; parameter: string; thumbnail: string }> = [
  { key: "forehead", label: "Trán", parameter: "fore_head_fillers", thumbnail: "fullForehead.jpg" },
  { key: "tear_trough", label: "Rãnh lệ", parameter: "tear_trough", thumbnail: "fullTearTrough.jpg" },
  { key: "apple_cheek", label: "Gò má", parameter: "apple_cheek_fillers", thumbnail: "fullAppleCheek.jpg" },
  { key: "cheek", label: "Má", parameter: "jowl_fill", thumbnail: "fullCheek.jpg" },
  { key: "nose_base", label: "Gốc mũi", parameter: "nose_fillers", thumbnail: "fullNoseBase.jpg" },
  { key: "aegyosal", label: "Bọng mắt", parameter: "aegyosal_fill", thumbnail: "fullAegyosal.jpg" },
  { key: "eye_socket", label: "Hốc mắt", parameter: "eye_socket_fillers", thumbnail: "fullEyeSocket.jpg" },
  { key: "brow_arch", label: "Khung mày", parameter: "brow_arch_fill", thumbnail: "fullBrowArch.jpg" },
  { key: "chin", label: "Cằm", parameter: "chin_fillers", thumbnail: "fullChin.jpg" },
  { key: "mouth_corner", label: "Khóe miệng", parameter: "angulus_oris_fill", thumbnail: "fullMouthCorner.jpg" },
];

const PRO_MODULES = [
  { icon: "▦", title: "PhotoBooth", detail: "84 preset Kumo", state: "Đang dùng", ready: true },
  { icon: "✦", title: "Trang điểm Pro", detail: "Catalog Kumo đã xác thực", state: "Đang dùng", ready: true },
  { icon: "◌", title: "Tóc & đường viền", detail: "Het + HairSeamer + 8 màu gốc", state: "Đang dùng", ready: true },
  { icon: "◇", title: "Nâng cơ & đầy đặn", detail: "4 vùng nâng · 10 vùng đầy đặn", state: "Đang dùng", ready: true },
  { icon: "🎨", title: "Bộ lọc & Chuyển màu", detail: "135 3D LUT + 10 gói màu Kumo", state: "Đang dùng", ready: true },
] as const;

const MAKEUP_TAB_ORDER = [
  "set",
  "eyelash",
  "mouth",
  "feature",
  "blush",
  "eyesocket",
  "eye",
  "eyebrow",
  "eyeliner",
  "makeup_highlight",
  "eyeshadow",
  "facialdecals",
] as const;

const MAKEUP_TAB_LABELS: Record<string, string> = {
  set: "Set",
  eyelash: "Lông mi",
  mouth: "Son bóng",
  feature: "Khối",
  blush: "Má hồng",
  eyesocket: "Mắt cười",
  eye: "Lens",
  eyebrow: "Lông mày",
  eyeliner: "Kẻ mắt",
  makeup_highlight: "Tạo khối sáng",
  eyeshadow: "Phấn mắt",
  facialdecals: "Điểm nhấn",
};

function makeupAssetUrl(path: string) {
  return path.startsWith("/assets/makeup/")
    ? `${API_URL}/api/assets/makeup/${path.slice("/assets/makeup/".length)}`
    : path;
}

function normalizeMakeupLibrary(library: KumoMakeupLibrary): KumoMakeupLibrary {
  return {
    ...library,
    parts: library.parts.map((part) => ({
      ...part,
      name: part.key === "eyesocket" ? MAKEUP_TAB_LABELS.eyesocket : part.name,
      materials: part.materials.map((material) => ({
        ...material,
        thumb: makeupAssetUrl(material.thumb),
        layers: material.layers.map((layer) => ({
          ...layer,
          tex: makeupAssetUrl(layer.tex),
          maskTex: layer.maskTex ? makeupAssetUrl(layer.maskTex) : null,
          clip: layer.clip ? makeupAssetUrl(layer.clip) : null,
        })),
      })),
    })),
    themes: library.themes.map((theme) => ({ ...theme, thumb: makeupAssetUrl(theme.thumb) })),
  };
}

type PresetMakeupParameter = { id?: string; alpha?: number; color?: string };

// PhotoBooth metadata also contains full-face operators such as Bronzers and
// ReconstructorV2p5D. Those are not ordinary 2D ARP overlays: Kumo evaluates
// them with a dedicated face mesh/operator. Drawing their source texture as a
// flat soft-light layer exposes the technical contour map on skin. Keep preset
// auto-makeup limited to the 2D contracts that this renderer implements
// faithfully; users can still choose every material explicitly in Makeup Pro.
const PHOTO_PRESET_SAFE_MAKEUP_PARTS = new Set([
  "blush",
  "eye",
  "eyebrow",
  "eyelash",
  "eyeshadow",
  "eyesocket",
  "mouth",
  "eyeliner",
]);

function photoPresetMakeupSelection(
  preset: PhotoPreset | null,
  profile: ProfileKey,
  library: KumoMakeupLibrary,
  strength: number,
): KumoMakeupSelection {
  if (!preset || strength <= 0) return {};
  const selection: KumoMakeupSelection = {};
  const profileIndex = PROFILE_INDEX[profile];
  for (const part of library.parts) {
    if (!PHOTO_PRESET_SAFE_MAKEUP_PARTS.has(part.key)) continue;
    const values = preset.all_params?.[part.key];
    const parameter = Array.isArray(values)
      ? values[profileIndex] as PresetMakeupParameter | undefined
      : values as PresetMakeupParameter | undefined;
    const alpha = Number(parameter?.alpha ?? 0);
    if (!parameter?.id || !Number.isFinite(alpha) || alpha <= 0) continue;
    const material = part.materials.find((item) => item.dir === parameter.id);
    if (!material?.layers.length) continue;
    const colorValues = typeof parameter.color === "string"
      ? parameter.color.split(";").slice(0, 3).map(Number)
      : [];
    selection[part.key] = {
      partKey: part.key,
      dir: material.dir,
      layers: material.layers,
      amount: alpha * Math.max(0, Math.min(100, strength)) / 100,
      color: colorValues.length === 3
        && colorValues.every(Number.isFinite)
        && colorValues.some((value) => value !== 0)
        ? colorValues as [number, number, number]
        : null,
    };
  }
  return selection;
}

export default function Home() {
  const inputRef = useRef<HTMLInputElement>(null);
  const analysisRequest = useRef(0);
  const analysisAbort = useRef<AbortController | null>(null);
  const processingRequest = useRef(0);
  const processingAbort = useRef<AbortController | null>(null);
  const modelRenderChain = useRef<Promise<void>>(Promise.resolve());
  const resultUrlRef = useRef<string | null>(null);
  const serverResultBlobRef = useRef<Blob | null>(null);
  const makeupRenderRequest = useRef(0);
  const previewRenderChain = useRef<Promise<void>>(Promise.resolve());
  const makeupSelectionRef = useRef<KumoMakeupSelection>({});
  const makeupLibraryRef = useRef<KumoMakeupLibrary | null>(null);
  const photoBoothRef = useRef<PhotoBoothRenderOptions>({
    preset: null,
    presetStrength: 100,
  });
  const analyzedFileRef = useRef<File | null>(null);
  const sourceImageSizeRef = useRef<{ width: number; height: number } | null>(null);
  const lastBaseSignature = useRef<string | null>(null);
  const effectLabelRef = useRef("Làm đẹp chân dung tự động");
  const previewDragRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    panX: number;
    panY: number;
  } | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [originalUrl, setOriginalUrl] = useState<string | null>(null);
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [isComparing, setIsComparing] = useState(false);
  const [previewZoom, setPreviewZoom] = useState(100);
  const [previewPan, setPreviewPan] = useState({ x: 0, y: 0 });
  const [previewDragging, setPreviewDragging] = useState(false);
  const [runState, setRunState] = useState<RunState>("idle");
  const [message, setMessage] = useState("Sẵn sàng nhận ảnh");
  const [processingMs, setProcessingMs] = useState<string | null>(null);
  const [apiOnline, setApiOnline] = useState(false);
  // Mặc định 0, không tự làm đẹp — chooseFile sets actual values when image is uploaded
  const [skinFleckClean, setSkinFleckClean] = useState(0);
  const [smoothFaceSkin, setSmoothFaceSkin] = useState(0);
  const [smoothTextureSkin, setSmoothTextureSkin] = useState(0);
  const [skinToneFace, setSkinToneFace] = useState(0);
  const [skinToneMultiple, setSkinToneMultiple] = useState(0);
  const [skinWhite, setSkinWhite] = useState(0);
  const [skinColorPreset, setSkinColorPreset] = useState<string>("none");
  const [skinColorStrength, setSkinColorStrength] = useState<number>(0);
  const [hairColorStrength, setHairColorStrength] = useState(100);
  const [hairColorPreset, setHairColorPreset] = useState<HairColorPreset>("none");
  const [faceLiftRegion, setFaceLiftRegion] = useState<FaceLiftRegion>("none");
  const [faceLiftStrength, setFaceLiftStrength] = useState(50);
  const [faceFillRegion, setFaceFillRegion] = useState<FaceFillRegion>("none");
  const [faceFillStrength, setFaceFillStrength] = useState(50);
  const [faces, setFaces] = useState<FaceAnalysis[]>([]);
  const [makeupLibrary, setMakeupLibrary] = useState<KumoMakeupLibrary | null>(null);
  const [makeupSelection, setMakeupSelection] = useState<KumoMakeupSelection>({});

  
  const [makeupTab, setMakeupTab] = useState<string>("set");
  const [makeupThemeId, setMakeupThemeId] = useState<number | null>(null);
  const [makeupLipstickPreset, setMakeupLipstickPreset] = useState<LipstickPreset>("yingtao");
  const [makeupLipstickStrength, setMakeupLipstickStrength] = useState(0);
  const [photoLibrary, setPhotoLibrary] = useState<PhotoPresetLibrary | null>(null);
  const [photoCategoryId, setPhotoCategoryId] = useState<number | null>(null);
  const [photoPresetId, setPhotoPresetId] = useState<number | null>(null);
  const [photoPresetStrength, setPhotoPresetStrength] = useState(100);
  const [filtersCatalog, setFiltersCatalog] = useState<FiltersCatalog | null>(null);
  const [colorRefPacks, setColorRefPacks] = useState<ColorRefPack[]>([]);
  const [filterId, setFilterId] = useState<string>("none");
  const [filterStrength, setFilterStrength] = useState<number>(100);
  const [filterTab, setFilterTab] = useState<"phobien" | "ai">("phobien");
  const [activeColorPackId, setActiveColorPackId] = useState<string | null>(null);
  const [selectedColorRef, setSelectedColorRef] = useState<string | null>(null);
  const filterRef = useRef({ filterId: "none", filterStrength: 100 });

  useEffect(() => {
    filterRef.current = { filterId, filterStrength };
  }, [filterId, filterStrength]);

  const [effectStatus, setEffectStatus] = useState<{ phase: EffectPhase; label: string }>({
    phase: "idle",
    label: "",
  });

  const activePhotoPreset = useMemo(
    () => photoLibrary?.presets.find((preset) => preset.id === photoPresetId) ?? null,
    [photoLibrary, photoPresetId],
  );

  const markEffectPending = useCallback((label: string) => {
    effectLabelRef.current = label;
    setEffectStatus({ phase: "loading", label });
  }, []);

  /**
   * PhotoBooth presets are complete Kumo snapshots, not additive filters.
   * Selecting one gives that snapshot exclusive ownership of every operator it
   * carries. Clear independent editor state here so an old Makeup Pro set,
   * manual retouch, face warp or hair colour can never
   * leak into the preset result.
   */
  function activatePhotoPreset(presetId: number | null, label: string) {
    markEffectPending(label);
    setPhotoPresetId(presetId);
    makeupSelectionRef.current = {};
    if (presetId === null) return;
    setSkinFleckClean(100);
    setSmoothFaceSkin(55);
    setSmoothTextureSkin(50);
    setSkinToneFace(16);
    setSkinWhite(10);
    setHairColorPreset("none");
    setFaceLiftRegion("none");
    setFaceFillRegion("none");
    setMakeupThemeId(null);
    setMakeupLipstickStrength(30);
    setMakeupSelection({});
  }

  function leavePhotoPreset() {
    if (photoPresetId !== null) setPhotoPresetId(null);
  }

  function setPreviewViewZoom(nextZoom: number) {
    const clampedZoom = Math.min(300, Math.max(50, nextZoom));
    setPreviewZoom(clampedZoom);
    if (clampedZoom <= 100) setPreviewPan({ x: 0, y: 0 });
  }

  function resetPreviewView() {
    previewDragRef.current = null;
    setPreviewDragging(false);
    setPreviewZoom(100);
    setPreviewPan({ x: 0, y: 0 });
  }

  function handlePreviewWheel(event: ReactWheelEvent<HTMLDivElement>) {
    // Trình duyệt cảnh báo preventDefault ở sự kiện cuộn (passive), nên ta bỏ đi.
    setPreviewViewZoom(previewZoom + (event.deltaY < 0 ? 25 : -25));
  }

  function handlePreviewPointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return;
    setIsComparing(true);
    if (previewZoom <= 100) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    previewDragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      panX: previewPan.x,
      panY: previewPan.y,
    };
    setPreviewDragging(true);
  }

  function handlePreviewPointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    const drag = previewDragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const zoomOverflow = previewZoom / 100 - 1;
    const maxX = event.currentTarget.clientWidth * zoomOverflow / 2;
    const maxY = event.currentTarget.clientHeight * zoomOverflow / 2;
    setPreviewPan({
      x: Math.max(-maxX, Math.min(maxX, drag.panX + event.clientX - drag.startX)),
      y: Math.max(-maxY, Math.min(maxY, drag.panY + event.clientY - drag.startY)),
    });
  }

  function handlePreviewPointerUp(event: ReactPointerEvent<HTMLDivElement>) {
    setIsComparing(false);
    const drag = previewDragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    previewDragRef.current = null;
    setPreviewDragging(false);
  }

  useEffect(() => {
    makeupSelectionRef.current = makeupSelection;
  }, [makeupSelection]);

  useEffect(() => {
    makeupLibraryRef.current = makeupLibrary;
  }, [makeupLibrary]);

  useEffect(() => {
    photoBoothRef.current = {
      preset: activePhotoPreset,
      presetStrength: photoPresetStrength,
    };
  }, [activePhotoPreset, photoPresetStrength]);

  useEffect(() => {
    let active = true;
    fetch(`${API_URL}/api/makeup/library`, { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error("Không tải được thư viện trang điểm Kumo.");
        return response.json() as Promise<KumoMakeupLibrary>;
      })
      .then((library) => {
        if (active) setMakeupLibrary(normalizeMakeupLibrary(library));
      })
      .catch(() => {
        if (active) setMakeupLibrary(null);
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    fetch(`${API_URL}/api/photobooth/library`, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("Không tải được thư viện PhotoBooth.");
        return response.json() as Promise<PhotoPresetLibrary>;
      })
      .then((library) => {
        if (!active) return;
        const normalized: PhotoPresetLibrary = {
          ...library,
          presets: library.presets.map((preset) => ({
            ...preset,
            cover: `${API_URL}${preset.cover}`,
          })),
        };
        setPhotoLibrary(normalized);
        setPhotoCategoryId(normalized.categories[0]?.id ?? null);
      })
      .catch(() => {
        if (active) setPhotoLibrary(null);
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    fetch(`${API_URL}/api/filters/library`, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("Không tải được thư viện bộ lọc.");
        return response.json() as Promise<FiltersCatalog>;
      })
      .then((catalog) => {
        if (active) setFiltersCatalog(catalog);
      })
      .catch(() => {
        if (active) setFiltersCatalog(null);
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    fetch(`${API_URL}/api/color_ref/packs`, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) return [];
        return response.json() as Promise<ColorRefPack[]>;
      })
      .then((packs) => {
        if (active) {
          const normalized = packs.map((pack) => ({
            ...pack,
            cover: pack.cover.startsWith("http") ? pack.cover : pack.cover,
            items: pack.items.map((item) => (item.startsWith("http") ? item : item)),
          }));
          setColorRefPacks(normalized);
        }
      })
      .catch(() => {
        if (active) setColorRefPacks([]);
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;

    async function checkHealth() {
      try {
        const response = await fetch(`${API_URL}/api/health`, { cache: "no-store" });
        const data = await response.json();
        if (active) setApiOnline(Boolean(response.ok && data.ok));
      } catch {
        if (active) setApiOnline(false);
      }
    }

    void checkHealth();
    const timer = window.setInterval(() => void checkHealth(), 2500);
    window.addEventListener("focus", checkHealth);
    return () => {
      active = false;
      window.clearInterval(timer);
      window.removeEventListener("focus", checkHealth);
    };
  }, []);

  useEffect(() => {
    function onPaste(event: ClipboardEvent) {
      const pasted = Array.from(event.clipboardData?.files ?? []).find((item) => item.type.startsWith("image/"));
      if (pasted) chooseFile(pasted);
    }
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  });

  const publishResultBlob = useCallback((blob: Blob) => {
    const nextResultUrl = URL.createObjectURL(blob);
    if (resultUrlRef.current) URL.revokeObjectURL(resultUrlRef.current);
    resultUrlRef.current = nextResultUrl;
    setResultUrl(nextResultUrl);
  }, []);

  const renderMakeupPreview = useCallback((
    baseBlob: Blob,
    selection = makeupSelectionRef.current,
    library = makeupLibraryRef.current,
  ) => {
    const requestId = ++makeupRenderRequest.current;
    const effectLabel = effectLabelRef.current;
    setEffectStatus({ phase: "loading", label: effectLabel });
    const run = async () => {
      if (requestId !== makeupRenderRequest.current) return;
      try {
        // Single Source of Truth (Server Engine):
        // Server handles all neural models, retouching, whitening, lipstick,
        // and 3D LUT presets. When in Photo Preset mode or when no custom makeup
        // is selected, display the server result directly with 0 duplicate layers.
        const photoOptions = photoBoothRef.current;
        const effectiveSelection = photoOptions.preset ? {} : selection;
        if (photoOptions.preset || !library || Object.keys(effectiveSelection).length === 0) {
          publishResultBlob(baseBlob);
          setEffectStatus({ phase: "done", label: effectLabel });
          return;
        }

        let rendered = await preparePhotoPreview(baseBlob);
        if (requestId !== makeupRenderRequest.current) return;

        const faceSelections = faces.map((face) => (
          (face.selectedProfile === "woman" || face.selectedProfile === "oldwoman") ? effectiveSelection : {}
        ));
        if (faceSelections.some((faceSelection) => Object.keys(faceSelection).length > 0)) {
          rendered = await renderKumoMakeup(
            rendered,
            faces.map((face) => face.landmarks),
            selection,
            library,
            `${API_URL}/api/assets/makeup/face_oval.png`,
            faceSelections,
            sourceImageSizeRef.current,
          );
        }
        if (requestId !== makeupRenderRequest.current) return;
        publishResultBlob(rendered);
        setEffectStatus({ phase: "done", label: effectLabel });
      } catch (error) {
        if (requestId === makeupRenderRequest.current) {
          setEffectStatus({ phase: "error", label: effectLabel });
        }
        throw error;
      }
    };

    const task = previewRenderChain.current.catch(() => undefined).then(run);
    previewRenderChain.current = task.catch(() => undefined);
    return task;
  }, [faces, publishResultBlob]);

  async function chooseFile(next?: File) {
    if (!next || !next.type.startsWith("image/")) return;
    if (next.size > 20 * 1024 * 1024) {
      setRunState("error");
      setMessage("Ảnh lớn hơn giới hạn 20 MB.");
      return;
    }
    try {
      const sourceBitmap = await createImageBitmap(next);
      sourceImageSizeRef.current = {
        width: sourceBitmap.width,
        height: sourceBitmap.height,
      };
      sourceBitmap.close();
    } catch {
      sourceImageSizeRef.current = null;
    }
    if (originalUrl) URL.revokeObjectURL(originalUrl);
    if (resultUrl) URL.revokeObjectURL(resultUrl);
    resultUrlRef.current = null;
    serverResultBlobRef.current = null;
    analyzedFileRef.current = null;
    makeupRenderRequest.current += 1;
    processingRequest.current += 1;
    processingAbort.current?.abort();
    analysisAbort.current?.abort();
    setFile(next);
    setOriginalUrl(URL.createObjectURL(next));
    setResultUrl(null);
    setFaces([]);
    setSkinFleckClean(0);
    setSmoothFaceSkin(0);
    setSmoothTextureSkin(0);
    setSkinToneFace(0);
    setSkinWhite(0);
    setHairColorPreset("none");
    setFaceLiftRegion("none");
    setFaceFillRegion("none");
    setMakeupThemeId(null);
    setMakeupLipstickStrength(30);
    setMakeupSelection({});
    setPhotoPresetId(null);
    lastBaseSignature.current = null;
    setRunState("analyzing");
    effectLabelRef.current = "Nhận diện khuôn mặt";
    setEffectStatus({ phase: "loading", label: "Nhận diện khuôn mặt" });
    setMessage("Ga2 đang phân loại riêng từng khuôn mặt theo 9 lớp Kumo…");
    
    resetPreviewView();

    const requestId = ++analysisRequest.current;
    const controller = new AbortController();
    analysisAbort.current = controller;
    const body = new FormData();
    body.append("image", next);
    try {
      const response = await fetch(`${API_URL}/api/portrait/analyze`, {
        method: "POST",
        body,
        signal: controller.signal,
      });
      if (!response.ok) {
        const problem = await response.json().catch(() => null);
        throw new Error(problem?.detail || "Ga2 không phân tích được ảnh.");
      }
      const data = await response.json();
      if (requestId !== analysisRequest.current) return;
      setApiOnline(true);
      
      if (data.image_width && data.image_height) {
        sourceImageSizeRef.current = {
          width: data.image_width,
          height: data.image_height,
        };
      }

      const detected = (data.faces as Omit<FaceAnalysis, "selectedProfile">[]).map((face) => ({
        ...face,
        selectedProfile: face.profile,
      }));
      analyzedFileRef.current = next;
      setFaces(detected);
      setRunState("idle");
      setEffectStatus({ phase: "done", label: `Đã nhận diện ${detected.length} khuôn mặt` });
      const uncertain = detected.filter((face) => face.review_required).length;
      setMessage(uncertain > 0
        ? `Đã nhận ${detected.length} khuôn mặt · ${uncertain} mặt cần bạn xác nhận nhóm`
        : `Đã nhận ${detected.length} khuôn mặt · profile Gốc được đặt riêng từng người`);
    } catch (error) {
      if (requestId !== analysisRequest.current) return;
      if (error instanceof DOMException && error.name === "AbortError") return;
      setRunState("error");
      setEffectStatus({ phase: "error", label: "Nhận diện khuôn mặt" });
      setMessage(error instanceof Error ? error.message : "Không phân tích được khuôn mặt.");
    }
  }

  const processImage = useCallback(async (requestId: number) => {
    if (!file || requestId !== processingRequest.current) return;
    const controller = new AbortController();
    processingAbort.current = controller;
    setRunState("processing");
    const effectLabel = effectLabelRef.current;
    setEffectStatus({ phase: "loading", label: effectLabel });
    setMessage("Kumoo đang tự áp dụng thay đổi…");
    const body = new FormData();
    body.append("image", file);
    const isolatedPreset = activePhotoPreset;

    body.append("skin_fleck_clean_flag", String(isolatedPreset ? 0 : skinFleckClean));
    body.append("smooth_face_skin_alpha", String(isolatedPreset ? 0 : smoothFaceSkin));
    body.append("smooth_texture_skin_alpha", String(isolatedPreset ? 0 : smoothTextureSkin));
    body.append("skin_tone_face_alpha", String(isolatedPreset ? 0 : skinToneFace));
    body.append("skin_white_alpha", String(isolatedPreset ? 0 : skinWhite));
    body.append("skin_tone_multiple_alpha", String(isolatedPreset ? 0 : skinToneMultiple));
    body.append("skin_color_lut_preset", isolatedPreset ? "none" : skinColorPreset);
    body.append("skin_color_lut_alpha", String(isolatedPreset ? 0 : (skinColorPreset === "none" ? 0 : skinColorStrength)));
    // Most ARP themes carry their mouth material locally. “Đẹp Đỏ” is the
    // exception: Kumoo applies Cherry through its separate MPLIPSTICKV2 pass.
    body.append("lipstick_alpha", String(isolatedPreset ? 0 : makeupLipstickStrength));
    body.append("lipstick_preset", makeupLipstickPreset);
    body.append("hair_color_strength", String(isolatedPreset ? 0 : hairColorStrength));
    body.append("hair_color_preset", isolatedPreset ? "none" : hairColorPreset);
    body.append("face_lift_region", isolatedPreset ? "none" : faceLiftRegion);
    body.append("face_lift_strength", String(faceLiftStrength));
    body.append("face_fill_region", isolatedPreset ? "none" : faceFillRegion);
    body.append("filter_id", filterId);
    body.append("filter_strength", String(filterStrength));
    body.append("profile_overrides", JSON.stringify(faces.map((face) => face.selectedProfile)));
    if (isolatedPreset) {
      body.append("photo_preset_params", JSON.stringify(isolatedPreset.all_params));
      body.append("photo_preset_strength", String(photoPresetStrength));
    }
    try {
      const response = await fetch(`${API_URL}/api/portrait/beautify`, {
        method: "POST",
        body,
        signal: controller.signal,
      });
      if (!response.ok) {
        const problem = await response.json().catch(() => null);
        throw new Error(problem?.detail || "Server không xử lý được ảnh.");
      }
      const blob = await response.blob();
      if (requestId !== processingRequest.current) return;
      serverResultBlobRef.current = blob;
      await renderMakeupPreview(blob);
      if (requestId !== processingRequest.current) return;
      setProcessingMs(response.headers.get("X-Processing-Ms"));
      setApiOnline(true);
      setRunState("done");
      setEffectStatus({ phase: "done", label: effectLabel });
      setMessage("Đã hoàn thành bằng runtime độc lập trên CPU");
      
    } catch (error) {
      if (requestId !== processingRequest.current) return;
      if (error instanceof DOMException && error.name === "AbortError") return;
      setRunState("error");
      setEffectStatus({ phase: "error", label: effectLabel });
      setMessage(error instanceof Error ? error.message : "Không kết nối được server ONNX.");
      if (error instanceof TypeError) setApiOnline(false);
    }
  }, [activePhotoPreset, faceFillRegion, faceFillStrength, faceLiftRegion, faceLiftStrength, file, faces, filterId, filterStrength, hairColorPreset, hairColorStrength, makeupLipstickPreset, makeupLipstickStrength, photoPresetStrength, renderMakeupPreview, skinColorPreset, skinColorStrength, skinFleckClean, skinToneFace, skinToneMultiple, skinWhite, smoothFaceSkin, smoothTextureSkin]);

  useEffect(() => {
    const baseBlob = serverResultBlobRef.current;
    if (!baseBlob) return;
    const timer = window.setTimeout(() => {
      void renderMakeupPreview(baseBlob, makeupSelection, makeupLibrary).catch(() => undefined);
    }, 80);
    return () => window.clearTimeout(timer);
  }, [filterId, filterStrength, makeupLibrary, makeupSelection, photoLibrary, photoPresetId, photoPresetStrength, renderMakeupPreview]);

  const queueProcessImage = useCallback((requestId: number) => {
    const run = async () => {
      if (requestId !== processingRequest.current) return;
      await processImage(requestId);
    };
    // Kumo serializes the expensive model stage. Aborting an HTTP request does
    // not stop CPU inference that already started on FastAPI, so keep one base
    // job active and coalesce every queued change to the newest request.
    const task = modelRenderChain.current.catch(() => undefined).then(run);
    modelRenderChain.current = task.catch(() => undefined);
    return task;
  }, [processImage]);

  useEffect(() => {
    if (!file || analyzedFileRef.current !== file || faces.length === 0 || !apiOnline) return;
    const requestId = ++processingRequest.current;
    // A base/model change makes any in-flight local composite stale. Local
    // controls can still preview against the last completed base while this
    // request waits, but an older preview may never overwrite the new base.
    makeupRenderRequest.current += 1;
    const baseSignature = JSON.stringify({
      file: [file.name, file.size, file.lastModified],
      skinFleckClean,
      smoothFaceSkin,
      smoothTextureSkin,
      skinToneFace,
      skinWhite,
      filterId,
      filterStrength,
      makeupLipstickPreset,
      makeupLipstickStrength,
      profiles: faces.map((face) => face.selectedProfile),
      photoPreset: activePhotoPreset
        ? [activePhotoPreset.id, photoPresetStrength]
        : null,
    });
    // If the photo preset changes, we MUST trigger the backend because it overrides skin params
    const isPresetChanged = JSON.parse(lastBaseSignature.current || "{}").photoPreset?.[0] !== (activePhotoPreset?.id);
    const materialOnly = lastBaseSignature.current === baseSignature && !isPresetChanged;
    lastBaseSignature.current = baseSignature;
    // Kumo keeps the analyzed portrait and hair matte alive; changing a hair
    // material should therefore feel immediate. Makeup is composited locally.
    // Base/model
    // controls retain the longer debounce so a dragged slider cannot queue
    // several expensive inference passes.
    const timer = window.setTimeout(
      () => void queueProcessImage(requestId),
      materialOnly ? 120 : 420,
    );
    return () => window.clearTimeout(timer);
  }, [activePhotoPreset, apiOnline, faceFillRegion, faceFillStrength, faceLiftRegion, faceLiftStrength, faces, file, filterId, filterStrength, makeupLipstickPreset, makeupLipstickStrength, photoPresetStrength, queueProcessImage, skinFleckClean, skinToneFace, skinWhite, smoothFaceSkin, smoothTextureSkin]);

  function chooseMakeupMaterial(partKey: string, material: KumoMakeupMaterial) {
    const partName = makeupLibraryRef.current?.parts.find((part) => part.key === partKey)?.name ?? "Trang điểm";
    markEffectPending(`${partName} · ${material.name}`);
    leavePhotoPreset();
    setMakeupThemeId(null);
    setMakeupLipstickStrength(0);
    setMakeupSelection((current) => ({
      ...current,
      [partKey]: {
        partKey,
        dir: material.dir,
        layers: material.layers,
        amount: material.alpha,
        color: material.rgb ?? null,
      },
    }));
  }

  function clearMakeupPart(partKey: string) {
    const partName = makeupLibraryRef.current?.parts.find((part) => part.key === partKey)?.name ?? "Trang điểm";
    markEffectPending(`Tắt ${partName.toLowerCase()}`);
    leavePhotoPreset();
    setMakeupThemeId(null);
    setMakeupLipstickStrength(0);
    setMakeupSelection((current) => {
      const next = { ...current };
      delete next[partKey];
      return next;
    });
  }

  function applyMakeupTheme(themeId: number) {
    if (!makeupLibrary) return;
    const theme = makeupLibrary.themes.find((item) => item.id === themeId);
    if (!theme) return;
    markEffectPending(`Set trang điểm · ${theme.name}`);
    leavePhotoPreset();
    const next: KumoMakeupSelection = {};
    for (const entry of theme.parts) {
      const part = makeupLibrary.parts.find((item) => item.key === entry.key);
      const material = part?.materials.find((item) => item.dir === entry.material);
      if (!material?.layers.length) continue;
      const colorValues = entry.color
        ? entry.color.split(";").slice(0, 3).map(Number)
        : [];
      next[entry.key] = {
        partKey: entry.key,
        dir: material.dir,
        layers: material.layers,
        // Kumo applies the Set alpha and the material's own MakeupAlpha in
        // sequence.  Replacing the material alpha with the Set alpha made
        // low-strength layers (especially pupil, blush and lipstick) roughly
        // twice as strong as the original application.
        amount: Math.round(
          ((theme.alpha ?? 100) * (material.alpha ?? 100)) / 100,
        ),
        color: colorValues.length === 3 && colorValues.every(Number.isFinite)
          ? colorValues as [number, number, number]
          : null,
      };
    }
    const lipstick = KUMO_THEME_LIPSTICK[theme.id];
    setMakeupLipstickPreset(lipstick?.preset ?? "yingtao");
    setMakeupLipstickStrength(lipstick?.strength ?? 0);
    setMakeupThemeId(themeId);
    setMakeupSelection(next);
  }

  function reset() {
    if (originalUrl) URL.revokeObjectURL(originalUrl);
    if (resultUrl) URL.revokeObjectURL(resultUrl);
    resultUrlRef.current = null;
    serverResultBlobRef.current = null;
    makeupRenderRequest.current += 1;
    lastBaseSignature.current = null;
    analyzedFileRef.current = null;
    analysisAbort.current?.abort();
    processingAbort.current?.abort();
    processingRequest.current += 1;
    setFile(null);
    setOriginalUrl(null);
    setResultUrl(null);
    setRunState("idle");
    setEffectStatus({ phase: "idle", label: "" });
    setMessage("Sẵn sàng nhận ảnh");
    setProcessingMs(null);
    setFaces([]);
    resetPreviewView();
    analysisRequest.current += 1;
  }

  const activeMakeupPart = makeupLibrary?.parts.find((part) => part.key === makeupTab) ?? null;
  const activeMakeupPick = activeMakeupPart ? makeupSelection[activeMakeupPart.key] : null;
  const activeMakeupCount = Object.keys(makeupSelection).length;
  const makeupMaterialCount = makeupLibrary?.parts.reduce(
    (total, part) => total + part.materials.length,
    0,
  ) ?? null;
  const makeupThemeCount = makeupLibrary?.themes.length ?? null;
  const makeupCatalogSummary = makeupMaterialCount === null || makeupThemeCount === null
    ? "Đang tải catalog Kumo"
    : `${makeupMaterialCount} vật liệu · ${makeupThemeCount} Set Kumo`;
  const visiblePhotoPresets = photoLibrary?.presets.filter((preset) => preset.category_id === photoCategoryId) ?? [];

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand" aria-label="Lumi Portrait Lab">
          <span className="brand-mark">L</span>
          <span>Lumi Portrait</span>
          <small>AI LAB</small>
        </div>
        <div className="top-actions">
          <span className={`status ${apiOnline ? "online" : "offline"}`}><i /> {apiOnline ? "Kumoo server trực tuyến" : "Đang chờ Kumoo server"}</span>
          {file && <button className="ghost-button" onClick={reset}>Ảnh mới</button>}
        </div>
      </header>

      <div className="workspace">
        <aside className="sidebar">
          <p className="eyebrow">CÔNG CỤ AI</p>
          <nav aria-label="Công cụ xử lý ảnh">
            <button className="nav-item active"><span>✦</span><b>Làm đẹp chân dung</b><small>Đang thử nghiệm</small></button>
            <a className="nav-item nav-link" href="#photobooth"><span>▦</span><b>PhotoBooth</b><small>84 preset Kumo</small></a>
            <a className="nav-item nav-link" href="#makeup-pro"><span>✧</span><b>Trang điểm Pro</b><small>{makeupCatalogSummary}</small></a>
            <a className="nav-item nav-link" href="#hair-color"><span>◌</span><b>Màu tóc</b><small>8 thumbnail Kumo gốc</small></a>
            <a className="nav-item nav-link" href="#face-volume"><span>◇</span><b>Nâng cơ &amp; đầy đặn</b><small>4 vùng nâng · 10 vùng đầy đặn</small></a>
            <button className="nav-item" disabled><span>◇</span><b>Chỉnh dáng</b><small>Chưa mở operator</small></button>
          </nav>
          <div className="model-note">
            <span>MODEL ĐANG DÙNG</span>
            <b>Fd + Ga2 + Lp106</b>
            <p>9 model + 3 operator Kumo · profile riêng từng mặt</p>
          </div>
        </aside>

        <section className="content">
          <div className="intro">
            <div><p className="eyebrow">PHÒNG THỬ NGHIỆM 01</p><h1>Làm đẹp chân dung</h1></div>
            <p>Chạy hệ thống Kumo theo vùng thật: làm đẹp da, son môi và đổi màu tóc bằng material gốc.</p>
          </div>

          <div className="studio-grid">
            <section className="canvas-card">
              <div className="preview-toolbar">
                <div><span className="live-pill"><i /> LIVE</span><b>Xem trước</b></div>
                <div style={{display: 'flex', gap: '12px', alignItems: 'center'}}>
                  {resultUrl && (
                    <button 
                      className="ghost-button" 
                      style={{padding: '4px 12px', fontSize: '12px'}}
                      onPointerDown={() => setIsComparing(true)} 
                      onPointerUp={() => setIsComparing(false)}
                      onPointerLeave={() => setIsComparing(false)}
                    >
                      Nhấn giữ để So sánh
                    </button>
                  )}
                  <span>{effectStatus.phase === "loading" ? `Đang áp dụng · ${effectStatus.label}` : resultUrl ? "Đã đồng bộ" : "Ảnh gốc"}</span>
                </div>
              </div>
              {originalUrl ? (
                <div
                  className={`comparison ${previewZoom > 100 ? "zoomed" : ""} ${previewDragging ? "dragging" : ""}`}
                  onWheel={handlePreviewWheel}
                  onPointerDownCapture={handlePreviewPointerDown}
                  onPointerMove={handlePreviewPointerMove}
                  onPointerUp={handlePreviewPointerUp}
                  onPointerCancel={handlePreviewPointerUp}
                  onPointerLeave={() => setIsComparing(false)}
                  onDoubleClick={resetPreviewView}
                >
                  <div
                    className="preview-plane"
                    style={{ transform: `translate(${previewPan.x}px, ${previewPan.y}px) scale(${previewZoom / 100})` }}
                  >
                    {/* Object URLs are local previews and cannot use a build-time image optimizer. */}
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img className="result-image" src={(isComparing ? originalUrl : resultUrl) ?? originalUrl} alt="Kết quả làm đẹp chân dung" draggable={false} />
                  </div>
                </div>
              ) : (
                <div className="portrait-placeholder"><div className="face-orbit" /><span>Ảnh của bạn sẽ xuất hiện tại đây</span></div>
              )}
              {originalUrl && (
                <div className="preview-zoom-controls" aria-label="Thu phóng ảnh xem trước">
                  <button
                    type="button"
                    onClick={() => setPreviewViewZoom(previewZoom - 25)}
                    disabled={previewZoom <= 50}
                    aria-label="Thu nhỏ ảnh xem trước"
                  >−</button>
                  <output aria-live="polite">{previewZoom}%</output>
                  <button
                    type="button"
                    onClick={() => setPreviewViewZoom(previewZoom + 25)}
                    disabled={previewZoom >= 300}
                    aria-label="Phóng to ảnh xem trước"
                  >+</button>
                  <button type="button" className="fit-view" onClick={resetPreviewView}>Vừa khung</button>
                </div>
              )}
              {originalUrl && effectStatus.phase !== "idle" && (
                <div className={`effect-progress ${effectStatus.phase}`} role="status" aria-live="polite">
                  <i aria-hidden="true" />
                  <span>
                    <b>{effectStatus.phase === "loading" ? "Đang áp dụng hiệu ứng" : effectStatus.phase === "done" ? "Đã áp dụng" : "Không áp dụng được"}</b>
                    <small>{effectStatus.label}</small>
                  </span>
                  {effectStatus.phase === "loading" && <em aria-hidden="true"><u /></em>}
                </div>
              )}
              
            </section>

            {!file ? (
              <section
                className="upload-card"
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => { event.preventDefault(); chooseFile(event.dataTransfer.files[0]); }}
              >
                <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={(event) => chooseFile(event.target.files?.[0])} />
                <div className="upload-icon">↑</div>
                <h2>Tải ảnh chân dung</h2>
                <p>Nhấp, kéo thả hoặc dán ảnh để bắt đầu.</p>
                <button className="primary-button" onClick={() => inputRef.current?.click()}>Chọn ảnh</button>
                <small>JPG, PNG hoặc WEBP · tối đa 20 MB</small>
              </section>
            ) : (
              <section className="control-card">
                <div className="control-heading">
                  <div><p className="eyebrow">LUMI BEAUTY STUDIO</p><h2>Chỉnh sửa chân dung</h2><small>Live preview cập nhật tự động theo từng lựa chọn</small></div>
                  <span className={`run-badge ${runState}`}>{runState === "analyzing" ? "Đang nhận diện" : runState === "processing" ? "Đang chạy" : runState === "done" ? "Đã xử lý" : "Bản nháp"}</span>
                </div>

                <div className="editor-tabs" aria-label="Đi tới nhóm chỉnh sửa">
                  <a href="#face-detect">Khuôn mặt</a>
                  <a href="#skin-retouch">Làm đẹp da</a>
                  <a href="#hair-color">Màu tóc</a>
                  <a href="#face-volume">Nâng &amp; đầy</a>
                  <a href="#makeup-pro">Trang điểm</a>
                  <a href="#photobooth">PhotoBooth</a>
                  <a href="#filter-lab">Bộ lọc</a>
                </div>

                <div className="face-profiles" id="face-detect">
                  <div className="face-profiles-title">
                    <div><b>Khuôn mặt trong ảnh</b><small>Ga2 ước lượng theo diện mạo · bạn có thể sửa nhóm trước khi chạy</small></div>
                    <span>{runState === "analyzing" ? "ĐANG QUÉT" : `${faces.length} MẶT`}</span>
                  </div>
                  {runState === "analyzing" ? (
                    <div className="profile-loading">Đang chạy Fd + Ga2 trên CPU…</div>
                  ) : (
                    <div className="profile-list">
                      {faces.map((face) => (
                        <div className="profile-row" key={face.id}>
                          <span className="face-avatar-wrap">
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img className="face-avatar" src={face.thumbnail} alt={`Khuôn mặt ${face.id + 1}`} />
                            <i className="face-number">{face.id + 1}</i>
                          </span>
                          <div><b>Mặt {face.id + 1} · AI: {face.label}{face.review_required ? " · cần xác nhận" : ""}</b><small>{PROFILE_DEFAULTS[face.selectedProfile]}</small></div>
                          <select
                            value={face.selectedProfile}
                            onChange={(event) => {
                              const nextProfile = event.target.value as ProfileKey;
                              markEffectPending(`Profile mặt ${face.id + 1} · ${PROFILE_OPTIONS.find((option) => option.key === nextProfile)?.label ?? nextProfile}`);
                              setFaces((current) => current.map((item) => item.id === face.id ? { ...item, selectedProfile: nextProfile } : item));
                            }}
                            aria-label={`Nhóm xử lý cho khuôn mặt ${face.id + 1}`}
                          >
                            {PROFILE_OPTIONS.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
                          </select>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="skin-controls" id="skin-retouch">
                  <div className="skin-controls-title">
                    <div><b>Điều chỉnh da</b><small>Mặc định 0, không tự làm đẹp. Số lớn bên phải là thông số Kumo thực đang áp dụng.</small></div>
                    <span>TỰ CHỈNH</span>
                  </div>

                  <label className="slider-row">
                    <span><b>Xóa mụn &amp; tàn nhang (Mặt)</b><em>{skinFleckClean}</em></span>
                    <input type="range" min="0" max="100" step="1" value={skinFleckClean} onInput={(event) => { markEffectPending("Xóa mụn & tàn nhang (Mặt)"); leavePhotoPreset(); setSkinFleckClean(Number(event.currentTarget.value)); }} disabled={runState === "processing"} aria-label="Mức xóa mụn và tàn nhang trên mặt" />
                    <small>Gợi ý Kumo · {skinSuggestion(faces, "blemish")} · vị trí thanh {skinFleckClean}%</small>
                  </label>

                  <div style={{ display: "none" }}>
                    <label className="slider-row">
                      <span><b>Mịn da tự nhiên</b><em>{effectiveSkinValues(faces, "smooth", smoothFaceSkin)}</em></span>
                      <input type="range" min="0" max="100" step="1" value={smoothFaceSkin} onInput={(event) => { markEffectPending("Mịn da tự nhiên"); leavePhotoPreset(); setSmoothFaceSkin(Number(event.currentTarget.value)); }} disabled={runState === "processing"} aria-label="Mức mịn da tự nhiên" />
                      <small>Gợi ý Kumo · {skinSuggestion(faces, "smooth")} · vị trí thanh {smoothFaceSkin}%</small>
                    </label>
                    <label className="slider-row">
                      <span><b>Đều màu da</b><em>{effectiveSkinValues(faces, "tone", skinToneFace)}</em></span>
                      <input type="range" min="0" max="100" step="1" value={skinToneFace} onInput={(event) => { markEffectPending("Đều màu da"); leavePhotoPreset(); setSkinToneFace(Number(event.currentTarget.value)); }} disabled={runState === "processing"} aria-label="Mức đều màu da" />
                      <small>Gợi ý Kumo · {skinSuggestion(faces, "tone")} · vị trí thanh {skinToneFace}%</small>
                    </label>
                  </div>

                  <label className="slider-row">
                    <span><b>Mịn da giữ kết cấu</b><em>{smoothTextureSkin}</em></span>
                    <input type="range" min="0" max="100" step="1" value={smoothTextureSkin} onInput={(event) => { markEffectPending("Mịn da giữ kết cấu"); leavePhotoPreset(); setSmoothTextureSkin(Number(event.currentTarget.value)); }} disabled={runState === "processing"} aria-label="Mức mịn da giữ kết cấu" />
                    <small>Tách tần số F1sch3b · giữ 100% lỗ chân lông và vân da · vị trí thanh {smoothTextureSkin}%</small>
                  </label>

                  <label className="slider-row">
                    <span><b>Sáng da tự nhiên</b><em>{skinWhite}</em></span>
                    <input type="range" min="0" max="100" step="1" value={skinWhite} onInput={(event) => { markEffectPending("Sáng da tự nhiên"); leavePhotoPreset(); setSkinWhite(Number(event.currentTarget.value)); }} disabled={runState === "processing"} aria-label="Mức sáng da tự nhiên" />
                    <small>Gợi ý Kumo · {skinSuggestion(faces, "white")} · vị trí thanh {skinWhite}%</small>
                  </label>

                  <label className="slider-row">
                    <span><b>Đều màu da (Nhiều người)</b><em>{skinToneMultiple}</em></span>
                    <input type="range" min="0" max="100" step="1" value={skinToneMultiple} onInput={(event) => { markEffectPending("Đều màu da (Nhiều người)"); leavePhotoPreset(); setSkinToneMultiple(Number(event.currentTarget.value)); }} disabled={runState === "processing"} aria-label="Mức đều màu da nhiều người" />
                    <small>Hài hòa sắc thái da toàn khuôn mặt và nhóm người · vị trí thanh {skinToneMultiple}%</small>
                  </label>

                  <div className="skin-tone-section">
                    <div className="skin-tone-header">
                      <b>Chọn tông da</b>
                      <span className="skin-tone-badge">Mới</span>
                    </div>

                    <div className="skin-tone-swatches" role="radiogroup" aria-label="Chọn tông da Kumo gốc">
                      {SKIN_TONE_SWATCHES.map((swatch) => (
                        <button
                          key={swatch.id}
                          type="button"
                          role="radio"
                          aria-checked={skinColorPreset === swatch.id}
                          title={swatch.label}
                          className={`skin-tone-swatch ${swatch.id === "none" ? "none" : ""} ${skinColorPreset === swatch.id ? "selected" : ""}`}
                          style={{ backgroundColor: swatch.id === "none" ? "#ffffff" : swatch.color }}
                          onClick={() => {
                            markEffectPending(`Tông da ${swatch.label}`);
                            leavePhotoPreset();
                            setSkinColorPreset(swatch.id);
                            if (swatch.id !== "none" && skinColorStrength === 0) {
                              setSkinColorStrength(60);
                            }
                          }}
                          disabled={runState === "processing"}
                        />
                      ))}
                    </div>

                    {skinColorPreset !== "none" && (
                      <label className="slider-row" style={{ marginTop: "10px" }}>
                        <span><b>Màu ưa chuộng</b><em>{skinColorStrength}</em></span>
                        <input
                          type="range"
                          min="0"
                          max="100"
                          step="1"
                          value={skinColorStrength}
                          onInput={(event) => {
                            markEffectPending("Màu ưa chuộng");
                            leavePhotoPreset();
                            setSkinColorStrength(Number(event.currentTarget.value));
                          }}
                          disabled={runState === "processing"}
                          aria-label="Mức màu ưa chuộng"
                        />
                        <small>Cường độ áp dụng tông da {SKIN_TONE_SWATCHES.find((s) => s.id === skinColorPreset)?.label} · vị trí thanh {skinColorStrength}%</small>
                      </label>
                    )}
                  </div>
                </div>

                <div className="hair-controls" id="hair-color">
                  <div className="skin-controls-title">
                    <div><b>Màu tóc</b><small>Thumbnail, material và cường độ lấy nguyên từ bộ Kumo gốc</small></div>
                    <span>KUMO 8 MÀU</span>
                  </div>

                  <div className="hair-color-grid" role="radiogroup" aria-label="Chọn màu tóc Kumo gốc">
                    {HAIR_COLOR_PRESETS.map((preset) => (
                      <button
                        key={preset.key}
                        type="button"
                        role="radio"
                        aria-checked={hairColorPreset === preset.key}
                        className={`hair-color-option ${hairColorPreset === preset.key ? "selected" : ""}`}
                        onClick={() => { markEffectPending(`Màu tóc · ${preset.label}`); leavePhotoPreset(); setHairColorPreset(preset.key); if (preset.key !== "none") setHairColorStrength(preset.defaultStrength); }}
                        disabled={runState === "processing"}
                      >
                        {preset.key === "none" ? (
                          <span className="hair-none">∅</span>
                        ) : (
                          // Exact Kumo thumbnail 01–08; the UI does not synthesize a swatch.
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={`${API_URL}/api/assets/haircolor/${preset.key}.jpg`} alt={`Màu tóc ${preset.label} ${preset.source}`} />
                        )}
                        <b>{preset.label}</b>
                        <small>{preset.key === "none" ? preset.detail : `${preset.key} · ${preset.source} · ${preset.detail}`}</small>
                      </button>
                    ))}
                  </div>

                  <label className="slider-row hair-color-strength">
                    <span><b>Cường độ màu tóc</b><em>{hairColorPreset === "none" ? 0 : hairColorStrength}</em></span>
                    <input type="range" min="0" max="100" step="1" value={hairColorStrength} onInput={(event) => { markEffectPending("Cường độ màu tóc"); setHairColorStrength(Number(event.currentTarget.value)); }} disabled={runState === "processing" || hairColorPreset === "none"} aria-label="Cường độ màu tóc Kumo" />
                    <small>Chọn màu sẽ về defaultAlpha gốc · kéo 45 là alpha 45% · HairSegment + HairSeamer giữ sợi tóc mảnh</small>
                  </label>
                </div>

                <div className="face-volume-controls" id="face-volume">
                  <div className="skin-controls-title">
                    <div><b>Nâng cơ &amp; đầy đặn</b><small>Lp106 neo riêng từng vùng · thumbnail và tên tham số từ Kumo gốc</small></div>
                    <span>14 VÙNG</span>
                  </div>

                  <section className="face-volume-group">
                    <div className="face-volume-subtitle"><b>Làm mịn và Nâng cơ</b><small><code>face_flat_lift_switch</code></small></div>
                    <div className="face-guide-grid face-guide-lift" role="radiogroup" aria-label="Vùng làm mịn và nâng cơ Kumo">
                      {FACE_LIFT_REGIONS.map((region) => (
                        <button
                          key={region.key}
                          type="button"
                          role="radio"
                          aria-checked={faceLiftRegion === region.key}
                          className={`face-guide-option ${faceLiftRegion === region.key ? "selected" : ""}`}
                          onClick={() => { markEffectPending(`Nâng cơ · ${region.label}`); leavePhotoPreset(); setFaceLiftRegion((current) => current === region.key ? "none" : region.key); }}
                          disabled={runState === "processing"}
                        >
                          {/* Exact 220×220 face guide from the original Kumo package. */}
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img src={`${API_URL}/api/assets/faceguide/${region.thumbnail}`} alt={`${region.label} · ${region.parameter}`} />
                          <b>{region.label}</b>
                          <small>{region.parameter}</small>
                        </button>
                      ))}
                    </div>
                    {faceLiftRegion !== "none" && (
                      <label className="slider-row face-volume-strength">
                        <span><b>Cường độ nâng cơ</b><em>{faceLiftStrength}</em></span>
                        <input type="range" min="0" max="100" step="1" value={faceLiftStrength} onInput={(event) => { markEffectPending("Cường độ nâng cơ"); setFaceLiftStrength(Number(event.currentTarget.value)); }} disabled={runState === "processing"} aria-label="Cường độ làm mịn và nâng cơ" />
                        <small>Áp dụng ngay cho vùng đang chọn; bấm lại thumbnail để tắt vùng</small>
                      </label>
                    )}
                  </section>

                  <section className="face-volume-group">
                    <div className="face-volume-subtitle"><b>Đầy đặn</b><small><code>face_full_switch</code></small></div>
                    <div className="face-guide-grid" role="radiogroup" aria-label="Vùng đầy đặn Kumo">
                      {FACE_FILL_REGIONS.map((region) => (
                        <button
                          key={region.key}
                          type="button"
                          role="radio"
                          aria-checked={faceFillRegion === region.key}
                          className={`face-guide-option ${faceFillRegion === region.key ? "selected" : ""}`}
                          onClick={() => { markEffectPending(`Đầy đặn · ${region.label}`); leavePhotoPreset(); setFaceFillRegion((current) => current === region.key ? "none" : region.key); }}
                          disabled={runState === "processing"}
                        >
                          {/* Exact 220×220 face guide from the original Kumo package. */}
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img src={`${API_URL}/api/assets/faceguide/${region.thumbnail}`} alt={`${region.label} · ${region.parameter}`} />
                          <b>{region.label}</b>
                          <small>{region.parameter}</small>
                        </button>
                      ))}
                    </div>
                    {faceFillRegion !== "none" && (
                      <label className="slider-row face-volume-strength">
                        <span><b>Cường độ đầy đặn</b><em>{faceFillStrength}</em></span>
                        <input type="range" min="0" max="100" step="1" value={faceFillStrength} onInput={(event) => { markEffectPending("Cường độ đầy đặn"); setFaceFillStrength(Number(event.currentTarget.value)); }} disabled={runState === "processing"} aria-label="Cường độ đầy đặn khuôn mặt" />
                        <small>Giữ nguyên màu và kết cấu da; chỉ chạy operator Lp106 tại vùng đã chọn</small>
                      </label>
                    )}
                  </section>

                  <div className="makeup-contract-note">
                    <b>Contract Kumo thật</b>
                    <small>4 khóa nâng cơ + 10 khóa đầy đặn; mỗi khuôn mặt dùng bộ 106 landmark và mask riêng, không lấy MTCheek/MTJaw classifier để giả lập biến dạng.</small>
                  </div>
                </div>

                <div className="pro-controls" id="makeup-pro">
                  <div className="skin-controls-title">
                    <div><b>Trang điểm Pro</b><small>{makeupCatalogSummary} · tự neo theo Lp106 của từng mặt</small></div>
                    <span>KUMO GỐC</span>
                  </div>

                  {!makeupLibrary ? (
                    <div className="makeup-loading">Đang tải thumbnail, texture và contract blend Kumo…</div>
                  ) : (
                    <>
                      <div className="makeup-tabs" role="tablist" aria-label="Nhóm trang điểm Kumo">
                        {MAKEUP_TAB_ORDER.filter((key) => key === "set" || makeupLibrary.parts.some((part) => part.key === key)).map((key) => (
                          <button
                            key={key}
                            type="button"
                            role="tab"
                            aria-selected={makeupTab === key}
                            className={makeupTab === key ? "selected" : ""}
                            onClick={() => setMakeupTab(key)}
                          >
                            {MAKEUP_TAB_LABELS[key]}
                            {key !== "set" && makeupSelection[key] && <i />}
                          </button>
                        ))}
                      </div>

                      {makeupTab === "set" ? (
                        <div className="makeup-material-grid makeup-theme-grid" role="radiogroup" aria-label="Set trang điểm Kumo">
                          <button
                            type="button"
                            className={`makeup-material-option ${activeMakeupCount === 0 ? "selected" : ""}`}
                            onClick={() => { markEffectPending("Tắt Set trang điểm"); leavePhotoPreset(); setMakeupThemeId(null); setMakeupLipstickStrength(0); setMakeupSelection({}); }}
                          >
                            <span className="makeup-none">∅</span>
                            <b>Không</b>
                            <small>Giữ khuôn mặt sau làm đẹp da</small>
                          </button>
                          {makeupLibrary.themes.map((theme) => (
                            <button
                              key={theme.id}
                              type="button"
                              className={`makeup-material-option ${makeupThemeId === theme.id ? "selected" : ""}`}
                              onClick={() => applyMakeupTheme(theme.id)}
                            >
                              {/* Original Kumo theme thumbnail. */}
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img src={theme.thumb} alt={`Set trang điểm ${theme.name}`} />
                              <b>{theme.name}</b>
                              <small>{theme.parts.length} lớp · gốc {theme.alpha}%</small>
                            </button>
                          ))}
                        </div>
                      ) : activeMakeupPart ? (
                        <>
                          {activeMakeupPart.colors.length > 0 && (
                            <div className="makeup-colors" aria-label={`Màu ${activeMakeupPart.name}`}>
                              {activeMakeupPart.colors.map((color) => {
                                const selected = activeMakeupPick?.color?.join() === color.rgb.join();
                                return (
                                  <button
                                    key={color.name}
                                    type="button"
                                    title={`${color.name} · rgb(${color.rgb.join(", ")})`}
                                    aria-label={`Màu ${color.name}`}
                                    className={selected ? "selected" : ""}
                                    style={{ background: `rgb(${color.rgb.join(",")})` }}
                                    disabled={!activeMakeupPick}
                                    onClick={() => {
                                      markEffectPending(`${activeMakeupPart.name} · màu ${color.name}`);
                                      setMakeupSelection((current) => ({
                                        ...current,
                                        [activeMakeupPart.key]: {
                                          ...current[activeMakeupPart.key],
                                          color: selected ? null : color.rgb,
                                        },
                                      }));
                                    }}
                                  />
                                );
                              })}
                              <small>{activeMakeupPick ? "Màu ORGBA gốc hoặc màu bạn chọn" : "Chọn kiểu trước khi đổi màu"}</small>
                            </div>
                          )}

                          <div className="makeup-material-grid" role="radiogroup" aria-label={`Chọn ${activeMakeupPart.name}`}>
                            <button
                              type="button"
                              className={`makeup-material-option ${!activeMakeupPick ? "selected" : ""}`}
                              onClick={() => clearMakeupPart(activeMakeupPart.key)}
                            >
                              <span className="makeup-none">∅</span>
                              <b>Không</b>
                              <small>Tắt riêng {activeMakeupPart.name.toLowerCase()}</small>
                            </button>
                            {activeMakeupPart.materials.map((material) => (
                              <button
                                key={material.dir}
                                type="button"
                                className={`makeup-material-option ${activeMakeupPick?.dir === material.dir ? "selected" : ""}`}
                                onClick={() => chooseMakeupMaterial(activeMakeupPart.key, material)}
                              >
                                {/* Original material thumbnail from the extracted Kumo package. */}
                                {/* eslint-disable-next-line @next/next/no-img-element */}
                                <img src={material.thumb} alt={`${activeMakeupPart.name} ${material.name}`} />
                                <b>{material.name}</b>
                                <small>{material.layers.length} lớp · gốc {material.alpha}%</small>
                              </button>
                            ))}
                          </div>

                          {activeMakeupPick && (
                            <label className="slider-row makeup-strength">
                              <span><b>Cường độ {activeMakeupPart.name.toLowerCase()}</b><em>{activeMakeupPick.amount}</em></span>
                              <input
                                type="range"
                                min="0"
                                max="100"
                                step="1"
                                value={activeMakeupPick.amount}
                                onInput={(event) => {
                                  const amount = event.currentTarget.valueAsNumber;
                                  markEffectPending(`Cường độ ${activeMakeupPart.name.toLowerCase()}`);
                                  setMakeupSelection((current) => ({
                                    ...current,
                                    [activeMakeupPart.key]: {
                                      ...current[activeMakeupPart.key],
                                      amount,
                                    },
                                  }));
                                }}
                                aria-label={`Cường độ ${activeMakeupPart.name}`}
                              />
                              <small>Thay đổi áp dụng ngay trên ảnh đã xử lý, không chạy lại model nền</small>
                            </label>
                          )}
                        </>
                      ) : null}

                      <div className="makeup-summary">
                        <span>{makeupLibrary.parts.reduce((total, part) => total + part.materials.length, 0)} vật liệu · {makeupLibrary.themes.length} Set</span>
                        {activeMakeupCount > 0 && (
                          <button type="button" onClick={() => { markEffectPending("Tắt toàn bộ trang điểm"); leavePhotoPreset(); setMakeupThemeId(null); setMakeupLipstickStrength(0); setMakeupSelection({}); }}>
                            Bỏ hết ({activeMakeupCount})
                          </button>
                        )}
                      </div>
                    </>
                  )}

                  <div className="makeup-contract-note">
                    <b>Contract Kumo thật</b>
                    <small>Texture + Rectangle 1000×1500 + ORGBA + BlendMode + HeadMaskPath, ghép affine theo mắt và miệng từ 106 landmark.</small>
                  </div>
                </div>

                <div className="photobooth-controls" id="photobooth">
                  <div className="skin-controls-title">
                    <div><b>PhotoBooth</b><small>Snapshot Kumo độc lập: da nền chạy một lần, makeup và màu ghép trên preview 1600 px đã cache</small></div>
                    <span>{photoLibrary ? `${photoLibrary.presets.length} PRESET` : "ĐANG TẢI"}</span>
                  </div>

                  {!photoLibrary ? (
                    <div className="makeup-loading">Đang tải danh mục và cover PhotoBooth gốc…</div>
                  ) : (
                    <>
                      <div className="photo-category-tabs" role="tablist" aria-label="Danh mục PhotoBooth">
                        {photoLibrary.categories.map((category) => (
                          <button
                            key={category.id}
                            type="button"
                            role="tab"
                            aria-selected={photoCategoryId === category.id}
                            className={photoCategoryId === category.id ? "selected" : ""}
                            onClick={() => setPhotoCategoryId(category.id)}
                          >
                            {category.name === "光线" ? "Ánh sáng" : category.name}
                          </button>
                        ))}
                      </div>

                      <div className="photo-preset-grid" role="radiogroup" aria-label="Preset PhotoBooth">
                        <button
                          type="button"
                          role="radio"
                          aria-checked={photoPresetId === null}
                          className={`photo-preset-option ${photoPresetId === null ? "selected" : ""}`}
                          onClick={() => activatePhotoPreset(null, "Bỏ preset PhotoBooth")}
                        >
                          <span className="photo-preset-none">∅</span>
                          <b>Gốc</b>
                          <small>Không áp preset</small>
                        </button>
                        {visiblePhotoPresets.map((preset) => (
                          <button
                            key={preset.id}
                            type="button"
                            role="radio"
                            aria-checked={photoPresetId === preset.id}
                            className={`photo-preset-option ${photoPresetId === preset.id ? "selected" : ""}`}
                            onClick={() => activatePhotoPreset(preset.id, `Áp preset ${preset.name}`)}
                          >
                            {/* Original PhotoBooth cover extracted with the preset catalog. */}
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img src={preset.cover} alt={`Preset PhotoBooth ${preset.name}`} />
                            <b>{preset.name}</b>
                            <small>{preset.param_count} khóa metadata Kumo</small>
                          </button>
                        ))}
                      </div>

                      {photoPresetId !== null && (
                        <>
                          <label className="slider-row photo-preset-strength">
                            <span><b>Cường độ preset</b><em>{photoPresetStrength}</em></span>
                          </label>
                        </>
                      )}
                    </>
                  )}

                </div>

                <div className="photobooth-controls" id="filter-lab">
                  <div className="skin-controls-title">
                    <div><b>Bộ lọc</b><small>135 3D LUT Kumo độc lập · màu phim, chân dung, cảnh quan &amp; AI</small></div>
                    <span>{filtersCatalog ? `${filtersCatalog.total_luts} BỘ LỌC` : "ĐANG TẢI"}</span>
                  </div>

                  {!filtersCatalog ? (
                    <div className="makeup-loading">Đang tải thư viện bộ lọc Kumo…</div>
                  ) : (
                    <>
                      {/* 2 Main Top Subtabs: Phổ biến | AI */}
                      <div className="photo-category-tabs" role="tablist" style={{ marginBottom: 12 }}>
                        <button
                          type="button"
                          role="tab"
                          aria-selected={filterTab === "phobien"}
                          className={filterTab === "phobien" ? "selected" : ""}
                          onClick={() => setFilterTab("phobien")}
                          style={{ flex: 1, textAlign: "center", fontWeight: 700 }}
                        >
                          Phổ biến
                        </button>
                        <button
                          type="button"
                          role="tab"
                          aria-selected={filterTab === "ai"}
                          className={filterTab === "ai" ? "selected" : ""}
                          onClick={() => setFilterTab("ai")}
                          style={{ flex: 1, textAlign: "center", fontWeight: 700 }}
                        >
                          AI 🛈
                        </button>
                      </div>

                      {/* Intensity Slider if a filter is active */}
                      {filterId !== "none" && (
                        <label className="slider-row photo-preset-strength" style={{ margin: "8px 0 14px" }}>
                          <span><b>Cường độ</b><em>{filterStrength}%</em></span>
                          <input
                            type="range"
                            min="0"
                            max="100"
                            value={filterStrength}
                            onChange={(e) => {
                              const v = Number(e.target.value);
                              setFilterStrength(v);
                              markEffectPending(`Cường độ bộ lọc ${v}%`);
                            }}
                          />
                        </label>
                      )}

                      {filterTab === "phobien" ? (
                        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                          {filtersCatalog.phobien.map((section) => (
                            <div key={section.id} className="filter-section-group">
                              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8, padding: "2px 4px" }}>
                                <b style={{ fontSize: 12, color: "#354257", display: "flex", alignItems: "center", gap: 5 }}>
                                  <span>⌄</span> {section.name}
                                </b>
                                <small style={{ fontSize: 10, color: "#8d98a5" }}>{section.filters.length} bộ lọc</small>
                              </div>
                              <div className="photo-preset-grid" role="radiogroup">
                                {section.filters.map((item) => (
                                  <button
                                    key={item.id}
                                    type="button"
                                    role="radio"
                                    aria-checked={filterId === item.id}
                                    className={`photo-preset-option ${filterId === item.id ? "selected" : ""}`}
                                    onClick={() => {
                                      setFilterId(item.id);
                                      if (item.default_alpha !== undefined && item.id !== "none") {
                                        setFilterStrength(item.default_alpha);
                                      }
                                      markEffectPending(item.id === "none" ? "Bỏ bộ lọc" : `Áp bộ lọc ${item.name}`);
                                    }}
                                  >
                                    {item.id === "none" || !item.thumbnail ? (
                                      <span className="photo-preset-none">⊘</span>
                                    ) : (
                                      // eslint-disable-next-line @next/next/no-img-element
                                      <img src={item.thumbnail} alt={item.name} />
                                    )}
                                    <b style={{ textAlign: "center", marginTop: 5, fontSize: 10 }}>{item.name}</b>
                                  </button>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                          {/* Row 1: Themes */}
                          <div className="filter-section-group">
                            <div className="photo-preset-grid" role="radiogroup">
                              {filtersCatalog.ai.themes.map((item) => (
                                <button
                                  key={item.id}
                                  type="button"
                                  role="radio"
                                  aria-checked={filterId === item.id}
                                  className={`photo-preset-option ${filterId === item.id ? "selected" : ""}`}
                                  onClick={() => {
                                    setFilterId(item.id);
                                    if (item.default_alpha !== undefined && item.id !== "none") {
                                      setFilterStrength(item.default_alpha);
                                    }
                                    markEffectPending(item.id === "none" ? "Bỏ bộ lọc" : `Áp phong cách ${item.name}`);
                                  }}
                                >
                                  {item.id === "none" || !item.thumbnail ? (
                                    <span className="photo-preset-none">⊘</span>
                                  ) : (
                                    // eslint-disable-next-line @next/next/no-img-element
                                    <img src={item.thumbnail} alt={item.name} />
                                  )}
                                  <b style={{ textAlign: "center", marginTop: 5, fontSize: 10 }}>{item.name}</b>
                                </button>
                              ))}
                            </div>
                          </div>

                          {/* Row 2: Subfilters */}
                          <div className="filter-section-group">
                            <div className="photo-preset-grid" role="radiogroup">
                              {filtersCatalog.ai.filters.map((item) => (
                                <button
                                  key={item.id}
                                  type="button"
                                  role="radio"
                                  aria-checked={filterId === item.id}
                                  className={`photo-preset-option ${filterId === item.id ? "selected" : ""}`}
                                  onClick={() => {
                                    setFilterId(item.id);
                                    if (item.default_alpha !== undefined) {
                                      setFilterStrength(item.default_alpha);
                                    }
                                    markEffectPending(`Áp sắc thái ${item.name}`);
                                  }}
                                >
                                  {/* eslint-disable-next-line @next/next/no-img-element */}
                                  <img src={item.thumbnail} alt={item.name} />
                                  <b style={{ textAlign: "center", marginTop: 5, fontSize: 10 }}>{item.name}</b>
                                </button>
                              ))}
                            </div>
                          </div>

                          {/* AI Color Transfer Section */}
                          <div className="ai-color-transfer-section">
                            <div className="ai-color-transfer-header">
                              <b>Chuyển màu AI</b>
                            </div>
                            <div className="ai-color-transfer-subtabs">
                              <button type="button" className="ai-subtab-btn active">Đề xuất</button>
                              <button type="button" className="ai-subtab-btn">Của tôi</button>
                            </div>
                            <div className="ai-color-transfer-actions">
                              <button type="button" className="ai-action-btn">
                                <span>+</span> Nhập
                              </button>
                              <button type="button" className="ai-action-btn">
                                <span style={{ fontSize: 13 }}>🖼️</span> Đặt làm mẫu
                              </button>
                            </div>
                            <div className="color-ref-pack-grid">
                              {colorRefPacks.map((pack) => (
                                <div
                                  key={pack.id}
                                  className={`color-ref-pack-card ${activeColorPackId === pack.id ? "selected" : ""}`}
                                  onClick={() => setActiveColorPackId(activeColorPackId === pack.id ? null : pack.id)}
                                >
                                  <div className="color-ref-cover-wrap">
                                    {/* eslint-disable-next-line @next/next/no-img-element */}
                                    <img src={pack.cover} alt={pack.name} className="color-ref-pack-cover" />
                                    <span className="color-ref-count-badge">{pack.count} ảnh</span>
                                  </div>
                                  <div className="color-ref-pack-title">
                                    {pack.name}
                                  </div>
                                  {activeColorPackId === pack.id && (
                                    <div className="color-ref-items-row" onClick={(e) => e.stopPropagation()}>
                                      {pack.items.map((itemUrl, idx) => (
                                        // eslint-disable-next-line @next/next/no-img-element
                                        <img
                                          key={itemUrl}
                                          src={itemUrl}
                                          alt={`Mẫu ${idx + 1}`}
                                          className={`color-ref-item-thumb ${selectedColorRef === itemUrl ? "selected" : ""}`}
                                          onClick={() => {
                                            setSelectedColorRef(itemUrl);
                                            const lutCandidate = filtersCatalog.phobien[0]?.filters[1]?.id || "Fa0000ygyMjU1Ma0";
                                            setFilterId(lutCandidate);
                                            markEffectPending(`Chuyển màu AI · ${pack.name} #${idx + 1}`);
                                          }}
                                        />
                                      ))}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>

                <div className="pro-module-panel">
                  <div className="pro-module-heading">
                    <div><b>Mở rộng chuyên nghiệp</b><small>Chỉ bật khi contract model và bước ghép ảnh đã được xác nhận</small></div>
                    <span>{PRO_MODULES.length} NHÓM</span>
                  </div>
                  <div className="pro-module-grid">
                    {PRO_MODULES.map((module) => (
                      <div key={module.title} className={`pro-module ${module.ready ? "ready" : "locked"}`}>
                        <i>{module.icon}</i>
                        <div><b>{module.title}</b><small>{module.title === "Trang điểm Pro" ? makeupCatalogSummary : module.detail}</small></div>
                        <em>{module.state}</em>
                      </div>
                    ))}
                  </div>
                </div>

                <details className="model-debug">
                  <summary>Chi tiết pipeline Kumo</summary>
                  <div className="model-flow">
                    <span><i>1</i> Fd + Ga2</span><b>→</b>
                    <span><i>2</i> FaceContour</span><b>→</b>
                    <span><i>3</i> Smooth + Healing</span><b>→</b>
                    <span><i>4</i> SkinTone + LUT</span><b>→</b>
                    <span><i>5</i> Lp106</span><b>→</b>
                    <span><i>6</i> Tóc + makeup</span>
                  </div>
                  <div className="model-contract">
                    <b>Contract Ga2 đã xác nhận</b>
                    <p><code>Fd</code> căn từng mặt → <code>Ga2</code> phân nhóm → <code>Lp106 + FaceContour</code> bảo vệ ngũ quan và tách đúng vùng xử lý.</p>
                  </div>
                </details>

                <div className={`message ${runState}`}><i /> <span>{message}{processingMs ? ` · ${processingMs} ms` : ""}</span></div>

                <div className="auto-run-note"><i>↻</i><span><b>Tự động áp dụng</b><small>Tải ảnh, kéo thanh hoặc chọn hiệu ứng — Kumoo tự chạy sau 0,42 giây.</small></span></div>
                {resultUrl && <a className="download-button" href={resultUrl} download="lumi-portrait.jpg">Tải ảnh kết quả</a>}
                {!apiOnline && <p className="server-hint">Hãy chạy server Python ở cổng 8417 rồi tải lại trang.</p>}
              </section>
            )}
          </div>

          <div className="trust-row">
            <span><b>9 + 3</b> model và operator Kumo thật</span>
            <span><b>0</b> dữ liệu gửi lên cloud</span>
            <span><b>100%</b> xử lý cục bộ</span>
          </div>
        </section>
      </div>
    </main>
  );
}
