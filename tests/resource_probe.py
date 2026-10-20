"""Read-only resource sampling during an opt-in acceptance suite."""
import argparse,json,pathlib,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('tag');a=p.parse_args()
base=ROOT/'output/acceptance';out=base/(a.tag+'-resources.jsonl');end=time.monotonic()+7200
while time.monotonic()<end and not (base/(a.tag+'-summary.json')).exists():
    try:
        memory={k:int(v.split()[0]) for k,v in (l.split(':',1) for l in pathlib.Path('/proc/meminfo').read_text().splitlines())}
        gpu=subprocess.check_output(['nvidia-smi','--query-gpu=index,memory.used,memory.free,utilization.gpu,power.draw,temperature.gpu','--format=csv,noheader,nounits'],text=True,timeout=4)
        start=time.monotonic();subprocess.run(['hyprctl','-j','cursorpos'],stdout=subprocess.DEVNULL,check=True,timeout=3);latency=(time.monotonic()-start)*1000
        row={'time':time.time(),'available_ram_mib':round(memory['MemAvailable']/1024,1),'swap_used_mib':round((memory['SwapTotal']-memory['SwapFree'])/1024,1),'desktop_ipc_ms':round(latency,3),'gpu':[list(map(float,l.split(','))) for l in gpu.strip().splitlines()]}
        with out.open('a') as f:f.write(json.dumps(row)+'\n')
    except Exception as error:
        with out.open('a') as f:f.write(json.dumps({'time':time.time(),'error':str(error)})+'\n')
    time.sleep(3)
print('Resource sampling finished:',out)
