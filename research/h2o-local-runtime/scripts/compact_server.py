"""Text-only two-way deployment: stock vLLM offline engine + unchanged released shim.
The adapter removes a duplicate Python API/engine process. CUDA stays on one thread.
No changes to weights, prompts, calibration, or the upstream identity/probe checks.
"""
import os
os.environ.setdefault('VLLM_ENABLE_V1_MULTIPROCESSING','0')
os.environ.setdefault('VLLM_WORKER_MULTIPROC_METHOD','spawn')
os.environ.setdefault('OMP_NUM_THREADS','2')
os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
os.environ.setdefault('HF_HUB_OFFLINE','1')
import sys,pathlib,json,concurrent.futures,argparse,time,threading
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'model'))
import h2o_lightning_shim as shipped
class LocalBackend:
 def __init__(self,tp,util,graphs=False):
  self.base='local-vllm-offline';self.model='h2oai/h2o-lightning-4b';self.worker=concurrent.futures.ThreadPoolExecutor(max_workers=1);self.slot=threading.BoundedSemaphore(4)
  self.worker.submit(self.load,tp,util,graphs).result()
 def load(self,tp,util,graphs):
  from vllm import LLM
  from vllm.config import PoolerConfig
  self.llm=LLM(model=str(ROOT/'model'),runner='pooling',convert='embed',dtype='bfloat16',max_model_len=2048,tensor_parallel_size=tp,gpu_memory_utilization=util,kv_cache_memory_bytes=268435456,max_num_seqs=2,max_num_batched_tokens=2048,enforce_eager=not graphs,enable_prefix_caching=False,enable_chunked_prefill=False,limit_mm_per_prompt={'image':0,'video':0},pooler_config=PoolerConfig(task='embed',seq_pooling_type='LAST',use_activation=False),hf_overrides={'is_causal':False,'text_config':{'is_causal':False}},disable_log_stats=True)
  self.tokenizer=self.llm.get_tokenizer()
  # Release checkpoint page cache after copying to GPU, without affecting file contents.
  fd=os.open(ROOT/'model/model.safetensors',os.O_RDONLY);os.posix_fadvise(fd,0,0,os.POSIX_FADV_DONTNEED);os.close(fd)
 def call(self,method,path,body=None):
  if method=='GET' and path=='/v1/models':return 200,{'data':[{'id':self.model,'max_model_len':2048}]}
  raise shipped.Unprocessable('Unsupported local backend route')
 def tokenize(self,text):return self.tokenizer.encode(text,add_special_tokens=False)
 def detokenize(self,ids):return self.tokenizer.decode(ids)
 def tokenize_chat(self,messages):raise shipped.Unprocessable("This local deployment accepts text only; image inputs are disabled")
 def embed(self,endpoint,token_ids=None,messages=None,max_pixels=0):
  if messages is not None:raise shipped.Unprocessable('This local deployment accepts text only')
  if len(token_ids)>2048:raise shipped.Unprocessable('Input exceeds maximum context length 2048')
  if not self.slot.acquire(blocking=False):raise shipped.UpstreamError('Local decision queue is full',429)
  try:return self.worker.submit(self._embed,token_ids).result(timeout=120)
  finally:self.slot.release()
 def _embed(self,ids):
  r=self.llm.embed([{'prompt_token_ids':ids}],use_tqdm=False)[0]
  return r.outputs.embedding,len(ids)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--tp',type=int,default=1);ap.add_argument('--util',type=float,default=.4);ap.add_argument('--port',type=int,default=8741);ap.add_argument('--graphs',action='store_true');a=ap.parse_args();t=time.monotonic()
 backend=LocalBackend(a.tp,a.util,a.graphs);cfg=json.load(open(ROOT/'model/serve_config.json'));cfg['_config_dir']=str(ROOT/'model');shim=shipped.Shim(shipped.Contract(cfg),min_context=2048,two_way_vllm=backend,model_dir=str(ROOT/'model'))
 print(json.dumps({'event':'loaded','seconds':time.monotonic()-t}),flush=True)
 server=shipped.Server(('127.0.0.1',a.port),shipped.make_handler(shim));server.serve_forever()
if __name__=='__main__':main()
