import { CANONICAL_POINTS, MESH_TRIANGLES } from "./meshData";
import { makeupTransform } from "./kumoMakeup";

let gl: WebGLRenderingContext | null = null;
let glCanvas: HTMLCanvasElement | null = null;
let program: WebGLProgram | null = null;
let posBuffer: WebGLBuffer | null = null;
let uvBuffer: WebGLBuffer | null = null;
let indexBuffer: WebGLBuffer | null = null;
let textureUnit: WebGLTexture | null = null;

function initWebGL(width: number, height: number) {
  if (typeof document === 'undefined') return false; // SSR safety
  if (!glCanvas) {
    glCanvas = document.createElement('canvas');
    gl = glCanvas.getContext('webgl', { premultipliedAlpha: true, antialias: true, alpha: true });
    if (!gl) return false;

    const vs = gl.createShader(gl.VERTEX_SHADER)!;
    gl.shaderSource(vs, `
      attribute vec2 a_position;
      attribute vec2 a_texCoord;
      uniform vec2 u_resolution;
      varying vec2 v_texCoord;
      void main() {
        vec2 zeroToOne = a_position / u_resolution;
        vec2 zeroToTwo = zeroToOne * 2.0;
        vec2 clipSpace = zeroToTwo - 1.0;
        gl_Position = vec4(clipSpace * vec2(1, -1), 0, 1);
        v_texCoord = a_texCoord;
      }
    `);
    gl.compileShader(vs);

    const fs = gl.createShader(gl.FRAGMENT_SHADER)!;
    gl.shaderSource(fs, `
      precision mediump float;
      uniform sampler2D u_image;
      varying vec2 v_texCoord;
      void main() {
        gl_FragColor = texture2D(u_image, v_texCoord);
      }
    `);
    gl.compileShader(fs);

    program = gl.createProgram()!;
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);

    posBuffer = gl.createBuffer();
    uvBuffer = gl.createBuffer();
    indexBuffer = gl.createBuffer();
    textureUnit = gl.createTexture();
  }

  if (glCanvas.width !== width || glCanvas.height !== height) {
    glCanvas.width = width;
    glCanvas.height = height;
    gl!.viewport(0, 0, width, height);
  }
  return true;
}

export function drawMeshWebGL(
  context: CanvasRenderingContext2D,
  source: HTMLCanvasElement,
  realLandmarks: number[][],
  globalTransform: NonNullable<ReturnType<typeof makeupTransform>>
) {
  const w = context.canvas.width;
  const h = context.canvas.height;
  if (!initWebGL(w, h)) return false;

  gl!.useProgram(program!);

  const realPts = [...realLandmarks];
  const corners = [[0,0], [1000,0], [0,1500], [1000,1500]];
  for (const c of corners) {
    const rx = globalTransform.a * c[0] + globalTransform.b * c[1] + globalTransform.c;
    const ry = globalTransform.d * c[0] + globalTransform.e * c[1] + globalTransform.f;
    realPts.push([rx, ry]);
  }
  
  const canonPts = [...CANONICAL_POINTS, ...corners];

  const positions = new Float32Array(realPts.length * 2);
  for(let i=0; i<realPts.length; i++) {
    positions[i*2] = realPts[i][0];
    positions[i*2+1] = realPts[i][1];
  }

  const uvs = new Float32Array(canonPts.length * 2);
  for(let i=0; i<canonPts.length; i++) {
    uvs[i*2] = canonPts[i][0] / 1000;
    uvs[i*2+1] = canonPts[i][1] / 1500;
  }

  const indices = new Uint16Array(MESH_TRIANGLES.length * 3);
  for(let i=0; i<MESH_TRIANGLES.length; i++) {
    indices[i*3] = MESH_TRIANGLES[i][0];
    indices[i*3+1] = MESH_TRIANGLES[i][1];
    indices[i*3+2] = MESH_TRIANGLES[i][2];
  }

  gl!.bindBuffer(gl!.ARRAY_BUFFER, posBuffer);
  gl!.bufferData(gl!.ARRAY_BUFFER, positions, gl!.STATIC_DRAW);
  const posLoc = gl!.getAttribLocation(program!, "a_position");
  gl!.enableVertexAttribArray(posLoc);
  gl!.vertexAttribPointer(posLoc, 2, gl!.FLOAT, false, 0, 0);

  gl!.bindBuffer(gl!.ARRAY_BUFFER, uvBuffer);
  gl!.bufferData(gl!.ARRAY_BUFFER, uvs, gl!.STATIC_DRAW);
  const uvLoc = gl!.getAttribLocation(program!, "a_texCoord");
  gl!.enableVertexAttribArray(uvLoc);
  gl!.vertexAttribPointer(uvLoc, 2, gl!.FLOAT, false, 0, 0);

  gl!.bindBuffer(gl!.ELEMENT_ARRAY_BUFFER, indexBuffer);
  gl!.bufferData(gl!.ELEMENT_ARRAY_BUFFER, indices, gl!.STATIC_DRAW);

  const resLoc = gl!.getUniformLocation(program!, "u_resolution");
  gl!.uniform2f(resLoc, w, h);

  gl!.bindTexture(gl!.TEXTURE_2D, textureUnit);
  gl!.texParameteri(gl!.TEXTURE_2D, gl!.TEXTURE_WRAP_S, gl!.CLAMP_TO_EDGE);
  gl!.texParameteri(gl!.TEXTURE_2D, gl!.TEXTURE_WRAP_T, gl!.CLAMP_TO_EDGE);
  gl!.texParameteri(gl!.TEXTURE_2D, gl!.TEXTURE_MIN_FILTER, gl!.LINEAR);
  gl!.texParameteri(gl!.TEXTURE_2D, gl!.TEXTURE_MAG_FILTER, gl!.LINEAR);
  gl!.texImage2D(gl!.TEXTURE_2D, 0, gl!.RGBA, gl!.RGBA, gl!.UNSIGNED_BYTE, source);

  gl!.clearColor(0,0,0,0);
  gl!.clear(gl!.COLOR_BUFFER_BIT | gl!.DEPTH_BUFFER_BIT);
  gl!.enable(gl!.BLEND);
  gl!.blendFunc(gl!.ONE, gl!.ONE_MINUS_SRC_ALPHA);

  gl!.drawElements(gl!.TRIANGLES, indices.length, gl!.UNSIGNED_SHORT, 0);

  context.save();
  context.setTransform(1,0,0,1,0,0);
  context.drawImage(glCanvas!, 0, 0);
  context.restore();
  return true;
}

/**
 * Kumoo 2.5D EyeLash Algorithm (Use2Dot5DEyeLash = 1)
 * 
 * Parametric Eyelid Radian Normal Curve deformation:
 * 1. Build eyelid curve C(t) from 5 upper eyelid landmarks
 * 2. Compute tangent T(t) and outward normal N(t) at each t
 * 3. Map each vertex: V(u,v) = C(u) + v * stripHeight * N(u)
 * 4. Render via WebGL vertex grid with bilinear sampling = sharp strands
 */
export function draw2dot5DEyeLash(
  context: CanvasRenderingContext2D,
  source: HTMLCanvasElement,
  layerRect: [number, number, number, number],
  canonicalW: number,
  canonicalH: number,
  canonLidPts: number[][],   // 5 canonical upper eyelid points [outer->inner]
  realLidPts: number[][],    // 5 real upper eyelid landmarks (output canvas coords)
  hiresScale: number = 1,    // scale factor of source relative to canonical
) {
  const w = context.canvas.width;
  const h = context.canvas.height;
  if (!initWebGL(w, h)) return false;

  const [sx, sy, sw, sh] = layerRect;
  const COLS = 20;
  const ROWS = 10;

  // Build parameterized curve from points
  function buildCurve(pts: number[][]) {
    let total = 0;
    const lens: number[] = [];
    for (let i = 0; i < pts.length - 1; i++) {
      const l = Math.hypot(pts[i+1][0] - pts[i][0], pts[i+1][1] - pts[i][1]) || 0.001;
      lens.push(l);
      total += l;
    }
    return {
      total,
      at(t: number) {
        const target = Math.max(0, Math.min(1, t)) * total;
        let cur = 0;
        for (let i = 0; i < pts.length - 1; i++) {
          if (cur + lens[i] >= target || i === pts.length - 2) {
            const lt = Math.min(1, Math.max(0, (target - cur) / lens[i]));
            const dx = pts[i+1][0] - pts[i][0];
            const dy = pts[i+1][1] - pts[i][1];
            const len = Math.hypot(dx, dy) || 0.001;
            return {
              x: pts[i][0] + dx * lt,
              y: pts[i][1] + dy * lt,
              // Normal perpendicular to tangent
              nx: -dy / len,
              ny: dx / len,
            };
          }
          cur += lens[i];
        }
        return { x: pts[0][0], y: pts[0][1], nx: 0, ny: -1 };
      }
    };
  }

  const canonCurve = buildCurve(canonLidPts);
  const realCurve = buildCurve(realLidPts);
  const scale = realCurve.total / canonCurve.total;

  // Canonical outer/inner X for parameter mapping
  const cOuterX = canonLidPts[0][0];
  const cInnerX = canonLidPts[canonLidPts.length - 1][0];
  const cWidth = cInnerX - cOuterX;

  // Build vertex grid
  const positions: number[] = [];
  const uvs: number[] = [];

  for (let r = 0; r <= ROWS; r++) {
    const rowFrac = r / ROWS; // 0=top(tips), 1=bottom(eyelid base)
    for (let c = 0; c <= COLS; c++) {
      const colFrac = c / COLS;
      const texX = sx + colFrac * sw;
      const texY = sy + rowFrac * sh;

      // UV coords for texture sampling (source may be hires-scaled)
      uvs.push((texX * hiresScale) / source.width, (texY * hiresScale) / source.height);

      // Parameter t along the eyelid (0=outer, 1=inner)
      const t = (texX - cOuterX) / cWidth;

      // Canonical: how far above the eyelid is this point?
      const cPt = canonCurve.at(t);
      const canonDist = cPt.y - texY; // positive = above eyelid

      // Real: place at eyelid + offset along normal
      const rPt = realCurve.at(t);
      
      // For upper eyelid: normal MUST point UP (negative Y in screen coords)
      // buildCurve returns (-dy, dx) which may point down, so flip if needed
      let nx = rPt.nx;
      let ny = rPt.ny;
      if (ny > 0) { nx = -nx; ny = -ny; }

      // canonDist > 0 = above eyelid → move along upward normal
      // canonDist < 0 = below eyelid → move against normal (toward eye)
      positions.push(
        rPt.x + nx * canonDist * scale,
        rPt.y + ny * canonDist * scale
      );
    }
  }

  // Triangle indices
  const indices: number[] = [];
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      const tl = r * (COLS + 1) + c;
      const tr = tl + 1;
      const bl = (r + 1) * (COLS + 1) + c;
      const br = bl + 1;
      indices.push(tl, tr, bl);
      indices.push(tr, br, bl);
    }
  }

  // Render via WebGL
  gl!.useProgram(program!);

  gl!.bindBuffer(gl!.ARRAY_BUFFER, posBuffer);
  gl!.bufferData(gl!.ARRAY_BUFFER, new Float32Array(positions), gl!.STATIC_DRAW);
  const posLoc = gl!.getAttribLocation(program!, "a_position");
  gl!.enableVertexAttribArray(posLoc);
  gl!.vertexAttribPointer(posLoc, 2, gl!.FLOAT, false, 0, 0);

  gl!.bindBuffer(gl!.ARRAY_BUFFER, uvBuffer);
  gl!.bufferData(gl!.ARRAY_BUFFER, new Float32Array(uvs), gl!.STATIC_DRAW);
  const uvLoc = gl!.getAttribLocation(program!, "a_texCoord");
  gl!.enableVertexAttribArray(uvLoc);
  gl!.vertexAttribPointer(uvLoc, 2, gl!.FLOAT, false, 0, 0);

  gl!.bindBuffer(gl!.ELEMENT_ARRAY_BUFFER, indexBuffer);
  gl!.bufferData(gl!.ELEMENT_ARRAY_BUFFER, new Uint16Array(indices), gl!.STATIC_DRAW);

  const resLoc = gl!.getUniformLocation(program!, "u_resolution");
  gl!.uniform2f(resLoc, w, h);

  gl!.bindTexture(gl!.TEXTURE_2D, textureUnit);
  gl!.texParameteri(gl!.TEXTURE_2D, gl!.TEXTURE_WRAP_S, gl!.CLAMP_TO_EDGE);
  gl!.texParameteri(gl!.TEXTURE_2D, gl!.TEXTURE_WRAP_T, gl!.CLAMP_TO_EDGE);
  gl!.texParameteri(gl!.TEXTURE_2D, gl!.TEXTURE_MIN_FILTER, gl!.LINEAR);
  gl!.texParameteri(gl!.TEXTURE_2D, gl!.TEXTURE_MAG_FILTER, gl!.LINEAR);
  gl!.texImage2D(gl!.TEXTURE_2D, 0, gl!.RGBA, gl!.RGBA, gl!.UNSIGNED_BYTE, source);

  gl!.clearColor(0, 0, 0, 0);
  gl!.clear(gl!.COLOR_BUFFER_BIT);
  gl!.enable(gl!.BLEND);
  gl!.blendFunc(gl!.ONE, gl!.ONE_MINUS_SRC_ALPHA);

  gl!.drawElements(gl!.TRIANGLES, indices.length, gl!.UNSIGNED_SHORT, 0);

  context.save();
  context.setTransform(1, 0, 0, 1, 0, 0);
  context.drawImage(glCanvas!, 0, 0);
  context.restore();
  return true;
}
