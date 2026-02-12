from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ASSETS_FILE = DATA_DIR / "assets.json"
UPSERT_LOG_FILE = DATA_DIR / "risk_upserts.log"

app = FastAPI(title="RiskFabric BEAM Mock", version="1.0.0")


def _read_assets() -> list[dict[str, Any]]:
    if not ASSETS_FILE.exists():
        return []
    return json.loads(ASSETS_FILE.read_text(encoding="utf-8"))


def _write_upsert_log(payload: dict[str, Any]) -> None:
    UPSERT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    line = {
        "received_at": datetime.now(tz=timezone.utc).isoformat(),
        "payload": payload,
    }
    with UPSERT_LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line, ensure_ascii=False) + "\n")


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": "beam-mock"}


@app.get("/api/v1/assets")
def get_assets(
    updated_since: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=200, ge=1, le=1000),
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
    x_client_secret: str | None = Header(default=None, alias="X-Client-Secret"),
) -> dict[str, Any]:
    if not x_client_id or not x_client_secret:
        raise HTTPException(status_code=401, detail="Missing client credentials")

    items = _read_assets()

    if updated_since:
        try:
            cutoff = datetime.fromisoformat(updated_since.replace("Z", "+00:00"))
            filtered: list[dict[str, Any]] = []
            for item in items:
                updated_at = item.get("updated_at")
                if not updated_at:
                    continue
                item_ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                if item_ts >= cutoff:
                    filtered.append(item)
            items = filtered
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid updated_since format") from exc

    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "items": items[start:end],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@app.post("/api/v1/risks/upsert")
def upsert_risks(
    payload: dict[str, Any],
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
    x_client_secret: str | None = Header(default=None, alias="X-Client-Secret"),
) -> dict[str, Any]:
    if not x_client_id or not x_client_secret:
        raise HTTPException(status_code=401, detail="Missing client credentials")

    risks = payload.get("risks")
    if not isinstance(risks, list) or not risks:
        raise HTTPException(status_code=400, detail="risks must be a non-empty array")

    accepted: list[dict[str, str]] = []
    rejected: list[dict[str, str]] = []

    for item in risks:
        key = str(item.get("risk_external_key", "")).strip()
        if not key:
            rejected.append({"risk_external_key": "", "error": "risk_external_key is required"})
            continue

        accepted.append(
            {
                "risk_external_key": key,
                "beam_risk_id": f"BEAM-{key}",
                "status": "upserted",
            }
        )

    _write_upsert_log(payload)

    return {
        "accepted": accepted,
        "rejected": rejected,
    }
