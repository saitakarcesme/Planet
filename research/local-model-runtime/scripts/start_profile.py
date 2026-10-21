"""Start only our bounded benchmark unit. Does not stop existing user services."""
import argparse,json,os,pathlib,socket,subprocess,time,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1];REPO=ROOT/'HyperQwen'
p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--tp',type=int,choices=[1,2],default=1);p.add_argument('--gpu',default='1');p.add_argument('--spec',choices=['off','mtp','dflash2'],default='mtp');p.add_argument('--vocab',choices=['0','1'],default='0');p.add_argument('--ctx',type=int,default=16384);p.add_argument('--prefix',choices=['0','1'],default='0');p.add_argument('--int8',action='store_true');p.add_argument('--kv-format',choices=['bf16','int8'],default='bf16');p.add_argument('--kv',type=int,default=2048);p.add_argument('--eager',action='store_true');a=p.parse_args()
assert a.name.replace('-','').isalnum();unit='petlab-'+a.name
with socket.socket() as s:assert s.connect_ex(('127.0.0.1',18020))!=0,'benchmark port occupied'
mem={k:int(v.split()[0]) for k,v in (l.split(':',1) for l in pathlib.Path('/proc/meminfo').read_text().splitlines())}
assert mem['MemAvailable']>13*1024**2,'Require 13 GiB available host RAM'
free={int(i):int(v) for i,v in (l.split(',') for l in subprocess.check_output(['nvidia-smi','--query-gpu=index,memory.free','--format=csv,noheader,nounits'],text=True).splitlines())}
gpus=a.gpu if a.tp==1 else '0,1';need=21000 if a.tp==1 else 12500
assert all(free[int(g)]>need for g in gpus.split(',')),('Insufficient free VRAM',free,need)
env={'CUDA_VISIBLE_DEVICES':gpus,'CUDA_DEVICE_ORDER':'PCI_BUS_ID','MODEL':str(ROOT/'models'/'fast'),'DRAFT':str(ROOT/'models'/'dflash'),'PORT':'18020','HOST':'127.0.0.1','CTX':'fast','SPEC':a.spec,'MAX_LEN':str(a.ctx),'MAX_SEQS':'2','CG':'8','KV_MEM':str(a.kv*1024**2),'GPU_UTIL':'.90','REQ_METRICS':'1','PREFIX_CACHE':a.prefix,'MTP_DRAFT_VOCAB':a.vocab,'VLLM_OFFLOAD_KEEP_SHM':'1','HF_HUB_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false','OMP_NUM_THREADS':'2','TORCHINDUCTOR_COMPILE_THREADS':'1','MAX_JOBS':'2','PYTORCH_CUDA_ALLOC_CONF':'expandable_segments:False','VLLM_CACHE_ROOT':str(ROOT/'cache'/'vllm'),'TRITON_CACHE_DIR':str(ROOT/'cache'/'triton'),'TORCHINDUCTOR_CACHE_DIR':str(ROOT/'cache'/'inductor'),'CUDA_CACHE_PATH':str(ROOT/'cache'/'cuda')}
env['CUDA_HOME']=str(REPO/'venv/lib/python3.12/site-packages/nvidia/cu13')
env['PATH']=env['CUDA_HOME']+'/bin:'+os.environ['PATH']
# Extend the upstream huge-context MTP/prefix correctness precaution to this
# bounded BF16 deployment as well. Do not depend on the launcher's CTX branch.
if a.spec=='mtp' and a.prefix=='1':env['CUDAGRAPH_MODE']='PIECEWISE'
extra=['--load-format=runai_streamer','--model-loader-extra-config={"memory_limit":2147483648}',f'--tensor-parallel-size={a.tp}','--disable-custom-all-reduce']
if a.eager:extra.append('--enforce-eager')
if a.spec=='off':extra.append('--per-request-spec-decode-metrics=none')
env['EXTRA_ARGS']=' '.join(extra)
if a.int8:env['INT8_ACT']='int8'
if a.kv_format=='int8':
 assert a.spec in ['dflash2','mtp'],'int8 KV requires one of the documented speculative paths'
 if a.spec=='dflash2':env.update(CTX='long',FA2_FP8KV='0',PTH_FA='0')
 else:env['EXTRA_ARGS']+=' --attention-backend=TRITON_ATTN --kv-cache-dtype=int8_per_token_head'
dry=subprocess.run(['bash',str(REPO/'single-user/start_qwen.sh')],env={**os.environ,**env,'PRINT_ARGV':'1'},capture_output=True,text=True,check=True)
(ROOT/'evidence'/f'{a.name}-launch.txt').write_text(json.dumps(env,indent=2)+'\n'+dry.stdout+'\n'+dry.stderr)
command=['systemd-run','--user',f'--unit={unit}','--property=MemoryHigh=10G','--property=MemoryMax=12G','--property=MemorySwapMax=0','--property=CPUQuota=400%','--property=Nice=10','--property=IOWeight=20','--property=TimeoutStopSec=20',f'--property=StandardOutput=append:{ROOT}/evidence/{a.name}-server.log',f'--property=StandardError=append:{ROOT}/evidence/{a.name}-server.log']
command += ['--setenv='+k+'='+v for k,v in env.items()]
command += ['bash',str(REPO/'single-user/start_qwen.sh')]
start=time.monotonic();stamp=time.time();subprocess.run(command,check=True)
state_path=ROOT/'STATE.json'
if state_path.exists():
 state=json.loads(state_path.read_text());state.update(running_profile=unit,updated=stamp);state_path.write_text(json.dumps(state,indent=2))
ready=False
for iteration in range(1200):
 # The streamer copies into its own bounded buffers. Its file page cache is
 # dispensable; release only our checkpoint pages every two seconds, including
 # the drafter's second pass, instead of waiting for all weights to finish.
 if iteration%2==0:
  for folder in ['fast','dflash']:
   for path in (ROOT/'models'/folder).glob('*.safetensors'):
    fd=os.open(path,os.O_RDONLY);os.posix_fadvise(fd,0,0,os.POSIX_FADV_DONTNEED);os.close(fd)
 try:
  with urllib.request.urlopen('http://127.0.0.1:18020/health',timeout=1) as r:
   if r.status==200:ready=True;break
 except Exception:pass
 if subprocess.run(['systemctl','--user','is-active','--quiet',unit]).returncode:break
 time.sleep(1)
if ready:
 for folder in ['fast','dflash']:
  for path in (ROOT/'models'/folder).glob('*.safetensors'):
   fd=os.open(path,os.O_RDONLY);os.posix_fadvise(fd,0,0,os.POSIX_FADV_DONTNEED);os.close(fd)
result={'name':a.name,'unit':unit,'args':vars(a),'start_time':stamp,'ready':ready,'startup_s':time.monotonic()-start}
result['resources']=subprocess.check_output(['systemctl','--user','show',unit,'-p','MemoryCurrent','-p','MemoryPeak','-p','MemorySwapCurrent','-p','CPUUsageNSec','-p','Result'],text=True)
(ROOT/'evidence'/f'{a.name}-startup.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result),flush=True)
if not ready:raise SystemExit(1)
