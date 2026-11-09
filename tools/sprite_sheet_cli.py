"""Cut a game sheet from a finished video at a fixed frame count and frame rate. Needs no GPU.

python tools/sprite_sheet_cli.py --video idle.mp4 --output out --action idle --frames 72 --fps 24
Writes <action>_<frames>f_<fps>fps.png and .json into --output.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import idle_tool as engine  # noqa: E402

ONE_SHOTS = ('attack', 'cast', 'hit', 'death', 'jump')


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--video', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--action', required=True, help='idle, walk, run, attack, cast, hit, death, jump or custom')
    p.add_argument('--frames', type=int, required=True, help='2 to 128; a shorter clip gives fewer')
    p.add_argument('--fps', type=int, required=True, help='1 to 60')
    p.add_argument('--columns', type=int, help='default keeps every side within 8192 pixels')
    p.add_argument('--background', choices=['ai', 'ai-smooth', 'ai-sparks', 'ai-soft', 'flat'],
                   help='default: ai-soft for attack and cast, otherwise ai')
    p.add_argument('--loop', action=argparse.BooleanOptionalAction, default=None, help='default depends on the action')
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if not 2 <= args.frames <= 128:
        raise SystemExit('frames must be 2 to 128')
    engine.sheet_options(dict(sheetFps=args.fps, sheetColumns=args.columns))
    if not args.video.is_file():
        raise SystemExit(f'video not found: {args.video}')
    loop = args.loop if args.loop is not None else args.action not in ONE_SHOTS
    mode = args.background or ('ai-soft' if args.action in ('attack', 'cast') else 'ai')
    args.output.mkdir(parents=True, exist_ok=True)
    stem = f'{args.action}_{args.frames}f_{args.fps}fps'
    paths = (args.output / f'{stem}.png', args.output / f'{stem}.json')
    with tempfile.TemporaryDirectory() as folder:
        scratch = Path(folder)
        packed = engine.make_sprite_sheet(args.video, scratch / 'sheet.png', args.frames, loop, scratch / 'cut.png', 24, mode,
                                          args.action, paths, args.fps, args.columns)
    game = packed['game']
    if not game:
        raise SystemExit('could not build a game sheet from this video')
    print(json.dumps(dict(sheet=str(paths[0].resolve()), atlas=str(paths[1].resolve()), frames=game['frameCount'], fps=args.fps,
                          columns=game['columns'], rows=game['rows'], cellWidth=game['cellWidth'], cellHeight=game['cellHeight'],
                          clippedFrames=game['edgeContactFrames'], oversize=game['oversize']), indent=1))


if __name__ == '__main__':
    main()
