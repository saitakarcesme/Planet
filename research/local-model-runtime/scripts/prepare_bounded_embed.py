"""Assemble pinned fast variant with official pack(), in small independent row blocks.

The official quant_schema.pack states rows are independent. We use that same
function on 512-row slices and stream the resulting tensors to keep RAM bounded.
Original downloaded shards are never modified. No CUDA is used.
"""
import hashlib,json,os,pathlib,shutil,struct,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'HyperQwen'/'prepare'))
import torch
from quant_schema import pack
torch.set_num_threads(2)
BASE=ROOT/'models'/'base';DEST=ROOT/'models'/'fast'
source=BASE/'model-00006-of-00007.safetensors';output=DEST/source.name
def header(path):
    with path.open('rb') as f:
        size=struct.unpack('<Q',f.read(8))[0];return json.loads(f.read(size)),8+size
def sync_drop(f):
    f.flush();os.fdatasync(f.fileno());os.posix_fadvise(f.fileno(),0,0,os.POSIX_FADV_DONTNEED)
def raw(t):return t.contiguous().view(torch.uint8).numpy().tobytes()
# Explicitly verify that the installed official implementation is chunk invariant.
torch.manual_seed(42);toy=torch.randn(1024,256,dtype=torch.bfloat16)
whole,_=pack('x',toy,8,torch.bfloat16,rows=1024)
left,_=pack('x',toy[:512],8,torch.bfloat16,rows=512)
right,_=pack('x',toy[512:],8,torch.bfloat16,rows=512)
for suffix in ['weight_packed','weight_scale']:
    assert torch.equal(whole['x.'+suffix],torch.cat([left['x.'+suffix],right['x.'+suffix]]))
del toy,whole,left,right
h,start=header(source);key=next(k for k in h if k.endswith('embed_tokens.weight'));base=key[:-7]
assert h[key]['dtype']=='BF16';rows,cols=h[key]['shape'];assert rows%512==0 and cols%128==0
packed_path=DEST/'embed-packed.part';scale_path=DEST/'embed-scales.part';max_error=0;error_numerator=0;error_denominator=0
with source.open('rb') as src,packed_path.open('wb') as p,scale_path.open('wb') as s:
    src.seek(start+h[key]['data_offsets'][0])
    for lo in range(0,rows,512):
        buf=bytearray(src.read(512*cols*2));assert len(buf)==512*cols*2
        w=torch.frombuffer(buf,dtype=torch.bfloat16).reshape(512,cols)
        values,err=pack(base,w,8,torch.bfloat16,rows=512)
        energy=w.float().square().sum().item()
        if energy:
            error_numerator+=err*err*energy;error_denominator+=energy;max_error=max(max_error,err)
        p.write(raw(values[base+'.weight_packed']));s.write(raw(values[base+'.weight_scale']))
        del values,w,buf
        if lo%8192==0:sync_drop(p);sync_drop(s);os.posix_fadvise(src.fileno(),0,src.tell(),os.POSIX_FADV_DONTNEED)
    sync_drop(p);sync_drop(s);os.posix_fadvise(src.fileno(),0,0,os.POSIX_FADV_DONTNEED)
relative_error=(error_numerator/error_denominator)**.5
assert relative_error<.01,('official whole-table error bound exceeded',relative_error)
new={};sources={}
for name,info in h.items():
    if name in ['__metadata__',key]:continue
    sources[name]=(source,start+info['data_offsets'][0],info['data_offsets'][1]-info['data_offsets'][0])
    new[name]={'dtype':info['dtype'],'shape':info['shape']}
for suffix,dtype,shape,path in [('weight_packed','I32',[rows,cols//4],packed_path),('weight_scale','BF16',[rows,cols//128],scale_path)]:
    name=base+'.'+suffix;new[name]={'dtype':dtype,'shape':shape};sources[name]=(path,0,path.stat().st_size)
shape_name=base+'.weight_shape';new[shape_name]={'dtype':'I64','shape':[2]};shape_bytes=struct.pack('<qq',rows,cols)
position=0
for name in sorted(new):
    size=16 if name==shape_name else sources[name][2]
    new[name]['data_offsets']=[position,position+size];position+=size
new['__metadata__']=h.get('__metadata__',{'format':'pt'})
encoded=json.dumps(new,separators=(',',':')).encode();encoded+=b' '*((-len(encoded))%8)
tmp=output.with_name(output.name+'.part')
with tmp.open('wb') as dst:
    dst.write(struct.pack('<Q',len(encoded)));dst.write(encoded)
    for name in sorted(n for n in new if n!='__metadata__'):
        if name==shape_name:dst.write(shape_bytes);continue
        path,offset,size=sources[name]
        with path.open('rb') as src:
            src.seek(offset);since=0
            while size:
                chunk=src.read(min(size,8*1024**2));assert chunk;dst.write(chunk);size-=len(chunk);since+=len(chunk)
                if since>=64*1024**2:sync_drop(dst);since=0;os.posix_fadvise(src.fileno(),0,src.tell(),os.POSIX_FADV_DONTNEED)
            os.posix_fadvise(src.fileno(),0,0,os.POSIX_FADV_DONTNEED)
    sync_drop(dst)
os.replace(tmp,output)
packed_path.unlink();scale_path.unlink()
for path in BASE.iterdir():
    if path.name in ['config.json','model.safetensors.index.json',source.name,'README.md']:continue
    target=DEST/path.name
    if target.exists():continue
    if path.suffix=='.safetensors':os.link(path,target)
    elif path.suffix in ['.json','.jinja']:shutil.copyfile(path,target)
# Verify the published index resolves every tensor with matching shard names.
index=json.loads((DEST/'model.safetensors.index.json').read_text())['weight_map'];headers={}
for shard in set(index.values()):headers[shard]=header(DEST/shard)[0]
for name,shard in index.items():assert name in headers[shard],(name,shard)
digest=hashlib.sha256()
with output.open('rb') as f:
    while chunk:=f.read(8*1024**2):digest.update(chunk)
    os.posix_fadvise(f.fileno(),0,0,os.POSIX_FADV_DONTNEED)
result={'source':str(source),'output':str(output),'sha256':digest.hexdigest(),'shape':[rows,cols],'bits':8,'group_size':128,'row_chunk':512,'relative_error':relative_error,'max_chunk_relative_error':max_error,'official_pack_chunk_parity':True,'index_tensor_count':len(index)}
(ROOT/'evidence'/'embedding-preparation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
