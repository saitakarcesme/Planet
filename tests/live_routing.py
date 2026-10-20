#!/usr/bin/env python3
"""Read-only local decision checks; no desktop or capability execution."""
import argparse
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.bridge import decision
from scripts.fast import select

CASES=[
    ("Would you pause the music for a moment?",'media.pause'),
    ("Müziği biraz duraklatır mısın?",'media.pause'),
    ("How much free disk space do I have?",'system.disk'),
    ("Bilgisayarımda ne kadar boş disk alanı kaldı?",'system.disk'),
    ("Could you tell me what time it is?",'system.time'),
    ("What song is currently playing?",'media.status'),
    ("Can you play something on Spotify please?",'media.search'),
    ("Spotify'da bir şey çalar mısın?",'media.search'),
    ("Play some music using Spotify",'media.search'),
    ("Play a song from my liked songs on Spotify",'media.liked'),
    ("Spotify üzerinde beğendiğim şarkılardan birini dinlemek istiyorum",'media.liked'),
    ("Put on some ABBA for me",'media.search'),
    ("Can you put on a song by Queen in Spotify?",'media.search'),
    ("Play ABBA on Spotify but only live recordings",None),
    ("Play some relaxing music without vocals on Spotify",None),
    ("Play my workout playlist on Spotify",None),
    ("Play the complete album Abbey Road in order on Spotify",None),
    ("Play something in Spotify and open my downloads folder",None),
    ("Open Spotify and delete my files",None),
    ("Pause the music and send a message to my friend",None),
]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tag',required=True);args=parser.parse_args()
    if not args.tag.replace('-','').isalnum():parser.error('Use a simple tag.')
    out=ROOT/'output/routing'/args.tag;out.mkdir(parents=True,exist_ok=False)
    rows=[]
    for text,expected in CASES:
        start=time.monotonic();choices=[]
        def decide(*args):
            value=decision(*args);choices.append(value);return value
        # Test routing boundaries only. Parameter extraction and real execution
        # are covered separately by live Spotify tests.
        value=select(text,decide,lambda skill,text:{k:('PROBE' if t=='string' else 1) for k,t in skill['params'].items()})
        actual=value[0] if value else None
        row=dict(request=text,expected=expected,actual=actual,passed=actual==expected,seconds=round(time.monotonic()-start,3),choices=choices)
        rows.append(row);print(json.dumps(row),flush=True)
        (out/'results.json').write_text(json.dumps(rows,indent=2))
    if not all(row['passed'] for row in rows):raise SystemExit(1)


if __name__=='__main__':main()
