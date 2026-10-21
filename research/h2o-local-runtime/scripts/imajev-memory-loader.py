"""Run the existing imajev server with identical weights, on-GPU loading to reduce peak RAM."""
import sys,runpy,os
from transformers import Qwen3_5ForConditionalGeneration
original=Qwen3_5ForConditionalGeneration.from_pretrained
@classmethod
def load(cls,*args,**kwargs):
 kwargs.setdefault('device_map',{'':'cuda'});kwargs.setdefault('low_cpu_mem_usage',True)
 return original(*args,**kwargs)
Qwen3_5ForConditionalGeneration.from_pretrained=load
os.chdir('/home/isa/Projects/imajev');sys.path.insert(0,'/home/isa/Projects/imajev/scripts');sys.argv=['scripts/playground/server.py','--backend','torch','--model-bundle','artifacts/model-qwen4b.json','--adapter','adapters/imajev-4b','--rotations','1','--calibration','adapters/imajev-4b/calibration.json','--model-name','imajev-4b','--max-input-tokens','2048','--host','127.0.0.1','--port','8741']
runpy.run_path('scripts/playground/server.py',run_name='__main__')
