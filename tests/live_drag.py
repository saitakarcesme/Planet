#!/usr/bin/env python3
"""Opt-in native Wayland pointer trials, serialized against model execution."""
import argparse,fcntl,json,math,pathlib,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
def call(*args):return subprocess.check_output(args,cwd=ROOT,text=True).strip()
def status():return json.loads(call(str(ROOT/'planet'),'status'))
def place(x,y):call('quickshell','ipc','-p',str(ROOT/'app'),'call','planet','move',str(x),str(y))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--open-chat',action='store_true')
    parser.add_argument('--tag',default='native-drag-v3')
    args=parser.parse_args()
    if not args.tag.replace('-','').isalnum():raise SystemExit('Use a simple report tag.')
    report=ROOT/'output/acceptance'/(args.tag+'.json')
    if report.exists():raise SystemExit('Report already exists; use a fresh tag.')
    with (ROOT/'.planet-controller.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        initial=status();cursor=json.loads(call('hyprctl','-j','cursorpos'))
        records=[]
        try:
            if initial['opened'] != args.open_chat:call(str(ROOT/'planet'),'toggle')
            time.sleep(.25)
            for i in range(8):
                x,y=(1700,700) if i%2==0 else (2450,620)
                target=2400 if i%2==0 else 1400
                place(x,y);time.sleep(.12)
                pointer=subprocess.Popen([str(ROOT/'.build/planet-pointer')],stdin=subprocess.PIPE,text=True)
                def send(s):pointer.stdin.write(s+'\n');pointer.stdin.flush()
                send(f'move {x+30} {y+30} 3840 1080');time.sleep(.08)
                send(f'move {x+31} {y+30} 3840 1080');time.sleep(.04)
                send(f'move {x+30} {y+30} 3840 1080');time.sleep(.04)
                before=status();send('button 272 1');time.sleep(.05)
                samples=[]
                try:
                    for step in range(1,41):
                        px=round(x+30+(target-x)*step/40);py=round(y+30-120*math.sin(step/40*math.pi))
                        send(f'move {px} {py} 3840 1080');time.sleep(.012 if i<4 else .025)
                        s=status();samples.append(math.hypot(px-30-s['x'],py-30-s['y']))
                finally:
                    send('button 272 0');time.sleep(.05);pointer.stdin.close();pointer.wait(timeout=3)
                after=status()
                record={'trial':i+1,'samples':len(samples),'max_error_px':max(samples),'mean_error_px':sum(samples)/len(samples),'events':after['dragEvents'],'cancelled':after['dragCancels']-before['dragCancels'],'released':not after['dragging'],'screen':after['screen'],'chat_open':args.open_chat,'chat_toggled':after['opened']!=args.open_chat}
                record['pass']=record['max_error_px']<=1 and record['events']>=40 and not record['cancelled'] and record['released'] and not record['chat_toggled']
                records.append(record);print(json.dumps(record),flush=True)
        finally:
            if status()['opened'] != initial['opened']:call(str(ROOT/'planet'),'toggle')
            place(round(initial['x']),round(initial['y']))
            subprocess.run([str(ROOT/'.build/planet-pointer')],input=f'move {cursor["x"]} {cursor["y"]} 3840 1080\n',text=True,check=True)
        report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text(json.dumps(records,indent=2))
        if not all(r['pass'] for r in records):raise SystemExit(1)

if __name__=='__main__':main()
