from __future__ import annotations
import json, os, uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import boto3

region=os.environ.get('AWS_REGION','us-east-1')
db=boto3.resource('dynamodb',region_name=region)
sessions=db.Table(os.environ.get('SESSIONS_TABLE','test-sessions')); tickets=db.Table(os.environ.get('TICKETS_TABLE','test-tickets')); catalog=db.Table(os.environ.get('CATALOG_TABLE','test-catalog'))
bedrock=boto3.client('bedrock-runtime',region_name=region)
model=os.environ.get('BEDROCK_MODEL_ID','us.amazon.nova-2-lite-v1:0')

def reply(status, body): return {'statusCode':status,'headers':{'content-type':'application/json'},'body':json.dumps(body,ensure_ascii=False,default=str)}
def step(state):
 names=[('Entender','Intenção identificada'),('Coletar','Dados do incidente coletados'),('Validar','Campos obrigatórios validados'),('Classificar','Impacto e prioridade classificados'),('Confirmar','Aguardando confirmação humana'),('Criar','Chamado criado')]
 until={'Coletar':2,'Confirmar':5,'Concluído':6}.get(state,1); return names[:until]
def analyse(message, services):
 prompt='''Extraia um chamado de TI em português. Responda SOMENTE JSON válido com as chaves service, summary, impact, complete, reply. impact deve ser Baixo, Médio ou Alto. Escolha o item de catálogo mais próximo mesmo quando a mensagem usa um sinônimo (por exemplo, “notebook” corresponde a “Notebook corporativo”). complete deve ser true quando a mensagem identifica um equipamento/serviço e descreve o problema; não peça confirmação nessa etapa. Se houver urgência de apresentação ou prazo em horas, use impact Alto. reply deve pedir confirmação dos dados quando complete for true; caso contrário, faça uma única pergunta objetiva. Catálogo disponível: '''+json.dumps(services,ensure_ascii=False)+"\nMensagem: "+message
 raw=bedrock.converse(modelId=model,messages=[{'role':'user','content':[{'text':prompt}]}],inferenceConfig={'maxTokens':220,'temperature':0}).get('output',{}).get('message',{}).get('content',[{'text':'{}'}])[0]['text']
 raw=raw.replace('```json','').replace('```','').strip(); return json.loads(raw[raw.find('{'):raw.rfind('}')+1])
def handler(event, context):
 try:
  payload=json.loads(event.get('body') or '{}'); message=str(payload.get('message','')).strip(); session_id=str(payload.get('sessionId','demo-session')); confirm=bool(payload.get('confirm'))
  if not message: return reply(400,{'error':'Envie uma mensagem.'})
  if confirm:
   state=sessions.get_item(Key={'id':session_id}).get('Item')
   if not state: return reply(409,{'error':'Não existe uma solicitação pendente para confirmar.'})
   ticket_id='INC-'+uuid.uuid4().hex[:8].upper(); expires=int((datetime.now(timezone.utc)+timedelta(days=7)).timestamp())
   ticket={'id':ticket_id,'sessionId':session_id,'service':state['service'],'summary':state['summary'],'impact':state['impact'],'status':'Aberto','expiresAt':expires}
   tickets.put_item(Item=ticket); sessions.delete_item(Key={'id':session_id})
   return reply(200,{'reply':f'Chamado {ticket_id} criado com prioridade {state["impact"].lower()}.','state':'Concluído','steps':step('Concluído'),'fields':{k:state[k] for k in ('service','summary','impact')},'ticket':ticket_id})
  services=[x['name'] for x in catalog.scan().get('Items',[])]
  fields=analyse(message,services)
  if not fields.get('complete'):
   return reply(200,{'reply':fields.get('reply','Preciso de mais detalhes.'),'state':'Coletar','steps':step('Coletar'),'fields':{'summary':message},'ticket':None})
  record={'id':session_id,'service':str(fields['service']),'summary':str(fields['summary']),'impact':str(fields.get('impact','Médio')),'expiresAt':int((datetime.now(timezone.utc)+timedelta(hours=2)).timestamp())}
  sessions.put_item(Item=record)
  return reply(200,{'reply':fields.get('reply','Revise os dados e confirme a criação.'),'state':'Confirmar','steps':step('Confirmar'),'fields':{k:record[k] for k in ('service','summary','impact')},'ticket':None})
 except Exception as e:
  print(json.dumps({'error':str(e)})); return reply(500,{'error':'Falha no agente. Consulte os logs CloudWatch.'})
