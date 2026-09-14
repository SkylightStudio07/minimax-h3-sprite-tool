import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from PIL import Image, ImageChops

import rigging_showcase


class ShowcaseTests(unittest.TestCase):
    def test_builds_flattened_animated_webp(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            manifest = {
                "canvas": {"width": 96, "height": 96},
                "parts": [
                    {"id": "back_hair", "file": "layers/back.png", "left": 26, "top": 6},
                    {"id": "face", "file": "layers/face.png", "left": 32, "top": 20},
                    {"id": "eyewhite_1", "file": "layers/eye.png", "left": 40, "top": 38},
                    {"id": "irides_1", "file": "layers/iris.png", "left": 43, "top": 39},
                    {"id": "eyelash_1", "file": "layers/lash.png", "left": 39, "top": 37},
                    {"id": "mouth_open", "file": "layers/mouth.png", "left": 44, "top": 52},
                    {"id": "front_hair", "file": "layers/front.png", "left": 30, "top": 8},
                ],
                "expressions": [
                    {"id": "eye_close", "file": "expressions/eye_close.png", "left": 39, "top": 40},
                    {"id": "mouth_close", "file": "expressions/mouth_close.png", "left": 43, "top": 53},
                ],
            }
            (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            def png(size, color):
                import io
                data = io.BytesIO(); Image.new("RGBA", size, color).save(data, format="PNG")
                return data.getvalue()
            with zipfile.ZipFile(folder / "character-unity-parts.zip", "w") as archive:
                for record in [*manifest["parts"], *manifest["expressions"]]:
                    archive.writestr(record["file"], png((28, 40) if "hair" in record["id"] else (12, 8), (180, 90, 220, 220)))
            result = rigging_showcase.build_showcase(folder, max_size=96, frame_count=12, duration_ms=60)
            self.assertEqual(result["frames"], 12)
            with Image.open(result["path"]) as animated:
                self.assertEqual(animated.format, "WEBP")
                self.assertEqual(animated.n_frames, 12)
                animated.seek(0); first = animated.convert("RGBA")
                animated.seek(4); later = animated.convert("RGBA")
                self.assertIsNotNone(ImageChops.difference(first, later).getbbox())


if __name__ == "__main__":
    unittest.main()
