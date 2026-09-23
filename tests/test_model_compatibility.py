"""Compatible transport preserves structured evidence and rejects tool calls."""

import json

import httpx2
import pytest

from acg_agent_platform.models.records import Classification
from acg_agent_platform.models.workflow import Envelope, Language, Stage
from acg_agent_platform.services.ollama import OllamaModel


def test_openai_compatible_schema_transport() -> None:
    def respond(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        assert request.url.path == "/v1/chat/completions"
        assert body["response_format"]["type"] == "json_schema"
        return httpx2.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": '{"category":"vpn"}'},
                    }
                ]
            },
        )

    adapter = OllamaModel(
        "http://127.0.0.1:11435",
        "qwen2.5:1.5b",
        openai_compatible=True,
        transport=httpx2.MockTransport(respond),
    )
    assert json.loads(
        adapter.infer(
            Envelope(
                stage=Stage.CLASSIFY,
                language=Language.EN,
                text="VPN error",
                classification=Classification.INTERNAL,
            )
        )
    ) == {"category": "vpn"}


@pytest.mark.parametrize(
    "payload",
    [
        {"choices": []},
        {"choices": [{"finish_reason": "tool_calls"}]},
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": "{}", "tool_calls": ["shell"]},
                }
            ]
        },
    ],
)
def test_unexpected_compatible_output_denied(payload) -> None:
    model = OllamaModel(
        "http://127.0.0.1:11435",
        "local",
        openai_compatible=True,
        transport=httpx2.MockTransport(lambda _: httpx2.Response(200, json=payload)),
    )
    with pytest.raises(RuntimeError):
        model.infer(
            Envelope(
                stage=Stage.CLASSIFY,
                language=Language.EN,
                text="VPN",
                classification=Classification.INTERNAL,
            )
        )
