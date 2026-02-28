from __future__ import annotations

import json
from uuid import uuid4

import httpx

from conformance import run_contract_suite


def test_run_contract_suite_happy_path() -> None:
    idempotency_cache: dict[str, tuple[str, str]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/v1/intents":
            body = json.loads(request.content.decode("utf-8"))
            idempotency_key = request.headers.get("idempotency-key")
            if idempotency_key:
                payload_signature = json.dumps(body, sort_keys=True)
                if idempotency_key in idempotency_cache:
                    previous_signature, previous_intent_id = idempotency_cache[idempotency_key]
                    if previous_signature != payload_signature:
                        return httpx.Response(409, json={"error": "idempotency_conflict"})
                    return httpx.Response(200, json={"intent_id": previous_intent_id})
                intent_id = str(uuid4())
                idempotency_cache[idempotency_key] = (payload_signature, intent_id)
                return httpx.Response(200, json={"intent_id": intent_id})
            return httpx.Response(200, json={"intent_id": str(uuid4())})
        return httpx.Response(404, json={"error": "not_found"})

    results = run_contract_suite(
        base_url="https://api.axme.test",
        api_key="token",
        transport_factory=lambda: httpx.MockTransport(handler),
    )
    assert len(results) == 3
    assert all(r.passed for r in results)


def test_run_contract_suite_reports_failures() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(500, json={"error": "down"})
        if request.url.path == "/v1/intents":
            return httpx.Response(500, json={"error": "down"})
        return httpx.Response(404, json={"error": "not_found"})

    results = run_contract_suite(
        base_url="https://api.axme.test",
        api_key="token",
        transport_factory=lambda: httpx.MockTransport(handler),
    )
    assert len(results) == 3
    assert not results[0].passed
    assert not results[1].passed
    assert not results[2].passed
