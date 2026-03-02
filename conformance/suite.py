from __future__ import annotations

from dataclasses import dataclass
import json
from uuid import UUID, uuid4
from typing import Callable

import httpx


@dataclass(frozen=True)
class ContractResult:
    name: str
    passed: bool
    details: str


CANONICAL_INTENT_STATUSES = {
    "CREATED",
    "SUBMITTED",
    "DELIVERED",
    "ACKNOWLEDGED",
    "IN_PROGRESS",
    "WAITING",
    "COMPLETED",
    "FAILED",
    "CANCELED",
}

QUOTA_DIMENSION_KEYS = (
    "requests_per_minute",
    "intents_per_day",
    "inbox_writes_per_day",
    "media_upload_bytes_per_day",
    "media_storage_bytes",
    "webhook_deliveries_per_day",
    "schema_writes_per_day",
)


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
            _check_trace_header_contract(client),
            _check_intent_create_contract(client),
            _check_intent_create_idempotency_contract(client),
            _check_intents_get_contract(client),
            _check_intents_events_contract(client),
            _check_intents_stream_resume_contract(client),
            _check_intents_continuation_autonomy_contract(client),
            _check_intents_resolve_contract(client),
            _check_intent_completion_delivery_contract(client),
            _check_inbox_list_contract(client),
            _check_inbox_thread_contract(client),
            _check_inbox_reply_contract(client),
            _check_inbox_changes_pagination_contract(client),
            _check_inbox_delegate_contract(client),
            _check_inbox_decision_contract(client),
            _check_inbox_messages_delete_contract(client),
            _check_approvals_decision_contract(client),
            _check_capabilities_contract(client),
            _check_invites_create_contract(client),
            _check_invites_get_contract(client),
            _check_invites_accept_contract(client),
            _check_media_create_upload_contract(client),
            _check_media_get_contract(client),
            _check_media_finalize_upload_contract(client),
            _check_schemas_upsert_contract(client),
            _check_schemas_get_contract(client),
            _check_users_check_nick_contract(client),
            _check_users_register_nick_contract(client),
            _check_users_rename_nick_contract(client),
            _check_users_profile_get_contract(client),
            _check_users_profile_update_contract(client),
            _check_enterprise_organizations_contract(client),
            _check_enterprise_workspaces_contract(client),
            _check_enterprise_access_requests_contract(client),
            _check_enterprise_quotas_usage_contract(client),
            _check_enterprise_service_accounts_contract(client),
            _check_enterprise_tenant_boundary_and_permission_contract(client),
            _check_webhooks_subscriptions_contract(client),
            _check_webhooks_events_contract(client),
        ]
    finally:
        client.close()


def run_mcp_contract_suite(
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
            _check_mcp_initialize_contract(client),
            _check_mcp_tools_list_contract(client),
            _check_mcp_tools_call_contract(client),
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


def _check_trace_header_contract(client: httpx.Client) -> ContractResult:
    trace_id = str(uuid4())
    response = client.get("/health", headers={"X-Trace-Id": trace_id})
    if response.status_code != 200:
        return ContractResult("trace_header", False, f"unexpected status={response.status_code}")
    data = response.json()
    if data.get("ok") is not True:
        return ContractResult("trace_header", False, "missing or invalid field: ok")
    return ContractResult("trace_header", True, "ok")


def _check_mcp_initialize_contract(client: httpx.Client) -> ContractResult:
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid4()),
        "method": "initialize",
        "params": {"protocolVersion": "2024-11-05"},
    }
    data, error = _mcp_call(client, payload)
    if error:
        return ContractResult("mcp_initialize", False, error)
    result = data.get("result")
    if not isinstance(result, dict):
        return ContractResult("mcp_initialize", False, "missing or invalid field: result")
    if not isinstance(result.get("protocolVersion"), str):
        return ContractResult("mcp_initialize", False, "missing or invalid field: protocolVersion")
    return ContractResult("mcp_initialize", True, "ok")


def _check_mcp_tools_list_contract(client: httpx.Client) -> ContractResult:
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid4()),
        "method": "tools/list",
        "params": {},
    }
    data, error = _mcp_call(client, payload)
    if error:
        return ContractResult("mcp_tools_list", False, error)
    result = data.get("result")
    if not isinstance(result, dict):
        return ContractResult("mcp_tools_list", False, "missing or invalid field: result")
    tools = result.get("tools")
    if not isinstance(tools, list):
        return ContractResult("mcp_tools_list", False, "missing or invalid field: tools")
    if tools:
        first = tools[0]
        if not isinstance(first, dict):
            return ContractResult("mcp_tools_list", False, "invalid tools item shape")
        if not isinstance(first.get("name"), str):
            return ContractResult("mcp_tools_list", False, "invalid tools item: name")
    return ContractResult("mcp_tools_list", True, "ok")


def _check_mcp_tools_call_contract(client: httpx.Client) -> ContractResult:
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid4()),
        "method": "tools/call",
        "params": {
            "name": "axme.check_nick",
            "arguments": {"nick": "@conformance_mcp"},
        },
    }
    data, error = _mcp_call(client, payload)
    if error:
        return ContractResult("mcp_tools_call", False, error)
    result = data.get("result")
    if not isinstance(result, dict):
        return ContractResult("mcp_tools_call", False, "missing or invalid field: result")
    if not isinstance(result.get("tool"), str):
        return ContractResult("mcp_tools_call", False, "missing or invalid field: tool")
    if not isinstance(result.get("status"), str):
        return ContractResult("mcp_tools_call", False, "missing or invalid field: status")
    return ContractResult("mcp_tools_call", True, "ok")


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
    if data.get("status") not in CANONICAL_INTENT_STATUSES:
        return ContractResult("intent_create", False, "create status is not canonical lifecycle status")
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


def _check_intents_get_contract(client: httpx.Client) -> ContractResult:
    correlation_id = str(uuid4())
    create_response = client.post("/v1/intents", json=_build_intent_create_payload(correlation_id=correlation_id))
    if create_response.status_code != 200:
        return ContractResult("intents_get", False, f"create status={create_response.status_code}")
    intent_id = create_response.json().get("intent_id")
    if not _is_uuid(intent_id):
        return ContractResult("intents_get", False, "invalid intent_id from create response")

    response = client.get(f"/v1/intents/{intent_id}")
    if response.status_code != 200:
        return ContractResult("intents_get", False, f"unexpected status={response.status_code}")
    data = response.json()
    if data.get("ok") is not True:
        return ContractResult("intents_get", False, "missing or invalid field: ok")
    intent = data.get("intent")
    if not isinstance(intent, dict):
        return ContractResult("intents_get", False, "missing or invalid field: intent")
    if intent.get("intent_id") != intent_id:
        return ContractResult("intents_get", False, "intent_id mismatch")
    if not isinstance(intent.get("intent_type"), str):
        return ContractResult("intents_get", False, "missing or invalid field: intent_type")
    if not isinstance(intent.get("payload"), dict):
        return ContractResult("intents_get", False, "missing or invalid field: payload")
    if intent.get("status") not in CANONICAL_INTENT_STATUSES:
        return ContractResult("intents_get", False, "intent.status is not canonical lifecycle status")

    return ContractResult("intents_get", True, "ok")


def _check_intents_events_contract(client: httpx.Client) -> ContractResult:
    correlation_id = str(uuid4())
    create_response = client.post("/v1/intents", json=_build_intent_create_payload(correlation_id=correlation_id))
    if create_response.status_code != 200:
        return ContractResult("intents_events", False, f"create status={create_response.status_code}")
    intent_id = create_response.json().get("intent_id")
    if not _is_uuid(intent_id):
        return ContractResult("intents_events", False, "invalid intent_id from create response")

    events_response = client.get(f"/v1/intents/{intent_id}/events")
    if events_response.status_code != 200:
        return ContractResult("intents_events", False, f"unexpected status={events_response.status_code}")
    events_data = events_response.json()
    events = events_data.get("events")
    if events_data.get("ok") is not True or not isinstance(events, list) or len(events) < 2:
        return ContractResult("intents_events", False, "missing or invalid field: events")

    seqs: list[int] = []
    for item in events:
        if not isinstance(item, dict):
            return ContractResult("intents_events", False, "invalid event item shape")
        seq = item.get("seq")
        event_type = item.get("event_type")
        if not isinstance(seq, int) or seq < 1:
            return ContractResult("intents_events", False, "invalid event seq")
        if not isinstance(event_type, str) or not event_type.startswith("intent."):
            return ContractResult("intents_events", False, "invalid event_type")
        if item.get("status") not in CANONICAL_INTENT_STATUSES:
            return ContractResult("intents_events", False, "event status is not canonical lifecycle status")
        seqs.append(seq)
    if seqs != sorted(seqs):
        return ContractResult("intents_events", False, "events are not ordered by seq")
    expected_prefix = ["intent.created", "intent.submitted", "intent.delivered"]
    observed_prefix = [item.get("event_type") for item in events[:3]]
    if observed_prefix != expected_prefix:
        return ContractResult(
            "intents_events",
            False,
            f"unexpected lifecycle prefix: {observed_prefix}",
        )

    first_seq = seqs[0]
    since_response = client.get(f"/v1/intents/{intent_id}/events", params={"since": first_seq})
    if since_response.status_code != 200:
        return ContractResult("intents_events", False, f"since status={since_response.status_code}")
    since_events = since_response.json().get("events")
    if not isinstance(since_events, list):
        return ContractResult("intents_events", False, "missing or invalid field: since events")
    if any(not isinstance(item, dict) or not isinstance(item.get("seq"), int) or item["seq"] <= first_seq for item in since_events):
        return ContractResult("intents_events", False, "since filter returned invalid seq values")

    return ContractResult("intents_events", True, "ok")


def _check_intents_stream_resume_contract(client: httpx.Client) -> ContractResult:
    correlation_id = str(uuid4())
    create_response = client.post("/v1/intents", json=_build_intent_create_payload(correlation_id=correlation_id))
    if create_response.status_code != 200:
        return ContractResult("intents_stream_resume", False, f"create status={create_response.status_code}")
    intent_id = create_response.json().get("intent_id")
    if not _is_uuid(intent_id):
        return ContractResult("intents_stream_resume", False, "invalid intent_id from create response")

    stream_response = client.get(
        f"/v1/intents/{intent_id}/events/stream",
        params={"since": 1, "wait_seconds": 2},
    )
    if stream_response.status_code != 200:
        return ContractResult("intents_stream_resume", False, f"unexpected status={stream_response.status_code}")

    raw_lines = stream_response.text.splitlines()
    event_name: str | None = None
    data_lines: list[str] = []
    seen_resumed = False
    for line in raw_lines:
        if line == "":
            if event_name and event_name.startswith("intent.") and data_lines:
                try:
                    payload = json.loads("\n".join(data_lines))
                except ValueError:
                    payload = None
                if isinstance(payload, dict):
                    seq = payload.get("seq")
                    if isinstance(seq, int) and seq > 1:
                        seen_resumed = True
                        break
            event_name = None
            data_lines = []
            continue
        if line.startswith("event:"):
            event_name = line.partition(":")[2].strip()
            continue
        if line.startswith("data:"):
            data_lines.append(line.partition(":")[2].lstrip())
            continue
    if not seen_resumed:
        return ContractResult("intents_stream_resume", False, "stream did not yield resumed events")

    return ContractResult("intents_stream_resume", True, "ok")


def _check_intents_continuation_autonomy_contract(client: httpx.Client) -> ContractResult:
    correlation_id = str(uuid4())
    create_response = client.post("/v1/intents", json=_build_intent_create_payload(correlation_id=correlation_id))
    if create_response.status_code != 200:
        return ContractResult("intents_continuation_autonomy", False, f"create status={create_response.status_code}")
    intent_id = create_response.json().get("intent_id")
    if not _is_uuid(intent_id):
        return ContractResult("intents_continuation_autonomy", False, "invalid intent_id from create response")

    baseline_events = client.get(f"/v1/intents/{intent_id}/events")
    if baseline_events.status_code != 200:
        return ContractResult("intents_continuation_autonomy", False, f"baseline events status={baseline_events.status_code}")
    baseline_payload = baseline_events.json().get("events")
    if not isinstance(baseline_payload, list) or not baseline_payload:
        return ContractResult("intents_continuation_autonomy", False, "missing baseline events")
    seq_values = [item.get("seq") for item in baseline_payload if isinstance(item, dict)]
    if not seq_values or not all(isinstance(seq, int) for seq in seq_values):
        return ContractResult("intents_continuation_autonomy", False, "invalid baseline seq values")
    since_seq = max(seq_values)

    resolve_response = client.post(
        f"/v1/intents/{intent_id}/resolve",
        json={"status": "COMPLETED", "result": {"ok": True}},
    )
    if resolve_response.status_code != 200:
        return ContractResult("intents_continuation_autonomy", False, f"resolve status={resolve_response.status_code}")

    polling_response = client.get(
        f"/v1/intents/{intent_id}/events",
        params={"since": since_seq},
    )
    if polling_response.status_code != 200:
        return ContractResult("intents_continuation_autonomy", False, f"polling status={polling_response.status_code}")
    polling_events = polling_response.json().get("events")
    if not isinstance(polling_events, list):
        return ContractResult("intents_continuation_autonomy", False, "invalid polling events payload")
    if not any(
        isinstance(item, dict)
        and item.get("event_type") == "intent.completed"
        and item.get("status") == "COMPLETED"
        for item in polling_events
    ):
        return ContractResult(
            "intents_continuation_autonomy",
            False,
            "polling did not expose terminal transition without get_intent side effects",
        )

    stream_response = client.get(
        f"/v1/intents/{intent_id}/events/stream",
        params={"since": since_seq, "wait_seconds": 2},
    )
    if stream_response.status_code != 200:
        return ContractResult("intents_continuation_autonomy", False, f"stream status={stream_response.status_code}")

    event_name: str | None = None
    data_lines: list[str] = []
    saw_terminal = False
    for line in stream_response.text.splitlines():
        if line == "":
            if event_name == "intent.completed" and data_lines:
                try:
                    payload = json.loads("\n".join(data_lines))
                except ValueError:
                    payload = None
                if isinstance(payload, dict) and payload.get("status") == "COMPLETED":
                    saw_terminal = True
                    break
            event_name = None
            data_lines = []
            continue
        if line.startswith("event:"):
            event_name = line.partition(":")[2].strip()
            continue
        if line.startswith("data:"):
            data_lines.append(line.partition(":")[2].lstrip())
            continue

    if not saw_terminal:
        return ContractResult(
            "intents_continuation_autonomy",
            False,
            "stream did not expose terminal transition without get_intent side effects",
        )

    return ContractResult("intents_continuation_autonomy", True, "ok")


def _check_intents_resolve_contract(client: httpx.Client) -> ContractResult:
    correlation_id = str(uuid4())
    create_response = client.post("/v1/intents", json=_build_intent_create_payload(correlation_id=correlation_id))
    if create_response.status_code != 200:
        return ContractResult("intents_resolve", False, f"create status={create_response.status_code}")
    intent_id = create_response.json().get("intent_id")
    if not _is_uuid(intent_id):
        return ContractResult("intents_resolve", False, "invalid intent_id from create response")

    resolve_response = client.post(
        f"/v1/intents/{intent_id}/resolve",
        json={"status": "COMPLETED", "result": {"ok": True}},
    )
    if resolve_response.status_code != 200:
        return ContractResult("intents_resolve", False, f"resolve status={resolve_response.status_code}")
    resolve_data = resolve_response.json()
    event = resolve_data.get("event")
    if resolve_data.get("ok") is not True or not isinstance(event, dict):
        return ContractResult("intents_resolve", False, "invalid resolve response shape")
    if event.get("event_type") != "intent.completed":
        return ContractResult("intents_resolve", False, "resolve did not emit terminal completed event")
    if event.get("status") != "COMPLETED":
        return ContractResult("intents_resolve", False, "resolve status mismatch")
    resolved_intent = resolve_data.get("intent")
    if not isinstance(resolved_intent, dict) or resolved_intent.get("status") != "COMPLETED":
        return ContractResult("intents_resolve", False, "resolved intent projection is not terminal canonical status")

    second_terminal = client.post(
        f"/v1/intents/{intent_id}/resolve",
        json={"status": "CANCELED", "reason": "too late"},
    )
    if second_terminal.status_code != 409:
        return ContractResult("intents_resolve", False, f"expected 409 for second terminal, got={second_terminal.status_code}")

    return ContractResult("intents_resolve", True, "ok")


def _check_intent_completion_delivery_contract(client: httpx.Client) -> ContractResult:
    correlation_id = str(uuid4())
    reply_to = "agent://conformance/reply-target"
    create_response = client.post(
        "/v1/intents",
        json=_build_intent_create_payload(correlation_id=correlation_id, reply_to=reply_to),
    )
    if create_response.status_code != 200:
        return ContractResult("intent_completion_delivery", False, f"create status={create_response.status_code}")
    intent_id = create_response.json().get("intent_id")
    if not _is_uuid(intent_id):
        return ContractResult("intent_completion_delivery", False, "invalid intent_id from create response")

    resolve_response = client.post(
        f"/v1/intents/{intent_id}/resolve",
        json={"status": "COMPLETED", "result": {"ok": True}},
    )
    if resolve_response.status_code != 200:
        return ContractResult("intent_completion_delivery", False, f"resolve status={resolve_response.status_code}")
    resolve_data = resolve_response.json()
    completion_delivery = resolve_data.get("completion_delivery")
    if not isinstance(completion_delivery, dict):
        return ContractResult("intent_completion_delivery", False, "missing completion_delivery object")
    if completion_delivery.get("delivered") is not True:
        return ContractResult("intent_completion_delivery", False, "completion delivery not marked delivered")
    if completion_delivery.get("reply_to") != reply_to:
        return ContractResult("intent_completion_delivery", False, "completion delivery reply_to mismatch")

    inbox_response = client.get("/v1/inbox", params={"owner_agent": reply_to})
    if inbox_response.status_code != 200:
        return ContractResult("intent_completion_delivery", False, f"inbox status={inbox_response.status_code}")
    threads = inbox_response.json().get("threads")
    if not isinstance(threads, list):
        return ContractResult("intent_completion_delivery", False, "invalid inbox threads payload")
    if not any(isinstance(thread, dict) and thread.get("thread_id") == intent_id for thread in threads):
        return ContractResult("intent_completion_delivery", False, "reply_to inbox does not expose completion thread")

    return ContractResult("intent_completion_delivery", True, "ok")


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


def _check_inbox_thread_contract(client: httpx.Client) -> ContractResult:
    owner_agent = "agent://conformance/owner"
    list_response = client.get("/v1/inbox", params={"owner_agent": owner_agent})
    if list_response.status_code != 200:
        return ContractResult("inbox_thread", False, f"list status={list_response.status_code}")
    threads = list_response.json().get("threads")
    if not isinstance(threads, list) or not threads:
        return ContractResult("inbox_thread", False, "missing or invalid field: threads")
    thread_id = threads[0].get("thread_id")
    if not _is_uuid(thread_id):
        return ContractResult("inbox_thread", False, "missing or invalid field: thread_id")

    response = client.get(f"/v1/inbox/{thread_id}", params={"owner_agent": owner_agent})
    if response.status_code != 200:
        return ContractResult("inbox_thread", False, f"unexpected status={response.status_code}")
    data = response.json()
    if data.get("ok") is not True:
        return ContractResult("inbox_thread", False, "missing or invalid field: ok")
    thread = data.get("thread")
    if not _is_thread_shape(thread):
        return ContractResult("inbox_thread", False, "invalid thread shape")
    if thread.get("thread_id") != thread_id:
        return ContractResult("inbox_thread", False, "thread_id mismatch")

    return ContractResult("inbox_thread", True, "ok")


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


def _check_inbox_changes_pagination_contract(client: httpx.Client) -> ContractResult:
    owner_agent = "agent://conformance/owner"
    response = client.get("/v1/inbox/changes", params={"owner_agent": owner_agent})
    if response.status_code != 200:
        return ContractResult("inbox_changes_pagination", False, f"unexpected status={response.status_code}")

    data = response.json()
    if data.get("ok") is not True:
        return ContractResult("inbox_changes_pagination", False, "missing or invalid field: ok")

    changes = data.get("changes")
    has_more = data.get("has_more")
    next_cursor = data.get("next_cursor")

    if not isinstance(changes, list):
        return ContractResult("inbox_changes_pagination", False, "missing or invalid field: changes")
    if not isinstance(has_more, bool):
        return ContractResult("inbox_changes_pagination", False, "missing or invalid field: has_more")
    if next_cursor is not None and not isinstance(next_cursor, str):
        return ContractResult("inbox_changes_pagination", False, "invalid field: next_cursor")

    if changes and not _is_inbox_change_shape(changes[0]):
        return ContractResult("inbox_changes_pagination", False, "invalid inbox change shape")

    if has_more:
        if not isinstance(next_cursor, str) or len(next_cursor) < 3:
            return ContractResult("inbox_changes_pagination", False, "has_more=true requires next_cursor")
        follow_up = client.get(
            "/v1/inbox/changes",
            params={"owner_agent": owner_agent, "cursor": next_cursor},
        )
        if follow_up.status_code != 200:
            return ContractResult(
                "inbox_changes_pagination",
                False,
                f"follow-up status={follow_up.status_code}",
            )

    return ContractResult("inbox_changes_pagination", True, "ok")


def _check_inbox_delegate_contract(client: httpx.Client) -> ContractResult:
    owner_agent = "agent://conformance/owner"
    list_response = client.get("/v1/inbox", params={"owner_agent": owner_agent})
    if list_response.status_code != 200:
        return ContractResult("inbox_delegate", False, f"list status={list_response.status_code}")
    threads = list_response.json().get("threads")
    if not isinstance(threads, list) or not threads:
        return ContractResult("inbox_delegate", False, "missing or invalid field: threads")
    thread_id = threads[0].get("thread_id")
    if not _is_uuid(thread_id):
        return ContractResult("inbox_delegate", False, "missing or invalid field: thread_id")

    response = client.post(
        f"/v1/inbox/{thread_id}/delegate",
        params={"owner_agent": owner_agent},
        json={"delegate_to": "agent://conformance/delegate", "note": "handoff"},
    )
    if response.status_code != 200:
        return ContractResult("inbox_delegate", False, f"unexpected status={response.status_code}")
    data = response.json()
    if data.get("ok") is not True:
        return ContractResult("inbox_delegate", False, "missing or invalid field: ok")
    thread = data.get("thread")
    if not _is_thread_shape(thread):
        return ContractResult("inbox_delegate", False, "invalid thread shape")

    return ContractResult("inbox_delegate", True, "ok")


def _check_inbox_decision_contract(client: httpx.Client) -> ContractResult:
    owner_agent = "agent://conformance/owner"
    list_response = client.get("/v1/inbox", params={"owner_agent": owner_agent})
    if list_response.status_code != 200:
        return ContractResult("inbox_decision", False, f"list status={list_response.status_code}")
    threads = list_response.json().get("threads")
    if not isinstance(threads, list) or not threads:
        return ContractResult("inbox_decision", False, "missing or invalid field: threads")
    thread_id = threads[0].get("thread_id")
    if not _is_uuid(thread_id):
        return ContractResult("inbox_decision", False, "missing or invalid field: thread_id")

    response = client.post(
        f"/v1/inbox/{thread_id}/approve",
        params={"owner_agent": owner_agent},
        json={"comment": "approved in conformance"},
    )
    if response.status_code != 200:
        return ContractResult("inbox_decision", False, f"unexpected status={response.status_code}")
    data = response.json()
    if data.get("ok") is not True:
        return ContractResult("inbox_decision", False, "missing or invalid field: ok")
    thread = data.get("thread")
    if not _is_thread_shape(thread):
        return ContractResult("inbox_decision", False, "invalid thread shape")

    return ContractResult("inbox_decision", True, "ok")


def _check_inbox_messages_delete_contract(client: httpx.Client) -> ContractResult:
    owner_agent = "agent://conformance/owner"
    list_response = client.get("/v1/inbox", params={"owner_agent": owner_agent})
    if list_response.status_code != 200:
        return ContractResult("inbox_messages_delete", False, f"list status={list_response.status_code}")
    threads = list_response.json().get("threads")
    if not isinstance(threads, list) or not threads:
        return ContractResult("inbox_messages_delete", False, "missing or invalid field: threads")
    thread_id = threads[0].get("thread_id")
    if not _is_uuid(thread_id):
        return ContractResult("inbox_messages_delete", False, "missing or invalid field: thread_id")

    response = client.post(
        f"/v1/inbox/{thread_id}/messages/delete",
        params={"owner_agent": owner_agent},
        json={"mode": "self", "limit": 1},
    )
    if response.status_code != 200:
        return ContractResult("inbox_messages_delete", False, f"unexpected status={response.status_code}")
    data = response.json()
    if data.get("ok") is not True:
        return ContractResult("inbox_messages_delete", False, "missing or invalid field: ok")
    if data.get("mode") not in {"self", "both"}:
        return ContractResult("inbox_messages_delete", False, "invalid field: mode")
    if not isinstance(data.get("deleted_count"), int) or data.get("deleted_count") < 0:
        return ContractResult("inbox_messages_delete", False, "missing or invalid field: deleted_count")
    message_ids = data.get("message_ids")
    if not isinstance(message_ids, list):
        return ContractResult("inbox_messages_delete", False, "missing or invalid field: message_ids")
    thread = data.get("thread")
    if not _is_thread_shape(thread):
        return ContractResult("inbox_messages_delete", False, "invalid thread shape")

    return ContractResult("inbox_messages_delete", True, "ok")


def _check_approvals_decision_contract(client: httpx.Client) -> ContractResult:
    approval_id = str(uuid4())
    response = client.post(
        f"/v1/approvals/{approval_id}/decision",
        json={"decision": "approve", "comment": "approved by conformance"},
    )
    if response.status_code != 200:
        return ContractResult("approvals_decision", False, f"unexpected status={response.status_code}")

    data = response.json()
    if data.get("ok") is not True:
        return ContractResult("approvals_decision", False, "missing or invalid field: ok")

    approval = data.get("approval")
    if not isinstance(approval, dict):
        return ContractResult("approvals_decision", False, "missing or invalid field: approval")
    if not _is_uuid(approval.get("approval_id")):
        return ContractResult("approvals_decision", False, "approval_id is not UUID")
    if approval.get("decision") not in {"approve", "reject"}:
        return ContractResult("approvals_decision", False, "invalid field: decision")
    if not isinstance(approval.get("decided_at"), str):
        return ContractResult("approvals_decision", False, "missing or invalid field: decided_at")
    comment = approval.get("comment")
    if comment is not None and not isinstance(comment, str):
        return ContractResult("approvals_decision", False, "invalid field: comment")

    return ContractResult("approvals_decision", True, "ok")


def _check_capabilities_contract(client: httpx.Client) -> ContractResult:
    response = client.get("/v1/capabilities")
    if response.status_code != 200:
        return ContractResult("capabilities_get", False, f"unexpected status={response.status_code}")

    data = response.json()
    if data.get("ok") is not True:
        return ContractResult("capabilities_get", False, "missing or invalid field: ok")

    capabilities = data.get("capabilities")
    supported_intent_types = data.get("supported_intent_types")
    if not isinstance(capabilities, list) or len(capabilities) < 1:
        return ContractResult("capabilities_get", False, "missing or invalid field: capabilities")
    if not all(isinstance(item, str) and len(item) >= 3 for item in capabilities):
        return ContractResult("capabilities_get", False, "invalid field: capabilities items")
    if not isinstance(supported_intent_types, list) or len(supported_intent_types) < 1:
        return ContractResult("capabilities_get", False, "missing or invalid field: supported_intent_types")
    if not all(isinstance(item, str) and item.startswith("intent.") and item.endswith(".v1") for item in supported_intent_types):
        return ContractResult("capabilities_get", False, "invalid field: supported_intent_types items")

    return ContractResult("capabilities_get", True, "ok")


def _check_invites_create_contract(client: httpx.Client) -> ContractResult:
    response = client.post(
        "/v1/invites/create",
        json={
            "owner_agent": "agent://conformance/owner",
            "recipient_hint": "Conformance receiver",
            "ttl_seconds": 3600,
        },
    )
    if response.status_code != 200:
        return ContractResult("invites_create", False, f"unexpected status={response.status_code}")

    data = response.json()
    if data.get("ok") is not True:
        return ContractResult("invites_create", False, "missing or invalid field: ok")
    token = data.get("token")
    invite_url = data.get("invite_url")
    if not isinstance(token, str) or len(token) < 12:
        return ContractResult("invites_create", False, "missing or invalid field: token")
    if not isinstance(invite_url, str) or not invite_url.startswith("http"):
        return ContractResult("invites_create", False, "missing or invalid field: invite_url")
    if data.get("status") not in {"pending", "accepted", "expired"}:
        return ContractResult("invites_create", False, "invalid field: status")

    return ContractResult("invites_create", True, "ok")


def _check_invites_get_contract(client: httpx.Client) -> ContractResult:
    create_response = client.post(
        "/v1/invites/create",
        json={
            "owner_agent": "agent://conformance/owner",
            "recipient_hint": "Conformance receiver",
            "ttl_seconds": 3600,
        },
    )
    if create_response.status_code != 200:
        return ContractResult("invites_get", False, f"create status={create_response.status_code}")
    token = create_response.json().get("token")
    if not isinstance(token, str) or len(token) < 12:
        return ContractResult("invites_get", False, "invalid token from create invite response")

    response = client.get(f"/v1/invites/{token}")
    if response.status_code != 200:
        return ContractResult("invites_get", False, f"unexpected status={response.status_code}")
    data = response.json()
    if data.get("ok") is not True:
        return ContractResult("invites_get", False, "missing or invalid field: ok")
    if data.get("token") != token:
        return ContractResult("invites_get", False, "token mismatch")
    if not isinstance(data.get("owner_agent"), str):
        return ContractResult("invites_get", False, "missing or invalid field: owner_agent")
    if data.get("status") not in {"pending", "accepted", "expired"}:
        return ContractResult("invites_get", False, "invalid field: status")

    return ContractResult("invites_get", True, "ok")


def _check_invites_accept_contract(client: httpx.Client) -> ContractResult:
    create_response = client.post(
        "/v1/invites/create",
        json={
            "owner_agent": "agent://conformance/owner",
            "recipient_hint": "Conformance receiver",
            "ttl_seconds": 3600,
        },
    )
    if create_response.status_code != 200:
        return ContractResult("invites_accept", False, f"create status={create_response.status_code}")
    token = create_response.json().get("token")
    if not isinstance(token, str) or len(token) < 12:
        return ContractResult("invites_accept", False, "invalid token from create invite response")

    response = client.post(
        f"/v1/invites/{token}/accept",
        json={"nick": "@Invite.Conformance.User", "display_name": "Conformance User"},
    )
    if response.status_code != 200:
        return ContractResult("invites_accept", False, f"unexpected status={response.status_code}")
    data = response.json()
    if data.get("ok") is not True:
        return ContractResult("invites_accept", False, "missing or invalid field: ok")
    if data.get("token") != token:
        return ContractResult("invites_accept", False, "token mismatch")
    if data.get("status") != "accepted":
        return ContractResult("invites_accept", False, "missing or invalid field: status")
    if not _is_uuid(data.get("user_id")):
        return ContractResult("invites_accept", False, "missing or invalid field: user_id")
    if not isinstance(data.get("owner_agent"), str):
        return ContractResult("invites_accept", False, "missing or invalid field: owner_agent")
    if not isinstance(data.get("public_address"), str):
        return ContractResult("invites_accept", False, "missing or invalid field: public_address")
    if data.get("registry_bind_status") not in {"propagated", "failed", "disabled", "skipped_no_hint"}:
        return ContractResult("invites_accept", False, "invalid field: registry_bind_status")

    return ContractResult("invites_accept", True, "ok")


def _check_media_create_upload_contract(client: httpx.Client) -> ContractResult:
    response = client.post(
        "/v1/media/create-upload",
        json={
            "owner_agent": "agent://conformance/owner",
            "filename": "contract.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 12345,
        },
    )
    if response.status_code != 200:
        return ContractResult("media_create_upload", False, f"unexpected status={response.status_code}")

    data = response.json()
    if data.get("ok") is not True:
        return ContractResult("media_create_upload", False, "missing or invalid field: ok")
    upload_id = data.get("upload_id")
    if not _is_uuid(upload_id):
        return ContractResult("media_create_upload", False, "missing or invalid field: upload_id")
    if data.get("status") != "pending":
        return ContractResult("media_create_upload", False, "invalid field: status")
    if not isinstance(data.get("upload_url"), str):
        return ContractResult("media_create_upload", False, "missing or invalid field: upload_url")

    return ContractResult("media_create_upload", True, "ok")


def _check_media_get_contract(client: httpx.Client) -> ContractResult:
    create_response = client.post(
        "/v1/media/create-upload",
        json={
            "owner_agent": "agent://conformance/owner",
            "filename": "contract.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 12345,
        },
    )
    if create_response.status_code != 200:
        return ContractResult("media_get", False, f"create status={create_response.status_code}")
    upload_id = create_response.json().get("upload_id")
    if not _is_uuid(upload_id):
        return ContractResult("media_get", False, "invalid upload_id from create upload response")

    response = client.get(f"/v1/media/{upload_id}")
    if response.status_code != 200:
        return ContractResult("media_get", False, f"unexpected status={response.status_code}")

    data = response.json()
    if data.get("ok") is not True:
        return ContractResult("media_get", False, "missing or invalid field: ok")
    upload = data.get("upload")
    if not isinstance(upload, dict):
        return ContractResult("media_get", False, "missing or invalid field: upload")
    if upload.get("upload_id") != upload_id:
        return ContractResult("media_get", False, "upload_id mismatch")
    if upload.get("status") not in {"pending", "ready", "expired"}:
        return ContractResult("media_get", False, "invalid field: status")

    return ContractResult("media_get", True, "ok")


def _check_media_finalize_upload_contract(client: httpx.Client) -> ContractResult:
    create_response = client.post(
        "/v1/media/create-upload",
        json={
            "owner_agent": "agent://conformance/owner",
            "filename": "contract.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 12345,
        },
    )
    if create_response.status_code != 200:
        return ContractResult("media_finalize_upload", False, f"create status={create_response.status_code}")
    upload_id = create_response.json().get("upload_id")
    if not _is_uuid(upload_id):
        return ContractResult("media_finalize_upload", False, "invalid upload_id from create upload response")

    response = client.post(
        "/v1/media/finalize-upload",
        json={
            "upload_id": upload_id,
            "size_bytes": 12345,
        },
    )
    if response.status_code != 200:
        return ContractResult("media_finalize_upload", False, f"unexpected status={response.status_code}")
    data = response.json()
    if data.get("ok") is not True:
        return ContractResult("media_finalize_upload", False, "missing or invalid field: ok")
    if data.get("upload_id") != upload_id:
        return ContractResult("media_finalize_upload", False, "upload_id mismatch")
    if data.get("status") != "ready":
        return ContractResult("media_finalize_upload", False, "invalid field: status")
    if not isinstance(data.get("finalized_at"), str):
        return ContractResult("media_finalize_upload", False, "missing or invalid field: finalized_at")

    return ContractResult("media_finalize_upload", True, "ok")


def _check_schemas_upsert_contract(client: httpx.Client) -> ContractResult:
    semantic_type = "axme.calendar.schedule.v1"
    response = client.post(
        "/v1/schemas",
        json={
            "semantic_type": semantic_type,
            "schema_json": {
                "type": "object",
                "required": ["date"],
                "properties": {"date": {"type": "string"}},
            },
            "compatibility_mode": "strict",
        },
    )
    if response.status_code != 200:
        return ContractResult("schemas_upsert", False, f"unexpected status={response.status_code}")

    data = response.json()
    if data.get("ok") is not True:
        return ContractResult("schemas_upsert", False, "missing or invalid field: ok")
    schema = data.get("schema")
    if not isinstance(schema, dict):
        return ContractResult("schemas_upsert", False, "missing or invalid field: schema")
    if schema.get("semantic_type") != semantic_type:
        return ContractResult("schemas_upsert", False, "semantic_type mismatch")
    if schema.get("compatibility_mode") not in {"strict", "backward", "warn"}:
        return ContractResult("schemas_upsert", False, "invalid field: compatibility_mode")
    if not isinstance(schema.get("schema_hash"), str) or len(schema.get("schema_hash")) != 64:
        return ContractResult("schemas_upsert", False, "missing or invalid field: schema_hash")

    return ContractResult("schemas_upsert", True, "ok")


def _check_schemas_get_contract(client: httpx.Client) -> ContractResult:
    semantic_type = "axme.calendar.schedule.v1"
    upsert = client.post(
        "/v1/schemas",
        json={
            "semantic_type": semantic_type,
            "schema_json": {
                "type": "object",
                "required": ["date"],
                "properties": {"date": {"type": "string"}},
            },
            "compatibility_mode": "strict",
        },
    )
    if upsert.status_code != 200:
        return ContractResult("schemas_get", False, f"upsert status={upsert.status_code}")

    response = client.get(f"/v1/schemas/{semantic_type}")
    if response.status_code != 200:
        return ContractResult("schemas_get", False, f"unexpected status={response.status_code}")
    data = response.json()
    if data.get("ok") is not True:
        return ContractResult("schemas_get", False, "missing or invalid field: ok")
    schema = data.get("schema")
    if not isinstance(schema, dict):
        return ContractResult("schemas_get", False, "missing or invalid field: schema")
    if schema.get("semantic_type") != semantic_type:
        return ContractResult("schemas_get", False, "semantic_type mismatch")
    if not isinstance(schema.get("schema_json"), dict):
        return ContractResult("schemas_get", False, "missing or invalid field: schema_json")

    return ContractResult("schemas_get", True, "ok")


def _check_users_check_nick_contract(client: httpx.Client) -> ContractResult:
    nick = f"@conformance_{uuid4().hex[:10]}"
    response = client.get("/v1/users/check-nick", params={"nick": nick})
    if response.status_code != 200:
        return ContractResult("users_check_nick", False, f"unexpected status={response.status_code}")

    data = response.json()
    if data.get("ok") is not True:
        return ContractResult("users_check_nick", False, "missing or invalid field: ok")
    if data.get("nick") != nick:
        return ContractResult("users_check_nick", False, "nick mismatch")
    if not isinstance(data.get("normalized_nick"), str):
        return ContractResult("users_check_nick", False, "missing or invalid field: normalized_nick")
    if not isinstance(data.get("public_address"), str):
        return ContractResult("users_check_nick", False, "missing or invalid field: public_address")
    if not isinstance(data.get("available"), bool):
        return ContractResult("users_check_nick", False, "missing or invalid field: available")

    return ContractResult("users_check_nick", True, "ok")


def _check_users_register_nick_contract(client: httpx.Client) -> ContractResult:
    nick = f"@conformance_{uuid4().hex[:10]}"
    response = client.post(
        "/v1/users/register-nick",
        json={"nick": nick, "display_name": "Conformance User"},
    )
    if response.status_code != 200:
        return ContractResult("users_register_nick", False, f"unexpected status={response.status_code}")

    data = response.json()
    if data.get("ok") is not True:
        return ContractResult("users_register_nick", False, "missing or invalid field: ok")
    if not _is_uuid(data.get("user_id")):
        return ContractResult("users_register_nick", False, "missing or invalid field: user_id")
    if not isinstance(data.get("owner_agent"), str):
        return ContractResult("users_register_nick", False, "missing or invalid field: owner_agent")
    if not isinstance(data.get("nick"), str):
        return ContractResult("users_register_nick", False, "missing or invalid field: nick")
    if not isinstance(data.get("public_address"), str):
        return ContractResult("users_register_nick", False, "missing or invalid field: public_address")
    if not isinstance(data.get("created_at"), str):
        return ContractResult("users_register_nick", False, "missing or invalid field: created_at")

    return ContractResult("users_register_nick", True, "ok")


def _check_users_rename_nick_contract(client: httpx.Client) -> ContractResult:
    source_nick = f"@conformance_{uuid4().hex[:10]}"
    register = client.post(
        "/v1/users/register-nick",
        json={"nick": source_nick, "display_name": "Conformance User"},
    )
    if register.status_code != 200:
        return ContractResult("users_rename_nick", False, f"register status={register.status_code}")

    owner_agent = register.json().get("owner_agent")
    if not isinstance(owner_agent, str):
        return ContractResult("users_rename_nick", False, "invalid owner_agent from register response")

    new_nick = f"@conformance_{uuid4().hex[:10]}"
    response = client.post(
        "/v1/users/rename-nick",
        json={"owner_agent": owner_agent, "nick": new_nick},
    )
    if response.status_code != 200:
        return ContractResult("users_rename_nick", False, f"unexpected status={response.status_code}")
    data = response.json()
    if data.get("ok") is not True:
        return ContractResult("users_rename_nick", False, "missing or invalid field: ok")
    if data.get("owner_agent") != owner_agent:
        return ContractResult("users_rename_nick", False, "owner_agent mismatch")
    if data.get("nick") != new_nick:
        return ContractResult("users_rename_nick", False, "nick mismatch")
    if not isinstance(data.get("public_address"), str):
        return ContractResult("users_rename_nick", False, "missing or invalid field: public_address")
    if not isinstance(data.get("renamed_at"), str):
        return ContractResult("users_rename_nick", False, "missing or invalid field: renamed_at")

    return ContractResult("users_rename_nick", True, "ok")


def _check_users_profile_get_contract(client: httpx.Client) -> ContractResult:
    nick = f"@conformance_{uuid4().hex[:10]}"
    register = client.post(
        "/v1/users/register-nick",
        json={"nick": nick, "display_name": "Conformance User"},
    )
    if register.status_code != 200:
        return ContractResult("users_profile_get", False, f"register status={register.status_code}")
    owner_agent = register.json().get("owner_agent")
    if not isinstance(owner_agent, str):
        return ContractResult("users_profile_get", False, "invalid owner_agent from register response")

    response = client.get("/v1/users/profile", params={"owner_agent": owner_agent})
    if response.status_code != 200:
        return ContractResult("users_profile_get", False, f"unexpected status={response.status_code}")
    data = response.json()
    if data.get("ok") is not True:
        return ContractResult("users_profile_get", False, "missing or invalid field: ok")
    if data.get("owner_agent") != owner_agent:
        return ContractResult("users_profile_get", False, "owner_agent mismatch")
    if not isinstance(data.get("normalized_nick"), str):
        return ContractResult("users_profile_get", False, "missing or invalid field: normalized_nick")
    if not isinstance(data.get("updated_at"), str):
        return ContractResult("users_profile_get", False, "missing or invalid field: updated_at")

    return ContractResult("users_profile_get", True, "ok")


def _check_users_profile_update_contract(client: httpx.Client) -> ContractResult:
    nick = f"@conformance_{uuid4().hex[:10]}"
    register = client.post(
        "/v1/users/register-nick",
        json={"nick": nick, "display_name": "Conformance User"},
    )
    if register.status_code != 200:
        return ContractResult("users_profile_update", False, f"register status={register.status_code}")
    owner_agent = register.json().get("owner_agent")
    if not isinstance(owner_agent, str):
        return ContractResult("users_profile_update", False, "invalid owner_agent from register response")

    response = client.post(
        "/v1/users/profile/update",
        json={"owner_agent": owner_agent, "display_name": "Conformance User Updated"},
    )
    if response.status_code != 200:
        return ContractResult("users_profile_update", False, f"unexpected status={response.status_code}")
    data = response.json()
    if data.get("ok") is not True:
        return ContractResult("users_profile_update", False, "missing or invalid field: ok")
    if data.get("owner_agent") != owner_agent:
        return ContractResult("users_profile_update", False, "owner_agent mismatch")
    if data.get("display_name") != "Conformance User Updated":
        return ContractResult("users_profile_update", False, "display_name mismatch")
    if not isinstance(data.get("updated_at"), str):
        return ContractResult("users_profile_update", False, "missing or invalid field: updated_at")

    return ContractResult("users_profile_update", True, "ok")


def _create_enterprise_organization_for_contract(
    client: httpx.Client,
    *,
    name: str,
) -> tuple[str | None, str | None]:
    response = client.post(
        "/v1/organizations",
        json={"name": name, "requested_by_actor_id": "actor://conformance/admin"},
    )
    if response.status_code != 200:
        return None, f"organization create status={response.status_code}"
    data = response.json()
    organization = data.get("organization")
    if data.get("ok") is not True or not isinstance(organization, dict):
        return None, "invalid organization create response shape"
    org_id = organization.get("org_id")
    if not _is_uuid(org_id):
        return None, "invalid org_id in create response"
    return org_id, None


def _create_enterprise_workspace_for_contract(
    client: httpx.Client,
    *,
    org_id: str,
    name: str,
) -> tuple[str | None, str | None]:
    response = client.post(
        f"/v1/organizations/{org_id}/workspaces",
        json={
            "org_id": org_id,
            "name": name,
            "environment": "sandbox",
            "region": "us-central1",
        },
    )
    if response.status_code != 200:
        return None, f"workspace create status={response.status_code}"
    data = response.json()
    workspace = data.get("workspace")
    if data.get("ok") is not True or not isinstance(workspace, dict):
        return None, "invalid workspace create response shape"
    workspace_id = workspace.get("workspace_id")
    if not _is_uuid(workspace_id):
        return None, "invalid workspace_id in create response"
    if workspace.get("org_id") != org_id:
        return None, "workspace org_id mismatch"
    return workspace_id, None


def _check_enterprise_organizations_contract(client: httpx.Client) -> ContractResult:
    org_id, error = _create_enterprise_organization_for_contract(client, name="Conformance Organization")
    if error:
        return ContractResult("enterprise_organizations", False, error)
    assert org_id is not None

    get_response = client.get(f"/v1/organizations/{org_id}")
    if get_response.status_code != 200:
        return ContractResult("enterprise_organizations", False, f"organization get status={get_response.status_code}")
    get_data = get_response.json()
    organization = get_data.get("organization")
    if get_data.get("ok") is not True or not isinstance(organization, dict):
        return ContractResult("enterprise_organizations", False, "invalid organization get response shape")
    if organization.get("org_id") != org_id:
        return ContractResult("enterprise_organizations", False, "organization org_id mismatch")
    if not isinstance(organization.get("name"), str):
        return ContractResult("enterprise_organizations", False, "organization name missing or invalid")
    if not isinstance(organization.get("workspaces_count"), int):
        return ContractResult("enterprise_organizations", False, "workspaces_count missing or invalid")
    if not isinstance(organization.get("members_count"), int):
        return ContractResult("enterprise_organizations", False, "members_count missing or invalid")
    return ContractResult("enterprise_organizations", True, "ok")


def _check_enterprise_workspaces_contract(client: httpx.Client) -> ContractResult:
    org_id, error = _create_enterprise_organization_for_contract(client, name="Conformance Workspace Org")
    if error:
        return ContractResult("enterprise_workspaces", False, error)
    assert org_id is not None

    workspace_id, workspace_error = _create_enterprise_workspace_for_contract(
        client,
        org_id=org_id,
        name="Conformance Workspace",
    )
    if workspace_error:
        return ContractResult("enterprise_workspaces", False, workspace_error)
    assert workspace_id is not None
    if not _is_uuid(workspace_id):
        return ContractResult("enterprise_workspaces", False, "workspace_id is not UUID")
    return ContractResult("enterprise_workspaces", True, "ok")


def _check_enterprise_access_requests_contract(client: httpx.Client) -> ContractResult:
    org_id, error = _create_enterprise_organization_for_contract(client, name="Conformance Access Org")
    if error:
        return ContractResult("enterprise_access_requests", False, error)
    assert org_id is not None

    create_response = client.post(
        "/v1/access-requests",
        json={
            "request_type": "join_organization",
            "requester_actor_id": "actor://conformance/requester",
            "org_id": org_id,
            "requested_role": "member",
            "justification": "Need tenant access for conformance checks.",
        },
    )
    if create_response.status_code != 200:
        return ContractResult("enterprise_access_requests", False, f"access request create status={create_response.status_code}")
    create_data = create_response.json()
    access_request = create_data.get("access_request")
    if create_data.get("ok") is not True or not isinstance(access_request, dict):
        return ContractResult("enterprise_access_requests", False, "invalid access request create response shape")
    access_request_id = access_request.get("access_request_id")
    if not _is_uuid(access_request_id):
        return ContractResult("enterprise_access_requests", False, "invalid access_request_id")

    review_response = client.post(
        f"/v1/access-requests/{access_request_id}/review",
        json={
            "decision": "approve",
            "reviewer_actor_id": "actor://conformance/reviewer",
            "review_comment": "approved in enterprise conformance smoke checks",
        },
    )
    if review_response.status_code != 200:
        return ContractResult("enterprise_access_requests", False, f"access request review status={review_response.status_code}")
    review_data = review_response.json()
    reviewed_request = review_data.get("access_request")
    if review_data.get("ok") is not True or not isinstance(reviewed_request, dict):
        return ContractResult("enterprise_access_requests", False, "invalid access request review response shape")
    if reviewed_request.get("access_request_id") != access_request_id:
        return ContractResult("enterprise_access_requests", False, "access_request_id mismatch after review")
    if reviewed_request.get("state") != "approved":
        return ContractResult("enterprise_access_requests", False, "review did not transition state to approved")
    return ContractResult("enterprise_access_requests", True, "ok")


def _check_enterprise_quotas_usage_contract(client: httpx.Client) -> ContractResult:
    org_id, error = _create_enterprise_organization_for_contract(client, name="Conformance Quotas Org")
    if error:
        return ContractResult("enterprise_quotas_usage", False, error)
    assert org_id is not None
    workspace_id, workspace_error = _create_enterprise_workspace_for_contract(
        client,
        org_id=org_id,
        name="Conformance Quotas Workspace",
    )
    if workspace_error:
        return ContractResult("enterprise_quotas_usage", False, workspace_error)
    assert workspace_id is not None

    dimensions = {
        "requests_per_minute": 500,
        "intents_per_day": 10000,
        "inbox_writes_per_day": 3000,
        "media_upload_bytes_per_day": 5000000,
        "media_storage_bytes": 10000000,
        "webhook_deliveries_per_day": 7000,
        "schema_writes_per_day": 500,
    }
    patch_response = client.patch(
        "/v1/quotas",
        json={
            "org_id": org_id,
            "workspace_id": workspace_id,
            "dimensions": dimensions,
            "soft_threshold_percent": 85,
            "hard_enforcement": True,
            "overage_mode": "block",
            "updated_by_actor_id": "actor://conformance/admin",
        },
    )
    if patch_response.status_code != 200:
        return ContractResult("enterprise_quotas_usage", False, f"quota patch status={patch_response.status_code}")
    patch_data = patch_response.json()
    patched_quota_policy = patch_data.get("quota_policy")
    if patch_data.get("ok") is not True or not _is_quota_policy_shape(patched_quota_policy):
        return ContractResult("enterprise_quotas_usage", False, "invalid quota patch response shape")

    get_response = client.get(
        "/v1/quotas",
        params={"org_id": org_id, "workspace_id": workspace_id},
    )
    if get_response.status_code != 200:
        return ContractResult("enterprise_quotas_usage", False, f"quota get status={get_response.status_code}")
    get_data = get_response.json()
    fetched_quota_policy = get_data.get("quota_policy")
    if get_data.get("ok") is not True or not _is_quota_policy_shape(fetched_quota_policy):
        return ContractResult("enterprise_quotas_usage", False, "invalid quota get response shape")
    if fetched_quota_policy.get("quota_policy_id") != patched_quota_policy.get("quota_policy_id"):
        return ContractResult("enterprise_quotas_usage", False, "quota_policy_id mismatch between patch and get")

    summary_response = client.get(
        "/v1/usage/summary",
        params={"org_id": org_id, "workspace_id": workspace_id},
    )
    if summary_response.status_code != 200:
        return ContractResult("enterprise_quotas_usage", False, f"usage summary status={summary_response.status_code}")
    summary_data = summary_response.json()
    summary = summary_data.get("summary")
    if summary_data.get("ok") is not True or not _is_usage_summary_shape(summary):
        return ContractResult("enterprise_quotas_usage", False, "invalid usage summary response shape")
    if summary.get("org_id") != org_id or summary.get("workspace_id") != workspace_id:
        return ContractResult("enterprise_quotas_usage", False, "usage summary tenant scope mismatch")
    timeseries_response = client.get(
        "/v1/usage/timeseries",
        params={"org_id": org_id, "workspace_id": workspace_id, "window_days": 7},
    )
    if timeseries_response.status_code != 200:
        return ContractResult("enterprise_quotas_usage", False, f"usage timeseries status={timeseries_response.status_code}")
    timeseries_data = timeseries_response.json()
    series = timeseries_data.get("series")
    if timeseries_data.get("ok") is not True or not _is_usage_series_shape(series):
        return ContractResult("enterprise_quotas_usage", False, "invalid usage timeseries response shape")

    strict_dimensions = dict(dimensions)
    strict_dimensions["intents_per_day"] = 1
    strict_patch = client.patch(
        "/v1/quotas",
        json={
            "org_id": org_id,
            "workspace_id": workspace_id,
            "dimensions": strict_dimensions,
            "soft_threshold_percent": 80,
            "hard_enforcement": True,
            "overage_mode": "block",
            "updated_by_actor_id": "actor://conformance/admin",
        },
    )
    if strict_patch.status_code != 200:
        return ContractResult("enterprise_quotas_usage", False, f"strict quota patch status={strict_patch.status_code}")
    first_intent = client.post(
        "/v1/intents",
        json={
            "intent_type": "notify.message.v1",
            "correlation_id": str(uuid4()),
            "from_agent": "agent://conformance/sender",
            "to_agent": "agent://conformance/receiver",
            "payload": {
                "text": "quota baseline",
                "tenant": {"org_id": org_id, "workspace_id": workspace_id},
            },
        },
    )
    if first_intent.status_code != 200:
        return ContractResult("enterprise_quotas_usage", False, f"first strict quota intent status={first_intent.status_code}")
    second_intent = client.post(
        "/v1/intents",
        json={
            "intent_type": "notify.message.v1",
            "correlation_id": str(uuid4()),
            "from_agent": "agent://conformance/sender",
            "to_agent": "agent://conformance/receiver",
            "payload": {
                "text": "quota exceed",
                "tenant": {"org_id": org_id, "workspace_id": workspace_id},
            },
        },
    )
    if second_intent.status_code != 429:
        return ContractResult(
            "enterprise_quotas_usage",
            False,
            f"expected strict quota status=429 got={second_intent.status_code}",
        )
    return ContractResult("enterprise_quotas_usage", True, "ok")


def _check_enterprise_service_accounts_contract(client: httpx.Client) -> ContractResult:
    org_id, error = _create_enterprise_organization_for_contract(client, name="Conformance Service Accounts Org")
    if error:
        return ContractResult("enterprise_service_accounts", False, error)
    assert org_id is not None
    workspace_id, workspace_error = _create_enterprise_workspace_for_contract(
        client,
        org_id=org_id,
        name="Conformance Service Accounts Workspace",
    )
    if workspace_error:
        return ContractResult("enterprise_service_accounts", False, workspace_error)
    assert workspace_id is not None

    create_response = client.post(
        "/v1/service-accounts",
        json={
            "org_id": org_id,
            "workspace_id": workspace_id,
            "name": "conformance-runner",
            "description": "conformance managed service account",
            "created_by_actor_id": "actor://conformance/admin",
        },
    )
    if create_response.status_code != 200:
        return ContractResult("enterprise_service_accounts", False, f"service-account create status={create_response.status_code}")
    create_data = create_response.json()
    service_account = create_data.get("service_account")
    if create_data.get("ok") is not True or not _is_service_account_shape(service_account):
        return ContractResult("enterprise_service_accounts", False, "invalid service-account create response shape")
    service_account_id = service_account.get("service_account_id")
    assert isinstance(service_account_id, str)

    list_response = client.get(
        "/v1/service-accounts",
        params={"org_id": org_id, "workspace_id": workspace_id},
    )
    if list_response.status_code != 200:
        return ContractResult("enterprise_service_accounts", False, f"service-account list status={list_response.status_code}")
    list_data = list_response.json()
    service_accounts = list_data.get("service_accounts")
    if list_data.get("ok") is not True or not isinstance(service_accounts, list):
        return ContractResult("enterprise_service_accounts", False, "invalid service-account list response shape")
    if not any(isinstance(item, dict) and item.get("service_account_id") == service_account_id for item in service_accounts):
        return ContractResult("enterprise_service_accounts", False, "service-account list missing created account")

    key_create_response = client.post(
        f"/v1/service-accounts/{service_account_id}/keys",
        json={"created_by_actor_id": "actor://conformance/admin"},
    )
    if key_create_response.status_code != 200:
        return ContractResult("enterprise_service_accounts", False, f"service-account key create status={key_create_response.status_code}")
    key_create_data = key_create_response.json()
    created_key = key_create_data.get("key")
    if key_create_data.get("ok") is not True or not _is_service_account_key_shape(created_key):
        return ContractResult("enterprise_service_accounts", False, "invalid service-account key create response shape")
    key_id = created_key.get("key_id")
    assert isinstance(key_id, str)

    revoke_response = client.post(
        f"/v1/service-accounts/{service_account_id}/keys/{key_id}/revoke",
    )
    if revoke_response.status_code != 200:
        return ContractResult("enterprise_service_accounts", False, f"service-account key revoke status={revoke_response.status_code}")
    revoke_data = revoke_response.json()
    revoked_key = revoke_data.get("key")
    if revoke_data.get("ok") is not True or not isinstance(revoked_key, dict):
        return ContractResult("enterprise_service_accounts", False, "invalid service-account key revoke response shape")
    if revoked_key.get("status") != "revoked":
        return ContractResult("enterprise_service_accounts", False, "service-account key revoke did not set status=revoked")
    return ContractResult("enterprise_service_accounts", True, "ok")


def _check_enterprise_tenant_boundary_and_permission_contract(client: httpx.Client) -> ContractResult:
    org_a, error_a = _create_enterprise_organization_for_contract(client, name="Conformance Tenant A")
    if error_a:
        return ContractResult("enterprise_tenant_boundary_permission", False, error_a)
    assert org_a is not None
    workspace_a, workspace_error_a = _create_enterprise_workspace_for_contract(
        client,
        org_id=org_a,
        name="Conformance Tenant A Workspace",
    )
    if workspace_error_a:
        return ContractResult("enterprise_tenant_boundary_permission", False, workspace_error_a)
    assert workspace_a is not None

    org_b, error_b = _create_enterprise_organization_for_contract(client, name="Conformance Tenant B")
    if error_b:
        return ContractResult("enterprise_tenant_boundary_permission", False, error_b)
    assert org_b is not None
    workspace_b, workspace_error_b = _create_enterprise_workspace_for_contract(
        client,
        org_id=org_b,
        name="Conformance Tenant B Workspace",
    )
    if workspace_error_b:
        return ContractResult("enterprise_tenant_boundary_permission", False, workspace_error_b)
    assert workspace_b is not None

    boundary_response = client.get(
        "/v1/quotas",
        params={"org_id": org_a, "workspace_id": workspace_b},
    )
    if boundary_response.status_code != 403:
        return ContractResult(
            "enterprise_tenant_boundary_permission",
            False,
            f"expected tenant boundary status=403 got={boundary_response.status_code}",
        )

    permission_response = client.post(
        "/v1/organizations",
        headers={"Authorization": ""},
        json={"name": "Conformance Unauthorized Org", "requested_by_actor_id": "actor://conformance/unauthorized"},
    )
    if permission_response.status_code != 401:
        return ContractResult(
            "enterprise_tenant_boundary_permission",
            False,
            f"expected permission status=401 got={permission_response.status_code}",
        )

    return ContractResult("enterprise_tenant_boundary_permission", True, "ok")


def _check_webhooks_subscriptions_contract(client: httpx.Client) -> ContractResult:
    owner_agent = "agent://conformance/owner"
    upsert_response = client.post(
        "/v1/webhooks/subscriptions",
        json={
            "callback_url": "https://integrator.example/webhooks/axme",
            "event_types": ["inbox.thread_created"],
            "active": True,
            "description": "conformance subscription",
        },
    )
    if upsert_response.status_code != 200:
        return ContractResult("webhooks_subscriptions", False, f"upsert status={upsert_response.status_code}")

    upsert_data = upsert_response.json()
    subscription = upsert_data.get("subscription")
    if upsert_data.get("ok") is not True or not _is_webhook_subscription_shape(subscription):
        return ContractResult("webhooks_subscriptions", False, "invalid upsert response shape")

    subscription_id = subscription.get("subscription_id")
    if not _is_uuid(subscription_id):
        return ContractResult("webhooks_subscriptions", False, "invalid subscription_id in upsert response")

    list_response = client.get("/v1/webhooks/subscriptions", params={"owner_agent": owner_agent})
    if list_response.status_code != 200:
        return ContractResult("webhooks_subscriptions", False, f"list status={list_response.status_code}")
    list_data = list_response.json()
    subscriptions = list_data.get("subscriptions")
    if list_data.get("ok") is not True or not isinstance(subscriptions, list):
        return ContractResult("webhooks_subscriptions", False, "invalid list response shape")
    if subscriptions and not _is_webhook_subscription_shape(subscriptions[0]):
        return ContractResult("webhooks_subscriptions", False, "invalid subscription item shape")

    delete_response = client.delete(
        f"/v1/webhooks/subscriptions/{subscription_id}",
        params={"owner_agent": owner_agent},
    )
    if delete_response.status_code != 200:
        return ContractResult("webhooks_subscriptions", False, f"delete status={delete_response.status_code}")
    delete_data = delete_response.json()
    if delete_data.get("ok") is not True:
        return ContractResult("webhooks_subscriptions", False, "delete response missing ok=true")
    if delete_data.get("subscription_id") != subscription_id:
        return ContractResult("webhooks_subscriptions", False, "deleted subscription_id mismatch")
    if not isinstance(delete_data.get("revoked_at"), str):
        return ContractResult("webhooks_subscriptions", False, "delete response missing revoked_at")

    return ContractResult("webhooks_subscriptions", True, "ok")


def _check_webhooks_events_contract(client: httpx.Client) -> ContractResult:
    owner_agent = "agent://conformance/owner"
    events_response = client.post(
        "/v1/webhooks/events",
        params={"owner_agent": owner_agent},
        json={
            "event_type": "inbox.thread_created",
            "source": "conformance",
            "payload": {"thread_id": str(uuid4())},
        },
    )
    if events_response.status_code != 200:
        return ContractResult("webhooks_events", False, f"events status={events_response.status_code}")

    events_data = events_response.json()
    event_id = events_data.get("event_id")
    if events_data.get("ok") is not True or not _is_uuid(event_id):
        return ContractResult("webhooks_events", False, "invalid events response shape")
    if not _has_webhook_delivery_counters(events_data):
        return ContractResult("webhooks_events", False, "events response missing delivery counters")

    replay_response = client.post(
        f"/v1/webhooks/events/{event_id}/replay",
        params={"owner_agent": owner_agent},
    )
    if replay_response.status_code != 200:
        return ContractResult("webhooks_events", False, f"replay status={replay_response.status_code}")

    replay_data = replay_response.json()
    if replay_data.get("ok") is not True:
        return ContractResult("webhooks_events", False, "replay response missing ok=true")
    if replay_data.get("event_id") != event_id:
        return ContractResult("webhooks_events", False, "replay response event_id mismatch")
    if not isinstance(replay_data.get("replayed_at"), str):
        return ContractResult("webhooks_events", False, "replay response missing replayed_at")
    if not _has_webhook_delivery_counters(replay_data):
        return ContractResult("webhooks_events", False, "replay response missing delivery counters")

    return ContractResult("webhooks_events", True, "ok")


def _mcp_call(client: httpx.Client, payload: dict[str, object]) -> tuple[dict[str, object], str | None]:
    response = client.post("/mcp", json=payload)
    if response.status_code != 200:
        return {}, f"unexpected status={response.status_code}"
    data = response.json()
    if not isinstance(data, dict):
        return {}, "invalid rpc payload type"
    error = data.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        code = error.get("code")
        return {}, f"rpc error code={code} message={message}"
    return data, None


def _build_intent_create_payload(*, correlation_id: str, reply_to: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "intent_type": "notify.message.v1",
        "correlation_id": correlation_id,
        "from_agent": "agent://conformance/sender",
        "to_agent": "agent://conformance/receiver",
        "payload": {"text": "hello from conformance"},
    }
    if isinstance(reply_to, str):
        payload["reply_to"] = reply_to
    return payload


def _is_inbox_change_shape(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    cursor = value.get("cursor")
    thread = value.get("thread")
    return isinstance(cursor, str) and len(cursor) >= 3 and _is_thread_shape(thread)


def _is_webhook_subscription_shape(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    required_keys = {
        "subscription_id",
        "owner_agent",
        "callback_url",
        "event_types",
        "active",
        "created_at",
        "updated_at",
        "revoked_at",
        "secret_hint",
    }
    if not required_keys.issubset(value.keys()):
        return False
    if not _is_uuid(value.get("subscription_id")):
        return False
    event_types = value.get("event_types")
    return isinstance(event_types, list) and len(event_types) >= 1


def _has_webhook_delivery_counters(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    counter_keys = ["queued_deliveries", "processed_deliveries", "delivered", "pending", "dead_lettered"]
    for key in counter_keys:
        counter = value.get(key)
        if not isinstance(counter, int) or counter < 0:
            return False
    return True


def _is_quota_policy_shape(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    required_keys = {
        "quota_policy_id",
        "org_id",
        "workspace_id",
        "dimensions",
        "soft_threshold_percent",
        "overage_mode",
        "updated_at",
    }
    if not required_keys.issubset(value.keys()):
        return False
    if not _is_uuid(value.get("quota_policy_id")):
        return False
    if not _is_uuid(value.get("org_id")):
        return False
    if not _is_uuid(value.get("workspace_id")):
        return False
    dimensions = value.get("dimensions")
    if not isinstance(dimensions, dict):
        return False
    for key in QUOTA_DIMENSION_KEYS:
        dimension = dimensions.get(key)
        if not isinstance(dimension, int) or dimension < 0:
            return False
    return True


def _is_usage_summary_shape(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    required_keys = {"org_id", "workspace_id", "window_start", "window_end", "dimensions"}
    if not required_keys.issubset(value.keys()):
        return False
    if not _is_uuid(value.get("org_id")):
        return False
    if not _is_uuid(value.get("workspace_id")):
        return False
    if not isinstance(value.get("window_start"), str):
        return False
    if not isinstance(value.get("window_end"), str):
        return False
    dimensions = value.get("dimensions")
    if not isinstance(dimensions, dict):
        return False
    for key in QUOTA_DIMENSION_KEYS:
        if not _is_usage_dimension_window(dimensions.get(key)):
            return False
    return True


def _is_usage_dimension_window(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    if not isinstance(value.get("used"), int) or value["used"] < 0:
        return False
    if not isinstance(value.get("limit"), int) or value["limit"] < 0:
        return False
    return isinstance(value.get("remaining"), int)


def _is_usage_series_shape(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    if not _is_uuid(value.get("org_id")):
        return False
    if not _is_uuid(value.get("workspace_id")):
        return False
    if value.get("granularity") not in {"hour", "day"}:
        return False
    points = value.get("points")
    if not isinstance(points, list):
        return False
    for point in points:
        if not isinstance(point, dict):
            return False
        if not isinstance(point.get("at"), str):
            return False
        dimensions = point.get("dimensions")
        if not isinstance(dimensions, dict):
            return False
        for key in QUOTA_DIMENSION_KEYS:
            quantity = dimensions.get(key)
            if not isinstance(quantity, int) or quantity < 0:
                return False
    return True


def _is_service_account_shape(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    required_keys = {
        "service_account_id",
        "org_id",
        "workspace_id",
        "name",
        "status",
        "created_by_actor_id",
        "created_at",
        "updated_at",
    }
    if not required_keys.issubset(value.keys()):
        return False
    if not isinstance(value.get("service_account_id"), str):
        return False
    if not _is_uuid(value.get("org_id")):
        return False
    if not _is_uuid(value.get("workspace_id")):
        return False
    return isinstance(value.get("name"), str) and isinstance(value.get("status"), str)


def _is_service_account_key_shape(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    required_keys = {"key_id", "service_account_id", "key_hint", "status", "created_at", "token"}
    if not required_keys.issubset(value.keys()):
        return False
    return (
        isinstance(value.get("key_id"), str)
        and isinstance(value.get("service_account_id"), str)
        and isinstance(value.get("key_hint"), str)
        and isinstance(value.get("token"), str)
        and value.get("status") == "active"
    )


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
