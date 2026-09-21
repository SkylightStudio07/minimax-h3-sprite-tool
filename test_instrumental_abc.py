import unittest

from tools.instrumental_abc import mute_vocal_abc


class InstrumentalAbcTests(unittest.TestCase):
    def test_mutes_vocal_notes_and_preserves_chords_bars_and_instrument(self):
        source = (
            'X:1\r\n'
            'M:4/4\r\n'
            'L:1/16\r\n'
            'V: Vocal clef=treble name="Vocal Melody"\r\n'
            'V: Ins clef=treble name="Ins Melody"\r\n'
            'K:Em\r\n'
            '% verse\r\n'
            'V: Vocal\r\n'
            '"Em"e2f2g4f2d2e4|"C"[CEG]16-|\r\n'
            'V: Ins\r\n'
            'e8b8|c16|\r\n'
        )
        result = mute_vocal_abc(source)
        self.assertEqual(result.vocal_lines, 1)
        self.assertGreater(result.muted_notes, 0)
        self.assertIn('V: Vocal clef=treble name="Vocal Melody"', result.abc)
        self.assertIn('"Em"z2z2z4z2z2z4|"C"z16|', result.abc)
        self.assertIn('V: Ins\r\ne8b8|c16|', result.abc)
        self.assertEqual(result.abc.count('|'), source.count('|'))

    def test_removes_grace_notes_and_ties_without_changing_metric_length(self):
        source = (
            'X:1\nM:4/4\nL:1/8\n'
            'V: Vocal clef=treble\nV: Ins clef=treble\nK:C\n'
            'V: Vocal\n{abc}^C2-D2|z4|\n'
            'V: Ins\nZ2|\n'
        )
        result = mute_vocal_abc(source)
        self.assertIn('V: Vocal\nz2z2|z4|', result.abc)
        self.assertNotIn('-', result.abc.split('V: Ins', 1)[0])

    def test_rejects_non_native_score_without_vocal_blocks(self):
        with self.assertRaisesRegex(ValueError, 'no native Vocal'):
            mute_vocal_abc('X:1\nM:4/4\nK:C\nCDEF|\n')


if __name__ == '__main__':
    unittest.main()
