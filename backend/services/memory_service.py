"""
UltraChat - Memory Service
Business logic for memory/knowledge management.
Memories are scoped to profiles.
"""

from typing import Optional, Dict, Any, List

from ..models import MemoryModel


class MemoryService:
    """
    Handles memory operations including:
    - CRUD operations for memories (profile-scoped)
    - Memory search and retrieval
    - Context building for chat
    """
    
    async def create_memory(
        self,
        content: str,
        profile_id: Optional[str] = None,
        category: str = "other",
        importance: int = 5,
        source_conversation_id: Optional[str] = None,
        source_message_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new memory (optionally scoped to profile)."""
        return await MemoryModel.create(
            content=content,
            profile_id=profile_id,
            category=category,
            importance=importance,
            source_conversation_id=source_conversation_id,
            source_message_id=source_message_id
        )
    
    async def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Get a memory by ID."""
        return await MemoryModel.get_by_id(memory_id)
    
    async def list_memories(
        self,
        profile_id: Optional[str] = None,
        category: Optional[str] = None,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get all memories with optional filtering (profile-scoped)."""
        return await MemoryModel.get_all(
            profile_id=profile_id,
            category=category,
            active_only=active_only,
            limit=limit,
            offset=offset
        )
    
    async def search_memories(
        self,
        query: str,
        profile_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search memories by content (profile-scoped)."""
        return await MemoryModel.search(query, profile_id, category, limit)
    
    async def update_memory(
        self,
        memory_id: str,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Update a memory."""
        return await MemoryModel.update(memory_id, **kwargs)
    
    async def delete_memory(self, memory_id: str) -> Dict[str, Any]:
        """Delete a memory."""
        success = await MemoryModel.delete(memory_id)
        if success:
            return {"success": True, "message": "Memory deleted"}
        return {"success": False, "error": "Failed to delete memory"}
    
    async def toggle_active(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Toggle a memory's active status."""
        memory = await MemoryModel.get_by_id(memory_id)
        if not memory:
            return None
        
        return await MemoryModel.update(
            memory_id,
            is_active=not memory.get('is_active', True)
        )
    
    async def get_for_context(self, profile_id: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top memories to include in chat context (profile-scoped)."""
        return await MemoryModel.get_for_context(profile_id, limit)
    
    async def get_categories(self) -> List[str]:
        """Get all unique memory categories."""
        return await MemoryModel.get_categories()
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return await MemoryModel.get_stats()
    
    async def bulk_update_importance(
        self,
        memory_ids: List[str],
        importance: int
    ) -> Dict[str, Any]:
        """Update importance for multiple memories."""
        updated = 0
        for memory_id in memory_ids:
            result = await MemoryModel.update(memory_id, importance=importance)
            if result:
                updated += 1
        
        return {"updated": updated, "total": len(memory_ids)}
    
    async def extract_from_conversation(
        self,
        conversation_id: str,
        content: str,
        profile_id: Optional[str] = None,
        message_id: Optional[str] = None,
        category: str = "context",
        importance: int = 5
    ) -> Dict[str, Any]:
        """Create a memory from conversation content."""
        return await self.create_memory(
            content=content,
            profile_id=profile_id,
            category=category,
            importance=importance,
            source_conversation_id=conversation_id,
            source_message_id=message_id
        )


# Global service instance
_memory_service: Optional[MemoryService] = None


def get_memory_service() -> MemoryService:
    """Get the global memory service instance."""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service
