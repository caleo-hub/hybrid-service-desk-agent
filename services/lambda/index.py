"""HTTP facade for the AgentCore LangGraph runtime."""
from __future__ import annotations

import json
import os
import time

import boto3

runtime = boto3.client("bedrock-agentcore", region_name=os.getenv("AWS_REGION", "us-east-1"))
RUNTIME_ARN = os.environ["AGENTCORE_RUNTIME_ARN"]


def response(status: int, body: dict) -> dict:
    return {"statusCode": status, "headers": {"content-type": "application/json"}, "body": json.dumps(body, ensure_ascii=False)}


def steps(state: str) -> list[tuple[str, str]]:
    all_steps = [("Entender", "Mensagem interpretada pelo LangGraph"), ("Coletar", "Campos coletados em etapas"), ("Validar", "Campos obrigatórios validados"), ("Confirmar", "Confirmação humana"), ("Criar", "Chamado criado no DynamoDB")]
    count = {"Coletar": 2, "Confirmar": 4, "Concluído": 5}.get(state, 1)
    return all_steps[:count]


def handler(event, context):
    try:
        payload = json.loads(event.get("body") or "{}")
        session_id = str(payload.get("sessionId", "")).strip()
        message = str(payload.get("message", "")).strip()
        if not session_id or len(session_id) < 33:
            return response(400, {"error": "sessionId deve ser um UUID válido."})
        if payload.get("confirm"):
            message = "sim"
        if not message:
            return response(400, {"error": "Envie uma mensagem."})
        started = time.perf_counter()
        invocation = runtime.invoke_agent_runtime(
            agentRuntimeArn=RUNTIME_ARN,
            runtimeSessionId=session_id,
            qualifier="DEFAULT",
            payload=json.dumps({"prompt": message}).encode(),
        )
        result = json.loads(invocation["response"].read())
        ticket_id = result.get("ticketId")
        state = "Concluído" if ticket_id else ("Confirmar" if result.get("complete") else ("Coletar" if result.get("ticketActive") else "Conversa"))
        return response(200, {
            "reply": result.get("result", "Não houve resposta do runtime."),
            "state": state,
            "steps": steps(state),
            "fields": result.get("ticket", {}),
            "ticket": ticket_id,
            "latency_ms": round((time.perf_counter() - started) * 1000),
        })
    except Exception as error:
        print(json.dumps({"error": str(error)}))
        return response(502, {"error": "Falha ao invocar o runtime AgentCore. Consulte os logs CloudWatch."})
