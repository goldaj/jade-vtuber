"""Private PWA model slots use synthetic bundles only; no real model or API."""
import asyncio
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.jade_runtime.config import Settings
from src.jade_runtime.mobile_gateway import MobileGateway


def bundle(path: Path, tag: bytes = b"next") -> dict:
    path.mkdir(parents=True)
    (path / "textures").mkdir()
    (path / "Jade.moc3").write_bytes(b"MOC3" + tag)
    (path / "textures/texture.png").write_bytes(b"\x89PNG\r\n\x1a\n" + tag)
    model = {"Version": 3, "FileReferences": {
        "Moc": "Jade.moc3", "Textures": ["textures/texture.png"]}}
    write_manifest(path, model)
    return model


def write_manifest(path: Path, model: dict) -> None:
    (path / "Jade.model3.json").write_text(json.dumps(model), encoding="utf-8")


class ModelSlotConfigurationTests(unittest.TestCase):
    def test_second_model_requires_explicit_configuration(self):
        self.assertEqual(Settings().mobile_second_model_dir, "")
        with patch("src.jade_runtime.config.environ", side_effect=lambda name, default="": default):
            self.assertEqual(Settings.load().mobile_second_model_dir, "")
        with patch("src.jade_runtime.config.environ", side_effect=lambda name, default="": (
                "  /private/future-model  " if name == "JADE_MOBILE_SECOND_MODEL_DIR" else default)):
            self.assertEqual(Settings.load().mobile_second_model_dir, "/private/future-model")


class MobileModelSlotTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.classic = self.root / "classic"
        bundle(self.classic, b"classic")
        self.gateway = MobileGateway(
            SimpleNamespace(), SimpleNamespace(), token="x" * 40,
            owner_login="owner@example.test", model_dir=self.classic)
        self.server = await asyncio.start_server(self.gateway._accept, "127.0.0.1", port=0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()
        if self.gateway.connections:
            await asyncio.gather(*self.gateway.connections, return_exceptions=True)

    async def request(self, path: str, *, owner="owner@example.test", bearer=False):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        headers = [f"GET {path} HTTP/1.1", f"Host: 127.0.0.1:{self.port}"]
        if owner is not None:
            headers.append(f"Tailscale-User-Login: {owner}")
        if bearer:
            headers.append("Authorization: Bearer " + "x" * 40)
        writer.write(("\r\n".join(headers) + "\r\n\r\n").encode("ascii"))
        await writer.drain()
        raw = await asyncio.wait_for(reader.read(), 5)
        writer.close()
        await writer.wait_closed()
        head, body = raw.split(b"\r\n\r\n", 1)
        return int(head.split()[1]), body, head

    async def catalogue(self):
        status, body, headers = await self.request("/assets/avatar-models.json")
        self.assertEqual(status, 200)
        self.assertIn(b"Cache-Control: no-store", headers)
        self.assertNotIn(str(self.root).encode(), body)
        return json.loads(body)

    async def assert_only_classic(self):
        catalogue = await self.catalogue()
        self.assertEqual(catalogue["version"], 1)
        self.assertEqual(catalogue["defaultId"], "classic")
        self.assertTrue(catalogue["models"][0]["available"])
        self.assertFalse(catalogue["models"][1]["available"])
        self.assertIsNone(catalogue["models"][1]["manifestUrl"])
        status, data, _ = await self.request("/model/Jade.moc3")
        self.assertEqual((status, data), (200, b"MOC3classic"))

    async def test_default_catalogue_never_probes_unconfigured_model(self):
        with patch.object(self.gateway, "_second_model_files", side_effect=AssertionError("must not scan")):
            catalogue = await self.catalogue()
        self.assertEqual(catalogue, {"version": 1, "defaultId": "classic", "models": [
            {"id": "classic", "label": "Modèle actuel", "available": True,
             "manifestUrl": "/model/Jade.model3.json", "presentation": "seated",
             "classicIntents": True, "idleMotion": "Idle"},
            {"id": "next", "label": "Nouveau modèle", "available": False,
             "manifestUrl": None, "presentation": "full",
             "classicIntents": False, "idleMotion": None}]})

    async def test_catalogue_and_both_models_keep_existing_owner_boundary(self):
        next_dir = self.root / "next"
        bundle(next_dir)
        self.gateway.second_model_dir = next_dir
        for path in ("/assets/avatar-models.json", "/model/Jade.model3.json",
                     "/models/next/Jade.model3.json", "/models/next/Jade.moc3"):
            for owner in (None, "stranger@example.test"):
                with self.subTest(path=path, owner=owner):
                    status, _, _ = await self.request(path, owner=owner, bearer=True)
                    self.assertEqual(status, 403)
            # Static model assets retain the same Tailscale owner-only boundary.
            status, _, _ = await self.request(path)
            self.assertEqual(status, 200)

    async def test_missing_or_partial_bundle_preserves_classic(self):
        self.gateway.second_model_dir = self.root / "missing"
        await self.assert_only_classic()
        next_dir = self.root / "partial"
        next_dir.mkdir()
        self.gateway.second_model_dir = next_dir
        await self.assert_only_classic()
        write_manifest(next_dir, {"Version": 3, "FileReferences": {
            "Moc": "Jade.moc3", "Textures": ["texture.png"]}})
        await self.assert_only_classic()
        status, _, _ = await self.request("/models/next/Jade.model3.json")
        self.assertEqual(status, 503)

    async def test_valid_bundle_routes_are_isolated_and_no_legacy_idle_is_injected(self):
        next_dir = self.root / "next"
        original = bundle(next_dir)
        self.gateway.second_model_dir = next_dir
        (next_dir / "Jade_idle.motion3.json").write_text("{}", encoding="utf-8")
        (next_dir / "private.txt").write_text("private", encoding="utf-8")
        catalogue = await self.catalogue()
        second = catalogue["models"][1]
        self.assertTrue(second["available"])
        self.assertEqual(second["manifestUrl"], "/models/next/Jade.model3.json")
        self.assertEqual(second["presentation"], "full")
        self.assertFalse(second["classicIntents"])
        self.assertIsNone(second["idleMotion"])
        status, model, _ = await self.request(second["manifestUrl"])
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(model), original)
        for prefix, expected in (("/model/", b"MOC3classic"), ("/models/next/", b"MOC3next")):
            status, data, _ = await self.request(prefix + "Jade.moc3")
            self.assertEqual((status, data), (200, expected))
        for name in ("private.txt", "Jade_idle.motion3.json", "../classic/Jade.moc3"):
            status, _, _ = await self.request("/models/next/" + name)
            self.assertEqual(status, 404)
        status, _, _ = await self.request("/models/unknown/Jade.model3.json")
        self.assertEqual(status, 404)
        status, _, _ = await self.request("/models/next/%2e%2e/classic/Jade.moc3")
        self.assertEqual(status, 400)

    async def test_referenced_optional_assets_are_whitelisted_only_in_their_bundle(self):
        next_dir = self.root / "next"
        original = bundle(next_dir)
        original["FileReferences"].update({
            "Physics": "physics.json", "Expressions": [{"Name": "Smile", "File": "smile.exp3.json"}],
            "Motions": {"Wave": [{"File": "wave.motion3.json"}]}})
        for name in ("physics.json", "smile.exp3.json", "wave.motion3.json"):
            (next_dir / name).write_text("{}", encoding="utf-8")
        write_manifest(next_dir, original)
        self.gateway.second_model_dir = next_dir
        self.assertTrue((await self.catalogue())["models"][1]["available"])
        for name in ("physics.json", "smile.exp3.json", "wave.motion3.json"):
            status, data, _ = await self.request("/models/next/" + name)
            self.assertEqual((status, data), (200, b"{}"))
            status, _, _ = await self.request("/model/" + name)
            self.assertEqual(status, 404)

    async def test_invalid_references_do_not_escape_the_slot(self):
        next_dir = self.root / "next"
        original = bundle(next_dir)
        self.gateway.second_model_dir = next_dir
        for invalid in ("../classic/Jade.moc3", "/Jade.moc3", "https://example.test/Jade.moc3",
                        "textures/../Jade.moc3", "textures//Jade.moc3", "private.txt", 42):
            with self.subTest(reference=invalid):
                model = json.loads(json.dumps(original))
                model["FileReferences"]["Moc"] = invalid
                write_manifest(next_dir, model)
                await self.assert_only_classic()
                status, _, _ = await self.request("/models/next/Jade.model3.json")
                self.assertEqual(status, 503)

    async def test_lfs_placeholders_empty_files_and_malformed_json_are_unavailable(self):
        next_dir = self.root / "next"
        original = bundle(next_dir)
        self.gateway.second_model_dir = next_dir
        for data in (b"", b"not a moc3", b"version https://git-lfs.github.com/spec/v1\noid sha256:fixture\n"):
            with self.subTest(asset=data[:7]):
                (next_dir / "Jade.moc3").write_bytes(data)
                await self.assert_only_classic()
        (next_dir / "Jade.moc3").write_bytes(b"MOC3next")
        texture = next_dir / "textures/texture.png"
        original_texture = texture.read_bytes()
        texture.write_bytes(b"not a PNG")
        await self.assert_only_classic()
        texture.write_bytes(original_texture)
        for model in ({}, {"Version": 3, "FileReferences": []},
                      {"Version": 3, "FileReferences": {"Moc": "Jade.moc3", "Textures": []}},
                      {"Version": 3, "FileReferences": {
                          "Moc": "Jade.moc3", "Textures": ["textures/texture.png"] * 65}},
                      {"Version": 3, "FileReferences": {**original["FileReferences"], "Motions": []}}):
            with self.subTest(model=model):
                write_manifest(next_dir, model)
                await self.assert_only_classic()
        (next_dir / "Jade.model3.json").write_text("not JSON", encoding="utf-8")
        await self.assert_only_classic()

    async def test_symlink_manifest_directory_and_asset_are_unavailable(self):
        next_dir = self.root / "next"
        bundle(next_dir)
        self.gateway.second_model_dir = next_dir
        original_manifest = next_dir / "Jade.model3.json"
        outside_manifest = self.root / "manifest.json"
        original_manifest.replace(outside_manifest)
        try:
            original_manifest.symlink_to(outside_manifest)
        except OSError:
            self.skipTest("symlink creation is unavailable on this platform")
        await self.assert_only_classic()
        original_manifest.unlink()
        outside_manifest.replace(original_manifest)
        texture = next_dir / "textures/texture.png"
        outside_texture = self.root / "texture.png"
        texture.replace(outside_texture)
        texture.symlink_to(outside_texture)
        await self.assert_only_classic()
        texture.unlink()
        outside_texture.replace(texture)
        texture_dir = next_dir / "textures"
        real_textures = next_dir / "real-textures"
        texture_dir.rename(real_textures)
        texture_dir.symlink_to(real_textures, target_is_directory=True)
        await self.assert_only_classic()
        texture_dir.unlink()
        real_textures.rename(texture_dir)
        alias = self.root / "linked-next"
        alias.symlink_to(next_dir, target_is_directory=True)
        self.gateway.second_model_dir = alias
        await self.assert_only_classic()

    async def test_bundle_disappearing_after_catalogue_does_not_break_classic(self):
        next_dir = self.root / "next"
        bundle(next_dir)
        self.gateway.second_model_dir = next_dir
        self.assertTrue((await self.catalogue())["models"][1]["available"])
        (next_dir / "textures/texture.png").unlink()
        status, _, _ = await self.request("/models/next/Jade.model3.json")
        self.assertEqual(status, 503)
        await self.assert_only_classic()


if __name__ == "__main__":
    unittest.main()
