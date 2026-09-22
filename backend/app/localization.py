import re
from typing import Any

LANGUAGE_ALIASES = {
    "en": "english",
    "eng": "english",
    "english": "english",
    "ph": "filipino",
    "philippines": "filipino",
    "filipino": "filipino",
    "tagalog": "filipino",
    "taglish": "taglish",
    "id": "indonesian",
    "indonesia": "indonesian",
    "bahasa indonesia": "indonesian",
    "indonesian": "indonesian",
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
    normalized = str(value).strip().lower()
    return LANGUAGE_ALIASES.get(normalized, detect_language(normalized))


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
