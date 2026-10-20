"""Native Spotify recipes: observed controls, fresh IDs, verified playback."""
import re
import time
from .skills import normalized
from .capabilities import CapabilityError, result


def play_selection(d,query):
    if 'spotify.desktop' not in d.apps:raise CapabilityError('Spotify is not installed.')
    launched=d.launch('spotify.desktop')
    if not launched.get('verified'):raise CapabilityError('Spotify did not open.')
    address=launched['window']['address']
    o=d.observe(address)
    if query is not None:
        field=next((n for n in o['elements'] if n.get('editable') and n.get('role') in ('entry','combo box') and 'play' in n.get('name','').lower()),None)
        if not field:raise CapabilityError('Spotify search is not exposed. Enable native accessibility first.')
        o=d.fill_field(field['id'],field['name'],query,'Return')
    else:
        candidates=[n for n in o['elements'] if n.get('role')=='button' and n.get('name','').startswith('Liked Songs') and 'table: Your Library' in n.get('context',[])]
        if len(candidates)!=1:raise CapabilityError('Your personal Liked Songs entry is not uniquely visible in the library.')
        entry=candidates[0];owner=entry['name'].rsplit(' • ',1)[-1]
        o=d.click(entry['id'],entry['actions'][0],entry['name'])
    deadline=time.monotonic()+5
    chosen=None
    while True:
        elements=o['elements']
        if query is None:
            labels=[n.get('name','') for n in elements]
            if any('public playlist' in s.casefold() for s in labels):raise CapabilityError('This is a public playlist, not your personal Liked Songs.')
            personal=any(n.get('role')=='table' and n.get('name')=='Liked Songs' for n in elements) and any(n.get('name')==owner for n in elements)
            if personal:
                chosen=next((n for n in elements if n.get('role')=='button' and n.get('name','').startswith('Play ') and 'table: Liked Songs' in n.get('context',[])),None)
        else:
            # Restrict to the current search-results region and exact title/artist
            # words, excluding unrelated player/library controls.
            terms=normalized(query).split()
            for n in elements:
                if n.get('role')!='button' or not n.get('name','').startswith('Play'):continue
                contexts=n.get('context',[])
                if not any('Search' in c or 'Songs' in c for c in contexts):continue
                row=next((c for c in contexts if c.startswith('table row: ')),None)
                peers=[e.get('name','') for e in elements if row and row in e.get('context',[])]
                description=normalized(' '.join([n.get('name',''),*contexts,*peers]))
                if all(re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)',description) for term in terms) and not any('playlist' in normalized(s) for s in peers):
                    chosen=n;break
        if chosen:break
        if time.monotonic()>=deadline:raise CapabilityError('No matching playable result was verified. Try a more specific artist or song name.')
        time.sleep(.15);o=d.observe(address)
    selection={'name':chosen['name'],'context':chosen.get('context',[])}
    d.click(chosen['id'],chosen['actions'][0],chosen['name'])
    first=None;deadline=time.monotonic()+5
    while True:
        current=next((p for p in d.media_status()['players'] if p['name']=='Spotify'),{})
        playing=current.get('state')=='Playing'
        if query is not None:
            text=normalized((current.get('title') or '')+' '+' '.join(current.get('artist') or []))
            matches=all(re.search(r'(?<!\w)'+re.escape(t)+r'(?!\w)',text) for t in normalized(query).split())
        else:
            label=normalized(selection['name']);title=normalized(current.get('title') or '')
            matches=bool(title) and title in label
        if playing and matches:
            if first and first.get('track_id')==current.get('track_id') and current.get('position_us',0)-first.get('position_us',0)>=150000:
                return result(player=current,selection=selection,position_advanced_us=current['position_us']-first['position_us'])
            if first is None:first=current
        else:first=None
        if time.monotonic()>=deadline:raise CapabilityError('Spotify did not confirm the requested track with advancing playback. No further action was taken.')
        time.sleep(.08)
