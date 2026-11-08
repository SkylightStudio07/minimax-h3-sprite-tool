import io
import json
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from pathlib import Path
from PIL import Image
import rigging_upscale as upscale
import rigging_editor as editor
import rigging_v2


class UpscaleTests(unittest.TestCase):
    def test_transparent_edge_has_no_black_fringe(self):
        image = Image.new('RGBA', (8, 8))
        for x in range(3, 6):
            for y in range(3, 6):
                image.putpixel((x, y), (240, 120, 60, 255))
        for scale in (2, 4):
            result = upscale.resize_layer(image, scale)
            self.assertEqual(result.size, (8 * scale, 8 * scale))
            for red, green, blue, alpha in result.getdata():
                if alpha > 30:
                    self.assertGreater(red, 220)

    def test_ai_export_preserves_alpha_coordinates_expressions_and_source(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name)
            layer=Image.new('RGBA',(8,8),(200,80,50,0));layer.paste((200,80,50,255),(2,2,6,6))
            raw=io.BytesIO();layer.save(raw,format='PNG')
            records=[dict(id='face',runtimeName='face',file='layers/face.png',left=2,top=3,width=8,height=8),dict(id='mouth_close',runtimeName='mouth',file='expressions/mouth.png',left=4,top=6,width=8,height=8)]
            manifest=dict(canvas=dict(width=32,height=32),parts=[records[0]],expressions=[records[1]],anchors=dict(face=dict(cx=4,cy=5)),editRevision=0)
            original=json.dumps(manifest).encode();(folder/'manifest.json').write_bytes(original)
            with zipfile.ZipFile(folder/'character-unity-parts.zip','w') as archive:
                for record in records:archive.writestr(record['file'],raw.getvalue())
            def batch(files,scale):
                self.assertEqual(len(files),2)
                for file in files:
                    with Image.open(file) as im:result=upscale.resize_layer(im,scale)
                    result.save(file)
            with patch.object(upscale.super_resolution,'status',return_value=dict(aiReady=True)),patch.object(upscale.super_resolution,'upscale_files',side_effect=batch):
                content=upscale.export_layers(folder,2,Path(__file__).parent/'tools/write_psd.js',method='anime-ai')
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                result=json.loads(archive.read('manifest.json'))
                self.assertIn('anime6b',result['upscaleExport']['method']);self.assertEqual(result['expressions'][0]['top'],12)
                for record in records:
                    with Image.open(io.BytesIO(archive.read(record['file']))) as im:
                        self.assertEqual(im.size,(16,16));self.assertEqual(im.getchannel('A').tobytes(),upscale.resize_layer(layer,2).getchannel('A').tobytes())
                self.assertEqual(archive.read('character.psd')[:4],b'8BPS')
            self.assertEqual((folder/'manifest.json').read_bytes(),original)
            with self.assertRaises(ValueError):upscale.export_layers(folder,2,Path('writer.js'),method='unknown')

    def test_export_keeps_working_files_and_scales_geometry(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name)
            image = io.BytesIO()
            Image.new('RGBA', (4, 5), (200, 100, 50, 255)).save(image, 'PNG')
            manifest = {'canvas': {'width': 32, 'height': 32},
                        'parts': [{'id': 'face', 'runtimeName': 'face', 'file': 'layers/face.png',
                                   'left': 3, 'top': 7, 'width': 4, 'height': 5}],
                        'expressions': [], 'anchors': {'face': {'cx': 5, 'cy': 9}, 'faceScale': .4},
                        'layerOrder': ['part:face'], 'editRevision': 3}
            original = json.dumps(manifest).encode()
            (folder / 'manifest.json').write_bytes(original)
            with zipfile.ZipFile(folder / 'character-unity-parts.zip', 'w') as archive:
                archive.writestr('layers/face.png', image.getvalue())
            before = (folder / 'character-unity-parts.zip').read_bytes()
            for scale in (2, 4):
                result = upscale.export_layers(folder, scale, Path(__file__).parent / 'tools/write_psd.js')
                with zipfile.ZipFile(io.BytesIO(result)) as archive:
                    enlarged = json.loads(archive.read('manifest.json'))
                    self.assertEqual(enlarged['parts'][0]['left'], 3 * scale)
                    self.assertEqual(enlarged['anchors']['face']['cx'], 5 * scale)
                    self.assertEqual(enlarged['anchors']['faceScale'], .4)
                    self.assertEqual(archive.read('character.psd')[:4], b'8BPS')
                    composite = Image.open(io.BytesIO(archive.read('composite.png')))
                    self.assertEqual(composite.size, (32 * scale, 32 * scale))
                    self.assertEqual(composite.getpixel((4 * scale, 8 * scale)), (200, 100, 50, 255))
            self.assertEqual((folder / 'manifest.json').read_bytes(), original)
            self.assertEqual((folder / 'character-unity-parts.zip').read_bytes(), before)
            with self.assertRaises(ValueError):
                upscale.export_layers(folder, True, Path('writer.js'))
            (folder / 'character.psd').write_bytes(b'original-psd')
            Image.new('RGBA',(32,32)).save(folder / 'composite.png')
            pose = {key: {'x': 8 + index, 'y': 10 + index} for index, key in enumerate(rigging_v2.POSE_KEYS)}
            rigging_v2.build_package(folder, Path(__file__).parent / 'unity-v2', 0, pose=pose)
            before_v2 = (folder / 'character-unity-skeleton.zip').read_bytes()
            with patch.object(rigging_v2, 'build_package', side_effect=RuntimeError('V2 failed')):
                with self.assertRaises(RuntimeError):
                    upscale.apply_layers(folder, 2, 0, Path(__file__).parent / 'tools/write_psd.js', Path(__file__).parent / 'unity-v2')
            self.assertEqual((folder / 'manifest.json').read_bytes(), original)
            self.assertEqual((folder / 'character-unity-skeleton.zip').read_bytes(), before_v2)
            # Existing revisions exist in a normal job. This fixture starts at v1.
            result = upscale.apply_layers(folder, 2, 0, Path(__file__).parent / 'tools/write_psd.js',
                                          Path(__file__).parent / 'unity-v2')
            self.assertEqual(result['revision'], 1)
            self.assertEqual(result['manifest']['unityPixelsPerUnit'], 200)
            self.assertGreater(result['bones'], 5)
            with zipfile.ZipFile(folder / 'character-unity-skeleton.zip') as archive:
                rig = json.loads(archive.read('rig-v2.json'))
                self.assertEqual(rig['sourceRevision'], 1)
                self.assertEqual(rig['poseSource'], 'user-points')
                hips = next(bone for bone in rig['bones'] if bone['name'] == 'hips')
                self.assertEqual(hips['x'], pose['hips']['x'] * 2)
                self.assertEqual(json.loads(archive.read('manifest.json'))['canvas']['width'], 64)
                self.assertIn('Unity/Editor/RiggingV1Importer.cs', archive.namelist())
                self.assertIn('UnityV2/Editor/RiggingV2Importer.cs', archive.namelist())
            original_layer = Image.open(io.BytesIO(editor.layer_bytes(folder, 'face', original=True)))
            self.assertEqual(original_layer.size, (8, 10))
            self.assertEqual(original_layer.getpixel((2,2)), (200,100,50,255))
            restored = editor.restore_version(folder, 0, 1)
            self.assertEqual(restored['manifest']['canvas']['width'], 32)
            self.assertEqual((folder / 'character.psd').read_bytes(), b'original-psd')
