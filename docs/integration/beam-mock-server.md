# BEAM Mock Server

Use this mock server to validate `beam_web_service:v1` before first live connection.

## Location

- `tools/beam_mock/app.py`
- `tools/beam_mock/data/assets.json`

## Quick Start

```bash
cd tools/beam_mock
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8091 --reload
```

## RiskFabric Configuration for Mock

```env
EAM_PLUGIN_NAME=beam_web_service
EAM_PLUGIN_VERSION=v1
EAM_BASE_URL=http://127.0.0.1:8091
EAM_CLIENT_ID=mock-client
EAM_CLIENT_SECRET=mock-secret
BEAM_LIVE_ENABLED=true
```

## Validate Inbound

```bash
cd apps/backend
poetry run python manage.py eam_sync --plugin-name beam_web_service --plugin-version v1 --direction inbound
```

## Validate Outbound

```bash
cd apps/backend
poetry run python manage.py eam_sync \
  --plugin-name beam_web_service \
  --plugin-version v1 \
  --direction outbound
```

For outbound payload override through API, post to `/api/v1/integration/eam/sync` with `context.risk_payload`.
