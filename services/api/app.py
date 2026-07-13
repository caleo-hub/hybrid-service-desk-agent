from __future__ import annotations
import json, os, uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[2]; WEB=ROOT/'apps'/'web'
STEPS=[('Entender','Intenção identificada'),('Coletar','Dados do incidente coletados'),('Validar','Campos obrigatórios validados'),('Classificar','Impacto e prioridade classificados'),('Confirmar','Aguardando confirmação humana'),('Criar','Chamado criado')]

def run(message:str, confirm:bool=False)->dict:
    lower=message.lower(); missing=not any(x in lower for x in ('notebook','vpn','email','acesso','impressora'))
    if missing: return {'reply':'Para criar o chamado, preciso saber qual serviço ou equipamento está com problema.', 'state':'Coletar','steps':STEPS[:2],'fields':{'description':message},'ticket':None}
    fields={'service':'Notebook corporativo' if 'notebook' in lower else 'Serviço de TI','impact':'Alto' if any(x in lower for x in ('duas horas','urgente','apresentação')) else 'Médio','summary':message}
    if not confirm: return {'reply':'Entendi o problema. Revise os dados e confirme a criação do chamado.', 'state':'Confirmar','steps':STEPS[:5],'fields':fields,'ticket':None}
    ticket='INC-'+uuid.uuid4().hex[:6].upper()
    return {'reply':f'Chamado {ticket} criado com prioridade alta. A equipe de campo foi notificada.', 'state':'Concluído','steps':STEPS,'fields':fields,'ticket':ticket}

class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**k): super().__init__(*a,directory=str(WEB),**k)
 def do_POST(self):
  if urlparse(self.path).path!='/api/message': self.send_error(404);return
  data=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or b'{}'); out=run(str(data.get('message','')),bool(data.get('confirm'))); raw=json.dumps(out,ensure_ascii=False).encode();self.send_response(200);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
if __name__=='__main__':
 port=int(os.getenv('PORT','3100'));print(f'Hybrid Service Desk Agent em http://localhost:{port}');ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
