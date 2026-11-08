"""Regression: reviewed native clips exceed the generation form's 64 frames."""
import io
import json
from unittest.mock import patch

from PIL import Image, ImageDraw
import character_studio
from test_character_studio import CharacterTests


class NativeGalleryTests(CharacterTests):
    def test_native_73_frame_gif_and_editor_keep_timing_and_last_cell(self):
        self.approve()
        folder = self.fixture()
        sheet = Image.new('RGBA', (128, 160))
        draw = ImageDraw.Draw(sheet)
        for i in range(73):
            x, y = i % 8 * 16, i // 8 * 16
            draw.rectangle((x + 2, y + 2, x + 12, y + 12), fill=(i * 3, 50, 100, 255))
        sheet.save(folder / 'sheet.png')
        timing = [42 if i % 3 else 41 for i in range(73)]
        with self.connect() as con:
            result = dict(spriteSheet='/outputs/results/sprite/sheet.png', frameCount=73, sheetTimingMs=timing)
            con.execute("UPDATE jobs SET result=? WHERE id='sprite'", (json.dumps(result),))
            con.commit()
        with patch.object(character_studio.engine, 'RESULT_ROOT', self.data / 'results'):
            response = self.admin.get('/api/jobs/sprite/sheet.gif?source=spriteSheet')
            self.assertEqual(response.status_code, 200, response.json)
            with Image.open(io.BytesIO(response.data)) as gif:
                self.assertEqual(gif.n_frames, 73)
                self.assertEqual(gif.size, (16, 16))
                self.assertAlmostEqual(sum(gif.seek(i) or gif.info['duration'] for i in range(73)), sum(timing), delta=10)
                self.assertEqual(gif.convert('RGB').getpixel((4, 4)), (216, 50, 100))
            response = self.post(self.admin, 'jobs/sprite/frames', source='spriteSheet')
            self.assertEqual(response.status_code, 201, response.json)
            doc = self.admin.get('/api/frames/' + response.json['id']).json
            self.assertEqual(len(doc['frames']), 73)
            self.assertEqual([f['durationMs'] for f in doc['frames']], timing)
