from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib import error, parse, request

from django.conf import settings

from .base import EamIntegrationPlugin


@dataclass
class BeamApiConfig:
    base_url: str
    client_id: str
    client_secret: str
    timeout_seconds: int
    live_enabled: bool
    assets_endpoint: str
    risk_upsert_endpoint: str


class BeamWebServicePluginV1(EamIntegrationPlugin):
    plugin_name = "beam_web_service"
    plugin_version = "v1"

    def run(self, *, direction: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = context or {}
        config = self._config()

        if not config.live_enabled:
            return self._offline_result(direction=direction, context=context)

        if direction == "inbound":
            payload = self._fetch_assets(config=config, context=context)
        elif direction == "outbound":
            payload = self._push_risk_payload(config=config, context=context)
        else:
            raise ValueError(f"Unsupported direction: {direction}")

        return {
            "plugin": f"{self.plugin_name}:{self.plugin_version}",
            "direction": direction,
            "status": "success",
            "message": "BEAM live sync completed.",
            "details": payload,
        }

    def _offline_result(self, *, direction: str, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "plugin": f"{self.plugin_name}:{self.plugin_version}",
            "direction": direction,
            "status": "success",
            "mode": "offline",
            "message": (
                "BEAM live mode is disabled (BEAM_LIVE_ENABLED=false). "
                "Use this mode during development until live connectivity is available."
            ),
            "ready_for_live_after": "2026-02-25",
            "context": context,
        }

    def _config(self) -> BeamApiConfig:
        return BeamApiConfig(
            base_url=settings.EAM_BASE_URL.rstrip("/"),
            client_id=settings.EAM_CLIENT_ID,
            client_secret=settings.EAM_CLIENT_SECRET,
            timeout_seconds=settings.BEAM_TIMEOUT_SECONDS,
            live_enabled=settings.BEAM_LIVE_ENABLED,
            assets_endpoint=settings.BEAM_ASSETS_ENDPOINT,
            risk_upsert_endpoint=settings.BEAM_RISK_UPSERT_ENDPOINT,
        )

    def _fetch_assets(self, *, config: BeamApiConfig, context: dict[str, Any]) -> dict[str, Any]:
        endpoint = context.get("assets_endpoint", config.assets_endpoint)
        query = context.get("query") or {}
        body = self._request_json(
            method="GET",
            url=self._build_url(config.base_url, endpoint, query=query),
            headers=self._headers(config),
            timeout_seconds=config.timeout_seconds,
        )
        return {"assets_endpoint": endpoint, "response": body}

    def _push_risk_payload(self, *, config: BeamApiConfig, context: dict[str, Any]) -> dict[str, Any]:
        endpoint = context.get("risk_upsert_endpoint", config.risk_upsert_endpoint)
        payload = context.get("risk_payload") or self._default_risk_payload()
        body = self._request_json(
            method="POST",
            url=self._build_url(config.base_url, endpoint),
            headers=self._headers(config),
            timeout_seconds=config.timeout_seconds,
            payload=payload,
        )
        return {"risk_upsert_endpoint": endpoint, "request_payload": payload, "response": body}

    @staticmethod
    def _default_risk_payload() -> dict[str, Any]:
        now_utc = datetime.now(tz=timezone.utc).isoformat()
        return {
            "risks": [
                {
                    "risk_external_key": "RF-MOCK-0001",
                    "title": "Mock outbound risk",
                    "description": "Generated default payload for BEAM mock connectivity tests.",
                    "source": "riskfabric",
                    "category": "operational",
                    "primary_asset_code": "LOK.ODA.001",
                    "asset_codes": ["LOK.ODA.001"],
                    "likelihood": 3,
                    "impact": 3,
                    "inherent_score": 9.0,
                    "residual_score": 6.0,
                    "status": "open",
                    "owner": "risk.owner@example.com",
                    "due_date": None,
                    "treatment": {
                        "strategy": "mitigate",
                        "progress_percent": 20,
                        "notes": "Initial containment actions started.",
                    },
                    "synced_at": now_utc,
                }
            ]
        }

    @staticmethod
    def _headers(config: BeamApiConfig) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Client-Id": config.client_id,
            "X-Client-Secret": config.client_secret,
            "X-Correlation-Id": datetime.now(tz=timezone.utc).strftime("beam-%Y%m%d%H%M%S"),
        }

    @staticmethod
    def _build_url(base_url: str, endpoint: str, query: dict[str, Any] | None = None) -> str:
        endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        url = f"{base_url}{endpoint}"
        if query:
            url = f"{url}?{parse.urlencode(query)}"
        return url

    @staticmethod
    def _request_json(
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        timeout_seconds: int,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = request.Request(url=url, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"BEAM HTTP error {exc.code}: {body}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"BEAM connection error: {exc.reason}") from exc
