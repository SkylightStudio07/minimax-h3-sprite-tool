import io
import json
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch,MagicMock
from PIL import Image
import image_caption as caption

class CaptionTests(unittest.TestCase):
    def test_repeated_tags_are_removed_without_losing_distinct_details(self):
        self.assertEqual(caption.appearance_only('black belt, red coat lining, Black belt, black  belt, gold belt buckle'),
                         'black belt, red coat lining, gold belt buckle')
    def test_timeout_stops_only_the_caption_process_tree(self):
        child=MagicMock(pid=12345)
        child.communicate.side_effect=[subprocess.TimeoutExpired('caption',240),('','')]
        child.poll.return_value=None
        with patch.object(caption.os,'name','nt'),patch.object(caption.subprocess,'Popen',return_value=child),patch.object(caption.subprocess,'run') as kill:
            with self.assertRaises(subprocess.TimeoutExpired):caption.run_worker(['python','caption.py'],{})
        self.assertEqual(kill.call_args.args[0],['taskkill','/PID','12345','/T','/F'])
        child.kill.assert_called_once()

    def test_detailed_draft_is_accepted_without_truncation(self):
        text=', '.join(f'detailed garment panel {i}' for i in range(90))
        self.assertGreater(len(text),1800)
        with patch.object(caption,'status_payload',return_value={'ready':True}):
            response=SimpleNamespace(returncode=0,stdout=json.dumps(dict(prompt=text,summary='의상 디테일 확인')))
            with patch.object(caption,'run_worker',return_value=response):
                result=caption.analyze(Image.new('RGB',(20,30),'red'))
            self.assertEqual(result['prompt'],text)
            response.stdout=json.dumps(dict(prompt='a'*(caption.MAX_PROMPT_CHARS+1),summary='확인'))
            with patch.object(caption,'run_worker',return_value=response),self.assertRaises(ValueError):
                caption.analyze(Image.new('RGB',(20,30),'red'))

    def test_appearance_draft_does_not_override_target_pose(self):
        self.assertEqual(caption.appearance_only('short black hair, hood up, navy long coat, standing with one hand raised, facing left, holding a rifle'),
                         'short black hair, hood up, navy long coat, holding a rifle')
        self.assertEqual(caption.appearance_only('short purple hair. Her left hand is raised, showing a gold mechanical claw. The right hand is relaxed at her side. The character stands against a gray background.'),
                         'short purple hair, showing a gold mechanical claw')
        response=SimpleNamespace(returncode=0,stdout=json.dumps(dict(prompt='short black hair, black hood, long coat, standing with one hand raised',summary='Check hood')))
        with patch.object(caption,'status_payload',return_value={'ready':True}),patch.object(caption,'run_worker',return_value=response):
            result=caption.analyze(Image.new('RGB',(20,30),'red'))
        self.assertNotIn('standing',result['prompt'])
        self.assertIn('후드',result['summary'])

    def test_prepare_crops_alpha_and_strips_metadata_without_changing_source(self):
        source=Image.new('RGBA',(1600,1200));source.paste((40,50,60,255),(200,100,1400,1100));before=source.tobytes()
        with Image.open(io.BytesIO(caption.prepare(source))) as result:
            self.assertEqual(result.mode,'RGB');self.assertLessEqual(max(result.size),768)
            self.assertEqual(result.getexif(),{});self.assertAlmostEqual(result.width/result.height,1.2,places=2)
        self.assertEqual(before,source.tobytes())
        with self.assertRaises(ValueError):caption.prepare(Image.new('RGBA',(20,20)))

    def test_no_remote_call_and_worker_is_offline_cpu_and_temp_image_removed(self):
        response=SimpleNamespace(returncode=0,stdout=json.dumps(dict(prompt='short purple hair, black hood, long black coat',summary='후드와 장갑을 확인하세요.')))
        with patch.object(caption,'status_payload',return_value={'ready':True}),patch.object(caption,'run_worker',return_value=response) as run:
            result=caption.analyze(Image.new('RGB',(20,30),'red'))
        self.assertEqual(result['provider'],'local')
        args=run.call_args
        self.assertEqual(args.args[1]['CUDA_VISIBLE_DEVICES'],'')
        self.assertEqual(args.args[1]['HF_HUB_OFFLINE'],'1')
        self.assertFalse(caption.Path(args.args[0][-1]).exists())

    def test_timeout_invalid_output_and_busy_are_recoverable(self):
        with patch.object(caption,'status_payload',return_value={'ready':True}):
            for response in [SimpleNamespace(returncode=1,stdout=''),SimpleNamespace(returncode=0,stdout='not json')]:
                with patch.object(caption,'run_worker',return_value=response),self.assertRaises(ValueError):caption.analyze(Image.new('RGB',(20,30)))
            with patch.object(caption,'run_worker',side_effect=subprocess.TimeoutExpired('worker',240)),self.assertRaises(ValueError):caption.analyze(Image.new('RGB',(20,30)))
            caption._slot.acquire()
            try:
                with self.assertRaises(caption.CaptionBusy):caption.analyze(Image.new('RGB',(20,30)))
            finally:caption._slot.release()
        self.assertTrue(caption._slot.acquire(blocking=False));caption._slot.release()

if __name__=='__main__':unittest.main()
