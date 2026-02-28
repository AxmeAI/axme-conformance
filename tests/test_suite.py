from __future__ import annotations

import httpx

from conformance import run_contract_suite


def test_run_contract_suite_happy_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/v1/intents":
            return httpx.Response(200, json={"intent_id": "it_contract"})
        return httpx.Response(404, json={"error": "not_found"})

    results = run_contract_suite(
        base_url="https://api.axme.test",
        api_key="token",
        transport_factory=lambda: httpx.MockTransport(handler),
    )
    assert len(results) == 2
    assert all(r.passed for r in results)


def test_run_contract_suite_reports_failures() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(500, json={"error": "down"})
        if request.url.path == "/v1/intents":
            return httpx.Response(200, json={"missing": "intent_id"})
        return httpx.Response(404, json={"error": "not_found"})

    results = run_contract_suite(
        base_url="https://api.axme.test",
        api_key="token",
        transport_factory=lambda: httpx.MockTransport(handler),
    )
    assert len(results) == 2
    assert not results[0].passed
    assert not results[1].passed
