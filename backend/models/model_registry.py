"""
UltraChat - Model Registry
Database operations for tracking and managing Ollama models.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from .database import get_database


class ModelRegistry:
    """Database operations for model tracking."""
    
    @staticmethod
    async def upsert(
        name: str,
        size: int = 0,
        digest: str = "",
        family: Optional[str] = None,
        parameter_size: Optional[str] = None,
        quantization_level: Optional[str] = None,
        modified_at: Optional[str] = None
    ) -> Dict[str, Any]:
        """Insert or update a model record."""
        db = get_database()
        
        existing = await ModelRegistry.get_by_name(name)
        
        async with db.get_connection() as conn:
            if existing:
                await conn.execute(
                    """
                    UPDATE models SET 
                        size = ?, digest = ?, family = ?,
                        parameter_size = ?, quantization_level = ?, modified_at = ?
                    WHERE name = ?
                    """,
                    (size, digest, family, parameter_size, quantization_level,
                     modified_at, name)
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO models 
                    (name, size, digest, family, parameter_size, quantization_level, modified_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (name, size, digest, family, parameter_size, quantization_level, modified_at)
                )
            await conn.commit()
        
        return await ModelRegistry.get_by_name(name)
    
    @staticmethod
    async def get_by_name(name: str) -> Optional[Dict[str, Any]]:
        """Get a model by name."""
        db = get_database()
        return await db.fetch_one(
            "SELECT * FROM models WHERE name = ?",
            (name,)
        )
    
    @staticmethod
    async def get_all() -> List[Dict[str, Any]]:
        """Get all tracked models."""
        db = get_database()
        return await db.fetch_all(
            """
            SELECT * FROM models 
            ORDER BY is_favorite DESC, use_count DESC, name ASC
            """
        )
    
    @staticmethod
    async def record_usage(name: str):
        """Record that a model was used."""
        db = get_database()
        now = datetime.now(timezone.utc).isoformat()
        
        async with db.get_connection() as conn:
            await conn.execute(
                """
                UPDATE models 
                SET use_count = use_count + 1, last_used_at = ?
                WHERE name = ?
                """,
                (now, name)
            )
            await conn.commit()
    
    @staticmethod
    async def set_favorite(name: str, is_favorite: bool) -> bool:
        """Set or unset a model as favorite."""
        db = get_database()
        
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "UPDATE models SET is_favorite = ? WHERE name = ?",
                (1 if is_favorite else 0, name)
            )
            await conn.commit()
            return cursor.rowcount > 0
    
    @staticmethod
    async def delete(name: str) -> bool:
        """Delete a model from registry."""
        db = get_database()
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM models WHERE name = ?",
                (name,)
            )
            await conn.commit()
            return cursor.rowcount > 0
    
    @staticmethod
    async def sync_with_ollama(models: List[Dict[str, Any]]):
        """
        Sync registry with actual Ollama models.
        Adds new models and removes deleted ones.
        """
        db = get_database()
        
        # Get current model names from Ollama
        ollama_names = {m['name'] for m in models}
        
        # Get current registry names
        registry_models = await ModelRegistry.get_all()
        registry_names = {m['name'] for m in registry_models}
        
        # Add new models
        for model in models:
            details = model.get('details', {}) or {}
            await ModelRegistry.upsert(
                name=model['name'],
                size=model.get('size', 0),
                digest=model.get('digest', ''),
                family=details.get('family'),
                parameter_size=details.get('parameter_size'),
                quantization_level=details.get('quantization_level'),
                modified_at=model.get('modified_at')
            )
        
        # Remove models no longer in Ollama
        removed = registry_names - ollama_names
        for name in removed:
            await ModelRegistry.delete(name)
    
    @staticmethod
    async def get_favorites() -> List[Dict[str, Any]]:
        """Get favorite models."""
        db = get_database()
        return await db.fetch_all(
            "SELECT * FROM models WHERE is_favorite = 1 ORDER BY name ASC"
        )
    
    @staticmethod
    async def get_recent(limit: int = 5) -> List[Dict[str, Any]]:
        """Get recently used models."""
        db = get_database()
        return await db.fetch_all(
            """
            SELECT * FROM models 
            WHERE last_used_at IS NOT NULL
            ORDER BY last_used_at DESC
            LIMIT ?
            """,
            (limit,)
        )
