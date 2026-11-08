"""Persistent rest rig and shared skinning contract regressions."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from PIL import Image
import rigging_bones as bones
import rigging_editor as editor
import rigging_v2
import rigging_upscale


class BoneTests(unittest.TestCase):
    def manifest(self):
        return {'canvas':{'width':256,'height':384},'parts':[
            {'id':'body','runtimeName':'body','file':'layers/body.png','left':20,'top':10,'width':210,'height':360},
            {'id':'hair','runtimeName':'hair','file':'layers/hair.png','left':80,'top':20,'width':100,'height':120}],
            'expressions':[], 'anchors':{}}

    def test_default_hair_controls_and_normalized_weights(self):
        manifest=self.manifest();rig=bones.get_rig(manifest)
        self.assertEqual(len(rig['bones']),19)
        self.assertEqual(rig['bindings']['part:hair'],['head','hair_hair','hair_tip_hair'])
        for mesh in bones.layer_meshes(manifest,rig):
            self.assertEqual(len(mesh['vertices']),81)
            self.assertEqual(len(mesh['indices']),384)
            for vertex in mesh['vertices']:
                self.assertAlmostEqual(sum(vertex['weights']),1)
                self.assertTrue(all(0<=i<len(rig['bones']) for i in vertex['boneIndices']))

    def test_reject_cycles_missing_core_unknown_layer_and_nonfinite(self):
        manifest=self.manifest();rig=bones.get_rig(manifest)
        for mutate in [lambda r:r['bones'][0].update(parent='head'),lambda r:r['bones'][1].update(parent='head'),
                       lambda r:r['bones'][0].update(x=float('nan')),lambda r:r['bindings'].update({'part:missing':['head']}),
                       lambda r:r['bones'].pop(4)]:
            bad=copy.deepcopy(rig);mutate(bad)
            with self.assertRaises(ValueError):bones.validate(bad,manifest)

    def fixture(self,folder):
        manifest=self.manifest();folder.mkdir()
        (folder/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
        (folder/'character.psd').write_bytes(b'original')
        Image.new('RGBA',(256,384),(10,20,30,255)).save(folder/'composite.png')
        with zipfile.ZipFile(folder/'character-unity-parts.zip','w') as archive:
            archive.writestr('manifest.json',json.dumps(manifest))
            for part in manifest['parts']:
                out=io.BytesIO();Image.new('RGBA',(part['width'],part['height']),(40,50,60,255)).save(out,'PNG')
                archive.writestr(part['file'],out.getvalue())
        return manifest

    def test_save_version_v2_weights_and_upscale_preserve_authoring(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name)/'job';manifest=self.fixture(folder);rig=bones.get_rig(manifest)
            next(b for b in rig['bones'] if b['name']=='head')['x']=150
            rig['bindings']['part:body']=['chest']
            result=editor.save_revision(folder,[{'kind':'rig_config','config':rig}],0,Path(__file__).parent/'tools/write_psd.js')
            self.assertEqual(result['revision'],1)
            self.assertNotIn('rigEditor',json.loads((folder/'revisions/0000/manifest.json').read_text()))
            updated=bones.get_rig(editor.read_manifest(folder),folder)
            self.assertEqual(next(b for b in updated['bones'] if b['name']=='head')['x'],150)
            built=rigging_v2.build_package(folder,Path(__file__).parent/'unity-v2',1)
            with zipfile.ZipFile(built['path']) as archive:
                exported=json.loads(archive.read('rig-v2.json'))
            self.assertEqual(exported['bones'],updated['bones'])
            self.assertEqual(exported['layerMeshes'],bones.layer_meshes(editor.read_manifest(folder),updated))
            self.assertEqual(exported['poseSource'],'editor')
            content=rigging_upscale.export_layers(folder,2,Path(__file__).parent/'tools/write_psd.js')
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                enlarged=json.loads(archive.read('manifest.json'))
            self.assertEqual(next(b for b in enlarged['rigEditor']['bones'] if b['name']=='head')['x'],300)
            editor.restore_version(folder,0,1)
            self.assertNotIn('rigEditor',editor.read_manifest(folder))

    def test_layer_reconciliation_keeps_edited_bones(self):
        manifest=self.manifest();config=bones.get_rig(manifest)
        manifest['rigEditor']=config
        manifest['parts'].pop()
        manifest['parts'].append({'id':'new_coat','runtimeName':'topwear','file':'layers/coat.png','left':0,'top':0,'width':200,'height':200})
        rig=bones.get_rig(manifest)
        self.assertNotIn('part:hair',rig['bindings'])
        self.assertIn('part:new_coat',rig['bindings'])
        self.assertEqual(rig['bones'],config['bones'])


if __name__=='__main__':unittest.main()
