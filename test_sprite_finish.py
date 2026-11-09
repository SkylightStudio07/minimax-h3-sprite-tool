import base64
import io
import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path
from types import SimpleNamespace

import av
import numpy as np
from PIL import Image

import idle_tool
import sprite_finish


def figure(arm=0, leg=0, y=0, x=0, size=128):
    """A body with one swinging arm and two legs on a flat gray background, returned as RGB."""
    a = np.full((size, size, 3), 128, np.uint8)
    cx = 60 + x
    a[30 + y:80 + y, cx - 8:cx + 8] = (200, 40, 40)
    a[40 + y:46 + y, cx + 8:cx + 8 + arm] = (40, 40, 200)
    a[80 + y:110 + y, cx - 8 + leg:cx - 1 + leg] = (20, 120, 20)
    a[80 + y:110 + y, cx + 1 - leg:cx + 8 - leg] = (240, 200, 20)
    return Image.fromarray(a)


def cutout(image):
    a = np.asarray(image.convert('RGB'))
    alpha = (np.max(np.abs(a.astype(int) - 128), axis=2) > 8).astype(np.uint8) * 255
    return Image.fromarray(np.dstack((a, alpha)))


class Picking(unittest.TestCase):
    def test_one_shot_keeps_first_last_and_the_peak_even_when_it_is_brief(self):
        arms = [0] * 25 + [10, 26, 44, 26, 10] + [0] * 30
        frames = [figure(arm=a) for a in arms]
        picked = sprite_finish.pick(frames, 6, 'attack', False)
        self.assertEqual(picked['method'], 'key-poses')
        self.assertEqual(len(picked['indices']), 6)
        self.assertIn(0, picked['indices'])
        self.assertIn(len(arms) - 1, picked['indices'])
        self.assertIn(27, picked['indices'])
        self.assertEqual(picked['indices'], sorted(set(picked['indices'])))
        self.assertNotIn(27, [i * len(arms) // 6 for i in range(6)], 'Even spacing would have missed this peak')

    def test_durations_keep_the_real_length(self):
        self.assertEqual(sum(sprite_finish.durations_ms([0, 10, 40], 48, 24)), 2000)
        self.assertEqual(sprite_finish.durations_ms([0, 10, 40], 48, 24)[1], 1250)

    def test_gait_samples_exactly_one_stride(self):
        period = 12
        legs = [round(10 * np.sin(2 * np.pi * i / period)) for i in range(60)]
        frames = [figure(leg=v, arm=(i % period) // 2) for i, v in enumerate(legs)]
        picked = sprite_finish.pick(frames, 8, 'run', True)
        self.assertEqual(picked['method'], 'one-stride')
        self.assertEqual(picked['end'] - picked['indices'][0], period)
        self.assertEqual(len(picked['indices']), 8)

    def test_gait_without_a_repeat_falls_back_to_even(self):
        frames = [figure(arm=i, x=i // 3) for i in range(40)]
        self.assertEqual(sprite_finish.pick(frames, 8, 'walk', True)['method'], 'even')

    def test_idle_is_left_evenly_spaced(self):
        frames = [figure(arm=i % 3) for i in range(30)]
        self.assertEqual(sprite_finish.pick(frames, 6, 'idle', True), dict(indices=[0, 5, 10, 15, 20, 25], end=30, method='even'))


class Sheet(unittest.TestCase):
    def test_ground_line_is_shared_and_pixels_are_only_moved(self):
        frames = [cutout(figure(y=y)) for y in (0, 2, -1, 1)]
        sheet, layout, report = sprite_finish.build(frames, 'idle', True, [100] * 4)
        bottoms = []
        cell_w, cell_h = layout['cellWidth'], layout['cellHeight']
        for i in range(4):
            cell = sheet.crop((i * cell_w, 0, (i + 1) * cell_w, cell_h))
            bottoms.append(cell.getchannel('A').getbbox()[3])
            colors = {tuple(c) for c in np.asarray(cell)[np.asarray(cell)[:, :, 3] > 0][:, :3]}
            self.assertEqual(colors, {(200, 40, 40), (20, 120, 20), (240, 200, 20)}, 'No resampling means no new colors')
        self.assertEqual(len(set(bottoms)), 1)
        self.assertEqual(bottoms[0], layout['pivotY'])
        self.assertLess(cell_w, 128)

    def test_a_real_leap_is_not_flattened(self):
        frames = [cutout(figure()), cutout(figure()), cutout(figure(y=-24)), cutout(figure())]
        _, _, report = sprite_finish.build(frames, 'attack', False, [100] * 4)
        self.assertEqual(report['shifts'][2], [0, 0])

    def test_jump_keeps_its_height(self):
        frames = [cutout(figure(y=y)) for y in (0, -4, -8, -4)]
        _, _, report = sprite_finish.build(frames, 'jump', False, [100] * 4)
        self.assertTrue(all(s == [0, 0] for s in report['shifts']))

    def test_walk_drift_is_removed_but_not_for_a_lunge(self):
        frames = [cutout(figure(x=i * 2, leg=(i % 2) * 3)) for i in range(8)]
        centers = lambda report: [sprite_finish.measure(f)['center'] + s[0] for f, s in zip(frames, report['shifts'])]
        walk = sprite_finish.build(frames, 'walk', True, [100] * 8)[2]
        self.assertLess(np.ptp(centers(walk)), 4)
        lunge = sprite_finish.build(frames, 'attack', False, [100] * 8)[2]
        self.assertTrue(all(s[0] == 0 for s in lunge['shifts']))

    def test_clipped_frames_are_reported(self):
        wide = figure(arm=70)
        report = sprite_finish.build([cutout(figure()), cutout(wide)], 'attack', False, [100, 100])[2]
        self.assertEqual(report['edgeContactFrames'], [1])

    def test_atlas_matches_the_sheet(self):
        frames = [cutout(figure(arm=i)) for i in range(10)]
        durations = list(range(50, 150, 10))
        with tempfile.TemporaryDirectory() as folder:
            png, data = Path(folder) / 'attack_game.png', Path(folder) / 'attack_game.json'
            report = sprite_finish.write(frames, 'attack', False, durations, png, data)
            atlas = json.loads(data.read_text(encoding='utf-8'))
            with Image.open(png) as sheet:
                self.assertEqual(sheet.size, (atlas['meta']['size']['w'], atlas['meta']['size']['h']))
                self.assertEqual(sheet.size, (report['cellWidth'] * 8, report['cellHeight'] * 2))
        self.assertEqual(atlas['meta']['image'], 'attack_game.png')
        self.assertEqual(atlas['animations']['attack'], [f'attack_{i:02d}' for i in range(10)])
        last = atlas['frames']['attack_09']
        self.assertEqual((last['frame']['x'], last['frame']['y']), (report['cellWidth'], report['cellHeight']))
        self.assertEqual(last['duration'], 140)
        self.assertLessEqual(last['pivot']['y'], 1)

    def test_no_character_is_an_error_not_a_blank_sheet(self):
        with self.assertRaises(ValueError):
            sprite_finish.build([Image.new('RGBA', (32, 32)), Image.new('RGBA', (32, 32))], 'idle', True, [100, 100])


class Pipeline(unittest.TestCase):
    def video(self, path, arms):
        with av.open(str(path), 'w') as out:
            stream = out.add_stream('libx264', rate=24)
            stream.width = stream.height = 128
            stream.pix_fmt = 'yuv420p'
            stream.options = {'crf': '12'}
            for arm in arms:
                for packet in stream.encode(av.VideoFrame.from_image(figure(arm=arm))):
                    out.mux(packet)
            for packet in stream.encode():
                out.mux(packet)

    def test_without_an_action_the_sheet_is_as_before(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.video(root / 'clip.mp4', [0] * 10 + [30] + [0] * 13)
            packed = idle_tool.make_sprite_sheet(root / 'clip.mp4', root / 'sheet.png', 6, False)
        self.assertEqual(packed['method'], 'even')
        self.assertIsNone(packed['game'])

    def test_one_shot_writes_a_game_sheet_with_real_timing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.video(root / 'clip.mp4', [0] * 20 + [14, 30, 44, 30, 14] + [0] * 23)
            game = (root / 'attack_game.png', root / 'attack_game.json')
            packed = idle_tool.make_sprite_sheet(root / 'clip.mp4', root / 'sheet.png', 6, False, root / 'cut.png', 24, 'flat', 'attack', game)
            self.assertTrue(game[0].is_file() and game[1].is_file() and (root / 'cut.png').is_file())
            with Image.open(root / 'sheet.png') as sheet:
                self.assertEqual(sheet.size, (128 * 6, 128))
        self.assertEqual(packed['method'], 'key-poses')
        self.assertEqual(sum(packed['durationMs']), 2000)
        self.assertEqual(packed['game']['durationMs'], packed['durationMs'])

    def test_a_failed_game_sheet_does_not_fail_the_job(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.video(root / 'clip.mp4', [0, 4, 8, 12, 8, 4, 0, 0])
            game = (root / 'g.png', root / 'g.json')
            with unittest.mock.patch.object(sprite_finish, 'write', side_effect=ValueError('boom')):
                packed = idle_tool.make_sprite_sheet(root / 'clip.mp4', root / 'sheet.png', 4, True, root / 'cut.png', 24, 'flat', 'idle', game)
            self.assertIsNone(packed['game'])
            self.assertTrue((root / 'cut.png').is_file())
            self.assertFalse(game[0].exists())

    def job(self, root, **extra):
        buffer = io.BytesIO()
        Image.new('RGBA', (256, 256), (70, 80, 120, 255)).save(buffer, format='PNG')
        payload = dict(imageData=base64.b64encode(buffer.getvalue()).decode(), width=256, height=256, duration=3, seed=1, animationType='attack', loop=False,
                       stabilize=False, optimizeLoop=False, frameCount=6, **extra)
        post = SimpleNamespace(ok=True, json=lambda: {'prompt_id': 'fake'})
        get = SimpleNamespace(json=lambda: {'fake': {'status': {'status_str': 'success', 'completed': True}}})
        updates = []
        with unittest.mock.patch.object(idle_tool, 'RESULT_ROOT', root / 'results'), unittest.mock.patch.object(idle_tool, 'upload_image', return_value='f.png'), \
                unittest.mock.patch.object(idle_tool, 'find_saved_video', return_value=root / 'clip.mp4'), unittest.mock.patch.object(idle_tool.requests, 'post', return_value=post), \
                unittest.mock.patch.object(idle_tool.requests, 'get', return_value=get), unittest.mock.patch.object(idle_tool, 'update_job', side_effect=lambda jid, **kw: updates.append(kw)):
            idle_tool.run_job('job', payload)
        return updates[-1]

    def test_job_publishes_the_game_sheet_and_key_pose_timing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.video(root / 'clip.mp4', [0] * 20 + [14, 30, 44, 30, 14] + [0] * 23)
            result = self.job(root, removeBackground=True, backgroundRemoval='flat')
            self.assertEqual(result['state'], 'complete', result)
            self.assertEqual(result['gameSheet'], '/outputs/results/job/attack_game.png')
            self.assertEqual(result['gameAtlas'], '/outputs/results/job/attack_game.json')
            self.assertTrue((root / 'results/job/attack_game.json').is_file())
        self.assertEqual(result['sheetSelection'], 'key-poses')
        self.assertEqual(sum(result['sheetTimingMs']), 2000)

    def test_job_without_transparency_has_no_game_sheet(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.video(root / 'clip.mp4', [0] * 20 + [14, 30, 44, 30, 14] + [0] * 23)
            result = self.job(root, removeBackground=False)
        self.assertEqual(result['state'], 'complete', result)
        self.assertIsNone(result['gameSheet'])

    def test_pixel_job_gets_a_game_sheet_too(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.video(root / 'clip.mp4', [0] * 20 + [16, 32, 44, 32, 16] + [0] * 23)
            result = self.job(root, removeBackground=True, backgroundRemoval='flat', pixelOutput=True, combatEffect='none')
        self.assertEqual(result['state'], 'complete', result)
        self.assertEqual(result['sheetSelection'], 'key-poses')
        self.assertTrue(result['gameSheet'])


if __name__ == '__main__':
    unittest.main()
