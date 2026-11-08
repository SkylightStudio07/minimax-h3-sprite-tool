"""Expression authoring regressions, using isolated jobs and the real PSD writer."""
import base64
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from PIL import Image
import rigging_editor as editor
import rigging_v2


class ExpressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / 'job'
        self.folder.mkdir()
        self.manifest = {'canvas': {'width': 96, 'height': 96}, 'parts': [], 'expressions': [
            {'id': 'mouth_close', 'runtimeName': 'mouth_close', 'file': 'expressions/mouth.png',
             'left': 40, 'top': 40, 'width': 8, 'height': 8}], 'sourceMouthState': 'closed'}
        image = Image.new('RGBA', (8, 8), (180, 50, 50, 255))
        output = io.BytesIO(); image.save(output, 'PNG')
        (self.folder / 'manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')
        (self.folder / 'character.psd').write_bytes(b'original')
        Image.new('RGBA', (96, 96)).save(self.folder / 'composite.png')
        with zipfile.ZipFile(self.folder / 'character-unity-parts.zip', 'w') as archive:
            archive.writestr('expressions/mouth.png', output.getvalue())
        self.writer = Path(__file__).parent / 'tools/write_psd.js'

    def create(self, copy=False, id='variant_smile'):
        return {'kind': 'variant_create', 'id': id, 'targetKey': 'expression:mouth_close', 'name': '웃는 입', 'copy': copy}

    def paint(self):
        return {'kind': 'paint', 'layerKey': 'expression:variant_smile', 'color': '#234567', 'size': 4,
                'points': [{'x': 44, 'y': 44, 'p': .5}, {'x': 47, 'y': 44, 'p': .5}]}

    def apply(self):
        return {'kind': 'variant_apply', 'layerKey': 'expression:variant_smile'}

    def save(self, operations, revision=0):
        return editor.save_revision(self.folder, operations, revision, self.writer)

    def test_draw_apply_preserves_source_and_reloads_variant(self):
        result = self.save([self.create(), self.paint(), self.apply()])
        records = dict(editor.layer_records(result['manifest']))
        slot = records['expression:mouth_close']
        self.assertEqual(slot['activeVariant'], 'variant_smile')
        self.assertEqual(slot['left'], 16)
        with zipfile.ZipFile(self.folder / 'character-unity-parts.zip') as archive:
            self.assertEqual(archive.read(slot['file']), archive.read(records['expression:variant_smile']['file']))
            current = Image.open(io.BytesIO(archive.read(slot['file']))).convert('RGBA')
            self.assertEqual(current.getpixel((28, 28)), (35, 69, 103, 255))
            self.assertIn('variantOf', archive.read('Unity/Editor/RiggingV1Importer.cs').decode())
        original = Image.open(io.BytesIO(editor.layer_bytes(self.folder, 'mouth_close', True, 'expression'))).convert('RGBA')
        self.assertEqual(original.getpixel((28, 28)), (180, 50, 50, 255))
        composite = Image.open(self.folder / 'composite.png').convert('RGBA')
        self.assertEqual(composite.getpixel((44, 44)), (35, 69, 103, 255))
        # Switching back to a retained copy uses the same slot and remains reversible.
        self.save([self.create(True, 'variant_copy')], 1)
        self.save([{'kind': 'variant_apply', 'layerKey': 'expression:variant_copy'}], 2)
        self.assertEqual(editor.read_manifest(self.folder)['expressions'][0]['activeVariant'], 'variant_copy')
        rigging_v2.build_package(self.folder, Path(__file__).parent / 'unity-v2', 3)
        with zipfile.ZipFile(self.folder / rigging_v2.V2_FILENAME) as archive:
            self.assertIn('expressions/variant_smile.png', archive.namelist())
            self.assertIn('variantOf', archive.read('UnityV2/Editor/RiggingV2Importer.cs').decode())

    def test_png_alignment_and_hidden_archive(self):
        image = Image.new('RGBA', (96, 96)); image.putpixel((45, 45), (1, 2, 3, 255))
        buffer = io.BytesIO(); image.save(buffer, 'PNG')
        data = 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode()
        operations = [self.create(), {'kind': 'variant_png', 'layerKey': 'expression:variant_smile', 'imageData': data}]
        self.save(operations)
        # Stored variants never enter the gallery composite before Apply.
        composite = Image.open(self.folder / 'composite.png').convert('RGBA')
        self.assertEqual(composite.getpixel((45, 45)), (180, 50, 50, 255))
        self.save([self.apply()], 1)
        composite = Image.open(self.folder / 'composite.png').convert('RGBA')
        self.assertEqual(composite.getpixel((45, 45)), (1, 2, 3, 255))
        self.assertEqual(composite.getpixel((44, 44))[3], 0)

    def test_invalid_operations_and_empty_apply_preserve_job(self):
        before = (self.folder / 'manifest.json').read_bytes()
        with self.assertRaisesRegex(ValueError, '비어'):
            self.save([self.create(), self.apply()])
        self.assertEqual((self.folder / 'manifest.json').read_bytes(), before)
        for operation in [self.create() | {'id': '../bad'}, self.paint() | {'layerKey': 'expression:mouth_close'},
                          self.create() | {'targetKey': 'expression:missing'}]:
            with self.assertRaises(ValueError):
                editor.validate_operations(self.manifest, [operation])
        with self.assertRaises(ValueError):
            editor.validate_operations(self.manifest, [self.create(), self.paint() | {'color': 'red'}])

    def test_psd_keeps_animation_slot_but_hides_variant_archive(self):
        self.save([self.create(), self.paint(), self.apply()])
        manifest = editor.read_manifest(self.folder)
        manifest['layerVisibility'] = {'expression:mouth_close': False, 'expression:variant_smile': True}
        with tempfile.TemporaryDirectory() as name:
            extracted = Path(name)
            with zipfile.ZipFile(self.folder / 'character-unity-parts.zip') as archive:
                editor._safe_extract(archive, extracted)
            captured = []
            def writer(args, **kwargs):
                payload = json.loads(Path(args[2]).read_text(encoding='utf-8'))
                captured.extend(payload['layers'])
                return type('Result', (), {'returncode': 0})()
            with patch.object(editor.subprocess, 'run', side_effect=writer):
                editor._write_psd(extracted, manifest, Image.new('RGBA', (96, 96)), self.writer, 'node')
            self.assertFalse(captured[0]['hidden'])
            self.assertTrue(captured[1]['hidden'])

    def test_copy_erase_restore_before_first_save(self):
        erase = self.paint() | {'kind': 'erase'}
        restore = self.paint() | {'kind': 'restore'}
        self.save([self.create(True), erase, restore, self.apply()])
        with zipfile.ZipFile(self.folder / 'character-unity-parts.zip') as archive:
            image = Image.open(io.BytesIO(archive.read('expressions/mouth.png'))).convert('RGBA')
            self.assertEqual(image.getpixel((28, 28)), (180, 50, 50, 255))


if __name__ == '__main__':
    unittest.main()
