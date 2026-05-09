"""Deterministic stylometric features extracted from a markdown body.

No DB access, no API calls. Stop-word lists are hardcoded — German + English.
"""
from __future__ import annotations
import re
import statistics
from collections import Counter

# Deutsche + englische stopwords. Hand-picked, ~250 entries.
_STOPWORDS: frozenset[str] = frozenset({
    # german
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "eines",
    "einem", "einen", "und", "oder", "aber", "nicht", "kein", "keine", "ist",
    "sind", "war", "waren", "wird", "werde", "werden", "wurde", "wurden",
    "hat", "habe", "haben", "hatte", "hatten", "kann", "kannst", "kannte",
    "können", "konnte", "konnten", "muss", "musst", "müssen", "sollte",
    "sollten", "soll", "sollen", "will", "willst", "wollen", "wollte",
    "wollten", "mag", "magst", "mögen", "mochte", "ich", "du", "er", "sie",
    "es", "wir", "ihr", "mich", "dich", "mir", "dir", "uns", "euch", "ihm",
    "ihn", "sich", "mein", "meine", "dein", "deine", "sein", "seine", "unser",
    "unsere", "euer", "eure", "in", "im", "an", "am", "auf", "aus", "bei",
    "von", "zu", "zur", "zum", "mit", "nach", "durch", "für", "gegen", "ohne",
    "um", "über", "unter", "vor", "hinter", "neben", "zwischen", "wenn",
    "dass", "weil", "denn", "als", "wie", "wo", "was", "warum", "wer", "wem",
    "wen", "welche", "welcher", "welches", "wieder", "noch", "schon", "auch",
    "so", "doch", "nur", "mehr", "sehr", "etwas", "alles", "nichts", "viel",
    "wenig", "andere", "anderen", "wenig", "genug", "ja", "nein", "vielleicht",
    # english
    "the", "a", "an", "and", "or", "but", "not", "no", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "having", "do",
    "does", "did", "doing", "will", "would", "could", "should", "may",
    "might", "must", "can", "shall", "i", "you", "he", "she", "it", "we",
    "they", "me", "him", "her", "us", "them", "my", "your", "his", "its",
    "our", "their", "this", "that", "these", "those", "what", "which", "who",
    "whom", "whose", "where", "when", "why", "how", "if", "while", "for",
    "of", "in", "on", "at", "to", "from", "by", "with", "about", "against",
    "between", "into", "through", "during", "before", "after", "above",
    "below", "up", "down", "out", "off", "over", "under", "again", "further",
    "then", "once", "here", "there", "all", "any", "both", "each", "few",
    "more", "most", "other", "some", "such", "only", "same", "than", "too",
    "very", "just", "much", "now", "yes", "okay", "ok",
})


_FIRST_PERSON_TOKENS = {
    "ich", "wir", "mein", "meine", "meinen", "meinem", "meiner",
    "unser", "unsere", "unserem", "unseren", "unseres",
    "i", "we", "my", "our", "mine", "ours", "me", "us",
}
_SECOND_PERSON_TOKENS = {
    "du", "ihr", "dein", "deine", "deinen", "deinem", "deiner",
    "euer", "eure", "euren", "eurem", "eurer",
    "sie",  # Anrede capitalised, but lowercased here — false positives possible, see register
    "you", "your", "yours",
}

_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"\b\w+\b", flags=re.UNICODE)
_FENCED_BLOCK_RE = re.compile(r"```.*?```", flags=re.DOTALL)
_LIST_LINE_RE = re.compile(r"^\s*([-*+]|\d+\.)\s+", flags=re.MULTILINE)
_WIKILINK_RE = re.compile(r"\[\[[^\]]+\]\]")
_BODY_CAP = 20_000  # paranoia for huge pages


def _truncate_body(body: str) -> str:
    if len(body) <= _BODY_CAP:
        return body
    return body[:_BODY_CAP]


def _strip_markdown_for_sentences(body: str) -> str:
    """Remove fenced code blocks before sentence splitting (they distort stats)."""
    return _FENCED_BLOCK_RE.sub(" ", body)


def _split_sentences(body: str) -> list[str]:
    if not body.strip():
        return []
    return [s for s in _SENTENCE_BOUNDARY_RE.split(body.strip()) if s.strip()]


def _classify_register(body: str) -> str:
    """Heuristic. Crude but useful. Order: empty → english → mixed → de-formal/informal."""
    if not body.strip():
        return "unknown"
    tokens = [t.lower() for t in _WORD_RE.findall(body)]
    if not tokens:
        return "unknown"
    de_marker = {"der", "die", "das", "und", "ist", "ich", "nicht", "auch"}
    en_marker = {"the", "and", "is", "not", "i", "of", "to"}
    de_hits = sum(1 for t in tokens if t in de_marker)
    en_hits = sum(1 for t in tokens if t in en_marker)
    total = len(tokens) or 1
    de_ratio = de_hits / total
    en_ratio = en_hits / total
    # english if english-marker dominant
    if en_ratio > 0.05 and en_ratio > de_ratio * 1.5:
        return "english"
    # mixed if both meaningful
    if de_ratio > 0.02 and en_ratio > 0.02 and abs(de_ratio - en_ratio) < 0.02:
        return "mixed"
    if de_ratio > 0.02:
        # informal vs formal — naive: presence of "du" / "ihr" → informal
        if any(t in {"du", "dich", "dir", "dein", "deine", "ihr", "euch", "euer"} for t in tokens):
            return "informal-de"
        # capitalised "Sie" survives only at sentence start in lowercased tokens, so ignore
        return "formal-de"
    return "unknown"


def _top_phrases(body: str, n: int = 5) -> list[str]:
    """5 most-frequent 2-3-token n-grams excluding stopword-only ones."""
    tokens = [t.lower() for t in _WORD_RE.findall(body)]
    if len(tokens) < 2:
        return []
    bigrams = [" ".join(tokens[i : i + 2]) for i in range(len(tokens) - 1)]
    trigrams = [" ".join(tokens[i : i + 3]) for i in range(len(tokens) - 2)]
    candidates = bigrams + trigrams
    # filter: drop n-grams where ALL tokens are stopwords
    keep = []
    for ng in candidates:
        toks = ng.split()
        if all(t in _STOPWORDS for t in toks):
            continue
        if any(len(t) < 3 for t in toks):
            continue
        keep.append(ng)
    counts = Counter(keep)
    return [ng for ng, _ in counts.most_common(n)]


def _preferred_separator(body: str) -> str:
    if not body:
        return ""
    seps = {sep: body.count(sep) for sep in ("—", ":", ";", ",")}
    # only consider separators that occur at all
    seps = {s: c for s, c in seps.items() if c > 0}
    if not seps:
        return ""
    return max(seps.items(), key=lambda kv: kv[1])[0]


def extract_stylometric(body: str) -> dict:
    """Compute the full stylometric feature dict from a markdown body.

    Always returns the same key set. Empty/short bodies get sane zeros.
    """
    body = _truncate_body(body or "")
    body_for_sentences = _strip_markdown_for_sentences(body)
    sentences = _split_sentences(body_for_sentences)
    n_sentences = len(sentences)

    if n_sentences == 0:
        return {
            "avg_sentence_length": 0.0,
            "sentence_length_stddev": 0.0,
            "question_rate": 0.0,
            "exclamation_rate": 0.0,
            "first_person_rate": 0.0,
            "second_person_rate": 0.0,
            "preferred_separator": "",
            "list_density": 0.0,
            "code_density": 0.0,
            "wikilink_density": 0.0,
            "top_phrases": [],
            "register": _classify_register(body),
        }

    sentence_word_counts = [len(_WORD_RE.findall(s)) for s in sentences]
    avg = sum(sentence_word_counts) / n_sentences
    stddev = statistics.pstdev(sentence_word_counts) if n_sentences > 1 else 0.0

    q_rate = sum(1 for s in sentences if s.rstrip().endswith("?")) / n_sentences
    e_rate = sum(1 for s in sentences if s.rstrip().endswith("!")) / n_sentences

    def has_token(s: str, vocab: set[str]) -> bool:
        toks = {t.lower() for t in _WORD_RE.findall(s)}
        return bool(toks & vocab)

    fp_rate = sum(1 for s in sentences if has_token(s, _FIRST_PERSON_TOKENS)) / n_sentences
    sp_rate = sum(1 for s in sentences if has_token(s, _SECOND_PERSON_TOKENS)) / n_sentences

    # list_density: fraction of non-blank lines that are list lines
    lines = [ln for ln in body.splitlines() if ln.strip()]
    list_lines = sum(1 for ln in lines if _LIST_LINE_RE.match(ln))
    list_density = (list_lines / len(lines)) if lines else 0.0

    # code_density: fraction of body chars inside fenced blocks
    code_chars = sum(len(m.group(0)) for m in _FENCED_BLOCK_RE.finditer(body))
    code_density = (code_chars / len(body)) if body else 0.0

    # wikilink_density: count per 100 words
    n_words = sum(sentence_word_counts) or 1
    wl_count = len(_WIKILINK_RE.findall(body))
    wl_density = (wl_count / n_words) * 100 if n_words else 0.0

    return {
        "avg_sentence_length": round(avg, 2),
        "sentence_length_stddev": round(stddev, 2),
        "question_rate": round(q_rate, 3),
        "exclamation_rate": round(e_rate, 3),
        "first_person_rate": round(fp_rate, 3),
        "second_person_rate": round(sp_rate, 3),
        "preferred_separator": _preferred_separator(body),
        "list_density": round(list_density, 3),
        "code_density": round(code_density, 3),
        "wikilink_density": round(wl_density, 3),
        "top_phrases": _top_phrases(body),
        "register": _classify_register(body),
    }
