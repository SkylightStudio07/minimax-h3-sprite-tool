"""Make a breathing loop and game sheet from one transparent still. Needs no GPU.

python tools/sprite_breathe_cli.py --image still.png --output out --neck 100 --axis 257 --half 66
--neck, --axis and --half are pixels in the still: the row the head ends on, the column of the body's center,
and half the torso's width. Writes breathe_<frames>f_<fps>fps.png and .json into --output.
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import sprite_breathe  # noqa: E402
import sprite_finish  # noqa: E402


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--image', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--neck', type=int, required=True, help='row of the neck line')
    p.add_argument('--axis', type=int, required=True, help='column of the body center')
    p.add_argument('--half', type=int, required=True, help='half width of the torso in pixels')
    p.add_argument('--frames', type=int, default=24, help='6 to 64')
    p.add_argument('--fps', type=int, default=12, help='1 to 60')
    p.add_argument('--columns', type=int, help='default keeps every side within 8192 pixels')
    args = p.parse_args(argv)
    if not 1 <= args.fps <= 60:
        raise SystemExit('--fps must be 1 to 60')
    with Image.open(args.image) as opened:
        still = opened.convert('RGBA')
    if still.getchannel('A').getextrema()[0] == 255:
        raise SystemExit('the image has no transparency; use a cut-out still')
    try:
        frames = sprite_breathe.loop(still, args.neck, args.axis, args.half, args.frames)
    except ValueError as error:
        raise SystemExit(str(error))
    args.output.mkdir(parents=True, exist_ok=True)
    stem = f'breathe_{args.frames}f_{args.fps}fps'
    paths = (args.output / f'{stem}.png', args.output / f'{stem}.json')
    game = sprite_finish.write(frames, 'idle', True, sprite_finish.uniform_ms(args.frames, args.fps), *paths, args.columns, args.fps)
    print(json.dumps(dict(sheet=str(paths[0].resolve()), atlas=str(paths[1].resolve()), frames=game['frameCount'], fps=args.fps,
                          columns=game['columns'], rows=game['rows'], cellWidth=game['cellWidth'], cellHeight=game['cellHeight']), indent=1))


if __name__ == '__main__':
    main()
