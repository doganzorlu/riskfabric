# BEAM Plugin Contract

This document describes the contract used by `beam_web_service:v1`.

## Files

- OpenAPI contract: `packages/contracts/beam-web-service-v1.openapi.yaml`

## Runtime Mapping

- Plugin: `beam_web_service:v1`
- Inbound endpoint env: `BEAM_ASSETS_ENDPOINT` (default: `/api/v1/assets`)
- Outbound endpoint env: `BEAM_RISK_UPSERT_ENDPOINT` (default: `/api/v1/risks/upsert`)
- Live mode gate: `BEAM_LIVE_ENABLED` (`false` during development)

## Development Mode

Use offline mode until live connectivity window:

- `BEAM_LIVE_ENABLED=false`
- Validate with:

```bash
poetry run python manage.py eam_sync --plugin-name beam_web_service --plugin-version v1
```

## Mock Server

- Guide: `docs/integration/beam-mock-server.md`
- Implementation: `tools/beam_mock/app.py`

## Live Cutover Checklist (target: 2026-02-25)

1. Set `BEAM_LIVE_ENABLED=true`.
2. Set production `EAM_BASE_URL`, `EAM_CLIENT_ID`, `EAM_CLIENT_SECRET`.
3. Confirm endpoint paths from BEAM team.
4. Run inbound smoke test.
5. Run outbound upsert test with one controlled risk record.
6. Enable scheduled sync jobs.
