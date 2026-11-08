import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
import image_engine
import image_background


class SheetTests(unittest.TestCase):
    def test_sheet_does_not_inherit_single_character_framing_or_negative(self):
        p=image_engine.validate(dict(model='anima-base',prompt='blue hair, white scarf',preset='rpg-sheet',styleId='rpgchara-anima',styleStrength=1,assetSpec=dict(type='topdown',directionCount=4,facing='front')))
        self.assertEqual(p['sheetLayout']['columns'],3)
        self.assertEqual(p['assetSpec']['outputMode'],'four-direction-sheet')
        self.assertIn('3x4 grid',p['resolvedPrompt'])
        self.assertNotIn('overhead camera',p['resolvedPrompt'])
        self.assertNotIn('reference sheet',p['resolvedNegativePrompt'])
        graph=image_engine.build_workflow(p,42)
        self.assertEqual(graph['1']['inputs']['unet_name'],'anima_baseV10.safetensors')
        self.assertEqual(graph['11']['class_type'],'LoraLoaderModelOnly')
        for change in [dict(model='anima-turbo'),dict(styleId=''),dict(pose={}),dict(faceDetail=True)]:
            with self.assertRaises(ValueError):image_engine.validate(dict(p)|change)

    def test_sheet_matte_keeps_rgb_dimensions_and_cell_boundaries(self):
        original=Image.new('RGBA',(11,17),(250,250,250,255))
        def fake(cell):
            alpha=Image.new('L',cell.size,100);alpha.putpixel((0,0),200);cell.putalpha(alpha);return cell
        with patch.object(image_background,'remove',side_effect=fake) as remove:
            result=image_background.remove_sheet(original,3,4,hard=True)
        self.assertEqual(remove.call_count,12)
        self.assertEqual(result.size,original.size)
        self.assertEqual(result.convert('RGB').tobytes(),original.convert('RGB').tobytes())
        self.assertEqual(set(np.asarray(result.getchannel('A')).ravel()),{0,255})
        self.assertEqual(result.getpixel((round(11/3),round(17/4)))[3],255)


if __name__=='__main__':unittest.main()
