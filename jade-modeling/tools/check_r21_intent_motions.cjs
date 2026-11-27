/* Verify the real r21 geometry with the licensed Cubism Core browser build.
   Usage: node check_r21_intent_motions.cjs CORE_JS MODEL_MOC [MODEL3_JSON]

   The default manifest is the application's r21 mobile manifest. MODEL_MOC
   may be a hydrated copy outside the checkout, but its SHA must match the
   manifest's MOC or its Git LFS pointer. No Git executable is required.

   JSON evidence is written to stdout; SDK diagnostics go to stderr. This is
   a geometry/parameter check, not a visual or physical-device acceptance.
*/
"use strict";
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const {setImmediate: nextTurn} = require("node:timers/promises");

const DEFAULT_MANIFEST = path.resolve(__dirname,
  "../assets/live2d/r21_professional_art/livraison/Jade_r21_v45_1/Jade_r21_v45/Jade_r21_mobile.model3.json");
const INTENTS = ["Neutral", "Playful", "Excited", "Curious", "Tender", "Reassuring", "Serious", "Sad", "Angry"];
const FPS = 60;
const hash = bytes => crypto.createHash("sha256").update(bytes).digest("hex");

async function loadCore(script) {
  const context = vm.createContext({
    console: {log: (...args) => console.error(...args), warn: (...args) => console.error(...args), error: (...args) => console.error(...args)},
    WebAssembly, atob, TextDecoder, TextEncoder, setTimeout, clearTimeout,
  });
  vm.runInContext(fs.readFileSync(script, "utf8"), context, {filename: path.basename(script)});
  const core = context.Live2DCubismCore;
  assert(core?.Version, "Expected the Cubism Core browser build");
  const deadline = Date.now() + 10000;
  for (;;) {
    try { if (core.Version.csmGetVersion() > 0) return core; } catch (error) {
      if (Date.now() >= deadline) throw error;
    }
    assert(Date.now() < deadline, "Cubism Core initialization timed out");
    await nextTurn();
  }
}

function sample(curve, time) {
  const data = curve.Segments;
  let t0 = data[0], v0 = data[1];
  for (let offset = 2; offset < data.length;) {
    const kind = data[offset], length = kind === 1 ? 7 : 3;
    assert([0, 1, 2, 3].includes(kind), "Unknown Cubism segment kind");
    assert(offset + length <= data.length, "Truncated Cubism segment");
    const t1 = data[offset + length - 2], v1 = data[offset + length - 1];
    assert(t1 > t0, "Motion times must increase");
    if (time <= t1) {
      const u = Math.max(0, Math.min(1, (time - t0) / (t1 - t0)));
      if (kind === 1) {
        assert(Math.abs(data[offset + 1] - t0 - (t1-t0)/3) < 2e-6, "Expected restricted Bezier");
        assert(Math.abs(data[offset + 3] - t0 - 2*(t1-t0)/3) < 2e-6, "Expected restricted Bezier");
        return (1-u)**3*v0 + 3*(1-u)**2*u*data[offset+2] + 3*(1-u)*u*u*data[offset+4] + u**3*v1;
      }
      if (kind === 0) return v0 + (v1-v0)*u;
      return kind === 2 ? v0 : v1;
    }
    t0 = t1; v0 = v1; offset += length;
  }
  return v0;
}

async function verify(corePath, mocPath, manifestPath) {
  const manifestBytes = fs.readFileSync(manifestPath), manifest = JSON.parse(manifestBytes);
  const base = path.dirname(manifestPath), bytes = fs.readFileSync(mocPath);
  const referencedMoc = fs.readFileSync(path.join(base, manifest.FileReferences.Moc));
  const lfsOid = referencedMoc.toString("utf8", 0, 160).match(/^version https:\/\/git-lfs.github.com\/spec\/v1\noid sha256:([a-f0-9]{64})\n/);
  assert.equal(hash(bytes), lfsOid?.[1] ?? hash(referencedMoc), "Supplied MOC differs from the active manifest");
  const C = await loadCore(corePath);
  const moc = C.Moc.fromArrayBuffer(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
  assert(moc, "Cubism Core did not load the supplied MOC");
  const model = C.Model.fromMoc(moc);
  assert(model, "Cubism Core did not create the model");
  const p = model.parameters, d = model.drawables;
  assert(p.ids.includes("ParamJadeWeightShift") && p.ids.includes("ParamJadeEarFollowL"), "Expected the r21 rig");
  p.values.set(p.defaultValues);
  model.update();
  const baseline = d.vertexPositions.map(x => Float32Array.from(x));
  const shoes = d.ids.map((id, index) => /SHOE/.test(id) ? index : -1).filter(index => index >= 0);
  assert(shoes.length >= 2, "Expected both r21 shoe drawables");
  const groups = manifest.FileReferences.Motions;
  assert.deepEqual(Object.keys(groups).filter(group => group !== "Idle").sort(), [...INTENTS].sort());
  let poses = 0;
  const rows = [];
  for (const [group, entries] of Object.entries(groups)) {
    if (group === "Idle") continue;
    assert.equal(entries.length, 2, `Expected two variants for ${group}`);
    for (const entry of entries) {
      const motionBytes = fs.readFileSync(path.join(base, entry.File));
      const motion = JSON.parse(motionBytes);
      assert(motion.Meta.AreBeziersRestricted && !motion.Meta.Loop);
      assert(Number.isFinite(motion.Meta.Duration) && motion.Meta.Duration > 0 && motion.Meta.Duration < 30);
      const tracks = motion.Curves.map(curve => {
        assert.equal(curve.Target, "Parameter");
        assert(!["ParamEyeLOpen", "ParamEyeROpen", "ParamMouthOpenY"].includes(curve.Id), "Blink/lip-sync must stay free");
        const index = p.ids.indexOf(curve.Id);
        assert(index >= 0, `Parameter missing from r21: ${curve.Id}`);
        return {curve, index};
      });
      let maxShoe = 0;
      const frames = Math.ceil(motion.Meta.Duration * FPS);
      for (let frame = 0; frame <= frames; frame++) {
        p.values.set(p.defaultValues);
        for (const {curve, index} of tracks) {
          const value = sample(curve, Math.min(frame / FPS, motion.Meta.Duration));
          assert(value >= p.minimumValues[index]-1e-6 && value <= p.maximumValues[index]+1e-6, `Out-of-range ${curve.Id}`);
          p.values[index] = value;
        }
        model.update();
        for (let j = 0; j < d.count; j++) for (const value of d.vertexPositions[j]) assert(Number.isFinite(value));
        for (const j of shoes) for (let k = 0; k < d.vertexPositions[j].length; k++) {
          maxShoe = Math.max(maxShoe, Math.abs(d.vertexPositions[j][k]-baseline[j][k]) * model.canvasinfo.PixelsPerUnit);
        }
        poses++;
      }
      let residual = 0;
      for (let j = 0; j < d.count; j++) for (let k = 0; k < d.vertexPositions[j].length; k++) {
        residual = Math.max(residual, Math.abs(d.vertexPositions[j][k]-baseline[j][k]) * model.canvasinfo.PixelsPerUnit);
      }
      assert(residual < .001, `Motion does not return to rest: ${entry.File}`);
      rows.push({motion: entry.File, sha256: hash(motionBytes), durationSeconds: motion.Meta.Duration,
        maxShoePixels: +maxShoe.toFixed(4), restResidualPixels: +residual.toFixed(5)});
    }
  }
  return {
    verification: "Cubism Core geometry and parameter bounds; no visual or hardware acceptance",
    model: "r21", mocSha256: hash(bytes), coreJsSha256: hash(fs.readFileSync(corePath)),
    coreVersion: C.Version.csmGetVersion(), manifest: path.basename(manifestPath), manifestSha256: hash(manifestBytes),
    sampleFps: FPS, poses, shoeDrawables: shoes.map(index => d.ids[index]), rows,
  };
}

async function main() {
  const [corePath, mocPath, manifestPath = DEFAULT_MANIFEST] = process.argv.slice(2);
  assert(corePath && mocPath, "Usage: node check_r21_intent_motions.cjs CORE_JS MODEL_MOC [MODEL3_JSON]");
  console.log(JSON.stringify(await verify(corePath, mocPath, manifestPath), null, 2));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
