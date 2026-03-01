from __future__ import annotations

import json
from uuid import uuid4

import httpx

from conformance import run_contract_suite


def test_run_contract_suite_happy_path() -> None:
    idempotency_cache: dict[str, tuple[str, str]] = {}
    intents: dict[str, dict[str, object]] = {}
    invites: dict[str, dict[str, object]] = {}
    media_uploads: dict[str, dict[str, object]] = {}
    schemas: dict[str, dict[str, object]] = {}
    users_by_owner: dict[str, dict[str, object]] = {}
    user_owner_by_normalized_nick: dict[str, str] = {}
    invite_counter = 0
    media_counter = 0
    thread_id = "11111111-1111-4111-8111-111111111111"
    intent_id = "22222222-2222-4222-8222-222222222222"
    event_id = "33333333-3333-4333-8333-333333333333"
    subscription_id = "44444444-4444-4444-8444-444444444444"
    approval_id = "55555555-5555-4555-8555-555555555555"

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
    approval_response = {
        "ok": True,
        "approval": {
            "approval_id": approval_id,
            "decision": "approve",
            "comment": "approved by conformance",
            "decided_at": "2026-02-28T00:00:02Z",
        },
    }
    capabilities_response = {
        "ok": True,
        "capabilities": ["inbox", "intents", "webhooks"],
        "supported_intent_types": ["intent.ask.v1", "intent.notify.v1"],
    }

    def normalize_nick(value: str) -> str:
        return value.strip().lstrip("@").lower()

    def make_public_address(normalized_nick: str) -> str:
        return f"{normalized_nick}@ax"

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal invite_counter, media_counter
        if request.url.path == "/health":
            trace_id = request.headers.get("x-trace-id")
            if trace_id is not None:
                assert isinstance(trace_id, str) and len(trace_id) > 0
            return httpx.Response(200, json={"ok": True})
        if request.url.path.startswith("/v1/intents/") and request.method == "GET":
            intent_id_from_path = request.url.path.split("/v1/intents/")[1]
            if intent_id_from_path not in intents:
                return httpx.Response(404, json={"error": "not_found"})
            return httpx.Response(200, json={"ok": True, "intent": intents[intent_id_from_path]})
        if request.url.path == "/v1/intents":
            body = json.loads(request.content.decode("utf-8"))

            def _store_intent(intent_id_value: str) -> None:
                intents[intent_id_value] = {
                    "intent_id": intent_id_value,
                    "status": "accepted",
                    "created_at": "2026-02-28T00:00:00Z",
                    "updated_at": "2026-02-28T00:00:01Z",
                    "intent_type": body.get("intent_type", "notify.message.v1"),
                    "correlation_id": body.get("correlation_id", str(uuid4())),
                    "from_agent": body.get("from_agent", "agent://conformance/sender"),
                    "to_agent": body.get("to_agent", "agent://conformance/receiver"),
                    "payload": body.get("payload") if isinstance(body.get("payload"), dict) else {},
                }

            idempotency_key = request.headers.get("idempotency-key")
            if idempotency_key:
                payload_signature = json.dumps(body, sort_keys=True)
                if idempotency_key in idempotency_cache:
                    previous_signature, previous_intent_id = idempotency_cache[idempotency_key]
                    if previous_signature != payload_signature:
                        return httpx.Response(409, json={"error": "idempotency_conflict"})
                    if previous_intent_id not in intents:
                        _store_intent(previous_intent_id)
                    return httpx.Response(200, json={"intent_id": previous_intent_id})
                new_intent_id = str(uuid4())
                idempotency_cache[idempotency_key] = (payload_signature, new_intent_id)
                _store_intent(new_intent_id)
                return httpx.Response(200, json={"intent_id": new_intent_id})
            generated_intent_id = str(uuid4())
            _store_intent(generated_intent_id)
            return httpx.Response(200, json={"intent_id": generated_intent_id})
        if request.url.path == "/v1/inbox":
            assert request.url.params.get("owner_agent") == "agent://conformance/owner"
            return httpx.Response(200, json={"ok": True, "threads": [thread_payload]})
        if request.url.path == f"/v1/inbox/{thread_id}" and request.method == "GET":
            assert request.url.params.get("owner_agent") == "agent://conformance/owner"
            return httpx.Response(200, json={"ok": True, "thread": thread_payload})
        if request.url.path == f"/v1/inbox/{thread_id}/reply":
            assert request.url.params.get("owner_agent") == "agent://conformance/owner"
            body = json.loads(request.content.decode("utf-8"))
            assert body["message"] == "ack from conformance"
            return httpx.Response(200, json={"ok": True, "thread": thread_payload})
        if request.url.path == f"/v1/inbox/{thread_id}/delegate" and request.method == "POST":
            assert request.url.params.get("owner_agent") == "agent://conformance/owner"
            body = json.loads(request.content.decode("utf-8"))
            assert body["delegate_to"] == "agent://conformance/delegate"
            assert body["note"] == "handoff"
            delegated_thread = dict(thread_payload)
            delegated_thread["status"] = "active"
            return httpx.Response(200, json={"ok": True, "thread": delegated_thread})
        if request.url.path == f"/v1/inbox/{thread_id}/approve" and request.method == "POST":
            assert request.url.params.get("owner_agent") == "agent://conformance/owner"
            body = json.loads(request.content.decode("utf-8"))
            assert body["comment"] == "approved in conformance"
            approved_thread = dict(thread_payload)
            approved_thread["status"] = "active"
            return httpx.Response(200, json={"ok": True, "thread": approved_thread})
        if request.url.path == f"/v1/inbox/{thread_id}/messages/delete" and request.method == "POST":
            assert request.url.params.get("owner_agent") == "agent://conformance/owner"
            body = json.loads(request.content.decode("utf-8"))
            assert body["mode"] == "self"
            assert body["limit"] == 1
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "thread": thread_payload,
                    "mode": "self",
                    "deleted_count": 1,
                    "message_ids": ["msg-1"],
                },
            )
        if request.url.path == "/v1/inbox/changes":
            assert request.url.params.get("owner_agent") == "agent://conformance/owner"
            if request.url.params.get("cursor") == "cur-2":
                return httpx.Response(200, json=changes_follow_up_payload)
            return httpx.Response(200, json=changes_payload)
        if request.url.path.startswith("/v1/approvals/") and request.url.path.endswith("/decision"):
            body = json.loads(request.content.decode("utf-8"))
            assert body["decision"] == "approve"
            assert body["comment"] == "approved by conformance"
            return httpx.Response(200, json=approval_response)
        if request.url.path == "/v1/capabilities":
            return httpx.Response(200, json=capabilities_response)
        if request.url.path == "/v1/invites/create" and request.method == "POST":
            body = json.loads(request.content.decode("utf-8"))
            assert body["owner_agent"] == "agent://conformance/owner"
            invite_counter += 1
            token = f"invite-token-{invite_counter:04d}"
            invite_state = {
                "token": token,
                "owner_agent": "agent://conformance/owner",
                "recipient_hint": body.get("recipient_hint"),
                "status": "pending",
                "created_at": "2026-02-28T00:00:00Z",
                "expires_at": "2026-03-01T00:00:00Z",
                "accepted_at": None,
                "accepted_owner_agent": None,
                "nick": None,
                "public_address": None,
            }
            invites[token] = invite_state
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "token": token,
                    "invite_url": f"https://invite.example/{token}",
                    "owner_agent": invite_state["owner_agent"],
                    "recipient_hint": invite_state["recipient_hint"],
                    "status": invite_state["status"],
                    "created_at": invite_state["created_at"],
                    "expires_at": invite_state["expires_at"],
                },
            )
        if request.url.path.startswith("/v1/invites/") and request.method == "GET":
            token = request.url.path.split("/")[-1]
            if token not in invites:
                return httpx.Response(404, json={"error": "not_found"})
            invite_state = invites[token]
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "token": token,
                    "owner_agent": invite_state["owner_agent"],
                    "recipient_hint": invite_state["recipient_hint"],
                    "status": invite_state["status"],
                    "created_at": invite_state["created_at"],
                    "expires_at": invite_state["expires_at"],
                    "accepted_at": invite_state["accepted_at"],
                    "accepted_owner_agent": invite_state["accepted_owner_agent"],
                    "nick": invite_state["nick"],
                    "public_address": invite_state["public_address"],
                },
            )
        if request.url.path.startswith("/v1/invites/") and request.url.path.endswith("/accept") and request.method == "POST":
            token = request.url.path.split("/")[-2]
            body = json.loads(request.content.decode("utf-8"))
            assert body["nick"] == "@Invite.Conformance.User"
            if token not in invites:
                return httpx.Response(404, json={"error": "not_found"})
            invites[token].update(
                {
                    "status": "accepted",
                    "accepted_at": "2026-02-28T00:00:10Z",
                    "accepted_owner_agent": "agent://conformance/accepted",
                    "nick": "@Invite.Conformance.User",
                    "public_address": "invite.conformance.user@ax",
                }
            )
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "token": token,
                    "status": "accepted",
                    "invite_owner_agent": "agent://conformance/owner",
                    "user_id": "66666666-6666-4666-8666-666666666666",
                    "owner_agent": "agent://conformance/accepted",
                    "nick": "@Invite.Conformance.User",
                    "public_address": "invite.conformance.user@ax",
                    "display_name": body.get("display_name"),
                    "accepted_at": "2026-02-28T00:00:10Z",
                    "registry_bind_status": "propagated",
                },
            )
        if request.url.path == "/v1/media/create-upload" and request.method == "POST":
            body = json.loads(request.content.decode("utf-8"))
            assert body["owner_agent"] == "agent://conformance/owner"
            assert body["filename"] == "contract.pdf"
            assert body["mime_type"] == "application/pdf"
            assert body["size_bytes"] == 12345
            media_counter += 1
            upload_id = f"77777777-7777-4777-8777-{media_counter:012d}"
            media_uploads[upload_id] = {
                "upload_id": upload_id,
                "owner_agent": "agent://conformance/owner",
                "bucket": "axme-media",
                "object_path": f"agent-conformance/contract-{media_counter}.pdf",
                "mime_type": "application/pdf",
                "filename": "contract.pdf",
                "size_bytes": 12345,
                "sha256": None,
                "status": "pending",
                "created_at": "2026-02-28T00:00:00Z",
                "expires_at": "2026-03-01T00:00:00Z",
                "finalized_at": None,
                "download_url": None,
                "preview_url": None,
            }
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "upload_id": upload_id,
                    "owner_agent": "agent://conformance/owner",
                    "bucket": "axme-media",
                    "object_path": f"agent-conformance/contract-{media_counter}.pdf",
                    "upload_url": f"https://upload.example/media/{media_counter}",
                    "status": "pending",
                    "expires_at": "2026-03-01T00:00:00Z",
                    "max_size_bytes": 10485760,
                },
            )
        if request.url.path.startswith("/v1/media/") and request.method == "GET":
            upload_id = request.url.path.split("/")[-1]
            if upload_id not in media_uploads:
                return httpx.Response(404, json={"error": "not_found"})
            return httpx.Response(200, json={"ok": True, "upload": media_uploads[upload_id]})
        if request.url.path == "/v1/media/finalize-upload" and request.method == "POST":
            body = json.loads(request.content.decode("utf-8"))
            upload_id = body["upload_id"]
            assert body["size_bytes"] == 12345
            if upload_id not in media_uploads:
                return httpx.Response(404, json={"error": "not_found"})
            media_uploads[upload_id].update(
                {
                    "status": "ready",
                    "finalized_at": "2026-02-28T00:00:10Z",
                    "download_url": f"https://download.example/media/{upload_id}",
                    "preview_url": f"https://preview.example/media/{upload_id}",
                }
            )
            upload = media_uploads[upload_id]
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "upload_id": upload_id,
                    "owner_agent": upload["owner_agent"],
                    "bucket": upload["bucket"],
                    "object_path": upload["object_path"],
                    "mime_type": upload["mime_type"],
                    "size_bytes": upload["size_bytes"],
                    "sha256": upload["sha256"],
                    "status": "ready",
                    "finalized_at": upload["finalized_at"],
                },
            )
        if request.url.path == "/v1/schemas" and request.method == "POST":
            body = json.loads(request.content.decode("utf-8"))
            semantic_type = body["semantic_type"]
            schemas[semantic_type] = {
                "semantic_type": semantic_type,
                "schema_ref": f"schema://{semantic_type}",
                "schema_hash": "a" * 64,
                "compatibility_mode": body["compatibility_mode"],
                "scope": body.get("scope", "tenant"),
                "owner_agent": "agent://conformance/owner",
                "active": body.get("active", True),
                "schema_json": body["schema_json"],
                "created_at": "2026-02-28T00:00:00Z",
                "updated_at": "2026-02-28T00:00:01Z",
            }
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "schema": {
                        "semantic_type": schemas[semantic_type]["semantic_type"],
                        "schema_ref": schemas[semantic_type]["schema_ref"],
                        "schema_hash": schemas[semantic_type]["schema_hash"],
                        "compatibility_mode": schemas[semantic_type]["compatibility_mode"],
                        "scope": schemas[semantic_type]["scope"],
                        "owner_agent": schemas[semantic_type]["owner_agent"],
                        "active": schemas[semantic_type]["active"],
                        "created_at": schemas[semantic_type]["created_at"],
                        "updated_at": schemas[semantic_type]["updated_at"],
                    },
                },
            )
        if request.url.path.startswith("/v1/schemas/") and request.method == "GET":
            semantic_type = request.url.path.split("/v1/schemas/")[1]
            if semantic_type not in schemas:
                return httpx.Response(404, json={"error": "not_found"})
            schema = schemas[semantic_type]
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "schema": {
                        "semantic_type": schema["semantic_type"],
                        "schema_ref": schema["schema_ref"],
                        "schema_hash": schema["schema_hash"],
                        "compatibility_mode": schema["compatibility_mode"],
                        "scope": schema["scope"],
                        "owner_agent": schema["owner_agent"],
                        "active": schema["active"],
                        "schema_json": schema["schema_json"],
                        "created_at": schema["created_at"],
                        "updated_at": schema["updated_at"],
                    },
                },
            )
        if request.url.path == "/v1/users/check-nick" and request.method == "GET":
            nick_value = request.url.params.get("nick")
            assert isinstance(nick_value, str) and len(nick_value) > 0
            normalized_nick = normalize_nick(nick_value)
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "nick": f"@{normalized_nick}",
                    "normalized_nick": normalized_nick,
                    "public_address": make_public_address(normalized_nick),
                    "available": normalized_nick not in user_owner_by_normalized_nick,
                },
            )
        if request.url.path == "/v1/users/register-nick" and request.method == "POST":
            body = json.loads(request.content.decode("utf-8"))
            normalized_nick = normalize_nick(body["nick"])
            if normalized_nick in user_owner_by_normalized_nick:
                return httpx.Response(409, json={"error": "nick already registered"})
            user_id = str(uuid4())
            owner_agent = f"agent://user/{user_id}"
            created_at = "2026-02-28T00:00:00Z"
            record = {
                "user_id": user_id,
                "owner_agent": owner_agent,
                "nick": f"@{normalized_nick}",
                "normalized_nick": normalized_nick,
                "public_address": make_public_address(normalized_nick),
                "display_name": body.get("display_name"),
                "phone": body.get("phone"),
                "email": body.get("email"),
                "created_at": created_at,
                "updated_at": created_at,
            }
            users_by_owner[owner_agent] = record
            user_owner_by_normalized_nick[normalized_nick] = owner_agent
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "user_id": record["user_id"],
                    "owner_agent": record["owner_agent"],
                    "nick": record["nick"],
                    "public_address": record["public_address"],
                    "display_name": record["display_name"],
                    "phone": record["phone"],
                    "email": record["email"],
                    "created_at": record["created_at"],
                },
            )
        if request.url.path == "/v1/users/rename-nick" and request.method == "POST":
            body = json.loads(request.content.decode("utf-8"))
            owner_agent = body["owner_agent"]
            if owner_agent not in users_by_owner:
                return httpx.Response(404, json={"error": "owner not found"})
            user = users_by_owner[owner_agent]
            normalized_nick = normalize_nick(body["nick"])
            existing_owner = user_owner_by_normalized_nick.get(normalized_nick)
            if existing_owner is not None and existing_owner != owner_agent:
                return httpx.Response(409, json={"error": "nick already registered"})
            old_normalized_nick = user["normalized_nick"]
            if isinstance(old_normalized_nick, str):
                user_owner_by_normalized_nick.pop(old_normalized_nick, None)
            user_owner_by_normalized_nick[normalized_nick] = owner_agent
            user["nick"] = f"@{normalized_nick}"
            user["normalized_nick"] = normalized_nick
            user["public_address"] = make_public_address(normalized_nick)
            if "display_name" in body:
                user["display_name"] = body.get("display_name")
            if "phone" in body:
                user["phone"] = body.get("phone")
            if "email" in body:
                user["email"] = body.get("email")
            user["updated_at"] = "2026-02-28T00:00:01Z"
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "user_id": user["user_id"],
                    "owner_agent": user["owner_agent"],
                    "nick": user["nick"],
                    "public_address": user["public_address"],
                    "display_name": user["display_name"],
                    "phone": user["phone"],
                    "email": user["email"],
                    "renamed_at": user["updated_at"],
                },
            )
        if request.url.path == "/v1/users/profile" and request.method == "GET":
            owner_agent = request.url.params.get("owner_agent")
            if owner_agent is None or owner_agent not in users_by_owner:
                return httpx.Response(404, json={"error": "owner not found"})
            user = users_by_owner[owner_agent]
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "user_id": user["user_id"],
                    "owner_agent": user["owner_agent"],
                    "nick": user["nick"],
                    "normalized_nick": user["normalized_nick"],
                    "public_address": user["public_address"],
                    "display_name": user["display_name"],
                    "phone": user["phone"],
                    "email": user["email"],
                    "updated_at": user["updated_at"],
                },
            )
        if request.url.path == "/v1/users/profile/update" and request.method == "POST":
            body = json.loads(request.content.decode("utf-8"))
            owner_agent = body["owner_agent"]
            if owner_agent not in users_by_owner:
                return httpx.Response(404, json={"error": "owner not found"})
            user = users_by_owner[owner_agent]
            if "nick" in body and body["nick"] is not None:
                normalized_nick = normalize_nick(body["nick"])
                existing_owner = user_owner_by_normalized_nick.get(normalized_nick)
                if existing_owner is not None and existing_owner != owner_agent:
                    return httpx.Response(409, json={"error": "nick already registered"})
                old_normalized_nick = user["normalized_nick"]
                if isinstance(old_normalized_nick, str):
                    user_owner_by_normalized_nick.pop(old_normalized_nick, None)
                user_owner_by_normalized_nick[normalized_nick] = owner_agent
                user["nick"] = f"@{normalized_nick}"
                user["normalized_nick"] = normalized_nick
                user["public_address"] = make_public_address(normalized_nick)
            if "display_name" in body:
                user["display_name"] = body.get("display_name")
            if "phone" in body:
                user["phone"] = body.get("phone")
            if "email" in body:
                user["email"] = body.get("email")
            user["updated_at"] = "2026-02-28T00:00:03Z"
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "user_id": user["user_id"],
                    "owner_agent": user["owner_agent"],
                    "nick": user["nick"],
                    "normalized_nick": user["normalized_nick"],
                    "public_address": user["public_address"],
                    "display_name": user["display_name"],
                    "phone": user["phone"],
                    "email": user["email"],
                    "updated_at": user["updated_at"],
                },
            )
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
    assert len(results) == 29
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
    assert len(results) == 29
    assert not results[0].passed
    assert not results[1].passed
    assert not results[2].passed
    assert not results[3].passed
    assert not results[4].passed
    assert not results[5].passed
    assert not results[6].passed
    assert not results[7].passed
    assert not results[8].passed
    assert not results[9].passed
    assert not results[10].passed
    assert not results[11].passed
    assert not results[12].passed
    assert not results[13].passed
    assert not results[14].passed
    assert not results[15].passed
    assert not results[16].passed
    assert not results[17].passed
    assert not results[18].passed
    assert not results[19].passed
    assert not results[20].passed
    assert not results[21].passed
    assert not results[22].passed
    assert not results[23].passed
    assert not results[24].passed
    assert not results[25].passed
    assert not results[26].passed
    assert not results[27].passed
    assert not results[28].passed
