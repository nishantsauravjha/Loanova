import os
import re
from typing import Any

import requests
import streamlit as st

DEFAULT_API_URL = os.getenv("LOANOVA_API_URL", "http://localhost:8000")


def dedupe_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for source in sources or []:
        key = (
            str(source.get("record_id", "unknown")),
            str(source.get("title", source.get("source", "unknown"))),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(source)
    return deduped


def strip_citation_suffix(content: str) -> str:
    if not content:
        return content
    return re.split(r"\n\s*\nCitations:\s*", content, maxsplit=1)[0].strip()


def get_voice_api_url() -> str:
    base_url = os.getenv("LOANOVA_API_URL", "http://localhost:8000").rstrip("/")
    return f"{base_url}/voice/conversation"


def call_voice_api(message: str, conversation_state: dict[str, Any] | None = None) -> dict[str, Any]:
    if not message or not message.strip():
        raise ValueError("A customer question or request is required.")

    payload: dict[str, Any] = {"message": message.strip()}
    if conversation_state:
        payload["conversation_state"] = conversation_state

    try:
        response = requests.post(get_voice_api_url(), json=payload, timeout=30)
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Unable to reach the Loanova API at {get_voice_api_url()}. Confirm the backend is running."
        ) from exc

    if response.status_code >= 400:
        detail = response.text.strip()
        try:
            payload_body = response.json()
            if isinstance(payload_body, dict):
                detail = payload_body.get("detail", detail)
        except ValueError:
            pass
        raise RuntimeError(
            f"Loanova API error ({response.status_code}): {detail or 'Unknown API error'}"
        )

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("The Loanova API returned invalid JSON.") from exc


def render_chat_message(entry: dict[str, Any]) -> None:
    role = entry.get("role", "assistant")
    content = strip_citation_suffix(entry.get("content", ""))

    with st.chat_message(role):
        st.markdown(content)

    sources = dedupe_sources(entry.get("sources") or [])
    if sources:
        with st.expander("Evidence & Sources"):
            for source in sources:
                title = source.get("title", "Untitled")
                record_id = source.get("record_id", "unknown")
                source_name = source.get("source", "unknown")
                st.caption(f"{record_id} — {title} ({source_name})")


def main() -> None:
    st.set_page_config(
        page_title="Loanova Assistant",
        page_icon="💼",
        layout="wide",
    )

    st.title("Loanova — Loan Assistance Assistant")
    st.caption("Grounded answers only. No real approvals, final rates, or binding offers are generated.")

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "conversation_state" not in st.session_state:
        st.session_state.conversation_state = {}

    st.sidebar.header("Session")
    st.sidebar.caption(f"API: {get_voice_api_url()}")
    if st.sidebar.button("Reset conversation"):
        st.session_state.messages = []
        st.session_state.conversation_state = {}
        st.rerun()

    for entry in st.session_state.messages:
        render_chat_message(entry)

    user_input = st.chat_input("Ask about the loan product, qualification details, or a human callback.")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        render_chat_message(st.session_state.messages[-1])

        try:
            with st.spinner("Checking the knowledge base and qualification flow..."):
                response = call_voice_api(user_input, st.session_state.conversation_state)
        except RuntimeError as exc:
            error_message = {"role": "assistant", "content": f"I hit an error: {exc}", "sources": []}
            st.session_state.messages.append(error_message)
            st.error(str(exc))
            render_chat_message(error_message)
            return

        answer = response.get("answer", "No answer returned.")
        status = response.get("status", "knowledge_answer")
        sources = dedupe_sources(response.get("sources", []))
        assistant_message = {
            "role": "assistant",
            "content": answer,
            "status": status,
            "sources": sources,
            "grounded": bool(response.get("grounded", False)),
            "escalated": bool(response.get("escalated", False)),
        }
        st.session_state.messages.append(assistant_message)
        render_chat_message(assistant_message)

        if response.get("missing_fields"):
            st.info(f"Missing information: {', '.join(response['missing_fields'])}")
        elif response.get("status") == "escalated":
            st.warning("Human follow-up requested.")

        if response.get("conversation_state"):
            st.session_state.conversation_state = response["conversation_state"]
        elif sources:
            st.session_state.conversation_state = {
                **st.session_state.conversation_state,
                "last_status": status,
                "last_source": sources[0].get("record_id"),
            }


if __name__ == "__main__":
    main()
