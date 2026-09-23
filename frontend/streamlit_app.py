import json
import os
import re
from typing import Any

import requests
import streamlit as st

DEFAULT_API_URL = "http://localhost:8000"


def _normalize_backend_url(raw_url: str | None) -> str:
    candidate = (raw_url or os.getenv("LOANOVA_API_URL") or DEFAULT_API_URL).strip().rstrip("/")
    if not candidate:
        return DEFAULT_API_URL
    if candidate.startswith("http://backend"):
        return candidate.replace("http://backend", "http://localhost", 1)
    if candidate.startswith("https://backend"):
        return candidate.replace("https://backend", "https://localhost", 1)
    return candidate


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
    base_url = _normalize_backend_url(os.getenv("LOANOVA_API_URL"))
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


def build_voice_component_html(api_url: str) -> str:
    return f"""
    <div class="loanova-voice-shell">
      <div class="loanova-voice-header">
        <strong>Browser voice</strong>
        <span id="loanova-voice-status" class="loanova-voice-status idle">Idle</span>
      </div>
      <div id="loanova-voice-history" class="loanova-voice-history"></div>
      <label class="loanova-voice-label" for="loanova-language-select">Voice language</label>
      <select id="loanova-language-select">
        <option value="english">English</option>
        <option value="filipino">Filipino / Tagalog</option>
        <option value="taglish">Taglish</option>
        <option value="indonesian">Bahasa Indonesia</option>
      </select>
      <label class="loanova-voice-label" for="loanova-voice-select">English voice</label>
      <select id="loanova-voice-select">
        <option value="">Default browser voice</option>
      </select>
      <label class="loanova-voice-label" for="loanova-voice-input">Recognized text / text fallback</label>
      <textarea id="loanova-voice-input" rows="4" placeholder="Speak or type a question here..."></textarea>
      <div class="loanova-voice-actions">
        <button id="loanova-mic-button" type="button">Start mic</button>
        <button id="loanova-send-button" type="button" class="primary">Send</button>
        <button id="loanova-stop-button" type="button" class="secondary">Stop</button>
      </div>
      <div class="loanova-voice-note">
        Browser speech recognition and synthesis are supported only in modern browsers. English uses en-US; Filipino/Tagalog uses fil-PH (or the closest supported locale); Indonesian uses id-ID. If a browser does not support the selected locale, the typed text fallback remains available.
      </div>
    </div>
    <style>
      .loanova-voice-shell {{
        font-family: Inter, "Segoe UI", sans-serif;
        border: 1px solid rgba(148, 163, 184, 0.14);
        border-radius: 16px;
        padding: 18px 18px 16px;
        background: rgba(11, 20, 29, 0.7);
        box-shadow: none;
        margin-bottom: 18px;
      }}
      .loanova-voice-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 14px;
        padding-bottom: 10px;
        border-bottom: none;
      }}
      .loanova-voice-header strong {{
        font-size: 1.05rem;
        font-weight: 700;
        color: #edf4ff;
      }}
      .loanova-voice-status {{
        display: inline-block;
        border-radius: 999px;
        padding: 5px 10px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.02em;
      }}
      .loanova-voice-status.idle {{ background: rgba(52, 211, 153, 0.12); color: #b8f5d9; }}
      .loanova-voice-status.listening {{ background: rgba(251, 191, 36, 0.12); color: #fbdc80; }}
      .loanova-voice-status.speaking {{ background: rgba(59, 130, 246, 0.12); color: #bfdbfe; }}
      .loanova-voice-status.error {{ background: rgba(248, 113, 113, 0.12); color: #fecaca; }}
      .loanova-voice-history {{
        max-height: 180px;
        overflow-y: auto;
        margin-bottom: 14px;
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding-right: 4px;
      }}
      .loanova-voice-entry {{
        padding: 10px 12px;
        border-radius: 10px;
        font-size: 13px;
        line-height: 1.5;
        border: none;
      }}
      .loanova-voice-entry.user {{ background: rgba(59, 130, 246, 0.08); color: #e2e8f0; border-color: rgba(59,130,246,0.2); }}
      .loanova-voice-entry.assistant {{ background: rgba(148, 163, 184, 0.06); color: #edf4ff; }}
      .loanova-voice-label {{
        display: block;
        font-size: 12px;
        color: #c7d2e8;
        margin: 8px 0 7px;
        font-weight: 600;
      }}
      select, textarea {{
        width: 100%;
        box-sizing: border-box;
        border: 1px solid rgba(148, 163, 184, 0.22);
        border-radius: 10px;
        padding: 12px 14px;
        font: inherit;
        background: rgba(15, 23, 42, 0.72);
        color: #edf4ff;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
      }}
      select {{
        margin-bottom: 12px;
      }}
      select:hover, textarea:hover {{
        border-color: rgba(148, 163, 184, 0.35);
      }}
      select:focus, textarea:focus {{
        border-color: rgba(96, 165, 250, 0.9);
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.18);
        outline: none;
      }}
      textarea {{
        width: 100%;
        box-sizing: border-box;
        resize: vertical;
        min-height: 86px;
        border-radius: 12px;
        padding: 12px 14px;
        line-height: 1.5;
      }}
      .loanova-voice-actions {{
        display: flex;
        gap: 10px;
        margin-top: 12px;
        flex-wrap: wrap;
      }}
      button {{
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 10px;
        padding: 9px 14px;
        background: rgba(15, 23, 42, 0.85);
        color: #edf4ff;
        cursor: pointer;
        font-weight: 600;
        transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
      }}
      button:hover {{
        transform: translateY(-1px);
        border-color: rgba(148, 163, 184, 0.38);
        box-shadow: 0 8px 18px rgba(2, 6, 23, 0.18);
      }}
      button.primary {{ background: linear-gradient(135deg, #2563eb, #3b82f6); color: white; border-color: rgba(59,130,246,0.8); }}
      button.secondary {{ background: rgba(148, 163, 184, 0.08); }}
      .loanova-voice-note {{
        margin-top: 14px;
        font-size: 11px;
        color: #b3c3db;
        line-height: 1.5;
        padding-top: 10px;
        border-top: none;
      }}
    </style>
    <script>
      const apiUrl = {json.dumps(api_url)};
      const statusNode = document.getElementById('loanova-voice-status');
      const historyNode = document.getElementById('loanova-voice-history');
      const inputNode = document.getElementById('loanova-voice-input');
      const micButton = document.getElementById('loanova-mic-button');
      const sendButton = document.getElementById('loanova-send-button');
      const stopButton = document.getElementById('loanova-stop-button');
      const languageSelect = document.getElementById('loanova-language-select');
      const voiceSelect = document.getElementById('loanova-voice-select');
      const state = {{
        conversationState: {{}} ,
        recognition: null,
        isListening: false,
        isSpeaking: false,
      }};

      const localeMap = {{
        english: 'en-US',
        filipino: 'fil-PH',
        taglish: 'fil-PH',
        indonesian: 'id-ID',
      }};

      function selectedLocale() {{
        return localeMap[languageSelect.value] || 'en-US';
      }}

      function setStatus(label, cls) {{
        statusNode.textContent = label;
        statusNode.className = 'loanova-voice-status ' + cls;
      }}

      function getVoiceCandidates(locale) {{
        const normalized = (locale || 'en-US').toLowerCase();
        if (normalized.startsWith('en')) {{
          return ['en-US', 'en-gb', 'en-au', 'en-ca', 'en', 'english'];
        }}
        if (normalized.startsWith('fil') || normalized.startsWith('tl')) {{
          return ['fil-PH', 'fil', 'tl-PH', 'tl'];
        }}
        if (normalized.startsWith('id')) {{
          return ['id-ID', 'id'];
        }}
        return [normalized];
      }}

      function getBestVoiceForLocale(locale) {{
        const voices = window.speechSynthesis?.getVoices?.() || [];
        const candidates = getVoiceCandidates(locale);
        const localeLower = (locale || 'en-US').toLowerCase();
        const localePrefix = localeLower.split('-')[0];

        const exactLocaleMatch = voices.find((voice) => {{
          const lang = (voice.lang || '').toLowerCase();
          const name = (voice.name || '').toLowerCase();
          return candidates.some((candidate) => {{
            const cc = candidate.toLowerCase();
            return lang === cc || name.includes(cc);
          }});
        }});
        if (exactLocaleMatch) {{
          return exactLocaleMatch;
        }}

        const samePrefixMatch = voices.find((voice) => {{
          const lang = (voice.lang || '').toLowerCase();
          const name = (voice.name || '').toLowerCase();
          return lang.startsWith(localePrefix) || name.includes(localePrefix);
        }});
        return samePrefixMatch || null;
      }}

      function populateVoiceDropdown() {{
        const voices = window.speechSynthesis?.getVoices?.() || [];
        const currentChoice = voiceSelect.value || '';
        const locale = selectedLocale();
        const localeLower = locale.toLowerCase();
        const preferredVoice = getBestVoiceForLocale(locale);

        while (voiceSelect.options.length > 0) {{
          voiceSelect.remove(0);
        }}

        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = 'Default browser voice';
        voiceSelect.appendChild(defaultOption);

        voices.forEach((voice) => {{
          const option = document.createElement('option');
          const lang = (voice.lang || '').toLowerCase();
          const name = (voice.name || '').toLowerCase();
          option.value = voice.name;
          option.textContent = voice.name + ' (' + voice.lang + ')';

          const isPreferred = preferredVoice && voice.name === preferredVoice.name;
          const isLocaleMatch = lang.startsWith(localeLower.split('-')[0]) || name.includes(localeLower.split('-')[0]);
          if (isPreferred) {{
            option.selected = true;
          }} else if (!currentChoice && isLocaleMatch) {{
            option.selected = true;
          }}
          voiceSelect.appendChild(option);
        }});

        if (!voiceSelect.value) {{
          voiceSelect.value = '';
        }}
      }}

      function ensureVoicesLoaded() {{
        return new Promise((resolve) => {{
          const loadVoices = () => {{
            const voices = window.speechSynthesis?.getVoices?.() || [];
            if (voices.length) {{
              populateVoiceDropdown();
              resolve(voices);
              return true;
            }}
            return false;
          }};
          if (loadVoices()) {{
            return;
          }}
          const onVoicesChanged = () => {{
            if (loadVoices()) {{
              window.speechSynthesis.removeEventListener('voiceschanged', onVoicesChanged);
            }}
          }};
          window.speechSynthesis.addEventListener('voiceschanged', onVoicesChanged);
        }});
      }}

      function addHistoryEntry(role, text) {{
        const entry = document.createElement('div');
        entry.className = 'loanova-voice-entry ' + role;
        entry.textContent = text;
        historyNode.appendChild(entry);
        historyNode.scrollTop = historyNode.scrollHeight;
      }}

      async function speakAnswer(answer) {{
        if (!answer || !('speechSynthesis' in window)) {{
          setStatus('Response ready', 'idle');
          return;
        }}
        const locale = selectedLocale();
        const utterance = new SpeechSynthesisUtterance(answer);
        utterance.lang = locale;
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;

        await ensureVoicesLoaded();
        const voices = window.speechSynthesis?.getVoices?.() || [];
        const selectedVoiceName = voiceSelect.value;
        const matchingVoice = voices.find((voice) => voice.name === selectedVoiceName) || getBestVoiceForLocale(locale);

        if (matchingVoice) {{
          const voiceLang = (matchingVoice.lang || '').toLowerCase();
          const voiceName = (matchingVoice.name || '').toLowerCase();
          const localeLower = locale.toLowerCase();
          const localePrefix = localeLower.split('-')[0];
          const isMatchingLocale = voiceLang === localeLower || voiceLang.startsWith(localePrefix) || voiceName.includes(localePrefix) || voiceName.includes('english');
          if (isMatchingLocale) {{
            utterance.voice = matchingVoice;
          }} else if (localeLower.startsWith('en')) {{
            setStatus('No suitable English voice available. Using the browser default voice is not high quality on this browser.', 'error');
          }}
        }} else if (locale.toLowerCase().startsWith('en')) {{
          setStatus('No suitable English voice available. Using the browser default voice is not high quality on this browser.', 'error');
        }}

        utterance.onstart = () => {{
          state.isSpeaking = true;
          setStatus('Speaking', 'speaking');
        }};
        utterance.onend = () => {{
          state.isSpeaking = false;
          setStatus('Idle', 'idle');
        }};
        utterance.onerror = () => {{
          state.isSpeaking = false;
          setStatus('Speech synthesis error. Text fallback remains available.', 'error');
        }};

        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(utterance);
      }}

      async function sendMessage() {{
        const text = (inputNode.value || '').trim();
        if (!text) {{
          setStatus('Type a question first', 'error');
          return;
        }}

        addHistoryEntry('user', text);
        setStatus('Sending...', 'idle');

        try {{
          const response = await fetch(apiUrl, {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ message: text, language: languageSelect.value, conversation_state: state.conversationState }})
          }});

          if (!response.ok) {{
            const detailText = await response.text();
            throw new Error(detailText || 'Unknown API error');
          }}

          const payload = await response.json();
          const answer = payload.answer || 'No answer returned.';
          if (payload.conversation_state) {{
            state.conversationState = payload.conversation_state;
          }}
          addHistoryEntry('assistant', answer);
          if (payload.answer) {{
            speakAnswer(payload.answer);
          }} else {{
            setStatus('Response ready', 'idle');
          }}
          inputNode.value = '';
        }} catch (error) {{
          addHistoryEntry('assistant', 'Error: ' + (error && error.message ? error.message : String(error)));
          setStatus('Error contacting the Loanova API', 'error');
        }}
      }}

      function stopListening() {{
        if (state.recognition) {{
          state.recognition.stop();
          state.recognition = null;
        }}
        state.isListening = false;
        setStatus('Idle', 'idle');
      }}

      function startListening() {{
        const SpeechRecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognitionCtor) {{
          setStatus('Speech recognition unavailable in this browser', 'error');
          return;
        }}

        if (state.recognition) {{
          state.recognition.stop();
        }}

        const recognition = new SpeechRecognitionCtor();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = selectedLocale();

        recognition.onstart = () => {{
          state.isListening = true;
          setStatus('Listening...', 'listening');
        }};

        recognition.onresult = (event) => {{
          let transcript = '';
          for (let i = 0; i < event.results.length; i += 1) {{
            transcript += event.results[i][0].transcript;
          }}
          inputNode.value = transcript.trim();
        }};

        recognition.onerror = (event) => {{
          state.isListening = false;
          if (event.error === 'not-allowed' || event.error === 'permission-denied') {{
            setStatus('Microphone permission denied. Use text input instead.', 'error');
          }} else if (event.error === 'language-not-supported') {{
            setStatus('Selected browser locale is unavailable; text input remains available.', 'error');
          }} else {{
            setStatus('Speech recognition error. Use text input instead.', 'error');
          }}
        }};

        recognition.onend = () => {{
          state.isListening = false;
          if (!inputNode.value.trim()) {{
            setStatus('Ready for text input', 'idle');
          }} else {{
            setStatus('Voice text captured', 'idle');
          }}
          state.recognition = null;
        }};

        state.recognition = recognition;
        recognition.start();
      }}

      languageSelect.addEventListener('change', () => {{
        populateVoiceDropdown();
        setStatus('Language selected: ' + languageSelect.value, 'idle');
      }});
      voiceSelect.addEventListener('change', () => {{
        setStatus('Voice selected: ' + (voiceSelect.value || 'Default browser voice'), 'idle');
      }});
      micButton.addEventListener('click', startListening);
      sendButton.addEventListener('click', sendMessage);
      stopButton.addEventListener('click', () => {{
        if (state.isListening) {{
          stopListening();
        }} else {{
          window.speechSynthesis?.cancel();
          setStatus('Stopped', 'idle');
        }}
      }});
      inputNode.addEventListener('keydown', (event) => {{
        if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {{
          sendMessage();
        }}
      }});
      populateVoiceDropdown();
      setStatus('Idle', 'idle');
    </script>
    """


def render_voice_panel() -> None:
    st.caption("Browser speech: recognition and speech synthesis only; no phone or telephony integration.")
    st.components.v1.html(build_voice_component_html(get_voice_api_url()), height=500, scrolling=True)


def inject_ui_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --loanova-bg: #071826;
            --loanova-bg-elevated: rgba(18, 31, 44, 0.9);
            --loanova-panel: rgba(18, 30, 42, 0.92);
            --loanova-panel-soft: rgba(26, 41, 54, 0.88);
            --loanova-border: rgba(148, 163, 184, 0.18);
            --loanova-text: #edf4ff;
            --loanova-muted: #a5b7cf;
            --loanova-accent: #3b82f6;
            --loanova-accent-strong: #2563eb;
            --loanova-success: #34d399;
            --loanova-warning: #fbbf24;
            --loanova-danger: #f87171;
        }

        html, body, [data-testid="stAppViewContainer"], .main, [data-testid="stMain"], .stApp {
            background: #020d13 !important;
            color: var(--loanova-text) !important;
        }

        .stApp {
            background: #020d13 !important;
        }

        .block-container,
        section[data-testid="stMain"] > div {
            background: #020d13 !important;
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        .stSidebar {
            background: linear-gradient(180deg, rgba(14, 25, 36, 0.96) 0%, rgba(12, 21, 31, 0.98) 100%);
            border-right: 1px solid rgba(148, 163, 184, 0.14);
            padding-left: 0.5rem;
            padding-right: 0.5rem;
        }

        section[data-testid="stSidebar"] > div {
            padding-top: 1.1rem;
        }

        [data-testid="stSidebarHeader"] {
            display: none !important;
        }

        [data-testid="stSidebarNav"] {
            gap: 0.75rem;
        }

        [data-testid="stSidebarNavLink"] {
            color: var(--loanova-text) !important;
            opacity: 0.9;
        }

        .sidebar-brand {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.25rem 0.5rem 1rem;
            margin-bottom: 1.2rem;
        }

        .sidebar-brand-icon {
            width: 2.2rem;
            height: 2.2rem;
            border-radius: 0.8rem;
            display: grid;
            place-items: center;
            background: linear-gradient(135deg, #ff5d57, #f24d4d);
            box-shadow: 0 10px 24px rgba(242, 77, 77, 0.35);
            font-size: 1.1rem;
        }

        .sidebar-brand-text {
            font-size: 1.15rem;
            font-weight: 700;
            letter-spacing: -0.04em;
            color: var(--loanova-text);
        }

        .sidebar-nav-item {
            width: 100%;
            display: flex;
            align-items: center;
            gap: 0.7rem;
            border-radius: 0.8rem;
            padding: 0.7rem 0.8rem;
            color: var(--loanova-text);
            background: transparent;
            border: 1px solid transparent;
            transition: all 0.2s ease;
            margin: 0.15rem 0;
        }

        .sidebar-nav-item.active {
            background: rgba(59, 130, 246, 0.18);
            border-color: rgba(96, 165, 250, 0.25);
            box-shadow: inset 0 0 0 1px rgba(96, 165, 250, 0.08);
        }

        .sidebar-nav-item:hover {
            background: rgba(148, 163, 184, 0.05);
            border-color: rgba(148, 163, 184, 0.12);
        }

        .sidebar-nav-icon {
            width: 1.1rem;
            text-align: center;
            opacity: 0.9;
            font-size: 1rem;
        }

        .sidebar-subtle {
            color: var(--loanova-muted);
            font-size: 0.82rem;
            margin-top: 0.35rem;
        }

        .stSidebar .stButton > button,
        .stButton > button {
            border-radius: 0.85rem;
            border: 1px solid var(--loanova-border);
            background: rgba(148, 163, 184, 0.08);
            color: var(--loanova-text);
            font-weight: 600;
            transition: all 0.2s ease;
        }

        .stSidebar .stButton > button:hover,
        .stButton > button:hover {
            border-color: rgba(148, 163, 184, 0.28);
            transform: translateY(-1px);
            box-shadow: 0 10px 20px rgba(15, 23, 42, 0.14);
        }

        .stButton > button:focus,
        select:focus,
        textarea:focus,
        input:focus {
            outline: 2px solid rgba(59, 130, 246, 0.68);
            outline-offset: 2px;
        }

        h1 {
            color: var(--loanova-text) !important;
            letter-spacing: -0.04em;
            margin-bottom: 0.35rem !important;
            font-size: clamp(2.1rem, 2.2vw, 2.7rem) !important;
        }

        .stCaption {
            color: var(--loanova-muted) !important;
            font-size: 0.96rem !important;
        }

        [data-testid="stChatMessage"] {
            background: transparent !important;
            border: none !important;
            padding: 0.2rem 0 !important;
        }

        [data-testid="stChatMessageContent"],
        [data-testid="stChatMessage"] p,
        .stMarkdownContainer p {
            color: var(--loanova-text) !important;
            line-height: 1.6 !important;
        }

        [data-testid="stChatMessage"] .stMarkdownContainer {
            background: rgba(15, 23, 42, 0.55);
            border: 1px solid var(--loanova-border);
            border-radius: 1rem;
            padding: 0.9rem 1rem;
            box-shadow: inset 0 1px 0 rgba(148, 163, 184, 0.08);
        }

        [data-testid="stChatMessage"]:has(.assistant) .stMarkdownContainer,
        [data-testid="stChatMessage"] .assistant .stMarkdownContainer {
            background: rgba(18, 31, 44, 0.82) !important;
        }

        [data-testid="stChatMessage"]:has(.user) .stMarkdownContainer,
        [data-testid="stChatMessage"] .user .stMarkdownContainer {
            background: rgba(37, 99, 235, 0.12) !important;
            border-color: rgba(59, 130, 246, 0.3);
        }

        .stChatInput {
            background: rgba(18, 28, 38, 0.9);
            border: 1px solid rgba(96, 165, 250, 0.18);
            border-radius: 1.25rem;
            box-shadow: none;
            padding: 0.15rem 0.3rem 0.15rem 0.9rem;
            margin-top: 1rem;
        }

        .stChatInput:focus-within {
            border-color: rgba(96, 165, 250, 0.9);
            box-shadow: 0 0 0 1px rgba(96, 165, 250, 0.28);
        }

        .stChatInput textarea {
            background: transparent !important;
            color: var(--loanova-text) !important;
            border: none !important;
            font-size: 1.06rem !important;
            padding: 0.75rem 0.4rem 0.75rem 0 !important;
            box-shadow: none !important;
            min-height: 3rem !important;
        }

        .stChatInput button {
            border-radius: 0.8rem;
            background: linear-gradient(135deg, #1d73ff, #3b82f6);
            border: none;
            color: white;
            font-weight: 700;
            padding: 0.7rem 1rem;
            min-width: 3.25rem;
            box-shadow: none;
        }

        .stChatInput button:hover {
            filter: brightness(1.08);
        }

        .loanova-dashboard-shell {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 0.5rem 2rem;
        }

        .loanova-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 1rem;
            margin: 0.5rem 0 1.5rem;
            padding: 0.25rem 0.2rem;
        }

        .loanova-header-title {
            display: flex;
            align-items: center;
            gap: 0.8rem;
        }

        .loanova-header-badge {
            width: 2.7rem;
            height: 2.7rem;
            border-radius: 0.8rem;
            display: grid;
            place-items: center;
            background: linear-gradient(135deg, #1fd4a2, #0ea5e9);
            box-shadow: 0 10px 24px rgba(16, 185, 129, 0.35);
            font-size: 1.3rem;
        }

        .loanova-header-copy {
            display: flex;
            flex-direction: column;
        }

        .loanova-header-copy h1 {
            font-size: 2.4rem !important;
            margin: 0 !important;
            letter-spacing: -0.06em;
            color: var(--loanova-text) !important;
        }

        .loanova-header-copy p {
            margin: 0.15rem 0 0 !important;
            color: var(--loanova-muted) !important;
            font-size: 1rem !important;
        }

        .loanova-status-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.55rem;
            padding: 0.45rem 0.8rem;
            border-radius: 999px;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(148, 163, 184, 0.14);
            color: #dfeaf9;
            font-size: 0.82rem;
            font-weight: 600;
        }

        .loanova-status-dot {
            width: 0.65rem;
            height: 0.65rem;
            border-radius: 50%;
            background: #34d399;
            box-shadow: 0 0 10px rgba(52, 211, 153, 0.8);
        }

        .loanova-hero {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 2rem;
            min-height: 170px;
            padding: 1.1rem 1.2rem 1rem 1.5rem;
            border-radius: 1.2rem;
            background: linear-gradient(135deg, rgba(37, 99, 235, 0.12), rgba(30, 64, 175, 0.18));
            border: 1px solid rgba(96, 165, 250, 0.16);
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
        }

        .loanova-hero-content {
            flex: 1;
            min-width: 0;
        }

        .loanova-hero-title {
            font-size: clamp(2.1rem, 2.8vw, 3.2rem) !important;
            line-height: 1.08 !important;
            letter-spacing: -0.06em;
            margin: 0 !important;
            font-weight: 800 !important;
            color: var(--loanova-text) !important;
        }

        .loanova-hero-subtitle {
            margin-top: 0.7rem;
            color: #dfeaf9 !important;
            font-size: 1.05rem !important;
            line-height: 1.55 !important;
            max-width: 750px;
        }

        .loanova-hero-badge {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 220px;
            min-width: 220px;
            height: 110px;
            border-radius: 1.2rem;
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.26), rgba(96, 165, 250, 0.12));
            border: 1px solid rgba(96, 165, 250, 0.22);
            color: var(--loanova-text);
            font-weight: 800;
            letter-spacing: 0.04em;
            font-size: 0.9rem;
            text-transform: uppercase;
            position: relative;
            overflow: hidden;
        }

        .loanova-hero-badge::before {
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(135deg, rgba(255,255,255,0.08), rgba(255,255,255,0.0));
        }

        .loanova-hero-badge span {
            position: relative;
            z-index: 1;
        }

        .loanova-message-wrap {
            display: grid;
            gap: 1.25rem;
            margin-top: 1.4rem;
        }

        .loanova-message-row {
            display: flex;
            align-items: flex-start;
            gap: 0.8rem;
        }

        .loanova-message-row.user {
            justify-content: flex-end;
        }

        .loanova-icon {
            width: 2.3rem;
            height: 2.3rem;
            border-radius: 0.7rem;
            display: grid;
            place-items: center;
            background: linear-gradient(135deg, rgba(67, 186, 255, 0.9), rgba(59, 130, 246, 0.75));
            flex-shrink: 0;
            font-size: 1.1rem;
            box-shadow: 0 8px 18px rgba(59, 130, 246, 0.18);
        }

        .loanova-prompt-card {
            display: inline-flex;
            align-items: center;
            padding: 0.7rem 1rem;
            border-radius: 999px;
            border: 1px solid rgba(96, 165, 250, 0.2);
            background: rgba(37, 99, 235, 0.12);
            color: #dfeaff;
            margin: 0.5rem 0;
            font-size: 0.95rem;
        }

        .loanova-user-bubble {
            max-width: 60%;
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.82), rgba(96, 165, 250, 0.72));
            color: white;
            border-radius: 1.2rem 1.2rem 0.35rem 1.2rem;
            padding: 0.9rem 1.1rem;
            font-size: 1.02rem;
            line-height: 1.55;
            box-shadow: 0 10px 18px rgba(59, 130, 246, 0.15);
        }

        .loanova-assistant-bubble {
            max-width: 72%;
            background: rgba(18, 31, 45, 0.78);
            border: 1px solid rgba(148, 163, 184, 0.12);
            border-radius: 1.2rem 1.2rem 1.2rem 0.35rem;
            padding: 1rem 1.1rem;
            color: var(--loanova-text);
            line-height: 1.6;
            font-size: 1.03rem;
        }

        .loanova-help-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            margin-top: 0.9rem;
            margin-left: 2.8rem;
        }

        .loanova-help-pill {
            border-radius: 999px;
            border: 1px solid rgba(96, 165, 250, 0.18);
            background: rgba(37, 99, 235, 0.08);
            color: #dfeaf9;
            padding: 0.55rem 0.9rem;
            font-size: 0.9rem;
            cursor: pointer;
        }

        .loanova-chat-panel {
            margin-top: 1rem;
            border-radius: 1.1rem;
            background: rgba(13, 24, 34, 0.82);
            border: 1px solid rgba(148, 163, 184, 0.12);
            padding: 0.3rem 0.5rem 0.5rem;
        }

        .loanova-voice-toolbar {
            display: grid;
            grid-template-columns: 1.2fr 1.2fr 1fr;
            gap: 1rem;
            align-items: end;
            margin-top: 1rem;
        }

        .loanova-voice-control {
            display: flex;
            flex-direction: column;
            gap: 0.45rem;
        }

        .loanova-voice-label {
            color: var(--loanova-muted);
            font-size: 0.8rem;
            font-weight: 600;
        }

        .loanova-voice-select {
            min-height: 2.8rem !important;
            border-radius: 0.8rem;
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid rgba(148, 163, 184, 0.14);
            color: var(--loanova-text);
        }

        .loanova-voice-actions {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            justify-content: center;
            min-height: 3.2rem;
        }

        .loanova-action-btn {
            max-width: 120px;
            flex: 1;
            min-height: 3rem;
            border-radius: 0.8rem;
            font-weight: 700;
            border: 1px solid rgba(148, 163, 184, 0.12);
        }

        .loanova-action-btn.primary {
            background: linear-gradient(135deg, #2563eb, #3b82f6);
            border-color: rgba(96, 165, 250, 0.4);
        }

        .loanova-action-btn.secondary {
            background: rgba(148, 163, 184, 0.08);
        }

        .loanova-floating-status {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            border-radius: 999px;
            padding: 0.35rem 0.7rem;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(148, 163, 184, 0.12);
            color: #dfeaf9;
            font-size: 0.85rem;
            font-weight: 600;
        }

        @media (max-width: 1100px) {
            .loanova-hero {
                flex-direction: column;
                align-items: flex-start;
            }
            .loanova-hero-badge {
                width: 100%;
                min-width: 0;
            }
        }

        @media (max-width: 768px) {
            .loanova-header {
                flex-direction: column;
                align-items: flex-start;
            }
            .loanova-header-copy h1 {
                font-size: 1.9rem !important;
            }
            .loanova-voice-toolbar {
                grid-template-columns: 1fr;
            }
            .loanova-user-bubble,
            .loanova-assistant-bubble {
                max-width: 100%;
            }
        }

        .stError, .stWarning, .stInfo {
            border-radius: 0.9rem;
            border: 1px solid var(--loanova-border);
            box-shadow: none;
        }

        .stExpander {
            border: 1px solid var(--loanova-border) !important;
            border-radius: 0.9rem !important;
            background: rgba(15, 23, 42, 0.5);
        }

        .stExpander summary {
            color: var(--loanova-text) !important;
            font-weight: 600;
        }

        @media (max-width: 768px) {
            .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
            }

            h1 {
                font-size: 1.8rem !important;
            }

            [data-testid="stChatMessage"] .stMarkdownContainer {
                padding: 0.8rem 0.9rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="Loanova Assistant",
        page_icon="💼",
        layout="wide",
    )

    inject_ui_theme()

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "conversation_state" not in st.session_state:
        st.session_state.conversation_state = {}

    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-brand">
                <div class="sidebar-brand-icon">🌱</div>
                <div class="sidebar-brand-text">loan</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        nav_items = [
            ("Chat", "💬", True),
            ("How it works", "💡", False),
            ("About", "ℹ️", False),
            ("Settings", "⚙️", False),
        ]

        for label, icon, active in nav_items:
            item_class = "sidebar-nav-item active" if active else "sidebar-nav-item"
            st.markdown(
                f'<div class="{item_class}"><span class="sidebar-nav-icon">{icon}</span><span>{label}</span></div>',
                unsafe_allow_html=True,
            )

        st.markdown("<div class='sidebar-subtle'>System ready</div>", unsafe_allow_html=True)
        st.markdown("<div class='sidebar-subtle'>API: {}</div>".format(get_voice_api_url()), unsafe_allow_html=True)
        if st.button("Reset conversation", use_container_width=True):
            st.session_state.messages = []
            st.session_state.conversation_state = {}
            st.rerun()

    st.markdown(
        """
        <div class="loanova-dashboard-shell">
          <div class="loanova-header">
            <div class="loanova-header-title">
              <div class="loanova-header-badge">🌱</div>
              <div class="loanova-header-copy">
                <h1>Loanova</h1>
                <p>Your AI-Powered Loan Assistance Assistant</p>
              </div>
            </div>
            <div class="loanova-status-pill"><span class="loanova-status-dot"></span>System Ready</div>
          </div>

          <div class="loanova-hero">
            <div class="loanova-hero-content">
              <h2 class="loanova-hero-title">Hi! I’m Loanova 👋</h2>
              <div class="loanova-hero-subtitle">Ask me anything about our business loan product — I can explain features, guide you through the qualification process, and answer your questions in multiple languages.</div>
            </div>
            <div class="loanova-hero-badge"><span>Business Loan</span></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="loanova-message-wrap">', unsafe_allow_html=True)
    for entry in st.session_state.messages:
        render_chat_message(entry)
    st.markdown('</div>', unsafe_allow_html=True)

    if not st.session_state.messages:
        st.markdown(
            """
            <div class="loanova-message-row">
              <div class="loanova-icon">🤖</div>
              <div class="loanova-assistant-bubble">
                Hello! I’m Loanova 👋<br>
                How can I help you with our business loan product today?
                <div class="loanova-help-row">
                  <span class="loanova-help-pill">What is this loan for?</span>
                  <span class="loanova-help-pill">Who is eligible?</span>
                  <span class="loanova-help-pill">What documents are needed?</span>
                  <span class="loanova-help-pill">How to apply?</span>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    render_voice_panel()

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
