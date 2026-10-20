"""Native Spotify recipes: observed controls, fresh IDs, verified playback."""
import re
import time
from .skills import normalized
from .capabilities import CapabilityError, result


GENERIC_MUSIC = {'some music', 'something', 'anything', 'a song', 'any song',
                 'music', 'bir sey', 'bir sarki', 'herhangi bir sarki', 'muzik'}


def playing_progress(d, matches, seconds=3):
    """Observe actual progressing playback, not just a successful input event."""
    first=None;deadline=time.monotonic()+seconds
    while True:
        current=next((p for p in d.media_status()['players'] if p['name']=='Spotify'),{})
        if current.get('state')=='Playing' and matches(current):
            if first and first.get('track_id')==current.get('track_id') and current.get('position_us',0)-first.get('position_us',0)>=150000:
                return result(player=current,position_advanced_us=current['position_us']-first['position_us'])
            first=current if first is None or first.get('track_id')!=current.get('track_id') else first
        else:first=None
        if time.monotonic()>=deadline:return None
        time.sleep(.08)


def ensure_spotify_controls(d,address):
    if d.accessibility_registered(address):return address
    # A CEF process started before the accessibility bus was enabled may never
    # attach, despite its launcher flag. Restart once through native MPRIS.
    deadline=time.monotonic()+.5
    while time.monotonic()<deadline:
        if d.accessibility_registered(address):return address
        time.sleep(.1)
    if '--force-renderer-accessibility' not in (d.apps['spotify.desktop'].get_commandline() or ''):
        raise CapabilityError('Spotify accessibility is not configured. Enable its native accessibility launcher first.')
    d.bus_call('org.mpris.MediaPlayer2.spotify','/org/mpris/MediaPlayer2','org.mpris.MediaPlayer2','Quit')
    deadline=time.monotonic()+4
    while any(w['address']==address for w in d.windows()):
        if time.monotonic()>=deadline:raise CapabilityError('Spotify did not close for accessibility recovery. Restart Spotify and try again.')
        time.sleep(.1)
    d.launch_attempts.discard('spotify.desktop')
    launched=d.launch('spotify.desktop')
    if not launched.get('verified'):raise CapabilityError('Spotify did not reopen for accessibility recovery.')
    address=launched['window']['address'];deadline=time.monotonic()+4
    while not d.accessibility_registered(address):
        if time.monotonic()>=deadline:raise CapabilityError('Spotify reopened but its native controls are still unavailable.')
        time.sleep(.1)
    return address


def wait_for_controls(d,address,observation,select,message,seconds=8):
    deadline=time.monotonic()+seconds
    while True:
        matches=select(observation['elements'])
        if len(matches)==1:return observation,matches[0]
        if len(matches)>1:raise CapabilityError('Spotify exposes multiple matching controls; no ambiguous action was taken.')
        if time.monotonic()>=deadline:raise CapabilityError(message)
        time.sleep(.15)
        observation=d.observe(address)


def play_selection(d,query):
    if 'spotify.desktop' not in d.apps:raise CapabilityError('Spotify is not installed.')
    if query is not None and normalized(query).strip(' .!?') in GENERIC_MUSIC:
        # The request names no artist/title. Resume the actual Spotify queue;
        # do not search for the literal words 'some music'.
        if not any(p['name']=='Spotify' for p in d.media_status()['players']):
            launched=d.launch('spotify.desktop')
            if not launched.get('verified'):raise CapabilityError('Spotify did not open.')
        deadline=time.monotonic()+3
        while not any(p['name']=='Spotify' for p in d.media_status()['players']):
            if time.monotonic()>=deadline:raise CapabilityError('Spotify has not exposed its player yet.')
            time.sleep(.1)
        d.bus_call('org.mpris.MediaPlayer2.spotify','/org/mpris/MediaPlayer2','org.mpris.MediaPlayer2.Player','Play')
        resumed=playing_progress(d,lambda p:bool(p.get('title')) and bool(p.get('track_id')))
        if resumed:return resumed
        # An empty/unavailable queue is handled through the real personal library.
        query=None
    launched=d.launch('spotify.desktop')
    if not launched.get('verified'):raise CapabilityError('Spotify did not open.')
    address=launched['window']['address']
    address=ensure_spotify_controls(d,address)
    o=d.observe(address)
    if query is not None:
        o,field=wait_for_controls(d,address,o,
            lambda nodes:[n for n in nodes if n.get('editable') and n.get('role') in ('entry','combo box') and 'play' in n.get('name','').lower()],
            'Spotify search did not become ready. Check its sign-in or loading screen.')
        o=d.fill_field(field['id'],field['name'],query,'Return')
    else:
        o,entry=wait_for_controls(d,address,o,
            lambda nodes:[n for n in nodes if n.get('role')=='button' and n.get('name','').startswith('Liked Songs') and 'table: Your Library' in n.get('context',[])],
            'Your personal Liked Songs entry did not become visible in the library.')
        owner=entry['name'].rsplit(' • ',1)[-1]
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
