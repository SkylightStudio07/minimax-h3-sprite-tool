"""Generate a character motion video and sprite sheet from one image, for use by other projects.

Runs the same pipeline as the site, but needs no account and never reaches the public gallery.
Exits once the files are in --output. Progress is written to <output>/status.json.
"""
import argparse
import base64
import json
import msvcrt
import shutil
import sqlite3
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psutil
import requests
from PIL import Image

import idle_tool as engine

MIN_FREE_RAM_GB = 2.0
LOCK_PATH = ROOT / 'data' / 'agent-cli.lock'
DONE_STATES = ('complete', 'error')


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image', required=True, type=Path, help='character image')
    p.add_argument('--output', required=True, type=Path, help='folder for the results')
    p.add_argument('--action', default='idle', choices=sorted(engine.ANIMATION_DEFAULTS))
    p.add_argument('--prompt', default='', help='movement description; empty uses the default for the action')
    p.add_argument('--mode', default=None, choices=engine.SAMPLING_MODES, help='default: turbo-v4')
    p.add_argument('--seconds', type=float, default=3, help='3 to 5')
    p.add_argument('--width', type=int, default=768)
    p.add_argument('--height', type=int, default=768)
    p.add_argument('--frames', type=int, default=8, help='sprite sheet frames, 2 to 128')
    p.add_argument('--fps', type=int, help='fixed sheet frame rate, 1 to 60; uses consecutive frames instead of picking by motion')
    p.add_argument('--columns', type=int, help='game sheet columns; default keeps every side within 8192 pixels')
    p.add_argument('--background', choices=['ai', 'ai-smooth', 'ai-sparks', 'ai-soft', 'flat', 'none'],
                   help='default: ai-soft for attack and cast, which keeps blasts and smoke; ai otherwise')
    p.add_argument('--subject', default='human', choices=['human', *engine.SUBJECT_DEFAULTS])
    p.add_argument('--strength', default='normal', choices=sorted(engine.MOTION_PROMPTS))
    p.add_argument('--facing', default='preserve', choices=sorted(engine.FACING_PROMPTS))
    p.add_argument('--padding', type=int, choices=[0, 10, 20, 30, 40, 50, 58], help='margin percent for wide motion; default 30 for attack and cast, otherwise 10')
    p.add_argument('--loop', action=argparse.BooleanOptionalAction, default=None, help='default depends on the action')
    p.add_argument('--seed', type=int, default=None)
    p.add_argument('--wait', type=int, default=3600, help='seconds to wait for other GPU work')
    p.add_argument('--force', action='store_true', help='generate even if --output already holds a result')
    return p.parse_args(argv)


def build_payload(args, image_bytes):
    if args.width % 32 or args.height % 32 or min(args.width, args.height) < 256 or args.width * args.height > 1_100_000:
        raise ValueError('width and height must be multiples of 32, at least 256, and at most 1.1 megapixels in total')
    if not 3 <= args.seconds <= 5 or not 2 <= args.frames <= 128:
        raise ValueError('seconds must be 3 to 5 and frames 2 to 128')
    if len(args.prompt) > 4000:
        raise ValueError('prompt must be 4000 characters or fewer')
    background = args.background or ('ai-soft' if args.action in ('attack', 'cast') else 'ai')
    payload = dict(
        imageData=base64.b64encode(image_bytes).decode('ascii'), filename='reference.png', jobType='video',
        workflowId='standard', samplingMode=args.mode or engine.default_sampling_mode(), animationType=args.action,
        prompt=args.prompt, duration=args.seconds, width=args.width, height=args.height, frameCount=args.frames,
        removeBackground=background != 'none', backgroundRemoval='flat' if background == 'none' else background,
        subjectType=args.subject, motionStrength=args.strength, facing=args.facing, motionPadding=args.padding if args.padding is not None else (30 if args.action in ('attack', 'cast') else 10),
        blinkMode='none', stabilize=True, optimizeLoop=True,
    )
    if args.fps is not None:
        payload['sheetFps'] = args.fps
    if args.columns is not None:
        payload['sheetColumns'] = args.columns
    if args.loop is not None:
        payload['loop'] = args.loop
    if args.seed is not None:
        payload['seed'] = args.seed
    return payload


def save_json(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def report(output, **fields):
    save_json(output / 'status.json', dict(fields, updated=time.strftime('%Y-%m-%dT%H:%M:%S')))
    print('STATUS', json.dumps(fields, ensure_ascii=False), flush=True)


def site_jobs_active():
    database = ROOT / 'data' / 'team.sqlite3'
    if not database.is_file():
        return 0
    connection = sqlite3.connect(f'file:{database.as_posix()}?mode=ro', uri=True, timeout=10)
    try:
        return connection.execute("SELECT count(*) FROM jobs WHERE state NOT IN ('complete','error','cancelled')").fetchone()[0]
    finally:
        connection.close()


def gpu_blocker():
    if psutil.virtual_memory().available / 1024 ** 3 < MIN_FREE_RAM_GB:
        return f'less than {MIN_FREE_RAM_GB:g} GB of RAM free'
    if site_jobs_active():
        return 'the site queue has active jobs'
    queue = requests.get(engine.COMFY_URL + '/queue', timeout=20).json()
    if queue.get('queue_running') or queue.get('queue_pending'):
        return 'ComfyUI is busy'
    return None


def wait_for_turn(output, limit):
    deadline = time.time() + limit
    LOCK_PATH.parent.mkdir(exist_ok=True)
    handle = open(LOCK_PATH, 'a+b')
    while True:
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            break
        except OSError:
            if time.time() > deadline:
                raise TimeoutError('another sprite_motion_cli run held the GPU for too long')
            report(output, state='waiting', message='another sprite_motion_cli run is using the GPU')
            time.sleep(15)
    engine.start_comfy()
    while True:
        blocker = gpu_blocker()
        if not blocker:
            return handle
        if time.time() > deadline:
            raise TimeoutError('gave up waiting: ' + blocker)
        report(output, state='waiting', message=blocker)
        time.sleep(15)


def preflight(mode):
    status = engine.status_payload()
    if not status['modelsReady'] or not status['licenseConfirmed']:
        raise RuntimeError('MiniMax H3 models or license confirmation are missing in G:/Minimax')
    if mode == 'turbo-v4' and not status['turboV4']:
        raise RuntimeError('Turbo v4 LoRA is not installed; pass --mode quality')


def run(job_id, payload, output):
    engine.RESULT_ROOT = engine.OUTPUT_ROOT / 'agent-cli'
    engine.JOBS[job_id] = dict(state='queued', message='starting')
    worker = threading.Thread(target=engine.run_job, args=(job_id, payload), daemon=True)
    worker.start()
    last = None
    while worker.is_alive():
        current = (engine.JOBS[job_id].get('state'), engine.JOBS[job_id].get('message'))
        if current != last:
            report(output, state=current[0], message=current[1], jobId=job_id)
            last = current
        time.sleep(2)
    worker.join()
    return engine.JOBS[job_id]


def publish(job, job_id, output, payload, seconds):
    source = engine.RESULT_ROOT / job_id
    action = job['animationType']
    files = {'video': f'{action}.mp4', 'rawVideo': f'{action}_raw.mp4', 'spriteSheet': f'{action}_sprite_sheet.png',
             'transparentSheet': f'{action}_transparent.png', 'gameSheet': f'{action}_game.png', 'gameAtlas': f'{action}_game.json',
             'promptRecord': 'generation_prompt.json'}
    copied = {}
    for key, name in files.items():
        if (source / name).is_file():
            shutil.copy2(source / name, output / name)
            copied[key] = str((output / name).resolve())
    count = int(job['frameCount'])
    columns = min(count, 8)
    with Image.open(output / files['spriteSheet']) as sheet:
        width, height = sheet.size
    rows = (count + columns - 1) // columns
    result = dict(status='complete', files=copied, frameCount=count, columns=columns, rows=rows,
                  cellWidth=width // columns, cellHeight=height // rows, loop=job['loop'], seed=job['seed'],
                  mode=payload['samplingMode'], action=action, backgroundRemoval=job.get('backgroundRemoval'),
                  warning=job.get('warning'), sheetTimingMs=job.get('sheetTimingMs'), sheetSelection=job.get('sheetSelection'), elapsedSeconds=round(seconds, 1))
    save_json(output / 'result.json', result)
    return result


def main(argv=None):
    args = parse_args(argv)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    existing = output / 'result.json'
    if existing.is_file() and not args.force:
        print(existing.read_text(encoding='utf-8'))
        print('ALREADY_GENERATED: pass --force to generate again', flush=True)
        return 0
    if not args.image.is_file():
        raise FileNotFoundError(args.image)
    payload = build_payload(args, args.image.read_bytes())
    preflight(payload['samplingMode'])
    lock = wait_for_turn(output, args.wait)
    try:
        started = time.time()
        job_id = time.strftime('%Y%m%d-%H%M%S-') + output.name[:40]
        job = run(job_id, payload, output)
        if job.get('state') != 'complete':
            report(output, state='error', message=job.get('message'), jobId=job_id)
            print('FAILED', job.get('message'), flush=True)
            return 1
        result = publish(job, job_id, output, payload, time.time() - started)
        report(output, state='complete', message='done', jobId=job_id)
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        print('COMPLETE', flush=True)
        return 0
    finally:
        lock.close()


if __name__ == '__main__':
    sys.exit(main())
