"""
UltraChat - Memory ORM Models
Database operations for memory/knowledge storage.
Memories are scoped to profiles.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from .database import get_database


class MemoryModel:
    """Database operations for memories (profile-scoped)."""
    
    @staticmethod
    async def create(
        content: str,
        profile_id: Optional[str] = None,
        category: str = "other",
        importance: int = 5,
        source_conversation_id: Optional[str] = None,
        source_message_id: Optional[str] = None,
        embedding: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """Create a new memory (optionally scoped to profile)."""
        db = get_database()
        now = datetime.utcnow().isoformat()
        memory_id = str(uuid.uuid4())
        
        async with db.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO memories 
                (id, profile_id, content, category, importance, source_conversation_id,
                 source_message_id, embedding, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (memory_id, profile_id, content, category, importance,
                 source_conversation_id, source_message_id, embedding, now, now)
            )
            await conn.commit()
        
        return await MemoryModel.get_by_id(memory_id)
    
    @staticmethod
    async def get_by_id(memory_id: str) -> Optional[Dict[str, Any]]:
        """Get a memory by ID."""
        db = get_database()
        return await db.fetch_one(
            "SELECT * FROM memories WHERE id = ?",
            (memory_id,)
        )
    
    @staticmethod
    async def get_all(
        profile_id: Optional[str] = None,
        category: Optional[str] = None,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get all memories with optional filtering (profile-scoped)."""
        db = get_database()
        
        query = "SELECT * FROM memories WHERE 1=1"
        params = []
        
        if active_only:
            query += " AND is_active = 1"
        
        if profile_id:
            query += " AND profile_id = ?"
            params.append(profile_id)
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        query += " ORDER BY importance DESC, created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        return await db.fetch_all(query, tuple(params))
    
    @staticmethod
    async def search(
        query: str,
        profile_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search memories by content (profile-scoped)."""
        db = get_database()
        search_term = f"%{query}%"
        
        sql = """
            SELECT * FROM memories 
            WHERE is_active = 1 AND content LIKE ?
        """
        params = [search_term]
        
        if profile_id:
            sql += " AND profile_id = ?"
            params.append(profile_id)
        
        if category:
            sql += " AND category = ?"
            params.append(category)
        
        sql += " ORDER BY importance DESC, created_at DESC LIMIT ?"
        params.append(limit)
        
        return await db.fetch_all(sql, tuple(params))
    
    @staticmethod
    async def get_for_context(profile_id: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top memories to include in chat context (profile-scoped)."""
        db = get_database()
        
        if profile_id:
            return await db.fetch_all(
                """
                SELECT * FROM memories 
                WHERE is_active = 1 AND profile_id = ?
                ORDER BY importance DESC, updated_at DESC
                LIMIT ?
                """,
                (profile_id, limit)
            )
        else:
            return await db.fetch_all(
                """
                SELECT * FROM memories 
                WHERE is_active = 1 AND profile_id IS NULL
                ORDER BY importance DESC, updated_at DESC
                LIMIT ?
                """,
                (limit,)
            )
    
    @staticmethod
    async def update(memory_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Update a memory."""
        db = get_database()
        
        allowed_fields = ['content', 'category', 'importance', 'is_active', 'embedding', 'profile_id']
        updates = []
        values = []
        
        for field in allowed_fields:
            if field in kwargs:
                updates.append(f"{field} = ?")
                if field == 'is_active':
                    values.append(1 if kwargs[field] else 0)
                else:
                    values.append(kwargs[field])
        
        if not updates:
            return await MemoryModel.get_by_id(memory_id)
        
        updates.append("updated_at = ?")
        values.append(datetime.utcnow().isoformat())
        values.append(memory_id)
        
        async with db.get_connection() as conn:
            await conn.execute(
                f"UPDATE memories SET {', '.join(updates)} WHERE id = ?",
                tuple(values)
            )
            await conn.commit()
        
        return await MemoryModel.get_by_id(memory_id)
    
    @staticmethod
    async def delete(memory_id: str) -> bool:
        """Delete a memory."""
        db = get_database()
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM memories WHERE id = ?",
                (memory_id,)
            )
            await conn.commit()
            return cursor.rowcount > 0
    
    @staticmethod
    async def get_categories() -> List[str]:
        """Get all unique categories."""
        db = get_database()
        rows = await db.fetch_all(
            "SELECT DISTINCT category FROM memories WHERE category IS NOT NULL ORDER BY category"
        )
        return [row['category'] for row in rows]
    
    @staticmethod
    async def get_stats() -> Dict[str, Any]:
        """Get memory statistics."""
        db = get_database()
        
        total = await db.fetch_one("SELECT COUNT(*) as count FROM memories")
        active = await db.fetch_one("SELECT COUNT(*) as count FROM memories WHERE is_active = 1")
        by_category = await db.fetch_all(
            """
            SELECT category, COUNT(*) as count 
            FROM memories 
            WHERE is_active = 1
            GROUP BY category
            """
        )
        
        return {
            "total": total['count'] if total else 0,
            "active": active['count'] if active else 0,
            "by_category": {row['category']: row['count'] for row in by_category}
        }
