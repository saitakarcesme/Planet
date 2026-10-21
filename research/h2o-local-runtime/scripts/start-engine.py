import argparse,subprocess,json,time,pathlib,urllib.request
p=argparse.ArgumentParser();p.add_argument('--name',default='single');p.add_argument('--gpus',default='1');p.add_argument('--tp',default='1');p.add_argument('--mode',default='two');p.add_argument('--port',default='8751');p.add_argument('--util',default='.45');a=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[1]; unit='h2ol-'+a.name
cmd=['systemd-run','--user','--unit='+unit,'--collect','-p','MemoryHigh=6500M','-p','MemoryMax=7G','-p','MemorySwapMax=0','-p','CPUQuota=250%','-p','Nice=10','-p','IOWeight=20','-p','TasksMax=256','-p','WorkingDirectory='+str(root),'-p','StandardOutput=append:'+str(root/'evidence'/f'{a.name}-engine.log'),'-p','StandardError=inherit']
for k,v in {'GPUS':a.gpus,'TP':a.tp,'MODE':a.mode,'ENGINE_PORT':a.port,'GPU_UTIL':a.util}.items():cmd+=['--setenv='+k+'='+v]
cmd += [str(root/'scripts/engine.sh')];t=time.monotonic();subprocess.run(cmd,check=True)
with (root/'evidence'/f'{a.name}-startup.json').open('w') as f:json.dump({'started':time.time(),'command':cmd,'unit':unit},f,indent=2)
print(unit,flush=True)
