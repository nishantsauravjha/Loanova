import re
from typing import Any

LANGUAGE_ALIASES = {
    "en": "english",
    "eng": "english",
    "english": "english",
    "en-us": "english",
    "fil": "filipino",
    "ph": "filipino",
    "philippines": "filipino",
    "filipino": "filipino",
    "fil-ph": "filipino",
    "filipino/ph": "filipino",
    "tagalog": "filipino",
    "taglish": "taglish",
    "id": "indonesian",
    "id-id": "indonesian",
    "indonesia": "indonesian",
    "bahasa indonesia": "indonesian",
    "bahasa-indonesia": "indonesian",
    "indonesian": "indonesian",
}

BROWSER_LOCALES = {
    "english": "en-US",
    "filipino": "fil-PH",
    "taglish": "fil-PH",
    "indonesian": "id-ID",
}

TAGALOG_MARKERS = (
    "kamusta",
    "magandang",
    "gusto",
    "kailangan",
    "ano",
    "beneficiary",
    "rider",
    "lapse",
    "renewal",
    "bancassurance",
    "negosyo",
    "pamilya",
    "pwede",
    "tulong",
    "para sa",
    "kumusta",
)

INDONESIAN_MARKERS = (
    "halo",
    "saya",
    "mau",
    "aku",
    "apakah",
    "cicilan",
    "tenor",
    "denda",
    "dp",
    "jatuh",
    "tempo",
    "angsuran",
    "pembiayaan",
    "kredit",
    "pinjaman",
    "membutuhkan",
    "tingkat",
    "bunga",
    "biaya",
    "cash",
)

ENGLISH_MARKERS = (
    "loan",
    "business",
    "premium",
    "coverage",
    "policy",
    "approval",
    "rate",
    "fee",
    "callback",
    "agent",
    "human",
)

LANGUAGE_EXAMPLES = {
    "filipino": [
        "Kamusta, ano ang loan para sa negosyo?",
        "Magandang araw, kailangan ko ng business loan para sa negosyo.",
        "Pwede po ba akong magtanong tungkol sa preliminary qualification?",
    ],
    "taglish": [
        "Magandang araw, I need a business loan for my negosyo.",
        "Hi, I want to know the product and the approval process.",
        "Kamusta, my business has been operating for 2 years and I need 50k.",
    ],
    "indonesian": [
        "Halo, apakah pinjaman usaha ini untuk modal kerja?",
        "Saya mau tahu cicilan dan tenor untuk pembiayaan.",
        "Apakah saya perlu membayar DP atau ada biaya lain?",
    ],
}

LANGUAGE_CAPABILITY_NOTES = {
    "filipino": {
        "locale": "fil-PH",
        "asr": "Browser speech recognition may work with Filipino/Tagalog locale if the browser and OS provide the language pack; quality is browser-dependent.",
        "tts": "Browser speech synthesis uses installed browser or OS voices; native Filipino TTS quality is not guaranteed and may fall back to default voices.",
        "regional_note": "Regional-accent quality can vary by browser and device; actual performance must be validated manually.",
    },
    "taglish": {
        "locale": "fil-PH",
        "asr": "Mixed English/Tagalog speech is supported only to the extent the browser recognizes the local locale and the user’s pronunciation.",
        "tts": "Taglish responses may use the browser default voice if no suitable local Filipino voice is installed.",
        "regional_note": "Code-switching quality is hardware- and browser-dependent; do not claim native-quality accent fidelity without evidence.",
    },
    "indonesian": {
        "locale": "id-ID",
        "asr": "Browser speech recognition may support Indonesian, but accuracy varies by browser, model, and local microphone quality.",
        "tts": "Browser speech synthesis quality depends on installed Indonesian voices; native-quality TTS is not guaranteed.",
        "regional_note": "Regional-accent support should be treated as browser-dependent and must be validated manually; the repo does not claim production accent guarantees.",
    },
}


def detect_language(text: str | None) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    if not normalized:
        return "english"

    tagalog_hits = sum(1 for marker in TAGALOG_MARKERS if marker in normalized)
    indonesian_hits = sum(1 for marker in INDONESIAN_MARKERS if marker in normalized)
    english_hits = sum(1 for marker in ENGLISH_MARKERS if marker in normalized)

    if tagalog_hits and english_hits:
        return "taglish"
    if tagalog_hits:
        return "filipino"
    if indonesian_hits and english_hits:
        return "indonesian"
    if indonesian_hits:
        return "indonesian"
    if english_hits:
        return "english"
    return "english"


def normalize_language_hint(value: Any) -> str:
    if value is None:
        return "english"
    normalized = str(value).strip().lower().replace("_", "-")
    if normalized in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[normalized]
    for alias, mapped in LANGUAGE_ALIASES.items():
        if normalized in alias:
            return mapped
    return detect_language(normalized)


def browser_locale_for_language(language: str | None) -> str:
    normalized = normalize_language_hint(language or "english")
    return BROWSER_LOCALES.get(normalized, "en-US")


def language_examples_for_market(language: str | None) -> list[str]:
    normalized = normalize_language_hint(language or "english")
    return list(LANGUAGE_EXAMPLES.get(normalized, LANGUAGE_EXAMPLES["filipino"]))


def get_market_voice_capabilities(language: str | None) -> dict[str, str]:
    normalized = normalize_language_hint(language or "english")
    notes = LANGUAGE_CAPABILITY_NOTES.get(normalized, LANGUAGE_CAPABILITY_NOTES["filipino"])
    return {
        "language": normalized,
        "browser_locale": browser_locale_for_language(normalized),
        "asr": notes["asr"],
        "tts": notes["tts"],
        "regional_note": notes["regional_note"],
    }


def _localize_unsupported_answer(language: str, answer: str) -> str:
    if language == "filipino":
        translated = answer.replace(
            "The requested loan rates, fees, eligibility, or approvals are unavailable in the demo knowledge base.",
            "Ang mga hinihinging rate ng loan, bayarin, pagiging kwalipikado, o approval ay hindi available sa demo knowledge base.",
        )
        translated = translated.replace(
            "This system supports synthetic, non-binding guidance only and can collect preliminary details or arrange a human follow-up.",
            "Ang sistemang ito ay para lamang sa synthetic, non-binding na gabay at maaari itong mangolekta ng paunang detalye o mag-ayos ng follow-up sa tao.",
        )
        return translated
    if language == "indonesian":
        translated = answer.replace(
            "The requested loan rates, fees, eligibility, or approvals are unavailable in the demo knowledge base.",
            "Informasi rate pinjaman, biaya, kelayakan, atau approval yang diminta tidak tersedia di basis pengetahuan demo.",
        )
        translated = translated.replace(
            "This system supports synthetic, non-binding guidance only and can collect preliminary details or arrange a human follow-up.",
            "Sistem ini hanya mendukung panduan demo sintetis yang tidak mengikat dan dapat mengumpulkan detail awal atau menghubungkan ke manusia untuk follow-up.",
        )
        return translated
    return answer


def localize_response_text(status: str, answer: str, language: str) -> str:
    if language == "english":
        return answer

    if status == "greeting":
        if language in {"filipino", "taglish"}:
            return "Kamusta! Ako si Loanova. Maaari kong sagutin ang mga tanong tungkol sa produkto, proseso ng preliminary qualification, o ikonekta ka sa isang human specialist kung kailangan."
        if language == "indonesian":
            return "Halo! Saya Loanova. Saya bisa menjawab pertanyaan tentang produk, menjelaskan proses kualifikasi awal, atau menghubungkan Anda dengan human specialist jika diperlukan."
        return answer

    if status == "unsupported_question":
        return _localize_unsupported_answer(language, answer)

    if status in {"knowledge_answer", "missing_fields", "conflict", "ready_for_review", "objection", "escalated"}:
        if language in {"filipino", "taglish"}:
            if "kamusta" not in answer.lower() and "loanova" not in answer.lower():
                return f"Kamusta! {answer}"
            return answer
        if language == "indonesian":
            if "halo" not in answer.lower() and "loanova" not in answer.lower():
                return f"Halo! {answer}"
            return answer
    return answer
