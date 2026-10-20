"""Typed, bounded native recipes for the Planet capability registry."""
import ast
import datetime
import json
import math
import operator
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid

from .desktop import Desktop, GLib, command, dispatch, hypr
from .skills import BY_ID, normalized, validate

DATA = Path(os.environ.get('PLANET_DATA_DIR', str(Path.home()/'.local/share/planet')))

class CapabilityError(Exception): pass

def result(verified=True, message='', **evidence):
    return {'verified':verified, 'message':message, **evidence}

def wait_until(read, check, seconds=1.5):
    deadline=time.monotonic()+seconds
    while True:
        value=read()
        if check(value):return value
        if time.monotonic()>=deadline:raise CapabilityError('The application did not confirm the requested change.')
        time.sleep(.04)

class Executor:
    def __init__(self, desktop=None, target_window=None):
        self.desktop=desktop or Desktop()
        self.target_window=target_window
        self.events=[]

    def run(self, id, args):
        validate(id,args)
        group,key=id.split('.',1)
        handler={'app':self.app,'window':self.window,'media':self.media,'files':self.files,
                 'system':self.system,'workspace':self.workspace,'monitor':self.monitor,
                 'dev':self.dev,'search':self.search,'helper':self.helper}[group]
        started=time.monotonic()
        value=handler(key,**args)
        if not isinstance(value,dict) or value.get('verified') is not True:
            raise CapabilityError(value.get('note','The requested result was not verified.') if isinstance(value,dict) else 'No verified result.')
        value['duration']=round(time.monotonic()-started,4)
        return value

    def app_id(self, app):
        aliases={'terminal':'foot.desktop','files':'org.gnome.Nautilus.desktop','dosyalar':'org.gnome.Nautilus.desktop',
                 'calculator':'omacalc.desktop','hesap makinesi':'omacalc.desktop','vscode':'com.microsoft.VSCode.desktop',
                 'writer':'libreoffice-writer.desktop','chrome':'google-chrome.desktop'}
        term=normalized(app.strip(' "\'.!'))
        catalog=self.desktop.catalog()
        preferred=aliases.get(term)
        exact=[a['id'] for a in catalog if normalized(a['name'])==term or normalized(a['id'].removesuffix('.desktop'))==term or a['id']==preferred]
        if 'discord.desktop' in exact:exact=['discord.desktop']
        if len(exact)!=1:raise CapabilityError('Specify one installed application by its exact name.')
        return exact[0]

    def app(self,key,app):
        id=self.app_id(app)
        if key=='open':
            launched=self.desktop.launch(id)
            if launched.get('verified'):self.target_window=launched['window']['address']
            return launched
        entry=self.desktop.apps[id]
        identities={id.removesuffix('.desktop').lower(),(entry.get_startup_wm_class() or '').lower(),Path(entry.get_executable() or '').name.lower()}
        matches=[w for w in self.desktop.windows() if w['class'].lower() in identities or self.desktop.process_identity(w['pid']) & identities]
        if not matches:raise CapabilityError('That application has no open window.')
        address=matches[0]['address'];self.desktop.focus(address)
        self.target_window=address
        return result(address=address)

    def target(self):
        address=self.target_window or hypr('activewindow').get('address')
        if not address:raise CapabilityError('Focus an application before opening Planet.')
        self.desktop.focus(address)
        return self.desktop.window(address)

    def window(self,key):
        before=self.target();address=before['address'];self.target_window=address
        read=lambda:self.desktop.window(address)
        if key in ('maximize','fullscreen','restore'):
            expected={'maximize':1,'fullscreen':2,'restore':0}[key]
            current=before.get('fullscreen',0)
            if current!=expected:
                if current:dispatch('hl.dsp.window.fullscreen({mode="'+('maximized' if current==1 else 'fullscreen')+'"})')
                if expected:dispatch('hl.dsp.window.fullscreen({mode="'+('maximized' if expected==1 else 'fullscreen')+'"})')
            after=wait_until(read,lambda w:w.get('fullscreen')==expected)
        elif key in ('float','tile'):
            desired=key=='float'
            if bool(before['floating'])!=desired:dispatch('hl.dsp.window.float({action="toggle"})')
            after=wait_until(read,lambda w:bool(w['floating'])==desired)
        elif key.startswith('focus_'):
            direction=key.split('_')[1][0]
            dispatch('hl.dsp.focus({direction="'+direction+'"})')
            after=wait_until(lambda:hypr('activewindow'),lambda w:bool(w.get('address')) and w['address']!=address)
        elif key.startswith('move_'):
            direction=key.split('_')[1][0]
            if before['floating']:
                dx,dy={'l':(-100,0),'r':(100,0),'u':(0,-100),'d':(0,100)}[direction]
                dispatch(f'hl.dsp.window.move({{x={dx},y={dy},relative=true}})')
            else:dispatch('hl.dsp.window.swap({direction="'+direction+'"})')
            after=wait_until(read,lambda w:w['at']!=before['at'])
        elif key=='center':
            if not before['floating']:raise CapabilityError('Center applies to floating windows. Use “float window” first.')
            dispatch('hl.dsp.window.center()')
            monitor=next(m for m in hypr('monitors') if m['id']==before['monitor'])
            after=wait_until(read,lambda w:abs((w['at'][0]+w['size'][0]/2)-(monitor['x']+monitor['width']/monitor['scale']/2))<5 and abs((w['at'][1]+w['size'][1]/2)-(monitor['y']+monitor['height']/monitor['scale']/2))<25)
        else:
            dx,dy={'wider':(100,0),'narrower':(-100,0),'taller':(0,100),'shorter':(0,-100)}[key]
            dispatch(f'hl.dsp.window.resize({{x={dx},y={dy},relative=true}})')
            after=wait_until(read,lambda w:w['size']!=before['size'])
        return result(window=after)

    def player(self):
        players=self.desktop.media_status()['players']
        spotify=[p for p in players if p['name']=='Spotify']
        if spotify:return spotify[0]
        active=[p for p in players if p['state']=='Playing']
        if len(active)==1:return active[0]
        if len(players)==1:return players[0]
        raise CapabilityError('Open a music player first, or leave only one player active.')

    def media_props(self,player):
        return self.desktop.bus_call(player,'/org/mpris/MediaPlayer2','org.freedesktop.DBus.Properties','GetAll',GLib.Variant('(s)',('org.mpris.MediaPlayer2.Player',)))[0]

    def media(self,key,percent=None,query=None):
        if key in ('search','liked'):
            from .music import play_selection
            return play_selection(self.desktop,query if key=='search' else None)
        p=self.player();player=p['player']
        if key=='status':return result(message=f"{p['state']}: {p.get('title') or 'No track'} — {', '.join(p.get('artist') or [])}",player=p)
        if key in ('play','pause','stop','next','previous'):
            action={'play':'Play','pause':'Pause','stop':'Stop','next':'Next','previous':'Previous'}[key]
            self.desktop.bus_call(player,'/org/mpris/MediaPlayer2','org.mpris.MediaPlayer2.Player',action)
            if key=='next':check=lambda q:q.get('track_id')!=p.get('track_id')
            elif key=='previous':check=lambda q:q.get('track_id')!=p.get('track_id') or (p.get('position_us',0)>2_000_000 and q.get('position_us',0)<1_000_000)
            elif key=='stop':check=lambda q:q.get('state') in ('Stopped','Paused')
            else:check=lambda q:q.get('state')=={'play':'Playing','pause':'Paused'}[key]
            after=wait_until(lambda:next((q for q in self.desktop.media_status()['players'] if q['player']==player),{}),check,3)
            return result(player=after)
        if key in ('forward','back'):
            delta=10_000_000 if key=='forward' else -10_000_000
            self.desktop.bus_call(player,'/org/mpris/MediaPlayer2','org.mpris.MediaPlayer2.Player','Seek',GLib.Variant('(x)',(delta,)))
            old=p.get('position_us') or 0
            after=wait_until(lambda:self.media_props(player),lambda q: q.get('Position',0)>=old+8_000_000 if delta>0 else q.get('Position',0)<=max(0,old-8_000_000),3)
            return result(position=after.get('Position'))
        if key=='volume':
            if not 0<=percent<=100:raise CapabilityError('Volume must be between 0 and 100.')
            prop,value,kind='Volume',percent/100,'d'
        elif key.startswith('shuffle'):prop,value,kind='Shuffle',key=='shuffle_on','b'
        else:prop,value,kind='LoopStatus','Playlist' if key=='repeat_on' else 'None','s'
        self.desktop.bus_call(player,'/org/mpris/MediaPlayer2','org.freedesktop.DBus.Properties','Set',GLib.Variant('(ssv)',('org.mpris.MediaPlayer2.Player',prop,GLib.Variant(kind,value))))
        after=wait_until(lambda:self.media_props(player),lambda q:abs(q.get(prop,0)-value)<.015 if kind=='d' else q.get(prop)==value)
        return result(property=prop,value=after[prop])

    def path(self,path,directory=False):
        path=path.strip(' "\'')
        p=self.desktop.home_path(str(Path(path).expanduser()))
        if directory and not p.is_dir():raise CapabilityError('The requested folder does not exist.')
        return p

    def folder(self,name):
        if name=='home':return Path.home()
        # Follow XDG user directories, not English directory-name assumptions.
        try:
            value=command(['xdg-user-dir',name.upper()]).strip()
            return self.path(value,True)
        except (OSError,ValueError,subprocess.SubprocessError):return self.path(str(Path.home()/name.title()),True)

    def files(self,key,path=None,query=None):
        if key in ('home','downloads','desktop','documents','pictures','music','videos'):
            return self.desktop.open_folder(str(self.folder(key)))
        if key=='open':return self.desktop.open_folder(str(self.path(path,True)))
        if key=='mkdir':return self.desktop.mkdir(str(self.path(path)))
        if key=='list':
            data=self.desktop.list_folder(str(self.path(path,True)))
            return result(message='\n'.join(e['kind']+'  '+e['name'] for e in data['entries']) or 'The folder is empty.',**data)
        if key in ('find_file','find_folder'):
            data=self.desktop.find_files(query,str(Path.home()),'file' if key=='find_file' else 'folder')
            return result(message=('\n'.join(e['path'] for e in data['matches']) or 'No matches in the searched locations.')+('\nSearch was limited.' if not data['complete'] else ''),**data)
        if key=='recent':
            paths,complete=self.walk(Path.home());paths=sorted(paths,key=lambda p:p.stat().st_mtime,reverse=True)[:20]
            return result(message='\n'.join(str(p) for p in paths) or 'No recent files in searched locations.',complete=complete)
        p=self.path(path)
        if not p.is_file():raise CapabilityError('The requested file does not exist.')
        if key=='info':return result(message=f'{p}\n{p.stat().st_size:,} bytes\nModified: {datetime.datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")}')
        if p.stat().st_size>65536:raise CapabilityError('Text preview is limited to 64 KiB.')
        return result(message=p.read_text(encoding='utf-8'),path=str(p))

    def system(self,key,percent=None):
        if key in ('volume_up','volume_down','volume','mute','unmute','mic_mute','mic_unmute','audio'):
            target='@DEFAULT_AUDIO_SOURCE@' if key.startswith('mic_') else '@DEFAULT_AUDIO_SINK@'
            read=lambda:command(['wpctl','get-volume',target]).strip()
            before=read()
            volume_match=re.search(r'Volume:\s*([\d.]+)',before)
            if not volume_match:raise CapabilityError('No default microphone is available.' if key.startswith('mic_') else 'No default audio output is available.')
            level=float(volume_match[1]);muted='MUTED' in before
            if key=='audio':
                mic=command(['wpctl','get-volume','@DEFAULT_AUDIO_SOURCE@']).strip()
                return result(message='Output: '+before+'\nMicrophone: '+(mic if re.search(r'Volume:',mic) else 'No default microphone.'))
            if key in ('volume_up','volume_down','volume'):
                value=min(1,max(0,level+(.05 if key=='volume_up' else -.05))) if key!='volume' else percent/100
                if not 0<=value<=1:raise CapabilityError('Volume must be between 0 and 100.')
                command(['wpctl','set-volume','--limit','1.0',target,str(value)])
                after=wait_until(read,lambda s:abs(float(re.search(r'Volume:\s*([\d.]+)',s)[1])-value)<.011)
            else:
                wanted=key in ('mute','mic_mute');command(['wpctl','set-mute',target,'1' if wanted else '0'])
                after=wait_until(read,lambda s:('MUTED' in s)==wanted)
            return result(audio=after)
        if key=='memory':
            data={k:int(v.split()[0]) for k,v in (l.split(':',1) for l in Path('/proc/meminfo').read_text().splitlines())}
            return result(message=f"Memory: {(data['MemTotal']-data['MemAvailable'])/1048576:.1f} / {data['MemTotal']/1048576:.1f} GiB used.")
        if key=='cpu':return result(message='CPU load (1, 5, 15 minutes): '+', '.join(f'{v:.2f}' for v in os.getloadavg())+f'\nLogical CPUs: {os.cpu_count()}')
        if key=='disk':
            d=shutil.disk_usage(Path.home());return result(message=f'Home filesystem: {d.free/2**30:.1f} GiB free / {d.total/2**30:.1f} GiB total.')
        if key=='battery':
            batteries=[p for p in Path('/sys/class/power_supply').glob('*') if (p/'type').read_text().strip()=='Battery']
            return result(message='\n'.join(f'{p.name}: {(p/"capacity").read_text().strip()}% — {(p/"status").read_text().strip()}' for p in batteries) or 'No battery is installed.')
        if key=='network':return result(message=command(['nmcli','-t','-f','DEVICE,TYPE,STATE','device','status']).strip())
        if key=='uptime':return result(message=f'System uptime: {float(Path("/proc/uptime").read_text().split()[0])/3600:.2f} hours.')
        return result(message=datetime.datetime.now().astimezone().strftime('%A, %d %B %Y · %H:%M:%S %Z'))

    def workspace(self,key,number=None):
        if key=='list':return result(message='\n'.join(f"{w['id']}: {w['name']} ({w['windows']} windows)" for w in hypr('workspaces')))
        if key in ('switch','move') and not 1<=number<=99:raise CapabilityError('Use a workspace number between 1 and 99.')
        before=hypr('activeworkspace')['id']
        if key=='move':
            w=self.target();dispatch(f'hl.dsp.window.move({{workspace="{number}"}})')
            after=wait_until(lambda:next(c for c in hypr('clients') if c['address']==w['address']),lambda w:w['workspace']['id']==number)
        else:
            if key in ('next','previous'):
                ids=sorted(w['id'] for w in hypr('workspaces') if w['id']>0)
                number=ids[(ids.index(before)+(1 if key=='next' else -1))%len(ids)]
            dispatch(f'hl.dsp.focus({{workspace="{number}"}})')
            after=wait_until(lambda:hypr('activeworkspace'),lambda w:w['id']==number)
        return result(workspace=after)

    def monitor(self,key):
        monitors=sorted(hypr('monitors'),key=lambda m:m['id'])
        if key=='list':return result(message='\n'.join(f"{m['name']}: {m['width']}×{m['height']}, scale {m['scale']}" for m in monitors))
        w=self.target() if key.startswith('move_') else None
        current=w['monitor'] if w else next(m['id'] for m in monitors if m['focused'])
        offset=-1 if key.endswith('previous') else 1
        target=monitors[([m['id'] for m in monitors].index(current)+offset)%len(monitors)]
        # Names are trusted compositor data but still validated before Lua insertion.
        name=target['name']
        if not re.fullmatch(r'[A-Za-z0-9_.-]+',name):raise CapabilityError('Unsupported monitor name.')
        if w:
            dispatch(f'hl.dsp.window.move({{monitor="{name}"}})')
            wait_until(lambda:self.desktop.window(w['address']),lambda c:c['monitor']==target['id'])
        else:
            dispatch(f'hl.dsp.focus({{monitor="{name}"}})')
            wait_until(lambda:hypr('monitors'),lambda ms:any(m['name']==name and m['focused'] for m in ms))
        return result(monitor=name)

    def dev(self,key,path):
        p=self.path(path,True)
        if key.startswith('git_'):
            operations={'git_status':['status','--short','--branch'],'git_branch':['branch','--show-current'],'git_log':['log','-5','--oneline'],'git_diff':['diff','--no-ext-diff','--no-textconv','--stat'],'git_remotes':['remote','-v']}
            output=command(['git','--no-pager','-c','core.fsmonitor=false','-C',str(p),*operations[key]],timeout=5)
            output=re.sub(r'(https?://)[^/@\s]+:[^/@\s]+@',r'\1[redacted]@',output)
            return result(message=output.strip() or 'No changes.',path=str(p))
        if key=='project':
            names=['package.json','pyproject.toml','Cargo.toml','go.mod','CMakeLists.txt','Makefile','README.md','README.txt','AGENTS.md']
            return result(message='\n'.join(name for name in names if (p/name).is_file()) or 'No recognized project manifests.',path=str(p))
        executable='code' if key=='editor' else 'foot'
        if not shutil.which(executable):raise CapabilityError(f'{executable} is not installed.')
        if key in ('claude','codex') and not shutil.which(key):raise CapabilityError(f'{key} is not installed.')
        marker='planet-'+uuid.uuid4().hex[:12]
        argv=['code','--new-window',str(p)] if key=='editor' else ['foot','--app-id='+marker,'--working-directory='+str(p)]
        if key in ('claude','codex'):argv.append(shutil.which(key))
        existing={w['address'] for w in self.desktop.windows()}
        with open(os.devnull,'rb+') as sink:subprocess.Popen(argv,cwd=p,stdin=sink,stdout=sink,stderr=sink,start_new_session=True)
        def matches():return [w for w in self.desktop.windows() if w['address'] not in existing and (w['class']==marker or key=='editor' and w['class'].lower() in ('code','com.microsoft.vscode'))]
        windows=wait_until(matches,bool,8)
        # A visible terminal is not proof that an interactive agent authenticated.
        message='Interactive session opened; complete any sign-in in its terminal.' if key in ('claude','codex') else ''
        return result(message=message,window=windows[0],path=str(p))

    def walk(self,base):
        deadline=time.monotonic()+2;paths=[];complete=True
        for root,dirs,files in os.walk(base,followlinks=False):
            dirs[:]=[d for d in dirs if not d.startswith('.') and d not in ('node_modules','__pycache__','.git','venv')]
            for name in files:
                p=Path(root)/name
                if not name.startswith('.') and not p.is_symlink() and p.is_file():paths.append(p)
                if len(paths)>=5000 or time.monotonic()>deadline:return paths,False
        return paths,complete

    def search(self,key,query=None,path=None):
        if key=='apps':
            found=[a['name'] for a in self.desktop.catalog() if normalized(query) in normalized(a['name'])];return result(message='\n'.join(found) or 'No installed application matches.')
        if key=='windows':
            found=[w['title'] for w in self.desktop.windows() if normalized(query) in normalized(w['title']+' '+w['class'])];return result(message='\n'.join(found) or 'No open window matches.')
        base=self.path(path,True) if key=='size' else Path.home()
        paths,complete=self.walk(base)
        note='\nSearch covers visible home files, excludes caches/dependencies, and is limited to 5,000 files / 2 seconds.'
        if key=='size':return result(message=f'{sum(p.stat().st_size for p in paths):,} bytes in {len(paths)} scanned files.'+note,complete=complete)
        if key=='projects':
            folders={p.parent for p in paths if (p.parent/'.git').exists()};return result(message=('\n'.join(str(p) for p in sorted(folders)) or 'No Git projects found in searched locations.')+note,complete=complete)
        if key=='large':found=sorted(paths,key=lambda p:p.stat().st_size,reverse=True)[:20]
        elif key=='contents':
            found=[];end=time.monotonic()+2
            for p in paths:
                if time.monotonic()>end:complete=False;break
                if p.suffix.lower() not in ('.txt','.md','.py','.js','.ts','.json','.yaml','.yml','.toml') or p.stat().st_size>65536:continue
                try:
                    if query.casefold() in p.read_text('utf-8').casefold():found.append(p)
                except (OSError,UnicodeError):continue
                if len(found)>=30:complete=False;break
        else:
            extensions={'documents':('.pdf','.txt','.md','.docx','.odt'),'pictures':('.png','.jpg','.jpeg','.webp','.svg'),'music':('.mp3','.flac','.wav','.ogg','.m4a'),'videos':('.mp4','.mkv','.webm','.mov')}[key]
            found=[p for p in paths if p.suffix.lower() in extensions and normalized(query) in normalized(p.name)][:30]
        return result(message=('\n'.join(str(p) for p in found) or 'No matches in searched locations.')+note,complete=complete)

    def helper(self,key,expression=None,text=None,minutes=None):
        DATA.mkdir(parents=True,exist_ok=True,mode=0o700)
        if key=='calculate':return result(message=str(calculate(expression)))
        notes=DATA/'notes'
        if key=='note':
            notes.mkdir(exist_ok=True,mode=0o700);p=notes/(datetime.datetime.now().strftime('%Y%m%d-%H%M%S-')+uuid.uuid4().hex[:8]+'.txt')
            with p.open('x') as f:f.write(text+'\n')
            p.chmod(0o600)
            return result(path=str(p),verified=p.read_text()==text+'\n')
        if key=='notes':return result(message='\n'.join(p.name for p in sorted(notes.glob('*.txt'),reverse=True)[:30]) or 'No Planet notes yet.')
        if key=='timers':return result(message=command(['systemctl','--user','list-timers','--all','--no-pager','planet-timer-*']).strip())
        if not 1<=minutes<=1440:raise CapabilityError('Choose between 1 and 1440 minutes.')
        unit='planet-timer-'+uuid.uuid4().hex[:12]
        notify=shutil.which('notify-send')
        if not notify:raise CapabilityError('Desktop notifications are unavailable.')
        command(['systemd-run','--user','--collect','--unit='+unit,'--on-active='+str(minutes)+'m',notify,'Planet',f'Your {minutes}-minute timer has finished.'])
        active=command(['systemctl','--user','show',unit+'.timer','--property=ActiveState','--value']).strip()
        return result(verified=active=='active',unit=unit+'.timer')


def calculate(expression):
    if len(expression)>150:raise CapabilityError('Expression is too long.')
    tree=ast.parse(expression,mode='eval');nodes=list(ast.walk(tree))
    if len(nodes)>50:raise CapabilityError('Expression is too complex.')
    operations={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.FloorDiv:operator.floordiv,ast.Mod:operator.mod,ast.Pow:operator.pow}
    def visit(n):
        if isinstance(n,ast.Constant) and type(n.value) in (int,float) and abs(n.value)<1e15:return n.value
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return (-1 if isinstance(n.op,ast.USub) else 1)*visit(n.operand)
        if isinstance(n,ast.BinOp) and type(n.op) in operations:
            a,b=visit(n.left),visit(n.right)
            if isinstance(n.op,ast.Pow) and abs(b)>12:raise CapabilityError('Exponent is too large.')
            value=operations[type(n.op)](a,b)
            if not isinstance(value,(int,float)) or not math.isfinite(value) or abs(value)>1e30:raise CapabilityError('Result exceeds the numeric limit.')
            return value
        raise CapabilityError('Use numbers and arithmetic operators only.')
    return visit(tree.body)
