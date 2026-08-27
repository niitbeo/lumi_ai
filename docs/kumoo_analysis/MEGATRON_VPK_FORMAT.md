# 🔓 Megatron VPK Container Format — Complete Analysis

> Updated: 2026-08-09 12:30

## File Overview

| File | Size | Purpose |
|---|---|---|
| `megatron.vpk` | 466 MB | AI model weights (encrypted) |
| `megatron_conf.vpk` | 109 MB | Model configs/metadata (encrypted) |

## Container Structure

```
┌─────────────────────────────────────────────────────┐
│                  megatron.vpk                       │
├────────┬──────────────────┬───────────────┬─────────┤
│ Header │   Index Region   │  Data Blob    │ Footer  │
│ 29 B   │   ~279 KB        │  ~465 MB      │ ~200 B  │
│        │ 940 × 298B blocks│  Encrypted    │ TOC ptrs│
└────────┴──────────────────┴───────────────┴─────────┘
```

### 1. Header (29 bytes)

```
Offset  Bytes              Value           Meaning
──────  ──────────────     ────────────    ──────────────────
0x00    2F 8B F3 00        0x00F38B2F      Magic signature
0x04    01 00 00 00        1               Format version
0x08    02 8F C8 0E        248,024,834     Encryption parameter
0x0C    A5 1D 00 00        7,589           Entry count (models)
0x10    00 00 00 00        0               Reserved
0x14    00 18 00 00        6,144           Block param
0x18    00 00 00 00        0               Reserved
0x1C    [3 bytes]          varies          Per-file nonce/seed
```

> [!IMPORTANT]
> Both VPK files share **identical** bytes 0-28. Only bytes 29-31 differ → per-file encryption nonce.

### 2. Index Region (~279 KB)

| Property | Value |
|---|---|
| Block count | 940 blocks |
| Block format | 297 bytes encrypted data + `0x79` separator |
| Total payload | 278,930 bytes |
| Bytes/entry | ~36.8 (7,589 entries) |
| Encryption | Stream cipher, entropy ~7.5 |

The `0x79` separator byte is constant and unencrypted — it's a **format marker** at every 298-byte boundary.

### 3. Data Blob (~465 MB)

| Property | Value |
|---|---|
| Starts at | byte 279,899 |
| Size | 487,933,909 bytes |
| Entropy | **7.98 bits/byte** (fully encrypted) |
| Content | MNN model weights (flatbuffer format) |
| No separators | Data is continuous encrypted stream |

### 4. Footer (~200 bytes)

```
Structure (from end of file, backwards):
  [-4]     0x5948121D          Footer magic/checksum
  [-12]    (0, block_idx)      Last model block index  
  [-20]    (count, count)      Section counts
  ...      (0, block_idx)      Model start block indices
  [-200]   encrypted hash      Section checksum (48 bytes)
```

Key block indices in footer: 1, 120, 1001, 51235, 363399, 605668-606131

## Encryption Analysis

| Property | Finding |
|---|---|
| Algorithm | Stream cipher (likely custom or ChaCha variant) |
| Key derivation | From bytes 29-31 (per-file nonce) + shared param at byte 8 |
| Keystream | Different per file (XOR of both files' data ≠ 0) |
| Separator 0x79 | Unencrypted constant (same in both files) |
| Data entropy | 7.98 (near-perfect random — strong encryption) |
| Index entropy | 7.5 (slightly lower — index has more structure) |

## MNN Model Format (Plaintext)

All 91 decrypted models share the same flatbuffer header:
```
20 00 00 00 1C 00 24 00 08 00 00 00 0C 00 10 00
14 00 05 00 06 00 18 00 1C 00 07 00 00 00 20 00
1C 00 00 00 00 00 03 00 ...
```
- Root offset: 32 (typical MNN flatbuffer)
- Source type: 3 (ONNX-converted)

## Comparison: megatron.vpk vs megatron_conf.vpk

| | megatron.vpk | megatron_conf.vpk |
|---|---|---|
| Header bytes 0-28 | Identical | Identical |
| Nonce (byte 29-31) | `F3 27 C0` | `E6 73 2D` |
| Index blocks | 940 | 4,602 |
| Index size | 279 KB | 1.3 MB |
| Data blob | 465 MB | 108.7 MB |
| Purpose | Model weights | Model configs |

## Assets Extracted to `cubeo-ai/kumoo_materials/`

| Asset | Count | Size |
|---|---|---|
| Makeup presets | 146 sets | 43 MB |
| Filter LUT tiles | 256 tiles (12 categories) | 348 MB |
| Sky replacement images | 45 JPEG | 213 MB |
| Preset configs | JSON | 3.9 MB |
| material.db | SQLite | 4 KB + 1MB WAL |

**Total materials extracted: ~608 MB**

## Decrypted Models Status

> [!TIP]
> A separate runtime-captured corpus contains **91 decrypted graph payloads** from the Tiamat model API.
> Located at: `cubeo-ai/decrypted_models/` (100 files including OpenVINO `.xml` variants).
>
> This count must not be equated one-to-one with every `.bin` entry in
> `megatron.vpk`. The archive still has 87 `.bin` entries (including
> `mtface_parsing*.bin`) whose name-to-captured-graph mapping and independent
> preprocessing/postprocessing contracts have not all been verified.

## What Would Be Needed to Fully Crack VPK

1. **Find the decryption key** — embedded in `Manis.framework` (24MB binary)
   - Key classes: `mizar::DefaultModelParser`, `mizar::CacheModelParser`
   - Strings: `unpack model failed`, `packages`, `offsets`
2. **Reverse `Manis.framework`** — compiled from `/Users/meitu/apollo-ws/source/mizar/`
3. **Runtime hook** — attach LLDB to Kumoo (PID 16953) and intercept `mizar::DefaultModelParser::unpack()`

Since all models are already extracted, cracking VPK is mainly academic.
