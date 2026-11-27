"""Asset contracts for all eighteen r21 intent motions; no legacy r20 fixture.

These tests check runnable Cubism curves and source/export integrity. They do
not replace observation of the rendered character or a native Cubism export.
"""
import importlib.util
import json
import math
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "jade-modeling/assets/live2d/r21_professional_art/livraison/Jade_r21_v45_1"
MODEL = BUNDLE / "Jade_r21_v45"
INTENTS = ("neutral", "playful", "excited", "curious", "tender", "reassuring", "serious", "sad", "angry")
NEW_INTENTS = ("sad", "angry")
# Ranges observed on the shipped r21 v49.1 through Cubism Core. Parameters
# driven by tracking/audio/physics are deliberately absent from new motions.
BOUNDS = {
    **{f"ParamAngle{axis}": (-30, 30) for axis in "XYZ"},
    **{f"ParamBodyAngle{axis}": (-10, 10) for axis in "XYZ"},
    **{name: (-1, 1) for name in (
        "ParamEyeBallX", "ParamEyeBallY", "ParamBrowLY", "ParamBrowRY",
        "ParamJadeIdleLean", "ParamJadeWeightShift")},
    **{name: (0, 1) for name in (
        "ParamJadeLegRelaxL", "ParamJadeLegRelaxR", "ParamJadeEarTwitchL", "ParamJadeEarTwitchR", "ParamBreath")},
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def segments(curve):
    """Read actual motion3 segment opcodes independently of the exporter."""
    flat = curve["Segments"]
    current = (flat[0], flat[1])
    offset = 2
    while offset < len(flat):
        kind = flat[offset]
        count = 6 if kind == 1 else 2
        values = flat[offset + 1:offset + 1 + count]
        if kind not in (0, 1, 2, 3) or len(values) != count:
            raise AssertionError("Malformed Cubism curve")
        points = [current, *[(values[i], values[i + 1]) for i in range(0, count, 2)]]
        yield kind, points
        current = points[-1]
        offset += 1 + count


def value_at(curve, time):
    for kind, points in segments(curve):
        start, end = points[0], points[-1]
        if time > end[0]:
            continue
        u = max(0, min(1, (time - start[0]) / (end[0] - start[0])))
        if kind == 0:
            return start[1] + (end[1] - start[1]) * u
        if kind == 1:
            return ((1-u)**3*start[1] + 3*(1-u)**2*u*points[1][1]
                    + 3*(1-u)*u*u*points[2][1] + u**3*end[1])
        return start[1] if kind == 2 else end[1]
    return curve["Segments"][-1]


# The private code preview carries Python tests but deliberately omits the
# entire modeling workshop. Its explicit export marker is required for this
# skip: missing assets in a full checkout (or a partial workshop) must fail.
@unittest.skipIf(
    (ROOT / "PREVIEW_NOT_FOR_PUBLICATION.txt").is_file()
    and not (ROOT / "jade-modeling").exists(),
    "private publication preview intentionally excludes the r21 modeling workshop",
)
class R21IntentMotionTests(unittest.TestCase):
    def test_both_r21_manifests_expose_two_motions_per_intent(self):
        for filename in ("Jade_r21_mobile.model3.json", "Jade_r21_v45.model3.json"):
            with self.subTest(manifest=filename):
                manifest = read(MODEL / filename)
                groups = manifest["FileReferences"]["Motions"]
                self.assertEqual(set(groups) - {"Idle"}, {name.title() for name in INTENTS})
                paths = []
                for name in INTENTS:
                    entries = groups[name.title()]
                    self.assertEqual(len(entries), 2, name)
                    for variant, entry in zip("AB", entries):
                        path = MODEL / entry["File"]
                        self.assertTrue(path.is_file(), path)
                        self.assertEqual(path.name, f"Jade_{name}_{variant}.motion3.json")
                        paths.append(path)
                self.assertEqual(len(set(paths)), 18)
                # New curves are shared between the mobile and portable r21
                # package, so maintaining one cannot silently leave the other stale.
                for name in NEW_INTENTS:
                    self.assertTrue(all(x["File"].startswith("mobile/") for x in groups[name.title()]))

    def test_eighteen_mobile_motions_have_valid_bounded_curves_and_free_blink_lipsync(self):
        known = {p["Id"] for p in read(MODEL / "Jade_r21_v45.cdi3.json")["Parameters"]}
        for name in INTENTS:
            for variant in "AB":
                with self.subTest(intent=name, variant=variant):
                    motion = read(MODEL / "mobile" / f"Jade_{name}_{variant}.motion3.json")
                    meta = motion["Meta"]
                    self.assertEqual(motion["Version"], 3)
                    self.assertFalse(meta["Loop"])
                    self.assertTrue(meta["AreBeziersRestricted"])
                    self.assertGreater(meta["Duration"], 0)
                    self.assertGreater(meta["FadeInTime"], 0)
                    self.assertGreater(meta["FadeOutTime"], 0)
                    self.assertEqual(meta["CurveCount"], len(motion["Curves"]))
                    ids = [c["Id"] for c in motion["Curves"]]
                    self.assertEqual(len(set(ids)), len(ids))
                    self.assertLessEqual(set(ids), known)
                    self.assertFalse(set(ids) & {"ParamMouthOpenY", "ParamMouthForm", "ParamEyeLOpen", "ParamEyeROpen"})
                    segment_count, point_count = 0, len(ids)
                    for curve in motion["Curves"]:
                        self.assertEqual(curve["Target"], "Parameter")
                        self.assertEqual(curve["Segments"][:2], [0, 0])
                        self.assertEqual(curve["Segments"][-2:], [meta["Duration"], 0])
                        low, high = BOUNDS[curve["Id"]]
                        for kind, points in segments(curve):
                            segment_count += 1
                            point_count += len(points) - 1
                            self.assertLess(points[0][0], points[-1][0])
                            self.assertEqual(sorted(p[0] for p in points), [p[0] for p in points])
                            for t, v in points:
                                self.assertTrue(math.isfinite(t) and math.isfinite(v))
                                self.assertGreaterEqual(v, low)
                                self.assertLessEqual(v, high)
                            if kind == 1:
                                t0, t1 = points[0][0], points[-1][0]
                                self.assertAlmostEqual(points[1][0], t0 + (t1-t0)/3, places=5)
                                self.assertAlmostEqual(points[2][0], t0 + 2*(t1-t0)/3, places=5)
                        # Sample all 18 real exports at frame cadence; not just key values.
                        for frame in range(math.ceil(meta["Duration"] * 60) + 1):
                            value = value_at(curve, frame / 60)
                            self.assertGreaterEqual(value, low - 1e-6)
                            self.assertLessEqual(value, high + 1e-6)
                    self.assertEqual(meta["TotalSegmentCount"], segment_count)
                    self.assertEqual(meta["TotalPointCount"], point_count)

    def test_new_variants_have_distinct_choreography_not_only_different_speed(self):
        for name in NEW_INTENTS:
            with self.subTest(intent=name):
                motions = [read(MODEL / "mobile" / f"Jade_{name}_{v}.motion3.json") for v in "AB"]
                tracks = [{c["Id"]: c for c in m["Curves"]} for m in motions]
                # A remains engaged in front; B turns away and returns. This
                # distinction survives normalising both clips to the same duration.
                self.assertNotIn("ParamAngleX", tracks[0])
                self.assertIn("ParamAngleX", tracks[1])
                weight = [value_at(t["ParamJadeWeightShift"], m["Meta"]["Duration"]*.3)
                          for t, m in zip(tracks, motions)]
                self.assertLess(weight[0] * weight[1], 0)
                for track in tracks:
                    self.assertTrue({"ParamEyeBallX", "ParamEyeBallY", "ParamAngleY",
                                     "ParamJadeIdleLean", "ParamJadeEarTwitchL", "ParamJadeEarTwitchR"} <= set(track))

    def test_editable_sources_reproduce_new_exports(self):
        path = ROOT / "jade-modeling/tools/export_r21_intent_motions.py"
        spec = importlib.util.spec_from_file_location("export_r21_intent_motions", path)
        exporter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(exporter)
        for name in NEW_INTENTS:
            source = BUNDLE / "Edition/mobile-intentions" / f"Jade_{name}.psd2live-motions.json"
            self.assertEqual(len(exporter.export_file(source, MODEL / "mobile", check=True)), 2)

    def test_angry_expression_is_mapped_and_leaves_audio_and_blink_controls_free(self):
        expression = read(MODEL / "expressions/Angry.exp3.json")
        self.assertEqual(expression["Type"], "Live2D Expression")
        controls = {p["Id"]: p for p in expression["Parameters"]}
        self.assertFalse(set(controls) & {"ParamMouthOpenY", "ParamEyeLOpen", "ParamEyeROpen"})
        self.assertLess(controls["ParamMouthForm"]["Value"], 0)
        for param in controls.values():
            self.assertEqual(param["Blend"], "Add")
            self.assertGreaterEqual(param["Value"], -1)
            self.assertLessEqual(param["Value"], 1)
        for filename in ("Jade_r21_mobile.model3.json", "Jade_r21_v45.model3.json"):
            entries = read(MODEL / filename)["FileReferences"]["Expressions"]
            self.assertEqual(sum(p["Name"] == "Angry" for p in entries), 1)
            self.assertIn({"Name": "Angry", "File": "expressions/Angry.exp3.json"}, entries)


if __name__ == "__main__":
    unittest.main()
