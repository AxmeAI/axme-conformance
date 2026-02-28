from __future__ import annotations

import json
from uuid import uuid4

import httpx

from conformance import run_contract_suite


def test_run_contract_suite_happy_path() -> None:
    idempotency_cache: dict[str, tuple[str, str]] = {}
    thread_id = "11111111-1111-4111-8111-111111111111"
    intent_id = "22222222-2222-4222-8222-222222222222"
    event_id = "33333333-3333-4333-8333-333333333333"
    subscription_id = "44444444-4444-4444-8444-444444444444"

    thread_payload = {
        "thread_id": thread_id,
        "intent_id": intent_id,
        "status": "active",
        "owner_agent": "agent://conformance/owner",
        "from_agent": "agent://conformance/sender",
        "to_agent": "agent://conformance/receiver",
        "created_at": "2026-02-28T00:00:00Z",
        "updated_at": "2026-02-28T00:00:01Z",
        "timeline": [
            {
                "event_id": event_id,
                "event_type": "message.sent",
                "actor": "gateway",
                "at": "2026-02-28T00:00:01Z",
                "details": {"message": "ok"},
            }
        ],
    }
    changes_payload = {
        "ok": True,
        "changes": [
            {
                "cursor": "cur-1",
                "thread": thread_payload,
            }
        ],
        "next_cursor": "cur-2",
        "has_more": True,
    }
    changes_follow_up_payload = {
        "ok": True,
        "changes": [],
        "next_cursor": None,
        "has_more": False,
    }
    webhook_subscription = {
        "subscription_id": subscription_id,
        "owner_agent": "agent://conformance/owner",
        "callback_url": "https://integrator.example/webhooks/axme",
        "event_types": ["inbox.thread_created"],
        "active": True,
        "description": "conformance subscription",
        "created_at": "2026-02-28T00:00:00Z",
        "updated_at": "2026-02-28T00:00:01Z",
        "revoked_at": None,
        "secret_hint": "****hint",
    }
    webhook_event_response = {
        "ok": True,
        "accepted_at": "2026-02-28T00:00:01Z",
        "event_type": "inbox.thread_created",
        "source": "conformance",
        "owner_agent": "agent://conformance/owner",
        "event_id": event_id,
        "queued_deliveries": 1,
        "processed_deliveries": 1,
        "delivered": 1,
        "pending": 0,
        "dead_lettered": 0,
    }
    webhook_replay_response = {
        "ok": True,
        "event_id": event_id,
        "owner_agent": "agent://conformance/owner",
        "event_type": "inbox.thread_created",
        "queued_deliveries": 1,
        "processed_deliveries": 1,
        "delivered": 1,
        "pending": 0,
        "dead_lettered": 0,
        "replayed_at": "2026-02-28T00:00:02Z",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            trace_id = request.headers.get("x-trace-id")
            if trace_id is not None:
                assert isinstance(trace_id, str) and len(trace_id) > 0
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
                new_intent_id = str(uuid4())
                idempotency_cache[idempotency_key] = (payload_signature, new_intent_id)
                return httpx.Response(200, json={"intent_id": new_intent_id})
            return httpx.Response(200, json={"intent_id": str(uuid4())})
        if request.url.path == "/v1/inbox":
            assert request.url.params.get("owner_agent") == "agent://conformance/owner"
            return httpx.Response(200, json={"ok": True, "threads": [thread_payload]})
        if request.url.path == f"/v1/inbox/{thread_id}/reply":
            assert request.url.params.get("owner_agent") == "agent://conformance/owner"
            body = json.loads(request.content.decode("utf-8"))
            assert body["message"] == "ack from conformance"
            return httpx.Response(200, json={"ok": True, "thread": thread_payload})
        if request.url.path == "/v1/inbox/changes":
            assert request.url.params.get("owner_agent") == "agent://conformance/owner"
            if request.url.params.get("cursor") == "cur-2":
                return httpx.Response(200, json=changes_follow_up_payload)
            return httpx.Response(200, json=changes_payload)
        if request.url.path == "/v1/webhooks/subscriptions" and request.method == "POST":
            return httpx.Response(200, json={"ok": True, "subscription": webhook_subscription})
        if request.url.path == "/v1/webhooks/subscriptions" and request.method == "GET":
            assert request.url.params.get("owner_agent") == "agent://conformance/owner"
            return httpx.Response(200, json={"ok": True, "subscriptions": [webhook_subscription]})
        if request.url.path == f"/v1/webhooks/subscriptions/{subscription_id}" and request.method == "DELETE":
            assert request.url.params.get("owner_agent") == "agent://conformance/owner"
            return httpx.Response(
                200,
                json={"ok": True, "subscription_id": subscription_id, "revoked_at": "2026-02-28T00:00:03Z"},
            )
        if request.url.path == "/v1/webhooks/events" and request.method == "POST":
            assert request.url.params.get("owner_agent") == "agent://conformance/owner"
            return httpx.Response(200, json=webhook_event_response)
        if request.url.path == f"/v1/webhooks/events/{event_id}/replay" and request.method == "POST":
            assert request.url.params.get("owner_agent") == "agent://conformance/owner"
            return httpx.Response(200, json=webhook_replay_response)
        return httpx.Response(404, json={"error": "not_found"})

    results = run_contract_suite(
        base_url="https://api.axme.test",
        api_key="token",
        transport_factory=lambda: httpx.MockTransport(handler),
    )
    assert len(results) == 9
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
    assert len(results) == 9
    assert not results[0].passed
    assert not results[1].passed
    assert not results[2].passed
    assert not results[3].passed
    assert not results[4].passed
    assert not results[5].passed
    assert not results[6].passed
    assert not results[7].passed
    assert not results[8].passed
