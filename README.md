# axme-conformance

**Conformance suite for the AXME platform.** Canonical contract test suite validating spec-runtime-SDK parity across all API families, lifecycle invariants, and enterprise-boundary guarantees.

> **Alpha** - Conformance surface is expanding alongside the API. Not all families have full coverage yet.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

**[Docs](https://github.com/AxmeAI/axme-docs)** · **[axp-spec](https://github.com/AxmeAI/axp-spec)**

---

## Purpose

Authoritative answer to: *"Does this implementation correctly implement the AXME protocol and public API contracts?"*

Validates:

- **API contract correctness** - request/response shapes, status codes, error semantics
- **Lifecycle invariants** - state machine rules, terminal-state immutability, transition ordering
- **Idempotency guarantees** - duplicate requests return identical responses without side effects
- **Cursor and pagination** - consistent traversal across pages, stable ordering
- **Event consistency** - SSE and webhook event ordering and delivery guarantees
- **Enterprise access and tenant boundaries** - org/workspace scoping, role enforcement, quota limits
- **Control-delta semantics** - `resume`, `controls`, and `policy` mutation rules and conflict resolution

---

## Repository Structure

```
axme-conformance/
├── conformance/
│   ├── __init__.py
│   └── suite.py               # All contract checks and MCP contract suite
├── tests/
│   └── test_suite.py          # Pytest harness - runs suite against local transport
├── pyproject.toml
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── SECURITY.md
└── LICENSE
```

---

## Conformance Traceability

Each check links a spec contract (from `axp-spec`) to a runtime behavior and an SDK binding.

<details>
<summary>Traceability map diagram</summary>

![Conformance Traceability Map](https://raw.githubusercontent.com/AxmeAI/axme-docs/main/docs/diagrams/platform/04-conformance-traceability-map.svg)

</details>

---

## Running the Suite

```bash
# Install
python -m pip install -e ".[dev]"

# Run all conformance checks
pytest

# Run a specific test by keyword
pytest tests/test_suite.py -k "intents_lifecycle" -v

# Run against a custom gateway
AXME_GATEWAY_URL=https://your-gateway.example.com pytest
```

---

## Coverage Matrix

All D1 families (intents, inbox, approvals, webhooks) have full contract checks. Enterprise admin families (orgs, workspaces, service accounts, quotas) are covered. Target for Alpha release: all D1 families at 100% pass rate.

---

## Integration Rule

A conformance check is considered passing only when it succeeds against:

1. The reference runtime (`axme-control-plane` staging)
2. All five SDK clients (Python, TypeScript, Go, Java, .NET)
3. The schema definitions in `axp-spec`

---

## Related

| | |
|---|---|
| [axp-spec](https://github.com/AxmeAI/axp-spec) | Source of truth for contracts being validated |
| Control-plane runtime (private) | Primary runtime under test |
| [axme-docs](https://github.com/AxmeAI/axme-docs) | Narrative documentation |
| [axme-sdk-python](https://github.com/AxmeAI/axme-sdk-python) | Python SDK |
| [axme-sdk-typescript](https://github.com/AxmeAI/axme-sdk-typescript) | TypeScript SDK |
| [axme-sdk-go](https://github.com/AxmeAI/axme-sdk-go) | Go SDK |
| [axme-sdk-java](https://github.com/AxmeAI/axme-sdk-java) | Java SDK |
| [axme-sdk-dotnet](https://github.com/AxmeAI/axme-sdk-dotnet) | .NET SDK |

---

## Contributing

New conformance check proposals: open an issue with label `conformance-proposal`. See [CONTRIBUTING.md](CONTRIBUTING.md).

---

[hello@axme.ai](mailto:hello@axme.ai) · [Security](SECURITY.md) · [License](LICENSE)
