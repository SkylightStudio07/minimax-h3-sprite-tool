import unittest
import idle_tool as engine


class PromptTests(unittest.TestCase):
    def test_walk_run_have_distinct_full_body_continuous_motion(self):
        for action in ('walk','run'):
            for loop in (False,True):
                for detail in ('',engine.LEGACY_GAIT_PROMPTS[action]):
                    text=engine.animation_prompt(detail,action,loop)
                    self.assertIn(engine.ANIMATION_DEFAULTS[action],text)
                    self.assertIn('shoulders',text);self.assertIn('pelvis',text)
                    self.assertIn('already in progress',text)
                    self.assertNotIn('settles back',text);self.assertNotIn('settled final pose',text)
                    self.assertEqual('<Picture 2>' in text,loop)
        self.assertIn('one support foot',engine.animation_prompt('','walk',True))
        self.assertIn('airborne phase',engine.animation_prompt('','run',True))
        self.assertIn('carry the rifle in both hands',engine.animation_prompt('carry the rifle in both hands','run',True))

    def test_fasth3_workflow(self):
        from unittest.mock import patch
        import sprite_workflows
        graph=engine.build_workflow('test.png','idle',3,512,512,7,workflow_id='fasth3-sprite')
        self.assertEqual(graph['2']['inputs']['unet_name'],sprite_workflows.FAST_FILENAME)
        self.assertEqual(graph['10']['inputs']['steps'],8)
        self.assertEqual(graph['11']['inputs']['model'],['18',0])
        self.assertEqual(graph['18']['inputs']['shift_video'],10)
        self.assertNotIn('7',graph)
        self.assertIn('last_frame',graph['6']['inputs'])
        for options in [dict(workflow_id='bad'),dict(workflow_id='fasth3-sprite',negative_enabled=True)]:
            with self.assertRaises(ValueError):engine.build_workflow('test.png','',3,512,512,7,**options)
        with self.assertRaises(ValueError):engine.build_workflow('test.png','',3,352,608,7,workflow_id='fasth3-sprite')
        with patch.object(sprite_workflows,'status',return_value=[{},dict(ready=False)]):
            with self.assertRaises(ValueError):sprite_workflows.validate(dict(workflowId='fasth3-sprite',width=512,height=512),engine.COMFY_ROOT)

    def test_subject_types(self):
        for subject in engine.SUBJECT_DEFAULTS:
            self.assertEqual(set(engine.SUBJECT_DEFAULTS[subject]), set(engine.ANIMATION_DEFAULTS))
            for action in engine.ANIMATION_DEFAULTS:
                p=engine.build_workflow('test.png','',5,352,608,123,animation_type=action,subject_type=subject)['6']['inputs']['prompt']
                self.assertIn(engine.SUBJECT_DEFAULTS[subject][action],p)
                for term in ('head-to-body', 'hair tips', 'The mouth'):
                    self.assertNotIn(term,p)
                if subject.endswith('machine'):
                    for term in ('breathing', 'eyelids', 'hips', 'shoulders', 'clothing'):
                        self.assertNotIn(term,p)
        self.assertIn('my custom motion',engine.animation_prompt('my custom motion','idle',True,subject_type='hover_machine'))
        with self.assertRaises(ValueError):
            engine.animation_prompt('','idle',True,subject_type='bad')

    def test_continuous_idle_and_legacy_templates(self):
        for seconds in (3, 5):
            for loop in (False, True):
                for detail in ('', *engine.LEGACY_IDLE_PROMPTS):
                    p=engine.animation_prompt(detail,'idle',loop,seconds=seconds)
                    self.assertIn('restrained living idle motion',p)
                    self.assertIn('final two seconds',p)
                    self.assertNotIn('settles back',p)
                    self.assertNotIn('settled final pose',p)
                    self.assertEqual('<Picture 2>' in p,loop)
        p=engine.animation_prompt('gently adjust the grip','idle',True)
        self.assertIn('gently adjust the grip',p)
        p=engine.animation_prompt('','attack',False)
        self.assertIn('settled final pose',p)

    def test_motion_strength_templates(self):
        for action in engine.ANIMATION_DEFAULTS:
            for strength, instruction in engine.MOTION_PROMPTS.items():
                w=engine.build_workflow('test.png','',5,352,608,123,animation_type=action,motion_strength=strength)
                p=w['6']['inputs']['prompt']
                self.assertIn(instruction,p)
                self.assertIn('static shot',p)
                self.assertIn('Never rotate',p)
        p=engine.animation_prompt('raise one hand','custom',False,motion_strength='high')
        self.assertIn('raise one hand',p)
        with self.assertRaises(ValueError):
            engine.animation_prompt('','idle',True,motion_strength='invalid')

    def test_loop_alignment_and_structure(self):
        w=engine.build_workflow('test.png','',5,352,608,123,flat_background=True)
        p=w['6']['inputs']['prompt']
        self.assertIn('<Picture 2>',p)
        self.assertIn('5.17 seconds',p)
        self.assertIn('last_frame',w['6']['inputs'])
        for field in ('integrated_multimodal_description:', 'overall_soundscape:', 'non_diegetic_music:'):
            self.assertEqual(p.count(field),1)
        self.assertIn('uniform medium-gray',p)
        self.assertIn('No blinking',p)
        self.assertNotIn('subtle blinking',p)

    def test_one_shot_and_opaque_background(self):
        w=engine.build_workflow('test.png','one weapon recoil',3,352,608,123,'attack',False,'right')
        p=w['6']['inputs']['prompt']
        self.assertNotIn('<Picture 2>',p)
        self.assertNotIn('last_frame',w['6']['inputs'])
        self.assertNotIn('medium-gray',p)
        self.assertIn('nose and gaze stay directed to screen right',p)
        self.assertIn('one weapon recoil',p)

    def test_fasth3_idle_preserves_torso_volume(self):
        for prompt in ('', engine.ANIMATION_DEFAULTS['idle'], *engine.LEGACY_IDLE_PROMPTS):
            w=engine.build_workflow('test.png',prompt,3,512,512,42,workflow_id='fasth3-sprite')
            p=w['6']['inputs']['prompt']
            self.assertNotIn('breathing',p)
            self.assertIn('same volume, width and contour',p)
            self.assertIn('hair tips',p)
        p=engine.animation_prompt('wave one hand','idle',True,rigid_idle=True)
        self.assertIn('wave one hand',p)

    def test_blink_option(self):
        p=engine.animation_prompt('', 'idle', True, blink_mode='once')
        self.assertIn('at most one',p)
        self.assertNotIn('No blinking',p)

    def test_legacy_idle_default(self):
        p=engine.animation_prompt('gentle breathing, subtle blinking, slight hair and clothing sway, feet remain planted','idle',True)
        self.assertNotIn('subtle blinking',p)
        self.assertIn('restrained living idle motion',p)

    def test_experimental_negative_layout_and_defaults(self):
        for loop in (False, True):
            w=engine.build_workflow('test.png','',3,352,608,123,loop=loop,flat_background=True,negative_enabled=True)
            self.assertEqual(w['11']['class_type'],'CFGGuider')
            self.assertEqual(w['11']['inputs']['cfg'],1.5)
            self.assertEqual(w['11']['inputs']['negative'],['17',0])
            a=dict(w['6']['inputs']);b=dict(w['17']['inputs'])
            positive=a.pop('prompt');negative=b.pop('prompt')
            self.assertEqual(a,b)
            for term in ('spotlight','stage lighting','cast shadow','vignette'):
                self.assertNotIn(term,positive.lower())
                self.assertNotIn(term,negative.lower())
        w=engine.build_workflow('test.png','',3,352,608,123)
        self.assertEqual(w['11']['class_type'],'BasicGuider')
        self.assertNotIn('17',w)

    def test_negative_validation(self):
        for cfg in (1,3,True,float('nan'),float('inf'),'1.5'):
            with self.assertRaises(ValueError):
                engine.guidance_options({'negativeEnabled':True,'cfgScale':cfg})
        with self.assertRaises(ValueError):
            engine.guidance_options({'negativeEnabled':True,'negativePrompt':''})

    def test_quality_default_and_turbo_option(self):
        for mode,steps,model in [('quality',20,'2'),('turbo',4,'7')]:
            for negative in (False,True):
                w=engine.build_workflow('test.png','',3,352,608,123,sampling_mode=mode,negative_enabled=negative)
                self.assertEqual(w['10']['inputs']['steps'],steps)
                self.assertEqual(w['10']['inputs']['model'],[model,0])
                self.assertEqual(w['11']['inputs']['model'],[model,0])
                self.assertEqual('7' in w,mode=='turbo')
        w=engine.build_workflow('test.png','',3,352,608,123)
        self.assertEqual(w['10']['inputs']['steps'],20)
        self.assertEqual(w['11']['class_type'],'BasicGuider')


class TurboV4WorkflowTest(unittest.TestCase):
    def build(self,**extra):
        return engine.build_workflow('a.png','move',3,768,768,1,**extra)
    def test_turbo_v4_uses_its_own_lora_sampler_and_eight_steps(self):
        w=self.build(sampling_mode='turbo-v4')
        self.assertEqual(w['7']['class_type'],'MiniMaxH3TurboLoRA');self.assertEqual(w['7']['inputs']['lora_name'],engine.TURBO_V4_LORA)
        self.assertEqual(w['9'],{'class_type':'MiniMaxH3TurboSampler','inputs':{}});self.assertEqual(w['10']['inputs']['steps'],8)
        self.assertEqual(w['10']['inputs']['model'],['7',0]);self.assertEqual(w['11']['inputs']['model'],['7',0])
    def test_older_modes_are_unchanged(self):
        self.assertEqual(self.build(sampling_mode='quality')['10']['inputs']['steps'],20)
        turbo=self.build(sampling_mode='turbo');self.assertEqual(turbo['7']['class_type'],'LoraLoaderModelOnly');self.assertEqual(turbo['9']['class_type'],'KSamplerSelect')
    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):self.build(sampling_mode='nope')


if __name__=='__main__':unittest.main()
