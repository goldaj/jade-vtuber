/* Run with Node 20+ and the licensed Cubism Core JavaScript from the mobile installation:
   node check_r21_face_turn.cjs path/to/live2dcubismcore.min.js path/to/model.moc3 */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const {setImmediate: nextTurn} = require("node:timers/promises");

async function loadCore(script) {
  const context = vm.createContext({console, WebAssembly, atob, TextDecoder, TextEncoder, setTimeout, clearTimeout});
  vm.runInContext(fs.readFileSync(script, "utf8"), context, {filename: script});
  const core = context.Live2DCubismCore;
  assert(core?.Version, "Expected the Cubism Core browser build");
  const deadline = Date.now() + 10000;
  for (;;) {
    try {
      if (core.Version.csmGetVersion() > 0) return core;
    } catch (error) {
      if (Date.now() >= deadline) throw error;
    }
    assert(Date.now() < deadline, "Cubism Core initialization timed out");
    await nextTurn();
  }
}

function project(model, positions, vertex) {
  const {CanvasOriginX, CanvasOriginY, PixelsPerUnit} = model.canvasinfo;
  return [CanvasOriginX + positions[vertex * 2] * PixelsPerUnit,
          CanvasOriginY - positions[vertex * 2 + 1] * PixelsPerUnit];
}

function drawable(model, name) {
  const index = model.drawables.ids.indexOf(name);
  assert(index >= 0, `R21 drawable missing: ${name}`);
  return index;
}

// Bind a painted landmark inside its neutral triangle. Its barycentric coordinates
// then follow that same pixel through every pose, even if a triangle changes shape.
function track(model, name, x, y) {
  const mesh = drawable(model, name);
  const {indices, vertexPositions} = model.drawables;
  const triangles = indices[mesh];
  for (let i = 0; i < triangles.length; i += 3) {
    const triangle = triangles.subarray(i, i + 3);
    const [[ax, ay], [bx, by], [cx, cy]] = Array.from(triangle, v => project(model, vertexPositions[mesh], v));
    const det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy);
    if (Math.abs(det) < 1e-7) continue;
    const a = ((by - cy) * (x - cx) + (cx - bx) * (y - cy)) / det;
    const b = ((cy - ay) * (x - cx) + (ax - cx) * (y - cy)) / det;
    const weights = [a, b, 1 - a - b];
    if (Math.min(...weights) < -1e-5) continue;
    return () => {
      const point = [0, 0];
      for (const [j, weight] of weights.entries()) {
        const [vx, vy] = project(model, vertexPositions[mesh], triangle[j]);
        point[0] += weight * vx;
        point[1] += weight * vy;
      }
      return point;
    };
  }
  throw new Error(`R21 landmark outside neutral artwork: ${name} (${x}, ${y})`);
}

function signedArea(vertices, indices, t) {
  const a = 2 * indices[t], b = 2 * indices[t + 1], c = 2 * indices[t + 2];
  return (vertices[b] - vertices[a]) * (vertices[c + 1] - vertices[a + 1]) -
         (vertices[b + 1] - vertices[a + 1]) * (vertices[c] - vertices[a]);
}

// Project onto the line joining the two eyes in the current pose. Normalising
// by their separation makes the reading independent of the drawing's scale or roll.
function eyeLineOffset(point, eyes) {
  const [left, right] = eyes.map(eye => eye.centre());
  const dx = right[0] - left[0], dy = right[1] - left[1];
  const cx = (left[0] + right[0]) / 2, cy = (left[1] + right[1]) / 2;
  return ((point[0] - cx) * dx + (point[1] - cy) * dy) / (dx * dx + dy * dy);
}

// The two construction drawings are registered independently on R21's native
// canvas. Each row specifies the two jaw edges at one height (Y, left X, right X).
// The tip ends beneath the mouth, with a longer sweep on the near side.
const drawnJaw = {
  left: [[929,1700,1997],[953,1717,1953],[977,1741,1906],[995,1768,1866],
         [1007,1788,1833],[1013,1800,1818],[1016,1808,1808]],
  right: [[929,1848,2139],[953,1891,2123],[977,1937,2100],[995,1977,2073],
          [1007,2011,2053],[1013,2025,2040],[1016,2033,2033]],
};

function distanceToJaw([x, y], rows, side) {
  let distance = Infinity;
  for (let i = 1; i < rows.length; ++i) {
    const a = rows[i - 1], b = rows[i], dx = b[side] - a[side], dy = b[0] - a[0];
    const t = Math.max(0, Math.min(1, ((x - a[side]) * dx + (y - a[0]) * dy) / (dx * dx + dy * dy)));
    distance = Math.min(distance, Math.hypot(x - a[side] - t * dx, y - a[0] - t * dy));
  }
  return distance;
}

function verify(model) {
  const p = model.parameters, d = model.drawables;
  assert.equal(model.canvasinfo.CanvasWidth, 3840, "Expected R21 paint canvas width");
  assert.equal(model.canvasinfo.CanvasHeight, 5000, "Expected R21 paint canvas height");
  p.values.set(p.defaultValues);
  model.update();
  const nose = track(model, "JAD_R21_RESTORED_FACE", 1917, 853);
  const mouth = track(model, "JAD_R21_MOUTH_NEUTRAL_CLEAN", 1920, 930);
  const chin = track(model, "JAD_R21_RESTORED_FACE", 1921, 1019);
  const jawMesh = "JAD_R21_RESTORED_FACE";
  // Material points along the lower painted line in the neutral artwork.
  // Placing them one pixel inside the alpha edge avoids sampling a transparent texel.
  const jaw = [
    [1823,977],[1844,989],[1861,997],[1878,1006],[1897,1014],[1913,1020],
    [1921,1023],
    [1929,1021],[1946,1014],[1964,1006],[1981,998],[1999,989],[2013,981],
  ].map(([x, y]) => ({side:x < 1921 ? 1 : 2, tip:x === 1921, point:track(model,jawMesh,x,y)}));
  // The RGB paint on row 60 spans x18–101 on both iris plates. Using these
  // samples avoids measuring the transparent border or sheared ArtMesh bounds.
  const eyes = [["R", 1735, 713], ["L", 1988, 711]].map(([side, x, y]) => {
    const irisName = `JAD_R21_EYE_${side}_SOCKET_SKIN`;
    const first = track(model, irisName, x + 18, y + 60);
    const last = track(model, irisName, x + 101, y + 60);
    const width = () => last()[0] - first()[0];
    return {width, front: width(), centre: track(model, irisName, x + 59.5, y + 60),
            iris: drawable(model, irisName), closed: drawable(model, `JAD_R21_EYE_${side}_CLOSED_TRUE`)};
  });
  const frontChin = eyeLineOffset(chin(), eyes);
  const parameters = ["ParamAngleX", "ParamAngleY", "ParamEyeLOpen", "ParamEyeROpen", "ParamMouthOpenY", "ParamMouthForm"];
  const indices = parameters.map(id => {
    const i = p.ids.indexOf(id);
    assert(i >= 0, `R21 parameter missing: ${id}`);
    return i;
  });
  function pose(x, y, eye, opening) {
    const values = [x, y, eye, eye, opening, .28];
    indices.forEach((index, i) => { p.values[index] = values[i]; });
    model.update();
  }
  const meshes = Array.from(d.ids.keys()).filter(i => /(?:EYE_|RESTORED_FACE|MOUTH|BROW|HAIR_CAP|RESTORED_EAR)/.test(d.ids[i]));
  const rows = [], problems = new Set();
  let poses = 0;
  for (const eye of [0, .45, 1]) for (const opening of [0, .55]) {
    pose(0, 0, eye, opening);
    // Comparing the same aperture/opening isolates inversion caused by the turn.
    const front = new Map(meshes.map(i => [i, d.vertexPositions[i].slice()]));
    for (const y of [-20, 0, 20]) for (const x of [-30, -24, -18, -12, -6, 0, 6, 12, 18, 24, 30]) {
      pose(x, y, eye, opening);
      poses += 1;
      if (eye === 0 && eyes.some(e => d.opacities[e.iris] > .001 || d.opacities[e.closed] < .99))
        problems.add("Full blink must hide both irises and show both closed-eye drawings.");
      for (const i of meshes) {
        if (d.opacities[i] < .01) continue;
        let folded = 0, total = 0;
        for (let t = 0; t < d.indices[i].length; t += 3) {
          const before = signedArea(front.get(i), d.indices[i], t);
          const now = signedArea(d.vertexPositions[i], d.indices[i], t);
          total += Math.abs(before);
          if (Math.abs(before) > 1e-8 && Math.sign(before) !== Math.sign(now)) folded += Math.abs(before);
        }
        if (folded > total * .0005) problems.add(`Folded mesh: ${d.ids[i]} at X=${x}, Y=${y}, eye=${eye}`);
      }
      if (eye !== 1 || y !== 0 || opening !== 0) continue;
      const far = x < 0 ? 0 : 1, near = 1 - far;
      const noseX = nose()[0], mouthX = mouth()[0], chinPoint = chin();
      const chinOffset = eyeLineOffset(chinPoint, eyes) - frontChin;
      const ratio = eyes[near].width() / eyes[near].front;
      rows.push({x, noseX: +noseX.toFixed(1), mouthX: +mouthX.toFixed(1), chinX: +chinPoint[0].toFixed(1),
                 chinVsEyes: +chinOffset.toFixed(3),
                 nearIris: +ratio.toFixed(3), farIris: +(eyes[far].width() / eyes[far].front).toFixed(3)});
      if (Math.abs(x) >= 18 && Math.sign(x) * (noseX - mouthX) <= 0)
        problems.add(`Painted nose trails the mouth at X=${x}.`);
      // R21 design tolerances at full turn, in units of Jade's own frontal iris.
      // Freedom within the envelope is intentional; check the silhouette separately.
      if (Math.abs(x) === 30) {
        const farRatio = eyes[far].width() / eyes[far].front;
        if (ratio < .85 || ratio > 1.15) problems.add(`Near iris distorted at X=${x}: width ratio ${ratio.toFixed(3)}.`);
        if (farRatio < .50 || farRatio > .85) problems.add(`Far iris outside 3/4 projection at X=${x}: width ratio ${farRatio.toFixed(3)}.`);
        // In both approved three-quarter drawings the chin turns past the eye
        // midpoint after correcting for roll. Jade's registered jaw drawings
        // put the tip under the mouth (native X 1808/1809 and 2033/2031).
        if (Math.sign(x) * chinOffset <= 0)
          problems.add(`Chin stays behind the eye midpoint at X=${x} (offset ${chinOffset.toFixed(3)}).`);
        if (Math.abs(mouthX - chinPoint[0]) > .20 * eyes[near].front)
          problems.add(`Chin separates from the painted mouth centre at X=${x}.`);
        const target = x < 0 ? drawnJaw.left : drawnJaw.right;
        const [tipY, tipX] = target.at(-1);
        for (const mark of jaw) {
          const point = mark.point();
          const gap = mark.tip ? Math.hypot(point[0] - tipX, point[1] - tipY) :
            distanceToJaw(point, target, mark.side);
          // A small allowance covers line thickness and the polyline approximation.
          if (gap > 4)
            problems.add(`Painted ${mark.tip ? "chin tip" : "jaw line"} misses the drawing at X=${x} by ${gap.toFixed(1)} native px.`);
        }
      }
    }
  }
  console.table(rows);
  console.log(`${poses} poses. Relative iris width uses the frontal painting as 1.000.`);
  if (problems.size) throw new Error(Array.from(problems).join("\n"));
}

async function main() {
  const [script, modelFile] = process.argv.slice(2);
  assert(script && modelFile, "Usage: node check_r21_face_turn.cjs CORE_JS MODEL_MOC3");
  const core = await loadCore(script);
  const bytes = fs.readFileSync(modelFile);
  const moc = core.Moc.fromArrayBuffer(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
  assert(moc, "Cubism rejected the supplied MOC");
  let model;
  try {
    model = core.Model.fromMoc(moc);
    assert(model, "Cubism could not initialise the model");
    verify(model);
  } finally {
    model?.release();
    moc._release();
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
