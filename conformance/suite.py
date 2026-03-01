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
            _check_trace_header_contract(client),
            _check_intent_create_contract(client),
            _check_intent_create_idempotency_contract(client),
            _check_inbox_list_contract(client),
            _check_inbox_reply_contract(client),
            _check_inbox_changes_pagination_contract(client),
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
            _check_webhooks_subscriptions_contract(client),
            _check_webhooks_events_contract(client),
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


def _build_intent_create_payload(*, correlation_id: str) -> dict[str, object]:
    return {
        "intent_type": "notify.message.v1",
        "correlation_id": correlation_id,
        "from_agent": "agent://conformance/sender",
        "to_agent": "agent://conformance/receiver",
        "payload": {"text": "hello from conformance"},
    }


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
