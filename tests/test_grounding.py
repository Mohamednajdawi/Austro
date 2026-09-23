"""Generated evidence must match authorized source text exactly."""

import json

import httpx2
import pytest

from acg_agent_platform.models.records import Classification
from acg_agent_platform.models.workflow import Envelope, Language, Stage
from acg_agent_platform.services.ollama import OllamaModel


@pytest.mark.parametrize(
    "source_id,quote,allowed",
    [
        ("KB-VPN", "Collect the VPN error code.", True),
        ("KB-VPN", "Restart the production server.", False),
        ("KB-SECRET", "Collect the VPN error code.", False),
    ],
)
def test_unsupported_model_quote_is_never_returned(
    source_id: str, quote: str, allowed: bool
) -> None:
    def respond(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={
                "done": True,
                "message": {
                    "content": json.dumps(
                        {"selections": [{"source_id": source_id, "quote": quote}]}
                    )
                },
            },
        )

    model = OllamaModel(
        "http://127.0.0.1:11435",
        "qwen2.5:1.5b",
        transport=httpx2.MockTransport(respond),
    )
    envelope = Envelope(
        stage=Stage.DRAFT,
        language=Language.EN,
        classification=Classification.INTERNAL,
        text=json.dumps(
            {
                "ticket": json.dumps({"title": "VPN issue"}),
                "sources": [{"id": "KB-VPN", "content": "Collect the VPN error code."}],
            }
        ),
    )
    if allowed:
        draft = json.loads(model.infer(envelope))["draft"]
        assert "[KB-VPN] Collect the VPN error code." in draft
        assert "No change executed" in draft
    else:
        with pytest.raises(RuntimeError, match="unsupported evidence"):
            model.infer(envelope)
