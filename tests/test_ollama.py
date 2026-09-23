"""Verify real model transport contracts without pretending mocks are live inference."""

import json

import httpx2

from acg_agent_platform.models.records import Classification
from acg_agent_platform.models.workflow import Envelope, Language, Stage
from acg_agent_platform.services.ollama import OllamaModel


def test_adapter_requests_structured_real_inference() -> None:
    def respond(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        assert request.url.path == "/api/chat"
        assert body["stream"] is False
        assert body["model"] == "qwen2.5:1.5b"
        assert "format" in body
        assert "tools" not in body
        return httpx2.Response(
            200, json={"done": True, "message": {"content": '{"category":"vpn"}'}}
        )

    adapter = OllamaModel(
        "http://127.0.0.1:11435",
        "qwen2.5:1.5b",
        transport=httpx2.MockTransport(respond),
    )
    result = adapter.infer(
        Envelope(
            stage=Stage.CLASSIFY,
            language=Language.EN,
            text="VPN error 809",
            classification=Classification.INTERNAL,
        )
    )
    assert json.loads(result) == {"category": "vpn"}
    assert adapter.name == "ollama/qwen2.5:1.5b"
