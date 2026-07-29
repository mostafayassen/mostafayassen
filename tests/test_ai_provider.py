"""Unit tests for app/integrations/ai_provider.py.

These deliberately don't require a real Ollama server: they run against a
host with nothing listening (a closed local port), which is the expected
situation in this sandbox and on a fresh install before the user has set
up Ollama. The point of these tests is to verify the "fail gracefully,
never raise" contract described in ai_provider.py's docstring.

If you *do* have Ollama running locally with the default model pulled,
test_live_ollama_if_available below will also exercise a real call; it
skips itself otherwise.
"""

from __future__ import annotations

from app.integrations.ai_provider import (
    AIResult,
    OllamaProvider,
    UNAVAILABLE_MESSAGE,
)
from app.models import Task

# A host guaranteed to refuse the connection immediately (no server there).
UNREACHABLE_HOST = "http://127.0.0.1:1"


def test_is_available_false_when_no_server():
    provider = OllamaProvider(host=UNREACHABLE_HOST)
    assert provider.is_available() is False


def test_summarize_email_fails_gracefully_without_server():
    provider = OllamaProvider(host=UNREACHABLE_HOST)
    result = provider.summarize_email("Meeting notes", "Please send the report by Friday.")
    assert isinstance(result, AIResult)
    assert result.ok is False
    assert "Ollama" in (result.error or "")


def test_suggest_quadrant_fails_gracefully_without_server():
    provider = OllamaProvider(host=UNREACHABLE_HOST)
    result = provider.suggest_quadrant("Fix production bug", "Customers affected now")
    assert result.ok is False
    assert result.error


def test_smart_reminder_text_fails_gracefully_without_server():
    provider = OllamaProvider(host=UNREACHABLE_HOST)
    task = Task(title="Submit expense report", deadline="2026-08-01T17:00:00")
    result = provider.smart_reminder_text(task)
    assert result.ok is False
    assert result.error


def test_live_ollama_if_available():
    """Best-effort live check: only runs real assertions if a local Ollama
    server is actually reachable (unlikely in this sandbox), otherwise it
    documents the skip and passes trivially."""
    provider = OllamaProvider()
    if not provider.is_available():
        import pytest

        pytest.skip("No local Ollama server running -- skipping live AI test.")
    result = provider.suggest_quadrant("Reply to urgent client escalation")
    assert isinstance(result, AIResult)
