import io
import json
import base64
from pathlib import Path
import tempfile
import unittest
import zipfile

from PIL import Image, ImageDraw

import rigging_editor as editor


class RiggingEditorTests(unittest.TestCase):
    def operation(self, layer="headwear"):
        return {"kind": "erase", "layerId": layer, "size": 8, "points": [{"x": 25, "y": 25, "p": 0.5}]}

    def test_erase_changes_alpha_but_preserves_rgb(self):
        image = Image.new("RGBA", (30, 30), (70, 80, 90, 255))
        changed = editor.erase_stroke(image, self.operation(), 10, 10)
        self.assertEqual(changed.getpixel((15, 15)), (70, 80, 90, 0))
        self.assertEqual(changed.getpixel((0, 0)), (70, 80, 90, 255))

    def test_restore_copies_original_pixels_inside_brush(self):
        current = Image.new("RGBA", (30, 30), (0, 0, 0, 0))
        original = Image.new("RGBA", (30, 30), (70, 80, 90, 255))
        operation = self.operation() | {"kind": "restore"}
        changed = editor.restore_stroke(current, original, operation, 10, 10)
        self.assertEqual(changed.getpixel((15, 15)), (70, 80, 90, 255))
        self.assertEqual(changed.getpixel((0, 0)), (0, 0, 0, 0))

    def test_validation_rejects_unknown_layer(self):
        manifest = {"canvas": {"width": 64, "height": 64}, "parts": [{"id": "headwear"}]}
        with self.assertRaisesRegex(ValueError, "레이어"):
            editor.validate_operations(manifest, [self.operation("missing")])

    def test_save_rebuilds_psd_zip_composite_and_backup(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name) / "job"
            source = Path(name) / "source"
            (source / "layers").mkdir(parents=True)
            face = Image.new("RGBA", (30, 30), (240, 170, 160, 255))
            headwear = Image.new("RGBA", (50, 40), (60, 65, 75, 255))
            face.save(source / "layers" / "face.png")
            headwear.save(source / "layers" / "headwear.png")
            manifest = {
                "schemaVersion": 1, "status": "ready",
                "canvas": {"width": 64, "height": 64, "origin": "top-left"},
                "parts": [
                    {"id": "face", "runtimeName": "face", "sourceLayerName": "face", "file": "layers/face.png", "left": 10, "top": 10, "width": 30, "height": 30},
                    {"id": "headwear", "runtimeName": "headwear", "sourceLayerName": "headwear", "file": "layers/headwear.png", "left": 5, "top": 5, "width": 50, "height": 40},
                ],
                "expressions": [], "anchors": {}, "warnings": [], "synthetic": {"eye": False, "mouth": False},
            }
            (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (source / "character.psd").write_bytes(b"original-psd")
            Image.new("RGBA", (64, 64)).save(source / "composite.png")
            folder.mkdir()
            for filename in ("manifest.json", "character.psd", "composite.png"):
                (folder / filename).write_bytes((source / filename).read_bytes())
            with zipfile.ZipFile(folder / "character-unity-parts.zip", "w") as archive:
                for item in source.rglob("*"):
                    if item.is_file():
                        archive.write(item, item.relative_to(source).as_posix())

            saved = editor.save_revision(
                folder, [self.operation()], 0,
                Path(__file__).parent / "tools" / "write_psd.js",
            )
            self.assertEqual(saved["revision"], 1)
            self.assertEqual((folder / "revisions" / "0000" / "character.psd").read_bytes(), b"original-psd")
            self.assertEqual((folder / "character.psd").read_bytes()[:4], b"8BPS")
            current = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual((current["editRevision"], current["editedParts"]), (1, ["headwear"]))
            with zipfile.ZipFile(folder / "character-unity-parts.zip") as archive:
                edited = Image.open(io.BytesIO(archive.read("layers/headwear.png"))).convert("RGBA")
                self.assertEqual(edited.getpixel((20, 20))[3], 0)
                self.assertEqual(archive.read("character.psd")[:4], b"8BPS")
            composite = Image.open(folder / "composite.png").convert("RGBA")
            self.assertEqual(composite.getpixel((25, 25))[:3], (240, 170, 160))

            restore = self.operation() | {"kind": "restore"}
            saved = editor.save_revision(
                folder, [restore], 1,
                Path(__file__).parent / "tools" / "write_psd.js",
            )
            self.assertEqual(saved["revision"], 2)
            with zipfile.ZipFile(folder / "character-unity-parts.zip") as archive:
                restored = Image.open(io.BytesIO(archive.read("layers/headwear.png"))).convert("RGBA")
                self.assertEqual(restored.getpixel((20, 20)), (60, 65, 75, 255))
            original_bytes = editor.layer_bytes(folder, "headwear", original=True)
            self.assertEqual(Image.open(io.BytesIO(original_bytes)).convert("RGBA").getpixel((20, 20)), (60, 65, 75, 255))

            versions = editor.list_versions(folder, 2)
            self.assertEqual([item["revision"] for item in versions], [0, 1, 2])
            self.assertEqual(versions[0]["label"], "작업 버전 v1")
            self.assertEqual(editor.version_file(folder, 1, 2, "character.psd").read_bytes()[:4], b"8BPS")
            restored_version = editor.restore_version(folder, 0, 2)
            self.assertEqual((restored_version["revision"], restored_version["targetRevision"]), (3, 0))
            self.assertEqual((folder / "character.psd").read_bytes(), b"original-psd")
            self.assertTrue((folder / "revisions" / "0002" / "character.psd").is_file())
            self.assertEqual(json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["editRevision"], 3)
            with zipfile.ZipFile(folder / "character-unity-parts.zip") as archive:
                self.assertEqual(json.loads(archive.read("manifest.json"))["editRevision"], 3)

            reordered = editor.save_revision(
                folder, [], 3, Path(__file__).parent / "tools" / "write_psd.js",
                layer_order=["part:headwear", "part:face"],
            )
            self.assertEqual(reordered["manifest"]["layerOrder"], ["part:headwear", "part:face"])
            self.assertEqual(Image.open(folder / "composite.png").convert("RGBA").getpixel((25, 25))[:3], (240, 170, 160))

    def test_layer_order_rejects_missing_and_duplicate_layers(self):
        manifest = {"parts": [{"id": "face"}], "expressions": [{"id": "eyebrow"}]}
        self.assertEqual(editor.effective_layer_order(manifest), ["part:face", "expression:eyebrow"])
        with self.assertRaisesRegex(ValueError, "빠졌거나 중복"):
            editor.validate_layer_order(manifest, ["part:face", "part:face"])

    def test_source_restore_creates_real_layer_and_rebuilds_package(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name) / "job"; package = Path(name) / "package"
            (package / "layers").mkdir(parents=True); folder.mkdir()
            manifest = {"schemaVersion": 1, "status": "ready", "canvas": {"width": 64, "height": 64},
                        "parts": [{"id": "face", "runtimeName": "face", "sourceLayerName": "face",
                                   "file": "layers/face.png", "left": 16, "top": 12, "width": 32, "height": 36}],
                        "expressions": [], "anchors": {}, "warnings": [], "sourceReference": editor.SOURCE_REFERENCE,
                        "layerOrder": ["part:face"]}
            Image.new("RGBA", (32, 36), (220, 170, 160, 255)).save(package / "layers" / "face.png")
            (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (package / "character.psd").write_bytes(b"old")
            Image.new("RGBA", (64, 64)).save(package / "composite.png")
            for filename in ("manifest.json", "character.psd", "composite.png"):
                (folder / filename).write_bytes((package / filename).read_bytes())
            with zipfile.ZipFile(folder / "character-unity-parts.zip", "w") as archive:
                for item in package.rglob("*"):
                    if item.is_file(): archive.write(item, item.relative_to(package).as_posix())
            source = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            ImageDraw.Draw(source).rectangle((4, 4, 24, 20), fill=(180, 20, 35, 255))
            source.save(folder / editor.SOURCE_REFERENCE)
            operation = {"kind": "source_restore", "recoveryType": "hood", "size": 12,
                         "points": [{"x": 12, "y": 12, "p": .5}]}
            saved = editor.save_revision(folder, [operation], 0,
                                         Path(__file__).parent / "tools" / "write_psd.js",
                                         layer_order=["part:face", "part:source_headwear_hood"])
            self.assertEqual(saved["revision"], 1)
            recovery = next(item for item in saved["manifest"]["parts"] if item["id"] == "source_headwear_hood")
            self.assertLess(recovery["width"], 64)
            with zipfile.ZipFile(folder / "character-unity-parts.zip") as archive:
                restored = Image.open(io.BytesIO(archive.read("layers/source_headwear_hood.png"))).convert("RGBA")
                self.assertEqual(restored.getpixel((12-recovery["left"], 12-recovery["top"])), (180, 20, 35, 255))
                self.assertNotIn(editor.SOURCE_REFERENCE, archive.namelist())
            self.assertEqual(Image.open(folder / "composite.png").convert("RGBA").getpixel((12, 12)), (180, 20, 35, 255))

            second = {"kind": "source_restore", "recoveryType": "hood", "size": 8,
                      "points": [{"x": 30, "y": 10, "p": .5}]}
            saved = editor.save_revision(folder, [second], 1,
                                         Path(__file__).parent / "tools" / "write_psd.js",
                                         layer_order=["part:face", "part:source_headwear_hood"])
            self.assertEqual(saved["revision"], 2)
            recovery = next(item for item in saved["manifest"]["parts"] if item["id"] == "source_headwear_hood")
            with zipfile.ZipFile(folder / "character-unity-parts.zip") as archive:
                restored = Image.open(io.BytesIO(archive.read(recovery["file"]))).convert("RGBA")
                self.assertEqual(restored.getpixel((12-recovery["left"], 12-recovery["top"])), (180, 20, 35, 255))

            merged = editor.save_revision(
                folder,
                [{"kind": "merge", "sourceLayerKey": "part:source_headwear_hood",
                  "targetLayerKey": "part:face"}],
                2, Path(__file__).parent / "tools" / "write_psd.js",
                layer_order=["part:face"],
            )
            self.assertEqual(merged["revision"], 3)
            self.assertEqual([part["id"] for part in merged["manifest"]["parts"]], ["face"])
            self.assertEqual(merged["manifest"]["layerOrder"], ["part:face"])
            face = merged["manifest"]["parts"][0]
            with zipfile.ZipFile(folder / "character-unity-parts.zip") as archive:
                self.assertNotIn("layers/source_headwear_hood.png", archive.namelist())
                image = Image.open(io.BytesIO(archive.read(face["file"]))).convert("RGBA")
                self.assertEqual(image.getpixel((12-face["left"], 12-face["top"])), (180, 20, 35, 255))

            restored_original = editor.save_revision(
                folder,
                [{"kind": "restore", "layerKey": "part:face", "size": 8,
                  "points": [{"x": 20, "y": 20, "p": .5}]}],
                3, Path(__file__).parent / "tools" / "write_psd.js",
                layer_order=["part:face"],
            )
            face = restored_original["manifest"]["parts"][0]
            with zipfile.ZipFile(folder / "character-unity-parts.zip") as archive:
                image = Image.open(io.BytesIO(archive.read(face["file"]))).convert("RGBA")
                self.assertEqual(image.getpixel((20-face["left"], 20-face["top"])), (220, 170, 160, 255))

    def test_merge_rejects_regular_source_layer(self):
        manifest = {"canvas": {"width": 64, "height": 64},
                    "parts": [{"id": "face"}, {"id": "headwear"}], "expressions": []}
        with self.assertRaisesRegex(ValueError, "원본에서 복원"):
            editor.validate_operations(manifest, [{"kind": "merge", "sourceLayerKey": "part:headwear",
                                                   "targetLayerKey": "part:face"}])

    def test_existing_job_can_attach_fitted_source_reference(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            (folder / "manifest.json").write_text(json.dumps({"canvas": {"width": 40, "height": 40}}), encoding="utf-8")
            source = Image.new("RGBA", (20, 10), (12, 34, 56, 255)); raw = io.BytesIO(); source.save(raw, "PNG")
            data = "data:image/png;base64," + base64.b64encode(raw.getvalue()).decode()
            target = editor.save_source_reference(folder, data)
            fitted = Image.open(target).convert("RGBA")
            self.assertEqual(fitted.size, (40, 40))
            self.assertEqual(fitted.getpixel((20, 20)), (12, 34, 56, 255))
            self.assertEqual(fitted.getpixel((20, 2))[3], 0)
            self.assertEqual(editor.read_manifest(folder)["sourceReference"], editor.SOURCE_REFERENCE)


if __name__ == "__main__":
    unittest.main()
