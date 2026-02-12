# BEAM Mock Server

Local mock implementation of the BEAM contract for pre-live integration testing.

## Run

```bash
cd tools/beam_mock
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8091 --reload
```

## Endpoints

- `GET /healthz`
- `GET /api/v1/assets`
- `POST /api/v1/risks/upsert`

## Configure RiskFabric for Mock

Set in `apps/backend/.env`:

```env
EAM_PLUGIN_NAME=beam_web_service
EAM_PLUGIN_VERSION=v1
EAM_BASE_URL=http://127.0.0.1:8091
EAM_CLIENT_ID=mock-client
EAM_CLIENT_SECRET=mock-secret
BEAM_LIVE_ENABLED=true
BEAM_ASSETS_ENDPOINT=/api/v1/assets
BEAM_RISK_UPSERT_ENDPOINT=/api/v1/risks/upsert
```

Then run:

```bash
cd apps/backend
poetry run python manage.py eam_sync --plugin-name beam_web_service --plugin-version v1
```

## Notes

- Incoming risk upsert payloads are appended to `tools/beam_mock/data/risk_upserts.log`.
- Update `tools/beam_mock/data/assets.json` to simulate BEAM asset changes.
