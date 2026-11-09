"""Give one unit's game sheets the same cell and foot anchor. Needs no GPU.

python tools/sprite_pack_cli.py --input idle_72f_24fps.json attack_73f_36fps.json --output pack
Each input JSON must sit next to the PNG it names. Writes <action>.png, <action>.json and pack.json.
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import sprite_finish  # noqa: E402

Image.MAX_IMAGE_PIXELS = None


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--input', type=Path, nargs='+', required=True, help='game sheet JSON files, one per action')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--columns', type=int, help='default keeps every side within 8192 pixels')
    args = p.parse_args(argv)
    actions, seen = [], set()
    for path in args.input:
        data = json.loads(path.read_text(encoding='utf-8'))
        name = next(iter(data['animations']))
        if name in seen:
            raise SystemExit(f'two inputs are both the {name} action')
        seen.add(name)
        actions.append((name, Image.open(path.parent / data['meta']['image']).convert('RGBA'), data))
    args.output.mkdir(parents=True, exist_ok=True)
    results, manifest = sprite_finish.pack_actions(actions, args.columns)
    for name, sheet, atlas in results:
        sheet.save(args.output / f'{name}.png', compress_level=6)
        (args.output / f'{name}.json').write_text(json.dumps(atlas, ensure_ascii=False, indent=1), encoding='utf-8')
    (args.output / 'pack.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
