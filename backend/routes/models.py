"""
UltraChat - Model Routes
API endpoints for model management.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional

from ..models.schemas import ModelPullRequest
from ..services import get_model_service


router = APIRouter(prefix="/models", tags=["models"])


@router.get("/status")
async def check_ollama_status():
    """Check if Ollama is running and accessible."""
    service = get_model_service()
    status = await service.check_connection_with_info()
    
    return status


@router.get("")
async def list_models():
    """Get all available local models."""
    service = get_model_service()
    models = await service.list_models()
    return {"models": models}


@router.get("/{model_name:path}")
async def get_model_info(model_name: str):
    """Get detailed information about a model."""
    service = get_model_service()
    info = await service.get_model_info(model_name)
    
    if not info:
        raise HTTPException(status_code=404, detail="Model not found")
    
    return info


@router.post("/pull")
async def pull_model(request: ModelPullRequest):
    """
    Download/pull a model.
    Returns Server-Sent Events with progress updates.
    """
    service = get_model_service()
    
    async def generate():
        async for event in service.pull_model(request.name):
            yield event
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.delete("/{model_name:path}")
async def delete_model(model_name: str):
    """Delete a local model."""
    service = get_model_service()
    result = await service.delete_model(model_name)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.post("/{model_name:path}/favorite")
async def set_favorite(model_name: str, is_favorite: bool = True):
    """Set or unset a model as favorite."""
    service = get_model_service()
    success = await service.set_favorite(model_name, is_favorite)
    
    return {"success": success}


@router.get("/favorites/list")
async def get_favorites():
    """Get favorite models."""
    service = get_model_service()
    favorites = await service.get_favorites()
    return {"models": favorites}


@router.get("/recent/list")
async def get_recent(limit: int = 5):
    """Get recently used models."""
    service = get_model_service()
    recent = await service.get_recent(limit)
    return {"models": recent}
