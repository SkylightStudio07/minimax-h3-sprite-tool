import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

import sprite_finish
from test_sprite_finish import cutout, figure
from tools import sprite_pack_cli


def built(action, frames, fps=24, loop=True):
    durations = sprite_finish.uniform_ms(len(frames), fps)
    sheet, layout, _ = sprite_finish.build(frames, action, loop, durations)
    return action, sheet, sprite_finish.atlas(f'{action}.png', action, loop, layout, durations, fps)


def cell(sheet, atlas, index):
    q = list(atlas['frames'].values())[index]['frame']
    return np.asarray(sheet.crop((q['x'], q['y'], q['x'] + q['w'], q['y'] + q['h'])))


class Pack(unittest.TestCase):
    def units(self):
        return [built('idle', [cutout(figure(arm=2)) for _ in range(3)]), built('attack', [cutout(figure(arm=a)) for a in (0, 50, 10, 0)], 36, False)]

    def test_actions_share_one_cell_and_anchor(self):
        results, manifest = sprite_finish.pack_actions(self.units())
        sizes = {(list(a['frames'].values())[0]['frame']['w'], list(a['frames'].values())[0]['frame']['h']) for _, _, a in results}
        self.assertEqual(sizes, {(manifest['cellWidth'], manifest['cellHeight'])})
        self.assertEqual({json.dumps(list(a['frames'].values())[0]['anchor']) for _, _, a in results}, {json.dumps(manifest['anchor'])})

    def test_the_body_lands_in_the_same_place_in_every_action(self):
        results, _ = sprite_finish.pack_actions(self.units())
        boxes = []
        for _, sheet, atlas in results:
            a = cell(sheet, atlas, 0)[:, :, :3]
            ys, xs = np.nonzero(np.all(a == (200, 40, 40), axis=2))
            boxes.append((xs.min(), xs.max(), ys.min(), ys.max()))
        self.assertEqual(boxes[0], boxes[1])

    def test_pixels_are_only_moved(self):
        action, sheet, atlas = built('idle', [cutout(figure(arm=4)) for _ in range(2)])
        results, _ = sprite_finish.pack_actions([(action, sheet, atlas), built('attack', [cutout(figure(arm=60)) for _ in range(2)], 36, False)])
        before = cell(sheet, atlas, 1)
        after = cell(results[0][1], results[0][2], 1)
        self.assertEqual(int((before[:, :, 3] > 0).sum()), int((after[:, :, 3] > 0).sum()))
        self.assertEqual({tuple(c) for c in before[before[:, :, 3] > 0]}, {tuple(c) for c in after[after[:, :, 3] > 0]})

    def test_timing_and_rate_survive(self):
        results, manifest = sprite_finish.pack_actions(self.units())
        attack = dict((n, a) for n, _, a in results)['attack']
        self.assertEqual([f['duration'] for f in attack['frames'].values()], sprite_finish.uniform_ms(4, 36))
        self.assertEqual((attack['meta']['fps'], attack['meta']['loop']), (36, False))
        self.assertEqual(manifest['actions']['attack']['fps'], 36)
        self.assertEqual(manifest['actions']['idle']['frameCount'], 3)

    def test_command_writes_every_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            inputs = []
            for name, sheet, atlas in self.units():
                sheet.save(root / f'{name}.png')
                (root / f'{name}.json').write_text(json.dumps(atlas), encoding='utf-8')
                inputs.append(str(root / f'{name}.json'))
            with contextlib.redirect_stdout(io.StringIO()):
                sprite_pack_cli.main(['--input', *inputs, '--output', str(root / 'out')])
            self.assertEqual(sorted(p.name for p in (root / 'out').iterdir()), ['attack.json', 'attack.png', 'idle.json', 'idle.png', 'pack.json'])
            with self.assertRaises(SystemExit):
                sprite_pack_cli.main(['--input', inputs[0], inputs[0], '--output', str(root / 'out')])


class Dropping(unittest.TestCase):
    def test_time_moves_to_the_frame_before(self):
        self.assertEqual(sprite_finish.drop_frames([5, 6, 7, 8], [10, 20, 30, 40], [2, 3]), ([5, 8], [60, 40]))

    def test_a_dropped_first_frame_loses_its_time(self):
        self.assertEqual(sprite_finish.drop_frames([5, 6], [10, 20], [1]), ([6], [20]))

    def test_nothing_to_drop(self):
        self.assertEqual(sprite_finish.drop_frames([5, 6], [10, 20], []), ([5, 6], [10, 20]))

    def test_bad_numbers(self):
        for drop in ([0], [3], [1, 2]):
            with self.assertRaises(ValueError):
                sprite_finish.drop_frames([5, 6], [10, 20], drop)


class Repair(unittest.TestCase):
    def frames(self, count=8):
        raw = [figure() for _ in range(count)]
        return raw, [cutout(f) for f in raw]

    def test_a_lost_body_is_refilled_from_its_own_frame(self):
        raw, cuts = self.frames()
        lit = np.asarray(raw[4]).copy()
        lit[(lit == (200, 40, 40)).all(axis=2)] = (250, 180, 90)
        raw[4] = Image.fromarray(lit)
        broken = np.array(cuts[4])
        broken[60:, :, 3] = 90
        cuts[4] = Image.fromarray(broken, 'RGBA')
        out = np.asarray(sprite_finish.repair_body(raw, cuts, floor=100)[4])
        self.assertEqual(out[75, 60, 3], 255)
        self.assertEqual(tuple(out[75, 60, :3]), (250, 180, 90), 'A lit body stays lit')
        self.assertEqual(out[105, 54, 3], 255, 'Thin feet below the floor line are kept without erosion')

    def test_background_stays_clear(self):
        raw, cuts = self.frames()
        broken = np.array(cuts[3])
        broken[..., 3] = (broken[..., 3] > 0) * 90
        cuts[3] = Image.fromarray(broken, 'RGBA')
        out = np.asarray(sprite_finish.repair_body(raw, cuts)[3])
        self.assertEqual(out[5, 5, 3], 0)

    def test_a_sound_clip_is_untouched(self):
        raw, cuts = self.frames()
        self.assertIs(sprite_finish.repair_body(raw, cuts)[2], cuts[2])

    def test_a_clip_that_keeps_changing_shape_is_left_alone(self):
        raw = [figure(x=i * 9) for i in range(8)]
        cuts = [cutout(f) for f in raw]
        self.assertTrue(all(a is b for a, b in zip(sprite_finish.repair_body(raw, cuts), cuts)))


if __name__ == '__main__':
    unittest.main()
