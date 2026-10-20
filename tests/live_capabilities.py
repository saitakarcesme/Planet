#!/usr/bin/env python3
"""Real CLI capability trials. --all operates windows/audio; --read-only does not.

Reports distinguish verified success, independent oracle success, failure and
untested capabilities. Fixtures are private. Never counts registry entries as
live passes. Closes only windows created by this suite and restores audio.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.skills import SKILLS
from scripts.desktop import Desktop,command,dispatch,hypr
from scripts.capabilities import Executor

READ_ONLY={'media.status','files.list','files.find_file','files.find_folder','files.recent','files.info','files.read',
           'system.audio','system.memory','system.cpu','system.disk','system.battery','system.network','system.uptime','system.time',
           'workspace.list','monitor.list','dev.git_status','dev.git_branch','dev.git_log','dev.git_diff','dev.git_remotes','dev.project',
           'search.apps','search.windows','search.projects','search.contents','search.documents','search.pictures','search.music','search.videos','search.large','search.size',
           'helper.calculate','helper.notes','helper.timers'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--all',action='store_true');parser.add_argument('--read-only',action='store_true');parser.add_argument('--tag',required=True);parser.add_argument('--only');args=parser.parse_args()
    if not args.all and not args.read_only:parser.error('Choose --all or --read-only.')
    if not args.tag.replace('-','').isalnum():parser.error('Use a simple report tag.')
    output=ROOT/'output/capabilities'/args.tag
    if output.exists():raise SystemExit('Use a fresh tag; existing evidence is preserved.')
    output.mkdir(parents=True)
    fixture=output/'fixture';fixture.mkdir()
    for name,text in [('sample.txt','Planet capability fixture\n'),('sample.md','# Planet fixture\n'),('sample.png','image fixture'),('sample.mp3','audio fixture'),('sample.mp4','video fixture')]: (fixture/name).write_text(text)
    command(['git','init','-q',str(fixture)])
    command(['git','-C',str(fixture),'add','sample.txt'])
    command(['git','-C',str(fixture),'-c','user.name=Planet Test','-c','user.email=test@localhost','-c','commit.gpgsign=false','commit','-qm','Fixture'])
    (fixture/'sample.txt').write_text('Planet capability fixture changed\n')
    env=dict(os.environ,PLANET_DATA_DIR=str(output/'data'))
    d=Desktop();e=Executor(d)
    initial_windows={w['address'] for w in d.windows()}
    original=hypr('activewindow');workspace=hypr('activeworkspace')['id'];cursor=hypr('cursorpos')
    (output/'initial.json').write_text(json.dumps({'windows':list(initial_windows),'active':original,'workspace':workspace,'cursor':cursor}))
    volumes={};settings={};target=None;fixture_processes=[];created_timers=[]
    report=[]
    selected=[s for s in SKILLS if args.all or s['id'] in READ_ONLY]
    if args.only:selected=[s for s in selected if s['id'] in args.only.split(',')]
    try:
        if args.all:
            command([str(ROOT/'planet'),'close'])
            for audio in ('@DEFAULT_AUDIO_SINK@','@DEFAULT_AUDIO_SOURCE@'):
                state=command(['wpctl','get-volume',audio]).strip()
                if 'Volume:' in state:volumes[audio]=state
            (output/'audio-before.json').write_text(json.dumps(volumes))
            # Keep real playback silent throughout the tests.
            command(['wpctl','set-mute','@DEFAULT_AUDIO_SINK@','1'])
            for p in d.media_status()['players']:
                if p['name']=='Spotify':
                    props=e.media_props(p['player']);settings[p['player']]={k:props[k] for k in ('Volume','Shuffle','LoopStatus') if k in props}
                    d.bus_call(p['player'],'/org/mpris/MediaPlayer2','org.freedesktop.DBus.Properties','Set',__import__('scripts.desktop',fromlist=['GLib']).GLib.Variant('(ssv)',('org.mpris.MediaPlayer2.Player','Volume',__import__('scripts.desktop',fromlist=['GLib']).GLib.Variant('d',0.0))))
            for i in range(2):
                marker='planet-capability-fixture-'+str(i)+'-'+uuid.uuid4().hex[:6]
                proc=subprocess.Popen(['foot','--app-id='+marker,'--working-directory='+str(fixture)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True);fixture_processes.append(proc)
                end=time.monotonic()+5
                while time.monotonic()<end:
                    found=[w for w in d.windows() if w['class']==marker]
                    if found:
                        if i==0:target=found[0]['address']
                        break
                    time.sleep(.05)
            if not target:raise RuntimeError('Could not create the dedicated test window.')
        for s in selected:
            id=s['id']
            try:
                if args.all:
                    # Target only our disposable window for all window mutations.
                    if id.startswith(('window.','workspace.','monitor.')) and id not in READ_ONLY:
                        d.focus(target)
                        w=d.window(target)
                        if w['fullscreen']:dispatch('hl.dsp.window.fullscreen({mode="'+('maximized' if w['fullscreen']==1 else 'fullscreen')+'"})')
                        if not d.window(target)['floating']:dispatch('hl.dsp.window.float({action="toggle"})')
                        dispatch('hl.dsp.window.resize({x=600,y=400})');dispatch('hl.dsp.window.center()')
                        if id.startswith('window.focus_'):
                            other=next(w for w in d.windows() if w['class'].startswith('planet-capability-fixture-') and w['address']!=target)
                            d.focus(other['address'])
                            if not d.window(other['address'])['floating']:dispatch('hl.dsp.window.float({action="toggle"})')
                            dispatch('hl.dsp.window.resize({x=240,y=180})')
                            target_state=d.window(target);tx,ty=target_state['at']
                            dx,dy={'left':(-320,0),'right':(700,0),'up':(0,-230),'down':(0,450)}[id.split('_')[-1]]
                            dispatch(f'hl.dsp.window.move({{x={tx+dx},y={ty+dy}}})')
                            d.focus(target)
                    if id=='media.pause':e.media('play')
                    if id in ('media.forward','media.back'):e.media('play')
                    if id=='media.back':e.media('forward')
                values={'app':'Foot','path':str(fixture),'query':'sample','percent':20,'number':9,'expression':'17 * 23','text':'Capability test note.','minutes':1}
                if id=='files.mkdir':values['path']=str(fixture/'created')
                if id in ('files.read','files.info'):values['path']=str(fixture/'sample.txt')
                if id=='files.find_folder':values['query']=args.tag
                if id=='search.apps':values['query']='Spotify'
                if id=='search.windows':values['query']='Spotify'
                if id=='search.contents':values['query']='Planet capability fixture'
                if id=='media.search':values['query']='ABBA'
                text=s['aliases'][0].format(**values)
                start=time.monotonic()
                process=subprocess.run([sys.executable,str(ROOT/'scripts/bridge.py')],input=json.dumps({'text':text,'context':{'window':target}})+'\n',text=True,capture_output=True,env=env,timeout=45)
                elapsed=time.monotonic()-start
                events=[json.loads(line) for line in process.stdout.splitlines() if line.startswith('{')]
                final=next((v for v in reversed(events) if v['type']=='result'),{})
                capability=next((v for v in events if v['type']=='capability'),{})
                passed=final.get('ok') is True and capability.get('id')==id
                oracle='native postcondition in executor'
                if id=='helper.calculate':passed=passed and final.get('message')=='391';oracle='independent arithmetic value'
                if id=='files.mkdir':passed=passed and (fixture/'created').is_dir();oracle='independent directory stat'
                if id=='files.read':passed=passed and final.get('message')==(fixture/'sample.txt').read_text();oracle='independent file bytes'
                if id=='helper.note':passed=passed and any(p.read_text()=='Capability test note.\n' for p in (output/'data/notes').glob('*.txt'));oracle='independent note bytes'
                if id in ('media.search','media.liked'):
                    media=next((p for p in d.media_status()['players'] if p['name']=='Spotify'),{})
                    first=media.get('position_us',0);time.sleep(.25)
                    after=next((p for p in d.media_status()['players'] if p['name']=='Spotify'),{})
                    passed=passed and after.get('state')=='Playing' and after.get('track_id')==media.get('track_id') and after.get('position_us',0)>first
                    if id=='media.search':passed=passed and 'ABBA' in (after.get('artist') or [])
                    oracle='independent MPRIS position and artist (search); runtime personal-collection evidence (liked)'
                row={'id':id,'seconds':round(elapsed,4),'pass':passed,'ok':final.get('ok',False),'oracle':oracle,'message':final.get('message','') if not passed else ''}
                (output/(id+'.json')).write_text(json.dumps({'text':text,'events':events,'stderr':process.stderr},ensure_ascii=False,indent=2))
            except Exception as error:row={'id':id,'pass':False,'error':str(error)[:300]}
            report.append(row);print(json.dumps(row),flush=True)
            (output/'results.json').write_text(json.dumps(report,indent=2))
            if args.all:
                # Audio test steps can unmute the sink; player volume is kept
                # at zero again before the next media/navigation task.
                if id=='media.volume':
                    from scripts.desktop import GLib
                    for player in settings:d.bus_call(player,'/org/mpris/MediaPlayer2','org.freedesktop.DBus.Properties','Set',GLib.Variant('(ssv)',('org.mpris.MediaPlayer2.Player','Volume',GLib.Variant('d',0.0))))
    finally:
        if args.all:
            from scripts.desktop import GLib
            d.media_status()
            for player,props in settings.items():
                try:
                    d.media_control(player,'Pause')
                    for key,value in props.items():d.bus_call(player,'/org/mpris/MediaPlayer2','org.freedesktop.DBus.Properties','Set',GLib.Variant('(ssv)',('org.mpris.MediaPlayer2.Player',key,GLib.Variant({'Volume':'d','Shuffle':'b','LoopStatus':'s'}[key],value))))
                except Exception as error:print('RESTORE MEDIA:',str(error),file=sys.stderr)
            import re
            for audio,state in volumes.items():
                command(['wpctl','set-volume',audio,re.search(r'Volume:\s*([\d.]+)',state)[1]])
                command(['wpctl','set-mute',audio,'1' if 'MUTED' in state else '0'])
            # Only terminals created by this test and the fixture editor window.
            for w in d.windows():
                if w['address'] not in initial_windows and (w['class'].startswith('planet-') or w['class'].lower() in ('code','com.microsoft.vscode') and 'fixture' in w['title'].lower()):
                    try:dispatch('hl.dsp.window.close({window="address:'+w['address']+'"})')
                    except Exception:pass
            dispatch(f'hl.dsp.focus({{workspace="{workspace}"}})')
            if original.get('address') and any(w['address']==original['address'] for w in d.windows()):d.focus(original['address'])
            # Cancel only timer units created in this suite, recorded in its fast trace.
            for p in (ROOT/'.planet-runs').glob('fast-*.json'):
                if p.stat().st_mtime>=output.stat().st_ctime:
                    try:
                        data=json.loads(p.read_text());unit=data.get('result',{}).get('unit')
                        if unit:subprocess.run(['systemctl','--user','stop',unit],capture_output=True)
                    except Exception:pass
        (output/'results.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'tested':len(report),'passed':sum(r['pass'] for r in report),'failed':[r['id'] for r in report if not r['pass']]}),flush=True)
    return 0 if all(r['pass'] for r in report) else 1

if __name__=='__main__':raise SystemExit(main())
