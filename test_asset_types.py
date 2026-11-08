import unittest
import asset_types
import image_engine


class AssetTypeTests(unittest.TestCase):
    def test_direction_plan_does_not_request_eight_unrelated_generations(self):
        p=image_engine.validate(dict(model='flanime-xl',prompt='adult knight',preset='sprite',assetSpec=dict(type='topdown',directionCount=8,facing='back-right')))
        self.assertEqual(p['count'],1)
        self.assertEqual(p['assetSpec']['outputMode'],'single-direction')
        self.assertEqual(p['assetSpec']['directionCount'],8)
        self.assertIn('overhead camera',p['resolvedPrompt'])
        self.assertIn('facing up-right',p['resolvedPrompt'])
        self.assertNotIn('three-quarter view',p['resolvedPrompt'])
        self.assertNotIn('reference sheet',p['resolvedPrompt'])
        self.assertEqual(image_engine.validate(p)['resolvedPrompt'],p['resolvedPrompt'])

    def test_live2d_and_side_are_distinct_camera_presets(self):
        base=dict(model='flanime-xl',prompt='adult knight',preset='sprite')
        live=image_engine.validate(base|dict(assetSpec=dict(type='live2d',facing='front')))
        side=image_engine.validate(base|dict(assetSpec=dict(type='side',facing='right')))
        self.assertIn('arms slightly away from torso',live['resolvedPrompt'])
        self.assertIn('eye-level camera',side['resolvedPrompt'])
        self.assertIn('facing right',side['resolvedPrompt'])
        self.assertNotIn('looking at viewer',side['resolvedPrompt'])

    def test_malformed_asset_specs_are_rejected(self):
        for value in [True,[],{},dict(type='../bad'),dict(type=[]),dict(type='side',directionCount=True),dict(type='side',directionCount=12),dict(type='side',facing=[]),dict(type='live2d',facing='back'),dict(type='illustration',directionCount=8)]:
            with self.subTest(value=value),self.assertRaises(ValueError):asset_types.validate(value)
        self.assertIsNone(asset_types.validate(None))
        self.assertEqual(asset_types.motion_prompt(None),'')

    def test_legacy_requests_keep_their_existing_prompt(self):
        p=image_engine.validate(dict(model='anima-turbo',prompt='adult knight',preset='sprite'))
        self.assertNotIn('assetSpec',p)
        self.assertIn('three-quarter view',p['resolvedPrompt'])


if __name__=='__main__':unittest.main()
