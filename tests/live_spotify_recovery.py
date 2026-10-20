#!/usr/bin/env python3
"""Opt-in Spotify regression. --cold reenacts startup with accessibility off.

Temporarily restarts Spotify for --cold, mutes sound, changes its current track,
then pauses playback and restores audio/focus. Private traces stay in output/.
"""
import argparse
import fcntl
import json
from pathlib import Path
import re
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.desktop import Desktop,Gio,hypr,command

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tag',required=True);parser.add_argument('--cold',action='store_true');args=parser.parse_args()
    if not args.tag.replace('-','').isalnum():parser.error('Use a simple tag.')
    out=ROOT/'output/spotify-recovery'/args.tag
    if out.exists():raise SystemExit('Use a fresh tag; previous evidence is preserved.')
    out.mkdir(parents=True)
    d=Desktop();focus=hypr('activewindow').get('address');audio=command(['wpctl','get-volume','@DEFAULT_AUDIO_SINK@'])
    rows=[]
    def spotify():return next((p for p in d.media_status()['players'] if p['name']=='Spotify'),{})
    (out/'before.json').write_text(json.dumps({'audio':audio,'focus':focus}))
    with (ROOT/'.planet-benchmark.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        try:
            command([str(ROOT/'planet'),'close']);command(['wpctl','set-mute','@DEFAULT_AUDIO_SINK@','1'])
            if args.cold:
                if spotify():
                    d.bus_call('org.mpris.MediaPlayer2.spotify','/org/mpris/MediaPlayer2','org.mpris.MediaPlayer2','Quit')
                    deadline=time.monotonic()+5
                    while any(w['class']=='Spotify' for w in d.windows()):
                        if time.monotonic()>deadline:raise RuntimeError('Spotify did not quit.')
                        time.sleep(.1)
                command(['busctl','--user','set-property','org.a11y.Bus','/org/a11y/bus','org.a11y.Status','IsEnabled','b','false'])
                # Deliberately bypass Desktop.launch to reproduce an app that the
                # user starts before Planet activates the accessibility bus.
                Gio.DesktopAppInfo.new('spotify.desktop').launch([],None)
                deadline=time.monotonic()+10
                while not spotify():
                    if time.monotonic()>deadline:raise RuntimeError('Spotify did not start.')
                    time.sleep(.1)
                (out/'cold.json').write_text(json.dumps({'accessibility_before':command(['busctl','--user','get-property','org.a11y.Bus','/org/a11y/bus','org.a11y.Status','IsEnabled']).strip()}))
            cases=[('play ABBA on spotify','ABBA'),('play some music on spotify',None),('play my liked songs',None),("Spotify'da bir şey çal",None),('play Queen on spotify','Queen')]
            for text,artist in cases:
                start=time.monotonic();p=subprocess.run(['python',str(ROOT/'scripts/bridge.py')],input=json.dumps({'text':text})+'\n',text=True,capture_output=True,timeout=65)
                seconds=time.monotonic()-start
                (out/(str(len(rows))+'.log')).write_text(p.stdout+p.stderr)
                events=[json.loads(l) for l in p.stdout.splitlines() if l.startswith('{')];result=next((e for e in events if e.get('type')=='result'),{})
                first=spotify();time.sleep(.3);second=spotify()
                advance=first.get('track_id')==second.get('track_id') and second.get('position_us',0)>first.get('position_us',0)
                correct=artist is None or artist.casefold() in [a.casefold() for a in second.get('artist',[])]
                passed=result.get('ok') is True and second.get('state')=='Playing' and advance and correct
                row={'request':text,'seconds':round(seconds,3),'passed':passed,'playing':second.get('state')=='Playing','position_advanced':advance,'artist_matches':correct,'result':result}
                rows.append(row);(out/'results.json').write_text(json.dumps(rows,indent=2));print(json.dumps(row),flush=True)
                if second.get('player'):
                    d.bus_call(second['player'],'/org/mpris/MediaPlayer2','org.mpris.MediaPlayer2.Player','Pause')
                    deadline=time.monotonic()+3
                    while spotify().get('state')!='Paused':
                        if time.monotonic()>deadline:raise RuntimeError('Inter-case pause was not confirmed.')
                        time.sleep(.05)
                    time.sleep(.25)
        finally:
            if spotify().get('state')=='Playing':d.bus_call('org.mpris.MediaPlayer2.spotify','/org/mpris/MediaPlayer2','org.mpris.MediaPlayer2.Player','Pause')
            command(['wpctl','set-volume','@DEFAULT_AUDIO_SINK@',re.search(r'Volume:\s*([\d.]+)',audio)[1]])
            command(['wpctl','set-mute','@DEFAULT_AUDIO_SINK@','1' if 'MUTED' in audio else '0'])
            d.ensure_accessibility()
            if focus:
                try:d.focus(focus)
                except ValueError:pass
    if not all(r['passed'] for r in rows):raise SystemExit(1)
if __name__=='__main__':main()
