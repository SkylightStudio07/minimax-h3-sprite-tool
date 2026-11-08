import base64
import unittest

import idle_tool as engine
from tools import sprite_motion_cli as cli


class SpriteMotionCliTest(unittest.TestCase):
    def args(self, *extra):
        return cli.parse_args(['--image', 'a.png', '--output', 'out', *extra])

    def test_defaults_match_the_expected_batch_settings(self):
        payload = cli.build_payload(self.args(), b'png')
        self.assertEqual(base64.b64decode(payload['imageData']), b'png')
        self.assertEqual((payload['width'], payload['height'], payload['duration'], payload['frameCount']), (768, 768, 3, 8))
        self.assertEqual(payload['samplingMode'], engine.default_sampling_mode())
        self.assertTrue(payload['removeBackground'])
        self.assertEqual(payload['backgroundRemoval'], 'ai')
        self.assertNotIn('loop', payload)

    def test_no_background_removal_and_explicit_options(self):
        payload = cli.build_payload(self.args('--background', 'none', '--no-loop', '--seed', '7', '--mode', 'quality'), b'x')
        self.assertFalse(payload['removeBackground'])
        self.assertIs(payload['loop'], False)
        self.assertEqual((payload['seed'], payload['samplingMode']), (7, 'quality'))

    def test_invalid_sizes_are_rejected_before_any_gpu_work(self):
        for extra in (['--width', '700'], ['--width', '2048', '--height', '2048'], ['--seconds', '9'], ['--frames', '65']):
            with self.assertRaises(ValueError):
                cli.build_payload(self.args(*extra), b'x')


if __name__ == '__main__':
    unittest.main()
