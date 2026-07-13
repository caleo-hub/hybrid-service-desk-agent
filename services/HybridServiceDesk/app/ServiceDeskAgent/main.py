"""LangGraph service-desk intake agent deployed on AgentCore Runtime."""

import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, TypedDict

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph_checkpoint_aws import AgentCoreMemorySaver
from model.load import load_model
import boto3

app = BedrockAgentCoreApp()
log = app.logger

REQUIRED_FIELDS = ("requester", "service", "summary", "impact", "urgency")
FIELD_QUESTIONS = {
    "requester": "Quem é a pessoa solicitante?",
    "service": "Qual serviço ou sistema está envolvido?",
    "summary": "Descreva brevemente o que está acontecendo.",
    "impact": "Qual é o impacto para a operação ou para os usuários?",
    "urgency": "Qual a urgência: baixa, média, alta ou crítica?",
}


class IntakeState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    ticket: dict[str, str]
    pending_field: str
    completed: bool
    ticket_id: str


def _json_object(text: str) -> dict[str, str]:
    """Extract exactly the object returned by the model; malformed output is safe."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return {key: str(value).strip() for key, value in data.items() if key in REQUIRED_FIELDS and value}


def _checkpointer():
    memory_id = os.getenv("MEMORY_SERVICEDESKAGENTMEMORY_ID")
    if memory_id:
        return AgentCoreMemorySaver(memory_id, region_name=os.getenv("AWS_REGION", "us-east-1"))
    # Allows `agentcore dev` to run before the managed memory is provisioned.
    return InMemorySaver()


def extract_fields(state: IntakeState) -> dict[str, Any]:
    ticket = dict(state.get("ticket", {}))
    latest = state["messages"][-1].content
    prompt = (
        "Você extrai informações de um chamado de service desk.\n\n"
        f"Campos já conhecidos: {json.dumps(ticket, ensure_ascii=False)}\n"
        f"Mensagem nova do usuário: {latest}\n\n"
        "Retorne SOMENTE JSON. Inclua apenas valores explicitamente fornecidos nesta mensagem "
        "para requester, service, summary, impact e urgency. Não invente valores."
    )
    response = load_model().invoke(prompt)
    ticket.update(_json_object(str(response.content)))
    return {"ticket": ticket}


def decide_next(state: IntakeState) -> dict[str, Any]:
    ticket = state.get("ticket", {})
    missing = next((field for field in REQUIRED_FIELDS if not ticket.get(field)), None)
    if missing:
        return {
            "pending_field": missing,
            "completed": False,
            "messages": [AIMessage(content=FIELD_QUESTIONS[missing])],
        }
    confirmation = (
        "Tenho todas as informações para o chamado:\n\n"
        f"- Solicitante: {ticket['requester']}\n"
        f"- Serviço: {ticket['service']}\n"
        f"- Resumo: {ticket['summary']}\n"
        f"- Impacto: {ticket['impact']}\n"
        f"- Urgência: {ticket['urgency']}\n\n"
        "Confirma a abertura do chamado?"
    )
    return {"pending_field": "confirmation", "completed": True, "messages": [AIMessage(content=confirmation)]}


def _confirmed(text: str) -> bool:
    return text.strip().lower() in {"sim", "s", "confirmo", "confirmar", "pode abrir", "pode criar"}


def confirm_or_continue(state: IntakeState) -> dict[str, Any]:
    """Create a real ticket only after the prior graph turn requested confirmation."""
    if not state.get("completed") or state.get("pending_field") != "confirmation":
        return {}
    latest = str(state["messages"][-1].content)
    if not _confirmed(latest):
        return {"messages": [AIMessage(content="Sem problema. Diga 'sim' quando quiser confirmar a abertura ou informe o que deseja corrigir.")]}
    ticket = state["ticket"]
    ticket_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
    table_name = os.getenv("TICKETS_TABLE")
    if not table_name:
        raise RuntimeError("Tabela de chamados não configurada no runtime.")
    boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1")).Table(table_name).put_item(
        Item={
            "id": ticket_id,
            "status": "Aberto",
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "expiresAt": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
            **ticket,
        }
    )
    return {"ticket_id": ticket_id, "messages": [AIMessage(content=f"Chamado {ticket_id} criado com sucesso.")]}


def route_after_confirmation(state: IntakeState) -> str:
    return "done" if state.get("ticket_id") or (state.get("completed") and state.get("pending_field") == "confirmation") else "extract"


def route_after_extract(_: IntakeState) -> str:
    return "decide"


_graph = StateGraph(IntakeState)
_graph.add_node("confirm_or_continue", confirm_or_continue)
_graph.add_node("extract_fields", extract_fields)
_graph.add_node("decide", decide_next)
_graph.add_edge(START, "confirm_or_continue")
_graph.add_conditional_edges("confirm_or_continue", route_after_confirmation, {"done": END, "extract": "extract_fields"})
_graph.add_conditional_edges("extract_fields", route_after_extract, {"decide": "decide"})
_graph.add_edge("decide", END)
workflow = _graph.compile(checkpointer=_checkpointer())


@app.entrypoint
async def invoke(payload, context):
    prompt = str(payload.get("prompt", "")).strip()
    if not prompt:
        return {"result": "Envie uma mensagem para iniciar o preenchimento do chamado."}
    session_id = getattr(context, "session_id", "default-session")
    result = await workflow.ainvoke(
        {"messages": [HumanMessage(content=prompt)]},
        config={"configurable": {"thread_id": session_id, "actor_id": "service-desk-demo"}},
    )
    answer = result["messages"][-1].content
    return {"result": answer, "ticket": result.get("ticket", {}), "ticketId": result.get("ticket_id"), "complete": result.get("completed", False)}


if __name__ == "__main__":
    app.run()
