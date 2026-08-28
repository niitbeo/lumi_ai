import { CANONICAL_POINTS, MESH_TRIANGLES } from "./meshData";
import { makeupTransform } from "./kumoMakeup";

export function solveAffine(
  p0: [number, number], p1: [number, number], p2: [number, number],
  f0: [number, number], f1: [number, number], f2: [number, number]
) {
  const det = (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p2[0] - p0[0]) * (p1[1] - p0[1]);
  if (Math.abs(det) < 1e-6) return null;

  const a = ((f1[0] - f0[0]) * (p2[1] - p0[1]) - (f2[0] - f0[0]) * (p1[1] - p0[1])) / det;
  const b = ((f2[0] - f0[0]) * (p1[0] - p0[0]) - (f1[0] - f0[0]) * (p2[0] - p0[0])) / det;
  const c = f0[0] - a * p0[0] - b * p0[1];

  const d = ((f1[1] - f0[1]) * (p2[1] - p0[1]) - (f2[1] - f0[1]) * (p1[1] - p0[1])) / det;
  const e = ((f2[1] - f0[1]) * (p1[0] - p0[0]) - (f1[1] - f0[1]) * (p2[0] - p0[0])) / det;
  const f = f0[1] - d * p0[0] - e * p0[1];

  return { a, b, c, d, e, f };
}

export function drawWarpedMesh(
  context: CanvasRenderingContext2D,
  texture: HTMLCanvasElement,
  realLandmarks: number[][],
  globalTransform: NonNullable<ReturnType<typeof makeupTransform>>
) {
  // Real points array matching CANONICAL_POINTS (110 points)
  const realPts = [...realLandmarks];
  
  // Extrapolate the 4 corners using globalTransform
  const corners = [[0,0], [1000,0], [0,1500], [1000,1500]];
  for (const c of corners) {
    const rx = globalTransform.a * c[0] + globalTransform.b * c[1] + globalTransform.c;
    const ry = globalTransform.d * c[0] + globalTransform.e * c[1] + globalTransform.f;
    realPts.push([rx, ry]);
  }

  // To prevent seams between triangles, we overlap them slightly
  // But canvas clip() is exact, so usually it's fine.
  // Actually, standard way is to just clip and draw.
  
  for (const tri of MESH_TRIANGLES) {
    const i0 = tri[0], i1 = tri[1], i2 = tri[2];
    const u0 = CANONICAL_POINTS[i0], u1 = CANONICAL_POINTS[i1], u2 = CANONICAL_POINTS[i2];
    const x0 = realPts[i0], x1 = realPts[i1], x2 = realPts[i2];
    
    const mat = solveAffine(
      [u0[0], u0[1]], [u1[0], u1[1]], [u2[0], u2[1]],
      [x0[0], x0[1]], [x1[0], x1[1]], [x2[0], x2[1]]
    );
    if (!mat) continue;

    const cx = (x0[0] + x1[0] + x2[0]) / 3;
    const cy = (x0[1] + x1[1] + x2[1]) / 3;
    const pad = 0; // Removing padding to prevent alpha accumulation on semi-transparent textures
    const px0 = x0[0] + (x0[0] - cx) * (pad / Math.max(0.001, Math.abs(x0[0] - cx)));
    const py0 = x0[1] + (x0[1] - cy) * (pad / Math.max(0.001, Math.abs(x0[1] - cy)));
    const px1 = x1[0] + (x1[0] - cx) * (pad / Math.max(0.001, Math.abs(x1[0] - cx)));
    const py1 = x1[1] + (x1[1] - cy) * (pad / Math.max(0.001, Math.abs(x1[1] - cy)));
    const px2 = x2[0] + (x2[0] - cx) * (pad / Math.max(0.001, Math.abs(x2[0] - cx)));
    const py2 = x2[1] + (x2[1] - cy) * (pad / Math.max(0.001, Math.abs(x2[1] - cy)));

    context.save();
    context.beginPath();
    context.moveTo(px0, py0);
    context.lineTo(px1, py1);
    context.lineTo(px2, py2);
    context.closePath();
    context.clip();

    context.setTransform(mat.a, mat.d, mat.b, mat.e, mat.c, mat.f);
    // Draw the entire texture, but it will be clipped to the triangle
    // It's mapped perfectly by setTransform
    context.drawImage(texture, 0, 0);
    context.restore();
  }
}
/**
 * Dense Grid Warp for eyelash region.
 * Creates a fine NxM grid over the eyelash canonical rect, maps each grid
 * point through the global mesh (finding which triangle contains it), then
 * draws 2*N*M small triangles. This gives smooth curvature because the large
 * mesh triangles are subdivided into many small ones.
 */
export function drawDenseEyelashWarp(
  context: CanvasRenderingContext2D,
  stageCanvas: HTMLCanvasElement,
  realLandmarks: number[][],
  globalTransform: NonNullable<ReturnType<typeof makeupTransform>>,
  rect: [number, number, number, number]
) {
  const [texX, texY, texW, texH] = rect;
  const COLS = 8;
  const ROWS = 6;

  // Build real points array (same as drawWarpedMesh)
  const realPts = [...realLandmarks];
  const corners = [[0,0], [1000,0], [0,1500], [1000,1500]];
  for (const c of corners) {
    const rx = globalTransform.a * c[0] + globalTransform.b * c[1] + globalTransform.c;
    const ry = globalTransform.d * c[0] + globalTransform.e * c[1] + globalTransform.f;
    realPts.push([rx, ry]);
  }

  // Pre-compute affine for each global mesh triangle
  const meshAffines: { tri: number[]; u: number[][]; mat: ReturnType<typeof solveAffine> }[] = [];
  for (const tri of MESH_TRIANGLES) {
    const u0 = CANONICAL_POINTS[tri[0]], u1 = CANONICAL_POINTS[tri[1]], u2 = CANONICAL_POINTS[tri[2]];
    const x0 = realPts[tri[0]], x1 = realPts[tri[1]], x2 = realPts[tri[2]];
    const mat = solveAffine(
      [u0[0], u0[1]], [u1[0], u1[1]], [u2[0], u2[1]],
      [x0[0], x0[1]], [x1[0], x1[1]], [x2[0], x2[1]]
    );
    meshAffines.push({ tri, u: [u0, u1, u2], mat });
  }

  // Point-in-triangle test using barycentric coordinates
  function pointInTri(px: number, py: number, t0: number[], t1: number[], t2: number[]): boolean {
    const d = (t1[0] - t0[0]) * (t2[1] - t0[1]) - (t2[0] - t0[0]) * (t1[1] - t0[1]);
    if (Math.abs(d) < 1e-10) return false;
    const a = ((px - t0[0]) * (t2[1] - t0[1]) - (t2[0] - t0[0]) * (py - t0[1])) / d;
    const b = ((t1[0] - t0[0]) * (py - t0[1]) - (px - t0[0]) * (t1[1] - t0[1])) / d;
    return a >= -0.01 && b >= -0.01 && (a + b) <= 1.01;
  }

  // Map a canonical point to real coordinates via the global mesh
  function canonToReal(cx: number, cy: number): [number, number] | null {
    for (const { u, mat } of meshAffines) {
      if (!mat) continue;
      if (pointInTri(cx, cy, u[0], u[1], u[2])) {
        return [mat.a * cx + mat.b * cy + mat.c, mat.d * cx + mat.e * cy + mat.f];
      }
    }
    return null;
  }

  // Build the grid: (ROWS+1) x (COLS+1) points
  const grid: ([number, number] | null)[][] = [];
  for (let r = 0; r <= ROWS; r++) {
    grid[r] = [];
    for (let c = 0; c <= COLS; c++) {
      const cx = texX + (c / COLS) * texW;
      const cy = texY + (r / ROWS) * texH;
      grid[r][c] = canonToReal(cx, cy);
    }
  }


  function expandTri(p0: [number, number], p1: [number, number], p2: [number, number], pad: number = 0.5): [[number, number], [number, number], [number, number]] {
    const cx = (p0[0] + p1[0] + p2[0]) / 3;
    const cy = (p0[1] + p1[1] + p2[1]) / 3;
    const l0 = Math.hypot(p0[0] - cx, p0[1] - cy) || 1;
    const l1 = Math.hypot(p1[0] - cx, p1[1] - cy) || 1;
    const l2 = Math.hypot(p2[0] - cx, p2[1] - cy) || 1;
    return [
      [p0[0] + (p0[0] - cx) / l0 * pad, p0[1] + (p0[1] - cy) / l0 * pad],
      [p1[0] + (p1[0] - cx) / l1 * pad, p1[1] + (p1[1] - cy) / l1 * pad],
      [p2[0] + (p2[0] - cx) / l2 * pad, p2[1] + (p2[1] - cy) / l2 * pad]
    ];
  }

  // Draw each grid cell as 2 triangles
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      const tl = grid[r][c];
      const tr = grid[r][c + 1];
      const bl = grid[r + 1][c];
      const br = grid[r + 1][c + 1];

      // Canonical positions for this cell
      const cTL: [number, number] = [texX + (c / COLS) * texW, texY + (r / ROWS) * texH];
      const cTR: [number, number] = [texX + ((c + 1) / COLS) * texW, texY + (r / ROWS) * texH];
      const cBL: [number, number] = [texX + (c / COLS) * texW, texY + ((r + 1) / ROWS) * texH];
      const cBR: [number, number] = [texX + ((c + 1) / COLS) * texW, texY + ((r + 1) / ROWS) * texH];

      // Triangle 1: TL, TR, BL
      if (tl && tr && bl) {
        const m = solveAffine(cTL, cTR, cBL, tl, tr, bl);
        if (m) {
          context.save();
          const [et0, et1, et2] = expandTri(tl, tr, bl, 0.5);
          context.beginPath();
          context.moveTo(et0[0], et0[1]);
          context.lineTo(et1[0], et1[1]);
          context.lineTo(et2[0], et2[1]);
          context.closePath();
          context.clip();
          context.setTransform(m.a, m.d, m.b, m.e, m.c, m.f);
          context.drawImage(stageCanvas, 0, 0);
          context.restore();
        }
      }

      // Triangle 2: TR, BR, BL
      if (tr && br && bl) {
        const m = solveAffine(cTR, cBR, cBL, tr, br, bl);
        if (m) {
          context.save();
          const [et0, et1, et2] = expandTri(tr, br, bl, 0.5);
          context.beginPath();
          context.moveTo(et0[0], et0[1]);
          context.lineTo(et1[0], et1[1]);
          context.lineTo(et2[0], et2[1]);
          context.closePath();
          context.clip();
          context.setTransform(m.a, m.d, m.b, m.e, m.c, m.f);
          context.drawImage(stageCanvas, 0, 0);
          context.restore();
        }
      }
    }
  }
}
