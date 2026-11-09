import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import av
import numpy as np
from PIL import Image

import idle_tool
import sprite_finish
import team_server as server
from test_character_studio import CharacterTests
from test_sprite_finish import cutout, figure


def write_clip(path, count):
    with av.open(str(path), 'w') as out:
        stream = out.add_stream('libx264', rate=24)
        stream.width = stream.height = 128
        stream.pix_fmt = 'yuv420p'
        stream.options = {'crf': '12'}
        for i in range(count):
            for packet in stream.encode(av.VideoFrame.from_image(figure(arm=i % 30))):
                out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)


class Choosing(unittest.TestCase):
    def test_closed_loop_drops_only_its_repeated_last_frame(self):
        self.assertEqual(sprite_finish.exact_indices(73, 72, True), list(range(72)))

    def test_one_shot_keeps_every_frame(self):
        self.assertEqual(sprite_finish.exact_indices(73, 73, False), list(range(73)))

    def test_more_frames_than_the_clip_gives_what_exists(self):
        self.assertEqual(sprite_finish.exact_indices(10, 20, False), list(range(10)))

    def test_fewer_frames_are_spread_across_the_clip(self):
        picked = sprite_finish.exact_indices(73, 12, False)
        self.assertEqual((len(picked), picked[0], picked[-1]), (12, 0, 72))

    def test_uniform_time_adds_up(self):
        self.assertEqual(sum(sprite_finish.uniform_ms(72, 24)), 3000)
        self.assertEqual(sum(sprite_finish.uniform_ms(73, 36)), 2028)
        self.assertLessEqual(max(sprite_finish.uniform_ms(73, 36)) - min(sprite_finish.uniform_ms(73, 36)), 1)


class Grid(unittest.TestCase):
    def test_keeps_eight_columns_when_they_fit(self):
        self.assertEqual(sprite_finish.fit_columns(72, 522, 606), 8)

    def test_tall_cells_get_more_columns(self):
        columns = sprite_finish.fit_columns(73, 708, 970)
        self.assertEqual(columns, 10)
        self.assertLessEqual((73 + columns - 1) // columns * 970, 8192)

    def test_wide_cells_get_fewer_columns(self):
        columns = sprite_finish.fit_columns(16, 1400, 300)
        self.assertLessEqual(columns * 1400, 8192)

    def test_explicit_columns_win_and_cannot_exceed_the_count(self):
        self.assertEqual(sprite_finish.fit_columns(73, 708, 970, 4), 4)
        self.assertEqual(sprite_finish.fit_columns(3, 10, 10, 8), 3)

    def test_impossible_sizes_are_reported(self):
        frames = [cutout(figure(arm=i)) for i in range(4)]
        with patch.object(sprite_finish, 'MAX_TEXTURE_SIDE', 40):
            report = sprite_finish.build(frames, 'idle', True, [100] * 4)[2]
        self.assertTrue(report['oversize'])

    def test_atlas_records_the_rate(self):
        frames = [cutout(figure(arm=i)) for i in range(3)]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sprite_finish.write(frames, 'idle', True, [42, 42, 42], root / 'a.png', root / 'a.json', 3, 24)
            meta = json.loads((root / 'a.json').read_text(encoding='utf-8'))['meta']
        self.assertEqual((meta['fps'], meta['frameCount']), (24, 3))


class Sheet(unittest.TestCase):
    def test_fixed_rate_uses_consecutive_frames_and_even_time(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_clip(root / 'clip.mp4', 25)
            game = (root / 'g.png', root / 'g.json')
            packed = idle_tool.make_sprite_sheet(root / 'clip.mp4', root / 's.png', 24, True, root / 't.png', 24, 'flat', 'idle', game, 24, 6)
            with Image.open(game[0]) as sheet:
                self.assertEqual(sheet.width, packed['game']['cellWidth'] * 6)
        self.assertEqual(packed['method'], 'exact')
        self.assertEqual(packed['indices'], list(range(24)))
        self.assertEqual(sum(packed['durationMs']), 1000)
        self.assertEqual(packed['game']['columns'], 6)

    def test_sheet_options_reject_bad_values(self):
        for bad in (dict(sheetFps=0), dict(sheetFps=61), dict(sheetFps=True), dict(sheetFps='24'), dict(sheetColumns=0), dict(sheetColumns=1.5)):
            with self.assertRaises(ValueError):
                idle_tool.sheet_options(bad)
        self.assertEqual(idle_tool.sheet_options(dict(sheetFps=36, sheetColumns=10)), (36, 10))
        self.assertEqual(idle_tool.sheet_options({}), (None, None))


class EffectRoom(unittest.TestCase):
    def barrel(self):
        a = np.zeros((400, 400, 4), np.uint8)
        a[160:300, 250:380] = (200, 200, 200, 255)
        a[200:216, 20:250] = (90, 90, 90, 255)
        buffer = io.BytesIO()
        Image.fromarray(a).save(buffer, format='PNG')
        return buffer.getvalue()

    def left_edge(self, **kw):
        out = np.asarray(Image.open(io.BytesIO(idle_tool.prepare_reference_image(self.barrel(), 512, 512, 30, **kw))).convert('RGB'), int)
        return int(np.nonzero(np.abs(out - 128).max(axis=2).max(axis=0) > 20)[0].min()), int(np.nonzero(np.abs(out - 128).max(axis=2).max(axis=0) > 20)[0].max())

    def test_more_canvas_on_the_barrel_side(self):
        plain, roomy = self.left_edge(), self.left_edge(effect_room=True)
        self.assertGreater(roomy[0], plain[0] + 10)
        self.assertLess(roomy[1], 512)

    def test_off_by_default_and_for_pixel_art(self):
        self.assertEqual(self.left_edge(), self.left_edge(effect_room=False))
        data = self.barrel()
        self.assertEqual(idle_tool.prepare_reference_image(data, 512, 512, 30, pixel_art=True, effect_room=True),
                         idle_tool.prepare_reference_image(data, 512, 512, 30, pixel_art=True))

    def test_prompts_do_not_mention_blasts_on_their_own(self):
        # Naming an effect, even to limit it, made H3 draw a larger one.
        for action in ('attack', 'cast', 'idle'):
            self.assertNotIn('muzzle flash', idle_tool.animation_prompt('', action, action == 'idle'))


class Route(CharacterTests):
    def setUp(self):
        super().setUp()
        self.approve()
        patcher = patch.object(server.engine, 'RESULT_ROOT', self.data / 'results')
        patcher.start()
        self.addCleanup(patcher.stop)
        uid = self.admin.get('/api/me').json['user']['id']
        folder = self.data / 'results' / 'done'
        folder.mkdir(parents=True)
        write_clip(folder / 'attack.mp4', 20)
        with self.connect() as con:
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)', ('done', uid, 'complete', 1, 1,
                        json.dumps(dict(jobType='video', animationType='attack', loop=False, frameCount=8)),
                        json.dumps(dict(video='/outputs/results/done/attack.mp4', rawVideo='/outputs/results/done/attack.mp4'))))
            con.commit()

    def extract(self, **kw):
        return self.post(self.admin, 'jobs/done/extract', **kw)

    def test_rate_and_columns_make_a_game_sheet(self):
        response = self.extract(frameCount=20, removeBackground=True, backgroundRemoval='flat', sheetFps=36, sheetColumns=5)
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['game']['columns'], 5)
        job = self.admin.get('/api/jobs/done').json
        self.assertEqual(len(job['exportSheets']), 4)
        game = next(k for k in job['exportSheets'] if k.endswith('_game'))
        self.assertEqual(job['exportSheetInfo'][game]['fps'], 36)
        for key in (game, game.replace('_game', '_atlas')):
            self.assertEqual(self.admin.get(job['exportSheets'][key]).status_code, 200, key)
        sources = self.admin.get('/api/jobs/done/frames').json['sources']
        self.assertFalse(any(s['key'].endswith('_atlas') for s in sources))
        chosen = next(s for s in sources if s['key'].endswith('_game'))
        self.assertEqual((chosen['columns'], chosen['count']), (5, 20))

    def test_viewer_lists_sheets_with_their_grid_and_atlas(self):
        self.assertEqual(self.extract(frameCount=20, removeBackground=True, backgroundRemoval='flat', sheetFps=36, sheetColumns=5).status_code, 200)
        data = self.admin.get('/api/jobs/done/sheets').json
        self.assertEqual(data['title'], 'attack')
        game = next(s for s in data['sheets'] if s['key'].endswith('_game'))
        self.assertEqual((game['columns'], game['rows'], game['count']), (5, 4, 20))
        self.assertTrue(game['label'].startswith('20프레임 게임용'))
        atlas = self.admin.get(game['atlas'])
        self.assertEqual(len(atlas.json['frames']), 20)
        plain = next(s for s in data['sheets'] if s['key'].endswith('_transparent'))
        self.assertEqual((plain['columns'], plain['rows']), (8, 3))
        self.assertNotIn('atlas', plain)
        self.assertEqual(self.admin.get(plain['url']).status_code, 200)

    def test_viewer_needs_a_login_and_a_finished_job(self):
        self.assertEqual(self.guest.get('/sprite-viewer').status_code, 401)
        self.assertEqual(self.guest.get('/api/jobs/done/sheets').status_code, 401)
        self.assertEqual(self.admin.get('/sprite-viewer').status_code, 200)
        self.assertEqual(self.admin.get('/api/jobs/missing/sheets').status_code, 400)

    def test_more_than_64_frames_is_allowed(self):
        self.assertEqual(self.extract(frameCount=129).status_code, 400)
        self.assertEqual(self.extract(frameCount=80).status_code, 200)

    def test_without_a_rate_nothing_extra_is_made(self):
        response = self.extract(frameCount=6, removeBackground=True, backgroundRemoval='flat')
        self.assertEqual(response.status_code, 200, response.json)
        self.assertIsNone(response.json['game'])
        self.assertEqual(len(self.admin.get('/api/jobs/done').json['exportSheets']), 2)

    def test_bad_rate_is_refused(self):
        self.assertEqual(self.extract(frameCount=6, removeBackground=True, backgroundRemoval='flat', sheetFps=99).status_code, 400)


if __name__ == '__main__':
    unittest.main()
