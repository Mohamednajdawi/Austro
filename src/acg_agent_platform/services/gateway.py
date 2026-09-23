"""Enforce payload policy around every injected model invocation."""

import json
import tomllib
from abc import ABC, abstractmethod
from importlib.resources import files

from acg_agent_platform.models.records import Classification
from acg_agent_platform.models.workflow import Envelope, Stage


class PolicyDenied(Exception):
    """Payload processing is prohibited by policy."""


class BasePolicy(ABC):
    @abstractmethod
    def inspect(self, envelope: Envelope) -> None:
        """Raise if any part of the envelope cannot be processed."""


class InternalOnlyPolicy(BasePolicy):
    def __init__(self, max_chars: int) -> None:
        self.max_chars = max_chars

    def inspect(self, envelope: Envelope) -> None:
        if envelope.classification != Classification.INTERNAL:
            raise PolicyDenied
        if len(envelope.text) > self.max_chars:
            raise PolicyDenied


class BaseModelAdapter(ABC):
    name: str

    @abstractmethod
    def infer(self, envelope: Envelope) -> str:
        """Return untrusted structured model output without executing tools."""


class FakeModel(BaseModelAdapter):
    name = "fake/deterministic-v1"

    def __init__(self) -> None:
        resource = files("acg_agent_platform").joinpath("resources/prompts.toml")
        self.prompts = tomllib.loads(resource.read_text(encoding="utf-8"))

    def infer(self, envelope: Envelope) -> str:
        if envelope.stage == Stage.CLASSIFY:
            category = "vpn" if "vpn" in envelope.text.casefold() else "unknown"
            return json.dumps({"category": category})
        return json.dumps({"draft": self.prompts[envelope.language.value]})


class ModelGateway:
    def __init__(self, model: BaseModelAdapter, policy: BasePolicy) -> None:
        self.model = model
        self.policy = policy
        self.calls = 0

    def invoke(self, envelope: Envelope) -> str:
        self.policy.inspect(envelope)
        self.calls += 1
        output = self.model.infer(envelope)
        self.policy.inspect(envelope.model_copy(update={"text": output}))
        return output
