"""Offline tests for the bounded avatar control protocol."""
from io import StringIO
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, call, patch

try:
    from demo.reelle.avatar import (AvatarControls, EXPRESSIONS, NEUTRAL_EXPRESSION,
                                   _apply_expression, _read_commands)
except ModuleNotFoundError as exc:
    if exc.name not in {"demo", "demo.reelle", "demo.reelle.avatar"}:
        raise
    AvatarControls = None


@unittest.skipIf(AvatarControls is None, "graphical demo omitted from this preview")
class AvatarControlsTests(unittest.TestCase):
    def test_expression_allowlist_matches_original_model(self):
        root = Path(__file__).resolve().parents[1]
        model = root / "jade-modeling/runtime-installed/Jade_professional_r20_idle_complete/Jade.model3.json"
        if not model.is_file():
            self.skipTest("model omitted from this preview")
        data = json.loads(model.read_text(encoding="utf-8"))
        names = [item["Name"] for item in data["FileReferences"]["Expressions"]]
        self.assertEqual(list(EXPRESSIONS), names)
        self.assertEqual(len(EXPRESSIONS), 7)

    def test_expression_is_bounded_coalesced_and_independent_of_mouth(self):
        controls = AvatarControls()
        for name in (*EXPRESSIONS, NEUTRAL_EXPRESSION):
            self.assertTrue(controls.accept(json.dumps({"type": "expression", "value": name})))
            self.assertEqual(controls.take_expression(), name)
            self.assertIsNone(controls.take_expression())
        for name in (None, True, 1, [], {}, "smile", "../../Smile", "x" * 1000):
            self.assertFalse(controls.accept(json.dumps({"type": "expression", "value": name})))
        self.assertIsNone(controls.take_expression())
        self.assertTrue(controls.accept('{"type":"expression","value":"Sad"}'))
        self.assertTrue(controls.accept('{"type":"mouth","value":0.8}'))
        self.assertTrue(controls.accept('{"type":"expression","value":"Smile"}'))
        self.assertEqual(controls.take_expression(), "Smile")
        self.assertEqual(controls.level(), 0.8)

    def test_expression_replaces_overlay_and_neutral_clears_it(self):
        model = Mock()
        _apply_expression(model, "Smile")
        self.assertEqual(model.mock_calls, [call.ResetExpressions(), call.SetExpression("Smile")])
        model.reset_mock()
        _apply_expression(model, NEUTRAL_EXPRESSION)
        self.assertEqual(model.mock_calls, [call.ResetExpressions()])
        model.reset_mock()
        with self.assertRaises(ValueError):
            _apply_expression(model, "unknown")
        model.ResetExpressions.assert_not_called()

    def test_mouth_values_and_expiration(self):
        controls = AvatarControls()
        with patch("demo.reelle.avatar.time.monotonic", return_value=10.0):
            self.assertTrue(controls.accept('{"type":"mouth","value":0.75}'))
        self.assertEqual(controls.level(now=10.4), 0.75)
        self.assertEqual(controls.level(now=10.6), 0.0)

    def test_rejects_bad_values_and_oversized_commands(self):
        controls = AvatarControls()
        for command in ('{}', 'null', '{', '{"type":"mouth","value":true}',
                        '{"type":"mouth","value":NaN}',
                        '{"type":"mouth","value":1.1}',
                        '{"type":"mouth","value":-0.1}',
                        '{"type":"mouth","value":' + '9' * 900 + '}', 'x' * 1025):
            self.assertFalse(controls.accept(command))
        self.assertEqual(controls.level(), 0.0)

    def test_eof_stops_and_long_line_cannot_inject_a_command_suffix(self):
        controls = AvatarControls()
        stream = StringIO('x' * 1025 + '{"type":"mouth","value":1}\n')
        _read_commands(stream, controls)
        self.assertTrue(controls.stopped.is_set())
        self.assertEqual(controls.level(), 0.0)

    def test_stop_command(self):
        controls = AvatarControls()
        self.assertTrue(controls.accept('{"type":"stop"}'))
        self.assertTrue(controls.stopped.is_set())


if __name__ == "__main__":
    unittest.main()
