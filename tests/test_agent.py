import importlib.util
import json
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "services/lambda/index.py"
spec = importlib.util.spec_from_file_location("agent", path)
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.saved = []
        agent.catalog.scan = lambda: {"Items": [{"name": "Notebook corporativo"}]}
        agent.sessions.get_item = lambda Key: {"Item": {}}
        agent.sessions.put_item = lambda Item: self.saved.append(Item)

    def test_graph_asks_only_next_missing_field(self):
        agent.analyse_turn = lambda message, current, services: {"service": "Notebook corporativo", "summary": "", "impact": "", "nextQuestion": "O que está acontecendo com o notebook?", "confirmationReply": ""}
        body = json.loads(agent.handler({"body": json.dumps({"message": "Meu notebook parou"})}, None)["body"])
        self.assertEqual(body["state"], "Coletar")
        self.assertEqual(body["missing"], ["summary", "impact"])
        self.assertIn("acontecendo", body["reply"])
        self.assertEqual(self.saved[0]["service"], "Notebook corporativo")

    def test_graph_merges_turns_and_then_requests_confirmation(self):
        agent.sessions.get_item = lambda Key: {"Item": {"id": Key["id"], "service": "Notebook corporativo", "history": []}}
        agent.analyse_turn = lambda message, current, services: {"service": "", "summary": "desliga sozinho", "impact": "Alto", "nextQuestion": "", "confirmationReply": "Confirma a abertura para o notebook?"}
        body = json.loads(agent.handler({"body": json.dumps({"message": "Ele desliga sozinho e bloqueia a apresentação"})}, None)["body"])
        self.assertEqual(body["state"], "Confirmar")
        self.assertEqual(body["fields"]["impact"], "Alto")
        self.assertIn("Confirma", body["reply"])

    def test_confirmation_creates_ticket_after_graph_is_complete(self):
        stored = {"id": "session-1", "state": "Confirmar", "service": "Notebook corporativo", "summary": "desliga sozinho", "impact": "Alto"}
        written = []
        agent.sessions.get_item = lambda Key: {"Item": stored}
        agent.sessions.delete_item = lambda Key: None
        agent.tickets.put_item = lambda Item: written.append(Item)
        body = json.loads(agent.handler({"body": json.dumps({"message": "confirmar", "sessionId": "session-1", "confirm": True})}, None)["body"])
        self.assertEqual(body["state"], "Concluído")
        self.assertEqual(len(written), 1)
