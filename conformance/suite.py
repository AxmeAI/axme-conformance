from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import httpx


@dataclass(frozen=True)
class ContractResult:
    name: str
    passed: bool
    details: str


def run_contract_suite(
    *,
    base_url: str,
    api_key: str,
    transport_factory: Callable[[], httpx.BaseTransport] | None = None,
) -> list[ContractResult]:
    transport = transport_factory() if transport_factory else None
    client = httpx.Client(
        base_url=base_url.rstrip("/"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        transport=transport,
        timeout=15.0,
    )
    try:
        return [
            _check_health_contract(client),
            _check_intent_create_contract(client),
        ]
    finally:
        client.close()


def _check_health_contract(client: httpx.Client) -> ContractResult:
    response = client.get("/health")
    if response.status_code != 200:
        return ContractResult("health", False, f"unexpected status={response.status_code}")
    data = response.json()
    if "ok" not in data:
        return ContractResult("health", False, "missing field: ok")
    return ContractResult("health", True, "ok")


def _check_intent_create_contract(client: httpx.Client) -> ContractResult:
    response = client.post(
        "/v1/intents",
        json={"intent_type": "notify", "recipient": "agent://user/conformance"},
    )
    if response.status_code != 200:
        return ContractResult("intent_create", False, f"unexpected status={response.status_code}")
    data = response.json()
    if "intent_id" not in data:
        return ContractResult("intent_create", False, "missing field: intent_id")
    return ContractResult("intent_create", True, "ok")
