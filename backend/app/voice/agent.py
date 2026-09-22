from typing import Any

from pydantic import BaseModel, Field

from ..agents.loan_graph import QualificationRequest, run_qualification_workflow
from ..kb.kb import answer_question


UNSUPPORTED_FINANCE_TERMS = [
    "apr",
    "annual percentage rate",
    "interest rate",
    "processing fee",
    "monthly payment",
    "approval",
    "approve",
    "approved",
    "eligibility",
    "eligible",
    "rate",
    "fee",
    "fees",
]

OBJECTION_TERMS = [
    "not eligible",
    "don't qualify",
    "dont qualify",
    "not qualify",
    "i don't qualify",
    "i dont qualify",
    "do not qualify",
    "i have objections",
    "concern",
    "objection",
    "problem",
    "unhappy",
]

ESCALATION_TERMS = [
    "human",
    "agent",
    "live person",
    "representative",
    "callback",
    "call me back",
    "speak to someone",
    "talk to a person",
]

QUALIFICATION_TERMS = [
    "need a loan",
    "need loan",
    "apply for",
    "business loan",
    "loan amount",
    "monthly revenue",
    "business type",
    "use of funds",
    "time in operation",
    "qualify",
    "eligible",
    "approval",
    "callback",
    "human",
]

GREETING_WORDS = {"hi", "hello", "hey", "greetings"}
GREETING_PHRASES = ("good morning", "good afternoon", "good evening")

INFO_REQUEST_PREFIXES = (
    "what is",
    "what are",
    "how does",
    "how do",
    "tell me about",
    "describe",
    "who is",
    "why",
    "when",
    "where",
)


class VoiceTurnRequest(BaseModel):
    message: str | None = Field(default=None, min_length=1, max_length=2000)
    question: str | None = Field(default=None, min_length=1, max_length=2000)
    business_type: str | None = None
    time_in_operation: str | None = None
    monthly_revenue: str | None = None
    requested_amount: str | None = None
    use_of_funds: str | None = None
    escalate: bool = False
    conversation_state: dict[str, Any] | None = None

    @property
    def text(self) -> str:
        return (self.message or self.question or "").strip()


def _normalize_text(value: str | None) -> str:
    return (value or "").strip().lower()


def _maybe_field_value(payload: VoiceTurnRequest, field_name: str) -> str:
    value = getattr(payload, field_name, None)
    if value is not None and str(value).strip():
        return str(value).strip()
    state = payload.conversation_state or {}
    value = state.get(field_name)
    if value is not None and str(value).strip():
        return str(value).strip()
    return ""


def _detect_conflicts(payload: VoiceTurnRequest) -> list[str]:
    state = payload.conversation_state or {}
    conflicts: list[str] = []
    for field_name in [
        "business_type",
        "time_in_operation",
        "monthly_revenue",
        "requested_amount",
        "use_of_funds",
    ]:
        current_value = _maybe_field_value(payload, field_name)
        previous_value = str(state.get(field_name, "")).strip()
        if previous_value and current_value and previous_value.lower() != current_value.lower():
            conflicts.append(field_name)
    return conflicts


def _looks_like_qualification_intent(message: str, payload: VoiceTurnRequest) -> bool:
    normalized = _normalize_text(message)
    if not normalized:
        return False

    if payload.escalate or any(term in normalized for term in ESCALATION_TERMS):
        return True

    if any(term in normalized for term in QUALIFICATION_TERMS):
        if any(prefix in normalized for prefix in INFO_REQUEST_PREFIXES):
            return False
        return True

    if any(
        _maybe_field_value(payload, field_name)
        for field_name in [
            "business_type",
            "time_in_operation",
            "monthly_revenue",
            "requested_amount",
            "use_of_funds",
        ]
    ):
        return True

    return False


def _is_greeting(message: str) -> bool:
    normalized = _normalize_text(message)
    if not normalized:
        return False
    tokens = normalized.replace("?", " ").replace("!", " ").split()
    if any(token in GREETING_WORDS for token in tokens):
        return True
    return any(phrase in normalized for phrase in GREETING_PHRASES)


def _is_information_request(message: str) -> bool:
    normalized = _normalize_text(message)
    if not normalized:
        return False
    if any(term in normalized for term in ["i need", "i want", "apply for", "need a loan", "need loan", "qualify", "eligible", "approved", "approval"]):
        return False
    return any(prefix in normalized for prefix in INFO_REQUEST_PREFIXES)


def _is_unsupported_financial_question(message: str) -> bool:
    normalized = _normalize_text(message)
    if not normalized:
        return False
    return any(term in normalized for term in UNSUPPORTED_FINANCE_TERMS)


def _build_qualification_payload(payload: VoiceTurnRequest) -> QualificationRequest:
    return QualificationRequest(
        question=payload.message,
        business_type=_maybe_field_value(payload, "business_type"),
        time_in_operation=_maybe_field_value(payload, "time_in_operation"),
        monthly_revenue=_maybe_field_value(payload, "monthly_revenue"),
        requested_amount=_maybe_field_value(payload, "requested_amount"),
        use_of_funds=_maybe_field_value(payload, "use_of_funds"),
        escalate=payload.escalate,
    )


def process_voice_turn(payload: VoiceTurnRequest | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, dict):
        if "message" not in payload and "question" in payload:
            payload = {**payload, "message": payload["question"]}
        if "conversation_state" not in payload and "state" in payload:
            payload = {**payload, "conversation_state": payload["state"]}
        payload = VoiceTurnRequest(**payload)
    elif payload is not None and not payload.message and getattr(payload, "question", None):
        payload = VoiceTurnRequest(
            message=payload.question,
            question=payload.question,
            business_type=payload.business_type,
            time_in_operation=payload.time_in_operation,
            monthly_revenue=payload.monthly_revenue,
            requested_amount=payload.requested_amount,
            use_of_funds=payload.use_of_funds,
            escalate=payload.escalate,
            conversation_state=payload.conversation_state,
        )

    message = payload.text.strip()
    normalized = _normalize_text(message)
    if not normalized:
        return {
            "status": "empty",
            "answer": "I’m ready to help with loan questions or preliminary qualification details. Please share the customer’s question or the information needed for review.",
            "grounded": False,
            "sources": [],
            "escalated": False,
        }

    conflicts = _detect_conflicts(payload)
    if conflicts:
        return {
            "status": "conflict",
            "answer": (
                "I noticed conflicting information for "
                + ", ".join(conflicts)
                + ". Please confirm the details before continuing. This does not imply approval or eligibility."
            ),
            "missing_fields": conflicts,
            "grounded": False,
            "sources": [],
            "escalated": False,
        }

    if _is_greeting(message):
        return {
            "status": "greeting",
            "answer": "Hi! I’m Loanova. I can answer product questions, explain the preliminary qualification process, or connect you with a human specialist if needed.",
            "grounded": False,
            "sources": [],
            "escalated": False,
        }

    escalation_requested = payload.escalate or any(term in normalized for term in ESCALATION_TERMS)
    if escalation_requested:
        workflow_result = run_qualification_workflow(_build_qualification_payload(payload))
        result = {
            "status": workflow_result.get("status", "escalated"),
            "answer": workflow_result.get("answer"),
            "missing_fields": workflow_result.get("missing_fields", []),
            "grounded": False,
            "sources": [],
            "escalated": True,
        }
        return result

    if _is_unsupported_financial_question(normalized):
        answer = answer_question(message)
        return {
            "status": "unsupported_question",
            **answer,
            "escalated": False,
        }

    if _is_information_request(message):
        answer = answer_question(message)
        return {
            "status": "knowledge_answer",
            **answer,
            "escalated": False,
        }

    if _looks_like_qualification_intent(message, payload):
        workflow_result = run_qualification_workflow(_build_qualification_payload(payload))
        result = {
            "status": workflow_result.get("status", "ready"),
            "answer": workflow_result.get("answer"),
            "missing_fields": workflow_result.get("missing_fields", []),
            "grounded": False,
            "sources": [],
            "escalated": workflow_result.get("status") == "escalated",
        }
        if workflow_result.get("status") in {"missing_fields", "objection", "escalated"}:
            return result
        if workflow_result.get("status") == "ready_for_review":
            return result

    if any(term in normalized for term in OBJECTION_TERMS):
        workflow_result = run_qualification_workflow(_build_qualification_payload(payload))
        return {
            "status": workflow_result.get("status", "objection"),
            "answer": workflow_result.get("answer"),
            "missing_fields": workflow_result.get("missing_fields", []),
            "grounded": False,
            "sources": [],
            "escalated": False,
        }

    answer = answer_question(message)
    return {
        "status": "knowledge_answer",
        **answer,
        "escalated": False,
    }


def handle_voice_turn(payload: VoiceTurnRequest | dict[str, Any]) -> dict[str, Any]:
    return process_voice_turn(payload)


def run_voice_agent(payload: VoiceTurnRequest | dict[str, Any]) -> dict[str, Any]:
    return process_voice_turn(payload)


class VoiceAgent:
    def __init__(self, payload: VoiceTurnRequest | dict[str, Any] | None = None):
        self.payload = payload

    def handle_turn(self, payload: VoiceTurnRequest | dict[str, Any] | None = None) -> dict[str, Any]:
        turn = payload or self.payload
        if turn is None:
            raise ValueError("A voice turn payload is required.")
        return process_voice_turn(turn)

    def run(self, payload: VoiceTurnRequest | dict[str, Any] | None = None) -> dict[str, Any]:
        return self.handle_turn(payload)
