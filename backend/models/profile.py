"""
UltraChat - Profile ORM Models
Database operations for user profiles.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from .database import get_database
from ..config import get_settings


class ProfileModel:
    """Database operations for profiles."""
    
    @staticmethod
    async def create(
        name: str,
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 40,
        max_tokens: int = 4096,
        context_length: int = 8192,
        model: Optional[str] = None,
        is_default: bool = False,
        voice_enabled: bool = False,
        voice_id: Optional[str] = None,
        stt_model: Optional[str] = None,
        last_mode: str = "chat",
        tools_enabled: Optional[str] = None,
        web_search_enabled: bool = False
    ) -> Dict[str, Any]:
        """Create a new profile."""
        db = get_database()
        now = datetime.now(timezone.utc).isoformat()
        profile_id = str(uuid.uuid4())
        
        # If this is default, unset other defaults
        if is_default:
            await ProfileModel._unset_all_defaults()
        
        async with db.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO profiles 
                (id, name, description, system_prompt, temperature, top_p, top_k,
                 max_tokens, context_length, model, is_default, 
                 voice_enabled, voice_id, stt_model, last_mode, tools_enabled, web_search_enabled,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (profile_id, name, description, system_prompt, temperature,
                 top_p, top_k, max_tokens, context_length, model,
                 1 if is_default else 0, 
                 1 if voice_enabled else 0, voice_id, stt_model, last_mode, tools_enabled,
                 1 if web_search_enabled else 0,
                 now, now)
            )
            await conn.commit()
        
        return await ProfileModel.get_by_id(profile_id)
    
    @staticmethod
    async def _unset_all_defaults():
        """Unset all default profiles."""
        db = get_database()
        async with db.get_connection() as conn:
            await conn.execute("UPDATE profiles SET is_default = 0")
            await conn.commit()
    
    @staticmethod
    async def get_by_id(profile_id: str) -> Optional[Dict[str, Any]]:
        """Get a profile by ID."""
        db = get_database()
        return await db.fetch_one(
            "SELECT * FROM profiles WHERE id = ?",
            (profile_id,)
        )
    
    @staticmethod
    async def get_default() -> Optional[Dict[str, Any]]:
        """Get the default profile."""
        db = get_database()
        profile = await db.fetch_one(
            "SELECT * FROM profiles WHERE is_default = 1 LIMIT 1"
        )
        
        if not profile:
            # Create a default profile if none exists
            settings = get_settings()
            profile = await ProfileModel.create(
                name="Default",
                description="Default chat profile",
                system_prompt="You are a helpful, intelligent assistant. Be concise, accurate, and friendly.",
                temperature=settings.chat_defaults.temperature,
                top_p=settings.chat_defaults.top_p,
                top_k=settings.chat_defaults.top_k,
                max_tokens=settings.chat_defaults.max_tokens,
                context_length=settings.chat_defaults.context_length,
                model=settings.ollama.default_model,
                is_default=True
            )
        
        return profile
    
    @staticmethod
    async def get_all() -> List[Dict[str, Any]]:
        """Get all profiles."""
        db = get_database()
        return await db.fetch_all(
            "SELECT * FROM profiles ORDER BY is_default DESC, name ASC"
        )
    
    @staticmethod
    async def update(profile_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Update a profile."""
        db = get_database()
        
        # Handle is_default specially
        if kwargs.get('is_default'):
            await ProfileModel._unset_all_defaults()
        
        allowed_fields = [
            'name', 'description', 'system_prompt', 'temperature',
            'top_p', 'top_k', 'max_tokens', 'context_length', 'model', 'is_default',
            'voice_enabled', 'voice_id', 'stt_model', 'last_mode', 'tools_enabled', 'web_search_enabled'
        ]
        updates = []
        values = []
        
        for field in allowed_fields:
            if field in kwargs and kwargs[field] is not None:
                updates.append(f"{field} = ?")
                if field in ('is_default', 'voice_enabled', 'web_search_enabled'):
                    values.append(1 if kwargs[field] else 0)
                else:
                    values.append(kwargs[field])
        
        if not updates:
            return await ProfileModel.get_by_id(profile_id)
        
        updates.append("updated_at = ?")
        values.append(datetime.now(timezone.utc).isoformat())
        values.append(profile_id)
        
        async with db.get_connection() as conn:
            await conn.execute(
                f"UPDATE profiles SET {', '.join(updates)} WHERE id = ?",
                tuple(values)
            )
            await conn.commit()
        
        return await ProfileModel.get_by_id(profile_id)
    
    @staticmethod
    async def delete(profile_id: str) -> bool:
        """Delete a profile."""
        db = get_database()
        
        # Don't delete if it's the only profile
        all_profiles = await ProfileModel.get_all()
        if len(all_profiles) <= 1:
            return False
        
        # Check if it's default
        profile = await ProfileModel.get_by_id(profile_id)
        was_default = profile and profile.get('is_default')
        
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM profiles WHERE id = ?",
                (profile_id,)
            )
            await conn.commit()
            
            # If we deleted the default, make another one default
            if was_default and cursor.rowcount > 0:
                remaining = await ProfileModel.get_all()
                if remaining:
                    await ProfileModel.update(remaining[0]['id'], is_default=True)
            
            return cursor.rowcount > 0
    
    @staticmethod
    async def duplicate(profile_id: str, new_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Duplicate a profile."""
        original = await ProfileModel.get_by_id(profile_id)
        if not original:
            return None
        
        return await ProfileModel.create(
            name=new_name or f"{original['name']} (Copy)",
            description=original.get('description'),
            system_prompt=original.get('system_prompt'),
            temperature=original.get('temperature', 0.7),
            top_p=original.get('top_p', 0.9),
            top_k=original.get('top_k', 40),
            max_tokens=original.get('max_tokens', 4096),
            context_length=original.get('context_length', 8192),
            model=original.get('model'),
            is_default=False
        )
