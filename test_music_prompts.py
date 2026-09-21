import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import music_prompts
import team_server


HEADERS = {'X-Sprite-Request': '1'}


class FakeGeminiResponse:
    ok = True
    status_code = 200

    def json(self):
        return {'candidates': [{'content': {'parts': [{'text':
            '{"prompt":"dark forest exploration, low strings, 90 BPM","reason":"어두운 숲 탐험 장면을 반영했습니다."}'
        }]}}]}


class FakeLiteResponse:
    ok = True
    status_code = 200

    def json(self):
        return {'candidates': [{'content': {'parts': [{'text':
            '{"prompt":"warm rainy village, acoustic guitar, clarinet, 82 BPM, seamless loop"}'
        }]}}]}


class MusicPromptTests(unittest.TestCase):
    def test_preset_and_direct_are_instrumental(self):
        preset = music_prompts.resolve({
            'promptMode': 'preset', 'preset': 'battle', 'title': '전투', 'seed': 7,
        })
        self.assertIn('no vocals', preset['resolvedPrompt'].lower())
        self.assertEqual(preset['seed'], 7)
        direct = music_prompts.resolve({
            'promptMode': 'direct', 'prompt': 'quiet snowy field, piano, 72 BPM', 'title': '설원',
        })
        self.assertIn('instrumental only', direct['resolvedPrompt'].lower())
        self.assertEqual(direct['lyrics'], music_prompts.INSTRUMENTAL_LYRICS)
        self.assertEqual(direct['vocalMode'], 'instrumental')
        self.assertIsInstance(direct['seed'], int)

    def test_instrumental_removes_conflicting_vocal_style_and_forces_planning(self):
        result = music_prompts.resolve({
            'promptMode': 'direct',
            'prompt': 'English, solemn dark choir textures, female singer, low strings, 78 BPM',
            'title': '성당', 'vocalMode': 'instrumental', 'cot': 'off',
        })
        style = result['resolvedPrompt'].lower()
        self.assertNotIn('choir', style)
        self.assertNotIn('singer', style)
        self.assertNotIn('female', style)
        self.assertIn('low strings', style)
        self.assertIn('no vocals', style)
        self.assertEqual(result['cot'], 'full')

    def test_vocal_song_keeps_lyrics_separate_from_style(self):
        lyrics = '[Verse]\n붉은 달 아래 길을 걷네\n[Chorus]\n새벽까지 노래하리'
        result = music_prompts.resolve({
            'promptMode': 'direct', 'prompt': 'Korean dark folk rock, female lead vocal, 96 BPM',
            'title': '붉은 달', 'vocalMode': 'lyrics', 'lyrics': lyrics,
        })
        self.assertEqual(result['lyrics'], lyrics)
        self.assertEqual(result['vocalMode'], 'lyrics')
        self.assertNotIn('instrumental only', result['resolvedPrompt'].lower())

    def test_gemini_document_resolution(self):
        with patch.dict(os.environ, {'GEMINI_PROVIDER': 'api-key', 'GEMINI_API_KEY': 'test'}):
            with patch.object(music_prompts.requests, 'post', return_value=FakeGeminiResponse()) as call:
                result = music_prompts.resolve({
                    'promptMode': 'gemini', 'title': '숲',
                    'gameDocument': '마법이 사라진 어두운 숲을 혼자 탐험한다.',
                })
        self.assertIn('no vocals', result['resolvedPrompt'].lower())
        self.assertIn('어두운 숲', result['promptReason'])
        self.assertEqual(call.call_args.kwargs['timeout'], 60)
        config = call.call_args.kwargs['json']['generationConfig']
        self.assertEqual(config['maxOutputTokens'], 4096)
        self.assertEqual(config['thinkingConfig']['thinkingBudget'], 1024)

    def test_vertex_document_resolution(self):
        environment = {
            'GEMINI_PROVIDER': 'vertex',
            'GEMINI_VERTEX_PROJECT': 'game-project',
            'GEMINI_VERTEX_LOCATION': 'asia-northeast3',
        }
        with patch.dict(os.environ, environment, clear=True):
            with patch.object(music_prompts, '_vertex_post', return_value=FakeGeminiResponse()) as call:
                result = music_prompts.resolve({
                    'promptMode': 'gemini', 'title': '숲',
                    'gameDocument': '마법이 사라진 어두운 숲을 혼자 탐험한다.',
                })
                status = music_prompts.status_payload()
        self.assertIn('no vocals', result['resolvedPrompt'].lower())
        self.assertEqual(status['provider'], 'vertex')
        self.assertTrue(status['configured'])
        self.assertEqual(status['maxDocumentChars'], 500000)
        self.assertEqual(status['maxMarkdownBytes'], 2000000)
        self.assertIn('asia-northeast3-aiplatform.googleapis.com', call.call_args.args[0])
        self.assertIn('/projects/game-project/locations/asia-northeast3/', call.call_args.args[0])

    def test_korean_direct_prompt_refinement_uses_lite_model(self):
        with patch.object(music_prompts, '_gemini_post', return_value=FakeLiteResponse()) as call:
            prompt = music_prompts.refine_direct_prompt('비 오는 마을의 따뜻하고 편안한 음악')
        self.assertIn('warm rainy village', prompt)
        self.assertIn('no vocals', prompt.lower())
        self.assertEqual(call.call_args.kwargs['model'], music_prompts.LITE_MODEL)

    def test_music_page_and_queue_api(self):
        with tempfile.TemporaryDirectory() as directory:
            app = team_server.create_app(Path(directory), runner=lambda *_: None,
                                         music_runner=lambda *_: None)
            client = app.test_client()
            code = (Path(directory) / 'admin-setup-code.txt').read_text()
            client.post('/api/register', json={
                'username': 'admin', 'name': '관리자', 'password': 'long-password', 'setupCode': code,
            }, headers=HEADERS)
            client.post('/api/login', json={'username': 'admin', 'password': 'long-password'},
                        headers=HEADERS)
            page = client.get('/music')
            self.assertEqual(page.status_code, 200)
            self.assertIn('Gemini 기획서 분석', page.text)
            self.assertIn('한국어 → 영어 프롬프트로 다듬기', page.text)
            page.close()
            with patch.object(music_prompts, 'refine_direct_prompt',
                              return_value='instrumental rainy town, no vocals') as refine:
                translated = client.post('/api/music/refine-prompt', json={
                    'prompt': '비 오는 마을 음악', 'vocalMode': 'instrumental',
                }, headers=HEADERS)
            self.assertEqual(translated.status_code, 200)
            self.assertIn('rainy town', translated.json['prompt'])
            refine.assert_called_once_with('비 오는 마을 음악', 'instrumental')
            response = client.post('/api/music/generate', json={
                'promptMode': 'preset', 'preset': 'town', 'title': '마을', 'seed': 11, 'cot': 'full',
            }, headers=HEADERS)
            self.assertEqual(response.status_code, 202)
            job = client.get('/api/jobs/' + response.json['jobId']).json
            self.assertEqual(job['jobType'], 'music')
            self.assertEqual(job['animationType'], 'BGM · 마을')
            self.assertIn('no vocals', response.json['resolvedPrompt'].lower())
            app.stop_worker()


if __name__ == '__main__':
    unittest.main()
