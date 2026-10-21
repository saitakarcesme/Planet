import argparse,subprocess,pathlib,time,json,urllib.request
p=argparse.ArgumentParser();p.add_argument('--name',default='single-two');p.add_argument('--mode',default='two');p.add_argument('--engine-port',default='8751');p.add_argument('--port',default='8741');a=p.parse_args();root=pathlib.Path(__file__).resolve().parents[1]
for _ in range(180):
 try: urllib.request.urlopen('http://127.0.0.1:'+a.engine_port+'/health',timeout=2);break
 except Exception:pass
 if subprocess.run(['systemctl','--user','is-active','--quiet','h2ol-'+a.name]).returncode:raise SystemExit('engine failed')
 time.sleep(2)
else:raise SystemExit('engine timeout')
subprocess.run(['systemd-run','--user','--unit=h2ol-shim-'+a.name,'--collect','-p','MemoryMax=512M','-p','MemorySwapMax=0','-p','CPUQuota=100%','-p','Nice=10','-p','StandardOutput=append:'+str(root/'evidence'/f'{a.name}-shim.log'),'-p','StandardError=inherit','--setenv=MODE='+a.mode,'--setenv=ENGINE_PORT='+a.engine_port,'--setenv=PORT='+a.port,str(root/'scripts/start-shim.sh')],check=True)
for _ in range(30):
 try: urllib.request.urlopen('http://127.0.0.1:'+a.port+'/health',timeout=2);break
 except Exception:time.sleep(1)
req={'state':'This is a warmup.','questions':{'warm':{'type':'noul','instructions':'Is this a warmup?'}}};t=time.perf_counter()
try:
 with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:'+a.port+'/v1/systemone',data=json.dumps(req).encode(),headers={'Content-Type':'application/json'}),timeout=180) as r:out=json.load(r)
except Exception as e:
 print(e.read().decode() if hasattr(e,'read') else str(e));raise
path=root/'evidence'/f'{a.name}-startup.json';d=json.load(open(path));d.update(first_request_ms=(time.perf_counter()-t)*1000,first_response=out,ready_s=time.time()-d['started']);path.write_text(json.dumps(d,indent=2));print(json.dumps(d),flush=True)
