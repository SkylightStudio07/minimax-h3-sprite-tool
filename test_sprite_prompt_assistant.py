import base64
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from PIL import Image
import sprite_prompts as prompts
import idle_tool
import team_server

PROFILE=dict(description='검은 마스크와 녹색 바이저를 쓴 정장 캐릭터. 화면 왼쪽 손은 소음 권총을 들고 반대 손은 닫힌 회색 서류가방을 든다.',uncertainty='',subjectType='human',facing='left')
PLAN=dict(identity=('Preserve the exact dark suit, full black mask and green visor. The leftmost hand holds the existing suppressed pistol; the opposite hand holds the closed grey briefcase. '),
          motion=('Keep both boots planted and the case hanging from its handle. Brace the shoulder, fire two compact flashes from the actual suppressor tip toward screen left, absorb recoil through the wrist and elbow, and return to the original aim by 3 seconds. Fixed camera and flat grey in every gap. '),summary='서류가방은 든 채 권총을 왼쪽으로 두 발 쏘고 조준 자세로 복귀합니다.')

class Response:
    ok=True
    status_code=200
    def __init__(self,data):self.data=data
    def json(self):return {'candidates':[{'finishReason':'STOP','content':{'parts':[{'thought':True,'text':'internal notes'},{'text':json.dumps(self.data,ensure_ascii=False)}]}}]}

class PromptTests(unittest.TestCase):
    def setUp(self):
        prompts._cache.clear()
        self.provider=patch.object(prompts,'status_payload',return_value=dict(configured=True));self.provider.start()
        self.addCleanup(self.provider.stop)

    def test_reference_cache_is_private_and_input_is_bounded(self):
        image=Image.new('RGBA',(2000,1000),(30,50,70,255))
        with patch.object(prompts.music_prompts,'_gemini_post',return_value=Response(PROFILE)) as call:
            first=prompts.analyze(image,'member-a');again=prompts.analyze(image,'member-a')
            self.assertFalse(first['cached']);self.assertTrue(again['cached']);self.assertEqual(call.call_count,1)
            encoded=call.call_args.args[0]['contents'][0]['parts'][0]['inlineData']
            with Image.open(io.BytesIO(base64.b64decode(encoded['data']))) as sent:
                self.assertEqual(sent.size,(1536,768));self.assertNotIn('exif',sent.info)
            prompts.analyze(image,'member-b');self.assertEqual(call.call_count,2)
            first['profile']['description']='changed'
            self.assertEqual(again['profile']['description'],PROFILE['description'])

    def test_edits_action_and_duration_are_used_and_cache_invalidates(self):
        p=dict(description=PROFILE['description'],animationType='attack',duration=3,loop=False)
        with patch.object(prompts.music_prompts,'_gemini_post',return_value=Response(PLAN)) as call:
            result=prompts.plan(p,'member-a');self.assertIn('briefcase',result['prompt'])
            self.assertTrue(prompts.plan(p,'member-a')['cached'])
            p.update(duration=5,description=PROFILE['description']+' 가방을 파란색으로 수정.')
            self.assertFalse(prompts.plan(p,'member-a')['cached']);self.assertEqual(call.call_count,2)
            actual=json.loads(call.call_args.args[0]['contents'][0]['parts'][0]['text'])
            self.assertEqual(actual['duration'],5);self.assertIn('파란색',actual['description'])
            self.assertNotIn('inlineData',call.call_args.args[0]['contents'][0]['parts'][0])

    def test_failure_is_retryable_and_does_not_expose_credentials(self):
        image=Image.new('RGB',(32,48),'red')
        with patch.object(prompts.music_prompts,'_gemini_post',side_effect=RuntimeError('url?key=PRIVATE_TOKEN')):
            with self.assertRaises(ValueError) as error:prompts.analyze(image,'member-a')
            self.assertNotIn('PRIVATE_TOKEN',str(error.exception))
        with patch.object(prompts.music_prompts,'_gemini_post',return_value=Response(PROFILE)) as call:
            self.assertFalse(prompts.analyze(image,'member-a')['cached']);self.assertEqual(call.call_count,1)
        with patch.object(prompts.music_prompts,'_gemini_post',return_value=Response({'description':'bad'})):
            with self.assertRaises(ValueError):prompts.analyze(Image.new('RGB',(32,48),'blue'),'member-a')

    def test_invalid_plans_never_reach_provider(self):
        valid=dict(description=PROFILE['description'])
        with patch.object(prompts.music_prompts,'_gemini_post') as call:
            for change in [dict(duration=True),dict(duration=60),dict(loop='yes'),dict(animationType='custom'),dict(notes=['bad']),dict(facing='diagonal')]:
                with self.assertRaises(ValueError):prompts.plan(valid|change,'member-a')
            call.assert_not_called()

    def test_guided_workflow_retains_action_without_generic_idle_pumping(self):
        prompt=idle_tool.animation_prompt('Small head check; both boots planted.','idle',True,'left',3,True,image_guided=True)
        self.assertIn('Small head check',prompt)
        self.assertNotIn('Maintain an even breathing rhythm',prompt)
        self.assertNotIn('Strict screen-left-facing side profile',prompt)
        self.assertIn('Match the opening pose',prompt)
        manual=idle_tool.animation_prompt('Small head check','idle',True)
        self.assertIn('Maintain an even breathing rhythm',manual)

class RouteTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.data=Path(self.temp.name)
        self.app=team_server.create_app(self.data,runner=lambda *_:None)
        self.client=self.app.test_client();self.guest=self.app.test_client()
        code=(self.data/'admin-setup-code.txt').read_text()
        self.post('register',username='prompt-admin',name='테스트',password='long-password',setupCode=code)
        self.post('login',username='prompt-admin',password='long-password')
        buf=io.BytesIO();Image.new('RGB',(32,48),'red').save(buf,format='PNG')
        self.image='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()
    def tearDown(self):self.app.stop_worker();self.temp.cleanup()
    def post(self,path,**p):return self.client.post('/api/'+path,json=p,headers={'X-Sprite-Request':'1'})

    def test_auth_validation_busy_and_no_generation_side_effect(self):
        self.assertEqual(self.guest.get('/api/sprite-prompts/status').status_code,401)
        self.assertEqual(self.guest.post('/api/sprite-prompts/analyze',json={'imageData':self.image},headers={'X-Sprite-Request':'1'}).status_code,401)
        self.assertEqual(self.client.post('/api/sprite-prompts/analyze',json={'imageData':self.image}).status_code,403)
        self.assertEqual(self.post('sprite-prompts/analyze',imageData='bad').status_code,400)
        with patch.object(prompts,'analyze',return_value=dict(profile=PROFILE)) as call:
            response=self.post('sprite-prompts/analyze',imageData=self.image)
            self.assertEqual(response.status_code,200);self.assertEqual(call.call_args.args[0].size,(32,48))
        with patch.object(prompts,'plan',side_effect=prompts.PromptBusy('잠시 후')):
            self.assertEqual(self.post('sprite-prompts/plan',description=PROFILE['description']).status_code,429)
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:self.assertEqual(con.execute('select count(*) from jobs').fetchone()[0],0)

    def test_applied_prompt_mode_is_saved_for_video_generation(self):
        response=self.post('generate',imageData=self.image,width=512,height=512,animationType='idle',prompt=PLAN['identity']+PLAN['motion'],motionPromptMode='image-guided')
        self.assertEqual(response.status_code,202,response.json)
        with closing(sqlite3.connect(self.data/'team.sqlite3')) as con:
            payload=json.loads(con.execute('select payload from jobs where id=?',(response.json['jobId'],)).fetchone()[0])
        self.assertEqual(payload['motionPromptMode'],'image-guided');self.assertIn('briefcase',payload['prompt'])
        self.assertEqual(self.post('generate',motionPromptMode='bad').status_code,400)

if __name__=='__main__':unittest.main()
