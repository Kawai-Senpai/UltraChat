"""
UltraChat - Memory Routes
API endpoints for memory management.
Memories are scoped to profiles.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional, List

from ..models.schemas import MemoryCreate, MemoryUpdate, MemoryResponse
from ..services import get_memory_service


router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("")
async def list_memories(
    profile_id: Optional[str] = None,
    category: Optional[str] = None,
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0
):
    """Get all memories with optional filtering (profile-scoped)."""
    service = get_memory_service()
    memories = await service.list_memories(
        profile_id=profile_id,
        category=category,
        active_only=active_only,
        limit=limit,
        offset=offset
    )
    return {"memories": memories}


@router.post("")
async def create_memory(data: MemoryCreate):
    """Create a new memory (optionally scoped to profile)."""
    service = get_memory_service()
    memory = await service.create_memory(
        content=data.content,
        profile_id=data.profile_id,
        category=data.category.value,
        importance=data.importance,
        source_conversation_id=data.source_conversation_id,
        source_message_id=data.source_message_id
    )
    return memory


@router.get("/search")
async def search_memories(
    query: str,
    profile_id: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 20
):
    """Search memories by content (profile-scoped)."""
    service = get_memory_service()
    memories = await service.search_memories(query, profile_id, category, limit)
    return {"memories": memories}


@router.get("/categories")
async def get_categories():
    """Get all unique memory categories."""
    service = get_memory_service()
    categories = await service.get_categories()
    return {"categories": categories}


@router.get("/stats")
async def get_stats():
    """Get memory statistics."""
    service = get_memory_service()
    return await service.get_stats()


@router.get("/context")
async def get_context_memories(profile_id: Optional[str] = None, limit: int = 10):
    """Get memories to include in chat context (profile-scoped)."""
    service = get_memory_service()
    memories = await service.get_for_context(profile_id, limit)
    return {"memories": memories}


@router.get("/{memory_id}")
async def get_memory(memory_id: str):
    """Get a memory by ID."""
    service = get_memory_service()
    memory = await service.get_memory(memory_id)
    
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    
    return memory


@router.patch("/{memory_id}")
async def update_memory(memory_id: str, data: MemoryUpdate):
    """Update a memory."""
    service = get_memory_service()
    
    update_data = data.model_dump(exclude_unset=True)
    if 'category' in update_data and update_data['category']:
        update_data['category'] = update_data['category'].value
    
    memory = await service.update_memory(memory_id, **update_data)
    
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    
    return memory


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str):
    """Delete a memory."""
    service = get_memory_service()
    result = await service.delete_memory(memory_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error"))
    
    return result


@router.post("/{memory_id}/toggle")
async def toggle_memory(memory_id: str):
    """Toggle a memory's active status."""
    service = get_memory_service()
    memory = await service.toggle_active(memory_id)
    
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    
    return memory


@router.post("/bulk/importance")
async def bulk_update_importance(memory_ids: List[str], importance: int):
    """Update importance for multiple memories."""
    service = get_memory_service()
    return await service.bulk_update_importance(memory_ids, importance)


@router.post("/extract")
async def extract_memory(
    conversation_id: str,
    content: str,
    message_id: Optional[str] = None,
    category: str = "context",
    importance: int = 5
):
    """Create a memory from conversation content."""
    service = get_memory_service()
    return await service.extract_from_conversation(
        conversation_id=conversation_id,
        content=content,
        message_id=message_id,
        category=category,
        importance=importance
    )
