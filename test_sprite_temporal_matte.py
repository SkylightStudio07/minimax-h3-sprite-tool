import unittest

import numpy as np

import sprite_temporal_matte as matte


def scene(count=9, size=96, shift=None, jitter=0):
    rng = np.random.default_rng(3)
    raws, cuts = [], []
    for frame in range(count):
        raw = np.full((size, size, 3), 128, np.uint8)
        left = 30 + (shift(frame) if shift else 0)
        for row in range(20, 76):
            raw[row, left:left + 30] = (40 + row, 180 - row, 90)
        cut = np.dstack((raw, np.zeros((size, size), np.uint8)))
        for row in range(20, 76):
            wobble = int(rng.integers(-jitter, jitter + 1)) if jitter else 0
            cut[row, left - wobble:left + 30 + wobble, 3] = 255
        cut[cut[:, :, 3] == 0] = 0
        raws.append(raw)
        cuts.append(cut)
    return raws, cuts


class TemporalMatteTest(unittest.TestCase):
    def test_static_edge_flicker_is_reduced(self):
        raws, cuts = scene(jitter=2)
        out = matte.stabilize(raws, cuts)
        self.assertLess(matte.static_flicker(raws, out), matte.static_flicker(raws, cuts) * .6)

    def test_interior_is_untouched(self):
        raws, cuts = scene(jitter=2)
        out = matte.stabilize(raws, cuts)
        for before, after in zip(cuts, out):
            np.testing.assert_array_equal(before[30:66, 40:52], after[30:66, 40:52])

    def test_clean_input_stays_clean(self):
        raws, cuts = scene()
        for before, after in zip(cuts, matte.stabilize(raws, cuts)):
            self.assertLessEqual(np.mean(before[:, :, 3] != after[:, :, 3]), .002)

    def test_moving_subject_does_not_ghost(self):
        raws, cuts = scene(shift=lambda frame: frame * 3)
        out = matte.stabilize(raws, cuts)
        for frame, after in enumerate(out):
            left = 30 + frame * 3
            self.assertEqual(int(after[40:60, :max(left - 6, 0), 3].max(initial=0)), 0)

    def test_transient_effect_keeps_its_own_matte(self):
        raws, cuts = scene()
        raws[4] = raws[4].copy()
        raws[4][10:14, 70:90] = (255, 240, 120)
        cuts[4] = cuts[4].copy()
        cuts[4][10:14, 70:90] = (255, 240, 120, 255)
        out = matte.stabilize(raws, cuts)
        self.assertGreater(np.mean(out[4][10:14, 72:88, 3]), 200)

    def test_refine_closes_notches_without_touching_separate_effects(self):
        raws, cuts = scene(count=1)
        raw, cut = raws[0], cuts[0].copy()
        cut[40, 30:32, 3] = 0
        raw[5:8, 80:90] = (250, 240, 120)
        cut[5:8, 80:90] = (250, 240, 120, 90)
        out = matte.refine_contour(raw, cut)
        self.assertGreater(int(out[40, 31, 3]), 127)
        np.testing.assert_array_equal(out[5:8, 80:90], cut[5:8, 80:90])

    def test_smooth_selected_cuts_each_needed_frame_once(self):
        from PIL import Image
        raws, cuts = scene(count=8, jitter=1)
        frames = [Image.fromarray(r) for r in raws]
        calls = []
        lookup = {id(f): c for f, c in zip(frames, cuts)}

        def cut(frame):
            calls.append(id(frame))
            return Image.fromarray(lookup[id(frame)])
        out = matte.smooth_selected(frames, [2, 3], cut, loop=False)
        self.assertEqual(len(out), 2)
        self.assertEqual(len(calls), len(set(calls)))
        self.assertEqual(out[0].mode, 'RGBA')

    def test_length_mismatch_is_rejected(self):
        raws, cuts = scene(count=3)
        with self.assertRaises(ValueError):
            matte.stabilize(raws, cuts[:2])


if __name__ == '__main__':
    unittest.main()
