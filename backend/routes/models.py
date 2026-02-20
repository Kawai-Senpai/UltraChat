"""
UltraChat - Model Routes
API endpoints for HuggingFace model management.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Optional, List
from pydantic import BaseModel

from ..services import get_model_service


router = APIRouter(prefix="/models", tags=["models"])


# ============================================
# Request/Response Schemas
# ============================================

class ModelDownloadRequest(BaseModel):
    """Request to download a model with multiple quantization options."""
    model_id: str
    quantizations: Optional[List[str]] = None  # ["4bit", "8bit", "fp16"] or None for fp32
    keep_cache: bool = False  # Keep raw HuggingFace files after quantization


class ModelLoadRequest(BaseModel):
    """Request to load a model into memory."""
    model_id: str
    quantization: Optional[str] = None


class AssistantModelLoadRequest(BaseModel):
    """Request to load an assistant model for speculative decoding."""
    model_id: str
    quantization: Optional[str] = None


class ModelDeleteRequest(BaseModel):
    """Request to delete a model."""
    model_id: str
    quantization: Optional[str] = None


# ============================================
# System Status
# ============================================

@router.get("/status")
async def get_system_status():
    """Get system status including GPU info and loaded model."""
    service = get_model_service()
    status = await service.get_status()
    return status


# ============================================
# HuggingFace Model Search
# ============================================

@router.get("/search")
async def search_hf_models(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100)
):
    """Search HuggingFace for text generation models."""
    service = get_model_service()
    models = await service.search_models(q, limit=limit)
    return {"models": models}


@router.get("/popular")
async def get_popular_models(limit: int = Query(20, ge=1, le=100)):
    """Get popular text generation models from HuggingFace."""
    service = get_model_service()
    models = await service.get_popular_models(limit=limit)
    return {"models": models}


@router.get("/hf/{model_id:path}")
async def get_hf_model_info(model_id: str):
    """Get detailed info about a HuggingFace model."""
    service = get_model_service()
    info = await service.get_hf_model_info(model_id)
    
    if not info:
        raise HTTPException(status_code=404, detail="Model not found on HuggingFace")
    
    return info


# ============================================
# Local Model Management
# ============================================

@router.get("")
@router.get("/local")
async def list_local_models():
    """Get all locally downloaded models."""
    service = get_model_service()
    models = await service.list_local_models()
    return {"models": models}


@router.post("/download")
async def download_model(request: ModelDownloadRequest):
    """
    Download a model from HuggingFace with multiple quantization options.
    Returns Server-Sent Events with progress updates.
    
    Example request:
    {
        "model_id": "meta-llama/Llama-2-7b-chat-hf",
        "quantizations": ["4bit", "8bit"],  // Downloads both 4-bit and 8-bit versions
        "keep_cache": false  // Delete raw files after quantization
    }
    """
    service = get_model_service()
    
    async def generate():
        async for event in service.download_model(
            request.model_id,
            request.quantizations,
            request.keep_cache,
        ):
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


@router.post("/delete")
async def delete_model(request: ModelDeleteRequest):
    """Delete a locally downloaded model."""
    service = get_model_service()
    result = await service.delete_model(request.model_id, request.quantization)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.delete("/{model_id:path}")
async def delete_model_by_path(model_id: str, quantization: Optional[str] = None):
    """Delete a locally downloaded model by path."""
    service = get_model_service()
    result = await service.delete_model(model_id, quantization)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


# ============================================
# Model Loading/Unloading
# ============================================

@router.post("/load")
async def load_model(request: ModelLoadRequest):
    """Load a model into GPU memory."""
    service = get_model_service()
    result = await service.load_model(request.model_id, request.quantization)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.post("/unload")
async def unload_model():
    """Unload the current model from memory."""
    service = get_model_service()
    result = await service.unload_model()
    return result


@router.get("/loaded")
async def get_loaded_model():
    """Get info about the currently loaded model."""
    service = get_model_service()
    loaded = await service.get_loaded_model()
    
    if not loaded:
        return {"loaded": False}
    
    return {"loaded": True, **loaded}


# ============================================
# Favorites & Recent
# ============================================

@router.post("/{model_id:path}/favorite")
async def set_favorite(model_id: str, is_favorite: bool = True):
    """Set or unset a model as favorite."""
    service = get_model_service()
    success = await service.set_favorite(model_id, is_favorite)
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


# ============================================
# Assistant Model (Speculative Decoding)
# ============================================

@router.get("/assistant/status")
async def get_assistant_status():
    """Get status of the assistant model for speculative decoding."""
    service = get_model_service()
    status = await service.get_assistant_status()
    return status


@router.post("/assistant/load")
async def load_assistant_model(request: AssistantModelLoadRequest):
    """Load an assistant model for speculative decoding."""
    service = get_model_service()
    result = await service.load_assistant_model(request.model_id, request.quantization)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.post("/assistant/unload")
async def unload_assistant_model():
    """Unload the assistant model."""
    service = get_model_service()
    result = await service.unload_assistant_model()
    return result
