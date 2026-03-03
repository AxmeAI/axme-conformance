from __future__ import annotations

import json
from uuid import uuid4

import httpx

from conformance import run_contract_suite, run_mcp_contract_suite


def test_run_contract_suite_happy_path() -> None:
    idempotency_cache: dict[str, tuple[str, str]] = {}
    intents: dict[str, dict[str, object]] = {}
    intent_events: dict[str, list[dict[str, object]]] = {}
    reply_threads_by_owner: dict[str, list[dict[str, object]]] = {}
    invites: dict[str, dict[str, object]] = {}
    media_uploads: dict[str, dict[str, object]] = {}
    schemas: dict[str, dict[str, object]] = {}
    users_by_owner: dict[str, dict[str, object]] = {}
    user_owner_by_normalized_nick: dict[str, str] = {}
    organizations: dict[str, dict[str, object]] = {}
    workspaces: dict[str, dict[str, object]] = {}
    access_requests: dict[str, dict[str, object]] = {}
    quota_policies: dict[tuple[str, str], dict[str, object]] = {}
    service_accounts: dict[str, dict[str, object]] = {}
    service_account_keys: dict[str, dict[str, object]] = {}
    intent_usage_by_scope: dict[tuple[str, str], int] = {}
    principals: dict[str, dict[str, object]] = {}
    aliases: dict[str, dict[str, object]] = {}
    endpoint_routes: dict[str, dict[str, object]] = {}
    transport_bindings: dict[str, dict[str, object]] = {}
    deliveries: dict[str, dict[str, object]] = {}
    reconcile_events: list[dict[str, object]] = []
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

    def has_authorization(request: httpx.Request) -> bool:
        authorization = request.headers.get("authorization")
        return isinstance(authorization, str) and authorization.strip() != ""

    def build_usage_window(limit: int) -> dict[str, int]:
        used = min(5, limit)
        return {"used": used, "limit": limit, "remaining": limit - used}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal invite_counter, media_counter
        if request.url.path == "/health":
            trace_id = request.headers.get("x-trace-id")
            if trace_id is not None:
                assert isinstance(trace_id, str) and len(trace_id) > 0
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/v1/organizations" and request.method == "POST":
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            body = json.loads(request.content.decode("utf-8"))
            org_id = str(uuid4())
            organization = {
                "org_id": org_id,
                "name": body["name"],
                "legal_name": body.get("legal_name"),
                "primary_domain": body.get("primary_domain"),
                "status": "active",
                "metadata": body.get("metadata", {}),
                "created_at": "2026-02-28T00:00:00Z",
                "updated_at": "2026-02-28T00:00:00Z",
                "workspaces_count": 0,
                "members_count": 0,
            }
            organizations[org_id] = organization
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "organization": {
                        "org_id": organization["org_id"],
                        "name": organization["name"],
                        "legal_name": organization["legal_name"],
                        "primary_domain": organization["primary_domain"],
                        "status": organization["status"],
                        "metadata": organization["metadata"],
                        "created_at": organization["created_at"],
                        "updated_at": organization["updated_at"],
                    },
                },
            )
        if request.url.path.startswith("/v1/organizations/"):
            parts = [part for part in request.url.path.split("/") if part]
            if len(parts) >= 3 and parts[0] == "v1" and parts[1] == "organizations":
                org_id_from_path = parts[2]
                organization = organizations.get(org_id_from_path)
                if organization is None:
                    return httpx.Response(404, json={"error": "not_found"})
                if len(parts) == 3 and request.method == "GET":
                    return httpx.Response(
                        200,
                        json={
                            "ok": True,
                            "organization": {
                                "org_id": organization["org_id"],
                                "name": organization["name"],
                                "legal_name": organization["legal_name"],
                                "primary_domain": organization["primary_domain"],
                                "status": organization["status"],
                                "metadata": organization["metadata"],
                                "created_at": organization["created_at"],
                                "updated_at": organization["updated_at"],
                                "workspaces_count": organization["workspaces_count"],
                                "members_count": organization["members_count"],
                            },
                        },
                    )
                if len(parts) == 4 and parts[3] == "workspaces" and request.method == "POST":
                    if not has_authorization(request):
                        return httpx.Response(401, json={"error": "unauthorized"})
                    body = json.loads(request.content.decode("utf-8"))
                    if body.get("org_id") != org_id_from_path:
                        return httpx.Response(422, json={"error": "org mismatch"})
                    workspace_id = str(uuid4())
                    workspace = {
                        "workspace_id": workspace_id,
                        "org_id": org_id_from_path,
                        "name": body["name"],
                        "environment": body["environment"],
                        "status": "active",
                        "region": body.get("region"),
                        "created_at": "2026-02-28T00:00:00Z",
                        "updated_at": "2026-02-28T00:00:01Z",
                    }
                    workspaces[workspace_id] = workspace
                    organization["workspaces_count"] = int(organization["workspaces_count"]) + 1
                    organization["updated_at"] = "2026-02-28T00:00:01Z"
                    return httpx.Response(200, json={"ok": True, "workspace": workspace})
        if request.url.path == "/v1/access-requests" and request.method == "POST":
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            body = json.loads(request.content.decode("utf-8"))
            access_request_id = str(uuid4())
            expires_at = body.get("expires_at") if isinstance(body.get("expires_at"), str) else None
            is_expired = isinstance(expires_at, str) and expires_at <= "2026-02-28T00:00:00Z"
            access_request = {
                "access_request_id": access_request_id,
                "request_type": body["request_type"],
                "state": "expired" if is_expired else "pending",
                "requester_actor_id": body["requester_actor_id"],
                "org_id": body.get("org_id"),
                "workspace_id": body.get("workspace_id"),
                "requested_role": body.get("requested_role"),
                "company_name": body.get("company_name"),
                "justification": body.get("justification"),
                "reviewer_actor_id": None,
                "review_comment": None,
                "reviewed_at": None,
                "expires_at": expires_at,
                "created_at": "2026-02-28T00:00:00Z",
                "updated_at": "2026-02-28T00:00:00Z",
            }
            access_requests[access_request_id] = access_request
            return httpx.Response(200, json={"ok": True, "access_request": access_request})
        if request.url.path == "/v1/access-requests" and request.method == "GET":
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            org_id = request.url.params.get("org_id")
            workspace_id = request.url.params.get("workspace_id")
            state_filter = request.url.params.get("state")
            rows: list[dict[str, object]] = []
            for item in access_requests.values():
                item_org = item.get("org_id")
                item_workspace = item.get("workspace_id")
                item_state = item.get("state")
                if isinstance(org_id, str) and item_org != org_id:
                    continue
                if isinstance(workspace_id, str) and item_workspace != workspace_id:
                    continue
                if isinstance(state_filter, str) and item_state != state_filter:
                    continue
                rows.append(item)
            return httpx.Response(200, json={"ok": True, "access_requests": rows})
        if request.url.path.startswith("/v1/access-requests/") and request.url.path.endswith("/review") and request.method == "POST":
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            access_request_id = request.url.path.split("/v1/access-requests/")[1].split("/review")[0]
            if access_request_id not in access_requests:
                return httpx.Response(404, json={"error": "not_found"})
            current_state = access_requests[access_request_id].get("state")
            if current_state not in {"pending", "under_review"}:
                return httpx.Response(409, json={"error": "not_reviewable"})
            body = json.loads(request.content.decode("utf-8"))
            review_state_by_decision = {
                "approve": "approved",
                "reject": "rejected",
                "waitlist": "waitlisted",
            }
            state = review_state_by_decision.get(body.get("decision"))
            if state is None:
                return httpx.Response(422, json={"error": "invalid_decision"})
            access_requests[access_request_id]["state"] = state
            access_requests[access_request_id]["reviewer_actor_id"] = body["reviewer_actor_id"]
            access_requests[access_request_id]["review_comment"] = body.get("review_comment")
            access_requests[access_request_id]["reviewed_at"] = "2026-02-28T00:00:02Z"
            access_requests[access_request_id]["updated_at"] = "2026-02-28T00:00:02Z"
            return httpx.Response(200, json={"ok": True, "access_request": access_requests[access_request_id]})
        if request.url.path == "/v1/quotas" and request.method == "PATCH":
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            body = json.loads(request.content.decode("utf-8"))
            org_id = body["org_id"]
            workspace_id = body["workspace_id"]
            workspace = workspaces.get(workspace_id)
            if workspace is None:
                return httpx.Response(404, json={"error": "workspace not found"})
            if workspace["org_id"] != org_id:
                return httpx.Response(403, json={"error": "workspace outside org scope"})
            key = (org_id, workspace_id)
            quota_policy = quota_policies.get(key)
            if quota_policy is None:
                quota_policy = {
                    "quota_policy_id": str(uuid4()),
                    "org_id": org_id,
                    "workspace_id": workspace_id,
                    "dimensions": body["dimensions"],
                    "soft_threshold_percent": body.get("soft_threshold_percent", 85),
                    "hard_enforcement": body.get("hard_enforcement", False),
                    "overage_mode": body["overage_mode"],
                    "updated_by_actor_id": body.get("updated_by_actor_id"),
                    "updated_at": "2026-02-28T00:00:03Z",
                }
                quota_policies[key] = quota_policy
            else:
                quota_policy.update(
                    {
                        "dimensions": body["dimensions"],
                        "soft_threshold_percent": body.get("soft_threshold_percent", quota_policy["soft_threshold_percent"]),
                        "hard_enforcement": body.get("hard_enforcement", quota_policy["hard_enforcement"]),
                        "overage_mode": body["overage_mode"],
                        "updated_by_actor_id": body.get("updated_by_actor_id"),
                        "updated_at": "2026-02-28T00:00:03Z",
                    }
                )
            return httpx.Response(200, json={"ok": True, "quota_policy": quota_policy})
        if request.url.path == "/v1/quotas" and request.method == "GET":
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            org_id = request.url.params.get("org_id")
            workspace_id = request.url.params.get("workspace_id")
            if not isinstance(org_id, str) or not isinstance(workspace_id, str):
                return httpx.Response(422, json={"error": "missing org/workspace"})
            workspace = workspaces.get(workspace_id)
            if workspace is None:
                return httpx.Response(404, json={"error": "workspace not found"})
            if workspace["org_id"] != org_id:
                return httpx.Response(403, json={"error": "workspace outside org scope"})
            quota_policy = quota_policies.get((org_id, workspace_id))
            if quota_policy is None:
                return httpx.Response(404, json={"error": "quota not found"})
            return httpx.Response(200, json={"ok": True, "quota_policy": quota_policy})
        if request.url.path == "/v1/usage/summary" and request.method == "GET":
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            org_id = request.url.params.get("org_id")
            workspace_id = request.url.params.get("workspace_id")
            if not isinstance(org_id, str) or not isinstance(workspace_id, str):
                return httpx.Response(422, json={"error": "missing org/workspace"})
            workspace = workspaces.get(workspace_id)
            if workspace is None:
                return httpx.Response(404, json={"error": "workspace not found"})
            if workspace["org_id"] != org_id:
                return httpx.Response(403, json={"error": "workspace outside org scope"})
            quota_policy = quota_policies.get((org_id, workspace_id))
            if quota_policy is None:
                return httpx.Response(404, json={"error": "quota not found"})
            dimensions = quota_policy["dimensions"]
            assert isinstance(dimensions, dict)
            current_intents_used = intent_usage_by_scope.get((org_id, workspace_id), 0)
            usage_dimensions = {
                "requests_per_minute": build_usage_window(int(dimensions["requests_per_minute"])),
                "intents_per_day": {
                    "used": current_intents_used,
                    "limit": int(dimensions["intents_per_day"]),
                    "remaining": int(dimensions["intents_per_day"]) - current_intents_used,
                },
                "inbox_writes_per_day": build_usage_window(int(dimensions["inbox_writes_per_day"])),
                "media_upload_bytes_per_day": build_usage_window(int(dimensions["media_upload_bytes_per_day"])),
                "media_storage_bytes": build_usage_window(int(dimensions["media_storage_bytes"])),
                "webhook_deliveries_per_day": build_usage_window(int(dimensions["webhook_deliveries_per_day"])),
                "schema_writes_per_day": build_usage_window(int(dimensions["schema_writes_per_day"])),
            }
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "summary": {
                        "org_id": org_id,
                        "workspace_id": workspace_id,
                        "window_start": "2026-02-28T00:00:00Z",
                        "window_end": "2026-02-28T00:59:59Z",
                        "dimensions": usage_dimensions,
                    },
                },
            )
        if request.url.path == "/v1/usage/timeseries" and request.method == "GET":
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            org_id = request.url.params.get("org_id")
            workspace_id = request.url.params.get("workspace_id")
            if not isinstance(org_id, str) or not isinstance(workspace_id, str):
                return httpx.Response(422, json={"error": "missing org/workspace"})
            workspace = workspaces.get(workspace_id)
            if workspace is None:
                return httpx.Response(404, json={"error": "workspace not found"})
            if workspace["org_id"] != org_id:
                return httpx.Response(403, json={"error": "workspace outside org scope"})
            current_intents_used = intent_usage_by_scope.get((org_id, workspace_id), 0)
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "series": {
                        "org_id": org_id,
                        "workspace_id": workspace_id,
                        "granularity": "day",
                        "points": [
                            {
                                "at": "2026-02-28T00:00:00Z",
                                "dimensions": {
                                    "requests_per_minute": 0,
                                    "intents_per_day": current_intents_used,
                                    "inbox_writes_per_day": 0,
                                    "media_upload_bytes_per_day": 0,
                                    "media_storage_bytes": 0,
                                    "webhook_deliveries_per_day": 0,
                                    "schema_writes_per_day": 0,
                                },
                            }
                        ],
                    },
                },
            )
        if request.url.path == "/v1/usage/rollups/daily" and request.method == "POST":
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            org_id = request.url.params.get("org_id")
            workspace_id = request.url.params.get("workspace_id")
            window_days = request.url.params.get("window_days")
            if not isinstance(org_id, str) or not isinstance(workspace_id, str):
                return httpx.Response(422, json={"error": "missing org/workspace"})
            workspace = workspaces.get(workspace_id)
            if workspace is None:
                return httpx.Response(404, json={"error": "workspace not found"})
            if workspace["org_id"] != org_id:
                return httpx.Response(403, json={"error": "workspace outside org scope"})
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "rollup": {
                        "org_id": org_id,
                        "workspace_id": workspace_id,
                        "window_days": int(window_days or 30),
                        "upserted": 1,
                        "generated_at": "2026-02-28T00:00:04Z",
                    },
                },
            )
        if request.url.path == "/v1/service-accounts" and request.method == "POST":
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            body = json.loads(request.content.decode("utf-8"))
            org_id = body.get("org_id")
            workspace_id = body.get("workspace_id")
            if not isinstance(org_id, str) or not isinstance(workspace_id, str):
                return httpx.Response(422, json={"error": "missing org/workspace"})
            workspace = workspaces.get(workspace_id)
            if workspace is None or workspace["org_id"] != org_id:
                return httpx.Response(403, json={"error": "workspace outside org scope"})
            service_account_id = f"sa_{uuid4().hex[:24]}"
            service_account = {
                "service_account_id": service_account_id,
                "org_id": org_id,
                "workspace_id": workspace_id,
                "name": body["name"],
                "description": body.get("description"),
                "status": "active",
                "created_by_actor_id": body["created_by_actor_id"],
                "created_at": "2026-02-28T00:00:00Z",
                "updated_at": "2026-02-28T00:00:00Z",
            }
            service_accounts[service_account_id] = service_account
            return httpx.Response(200, json={"ok": True, "service_account": service_account})
        if request.url.path == "/v1/service-accounts" and request.method == "GET":
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            org_id = request.url.params.get("org_id")
            workspace_id = request.url.params.get("workspace_id")
            if not isinstance(org_id, str):
                return httpx.Response(422, json={"error": "missing org_id"})
            items = [
                account
                for account in service_accounts.values()
                if account.get("org_id") == org_id and (workspace_id is None or account.get("workspace_id") == workspace_id)
            ]
            return httpx.Response(200, json={"ok": True, "service_accounts": items})
        if request.url.path.startswith("/v1/service-accounts/") and request.url.path.endswith("/keys") and request.method == "POST":
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            service_account_id = request.url.path.split("/v1/service-accounts/")[1].split("/keys")[0]
            if service_account_id not in service_accounts:
                return httpx.Response(404, json={"error": "service_account_not_found"})
            key_id = f"sak_{uuid4().hex[:24]}"
            key_payload = {
                "key_id": key_id,
                "service_account_id": service_account_id,
                "key_hint": key_id[:8],
                "status": "active",
                "created_at": "2026-02-28T00:00:00Z",
                "expires_at": None,
                "token": f"axme_sa_{service_account_id}_{uuid4().hex}",
            }
            service_account_keys[key_id] = key_payload
            return httpx.Response(200, json={"ok": True, "key": key_payload})
        if (
            request.url.path.startswith("/v1/service-accounts/")
            and "/keys/" in request.url.path
            and request.url.path.endswith("/revoke")
            and request.method == "POST"
        ):
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            parts = [part for part in request.url.path.split("/") if part]
            service_account_id = parts[2]
            key_id = parts[4]
            if service_account_id not in service_accounts or key_id not in service_account_keys:
                return httpx.Response(404, json={"error": "not_found"})
            key_payload = dict(service_account_keys[key_id])
            key_payload["status"] = "revoked"
            key_payload["revoked_at"] = "2026-02-28T00:00:05Z"
            service_account_keys[key_id] = key_payload
            return httpx.Response(200, json={"ok": True, "key": key_payload})
        if request.url.path.startswith("/v1/intents/") and request.url.path.endswith("/events/stream") and request.method == "GET":
            intent_id_from_path = request.url.path.split("/v1/intents/")[1].split("/events/stream")[0]
            if intent_id_from_path not in intents:
                return httpx.Response(404, json={"error": "not_found"})
            since_raw = request.url.params.get("since")
            since = int(since_raw) if isinstance(since_raw, str) and since_raw.isdigit() else 0
            sse_lines: list[str] = []
            for event in intent_events.get(intent_id_from_path, []):
                seq = event.get("seq")
                if not isinstance(seq, int) or seq <= since:
                    continue
                sse_lines.extend(
                    [
                        f"id: {seq}",
                        f"event: {event.get('event_type')}",
                        f"data: {json.dumps(event)}",
                        "",
                    ]
                )
            next_seq = len(intent_events.get(intent_id_from_path, [])) + 1
            sse_lines.extend(
                [
                    "event: stream.timeout",
                    f"data: {json.dumps({'ok': True, 'next_seq': next_seq})}",
                    "",
                ]
            )
            return httpx.Response(200, text="\n".join(sse_lines), headers={"content-type": "text/event-stream"})
        if request.url.path.startswith("/v1/intents/") and request.url.path.endswith("/events") and request.method == "GET":
            intent_id_from_path = request.url.path.split("/v1/intents/")[1].split("/events")[0]
            if intent_id_from_path not in intents:
                return httpx.Response(404, json={"error": "not_found"})
            events = list(intent_events.get(intent_id_from_path, []))
            since_raw = request.url.params.get("since")
            if isinstance(since_raw, str) and since_raw.isdigit():
                since = int(since_raw)
                events = [item for item in events if isinstance(item.get("seq"), int) and item["seq"] > since]
            return httpx.Response(200, json={"ok": True, "events": events})
        if request.url.path.startswith("/v1/intents/") and request.url.path.endswith("/resolve") and request.method == "POST":
            intent_id_from_path = request.url.path.split("/v1/intents/")[1].split("/resolve")[0]
            if intent_id_from_path not in intents:
                return httpx.Response(404, json={"error": "not_found"})
            body = json.loads(request.content.decode("utf-8"))
            status = body.get("status")
            if status not in {"COMPLETED", "FAILED", "CANCELED"}:
                return httpx.Response(422, json={"error": "invalid_status"})
            events = intent_events.setdefault(intent_id_from_path, [])
            if events and events[-1].get("status") in {"COMPLETED", "FAILED", "CANCELED"}:
                return httpx.Response(409, json={"error": "intent already in terminal state"})
            event_type_map = {
                "COMPLETED": "intent.completed",
                "FAILED": "intent.failed",
                "CANCELED": "intent.canceled",
            }
            details: dict[str, object]
            if status == "COMPLETED":
                details = {"result": body.get("result") if isinstance(body.get("result"), dict) else {}}
            elif status == "FAILED":
                details = {"error": body.get("error") if isinstance(body.get("error"), dict) else {}}
            else:
                details = {"reason": body.get("reason") if isinstance(body.get("reason"), str) else "canceled"}
            terminal_event = {
                "intent_id": intent_id_from_path,
                "seq": len(events) + 1,
                "event_type": event_type_map[status],
                "status": status,
                "waiting_reason": None,
                "handler": intents[intent_id_from_path].get("to_agent"),
                "actor": body.get("actor") or "agent://conformance/resolver",
                "at": "2026-02-28T00:00:10Z",
                "details": details,
            }
            events.append(terminal_event)
            intents[intent_id_from_path]["status"] = status
            intents[intent_id_from_path]["updated_at"] = "2026-02-28T00:00:10Z"
            completion_delivery: dict[str, object] = {"delivered": False, "reason": "reply_to_not_set"}
            reply_to = intents[intent_id_from_path].get("reply_to")
            if isinstance(reply_to, str) and reply_to:
                completion_delivery = {
                    "delivered": True,
                    "reply_to": reply_to,
                    "thread_id": intent_id_from_path,
                    "message_id": str(uuid4()),
                    "completion": {
                        "type": terminal_event["event_type"],
                        "intent_id": intent_id_from_path,
                        "status": status,
                    },
                }
                reply_threads = reply_threads_by_owner.setdefault(reply_to, [])
                if not any(thread.get("thread_id") == intent_id_from_path for thread in reply_threads):
                    reply_threads.append(
                        {
                            "thread_id": intent_id_from_path,
                            "intent_id": intent_id_from_path,
                            "status": "done",
                            "owner_agent": reply_to,
                            "from_agent": "agent://axme.intent-protocol",
                            "to_agent": reply_to,
                            "created_at": "2026-02-28T00:00:10Z",
                            "updated_at": "2026-02-28T00:00:10Z",
                            "timeline": [
                                {
                                    "event_id": str(uuid4()),
                                    "event_type": "intent_completion_delivered",
                                    "actor": "gateway",
                                    "at": "2026-02-28T00:00:10Z",
                                    "details": {"intent_id": intent_id_from_path},
                                }
                            ],
                        }
                    )
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "intent": intents[intent_id_from_path],
                    "event": terminal_event,
                    "completion_delivery": completion_delivery,
                },
            )
        if request.url.path.startswith("/v1/intents/") and request.method == "GET":
            intent_id_from_path = request.url.path.split("/v1/intents/")[1]
            if intent_id_from_path not in intents:
                return httpx.Response(404, json={"error": "not_found"})
            return httpx.Response(200, json={"ok": True, "intent": intents[intent_id_from_path]})
        if request.url.path == "/v1/intents":
            body = json.loads(request.content.decode("utf-8"))
            payload_section = body.get("payload")
            quota_scope: tuple[str, str] | None = None
            if isinstance(payload_section, dict):
                tenant_section = payload_section.get("tenant")
                if isinstance(tenant_section, dict):
                    tenant_org_id = tenant_section.get("org_id")
                    tenant_workspace_id = tenant_section.get("workspace_id")
                    if isinstance(tenant_org_id, str) and isinstance(tenant_workspace_id, str):
                        quota_scope = (tenant_org_id, tenant_workspace_id)
            if quota_scope is not None:
                quota_policy = quota_policies.get(quota_scope)
                if quota_policy is not None:
                    dimensions = quota_policy.get("dimensions")
                    if isinstance(dimensions, dict):
                        intents_limit = dimensions.get("intents_per_day")
                        current_usage = intent_usage_by_scope.get(quota_scope, 0)
                        if (
                            quota_policy.get("hard_enforcement") is True
                            and quota_policy.get("overage_mode") == "block"
                            and isinstance(intents_limit, int)
                            and intents_limit >= 0
                            and current_usage >= intents_limit
                        ):
                            return httpx.Response(429, json={"detail": "quota exceeded for intents_per_day"})

            def _store_intent(intent_id_value: str) -> None:
                intents[intent_id_value] = {
                    "intent_id": intent_id_value,
                    "status": "DELIVERED",
                    "created_at": "2026-02-28T00:00:00Z",
                    "updated_at": "2026-02-28T00:00:01Z",
                    "intent_type": body.get("intent_type", "notify.message.v1"),
                    "correlation_id": body.get("correlation_id", str(uuid4())),
                    "from_agent": body.get("from_agent", "agent://conformance/sender"),
                    "to_agent": body.get("to_agent", "agent://conformance/receiver"),
                    "reply_to": body.get("reply_to"),
                    "payload": body.get("payload") if isinstance(body.get("payload"), dict) else {},
                }
                intent_events[intent_id_value] = [
                    {
                        "intent_id": intent_id_value,
                        "seq": 1,
                        "event_type": "intent.created",
                        "status": "CREATED",
                        "waiting_reason": None,
                        "handler": intents[intent_id_value]["from_agent"],
                        "actor": intents[intent_id_value]["from_agent"],
                        "at": "2026-02-28T00:00:00Z",
                        "details": {"intent_type": intents[intent_id_value]["intent_type"]},
                    },
                    {
                        "intent_id": intent_id_value,
                        "seq": 2,
                        "event_type": "intent.submitted",
                        "status": "SUBMITTED",
                        "waiting_reason": None,
                        "handler": intents[intent_id_value]["from_agent"],
                        "actor": "gateway",
                        "at": "2026-02-28T00:00:01Z",
                        "details": {"source": "conformance"},
                    },
                    {
                        "intent_id": intent_id_value,
                        "seq": 3,
                        "event_type": "intent.delivered",
                        "status": "DELIVERED",
                        "waiting_reason": None,
                        "handler": intents[intent_id_value]["to_agent"],
                        "actor": "gateway",
                        "at": "2026-02-28T00:00:01Z",
                        "details": {"source": "conformance"},
                    },
                ]

            idempotency_key = request.headers.get("idempotency-key")
            if idempotency_key:
                payload_signature = json.dumps(body, sort_keys=True)
                if idempotency_key in idempotency_cache:
                    previous_signature, previous_intent_id = idempotency_cache[idempotency_key]
                    if previous_signature != payload_signature:
                        return httpx.Response(409, json={"error": "idempotency_conflict"})
                    if previous_intent_id not in intents:
                        _store_intent(previous_intent_id)
                    return httpx.Response(200, json={"intent_id": previous_intent_id, "status": intents[previous_intent_id]["status"]})
                new_intent_id = str(uuid4())
                idempotency_cache[idempotency_key] = (payload_signature, new_intent_id)
                _store_intent(new_intent_id)
                if quota_scope is not None:
                    intent_usage_by_scope[quota_scope] = intent_usage_by_scope.get(quota_scope, 0) + 1
                return httpx.Response(200, json={"intent_id": new_intent_id, "status": intents[new_intent_id]["status"]})
            generated_intent_id = str(uuid4())
            _store_intent(generated_intent_id)
            if quota_scope is not None:
                intent_usage_by_scope[quota_scope] = intent_usage_by_scope.get(quota_scope, 0) + 1
            return httpx.Response(200, json={"intent_id": generated_intent_id, "status": intents[generated_intent_id]["status"]})
        if request.url.path == "/v1/inbox":
            owner_agent = request.url.params.get("owner_agent")
            if owner_agent == "agent://conformance/owner":
                return httpx.Response(200, json={"ok": True, "threads": [thread_payload]})
            return httpx.Response(200, json={"ok": True, "threads": list(reply_threads_by_owner.get(owner_agent or "", []))})
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
        if request.url.path == "/v1/principals" and request.method == "POST":
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            body = json.loads(request.content.decode("utf-8"))
            org_id = body.get("org_id")
            workspace_id = body.get("workspace_id")
            if not isinstance(org_id, str) or not isinstance(workspace_id, str):
                return httpx.Response(422, json={"error": "missing org/workspace"})
            workspace = workspaces.get(workspace_id)
            if workspace is None or workspace.get("org_id") != org_id:
                return httpx.Response(403, json={"error": "workspace outside org scope"})
            principal_id = f"prn_{uuid4().hex[:24]}"
            principal = {
                "principal_id": principal_id,
                "org_id": org_id,
                "workspace_id": workspace_id,
                "principal_type": body.get("principal_type", "service_agent"),
                "display_name": body.get("display_name"),
                "status": "active",
                "metadata": body.get("metadata", {}),
                "created_at": "2026-02-28T00:00:00Z",
                "updated_at": "2026-02-28T00:00:00Z",
            }
            principals[principal_id] = principal
            return httpx.Response(200, json={"ok": True, "principal": principal})
        if request.url.path.startswith("/v1/principals/") and request.method == "GET":
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            principal_id = request.url.path.split("/v1/principals/")[1]
            principal = principals.get(principal_id)
            if principal is None:
                return httpx.Response(404, json={"error": "principal_not_found"})
            return httpx.Response(200, json={"ok": True, "principal": principal})
        if request.url.path == "/v1/aliases" and request.method == "POST":
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            body = json.loads(request.content.decode("utf-8"))
            principal_id = body.get("principal_id")
            principal = principals.get(principal_id or "")
            if principal is None:
                return httpx.Response(404, json={"error": "principal_not_found"})
            alias_value = body.get("alias")
            if not isinstance(alias_value, str):
                return httpx.Response(422, json={"error": "invalid_alias"})
            alias_id = f"pal_{uuid4().hex[:24]}"
            alias_payload = {
                "alias_id": alias_id,
                "principal_id": principal_id,
                "org_id": principal["org_id"],
                "workspace_id": principal["workspace_id"],
                "alias": alias_value,
                "alias_type": body.get("alias_type", "service"),
                "status": "active",
                "metadata": body.get("metadata", {}),
                "created_at": "2026-02-28T00:00:00Z",
                "updated_at": "2026-02-28T00:00:00Z",
                "revoked_at": None,
            }
            aliases[alias_id] = alias_payload
            return httpx.Response(200, json={"ok": True, "alias": alias_payload})
        if request.url.path.startswith("/v1/aliases/") and request.url.path.endswith("/revoke") and request.method == "POST":
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            alias_id = request.url.path.split("/v1/aliases/")[1].split("/revoke")[0]
            alias_payload = aliases.get(alias_id)
            if alias_payload is None:
                return httpx.Response(404, json={"error": "alias_not_found"})
            alias_payload = dict(alias_payload)
            alias_payload["status"] = "revoked"
            alias_payload["revoked_at"] = "2026-02-28T00:00:05Z"
            aliases[alias_id] = alias_payload
            return httpx.Response(200, json={"ok": True, "alias": alias_payload})
        if request.url.path == "/v1/routing/endpoints" and request.method == "POST":
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            body = json.loads(request.content.decode("utf-8"))
            principal_id = body.get("principal_id")
            principal = principals.get(principal_id or "")
            if principal is None:
                return httpx.Response(404, json={"error": "principal_not_found"})
            route_id = f"rte_{uuid4().hex[:24]}"
            route_payload = {
                "route_id": route_id,
                "principal_id": principal_id,
                "org_id": principal["org_id"],
                "workspace_id": principal["workspace_id"],
                "transport_type": body.get("transport_type", "http"),
                "endpoint_url": body.get("endpoint_url"),
                "auth_mode": body.get("auth_mode", "jwt"),
                "region": body.get("region"),
                "cluster_id": body.get("cluster_id"),
                "failover_policy": body.get("failover_policy", "none"),
                "priority": body.get("priority", 100),
                "health_status": body.get("health_status", "unknown"),
                "status": "active",
                "metadata": body.get("metadata", {}),
                "created_at": "2026-02-28T00:00:00Z",
                "updated_at": "2026-02-28T00:00:00Z",
            }
            endpoint_routes[route_id] = route_payload
            return httpx.Response(200, json={"ok": True, "route": route_payload})
        if request.url.path.startswith("/v1/routing/endpoints/") and request.method == "PATCH":
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            route_id = request.url.path.split("/v1/routing/endpoints/")[1]
            route_payload = endpoint_routes.get(route_id)
            if route_payload is None:
                return httpx.Response(404, json={"error": "route_not_found"})
            body = json.loads(request.content.decode("utf-8"))
            route_payload = dict(route_payload)
            for field in (
                "endpoint_url",
                "auth_mode",
                "region",
                "cluster_id",
                "failover_policy",
                "priority",
                "health_status",
                "status",
            ):
                if field in body and body.get(field) is not None:
                    route_payload[field] = body[field]
            route_payload["updated_at"] = "2026-02-28T00:00:05Z"
            endpoint_routes[route_id] = route_payload
            return httpx.Response(200, json={"ok": True, "route": route_payload})
        if request.url.path == "/v1/transports/bindings" and request.method == "POST":
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            body = json.loads(request.content.decode("utf-8"))
            principal_id = body.get("principal_id")
            principal = principals.get(principal_id or "")
            if principal is None:
                return httpx.Response(404, json={"error": "principal_not_found"})
            binding_id = f"tb_{uuid4().hex[:24]}"
            binding_payload = {
                "binding_id": binding_id,
                "principal_id": principal_id,
                "org_id": principal["org_id"],
                "workspace_id": principal["workspace_id"],
                "transport_type": body.get("transport_type", "http"),
                "transport_handle": body.get("transport_handle"),
                "priority": body.get("priority", 100),
                "status": body.get("status", "active"),
                "metadata": body.get("metadata", {}),
                "created_at": "2026-02-28T00:00:00Z",
                "updated_at": "2026-02-28T00:00:00Z",
            }
            transport_bindings[binding_id] = binding_payload
            return httpx.Response(200, json={"ok": True, "binding": binding_payload})
        if request.url.path == "/v1/routing/resolve" and request.method == "POST":
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            body = json.loads(request.content.decode("utf-8"))
            org_id = body.get("org_id")
            workspace_id = body.get("workspace_id")
            alias_value = body.get("alias")
            principal_id = body.get("principal_id")
            if isinstance(alias_value, str):
                for alias_payload in aliases.values():
                    if (
                        alias_payload.get("status") == "active"
                        and alias_payload.get("alias") == alias_value
                        and alias_payload.get("org_id") == org_id
                        and alias_payload.get("workspace_id") == workspace_id
                    ):
                        principal_id = alias_payload["principal_id"]
                        break
            principal = principals.get(principal_id or "")
            if principal is None:
                return httpx.Response(404, json={"error": "principal_not_found"})
            routes = [
                route
                for route in endpoint_routes.values()
                if route.get("principal_id") == principal["principal_id"] and route.get("status") == "active"
            ]
            if not routes:
                return httpx.Response(404, json={"error": "route_not_found"})
            binding_candidates = [
                item
                for item in transport_bindings.values()
                if item.get("principal_id") == principal["principal_id"] and item.get("status") == "active"
            ]
            binding_candidates.sort(key=lambda item: int(item.get("priority", 100)))
            transport_priority: dict[str, int] = {}
            for binding in binding_candidates:
                transport_type = str(binding.get("transport_type") or "")
                if transport_type and transport_type not in transport_priority:
                    transport_priority[transport_type] = int(binding.get("priority", 100))
            routes.sort(
                key=lambda item: (
                    int(transport_priority.get(str(item.get("transport_type") or ""), 10000)),
                    int(item.get("priority", 100)),
                    str(item.get("route_id") or ""),
                )
            )
            primary_route = routes[0]
            selected_route = primary_route
            fallback_applied = False
            fallback_from_route_id = None
            fallback_reason = None
            primary_health = str(primary_route.get("health_status") or "unknown")
            primary_policy = str(primary_route.get("failover_policy") or "none")
            if primary_health not in {"healthy", "degraded"}:
                if primary_policy in {"same_region", "cross_region"}:
                    for candidate in routes[1:]:
                        candidate_health = str(candidate.get("health_status") or "unknown")
                        if candidate_health not in {"healthy", "degraded"}:
                            continue
                        if primary_policy == "same_region" and candidate.get("region") != primary_route.get("region"):
                            continue
                        selected_route = candidate
                        fallback_applied = True
                        fallback_from_route_id = primary_route.get("route_id")
                        fallback_reason = "primary_route_not_healthy"
                        break
                if not fallback_applied:
                    fallback_reason = "no_healthy_fallback_route"
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "resolution": {
                        "alias": next((item for item in aliases.values() if item.get("alias") == alias_value), None),
                        "principal": principal,
                        "primary_route": primary_route,
                        "selected_route": selected_route,
                        "candidate_routes": routes,
                        "fallback_applied": fallback_applied,
                        "fallback_from_route_id": fallback_from_route_id,
                        "fallback_reason": fallback_reason,
                        "resolver_chain": ["alias", "principal_id", "endpoint_route", "transport_dispatch"],
                    },
                },
            )
        if request.url.path == "/v1/deliveries" and request.method == "POST":
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            body = json.loads(request.content.decode("utf-8"))
            org_id = body.get("org_id")
            workspace_id = body.get("workspace_id")
            idempotency_key = body.get("idempotency_key")
            if isinstance(idempotency_key, str):
                for item in deliveries.values():
                    if (
                        item.get("org_id") == org_id
                        and item.get("workspace_id") == workspace_id
                        and item.get("idempotency_key") == idempotency_key
                    ):
                        return httpx.Response(200, json={"ok": True, "delivery": item})
            alias_value = body.get("alias")
            principal_id = body.get("principal_id")
            if isinstance(alias_value, str):
                for alias_payload in aliases.values():
                    if alias_payload.get("alias") == alias_value and alias_payload.get("status") == "active":
                        principal_id = alias_payload["principal_id"]
                        break
            principal = principals.get(principal_id or "")
            if principal is None:
                return httpx.Response(404, json={"error": "principal_not_found"})
            routes = [route for route in endpoint_routes.values() if route.get("principal_id") == principal["principal_id"]]
            if not routes:
                return httpx.Response(404, json={"error": "route_not_found"})
            active_routes = [route for route in routes if route.get("status") == "active"]
            if not active_routes:
                return httpx.Response(404, json={"error": "route_not_found"})
            binding_candidates = [
                item
                for item in transport_bindings.values()
                if item.get("principal_id") == principal["principal_id"] and item.get("status") == "active"
            ]
            binding_candidates.sort(key=lambda item: int(item.get("priority", 100)))
            transport_priority: dict[str, int] = {}
            for binding in binding_candidates:
                transport_type = str(binding.get("transport_type") or "")
                if transport_type and transport_type not in transport_priority:
                    transport_priority[transport_type] = int(binding.get("priority", 100))
            active_routes.sort(
                key=lambda item: (
                    int(transport_priority.get(str(item.get("transport_type") or ""), 10000)),
                    int(item.get("priority", 100)),
                    str(item.get("route_id") or ""),
                )
            )
            primary_route = active_routes[0]
            selected_route = primary_route
            primary_health = str(primary_route.get("health_status") or "unknown")
            primary_policy = str(primary_route.get("failover_policy") or "none")
            if primary_health not in {"healthy", "degraded"} and primary_policy in {"same_region", "cross_region"}:
                for candidate in active_routes[1:]:
                    candidate_health = str(candidate.get("health_status") or "unknown")
                    if candidate_health not in {"healthy", "degraded"}:
                        continue
                    if primary_policy == "same_region" and candidate.get("region") != primary_route.get("region"):
                        continue
                    selected_route = candidate
                    break
            delivery_id = f"dlv_{uuid4().hex[:24]}"
            delivery_payload = {
                "delivery_id": delivery_id,
                "replay_of_delivery_id": body.get("replay_of_delivery_id"),
                "org_id": org_id,
                "workspace_id": workspace_id,
                "principal_id": principal["principal_id"],
                "alias": alias_value,
                "transport_type": selected_route["transport_type"],
                "route_id": selected_route["route_id"],
                "status": "pending" if str(selected_route.get("health_status") or "unknown") in {"degraded", "unhealthy"} else "delivered",
                "correlation_id": body.get("correlation_id"),
                "idempotency_key": idempotency_key,
                "payload": body.get("payload", {}),
                "error_detail": None,
                "created_at": "2026-02-28T00:00:00Z",
                "updated_at": "2026-02-28T00:00:00Z",
            }
            deliveries[delivery_id] = delivery_payload
            return httpx.Response(200, json={"ok": True, "delivery": delivery_payload})
        if request.url.path == "/v1/deliveries-operations" and request.method == "GET":
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            org_id = request.url.params.get("org_id")
            workspace_id = request.url.params.get("workspace_id")
            window_hours = request.url.params.get("window_hours")
            filtered = [
                item
                for item in deliveries.values()
                if (org_id is None or item.get("org_id") == org_id)
                and (workspace_id is None or item.get("workspace_id") == workspace_id)
            ]
            status_counts = {"submitted": 0, "delivered": 0, "failed": 0, "pending": 0, "dead_lettered": 0}
            by_transport: dict[str, dict[str, object]] = {}
            by_route: dict[str, dict[str, object]] = {}
            replay_count = 0
            latency_samples_ms: list[float] = []
            by_transport_latency_samples_ms: dict[str, list[float]] = {}
            for item in filtered:
                status = str(item.get("status") or "submitted")
                transport_type = str(item.get("transport_type") or "unknown")
                route_id = str(item.get("route_id") or "unknown")
                if status in status_counts:
                    status_counts[status] = int(status_counts[status]) + 1
                if item.get("replay_of_delivery_id") is not None:
                    replay_count += 1
                if transport_type not in by_transport:
                    by_transport[transport_type] = {
                        "transport_type": transport_type,
                        "total": 0,
                        "status_counts": {"submitted": 0, "delivered": 0, "failed": 0, "pending": 0, "dead_lettered": 0},
                        "error_rate": 0.0,
                    }
                transport_bucket = by_transport[transport_type]
                transport_bucket["total"] = int(transport_bucket["total"]) + 1
                transport_bucket["status_counts"][status] = int(transport_bucket["status_counts"].get(status, 0)) + 1
                if status in {"delivered", "failed", "dead_lettered"}:
                    created_at = str(item.get("created_at") or "")
                    updated_at = str(item.get("updated_at") or "")
                    latency_ms = 10000.0 if created_at != updated_at else 0.0
                    latency_samples_ms.append(latency_ms)
                    if transport_type not in by_transport_latency_samples_ms:
                        by_transport_latency_samples_ms[transport_type] = []
                    by_transport_latency_samples_ms[transport_type].append(latency_ms)
                if route_id not in by_route:
                    by_route[route_id] = {
                        "route_id": route_id,
                        "total": 0,
                        "status_counts": {"submitted": 0, "delivered": 0, "failed": 0, "pending": 0, "dead_lettered": 0},
                    }
                route_bucket = by_route[route_id]
                route_bucket["total"] = int(route_bucket["total"]) + 1
                route_bucket["status_counts"][status] = int(route_bucket["status_counts"].get(status, 0)) + 1
            for bucket in by_transport.values():
                total = int(bucket["total"])
                errors = int(bucket["status_counts"]["failed"]) + int(bucket["status_counts"]["dead_lettered"])
                bucket["error_rate"] = float(errors / total) if total > 0 else 0.0
                transport_type = str(bucket["transport_type"])
                transport_latencies = by_transport_latency_samples_ms.get(transport_type, [])
                sample_count = len(transport_latencies)
                avg_ms = float(sum(transport_latencies) / sample_count) if sample_count > 0 else 0.0
                bucket["latency"] = {
                    "sample_count": sample_count,
                    "slo_target_ms": 1000.0,
                    "avg_ms": avg_ms,
                    "p95_ms": avg_ms if sample_count > 0 else 0.0,
                    "max_ms": max(transport_latencies) if sample_count > 0 else 0.0,
                    "slo_attainment_rate": (
                        float(sum(1 for value in transport_latencies if value <= 1000.0)) / float(sample_count)
                        if sample_count > 0
                        else 0.0
                    ),
                }
            latency_sample_count = len(latency_samples_ms)
            latency_avg_ms = (
                float(sum(latency_samples_ms) / float(latency_sample_count))
                if latency_sample_count > 0
                else 0.0
            )
            pending_to_delivered_count = 0
            pending_to_dead_lettered_count = 0
            for event in reconcile_events:
                if org_id is not None and event.get("org_id") != org_id:
                    continue
                if workspace_id is not None and event.get("workspace_id") != workspace_id:
                    continue
                count_value = int(event.get("reconciled_count") or 0)
                if str(event.get("target_status") or "dead_lettered") == "delivered":
                    pending_to_delivered_count += count_value
                else:
                    pending_to_dead_lettered_count += count_value
            total_recovered = pending_to_delivered_count + pending_to_dead_lettered_count
            recovery_denominator = total_recovered + int(status_counts["pending"])
            pending_recovery_rate = (
                float(total_recovered) / float(recovery_denominator)
                if recovery_denominator > 0
                else 0.0
            )
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "operations": {
                        "org_id": org_id,
                        "workspace_id": workspace_id,
                        "window_hours": int(window_hours or 24),
                        "window_start": "2026-02-27T00:00:00Z",
                        "window_end": "2026-02-28T00:00:00Z",
                        "total_deliveries": len(filtered),
                        "replay_count": replay_count,
                        "status_counts": status_counts,
                        "latency": {
                            "sample_count": latency_sample_count,
                            "slo_target_ms": 1000.0,
                            "avg_ms": latency_avg_ms,
                            "p95_ms": latency_avg_ms if latency_sample_count > 0 else 0.0,
                            "max_ms": max(latency_samples_ms) if latency_sample_count > 0 else 0.0,
                            "slo_attainment_rate": (
                                float(sum(1 for value in latency_samples_ms if value <= 1000.0)) / float(latency_sample_count)
                                if latency_sample_count > 0
                                else 0.0
                            ),
                        },
                        "recovery_counters": {
                            "pending_to_delivered_count": pending_to_delivered_count,
                            "pending_to_dead_lettered_count": pending_to_dead_lettered_count,
                            "total_recovered": total_recovered,
                            "pending_recovery_rate": pending_recovery_rate,
                            "delivered_recovery_share": (
                                float(pending_to_delivered_count) / float(total_recovered)
                                if total_recovered > 0
                                else 0.0
                            ),
                            "dead_lettered_recovery_share": (
                                float(pending_to_dead_lettered_count) / float(total_recovered)
                                if total_recovered > 0
                                else 0.0
                            ),
                        },
                        "by_transport": list(by_transport.values()),
                        "by_route": list(by_route.values()),
                    },
                },
            )
        if request.url.path == "/v1/deliveries/reconcile" and request.method == "POST":
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            body = json.loads(request.content.decode("utf-8"))
            org_id = body.get("org_id")
            workspace_id = body.get("workspace_id")
            target_status = str(body.get("target_status") or "dead_lettered")
            reason = body.get("reason")
            if target_status not in {"delivered", "dead_lettered"}:
                return httpx.Response(422, json={"error": "invalid_target_status"})
            reconciled_ids: list[str] = []
            by_target_status = {"delivered": 0, "dead_lettered": 0}
            by_transport: dict[str, int] = {}
            by_route: dict[str, int] = {}
            for delivery_id, item in list(deliveries.items()):
                if item.get("status") != "pending":
                    continue
                if org_id is not None and item.get("org_id") != org_id:
                    continue
                if workspace_id is not None and item.get("workspace_id") != workspace_id:
                    continue
                next_item = dict(item)
                next_item["status"] = target_status
                if target_status == "dead_lettered":
                    next_item["error_detail"] = str(reason or "reconciled pending delivery after timeout")
                else:
                    next_item["error_detail"] = str(reason) if isinstance(reason, str) else None
                next_item["updated_at"] = "2026-02-28T00:00:10Z"
                deliveries[delivery_id] = next_item
                reconciled_ids.append(delivery_id)
                by_target_status[target_status] = int(by_target_status[target_status]) + 1
                transport_type = str(next_item.get("transport_type") or "unknown")
                route_id = str(next_item.get("route_id") or "unknown")
                by_transport[transport_type] = int(by_transport.get(transport_type, 0)) + 1
                by_route[route_id] = int(by_route.get(route_id, 0)) + 1
            reconcile_events.append(
                {
                    "org_id": org_id,
                    "workspace_id": workspace_id,
                    "target_status": target_status,
                    "reconciled_count": len(reconciled_ids),
                }
            )
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "reconciliation": {
                        "org_id": org_id,
                        "workspace_id": workspace_id,
                        "max_pending_age_seconds": int(body.get("max_pending_age_seconds", 300)),
                        "limit": int(body.get("limit", 500)),
                        "target_status": target_status,
                        "reconciled_count": len(reconciled_ids),
                        "reconciled_delivery_ids": reconciled_ids,
                        "by_target_status": by_target_status,
                        "by_transport": [
                            {"transport_type": key, "count": by_transport[key]}
                            for key in sorted(by_transport.keys())
                        ],
                        "by_route": [
                            {"route_id": key, "count": by_route[key]}
                            for key in sorted(by_route.keys())
                        ],
                        "reconciled_at": "2026-02-28T00:00:10Z",
                    },
                },
            )
        if request.url.path.startswith("/v1/deliveries/") and request.url.path.endswith("/replay") and request.method == "POST":
            if not has_authorization(request):
                return httpx.Response(401, json={"error": "unauthorized"})
            delivery_id = request.url.path.split("/v1/deliveries/")[1].split("/replay")[0]
            original = deliveries.get(delivery_id)
            if original is None:
                return httpx.Response(404, json={"error": "delivery_not_found"})
            replay_id = f"dlv_{uuid4().hex[:24]}"
            replay_payload = dict(original)
            replay_payload["delivery_id"] = replay_id
            replay_payload["replay_of_delivery_id"] = delivery_id
            replay_payload["idempotency_key"] = None
            deliveries[replay_id] = replay_payload
            return httpx.Response(200, json={"ok": True, "delivery": replay_payload})
        return httpx.Response(404, json={"error": "not_found"})

    results = run_contract_suite(
        base_url="https://api.axme.test",
        api_key="token",
        transport_factory=lambda: httpx.MockTransport(handler),
    )
    assert len(results) == 41
    assert all(r.passed for r in results), [f"{r.name}: {r.details}" for r in results if not r.passed]


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
    assert len(results) == 41
    assert all(not result.passed for result in results)


def test_run_mcp_contract_suite_happy_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path != "/mcp" or request.method != "POST":
            return httpx.Response(404, json={"error": "not_found"})
        body = json.loads(request.content.decode("utf-8"))
        method = body.get("method")
        if method == "initialize":
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {"listChanged": False}}},
                },
            )
        if method == "tools/list":
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "result": {
                        "tools": [
                            {
                                "name": "axme.check_nick",
                                "inputSchema": {
                                    "type": "object",
                                    "required": ["nick"],
                                    "properties": {"nick": {"type": "string"}},
                                },
                            }
                        ]
                    },
                },
            )
        if method == "tools/call":
            params = body.get("params", {})
            assert params.get("name") == "axme.check_nick"
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "result": {
                        "ok": True,
                        "tool": "axme.check_nick",
                        "status": "completed",
                        "data": {"ok": True, "available": True},
                    },
                },
            )
        return httpx.Response(400, json={"error": "unsupported_method"})

    results = run_mcp_contract_suite(
        base_url="https://api.axme.test",
        api_key="token",
        transport_factory=lambda: httpx.MockTransport(handler),
    )
    assert len(results) == 3
    assert all(r.passed for r in results)


def test_run_mcp_contract_suite_reports_failures() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/mcp":
            return httpx.Response(500, json={"error": "down"})
        return httpx.Response(404, json={"error": "not_found"})

    results = run_mcp_contract_suite(
        base_url="https://api.axme.test",
        api_key="token",
        transport_factory=lambda: httpx.MockTransport(handler),
    )
    assert len(results) == 3
    assert not results[0].passed
    assert not results[1].passed
    assert not results[2].passed
