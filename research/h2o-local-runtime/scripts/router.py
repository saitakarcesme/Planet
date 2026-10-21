"""Two replicas: GPU1 preferred; simultaneous work may use GPU0. Loopback only."""
import json,threading,urllib.request,urllib.error
import pynvml
pynvml.nvmlInit()
gpu0=pynvml.nvmlDeviceGetHandleByIndex(0)
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
urls=['http://127.0.0.1:8742','http://127.0.0.1:8743'];busy=[0,0];lock=threading.Lock()
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def respond(self,status,body):
  data=json.dumps(body).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
 def do_GET(self):
  if self.path!='/health':return self.respond(404,{'error':'not found'})
  results=[]
  for url in urls:
   try:
    with urllib.request.urlopen(url+'/health',timeout=2) as r:results.append(json.load(r))
   except Exception as e:return self.respond(503,{'error':str(e)})
  self.respond(200,{'replicas':results,'policy':'GPU1 preferred, GPU0 on concurrent work','inflight':busy.copy()})
 def do_POST(self):
  if self.path!='/v1/systemone':return self.respond(404,{'error':'not found'})
  try:n=int(self.headers.get('Content-Length','0'))
  except ValueError:return self.respond(400,{'error':'bad content length'})
  if n<=0 or n>1024*1024:return self.respond(413,{'error':'body size limit'})
  body=self.rfile.read(n)
  with lock:
   if sum(busy)>=4:return self.respond(429,{'error':'bounded local queue full'})
   index=0 if busy[0]<=busy[1] else 1;busy[index]+=1
  try:
   # Leave a 1.5 GiB *free* margin on the desktop GPU; defer to GPU1 otherwise.
   if index==1:
    free=pynvml.nvmlDeviceGetMemoryInfo(gpu0).free//1024**2
    if free<1536:
     with lock:busy[1]-=1;busy[0]+=1
     index=0
   with urllib.request.urlopen(urllib.request.Request(urls[index]+self.path,data=body,headers={'Content-Type':'application/json'}),timeout=120) as r:out=json.load(r);status=r.status
   out['deployment']={'replica_gpu':1 if index==0 else 0};self.respond(status,out)
  except urllib.error.HTTPError as e:
   try:out=json.loads(e.read())
   except Exception:out={'error':str(e)}
   self.respond(e.code,out)
  except Exception as e:self.respond(502,{'error':str(e)})
  finally:
   with lock:busy[index]-=1
ThreadingHTTPServer(('127.0.0.1',8741),Handler).serve_forever()
