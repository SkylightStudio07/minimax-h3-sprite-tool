import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from PIL import Image

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


if __name__ == "__main__":
    unittest.main()
