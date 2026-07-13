import importlib.util
import io
import json
from pathlib import Path
import unittest


path = Path(__file__).resolve().parents[1] / "services/lambda/index.py"
spec = importlib.util.spec_from_file_location("agent", path)
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)


class AgentTests(unittest.TestCase):
    def setUp(self):
        agent.RUNTIME_ARN = "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/demo"

    def test_rejects_missing_or_short_session_id(self):
        result = agent.handler({"body": json.dumps({"message": "Meu notebook parou"})}, None)
        self.assertEqual(result["statusCode"], 400)
        self.assertIn("sessionId", json.loads(result["body"])["error"])

    def test_invokes_agentcore_and_returns_ticket_state(self):
        captured = {}

        def invoke_agent_runtime(**request):
            captured.update(request)
            return {"response": io.BytesIO(json.dumps({
                "result": "Registrei o incidente.",
                "ticketId": "INC-123456",
                "ticket": {"service": "Notebook corporativo", "impact": "Alto"},
            }).encode())}

        agent.runtime.invoke_agent_runtime = invoke_agent_runtime
        session_id = "123e4567-e89b-12d3-a456-426614174000"
        result = agent.handler({"body": json.dumps({"sessionId": session_id, "message": "Pode confirmar"})}, None)
        body = json.loads(result["body"])
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(captured["agentRuntimeArn"], agent.RUNTIME_ARN)
        self.assertEqual(captured["runtimeSessionId"], session_id)
        self.assertEqual(body["ticket"], "INC-123456")

    def test_confirm_flag_sends_confirmation_to_runtime(self):
        captured = {}

        def invoke_agent_runtime(**request):
            captured.update(json.loads(request["payload"].decode()))
            return {"response": io.BytesIO(json.dumps({"result": "Confirmado", "ticketActive": True}).encode())}

        agent.runtime.invoke_agent_runtime = invoke_agent_runtime
        result = agent.handler({"body": json.dumps({
            "sessionId": "123e4567-e89b-12d3-a456-426614174000",
            "message": "texto ignorado",
            "confirm": True,
        })}, None)
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(captured["prompt"], "sim")
