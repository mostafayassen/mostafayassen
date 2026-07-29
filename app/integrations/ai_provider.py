"""AI abstraction layer.

Defines a small provider interface (``AIProvider``) so the rest of the app
never talks to a specific AI backend directly. The default and only
implementation shipped in v1 is ``OllamaProvider``, which talks to a
locally-running Ollama server (https://ollama.com) over plain HTTP -- no API
key, no cost, no data leaving the user's machine.

If Ollama isn't installed/running, every method fails *gracefully*: it
returns an ``AIResult`` with ``ok=False`` and a human-readable message
instead of raising, so the UI can just show that message rather than
crashing. This also means a paid API (OpenAI, Anthropic, etc.) could be
added later as a second class implementing the same interface without
touching any calling code.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from app.models import ALL_QUADRANTS, QUADRANT_LABELS, Task

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"
REQUEST_TIMEOUT_SECONDS = 30


@dataclass
class AIResult:
    """Uniform result type returned by every AIProvider method."""

    ok: bool
    text: str = ""
    error: Optional[str] = None

    @classmethod
    def failure(cls, message: str) -> "AIResult":
        return cls(ok=False, text="", error=message)

    @classmethod
    def success(cls, text: str) -> "AIResult":
        return cls(ok=True, text=text, error=None)


class AIProvider(ABC):
    """Interface every AI backend must implement."""

    @abstractmethod
    def is_available(self) -> bool:
        """Cheap check for whether this provider can currently be used."""

    @abstractmethod
    def summarize_email(self, subject: str, body: str) -> AIResult:
        """Summarize an email and extract candidate task(s) from it."""

    @abstractmethod
    def suggest_quadrant(self, title: str, description: str = "") -> AIResult:
        """Suggest an Eisenhower quadrant for a task. text is one of
        app.models.ALL_QUADRANTS on success."""

    @abstractmethod
    def smart_reminder_text(self, task: Task) -> AIResult:
        """Generate a short, human-friendly reminder string for a task
        approaching its deadline."""


UNAVAILABLE_MESSAGE = (
    "AI features unavailable — install and run Ollama (https://ollama.com), "
    "then pull a model, e.g.:\n"
    "    ollama pull llama3.2\n"
    "See the README 'AI features (Ollama)' section for details."
)


class OllamaProvider(AIProvider):
    """Talks to a local Ollama server via its HTTP API (/api/generate).

    Uses only the standard library (urllib) so the app doesn't hard-require
    the `ollama` pip package to be installed just to check availability;
    if the `ollama` package is present we use it, otherwise we fall back to
    raw HTTP against the same local endpoint.
    """

    def __init__(self, host: str = DEFAULT_OLLAMA_HOST, model: str = DEFAULT_MODEL):
        self.host = host.rstrip("/")
        self.model = model

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.host}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _generate(self, prompt: str, system: Optional[str] = None) -> AIResult:
        if not self.is_available():
            return AIResult.failure(UNAVAILABLE_MESSAGE)

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self.host}/api/generate",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                text = body.get("response", "").strip()
                if not text:
                    return AIResult.failure(
                        "Ollama returned an empty response. Is the model "
                        f"'{self.model}' pulled? Try: ollama pull {self.model}"
                    )
                return AIResult.success(text)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return AIResult.failure(
                    f"Model '{self.model}' not found on this Ollama server. "
                    f"Run: ollama pull {self.model}"
                )
            return AIResult.failure(f"Ollama request failed (HTTP {exc.code}).")
        except urllib.error.URLError:
            return AIResult.failure(UNAVAILABLE_MESSAGE)
        except Exception as exc:  # noqa: BLE001 - AI calls must never crash the app
            return AIResult.failure(f"Unexpected AI error: {exc}")

    def summarize_email(self, subject: str, body: str) -> AIResult:
        system = (
            "You help a busy professional triage email. Read the email and "
            "produce: (1) a one-sentence summary, and (2) a bullet list of "
            "any concrete action items / tasks implied by the email, each "
            "starting with a verb. If there are no action items, say so. "
            "Be concise."
        )
        prompt = f"Subject: {subject}\n\nBody:\n{body}"
        return self._generate(prompt, system=system)

    def suggest_quadrant(self, title: str, description: str = "") -> AIResult:
        quadrant_list = ", ".join(ALL_QUADRANTS)
        system = (
            "You are a prioritization assistant using the Eisenhower matrix. "
            "Given a task title and description, decide which single "
            f"quadrant it belongs in. Reply with EXACTLY one of these "
            f"tokens and nothing else: {quadrant_list}"
        )
        prompt = f"Title: {title}\nDescription: {description}"
        result = self._generate(prompt, system=system)
        if not result.ok:
            return result

        cleaned = result.text.strip().lower().strip(".")
        for q in ALL_QUADRANTS:
            if q in cleaned:
                return AIResult.success(q)
        # Model didn't answer in the expected format -- fail gracefully
        # rather than guessing wrong silently.
        return AIResult.failure(
            "AI gave an unrecognized answer for priority suggestion: "
            f"'{result.text[:120]}'. Please pick a quadrant manually."
        )

    def smart_reminder_text(self, task: Task) -> AIResult:
        system = (
            "You write short, friendly reminder notifications (max 2 "
            "sentences) about an approaching task deadline. Be encouraging, "
            "not alarming."
        )
        quadrant_label = QUADRANT_LABELS.get(task.quadrant, task.quadrant)
        prompt = (
            f"Task: {task.title}\n"
            f"Deadline: {task.deadline}\n"
            f"Priority: {quadrant_label}\n"
            f"Status: {task.status}\n"
            f"Estimated time: {task.estimate_minutes} minutes, "
            f"time spent so far: {task.actual_minutes} minutes."
        )
        return self._generate(prompt, system=system)


def get_default_provider(host: str = DEFAULT_OLLAMA_HOST, model: str = DEFAULT_MODEL) -> AIProvider:
    """Factory used by the rest of the app. Swap this to change providers."""
    return OllamaProvider(host=host, model=model)
