"""Local inference with structured schemas, no tools, proxies or redirects."""

import json
import threading
import tomllib
from importlib.resources import files

import httpx2
from pydantic import BaseModel, ConfigDict, Field

from acg_agent_platform.models.workflow import (
    ClassificationResult,
    DraftResult,
    Envelope,
    Stage,
)
from acg_agent_platform.services.gateway import BaseModelAdapter


class EvidenceSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_id: str
    quote: str = Field(min_length=8, max_length=2000)


class GroundedSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    selections: list[EvidenceSelection] = Field(min_length=1, max_length=3)


class OllamaModel(BaseModelAdapter):
    def __init__(
        self,
        url: str,
        model: str,
        timeout: float = 120,
        *,
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        self.url = url.rstrip("/")
        self.model = model
        self.name = f"ollama/{model}"
        self.timeout = timeout
        self.transport = transport
        self._slots = threading.BoundedSemaphore(1)
        self.prompts = tomllib.loads(
            files("acg_agent_platform")
            .joinpath("resources/real-prompts.toml")
            .read_text(encoding="utf-8")
        )

    def available(self) -> bool:
        try:
            with httpx2.Client(
                timeout=2, trust_env=False, transport=self.transport
            ) as client:
                response = client.get(self.url + "/api/tags")
                response.raise_for_status()
                return any(
                    item.get("name") == self.model
                    for item in response.json().get("models", [])
                )
        except (httpx2.HTTPError, ValueError, TypeError, AttributeError):
            return False

    def infer(self, envelope: Envelope) -> str:
        if not self._slots.acquire(blocking=False):
            raise RuntimeError("Local model busy; retry after current run")
        try:
            schema = (
                ClassificationResult
                if envelope.stage == Stage.CLASSIFY
                else DraftResult
            ).model_json_schema()
            if envelope.stage == Stage.DRAFT:
                schema = GroundedSelection.model_json_schema()
            instructions = str(self.prompts[envelope.stage.value])
            instructions += f"\nRespond in {envelope.language.value}. JSON only."
            payload = {
                "model": self.model,
                "stream": False,
                "format": schema,
                "messages": [
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": envelope.text},
                ],
                "options": {
                    "temperature": 0,
                    "num_predict": 900,
                    "num_ctx": 8192,
                    "num_thread": 4,
                },
                "keep_alive": "5m",
            }
            with (
                httpx2.Client(
                    timeout=httpx2.Timeout(self.timeout, connect=3),
                    trust_env=False,
                    follow_redirects=False,
                    transport=self.transport,
                ) as client,
                client.stream("POST", self.url + "/api/chat", json=payload) as response,
            ):
                response.raise_for_status()
                chunks = bytearray()
                for chunk in response.iter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > 131072:
                        raise RuntimeError("Model response too large")
            data = json.loads(chunks)
            if data.get("done") is not True or data.get("done_reason") == "length":
                raise RuntimeError("Incomplete model response")
            message = data.get("message", {})
            if message.get("tool_calls") or not isinstance(message.get("content"), str):
                raise RuntimeError("Unexpected model response")
            content = str(message["content"])
            if envelope.stage == Stage.DRAFT:
                return self._grounded_note(envelope, content)
            return content
        except (httpx2.HTTPError, KeyError, TypeError, AttributeError) as exc:
            raise RuntimeError("Local inference unavailable") from exc
        finally:
            self._slots.release()

    def _grounded_note(self, envelope: Envelope, output: str) -> str:
        selection = GroundedSelection.model_validate_json(output)
        context = json.loads(envelope.text)
        ticket = json.loads(context["ticket"])
        sources = {item["id"]: item["content"] for item in context["sources"]}
        lines = []
        for item in selection.selections:
            if (
                item.source_id not in sources
                or item.quote not in sources[item.source_id]
            ):
                raise RuntimeError("Model produced unsupported evidence")
            line = f"[{item.source_id}] {item.quote}"
            if line not in lines:
                lines.append(line)
        german = envelope.language.value == "de"
        heading = (
            "Quellenbasierte Prüfschritte"
            if german
            else "Source-supported review steps"
        )
        footer = (
            "Menschliche Prüfung erforderlich. Keine Änderung ausgeführt. "
            "Ursache und Lösung sind nicht bestätigt."
            if german
            else "Human review required. No change executed. "
            "Cause and resolution are unconfirmed."
        )
        note = (
            f"Ticket: {ticket['title']}\n\n{heading}:\n"
            + "\n".join(lines)
            + "\n\n"
            + footer
        )
        return DraftResult(draft=note).model_dump_json()
