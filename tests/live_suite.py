#!/usr/bin/env python3
"""Opt-in real model/desktop acceptance trials. Not run by unittest.

Uses only a private fixture tree for filesystem mutations. Media is muted during
trials and paused before restoring its original volume. Never sends messages,
installs software, deletes user files, or replaces native apps with web pages.
"""
import argparse
import contextlib
import fcntl
import io
import json
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from urllib.parse import unquote
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.bridge import Controller, ROOT
from scripts.desktop import Desktop, hypr, GLib

FIXTURES = ROOT/'output/live-fixtures'
REPORTS = ROOT/'output/acceptance'


def cases():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    names = ['Aurora Notes', 'Coffee Sketches', 'Client-Blue', 'Music Ideas', 'Travel 2027', 'Project Atlas',
             'Meeting Drafts', 'Weekend Plans', 'Invoice Samples', 'Photo Concepts', 'Garden Log', 'Günlük Notlar',
             'Reading Queue', 'Podcast Ideas', 'Design References', 'Archive October']
    for name in names:
        p = FIXTURES/'existing'/name;p.mkdir(parents=True, exist_ok=True)
        (p/'fixture.txt').write_text('Planet acceptance fixture. No personal user data.\n')
    result = []
    def add(category, prompt, **expect):
        result.append({'id': f'{category}-{sum(c["category"]==category for c in result)+1:02}', 'category': category, 'prompt': prompt, 'expect': expect})
    for app, app_id, phrases in [
        ('Omacalc','omacalc.desktop',['Open Omacalc.', 'Hesap makinesini aç.', 'Bring the calculator application to the front.']),
        ('Files','org.gnome.Nautilus.desktop',['Open Files.', 'Dosya yöneticisini açar mısın?', 'Bring my file manager to the front.']),
        ('Spotify','spotify.desktop',['Open Spotify.', 'Spotify uygulamasını aç.', 'Bring the Spotify desktop app forward.']),
        ('Pinta','com.github.PintaProject.Pinta.desktop',['Open Pinta.', 'Pinta uygulamasını aç.', 'Bring the Pinta drawing application to the front.'])]:
        for prompt in phrases: add('launch',prompt,app_id=app_id)
    calculations = [(17,'*',23),(48,'+',37),(144,'/',12),(205,'-',76),(19,'*',8),(67,'+',89),
                    (315,'/',9),(402,'-',157),(26,'*',14),(518,'+',207),(896,'/',7),(1000,'-',384),
                    (32,'*',27),(729,'+',154),(624,'/',8),(863,'-',279),(41,'*',16),(253,'+',468),
                    (936,'/',12),(704,'-',318),(57,'*',13),(184,'+',629),(975,'/',15),(901,'-',467)]
    for i,(a,op,b) in enumerate(calculations):
        value = {'+':lambda:a+b,'-':lambda:a-b,'*':lambda:a*b,'/':lambda:a/b}[op]()
        phrase = f'In Omacalc, clear the old calculation, calculate {a} {op} {b}, and verify the displayed answer.' if i%2==0 else f'Omacalc uygulamasında önce eski hesabı temizle, {a} {op} {b} işlemini yap ve ekrandaki sonucu doğrula.'
        add('calculator',phrase,value=str(int(value)))
    for i,name in enumerate(names[:12]):
        prompt = f'Find the folder named "{name}" under {FIXTURES}. Tell me its full path.' if i%2==0 else f'{FIXTURES} altında "{name}" isimli klasörü bulup tam yolunu söyler misin?'
        add('find',prompt,path=str(FIXTURES/'existing'/name))
    for i in range(6):
        query=f'Unlisted Nebula {i+1}'
        add('missing',f'Look for a folder named "{query}" under {FIXTURES}. If it is absent, report that; do not create it.',query=query)
    for i,name in enumerate(['Sprint One','Yeni Taslak','audio-notes','Plan B','Research 2028','İş Akışı','Mockups/Day One','Session Notes','Release Draft','Demo Library','sandbox/child-a','Final Notes']):
        p=FIXTURES/'created'/name
        prompt=f'Create the folder {p}.' if i%2==0 else f'{p} yolunda bir klasör oluştur.'
        add('mkdir',prompt,path=str(p))
    for i,name in enumerate(names):
        p=FIXTURES/'existing'/name
        phrase=f'Open the folder {p} in the native file manager.' if i%2==0 else f'{p} klasörünü dosya yöneticisinde aç.'
        add('navigate',phrase,path=str(p))
    for i in range(6):
        add('music', 'Resume playback in Spotify.' if i%2==0 else 'Spotify’da müziği devam ettir.',state='Playing')
        add('music', 'Pause the music in Spotify.' if i%2==0 else 'Spotify’da çalan müziği duraklat.',state='Paused')
        add('music_info', ['What song is selected in Spotify?','Spotify’da hangi şarkı var?','Read the current track and artist in Spotify.'][i%3])
    for a,b in [(29,13),(47,9),(81,7),(34,18),(65,12),(92,11)]:
        add('answer',f'What is {a} times {b}? Answer in one short sentence without opening an application.',value=str(a*b))
    for i in range(6):
        name=f'PlanetMissingApp{i+1}ZZ'
        add('unknown_app',f'Open the native application {name}. If it is not installed, tell me. Do not open a browser or install anything.',name=name)
    for i,name in enumerate(names[:6]):
        p=FIXTURES/'combined'/f'Trial {i+1}'
        add('combined',f'Create {p}, open it in the file manager, then list its contents.',path=str(p))
    return result


def verify(case, c, result):
    category=case['category'];e=case['expect'];ok,message,code=result
    tools=[event for event in c.trace if event['kind']=='tool']
    names=[t['name'] for t in tools]
    evidence={'tools': names, 'reported_ok': ok, 'code': code}
    if category=='launch':
        app=c.desktop.apps[e['app_id']]
        identities={(app.get_startup_wm_class() or '').lower(),Path(app.get_executable() or '').name.lower(),e['app_id'].removesuffix('.desktop').lower()}
        active=hypr('activewindow');evidence['active_class']=active.get('class')
        passed=(active.get('class','').lower() in identities or bool(c.desktop.process_identity(active.get('pid',0)) & identities)) and bool(tools)
    elif category=='calculator':
        matches=[w for w in c.desktop.windows() if w['class'].lower()=='omacalc']
        if not matches:return False,{**evidence,'reason':'Calculator window missing'}
        observed=c.desktop.observe(matches[0]['address'])
        display=[n['text'] for n in observed['elements'] if n.get('source')=='ocr' and n['position'][1]<160]
        evidence['display']=display;evidence['expected']=e['value']
        passed=any(re.sub(r'[^0-9-]','',s)==e['value'] for s in display) and any(n in names for n in ('type_text','click','keys'))
    elif category=='find':
        found=[str(m['path']) for t in tools if t['name']=='find_files' for m in t['result'].get('matches',[])]
        passed=e['path'] in found and e['path'] in message;evidence['found']=found
    elif category=='missing':
        queried=[t for t in tools if t['name']=='find_files']
        passed=bool(queried) and all(not t['result']['matches'] for t in queried) and not any(n in names for n in ('mkdir','open_folder','launch'))
        # Correctly reporting absence can be blocked or done, depending on phrasing.
        ok=code in ('done','blocked','needs_input')
    elif category=='mkdir':
        passed=Path(e['path']).is_dir() and any(t['name']=='mkdir' and t['result'].get('path')==e['path'] for t in tools)
    elif category in ('navigate','combined'):
        locations=c.desktop.folder_windows()['locations'];evidence['locations']=locations
        passed=Path(e['path']).as_uri() in locations and ('open_folder' in names or any(n in names for n in ('keys','type_text')))
        if category=='combined':passed=passed and 'mkdir' in names and 'list_folder' in names
    elif category=='music':
        players=c.desktop.media_status()['players'];player=next((p for p in players if p['name']=='Spotify'),{})
        passed=player.get('state')==e['state'] and 'media_control' in names;evidence['player']=player
    elif category=='music_info':
        players=c.desktop.media_status()['players'];player=next((p for p in players if p['name']=='Spotify'),{})
        passed='media_status' in names and bool(player.get('title')) and player['title'].casefold() in message.casefold()
        evidence['title']=player.get('title')
    elif category=='answer':
        passed=e['value'] in message and not tools
    elif category=='unknown_app':
        passed=not any(n in names for n in ('launch','type_text','click','keys','mkdir','open_folder')) and code in ('needs_input','blocked')
        ok=True
    elif category=='document':
        path=Path(e['path'])
        contents=path.read_text() if path.is_file() else ''
        evidence['saved_file_exists']=path.is_file()
        evidence['expected_text_found']=e['text'] in contents
        passed=bool(tools) and evidence['expected_text_found']
    elif category=='music_playlist':
        players=c.desktop.media_status()['players'];player=next((p for p in players if p['name']=='Spotify'),{})
        snapshots=[t['result'] for t in tools if 'elements' in t['result']]
        labels=[' '.join((n.get('name',''),n.get('text',''))) for s in snapshots for n in s['elements']]
        evidence['playing']=player.get('state')=='Playing'
        evidence['playlist_observed']=any(e['playlist'].casefold() in s.casefold() for s in labels)
        personal=[s for s in snapshots if any(n.get('text','')=='Liked Songs' for n in s['elements']) and not any('public playlist' in n.get('text','').casefold() for n in s['elements'])]
        body_labels=[n.get('text','') for s in personal for n in s['elements'] if n.get('position',[0,10000])[1]<s['window']['size'][1]-150]
        evidence['track_observed']=bool(player.get('title')) and any(player['title'].casefold() in s.casefold() for s in body_labels)
        evidence['track_changed']=bool(player.get('track_id')) and player['track_id']!=e.get('initial_track_id')
        passed=evidence['playing'] and evidence['playlist_observed'] and evidence['track_observed'] and evidence['track_changed'] and any(n in names for n in ('click','keys','type_text'))
    else:raise ValueError(category)
    return bool(ok and passed),evidence


def media_volume(d, player, value=None):
    if value is None:
        return d.bus_call(player,'/org/mpris/MediaPlayer2','org.freedesktop.DBus.Properties','Get',GLib.Variant('(ss)',('org.mpris.MediaPlayer2.Player','Volume')))[0]
    return d.bus_call(player,'/org/mpris/MediaPlayer2','org.freedesktop.DBus.Properties','Set',GLib.Variant('(ssv)',('org.mpris.MediaPlayer2.Player','Volume',GLib.Variant('d',value))))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tag',required=True);parser.add_argument('--start',type=int,default=0);parser.add_argument('--limit',type=int);parser.add_argument('--categories',default='');parser.add_argument('--sample',action='store_true');parser.add_argument('--cases-file',type=Path);args=parser.parse_args()
    if not re.fullmatch('[a-z0-9-]+',args.tag):raise SystemExit('Use a simple report tag.')
    bench_lock=(ROOT/'.planet-benchmark.lock').open('w');fcntl.flock(bench_lock,fcntl.LOCK_EX)
    all_cases=json.loads(args.cases_file.read_text()) if args.cases_file else cases();selected=[c for c in all_cases if not args.categories or c['category'] in args.categories.split(',')][args.start:]
    if args.sample:
        seen=set();selected=[c for c in selected if c['category'] not in seen and not seen.add(c['category'])]
    if args.limit is not None:selected=selected[:args.limit]
    REPORTS.mkdir(parents=True,exist_ok=True)
    output=REPORTS/(args.tag+'.jsonl')
    if output.exists():raise SystemExit('Report tag already exists; use a new tag to preserve evidence.')
    (REPORTS/(args.tag+'-cases.json')).write_text(json.dumps(selected,ensure_ascii=False,indent=2))
    d=Desktop();players=d.media_status()['players'];volumes={p['player']:media_volume(d,p['player']) for p in players if p['name']=='Spotify'}
    for p in volumes:media_volume(d,p,0.0)
    subprocess.run([str(ROOT/'planet'),'close'],capture_output=True)
    completed=[]
    def deadline(signum, frame):raise TimeoutError('Acceptance case exceeded 210 seconds.')
    signal.signal(signal.SIGALRM,deadline)
    signal.signal(signal.SIGTERM,lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        for i,case in enumerate(selected):
            for player in volumes: media_volume(d,player,0.0)
            start=time.monotonic();c=None
            with (ROOT/'.planet-controller.lock').open('w') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX)
                signal.alarm(210)
                try:
                    if case['category']=='music_playlist':
                        player=next((p for p in d.media_status()['players'] if p['name']=='Spotify'),{})
                        case['expect']['initial_track_id']=player.get('track_id')
                    with contextlib.redirect_stdout(io.StringIO()):
                        c=Controller(case['prompt']);result=c.run()
                    passed,evidence=verify(case,c,result)
                    record={**case,'pass':passed,'result':result,'evidence':evidence}
                except Exception as error:
                    record={**case,'pass':False,'error':str(error)}
                finally:
                    signal.alarm(0)
                    if c:c.save_trace()
            record['seconds']=round(time.monotonic()-start,3)
            if c:record['trace']=str(c.live_log)
            completed.append(record)
            with output.open('a') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
            print(json.dumps({'case':case['id'],'n':i+1,'total':len(selected),'pass':record['pass'],'seconds':record['seconds'],'error':record.get('error'),'message':record.get('result',[None,None])[1]},ensure_ascii=False),flush=True)
    finally:
        for p,v in volumes.items():
            try:
                d.media_status();d.media_control(p,'Pause');media_volume(d,p,v)
            except Exception as error:print('Media restore:',error,file=sys.stderr)
        summary={'tag':args.tag,'attempts':len(completed),'passed':sum(r['pass'] for r in completed),'categories':{}}
        for category in sorted({r['category'] for r in completed}):
            group=[r for r in completed if r['category']==category]
            summary['categories'][category]={'attempts':len(group),'passed':sum(r['pass'] for r in group)}
        (REPORTS/(args.tag+'-summary.json')).write_text(json.dumps(summary,indent=2))
        print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
