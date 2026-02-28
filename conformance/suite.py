from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4
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
            _check_intent_create_idempotency_contract(client),
            _check_inbox_list_contract(client),
            _check_inbox_reply_contract(client),
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
    correlation_id = str(uuid4())
    response = client.post("/v1/intents", json=_build_intent_create_payload(correlation_id=correlation_id))
    if response.status_code != 200:
        return ContractResult("intent_create", False, f"unexpected status={response.status_code}")
    data = response.json()
    if "intent_id" not in data:
        return ContractResult("intent_create", False, "missing field: intent_id")
    if not _is_uuid(data["intent_id"]):
        return ContractResult("intent_create", False, "intent_id is not UUID")
    return ContractResult("intent_create", True, "ok")


def _check_intent_create_idempotency_contract(client: httpx.Client) -> ContractResult:
    correlation_id = str(uuid4())
    idempotency_key = f"cf-{uuid4()}"
    payload = _build_intent_create_payload(correlation_id=correlation_id)

    first = client.post("/v1/intents", json=payload, headers={"Idempotency-Key": idempotency_key})
    if first.status_code != 200:
        return ContractResult("intent_create_idempotency", False, f"first status={first.status_code}")

    first_data = first.json()
    first_intent_id = first_data.get("intent_id")
    if first_intent_id is None:
        return ContractResult("intent_create_idempotency", False, "missing field: intent_id")
    if not _is_uuid(first_intent_id):
        return ContractResult("intent_create_idempotency", False, "intent_id is not UUID")

    second = client.post("/v1/intents", json=payload, headers={"Idempotency-Key": idempotency_key})
    if second.status_code != 200:
        return ContractResult("intent_create_idempotency", False, f"repeat status={second.status_code}")

    second_data = second.json()
    if second_data.get("intent_id") != first_intent_id:
        return ContractResult("intent_create_idempotency", False, "idempotent replay returned different intent_id")

    mutated_payload = dict(payload)
    mutated_payload["payload"] = {"text": "different body", "priority": "high"}
    conflict = client.post(
        "/v1/intents",
        json=mutated_payload,
        headers={"Idempotency-Key": idempotency_key},
    )
    if conflict.status_code != 409:
        return ContractResult("intent_create_idempotency", False, f"expected conflict status=409 got={conflict.status_code}")

    return ContractResult("intent_create_idempotency", True, "ok")


def _check_inbox_list_contract(client: httpx.Client) -> ContractResult:
    response = client.get("/v1/inbox", params={"owner_agent": "agent://conformance/owner"})
    if response.status_code != 200:
        return ContractResult("inbox_list", False, f"unexpected status={response.status_code}")
    data = response.json()
    if data.get("ok") is not True:
        return ContractResult("inbox_list", False, "missing or invalid field: ok")
    threads = data.get("threads")
    if not isinstance(threads, list):
        return ContractResult("inbox_list", False, "missing or invalid field: threads")
    if threads and not _is_thread_shape(threads[0]):
        return ContractResult("inbox_list", False, "invalid thread shape")
    return ContractResult("inbox_list", True, "ok")


def _check_inbox_reply_contract(client: httpx.Client) -> ContractResult:
    owner_agent = "agent://conformance/owner"
    thread_id = str(uuid4())

    list_response = client.get("/v1/inbox", params={"owner_agent": owner_agent})
    if list_response.status_code == 200:
        list_data = list_response.json()
        threads = list_data.get("threads")
        if isinstance(threads, list) and threads:
            candidate_id = threads[0].get("thread_id")
            if _is_uuid(candidate_id):
                thread_id = candidate_id

    reply_response = client.post(
        f"/v1/inbox/{thread_id}/reply",
        params={"owner_agent": owner_agent},
        json={"message": "ack from conformance"},
    )
    if reply_response.status_code != 200:
        return ContractResult("inbox_reply", False, f"unexpected status={reply_response.status_code}")
    data = reply_response.json()
    if data.get("ok") is not True:
        return ContractResult("inbox_reply", False, "missing or invalid field: ok")
    thread = data.get("thread")
    if not _is_thread_shape(thread):
        return ContractResult("inbox_reply", False, "invalid thread shape")
    if thread.get("thread_id") != thread_id:
        return ContractResult("inbox_reply", False, "thread_id mismatch in reply response")
    return ContractResult("inbox_reply", True, "ok")


def _build_intent_create_payload(*, correlation_id: str) -> dict[str, object]:
    return {
        "intent_type": "notify.message.v1",
        "correlation_id": correlation_id,
        "from_agent": "agent://conformance/sender",
        "to_agent": "agent://conformance/receiver",
        "payload": {"text": "hello from conformance"},
    }


def _is_thread_shape(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    required_keys = {
        "thread_id",
        "intent_id",
        "status",
        "owner_agent",
        "from_agent",
        "to_agent",
        "created_at",
        "updated_at",
        "timeline",
    }
    if not required_keys.issubset(value.keys()):
        return False
    if not _is_uuid(value.get("thread_id")):
        return False
    if not _is_uuid(value.get("intent_id")):
        return False
    timeline = value.get("timeline")
    return isinstance(timeline, list) and len(timeline) >= 1


def _is_uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        UUID(value)
        return True
    except ValueError:
        return False
