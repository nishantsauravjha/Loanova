import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(FRONTEND))

from app.agents.loan_graph import run_qualification_workflow
from app.kb import kb
from app.main import app
import streamlit_app
from fastapi.testclient import TestClient


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


def test_build_voice_component_html_includes_browser_voice_contract():
    html = streamlit_app.build_voice_component_html("http://localhost:8000/voice/conversation")

    assert "SpeechRecognition" in html
    assert "/voice/conversation" in html
    assert "Microphone permission denied" in html
    assert "speechSynthesis" in html
    assert "Browser speech recognition and synthesis are supported only in modern browsers" in html


def test_q1_real_call_recording_template_has_three_calls_and_no_fabrication_claims():
    template = ROOT / "docs" / "q1_real_call_recording_template.md"
    assert template.exists()
    text = template.read_text(encoding="utf-8")
    assert "Call 1" in text and "Call 2" in text and "Call 3" in text
    assert "No fabricated" in text or "do not fabricate" in text.lower()
    assert "browser" in text.lower() and "voice" in text.lower()


def test_build_voice_component_html_uses_explicit_voice_selection_and_missing_voice_warning():
    html = streamlit_app.build_voice_component_html("http://localhost:8000/voice/conversation")

    assert "loanova-voice-select" in html
    assert "voiceschanged" in html
    assert "getVoices" in html
    assert "voiceSelect.value" in html
    assert "utterance.voice = matchingVoice" in html
    assert "No suitable English voice available. Using the browser default voice is not high quality on this browser." in html
    assert "rate = 1.0" in html
    assert "pitch = 1.0" in html
    assert "window.speechSynthesis.cancel()" in html
    assert "voice.name === selectedVoiceName" in html


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


def test_prepare_records_for_ingestion_cleans_deduplicates_and_flags_pii():
    records = [
        {
            "record_id": "loan_099",
            "title": "  Example Loan  ",
            "category": "product",
            "source": "demo://example",
            "version": "1.0",
            "content": "  The demo loan is for   small businesses.  Contact jamie@example.com for details.  ",
        },
        {
            "record_id": "loan_099",
            "title": "Example Loan",
            "category": "product",
            "source": "demo://example",
            "version": "1.0",
            "content": "The demo loan is for small businesses. Contact jamie@example.com for details.",
        },
    ]

    cleaned = kb.prepare_records_for_ingestion(records)

    assert len(cleaned) == 1
    assert cleaned[0]["title"] == "Example Loan"
    assert cleaned[0]["content"] == "The demo loan is for small businesses. Contact [email redacted] for details."
    assert cleaned[0]["pii"] is True


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


def test_document_upload_ingestion_parses_clean_chunks_and_is_retrievable(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    created = {}

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, *args, **kwargs):
            pass

        def commit(self):
            pass

    class FakeStore:
        def __init__(self):
            self.docs = []

        def add_documents(self, docs, ids=None):
            created["docs"] = docs
            created["ids"] = ids or []

        def similarity_search_with_score(self, question, k=4):
            return [
                (
                    type(
                        "Doc",
                        (),
                        {
                            "page_content": "This uploaded business loan policy supports working capital and equipment funding.",
                            "metadata": {
                                "record_id": "upload_001",
                                "title": "Uploaded Policy",
                                "category": "product",
                                "source": "uploaded://loan-policy",
                                "version": "1.0",
                                "pii": False,
                            },
                        },
                    )(),
                    0.08,
                )
            ]

    monkeypatch.setattr(kb, "get_embeddings", lambda: DummyEmbeddings())
    monkeypatch.setattr(kb, "get_vector_store", lambda: FakeStore())
    monkeypatch.setattr(kb, "get_connection", lambda: FakeConn())

    document_path = tmp_path / "loan_policy.txt"
    document_path.write_text(
        "The uploaded business loan policy supports working capital and equipment funding for small businesses. Contact customer@example.com for details.",
        encoding="utf-8",
    )

    result = kb.ingest_document_file(
        str(document_path),
        title="Uploaded Policy",
        category="product",
        source="uploaded://loan-policy",
    )
    retrieved = kb.retrieve("What does the uploaded policy support?", limit=1)

    assert result["ingested_records"] == 1
    assert created["docs"]
    assert created["docs"][0].metadata["source"] == "uploaded://loan-policy"
    assert retrieved[0]["source"] == "uploaded://loan-policy"
    assert retrieved[0]["record_id"] == "upload_001"


def test_readable_pdf_document_upload_ingestion_parses_and_redacts_pii(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    created = {}

    from reportlab.pdfgen import canvas

    pdf_path = tmp_path / "loan_policy.pdf"
    c = canvas.Canvas(str(pdf_path))
    c.drawString(50, 750, "The demo business loan supports working capital and equipment funding for small businesses.")
    c.drawString(50, 730, "Contact customer@example.com for details.")
    c.save()

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, *args, **kwargs):
            pass

        def commit(self):
            pass

    class FakeStore:
        def __init__(self):
            self.docs = []

        def add_documents(self, docs, ids=None):
            created["docs"] = docs
            created["ids"] = ids or []

    monkeypatch.setattr(kb, "get_embeddings", lambda: DummyEmbeddings())
    monkeypatch.setattr(kb, "get_vector_store", lambda: FakeStore())
    monkeypatch.setattr(kb, "get_connection", lambda: FakeConn())

    result = kb.ingest_document_file(
        str(pdf_path),
        title="PDF policy",
        category="product",
        source="uploaded://pdf-policy",
    )

    assert result["ingested_records"] == 1
    assert created["docs"]
    assert created["docs"][0].metadata["source"] == "uploaded://pdf-policy"
    assert "working capital" in created["docs"][0].page_content.lower()
    assert "customer@example.com" not in created["docs"][0].page_content


def test_empty_pdf_document_upload_fails_without_placeholder(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    from pypdf import PdfWriter

    pdf_path = tmp_path / "empty_policy.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(str(pdf_path))

    with pytest.raises(ValueError, match="No readable text was extracted|OCR is not supported"):
        kb.ingest_document_file(
            str(pdf_path),
            title="Empty PDF policy",
            category="product",
            source="uploaded://empty-pdf-policy",
        )


def test_api_empty_pdf_upload_returns_422_with_clear_error(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    from pypdf import PdfWriter

    pdf_path = tmp_path / "empty_policy.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(str(pdf_path))

    with TestClient(app) as client:
        response = client.post(
            "/kb/ingest/file",
            files={"file": ("empty_policy.pdf", pdf_path.read_bytes(), "application/pdf")},
            data={"title": "Empty PDF policy", "category": "product", "source": "uploaded://empty-pdf-policy"},
        )

    assert response.status_code == 422
    assert "No readable text was extracted" in response.json()["detail"]
    assert "OCR is not supported" in response.json()["detail"]


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


def test_language_detection_handles_tagalog_and_indonesian_markers():
    from app.localization import detect_language

    assert detect_language("Kamusta, kailangan ko ng business loan para sa negosyo") == "taglish"
    assert detect_language("Halo, saya mau cicilan dan tenor untuk pembiayaan") == "indonesian"
    assert detect_language("Hi, I need a loan and premium coverage") == "english"
    assert detect_language("Magandang araw, I need a business loan and premium; saya mau cicilan") == "taglish"


def test_language_selection_aliases_are_explicit_and_stable():
    from app.localization import browser_locale_for_language, normalize_language_hint

    assert normalize_language_hint("English") == "english"
    assert normalize_language_hint("fil-PH") == "filipino"
    assert normalize_language_hint("Tagalog") == "filipino"
    assert normalize_language_hint("taglish") == "taglish"
    assert normalize_language_hint("Bahasa Indonesia") == "indonesian"
    assert browser_locale_for_language("filipino") == "fil-PH"
    assert browser_locale_for_language("indonesian") == "id-ID"


def test_voice_agent_localizes_filipino_greeting_and_query_flow(monkeypatch):
    from app.voice.agent import process_voice_turn

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
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
            return type("Result", (), {"content": "The demo loan supports working capital and equipment funding."})()

    monkeypatch.setattr(kb, "get_chat_model", lambda: AnsweringChat())

    result = process_voice_turn({
        "message": "Kamusta, ano ang loan para sa negosyo?",
        "market": "philippines",
    })

    assert result["status"] == "knowledge_answer"
    assert "kamusta" in result["answer"].lower() or "loanova" in result["answer"].lower()
    assert result["grounded"] is True
    assert result["sources"][0]["record_id"] == "loan_001"


def test_voice_agent_supports_explicit_taglish_language_selection_and_mixed_language_input(monkeypatch):
    from app.voice.agent import process_voice_turn

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
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
            return type("Result", (), {"content": "The demo loan supports working capital and equipment funding."})()

    monkeypatch.setattr(kb, "get_chat_model", lambda: AnsweringChat())

    result = process_voice_turn({
        "message": "Halo, what is the business loan for a small business?",
        "language": "taglish",
    })

    assert result["status"] == "knowledge_answer"
    assert result["grounded"] is True
    assert result["sources"][0]["record_id"] == "loan_001"
    assert "loanova" in result["answer"].lower() or "business" in result["answer"].lower()


def test_voice_agent_localizes_indonesian_unsupported_financial_request(monkeypatch):
    from app.voice.agent import process_voice_turn

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
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

    result = process_voice_turn({
        "message": "Halo, berapa APR dan fee untuk pembiayaan ini?",
        "market": "indonesia",
    })

    assert result["status"] == "unsupported_question"
    assert result["grounded"] is False
    assert result["sources"][0]["record_id"] == "loan_004"
    assert "tidak" in result["answer"].lower() or "unavailable" in result["answer"].lower() or "n/a" in result["answer"].lower()


def test_q3_language_examples_and_capability_matrix_cover_required_markets():
    from app import localization

    filipino = localization.language_examples_for_market("filipino")
    taglish = localization.language_examples_for_market("taglish")
    indonesian = localization.language_examples_for_market("indonesian")

    assert len(filipino) >= 3
    assert len(taglish) >= 3
    assert len(indonesian) >= 3
    assert all("kamusta" in example.lower() or "magandang" in example.lower() or "pwede" in example.lower() for example in filipino)
    assert "business" in " ".join(taglish).lower()
    assert all("halo" in example.lower() or "saya" in example.lower() or "apakah" in example.lower() for example in indonesian)

    filipino_capabilities = localization.get_market_voice_capabilities("filipino")
    indonesian_capabilities = localization.get_market_voice_capabilities("indonesian")

    assert filipino_capabilities["browser_locale"] == "fil-PH"
    assert indonesian_capabilities["browser_locale"] == "id-ID"
    assert "browser" in filipino_capabilities["asr"].lower()
    assert "browser" in indonesian_capabilities["tts"].lower()
    assert "not guaranteed" in indonesian_capabilities["tts"].lower() or "not guaranteed" in filipino_capabilities["tts"].lower()


def test_voice_agent_keeps_english_q1_q2_behavior_untouched(monkeypatch):
    from app.voice.agent import process_voice_turn

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
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
            return type("Result", (), {"content": "The demo loan supports working capital and equipment funding."})()

    monkeypatch.setattr(kb, "get_chat_model", lambda: AnsweringChat())

    result = process_voice_turn({"message": "What is this loan for?"})

    assert result["status"] == "knowledge_answer"
    assert result["grounded"] is True
    assert result["sources"][0]["record_id"] == "loan_001"


def test_browser_voice_component_reports_locale_fallback_behavior():
    html = streamlit_app.build_voice_component_html("http://localhost:8000/voice/conversation")

    assert "fil-PH" in html
    assert "id-ID" in html
    assert "text input remains available" in html.lower()
    assert "loanova-language-select" in html


def test_voice_agent_uses_grounded_kb_for_supported_question(monkeypatch):
    from app.voice.agent import process_voice_turn

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
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
            return type("Result", (), {"content": "The demo loan supports working capital and equipment funding."})()

    monkeypatch.setattr(kb, "get_chat_model", lambda: AnsweringChat())

    result = process_voice_turn({
        "message": "What is this loan for?",
        "conversation_state": {},
    })

    assert result["grounded"] is True
    assert "loan_001" in result["answer"]
    assert result["sources"][0]["record_id"] == "loan_001"


def test_voice_agent_handles_greeting_without_kb_fallback():
    from app.voice.agent import process_voice_turn

    result = process_voice_turn({"message": "Hi"})

    assert result["status"] == "greeting"
    assert result["sources"] == []
    assert "loanova" in result["answer"].lower()
    assert "current knowledge base" not in result["answer"].lower()


def test_voice_agent_answers_product_question_before_qualification_flow(monkeypatch):
    from app.voice.agent import process_voice_turn

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
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
            return type("Result", (), {"content": "The demo loan supports working capital and equipment funding."})()

    monkeypatch.setattr(kb, "get_chat_model", lambda: AnsweringChat())

    result = process_voice_turn({
        "message": "What is the business loan for?",
        "conversation_state": {},
    })

    assert result["status"] == "knowledge_answer"
    assert result["grounded"] is True
    assert result["sources"][0]["record_id"] == "loan_001"


def test_voice_agent_handles_missing_information_and_objection(monkeypatch):
    from app.voice.agent import process_voice_turn

    monkeypatch.setattr(kb, "retrieve", lambda question, limit=4: [])

    result = process_voice_turn({
        "message": "I do not qualify and I need a business loan.",
        "business_type": "",
        "time_in_operation": "2 years",
        "requested_amount": "",
        "use_of_funds": "inventory",
    })

    assert result["status"] == "missing_fields"
    assert "business_type" in result["missing_fields"] or "requested_amount" in result["missing_fields"]
    assert "business type" in result["answer"].lower() or "requested loan amount" in result["answer"].lower()


def test_voice_agent_escalates_human_request(monkeypatch):
    from app.voice.agent import process_voice_turn

    monkeypatch.setattr(kb, "retrieve", lambda question, limit=4: [])

    result = process_voice_turn({
        "message": "Please connect me with a live agent for a callback.",
        "business_type": "restaurant",
        "time_in_operation": "2 years",
        "monthly_revenue": "75000",
        "requested_amount": "50000",
        "use_of_funds": "inventory",
    })

    assert result["status"] == "escalated"
    assert result["escalated"] is True
    assert "human" in result["answer"].lower()


def test_voice_agent_avoids_inventing_financial_claims(monkeypatch):
    from app.voice.agent import process_voice_turn

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
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

    result = process_voice_turn({
        "message": "What is the exact APR and fee for this loan?",
    })

    assert result["grounded"] is False
    assert result["sources"][0]["record_id"] == "loan_004"
    assert "unavailable" in result["answer"].lower()


def test_frontend_uses_host_browser_backend_url_when_backend_service_name_is_present(monkeypatch):
    monkeypatch.setenv("LOANOVA_API_URL", "http://backend:8000")

    assert streamlit_app.get_voice_api_url() == "http://localhost:8000/voice/conversation"


def test_frontend_calls_voice_api_contract(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "status": "knowledge_answer",
                "answer": "The demo loan supports working capital and equipment funding.",
                "grounded": True,
                "sources": [{
                    "record_id": "loan_001",
                    "title": "Business Loan Overview",
                    "source": "demo://loan-product-overview",
                }],
                "escalated": False,
            }

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(streamlit_app.requests, "post", fake_post)

    result = streamlit_app.call_voice_api("What is this loan for?", {"last_status": "ready"})

    assert captured["url"].endswith("/voice/conversation")
    assert captured["json"]["message"] == "What is this loan for?"
    assert captured["json"]["conversation_state"]["last_status"] == "ready"
    assert result["grounded"] is True
    assert result["sources"][0]["record_id"] == "loan_001"


def test_frontend_deduplicates_relevant_sources():
    sources = [
        {"record_id": "loan_001", "title": "Business Loan Overview", "source": "demo://loan-product-overview"},
        {"record_id": "loan_001", "title": "Business Loan Overview", "source": "demo://loan-product-overview"},
        {"record_id": "loan_004", "title": "Interest Rates and Fees", "source": "demo://rates-and-fees"},
    ]

    assert len(streamlit_app.dedupe_sources(sources)) == 2
    assert streamlit_app.strip_citation_suffix("The loan supports working capital.\n\nCitations: [loan_001] Business Loan Overview (demo://loan-product-overview)") == "The loan supports working capital."


def test_frontend_handles_backend_error(monkeypatch):
    class FakeResponse:
        status_code = 500
        text = '{"detail": "backend unavailable"}'

        def json(self):
            return {"detail": "backend unavailable"}

    def fake_post(url, json, timeout):
        return FakeResponse()

    monkeypatch.setattr(streamlit_app.requests, "post", fake_post)

    with pytest.raises(RuntimeError, match="backend unavailable"):
        streamlit_app.call_voice_api("What is the APR?")


def test_q4_signal_extraction_identifies_cross_sell_and_compliance_risks():
    from app.audio.insights import extract_call_signals

    transcript = (
        "Customer: I also have a second vehicle. "
        "Agent: I should disclose the policy terms before proceeding."
    )

    signals = extract_call_signals(transcript)
    labels = {signal["category"] for signal in signals}

    assert "missed_cross_sell" in labels
    assert "compliance_gap" in labels
    assert any(signal["confidence"] >= 0.6 for signal in signals)


def test_q4_nudge_engine_suppresses_duplicates_and_low_confidence():
    from app.audio.insights import generate_nudges

    signals = [
        {"category": "missed_cross_sell", "confidence": 0.91, "message": "Customer mentioned a second vehicle."},
        {"category": "missed_cross_sell", "confidence": 0.91, "message": "Customer mentioned a second vehicle."},
        {"category": "frustration", "confidence": 0.20, "message": "Customer sounded a bit annoyed."},
    ]

    nudges = generate_nudges(signals)
    labels = [nudge["category"] for nudge in nudges]

    assert labels.count("missed_cross_sell") == 1
    assert "frustration" not in labels
    assert any(nudge["priority"] >= 1 for nudge in nudges)


def test_q4_nudge_engine_respects_cooldown_window():
    from app.audio.insights import generate_nudges

    signals = [
        {"category": "missed_cross_sell", "confidence": 0.91, "message": "Customer mentioned a second vehicle.", "timestamp_ms": 2000},
    ]
    history = [{"category": "missed_cross_sell", "timestamp_ms": 0, "message": "Previous second-vehicle signal"}]

    nudges = generate_nudges(signals, history=history)

    assert nudges == []


def test_q4_latencies_are_reported_for_real_time_pipeline():
    from app.audio.insights import process_live_audio_stream

    result = process_live_audio_stream({
        "call_id": "call_123",
        "audio_chunks": [
            {"chunk_id": "c1", "timestamp_ms": 0, "duration_ms": 1000, "transcript": "Customer: I need a callback."},
            {"chunk_id": "c2", "timestamp_ms": 1000, "duration_ms": 1000, "transcript": "Agent: We can offer a callback."},
        ],
        "conversation_state": {"last_status": "ready"},
    })

    assert result["call_id"] == "call_123"
    assert result["latency"]["p95_ms"] >= result["latency"]["p50_ms"]
    assert result["latency"]["asr_ms"] >= 0
    assert result["transcript"]
    assert result["nudges"]


def test_q4_false_positive_controls_block_ambiguous_noise():
    from app.audio.insights import generate_nudges, extract_call_signals

    noisy = "Customer: uh hmm maybe maybe I am okay. Not clear."
    signals = extract_call_signals(noisy)
    nudges = generate_nudges(signals)

    assert signals == []
    assert nudges == []


def test_q4_frustration_signal_is_detected_and_nudged():
    from app.audio.insights import extract_call_signals, generate_nudges

    transcript = "Customer: I am upset and frustrated because I need a callback."
    signals = extract_call_signals(transcript)
    nudges = generate_nudges(signals)

    assert any(signal["category"] == "frustration" for signal in signals)
    assert any(nudge["category"] == "frustration" for nudge in nudges)
    assert any(nudge["priority"] >= 3 for nudge in nudges)


def test_voice_agent_integration_keeps_q1_q2_grounding_when_live_insights_are_present(monkeypatch):
    from app.voice.agent import process_voice_turn
    from app.audio.insights import process_live_audio_stream

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
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
            return type("Result", (), {"content": "The demo loan supports working capital and equipment funding."})()

    monkeypatch.setattr(kb, "get_chat_model", lambda: AnsweringChat())

    live_result = process_live_audio_stream({
        "call_id": "call_456",
        "audio_chunks": [{"chunk_id": "a1", "timestamp_ms": 0, "duration_ms": 2000, "transcript": "Customer: I also have a second vehicle and want to learn about the product."}],
        "conversation_state": {"last_status": "ready"},
    })

    result = process_voice_turn({
        "message": "What is this loan for?",
        "conversation_state": {"last_status": "ready", "live_insights": live_result},
    })

    assert live_result["nudges"]
    assert result["status"] == "knowledge_answer"
    assert result["grounded"] is True
    assert result["sources"][0]["record_id"] == "loan_001"
