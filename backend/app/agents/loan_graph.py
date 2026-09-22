import re
from typing import Any, Iterable

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from .loan_state import REQUIRED_FIELDS, LoanQualificationState


class QualificationRequest(BaseModel):
    question: str | None = Field(default=None, max_length=2000)
    business_type: str | None = None
    time_in_operation: str | None = None
    monthly_revenue: str | None = None
    requested_amount: str | None = None
    use_of_funds: str | None = None
    escalate: bool = False


def _field_labels() -> dict[str, str]:
    return {
        "business_type": "business type",
        "time_in_operation": "time in operation",
        "monthly_revenue": "monthly revenue",
        "requested_amount": "requested loan amount",
        "use_of_funds": "use of funds",
    }


def _normalize_state(payload: dict[str, Any] | QualificationRequest) -> LoanQualificationState:
    data = payload.model_dump(exclude_none=True) if isinstance(payload, QualificationRequest) else payload
    state: LoanQualificationState = {
        "question": data.get("question") or "",
        "business_type": data.get("business_type") or "",
        "time_in_operation": data.get("time_in_operation") or "",
        "monthly_revenue": data.get("monthly_revenue") or "",
        "requested_amount": data.get("requested_amount") or "",
        "use_of_funds": data.get("use_of_funds") or "",
        "escalate": bool(data.get("escalate", False)),
        "missing_fields": [],
        "status": "initial",
        "answer": "",
    }
    return state


def check_missing_fields(state: LoanQualificationState) -> LoanQualificationState:
    missing = [
        field
        for field in REQUIRED_FIELDS
        if not str(state.get(field, "") or "").strip()
    ]
    state["missing_fields"] = missing
    if missing:
        state["status"] = "missing_fields"
        state["answer"] = ""
    else:
        state["status"] = "ready"
    return state


def route_after_fields(state: LoanQualificationState) -> str:
    question = (state.get("question") or "").lower()
    if state.get("escalate") or "human" in question or "callback" in question or "agent" in question:
        return "escalate"
    if state.get("missing_fields"):
        return "missing"
    if any(term in question for term in ["eligibility", "eligible", "approval", "approved", "rate", "fee"]):
        return "objection"
    return "assess"


def handle_missing_fields(state: LoanQualificationState) -> LoanQualificationState:
    labels = _field_labels()
    missing = [labels.get(field, field) for field in state.get("missing_fields", [])]
    state["status"] = "missing_fields"
    state["answer"] = (
        "I need a few preliminary details before I can continue: "
        + ", ".join(missing)
        + ". This is a synthetic demo workflow and does not imply approval."
    )
    return state


def handle_objection(state: LoanQualificationState) -> LoanQualificationState:
    state["status"] = "objection"
    state["answer"] = (
        "I understand the concern about eligibility. I can collect preliminary qualification details such as business type, time in operation, monthly revenue, requested loan amount, and use of funds. "
        "This does not guarantee approval or eligibility, and a human specialist can assist if needed."
    )
    return state


def handle_escalation(state: LoanQualificationState) -> LoanQualificationState:
    state["status"] = "escalated"
    state["answer"] = (
        "I can connect you with a human specialist for follow-up. Please note that this demo system cannot guarantee a callback or approval without a successful scheduling action."
    )
    return state


def assess_qualification(state: LoanQualificationState) -> LoanQualificationState:
    state["status"] = "ready_for_review"
    state["answer"] = (
        "I have the preliminary details needed for review. This is a fictional demo workflow and does not constitute a loan approval, eligibility decision, or final offer. "
        "A human team can review the information if needed."
    )
    return state


def build_qualification_graph():
    workflow = StateGraph(LoanQualificationState)
    workflow.add_node("check_missing_fields", check_missing_fields)
    workflow.add_node("missing_fields_handler", handle_missing_fields)
    workflow.add_node("objection_handler", handle_objection)
    workflow.add_node("escalation_handler", handle_escalation)
    workflow.add_node("assessment_handler", assess_qualification)

    workflow.set_entry_point("check_missing_fields")
    workflow.add_conditional_edges(
        "check_missing_fields",
        route_after_fields,
        {
            "missing": "missing_fields_handler",
            "objection": "objection_handler",
            "escalate": "escalation_handler",
            "assess": "assessment_handler",
        },
    )
    workflow.add_edge("missing_fields_handler", END)
    workflow.add_edge("objection_handler", END)
    workflow.add_edge("escalation_handler", END)
    workflow.add_edge("assessment_handler", END)
    return workflow.compile()


QUALIFICATION_GRAPH = build_qualification_graph()


def run_qualification_workflow(payload: dict[str, Any] | QualificationRequest) -> LoanQualificationState:
    normalized = _normalize_state(payload)
    return QUALIFICATION_GRAPH.invoke(normalized)
