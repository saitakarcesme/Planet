#!/usr/bin/env python3
"""Opt-in current command UI checks; temporarily moves pointer and native focus."""
import argparse
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.desktop import Desktop,hypr

def ipc(method,*args):
    return subprocess.check_output(['quickshell','ipc','-p',str(ROOT/'app'),'call','planet',method,*args],text=True).strip()
def state():return json.loads(ipc('status'))
def panel():return next(p for p in json.loads(ipc('inspect')) if p['active'])
def wait(check,timeout=10):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if check():return
        time.sleep(.05)
    raise TimeoutError('UI postcondition did not arrive')
def key(*args):subprocess.run(['wtype',*args],check=True)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tag',required=True);args=parser.parse_args()
    if not args.tag.replace('-','').isalnum():raise SystemExit('Use a simple tag.')
    out=ROOT/'output/capabilities'/args.tag
    if out.exists():raise SystemExit('Use a fresh tag.')
    out.mkdir(parents=True)
    records=[]
    def record(name,passed,**evidence):
        records.append(dict(case=name,passed=bool(passed),**evidence))
        (out/'results.json').write_text(json.dumps(records,indent=2)+'\n')
        if not passed:raise AssertionError(name)
    cursor=hypr('cursorpos');active=hypr('activewindow');monitors=hypr('monitors')
    width=max(m['x']+m['width']/m['scale'] for m in monitors);height=max(m['y']+m['height']/m['scale'] for m in monitors)
    def pointer(x,y,extra=''):
        subprocess.run([str(ROOT/'.build/planet-pointer')],input=f'move {int(x)} {int(y)} {int(width)} {int(height)}\nwait 100\n'+extra,text=True,check=True)
    with (ROOT/'.planet-benchmark.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        try:
            ipc('close');ipc('clear');time.sleep(.3)
            record('normally-invisible',not state()['opened'] and state()['glow']==0 and all(not p['card']['visible'] for p in json.loads(ipc('inspect'))))
            binds=hypr('binds')
            record('shortcut-registered',any(b['modmask']==72 and b['key'].upper()=='P' and b.get('description')=='Planet' for b in binds),note='Compositor registration checked; virtual wtype events do not trigger global bindings on this session.')
            for monitor in monitors:
                pointer(monitor['x']+monitor['width']/monitor['scale']/2,monitor['y']+monitor['height']/monitor['scale']/2)
                ipc('toggle');wait(lambda:state()['opened']);time.sleep(.35)
                p=panel();c=p['card']
                record('centered-on-'+monitor['name'],p['screen']==monitor['name'] and c['width']==min(780,p['width']-64) and abs(c['x']+c['width']/2-p['width']/2)<=1 and abs(c['y']+c['height']/2-p['height']/2)<=1 and c['visible'] and p['glow']==1)
                ipc('capture',str(out/('panel-'+monitor['name']+'.png')))
                key('-k','Escape');wait(lambda:not state()['opened'])
            ipc('toggle');wait(lambda:state()['opened']);time.sleep(.2)
            key('Calculate 17 * 23');key('-k','Return');wait(lambda:state()['phase']=='success' and not state()['busy'])
            ipc('capture',str(out/'result.png'));time.sleep(.2)
            c=panel()['card']
            subprocess.run(['magick',str(out/'result.png'),'-crop',f"{int(c['width'])}x{int(c['height'])}+{int(c['x'])}+{int(c['y'])}",'+repage','-background','white','-alpha','remove','-resize','200%',str(out/'result-ocr.png')],check=True)
            text=subprocess.check_output(['tesseract',str(out/'result-ocr.png'),'stdout','--psm','6'],stderr=subprocess.DEVNULL,text=True)
            record('typed-command-returns-answer','391' in text and state()['output']==3 and state()['history']==0)
            key('Calculate 2 + 3');key('-k','Return');wait(lambda:not state()['busy'] and state()['output']==1)
            record('result-replaces-previous',state()['history']==0 and state()['output']==1)
            key('/skills');key('-k','Return');wait(lambda:not state()['busy'] and state()['output']>1000)
            p=panel();c=p['card'];m=next(m for m in monitors if m['name']==p['screen'])
            pointer(m['x']+c['x']+c['width']/2,m['y']+c['y']+c['height']-60,'scroll 6\nwait 100\n')
            time.sleep(.2);after=panel()['card']
            record('bounded-scrollable-result',c['outputHeight']<=340 and c['contentHeight']>c['outputHeight'] and after['scrollY']>0,height=c['outputHeight'],scrollY=after['scrollY'])
            # Read-only long model response, cancelled through the same UI Stop handler.
            ipc('submit','Write an English essay of 1000 words about mechanical clocks.')
            wait(lambda:state()['busy']);time.sleep(.3);start=time.monotonic();ipc('cancel');wait(lambda:not state()['busy'],5)
            record('cancel-running-model',state()['opened'] and state()['phase']=='error' and state()['output']>0,cancel_to_idle_s=round(time.monotonic()-start,3))
            # Existing Spotify window: focus only, no playback or account mutation.
            ipc('submit','Open Spotify');wait(lambda:not state()['busy'] and not state()['opened'],10);time.sleep(.3)
            record('action-closes-silently',state()['output']==0 and state()['history']==0 and state()['glow']==0)
        finally:
            if state()['busy']:ipc('cancel');wait(lambda:not state()['busy'],5)
            ipc('close');ipc('clear')
            pointer(cursor['x'],cursor['y'])
            if active.get('address'):
                try:Desktop().focus(active['address'])
                except Exception:pass
    print(json.dumps(records,indent=2))
if __name__=='__main__':main()
