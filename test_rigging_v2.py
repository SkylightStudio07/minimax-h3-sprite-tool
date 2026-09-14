import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from PIL import Image, ImageDraw

import rigging_v2


class RiggingV2Tests(unittest.TestCase):
    def manifest(self):
        return {
            "schemaVersion": 1,
            "canvas": {"width": 256, "height": 384, "origin": "top-left"},
            "anchors": {"face": {"cx": 132, "cy": 68}, "neckPivot": {"cx": 128, "cy": 116}},
            "parts": [{"id": "body", "runtimeName": "body", "file": "layers/body.png", "left": 40, "top": 20, "width": 170, "height": 350}],
            "expressions": [],
        }

    def test_skeleton_has_parent_first_humanoid_hierarchy(self):
        rig = rigging_v2.build_skeleton(self.manifest(), (40, 20, 210, 370))
        self.assertEqual(len(rig["bones"]), 17)
        by_name = {bone["name"]: index for index, bone in enumerate(rig["bones"])}
        self.assertEqual(rig["bones"][0]["name"], "hips")
        for index, bone in enumerate(rig["bones"]):
            if bone["parent"]:
                self.assertLess(by_name[bone["parent"]], index)
        self.assertLess(rig["bones"][by_name["head"]]["y"], rig["bones"][by_name["hips"]]["y"])
        self.assertLess(rig["bones"][by_name["shoulder_l"]]["x"], rig["bones"][by_name["shoulder_r"]]["x"])

    def test_package_contains_v2_contract_and_unity_scripts(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            folder = root / "result"
            folder.mkdir()
            manifest = self.manifest()
            (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            composite = Image.new("RGBA", (256, 384))
            ImageDraw.Draw(composite).rectangle((40, 20, 210, 370), fill="white")
            composite.save(folder / "composite.png")
            with zipfile.ZipFile(folder / "character-unity-parts.zip", "w") as archive:
                archive.writestr("manifest.json", json.dumps(manifest))
                archive.writestr("layers/body.png", b"png")
                archive.writestr("Unity/Runtime/RiggingV1Avatar.cs", "class V1 {}")
            unity = root / "unity-v2"
            (unity / "Editor").mkdir(parents=True)
            (unity / "Runtime").mkdir(parents=True)
            (unity / "Editor" / "RiggingV2Importer.cs").write_text("class Importer {}", encoding="utf-8")
            (unity / "Runtime" / "RiggingV2Avatar.cs").write_text("class Avatar {}", encoding="utf-8")

            result = rigging_v2.build_package(folder, unity, 3)
            self.assertEqual((result["bones"], result["sourceRevision"]), (17, 3))
            with zipfile.ZipFile(result["path"]) as archive:
                self.assertIsNone(archive.testzip())
                names = set(archive.namelist())
                self.assertIn("rig-v2.json", names)
                self.assertIn("UnityV2/Editor/RiggingV2Importer.cs", names)
                rig = json.loads(archive.read("rig-v2.json"))
                self.assertEqual((rig["sourceRevision"], len(rig["bones"])), (3, 17))


if __name__ == "__main__":
    unittest.main()
