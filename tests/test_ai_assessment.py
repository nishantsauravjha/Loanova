import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.agents.loan_graph import run_qualification_workflow
from app.kb import kb


@pytest.fixture
def synthetic_records(tmp_path):
    data = [
        {
            "record_id": "loan_001",
            "title": "Business Loan Overview",
            "category": "product",
            "source": "demo://loan-product-overview",
            "version": "1.0",
            "content": "The demo business loan is intended for small businesses seeking funds for working capital, equipment, or business expansion. This is a fictional demo product and not an actual loan offer.",
        },
        {
            "record_id": "loan_002",
            "title": "Illustrative Qualification Criteria",
            "category": "qualification",
            "source": "demo://qualification-rules",
            "version": "1.0",
            "content": "For this fictional demo, a lead should provide business type, time in operation, approximate monthly revenue, requested loan amount, and intended use of funds. These details are preliminary qualification only and do not constitute approval.",
        },
        {
            "record_id": "loan_004",
            "title": "Interest Rates and Fees",
            "category": "faq",
            "source": "demo://rates-and-fees",
            "version": "1.0",
            "content": "The demo knowledge base contains no approved interest rates, processing fees, repayment schedules, or final loan offers. The assistant must state that these details are unavailable rather than inventing numbers.",
        },
    ]
    path = tmp_path / "loan_knowledge.json"
    path.write_text(json.dumps(data))
    return path


class DummyEmbeddings:
    def embed_query(self, text):
        return [0.1, 0.2, 0.3]

    def embed_documents(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


class DummyChat:
    def __init__(self, *args, **kwargs):
        pass

    def invoke(self, messages):
        content = "The demo knowledge base does not include approved rates or fees, so the assistant must say they are unavailable."
        return type("Result", (), {"content": content})()


def test_vector_store_initializes_with_langchain_postgres_signature(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    captured = {}

    class FakePGVector:
        def __init__(self, embeddings, **kwargs):
            captured["embeddings"] = embeddings
            captured["connection"] = kwargs["connection"]
            captured["collection_name"] = kwargs["collection_name"]
            captured["create_extension"] = kwargs["create_extension"]

    monkeypatch.setattr(kb, "PGVector", FakePGVector)
    monkeypatch.setattr(kb, "get_embeddings", lambda: DummyEmbeddings())

    store = kb.get_vector_store()

    assert isinstance(store, FakePGVector)
    assert isinstance(captured["embeddings"], DummyEmbeddings)
    assert captured["collection_name"] == "loan_knowledge_demo"
    assert captured["create_extension"] is False
    assert captured["connection"].startswith("postgresql+psycopg://")


def test_ingest_json_stores_chunks_and_metadata(monkeypatch, synthetic_records):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(kb, "get_embeddings", lambda: DummyEmbeddings())

    captured = {}

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, *args, **kwargs):
            pass

        def commit(self):
            pass

    class FakePGVector:
        def __init__(self, embeddings, **kwargs):
            self.documents = []
            self.ids = []
            captured.setdefault("docs", [])
            captured.setdefault("ids", [])

        def add_documents(self, docs, ids=None):
            captured["docs"].extend(docs)
            captured["ids"].extend(ids or [])

    monkeypatch.setattr(kb, "PGVector", FakePGVector)
    monkeypatch.setattr(kb, "get_connection", lambda: FakeConn())

    result = kb.ingest_json(str(synthetic_records))

    assert result["ingested_records"] == 3
    assert len(captured["docs"]) >= 1
    assert any(item.startswith("loan_001_") for item in captured["ids"])
    assert any(doc.metadata["record_id"] == "loan_001" for doc in captured["docs"])


def test_retrieve_returns_traceable_metadata(monkeypatch, synthetic_records):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://app:app_password@db:5432/assessment")
    monkeypatch.setattr(kb, "get_embeddings", lambda: DummyEmbeddings())
    monkeypatch.setattr(kb, "get_vector_store", lambda: type("Store", (), {"add_documents": lambda self, docs, ids=None: None, "similarity_search_with_score": lambda self, question, k=4: [(type("Doc", (), {"page_content": "The demo business loan supports working capital.", "metadata": {"record_id": "loan_001", "title": "Business Loan Overview", "category": "product", "source": "demo://loan-product-overview", "version": "1.0", "pii": False}},)(), 0.11)]})())

    results = kb.retrieve("What is the business loan for?", limit=1)

    assert len(results) == 1
    assert results[0]["record_id"] == "loan_001"
    assert results[0]["title"] == "Business Loan Overview"
    assert results[0]["source"] == "demo://loan-product-overview"
    assert "pii" in results[0]


def test_answer_question_includes_citations(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setattr(kb, "retrieve", lambda question, limit=4: [{
        "record_id": "loan_004",
        "title": "Interest Rates and Fees",
        "content": "The demo knowledge base contains no approved interest rates, processing fees, repayment schedules, or final loan offers.",
        "category": "faq",
        "source": "demo://rates-and-fees",
        "version": "1.0",
        "pii": False,
        "similarity": 0.91,
    }])
    monkeypatch.setattr(kb, "get_chat_model", lambda: DummyChat())

    response = kb.answer_question("What is the APR?")

    assert response["grounded"] is False
    assert "unavailable" in response["answer"].lower()
    assert response["sources"][0]["record_id"] == "loan_004"
    assert response["sources"][0]["title"] == "Interest Rates and Fees"
    assert "loan_004" in response["answer"]


def test_unsupported_question_returns_safe_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(kb, "retrieve", lambda question, limit=4: [])

    response = kb.answer_question("What is the exact APR for this loan?")

    assert response["grounded"] is False
    assert "human" in response["answer"].lower()
    assert response["sources"] == []


def test_supported_answer_uses_citations(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setattr(kb, "retrieve", lambda question, limit=4: [{
        "record_id": "loan_001",
        "title": "Business Loan Overview",
        "content": "This demo loan is intended for small businesses seeking working capital or equipment funding.",
        "category": "product",
        "source": "demo://loan-product-overview",
        "version": "1.0",
        "pii": False,
        "similarity": 0.87,
    }])

    class AnsweringChat(DummyChat):
        def invoke(self, messages):
            return type("Result", (), {"content": "The demo loan is meant for small businesses seeking working capital or equipment funding."})()

    monkeypatch.setattr(kb, "get_chat_model", lambda: AnsweringChat())

    response = kb.answer_question("What is this loan for?")

    assert response["grounded"] is True
    assert response["sources"][0]["record_id"] == "loan_001"
    assert "loan_001" in response["answer"]
    assert "demo://loan-product-overview" in response["answer"] or response["answer"].endswith("loan_001") is False


def test_retrieved_but_insufficient_evidence_is_not_grounded(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(kb, "retrieve", lambda question, limit=4: [{
        "record_id": "loan_999",
        "title": "Weak Match",
        "content": "This record is loosely related to the query.",
        "category": "general",
        "source": "demo://weak-match",
        "version": "1.0",
        "pii": False,
        "similarity": 0.10,
    }])

    response = kb.answer_question("Tell me about loan guarantees")

    assert response["grounded"] is False
    assert response["sources"] == []
    assert "current knowledge base" in response["answer"].lower()


def test_qualification_workflow_handles_missing_fields():
    state = {
        "question": "I need a business loan.",
        "business_type": "",
        "requested_amount": "",
        "use_of_funds": "",
    }

    result = run_qualification_workflow(state)

    assert result["status"] == "missing_fields"
    assert "business_type" in result["missing_fields"]
    assert "requested_amount" in result["missing_fields"]


def test_escalation_flow_requests_human():
    state = {
        "question": "I want a human callback right now.",
        "business_type": "restaurant",
        "time_in_operation": "2 years",
        "monthly_revenue": "75000",
        "requested_amount": "50000",
        "use_of_funds": "inventory",
        "escalate": True,
    }

    result = run_qualification_workflow(state)

    assert result["status"] == "escalated"
    assert "human" in result["answer"].lower()
