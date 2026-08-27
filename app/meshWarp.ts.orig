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
