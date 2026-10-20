#!/usr/bin/env python3
"""Opt-in failure injection into Planet's owned H2O unit; no desktop input."""
import argparse
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.model_runtime import health,ready


def request(text,timeout=180):
    start=time.monotonic()
    process=subprocess.run([sys.executable,str(ROOT/'scripts/bridge.py'),text],
                           capture_output=True,text=True,timeout=timeout)
    events=[json.loads(line) for line in process.stdout.splitlines() if line.startswith('{')]
    return events,round(time.monotonic()-start,3),process.stdout+process.stderr


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tag',required=True);args=parser.parse_args()
    if not args.tag.replace('-','').isalnum():parser.error('Use a simple tag.')
    out=ROOT/'output/runtime'/args.tag
    out.mkdir(parents=True,exist_ok=False)
    rows=[]
    def record(case,passed,**fields):
        row=dict(case=case,passed=passed,**fields);rows.append(row)
        (out/'results.json').write_text(json.dumps(rows,indent=2))
        print(json.dumps(row),flush=True)
        if not passed:raise AssertionError(case)
    with (ROOT/'.planet-benchmark.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        record('runtime-enabled',subprocess.check_output(
            ['systemctl','--user','is-enabled','planet-models.service'],text=True).strip()=='enabled')
        if not ready(health()):raise RuntimeError('Begin with a healthy resident pair.')
        subprocess.run(['systemctl','--user','stop','h2ol-petlab-gpu0.service'],check=True)
        record('injected-model-failure',not health()['h2o'])
        events,seconds,raw=request('calculate 17 * 23',10)
        record('native-action-works-offline',any(e.get('type')=='result' and e.get('ok') and e.get('message')=='391' for e in events),seconds=seconds)
        events,seconds,raw=request('Explain in one short English sentence what a keyboard is.')
        (out/'recovery.log').write_text(raw)
        result=next((e for e in events if e.get('type')=='result'),{})
        record('automatic-recovery-and-answer',bool(result.get('ok')) and bool(result.get('message')) and ready(health()),seconds=seconds,
               warming_status=any(e.get('phase')=='starting' for e in events))


if __name__=='__main__':main()
