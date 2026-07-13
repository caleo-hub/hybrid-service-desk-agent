"""LangGraph service-desk intake agent deployed on AgentCore Runtime."""

import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal, TypedDict

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph_checkpoint_aws import AgentCoreMemorySaver
from model.load import load_model
from pydantic import BaseModel, Field
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


class TurnPlan(BaseModel):
    """LLM decision for one turn; LangGraph validates and executes it."""
    intent: Literal["collect", "correct", "confirm", "clarify", "answer_question", "cancel"]
    field_updates: dict[str, str] = Field(default_factory=dict)
    next_question: str = ""
    reply: str = ""


class IntakeState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    ticket: dict[str, str]
    pending_field: str
    completed: bool
    ticket_id: str
    intent: str
    planned_reply: str


def _checkpointer():
    memory_id = os.getenv("MEMORY_SERVICEDESKAGENTMEMORY_ID")
    if memory_id:
        return AgentCoreMemorySaver(memory_id, region_name=os.getenv("AWS_REGION", "us-east-1"))
    # Allows `agentcore dev` to run before the managed memory is provisioned.
    return InMemorySaver()


def reason_about_turn(state: IntakeState) -> dict[str, Any]:
    """An agentic LangChain node: interpret any turn and propose a state update."""
    ticket = dict(state.get("ticket", {}))
    latest = state["messages"][-1].content
    prompt = (
        "Você é o agente que conduz a abertura de chamados de service desk. Analise a mensagem no contexto do "
        "estado já coletado. O cliente pode responder em qualquer ordem, corrigir dados, fazer perguntas ou confirmar. "
        "Escolha a intenção: collect, correct, confirm, clarify, answer_question ou cancel. Extraia somente fatos explícitos "
        "nos campos requester, service, summary, impact e urgency; não invente. Normalize menções explícitas de 'urgente' "
        "para urgency='alta' e 'bloqueado/sem conseguir trabalhar' para impact='bloqueado para trabalhar'. Se algo estiver "
        "ambíguo, use clarify e pergunte de forma natural. Se faltar algo, use collect e pergunte apenas UMA informação "
        "mais útil agora.\n\n"
        f"Estado atual: {json.dumps(ticket, ensure_ascii=False)}\nMensagem: {latest}"
    )
    plan = load_model().with_structured_output(TurnPlan).invoke(prompt)
    updates = {key: str(value).strip() for key, value in plan.field_updates.items() if key in REQUIRED_FIELDS and str(value).strip()}
    ticket.update(updates)
    return {"ticket": ticket, "intent": plan.intent, "planned_reply": plan.reply or plan.next_question}


def respond_or_request_next(state: IntakeState) -> dict[str, Any]:
    ticket = state.get("ticket", {})
    intent = state.get("intent", "collect")
    if intent == "cancel":
        return {"pending_field": "", "completed": False, "messages": [AIMessage(content="Tudo bem, cancelei esta abertura. Quando quiser, podemos iniciar um novo chamado.")]}
    if intent in {"clarify", "answer_question"} and state.get("planned_reply"):
        return {"messages": [AIMessage(content=state["planned_reply"])]}
    missing = next((field for field in REQUIRED_FIELDS if not ticket.get(field)), None)
    if missing:
        return {
            "pending_field": missing,
            "completed": False,
            # The LLM can decide what is missing, but this deterministic guard
            # keeps the interview easy to follow: exactly one field per turn.
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


def create_ticket_if_confirmed(state: IntakeState) -> dict[str, Any]:
    """Create a real ticket only after the prior graph turn requested confirmation."""
    if not state.get("completed") or state.get("pending_field") != "confirmation" or state.get("intent") != "confirm":
        return {}
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


def route_after_reasoning(state: IntakeState) -> str:
    if state.get("completed") and state.get("pending_field") == "confirmation" and state.get("intent") == "confirm":
        return "create"
    return "respond"


_graph = StateGraph(IntakeState)
_graph.add_node("reason_about_turn", reason_about_turn)
_graph.add_node("create_ticket", create_ticket_if_confirmed)
_graph.add_node("respond_or_request_next", respond_or_request_next)
_graph.add_edge(START, "reason_about_turn")
_graph.add_conditional_edges("reason_about_turn", route_after_reasoning, {"create": "create_ticket", "respond": "respond_or_request_next"})
_graph.add_edge("create_ticket", END)
_graph.add_edge("respond_or_request_next", END)
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
