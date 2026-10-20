"""One hundred explicit local capabilities; anchored aliases are user-approved.

Aliases select typed recipes, never shell text. Unmatched/compound requests go
back to the observed model planner. A registry entry is not a success claim.
"""
import json
import re
import unicodedata

SKILLS = []
def add(id, title, aliases, params=None, **fixed):
    SKILLS.append(dict(id=id, title=title, aliases=aliases, params=params or {}, fixed=fixed))

add('app.open', 'Open an installed native application', ['open {app}', '{app} ac'], {'app':'string'})
add('app.focus', 'Focus an existing application', ['focus {app}', '{app} uygulamasina gec'], {'app':'string'})
for key,title,aliases in [
 ('maximize','Maximize current window',['maximize window','pencereyi buyut']),
 ('fullscreen','Fullscreen current window',['fullscreen window','tam ekran yap']),
 ('restore','Restore current window',['restore window','tam ekrandan cik']),
 ('float','Float current window',['float window','pencereyi yuzdur']),
 ('tile','Tile current window',['tile window','pencereyi dose']),
 ('center','Center floating window',['center window','pencereyi ortala'])]:add('window.'+key,title,aliases)
for key,tr in [('left','sol'),('right','sag'),('up','ust'),('down','alt')]:
    add('window.focus_'+key,'Focus '+key+' window',['focus '+key+' window',tr+' pencereye gec'])
    add('window.move_'+key,'Move current window '+key,['move window '+key,'pencereyi '+tr+' tarafa tasi'])
for key,tr in [('wider','genislet'),('narrower','daralt'),('taller','uzat'),('shorter','kisalt')]:
    add('window.'+key,'Make current window '+key,['make window '+key,'pencereyi '+tr])

for key,title,aliases in [
 ('play','Resume media',['resume music','play music','muzigi devam ettir','muzik cal']),
 ('pause','Pause media',['pause music','muzigi duraklat','muzigi durdur']),
 ('next','Next track',['next track','sonraki sarki']),
 ('previous','Previous track',['previous track','onceki sarki']),
 ('stop','Stop media',['stop playback','calmayi durdur']),
 ('status','Current track information',['what is playing','current track','ne caliyor']),
 ('forward','Seek forward ten seconds',['skip forward','10 saniye ileri sar']),
 ('back','Seek back ten seconds',['skip back','10 saniye geri sar']),
 ('shuffle_on','Enable shuffle',['shuffle on','karisik calma ac']),
 ('shuffle_off','Disable shuffle',['shuffle off','karisik calma kapat']),
 ('repeat_on','Repeat playlist',['repeat playlist','liste tekrarini ac']),
 ('repeat_off','Disable repeat',['repeat off','tekrari kapat']),
 ('liked','Play a personal liked song',['play my liked songs','begenilen sarkilarimdan birini cal','spotify begenilenlerden cal'])]:add('media.'+key,title,aliases)
add('media.volume','Set player volume percent',['music volume {percent}','muzik sesini {percent} yap'],{'percent':'integer'})
add('media.search','Find and play an artist or song in Spotify',['play {query} on spotify','spotify play {query}','spotifydan {query} sarkisi ac bir tane','spotifydan {query} cal','spotifyda {query} cal',"spotify'da {query} cal",'spotifyda {query} ac',"spotify'da {query} ac",'{query} cal'],{'query':'string'})

for key,tr in [('home','ev'),('downloads','indirilenler'),('desktop','masaustu'),('documents','belgeler'),('pictures','resimler'),('music','muzik'),('videos','videolar')]:
    add('files.'+key,'Open '+key+' folder',['open '+key+' folder',tr+' klasorunu ac'],folder=key)
for key,title,aliases,params in [
 ('open','Open a folder',['open folder {path}','{path} klasorunu ac'],{'path':'string'}),
 ('mkdir','Create a folder',['create folder {path}','{path} klasoru olustur'],{'path':'string'}),
 ('list','List folder contents',['list folder {path}','{path} klasorunu listele'],{'path':'string'}),
 ('find_file','Find a file by name',['find file {query}','{query} dosyasini bul'],{'query':'string'}),
 ('find_folder','Find a folder by name',['find folder {query}','{query} klasorunu bul'],{'query':'string'}),
 ('recent','List recently modified files',['recent files','son dosyalar'],{}),
 ('info','Read file metadata',['file info {path}','{path} dosya bilgisi'],{'path':'string'}),
 ('read','Read a local text file',['read file {path}','{path} dosyasini oku'],{'path':'string'})]:add('files.'+key,title,aliases,params)

for key,title,aliases in [
 ('volume_up','Increase output volume by five percent',['volume up','sesi arttir']),
 ('volume_down','Decrease output volume by five percent',['volume down','sesi azalt']),
 ('mute','Mute output audio',['mute sound','sesi kapat']),
 ('unmute','Unmute output audio',['unmute sound','sesi ac']),
 ('mic_mute','Mute microphone',['mute microphone','mikrofonu kapat']),
 ('mic_unmute','Unmute microphone',['unmute microphone','mikrofonu ac']),
 ('audio','Read audio levels',['audio status','ses durumu']),
 ('memory','Read memory usage',['memory usage','ram kullanimi']),
 ('cpu','Read CPU load',['cpu load','islemci yuku']),
 ('disk','Read free disk space',['free disk space','bos disk alani']),
 ('battery','Read battery state',['battery status','pil durumu']),
 ('network','Read network connections',['network status','ag durumu']),
 ('uptime','Read system uptime',['system uptime','sistem calisma suresi']),
 ('time','Read local date and time',['what time is it','saat kac'])]:add('system.'+key,title,aliases)
add('system.volume','Set output volume percent',['set volume {percent}','sesi {percent} yap'],{'percent':'integer'})

for key,title,aliases,params in [
 ('switch','Switch to workspace',['workspace {number}','calisma alani {number}'],{'number':'integer'}),
 ('move','Move current window to workspace',['move window to workspace {number}','pencereyi {number} calisma alanina tasi'],{'number':'integer'}),
 ('next','Next existing workspace',['next workspace','sonraki calisma alani'],{}),
 ('previous','Previous existing workspace',['previous workspace','onceki calisma alani'],{}),
 ('list','List workspaces',['list workspaces','calisma alanlarini listele'],{})]:add('workspace.'+key,title,aliases,params)
for key,title,aliases in [
 ('next','Focus next monitor',['next monitor','sonraki ekrana gec']),
 ('previous','Focus previous monitor',['previous monitor','onceki ekrana gec']),
 ('move_next','Move window to next monitor',['move window to next monitor','pencereyi sonraki ekrana tasi']),
 ('move_previous','Move window to previous monitor',['move window to previous monitor','pencereyi onceki ekrana tasi']),
 ('list','List monitor geometry',['list monitors','ekranlari listele'])]:add('monitor.'+key,title,aliases)

for key,title,aliases in [
 ('terminal','Open terminal in folder',['terminal in {path}','{path} icinde terminal ac']),
 ('editor','Open folder in code editor',['edit project {path}','{path} projesini editorde ac']),
 ('git_status','Git working tree status',['git status {path}','{path} git durumu']),
 ('git_branch','Read Git branch',['git branch {path}','{path} git dali']),
 ('git_log','Read recent Git commits',['git log {path}','{path} son commitler']),
 ('git_diff','Read Git diff',['git diff {path}','{path} degisiklikleri']),
 ('git_remotes','Read Git remotes',['git remotes {path}','{path} uzak repolar']),
 ('claude','Open interactive Claude session in folder',['claude in {path}','{path} icinde claude ac']),
 ('codex','Open interactive Codex session in folder',['codex in {path}','{path} icinde codex ac']),
 ('project','Inspect project manifests',['inspect project {path}','{path} projesini incele'])]:add('dev.'+key,title,aliases,{'path':'string'})

for key,title,aliases,params in [
 ('apps','Find installed applications',['find app {query}','{query} uygulamasini bul'],{'query':'string'}),
 ('windows','Find open windows',['find window {query}','{query} penceresini bul'],{'query':'string'}),
 ('projects','Find local Git projects',['find projects','projeleri bul'],{}),
 ('contents','Search plain text contents',['search text {query}','metin ara {query}'],{'query':'string'}),
 ('documents','Find documents by name',['find document {query}','belge ara {query}'],{'query':'string'}),
 ('pictures','Find images by name',['find image {query}','resim ara {query}'],{'query':'string'}),
 ('music','Find local audio by name',['find audio {query}','ses dosyasi ara {query}'],{'query':'string'}),
 ('videos','Find local video by name',['find video {query}','video ara {query}'],{'query':'string'}),
 ('large','Find largest local files',['find large files','buyuk dosyalari bul'],{}),
 ('size','Measure folder size',['folder size {path}','{path} klasor boyutu'],{'path':'string'})]:add('search.'+key,title,aliases,params)

add('helper.calculate','Calculate an arithmetic expression',['calculate {expression}','hesapla {expression}'],{'expression':'string'})
add('helper.note','Save a new plain-text note',['note {text}','not al {text}'],{'text':'string'})
add('helper.notes','List Planet notes',['list notes','notlari listele'])
add('helper.timer','Start a timer in minutes',['timer {minutes}','{minutes} dakika zamanlayici'],{'minutes':'integer'})
add('helper.timers','List Planet timers',['list timers','zamanlayicilari listele'])

BY_ID = {s['id']: s for s in SKILLS}
assert len(SKILLS) == len(BY_ID) == 100

def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',text.casefold().replace('ı','i')) if not unicodedata.combining(c))

def match(text):
    """Full-string matches only. Preserve original paths, case and user content."""
    source=text.strip()
    # A compound request must never partially execute a single recipe.
    if re.search(r'\b(and then|then|and|sonra|ardindan|ve)\b|[;\n]',normalized(source)):
        return None
    matches=[]
    for skill in SKILLS:
        for alias in skill['aliases']:
            pattern=re.escape(alias)
            for name,kind in skill['params'].items():
                pattern=pattern.replace(re.escape('{'+name+'}'), '(?P<'+name+'>'+ (r'\d+' if kind=='integer' else r'.+?') +')')
            found=re.fullmatch(pattern,normalized(source))
            if found:
                # NFKD may change string lengths: recover captures with a mapped
                # normalized index, retaining accented Unicode paths verbatim.
                offsets=[]
                for index,char in enumerate(source):offsets.extend([index]*len(normalized(char)))
                values={k:source[offsets[a]:offsets[b] if b<len(offsets) else len(source)] for k in skill['params'] for a,b in [found.span(k)]}
                for k,kind in skill['params'].items():
                    if kind=='integer':values[k]=int(values[k])
                matches.append((skill['id'],values,len(re.sub(r'\{\w+\}', '', alias))))
    if not matches:return None
    # Specific phrases beat generic app/music catch-alls.
    matches.sort(key=lambda m:m[2],reverse=True)
    return matches[0][:2]


def validate(id, args):
    skill=BY_ID.get(id)
    if not skill or not isinstance(args,dict) or set(args)!=set(skill['params']):raise ValueError('Invalid capability arguments.')
    for name,kind in skill['params'].items():
        value=args[name]
        if kind=='integer' and (type(value)!=int or not 0<=value<=10000):raise ValueError('Invalid numeric value.')
        if kind=='string' and (not isinstance(value,str) or not value.strip() or len(value)>4000 or any(ord(c)<32 for c in value)):raise ValueError('Use a non-empty single-line value.')
    return skill

if __name__=='__main__':
    print(json.dumps(SKILLS,ensure_ascii=False,indent=2))
