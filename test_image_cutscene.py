import unittest
import io
import base64
from PIL import Image
from unittest.mock import patch
import image_engine as engine
import image_cutscene
import image_face_detail


class CutsceneTests(unittest.TestCase):
    def test_mix_and_face_use_separate_model_paths_at_native_resolution(self):
        for denoise in [.12,.20]:
            with patch.object(image_face_detail,'ready',return_value=True):
                p=engine.validate(dict(model=image_cutscene.MODEL_ID,prompt='purple bob hair, blue eyes, black coat',faceDetail=True,faceDetailDenoise=denoise,assetSpec=dict(type='side',directionCount=1,facing='right')))
            graph=engine.build_workflow(p,42)
            self.assertEqual(graph['3']['inputs']['model'],['11',0])
            self.assertEqual(graph['11']['inputs']['strength_model'],.4)
            self.assertEqual(graph['3']['inputs']['strength_model'],1.)
            self.assertEqual(graph['14']['inputs']['model'],['1',0])
            self.assertEqual(graph['23']['inputs']['model'],['14',0])
            self.assertEqual(graph['23']['inputs']['denoise'],denoise)
            self.assertEqual(graph['23']['inputs']['vae'],['1',2])
            self.assertEqual(graph['24']['inputs']['images'],['8',0])
            self.assertEqual((p['outputWidth'],p['outputHeight']),(832,1216))
            self.assertEqual(engine.backend_url(p),engine.image_soya.URL)
            self.assertIn('ring above head',p['resolvedNegativePrompt'])
            self.assertNotIn('blue archive',p['resolvedPrompt'])
            self.assertNotIn('camera',p['resolvedPrompt'])
            self.assertEqual(p['counterIntegrityStatus'],'upstream-mismatch-user-approved')
            self.assertEqual(engine.validate(p)['resolvedPrompt'],p['resolvedPrompt'])

    def test_reference_pose_and_masked_correction(self):
        def data(color):
            buf=io.BytesIO();Image.new('RGBA',(32,48),color).save(buf,format='PNG')
            return 'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()
        request=dict(model=image_cutscene.MODEL_ID,prompt='adult hooded fighter',mode='reference',imageData=data('red'),count=3,denoise=.8,pose=dict(points=[[.5,.5]]*18,strength=1.2))
        with patch.object(engine.image_pose,'status',return_value=dict(ready=True)):
            p=engine.validate(request)
        graph=engine.build_workflow(p,42,'ref.png','pose.png')
        self.assertEqual(graph['6']['class_type'],'VAEEncode')
        self.assertEqual(graph['6']['inputs']['vae'],['1',2])
        self.assertEqual(graph['10']['inputs']['image'],'ref.png')
        self.assertEqual(graph['51']['inputs']['image'],'pose.png')
        self.assertEqual(graph['7']['inputs']['positive'],['52',0])
        self.assertEqual(graph['7']['inputs']['denoise'],.8)
        self.assertEqual(p['count'],3)
        request.update(mode='inpaint',maskData=data('white'),pose=None,denoise=.3)
        p=engine.validate(request)
        graph=engine.build_workflow(p,43,'mask.png')
        self.assertEqual(graph['6']['class_type'],'VAEEncodeForInpaint')
        self.assertNotIn('52',graph)
        self.assertEqual(p['background'],'keep')
        self.assertEqual(graph['7']['inputs']['denoise'],.3)
        with self.assertRaises(ValueError):engine.validate(request|dict(maskData=data('black')))

    def test_recipe_rejects_unsupported_combinations_and_denoise(self):
        request=dict(model=image_cutscene.MODEL_ID,prompt='adult knight')
        for extra in [dict(mode='reference'),dict(counterMixStrength=True),dict(counterMixStrength=.9),dict(cutsceneMixStrength=float('nan')),dict(pose={}),dict(styleId='epic-seven-sprites'),dict(lookId='cutscene-counter-reviewed')]:
            with self.subTest(extra=extra),self.assertRaises(ValueError):engine.validate(request|extra)
        with patch.object(image_face_detail,'ready',return_value=True):
            for value in [.15,True,float('nan')]:
                with self.assertRaises(ValueError):engine.validate(request|dict(faceDetail=True,faceDetailDenoise=value))
        p=engine.validate(request)
        self.assertNotIn('23',engine.build_workflow(p,42))
        self.assertEqual(engine.DEFAULT_MODEL,'soya-anima-flanime')


if __name__=='__main__':unittest.main()
