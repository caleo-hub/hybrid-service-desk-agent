"""Servidor local do frontend; o fluxo do agente roda na API AWS exportada."""
from __future__ import annotations
import json, os, re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[2]; WEB=ROOT/'apps'/'web'; CONFIG=WEB/'config.local.js'
def api_url():
 match=re.search(r"apiUrl\s*:\s*['\"](https://[^'\"\s]+)['\"]",CONFIG.read_text()) if CONFIG.exists() else None
 return match.group(1) if match else None
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**k): super().__init__(*a,directory=str(WEB),**k)
 def do_GET(self):
  if urlparse(self.path).path=='/api/health': return self.send_json({'status':'ok','apiConfigured':bool(api_url())})
  super().do_GET()
 def do_POST(self):
  if urlparse(self.path).path!='/api/message':self.send_error(404);return
  target=api_url()
  if not target:return self.send_json({'error':'API AWS não configurada. Execute make deploy e make seed.'},503)
  try:
   body=self.rfile.read(int(self.headers.get('Content-Length','0'))); request=Request(target.rstrip('/')+'/message',data=body,headers={'Content-Type':'application/json'},method='POST')
   with urlopen(request,timeout=35) as response:self.send_json(json.loads(response.read()),response.status)
  except HTTPError as error:self.send_json(json.loads(error.read() or b'{"error":"Erro na API"}'),error.code)
  except (URLError,TimeoutError,ValueError) as error:self.send_json({'error':f'Falha ao chamar a API AWS: {error}'},502)
 def send_json(self,payload,status=200):
  raw=json.dumps(payload,ensure_ascii=False,default=str).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
if __name__=='__main__':
 port=int(os.getenv('PORT','3100'));print(f'Hybrid Service Desk Agent em http://localhost:{port}');ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
