"""Provider boundary and deterministic local test adapter; no network clients live here."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ProviderAvailability:
    provider_id: str
    status: str
    configured: bool
    network_enabled: bool
    operational: bool


@dataclass(frozen=True)
class ProviderRequest:
    provider_id: str
    prompt: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class CostEstimate:
    amount_cents: int
    currency: str
    basis: str
    simulated: bool


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    source: str
    is_fixture: bool
    cost: CostEstimate


class ProviderError(RuntimeError):
    """Typed provider boundary error; real adapters should subclass this."""


class ProviderNotReady(ProviderError):
    pass


class ProviderAdapter(Protocol):
    """Version-1 provider contract; production implementations remain future work."""

    contract_version: str

    def availability(self) -> ProviderAvailability: ...
    def validate_configuration(self, configuration: dict[str, Any]) -> bool: ...
    def prepare_request(self, prompt: str, metadata: dict[str, Any] | None = None) -> ProviderRequest: ...
    def estimate_cost(self, request: ProviderRequest) -> CostEstimate: ...
    def execute(self, request: ProviderRequest) -> ProviderResponse: ...
    def cancel(self, request_id: str) -> bool: ...


class WaitingProvider:
    """Placeholder for a real provider: never claims to be connected or calls a network."""

    contract_version = "1"

    def __init__(self, provider_id: str):
        self.provider_id = provider_id

    def availability(self) -> ProviderAvailability:
        return ProviderAvailability(self.provider_id, "WAITING_FOR_PROVIDER", False, False, False)

    def validate_configuration(self, configuration: dict[str, Any]) -> bool:
        return False

    def prepare_request(self, prompt: str, metadata: dict[str, Any] | None = None) -> ProviderRequest:
        raise ProviderNotReady("provider is not configured; request was not prepared")

    def estimate_cost(self, request: ProviderRequest) -> CostEstimate:
        raise ProviderNotReady("provider is not configured; no cost estimate is available")

    def execute(self, request: ProviderRequest) -> ProviderResponse:
        raise ProviderNotReady("provider is not configured; no external call was made")

    def cancel(self, request_id: str) -> bool:
        return False


class FixtureProvider:
    """Deterministic test fixture. Available to tests only; never a live provider."""

    contract_version = "1"

    def __init__(self, provider_id: str = "fixture-local", response_text: str = "FIXTURE: deterministic test response"):
        self.provider_id = provider_id
        self.response_text = response_text

    def availability(self) -> ProviderAvailability:
        return ProviderAvailability(self.provider_id, "FIXTURE_ONLY", True, False, False)

    def validate_configuration(self, configuration: dict[str, Any]) -> bool:
        return configuration == {"mode": "fixture"}

    def prepare_request(self, prompt: str, metadata: dict[str, Any] | None = None) -> ProviderRequest:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt is required")
        return ProviderRequest(self.provider_id, prompt.strip(), dict(metadata or {}))

    def estimate_cost(self, request: ProviderRequest) -> CostEstimate:
        self._validate_request(request)
        return CostEstimate(0, "USD", "FIXTURE_ZERO_COST", True)

    def execute(self, request: ProviderRequest) -> ProviderResponse:
        self._validate_request(request)
        return ProviderResponse(self.response_text, "LOCAL_FIXTURE", True, self.estimate_cost(request))

    def cancel(self, request_id: str) -> bool:
        # The synchronous fixture finishes immediately; there is no live task to cancel.
        return False

    def _validate_request(self, request: ProviderRequest) -> None:
        if request.provider_id != self.provider_id:
            raise ProviderError("request belongs to a different provider")
