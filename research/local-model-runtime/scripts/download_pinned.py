"""Pinned, serial HTTPS downloads with bounded buffers and page-cache release."""
import hashlib,json,os,pathlib,time,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
SPECS=[('base','dbirks/Qwen3.8-27B-W4A16-AutoRound','1f05c441c4e64ae0549de44fa9ea5a6d43610314'),('fast','syvai/qwen3.8-27b-3090-fast-variant','124c14e7e8c7d2f5402933b9af368e772a9fcf0c'),('dflash','syvai/Qwen3.8-27B-DFlash2-W4A16','4d30ec736ffc6b8688dc2ae2b502d9b48bdec279')]
manifest=[]
for label,repo,rev in SPECS:
    with urllib.request.urlopen(f'https://huggingface.co/api/models/{repo}/revision/{rev}?blobs=true',timeout=60) as r: info=json.load(r)
    assert info['sha']==rev
    (ROOT/'evidence'/f'hyper-{label}-blobs.json').write_text(json.dumps(info,indent=2))
    dest=ROOT/'models'/label;dest.mkdir(parents=True,exist_ok=True)
    for entry in info['siblings']:
        name=entry['rfilename']
        if '/' in name or name.startswith('.'):continue
        if label=='base' and name in ['model-00007-of-00007.safetensors','model_extra_tensors.safetensors']:continue
        if not name.endswith(('.json','.jinja','.safetensors','.pt','.md')):continue
        path=dest/name;temp=path.with_name(name+'.part');expected=entry.get('lfs',{}).get('sha256');size=entry.get('size');digest=hashlib.sha256();start=time.monotonic()
        if path.exists() and path.stat().st_size==size:
            with path.open('rb') as f:
                while chunk:=f.read(8*1024**2):digest.update(chunk)
                os.posix_fadvise(f.fileno(),0,0,os.POSIX_FADV_DONTNEED)
            if not expected or digest.hexdigest()==expected:
                manifest.append(dict(repo=repo,revision=rev,file=name,bytes=size,sha256=digest.hexdigest(),cached=True));continue
        digest=hashlib.sha256();count=0;flushed=0
        for attempt in range(3):
            try:
                digest=hashlib.sha256();count=0;flushed=0
                if temp.exists():
                    with temp.open('rb') as previous:
                        while chunk:=previous.read(8*1024**2):digest.update(chunk);count+=len(chunk)
                        os.posix_fadvise(previous.fileno(),0,0,os.POSIX_FADV_DONTNEED)
                request=urllib.request.Request(f'https://huggingface.co/{repo}/resolve/{rev}/{name}',headers={'Range':f'bytes={count}-'} if count else {})
                r=urllib.request.urlopen(request,timeout=120)
                if r.status!=206:digest=hashlib.sha256();count=0
                flushed=count
                with r,temp.open('ab' if count else 'wb',buffering=0) as f:
                    while chunk:=r.read(8*1024**2):
                        f.write(chunk);digest.update(chunk);count+=len(chunk)
                        if count-flushed>=64*1024**2:
                            os.fdatasync(f.fileno());os.posix_fadvise(f.fileno(),0,count,os.POSIX_FADV_DONTNEED);flushed=count
                    os.fdatasync(f.fileno());os.posix_fadvise(f.fileno(),0,0,os.POSIX_FADV_DONTNEED)
                assert size is None or count==size,(name,count,size)
                assert not expected or digest.hexdigest()==expected,(name,'hash mismatch')
                os.replace(temp,path);break
            except Exception as e:
                print(label,name,'attempt failed',attempt+1,type(e).__name__,flush=True)
                if attempt==2:raise
                time.sleep(3)
        row=dict(repo=repo,revision=rev,file=name,bytes=count,sha256=digest.hexdigest(),seconds=time.monotonic()-start)
        manifest.append(row);print(json.dumps(row),flush=True)
        (ROOT/'evidence'/'download-manifest.json').write_text(json.dumps(manifest,indent=2))
(ROOT/'evidence'/'download-manifest.json').write_text(json.dumps(manifest,indent=2))
