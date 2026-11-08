import base64
import io
import math
import unittest
from unittest.mock import patch
from PIL import Image
import image_engine
import image_pose


POINTS = [[.5,.12],[.5,.23],[.4,.25],[.35,.4],[.3,.55],[.6,.25],[.65,.4],[.7,.55],[.44,.54],[.42,.73],[.4,.93],[.56,.54],[.58,.73],[.6,.93],[.48,.11],[.52,.11],[.46,.12],[.54,.12]]


class PoseTests(unittest.TestCase):
    def test_untrusted_pose_is_bounded_and_only_supported_configuration_allowed(self):
        with patch.object(image_pose,'status',return_value={'ready':True}):
            for value in [True,{}, {'points':POINTS[:-1]}, {'points':[[math.nan,0]]+POINTS[1:]}, {'points':[[2,0]]+POINTS[1:]}, {'points':[[True,0]]+POINTS[1:]}, {'points':POINTS,'strength':10}]:
                with self.subTest(value=value),self.assertRaises(ValueError):
                    image_pose.validate(value,'flanime-xl','reference')
            for model,mode,face in [('anima-turbo','text',False),('flanime-xl','inpaint',False),('flanime-xl','text',True)]:
                with self.assertRaises(ValueError):
                    image_pose.validate({'points':POINTS},model,mode,face)
        with patch.object(image_pose,'status',return_value={'ready':False}),self.assertRaises(ValueError):
            image_pose.validate({'points':POINTS},'flanime-xl','text')

    def test_pose_flows_through_validation_and_both_sampler_conditionings(self):
        with patch.object(image_pose,'status',return_value={'ready':True}):
            p=image_engine.validate(dict(model='flanime-xl',prompt='adult knight, facing right',pose={'points':POINTS,'strength':.8}))
        graph=image_engine.build_workflow(p,42,pose_image_name='pose.png')
        self.assertEqual(graph['52']['inputs']['strength'],.8)
        self.assertEqual(graph['7']['inputs']['positive'],['52',0])
        self.assertEqual(graph['7']['inputs']['negative'],['52',1])
        self.assertEqual(graph['51']['inputs']['image'],'pose.png')
        self.assertEqual(p['pose']['version'],image_pose.VERSION)
        with self.assertRaises(ValueError):image_engine.build_workflow(p,42)
        plain=image_engine.validate(dict(model='flanime-xl',prompt='knight'))
        self.assertNotIn('50',image_engine.build_workflow(plain,42))

    def test_reference_preserves_geometry_and_rejects_empty_alpha(self):
        source=Image.new('RGBA',(300,500));source.paste((255,0,0,255),(100,50,200,450))
        prepared=image_pose.prepare_reference(source,(1024,1536))
        pixels=prepared.load();xs=[];ys=[]
        for y in range(prepared.height):
            for x in range(prepared.width):
                if pixels[x,y]==(255,0,0):xs.append(x);ys.append(y)
        self.assertAlmostEqual((max(xs)-min(xs)+1)/(max(ys)-min(ys)+1),.25,places=2)
        self.assertEqual(prepared.getpixel((0,0)),(210,210,210))
        with self.assertRaises(ValueError):image_pose.prepare_reference(Image.new('RGBA',(20,20)),(512,768))
        buf=io.BytesIO();source.save(buf,format='PNG')
        p=image_engine.validate(dict(model='flanime-xl',mode='reference',prompt='knight',denoise=.3,imageData=base64.b64encode(buf.getvalue()).decode()))
        graph=image_engine.build_workflow(p,42,image_name='reference.png')
        self.assertEqual(graph['6']['class_type'],'VAEEncode')
        self.assertEqual(graph['7']['inputs']['denoise'],.3)
        self.assertEqual((p['width'],p['height']),(1024,1536))


if __name__=='__main__':unittest.main()
