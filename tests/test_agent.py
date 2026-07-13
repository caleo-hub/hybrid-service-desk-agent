import importlib.util,json
from pathlib import Path
import unittest
path=Path(__file__).resolve().parents[1]/'services/lambda/index.py';spec=importlib.util.spec_from_file_location('agent',path);agent=importlib.util.module_from_spec(spec);spec.loader.exec_module(agent)
class AgentTests(unittest.TestCase):
 def test_collects_when_model_marks_request_incomplete(self):
  agent.catalog.scan=lambda:{'Items':[]};agent.analyse=lambda message,services:{'complete':False,'reply':'Qual equipamento está com problema?'}
  body=json.loads(agent.handler({'body':json.dumps({'message':'não funciona'})},None)['body']);self.assertEqual(body['state'],'Coletar')
 def test_awaits_confirmation_for_complete_request(self):
  agent.catalog.scan=lambda:{'Items':[{'name':'Notebook corporativo'}]};agent.analyse=lambda message,services:{'complete':True,'service':'Notebook corporativo','summary':message,'impact':'Alto','reply':'Confirme os dados.'};agent.sessions.put_item=lambda Item:None
  body=json.loads(agent.handler({'body':json.dumps({'message':'Notebook desligando'})},None)['body']);self.assertEqual(body['state'],'Confirmar')
