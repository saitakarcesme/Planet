import sys,json,pathlib,time,urllib.request,subprocess
root=pathlib.Path(__file__).resolve().parents[1];name=sys.argv[1];port=sys.argv[2] if len(sys.argv)>2 else '8741';path=root/'evidence'/f'{name}-startup.json';d=json.load(open(path))
for _ in range(180):
 try:urllib.request.urlopen('http://127.0.0.1:'+port+'/health',timeout=2);break
 except Exception:pass
 if subprocess.run(['systemctl','--user','is-active','--quiet',d['unit']]).returncode:raise SystemExit('engine failed')
 time.sleep(2)
else:raise SystemExit('engine timeout')
req={'state':'This is a warmup.','questions':{'warm':{'type':'noul','instructions':'Is this a warmup?'}}};t=time.perf_counter()
try:
 with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:'+port+'/v1/systemone',data=json.dumps(req).encode(),headers={'Content-Type':'application/json'}),timeout=180) as r:out=json.load(r)
except Exception as e:
 print(e.read().decode() if hasattr(e,'read') else str(e));raise
# The released shim may hash the checkpoint on first use; drop only that file's cache again.
import os
fd=os.open(root/'model/model.safetensors',os.O_RDONLY);os.posix_fadvise(fd,0,0,os.POSIX_FADV_DONTNEED);os.close(fd)
d.update(first_request_ms=(time.perf_counter()-t)*1000,first_response=out,ready_s=time.time()-d['started']);path.write_text(json.dumps(d,indent=2));print(json.dumps(d),flush=True)
