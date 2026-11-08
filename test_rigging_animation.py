import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import rigging_animation as animation
import rigging_bones
import rigging_editor
import rigging_v2
import rigging_upscale
import test_rigging_bones as fixtures


class AnimationTests(unittest.TestCase):
    def config(self):
        return {'schemaVersion':1,'clips':[{'id':'clip_idle','name':'Idle','fps':24,'frames':48,'loop':True,'easing':'smooth','keys':[
            {'frame':0,'pose':{}},{'frame':24,'pose':{'head':{'dx':10,'dy':4,'angle':20}}}]}]}

    def test_interpolation_loop_hold_and_shortest_rotation(self):
        clip=self.config()['clips'][0]
        self.assertEqual(animation.sample(clip,12)['head'],{'dx':5,'dy':2,'angle':10})
        self.assertEqual(animation.sample(clip,36)['head'],{'dx':5,'dy':2,'angle':10})
        self.assertEqual(animation.sample(clip,48)['head'],{'dx':0,'dy':0,'angle':0})
        clip['loop']=False;self.assertEqual(animation.sample(clip,47)['head']['dx'],10)
        clip['easing']='hold';self.assertEqual(animation.sample(clip,12)['head']['dx'],0)
        clip['easing']='linear';clip['keys'][0]['pose']={'head':{'angle':179}};clip['keys'][1]['pose']={'head':{'angle':-179}}
        self.assertEqual(animation.sample(clip,12)['head']['angle'],180)

    def test_validation_limits_and_corrupt_pose(self):
        manifest=fixtures.BoneTests().manifest();rig=rigging_bones.get_rig(manifest)
        for mutate in [lambda c:c['clips'][0].update(fps=0),lambda c:c['clips'][0].update(frames=12),
                       lambda c:c['clips'][0]['keys'].append(c['clips'][0]['keys'][0]),
                       lambda c:c['clips'][0]['keys'][0].update(pose={'missing':{}}),
                       lambda c:c['clips'][0]['keys'][0].update(pose={'head':{'dx':float('nan')}})]:
            config=self.config();mutate(config)
            with self.assertRaises(ValueError):animation.validate(config,rig,manifest['canvas'])
        self.assertEqual(animation.validate(self.config(),rig,manifest['canvas'])['clips'][0]['name'],'Idle')

    def test_revision_restore_unity_clips_and_scaling(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name)/'job';manifest=fixtures.BoneTests().fixture(folder);rig=rigging_bones.get_rig(manifest)
            next(b for b in rig['bones'] if b['name']=='head')['x']=150
            config=self.config();writer=Path(__file__).parent/'tools/write_psd.js'
            saved=rigging_editor.save_revision(folder,[{'kind':'rig_animation','config':config,'rig':rig}],0,writer)
            self.assertEqual(saved['manifest']['rigAnimations'],config)
            self.assertEqual(next(b for b in saved['manifest']['rigEditor']['bones'] if b['name']=='head')['x'],150)
            built=rigging_v2.build_package(folder,Path(__file__).parent/'unity-v2',1)
            with zipfile.ZipFile(built['path']) as archive:
                exported=json.loads(archive.read('rig-v2.json'))
                self.assertEqual(exported['animations'][0]['tracks'][0]['keys'][0]['angle'],0)
                self.assertEqual(exported['animations'][0]['tracks'][0]['keys'][1]['angle'],20)
                self.assertIn('UnityV2/Runtime/RiggingV2ClipPlayer.cs',archive.namelist())
                self.assertIn('UnityV2/Editor/RiggingV2AnimationBuilder.cs',archive.namelist())
            enlarged=rigging_upscale.export_layers(folder,2,writer)
            with zipfile.ZipFile(io.BytesIO(enlarged)) as archive:
                scaled=json.loads(archive.read('manifest.json'))['rigAnimations']['clips'][0]['keys'][1]['pose']['head']
            self.assertEqual(scaled,{'dx':20,'dy':8,'angle':20})
            rigging_editor.restore_version(folder,0,1)
            self.assertNotIn('rigAnimations',rigging_editor.read_manifest(folder))


if __name__=='__main__':unittest.main()
