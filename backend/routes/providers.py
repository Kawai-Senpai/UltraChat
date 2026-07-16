"""Runtime provider discovery endpoints for the UltraChat stress-test UI."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException

from ..models.schemas import ProviderModelsRequest
from ..services.remote_chat_service import provider_capabilities

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/capabilities")
async def capabilities():
    return {"providers": provider_capabilities()}


@router.post("/models")
async def discover_models(request: ProviderModelsRequest):
    """Discover the ML Junction public catalog from a configurable gateway root."""
    headers = {"Authorization": f"Bearer {request.api_key}"} if request.api_key else {}
    try:
        async with httpx.AsyncClient(base_url=request.base_url.rstrip("/"), timeout=15) as client:
            response = await client.get("/v1/models", headers=headers)
            response.raise_for_status()
        body = response.json()
        records = body.get("data", body.get("models", body if isinstance(body, list) else []))
        models = [
            item.get("id", item.get("model", item.get("name")))
            if isinstance(item, dict)
            else str(item)
            for item in records
            if not isinstance(item, dict) or item.get("platform_available", True)
        ]
        return {"models": [item for item in models if item], "source": "mljunction_catalog"}
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Could not discover models: {exc}") from exc
