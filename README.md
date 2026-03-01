# axme-conformance

Conformance suite for API and SDK compatibility checks.

## Status

Initial harness skeleton in progress.

## Scope (Track C baseline)

- Health contract
- Intent create contract
- Intent create idempotency/correlation contract
- Intent events list contract (`since` cursor semantics)
- Intent stream resume contract (`/events/stream`)
- Intent resolve + terminal immutability contract
- Intent completion delivery contract (`reply_to` inbox visibility)
- Inbox list contract
- Inbox reply contract
- Inbox changes pagination contract
- Webhooks subscriptions contract
- Webhooks events/replay contract
- Baseline suite execution and result model

## Development

```bash
python -m pip install -e ".[dev]"
pytest
```
