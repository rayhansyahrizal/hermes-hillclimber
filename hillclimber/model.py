"""Model adapters for route generation."""

from collections.abc import Sequence
import re
import subprocess
from typing import Protocol


class RouteModel(Protocol):
    name: str

    def complete(self, prompt: str) -> str:
        ...


class ScriptedModel:
    """Zero-cost deterministic model used by tests and dry runs."""

    name = "scripted-local"

    def __init__(self, responses: Sequence[str]):
        self._responses = list(responses)
        self.calls = 0

    def complete(self, prompt: str) -> str:
        if self.calls >= len(self._responses):
            raise RuntimeError("scripted model has no response for this round")
        response = self._responses[self.calls]
        self.calls += 1
        return response


class HermesModel:
    """Restricted one-turn adapter to the locally configured Hermes CLI."""

    def __init__(self, *, model: str, provider: str, timeout: int = 180):
        self.model = model
        self.provider = provider
        self.timeout = timeout
        self.calls = 0
        self.name = f"{provider}/{model}"

    def complete(self, prompt: str) -> str:
        command = [
            "hermes",
            "chat",
            "--quiet",
            "--ignore-rules",
            "--max-turns",
            "1",
            "--source",
            "tool",
            "--provider",
            self.provider,
            "--model",
            self.model,
            "--query",
            prompt,
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False,
        )
        self.calls += 1
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or "Hermes CLI failed"
            raise RuntimeError(detail)
        output = completed.stdout.strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", output, re.DOTALL)
        if fenced:
            return fenced.group(1).strip()
        start, end = output.find("{"), output.rfind("}")
        if start >= 0 and end > start:
            return output[start : end + 1]
        return output
