import unittest
import effect_prompts
import idle_tool


class EffectPromptTests(unittest.TestCase):
    def test_loop_keyframe_and_anatomy_isolation(self):
        for kind, config in effect_prompts.TEMPLATES.items():
            with self.subTest(kind=kind):
                graph=idle_tool.build_workflow('fixture.png','',3,512,512,42,workflow_id='fasth3-sprite')
                effect_prompts.apply(graph,kind)
                inputs=graph['6']['inputs']
                self.assertEqual('last_frame' in inputs,config['loop'])
                self.assertEqual('<Picture 2>' in inputs['prompt'],config['loop'])
                for term in ('breathing','chest','eyelids','feet','hips'):
                    self.assertNotIn(term,inputs['prompt'])
                self.assertEqual(graph['10']['inputs']['steps'],8)
                self.assertIn(config['motion'],inputs['prompt'])

    def test_custom_motion(self):
        text=effect_prompts.prompt('slash',3,'A red arc travels left.')
        self.assertIn('A red arc travels left.',text)
        self.assertNotIn('<Picture 2>',text)
        with self.assertRaises(KeyError):
            effect_prompts.prompt('unknown',3)


if __name__=='__main__':
    unittest.main()
