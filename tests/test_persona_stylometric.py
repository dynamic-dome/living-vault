"""Tests for the deterministic stylometric extractor.

extract_stylometric(body: str) -> dict must produce the exact field set
the Phase-9 spec lists, with sane defaults for edge cases.
"""
from __future__ import annotations
import pytest

from living_vault.core.voice.stylometric import extract_stylometric


REQUIRED_FIELDS = {
    "avg_sentence_length",
    "sentence_length_stddev",
    "question_rate",
    "exclamation_rate",
    "first_person_rate",
    "second_person_rate",
    "preferred_separator",
    "list_density",
    "code_density",
    "wikilink_density",
    "top_phrases",
    "register",
}


def test_returns_all_required_fields_for_simple_body():
    body = "This is a test. It has two sentences."
    out = extract_stylometric(body)
    assert set(out.keys()) == REQUIRED_FIELDS


def test_avg_sentence_length_is_in_words():
    body = "One two three four five. Six seven eight."
    out = extract_stylometric(body)
    # Sentence 1 has 5 words, sentence 2 has 3 words. Avg = 4.0
    assert out["avg_sentence_length"] == pytest.approx(4.0, abs=0.01)


def test_question_rate_counts_question_marks():
    body = "Statement one. Question one? Question two? Statement two."
    out = extract_stylometric(body)
    assert out["question_rate"] == pytest.approx(0.5, abs=0.01)


def test_first_person_rate_de_and_en():
    body = (
        "Ich denke das ist richtig. "
        "Wir sehen es so. "
        "I believe so. "
        "It is what it is."
    )
    out = extract_stylometric(body)
    # 3 of 4 sentences contain ich/wir/I/we
    assert out["first_person_rate"] == pytest.approx(0.75, abs=0.01)


def test_preferred_separator_picks_em_dash_when_dominant():
    body = "Eins — zwei. Drei — vier. Fünf, sechs."
    out = extract_stylometric(body)
    assert out["preferred_separator"] == "—"


def test_list_density_sees_markdown_lists():
    body = (
        "Intro paragraph. Another sentence here.\n"
        "\n"
        "- item one\n"
        "- item two\n"
        "- item three\n"
    )
    out = extract_stylometric(body)
    # 3 of 5 lines are list lines (content lines, not blank)
    assert out["list_density"] > 0.4
    assert out["list_density"] <= 1.0


def test_code_density_sees_fenced_blocks():
    body = (
        "Text before.\n"
        "```python\n"
        "def x(): return 1\n"
        "```\n"
        "Text after."
    )
    out = extract_stylometric(body)
    assert out["code_density"] > 0.0
    assert out["code_density"] <= 1.0


def test_top_phrases_excludes_stopwords_and_returns_at_most_five():
    body = (
        "in der praxis funktioniert das. "
        "in der praxis sehen wir das oft. "
        "siehe auch die referenz. "
        "siehe auch den beweis."
    )
    out = extract_stylometric(body)
    phrases = out["top_phrases"]
    assert isinstance(phrases, list)
    assert len(phrases) <= 5
    assert any("praxis" in p for p in phrases) or any("siehe auch" in p for p in phrases)


def test_register_classifies_german_informal():
    body = "Du machst das so wie ich es dir gesagt habe. Wir sehen das gleich."
    out = extract_stylometric(body)
    assert out["register"] == "informal-de"


def test_empty_body_returns_zeroed_defaults_no_crash():
    out = extract_stylometric("")
    assert out["avg_sentence_length"] == 0.0
    assert out["question_rate"] == 0.0
    assert out["top_phrases"] == []
    assert out["register"] in {"informal-de", "formal-de", "english", "mixed", "unknown"}


def test_single_sentence_no_separator_does_not_crash():
    out = extract_stylometric("Hello world")
    assert out["preferred_separator"] in {"—", ":", ";", ",", ""}


def test_pure_code_body_has_nonzero_code_density():
    """Regression: early-return path used to silently return code_density=0.0 for
    pure-code bodies (no prose sentences). After fix, code_density reflects truth."""
    body = "```python\ndef x(): return 1\n```"
    out = extract_stylometric(body)
    assert out["code_density"] > 0.0
    assert out["avg_sentence_length"] == 0.0  # still no sentences
