#!/usr/bin/env python3
"""Opt-in live UI: bridge response, cancellation, wheel scrolling and collapse."""
import argparse
import fcntl
import json
from pathlib import Path
import subprocess
import time
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.desktop import Desktop
parser=argparse.ArgumentParser();parser.add_argument('--tag',default='ui-pipeline');parser.add_argument('--launch',action='store_true');args=parser.parse_args()
if not args.tag.replace('-','').isalnum():raise SystemExit('Use a simple tag.')
def ipc(method, *args):
    return subprocess.check_output(['quickshell','ipc','-p',str(ROOT/'app'),'call','planet',method,*args],text=True).strip()
def state():return json.loads(ipc('status'))
def wait_idle(timeout=30):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if not state()['busy']:return
        time.sleep(.1)
    raise TimeoutError('UI task did not finish')

with (ROOT/'.planet-benchmark.lock').open('w') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    report=ROOT/'output/acceptance'/(args.tag+'.json')
    if report.exists():raise SystemExit('Preserve existing report before rerunning.')
    records=[]
    ipc('close')
    records.append({'case':'normally-collapsed','pass':not state()['opened']})
    ipc('submit','What is 55 times 13? Answer in one short English sentence. Do not open any application.')
    wait_idle();time.sleep(.5)
    history=json.loads((ROOT/'.local-state.json').read_text())['messages']
    records.append({'case':'ui-to-local-model-to-ui','pass':'715' in history[-1]['body'] and history[-1]['role']=='assistant'})
    panel=next(p for p in json.loads(ipc('inspect')) if p['active'])
    before=panel['layout'];w=panel['width'];x=panel['x'];y=panel['y'];cw=before['chatWidth']
    chat_x=max(12,min(x+70 if x+70+cw<=w-12 else x-cw-10,w-cw-12))
    composer_y=max(100,min(y+11,panel['height']-before['composerHeight']-48))
    monitors=json.loads(subprocess.check_output(['hyprctl','-j','monitors'],text=True))
    monitor=next(m for m in monitors if m['name']==panel['screen'])
    px=round(monitor['x']+chat_x+cw-5);py=round(monitor['y']+composer_y-10-before['historyHeight']/2)
    subprocess.run([str(ROOT/'.build/planet-pointer')],input=f'move {px} {py} 3840 1080\nwait 100\nscroll -6\nwait 100\n',text=True,check=True)
    time.sleep(.2)
    after=next(p for p in json.loads(ipc('inspect')) if p['active'])['layout']
    records.append({'case':'native-wheel-scroll','pass':after['scrollY']<before['scrollY'],
                    'before':before['scrollY'],'after':after['scrollY']})
    if args.launch:
        ipc('submit','Open the native Pinta drawing application.')
        wait_idle();time.sleep(2)
        desktop=Desktop()
        found=[w for w in desktop.windows() if 'pinta' in desktop.process_identity(w['pid'])]
        records.append({'case':'native-app-survives-bridge-exit','pass':bool(found)})
    ipc('submit','Write an English essay of 600 words about the history of mechanical clocks. Do not use any application.')
    time.sleep(.25);start=time.monotonic();ipc('cancel');wait_idle(5);time.sleep(.5)
    history=json.loads((ROOT/'.local-state.json').read_text())['messages']
    records.append({'case':'cancel-local-request','pass':'Stopped.' in history[-1]['body'],
                    'cancel_to_idle_seconds':round(time.monotonic()-start-.5,3)})
    ipc('close')
    records.append({'case':'collapse-after-task','pass':not state()['opened']})
    report.write_text(json.dumps(records,indent=2)+'\n')
    print(json.dumps(records),flush=True)
    if not all(r['pass'] for r in records):raise SystemExit(1)
