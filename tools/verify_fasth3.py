"""Isolated real inference smoke test; never enables the production profile."""
import base64
import json
from pathlib import Path
import sqlite3
import sys
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import idle_tool as engine
import sprite_workflows
import requests

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    with sqlite3.connect('file:data/team.sqlite3?mode=ro', uri=True) as con:
        active = con.execute("SELECT count(*) FROM jobs WHERE state NOT IN ('complete','error','cancelled')").fetchone()[0]
    queue = requests.get(engine.COMFY_URL+'/queue', timeout=10).json()
    if active or queue['queue_running'] or queue['queue_pending']:
        raise RuntimeError('Queue busy; retry when idle')
    job = 'fasth3-validation-20261016-rigid-idle'
    hair_only = '--hair-only' in sys.argv
    if hair_only:
        job += '-hair-only'
    source = engine.ROOT/'outputs/background-validation-20261015/flat-color-0.5-transparent.png'
    payload = dict(workflowId='fasth3-sprite', width=512, height=512,
                   duration=3, seed=42, animationType='idle', loop=True,
                   frameCount=8, removeBackground=True, stabilize=True,
                   filename=source.name,
                   imageData=base64.b64encode(source.read_bytes()).decode())
    if hair_only:
        payload.update(motionStrength='low', prompt=(
            'Only the loose hair tips and outer sleeve cuffs flutter gently in a light breeze. '
            'The face, head position, shoulders, chest, waist and entire jacket front remain completely still, '
            'identical to the reference image in every frame. Animate only these loose edges.'))
    engine.JOBS[job] = {'state':'queued'}
    original = sprite_workflows.status
    def local_status(root):
        profiles = original(root)
        profiles[1]['ready'] = profiles[1]['installed']
        return profiles
    started = time.monotonic()
    print('Starting isolated 512x512 / 3s / 8-step test', flush=True)
    with patch.object(sprite_workflows, 'status', local_status):
        engine.run_job(job, payload)
    result = dict(engine.JOBS[job], elapsedSeconds=round(time.monotonic()-started, 2))
    target = engine.RESULT_ROOT/job/'validation.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    sys.exit(0 if result['state']=='complete' else 1)
