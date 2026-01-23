"""
UltraChat - Voice ORM Models
Database operations for voice management (system + user voices).
"""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

from .database import get_database


# System voice mappings - human readable names for system voices
SYSTEM_VOICE_NAMES = {
    "ancient vampire lord.mp3": {"name": "Ancient Vampire Lord", "category": "character", "description": "Dark, ancient vampire narrator"},
    "blondie - seductive and soft-spoken.mp3": {"name": "Seductive Whisper", "category": "character", "description": "Seductive and soft-spoken female voice"},
    "david - deep and engaging storyteller.mp3": {"name": "Deep Storyteller", "category": "narrator", "description": "Deep and engaging male storyteller"},
    "declan - horror, narrator.mp3": {"name": "Horror Narrator", "category": "narrator", "description": "Horror narrator with suspenseful tone"},
    "gravel, deep anti-hero.mp3": {"name": "Gravel Anti-Hero", "category": "character", "description": "Deep gravelly anti-hero voice"},
    "hank - deep and engaging narrator.mp3": {"name": "Engaging Narrator", "category": "narrator", "description": "Deep and engaging male narrator"},
    "jerry b - effortless, cool and laid-back.mp3": {"name": "Cool & Laid-back", "category": "casual", "description": "Effortless, cool and laid-back male voice"},
    "jerry b - jolly santa claus.mp3": {"name": "Jolly Santa", "category": "character", "description": "Jolly Santa Claus voice"},
    "julian - intimate, warm, whispery asmr.mp3": {"name": "Warm ASMR", "category": "asmr", "description": "Intimate, warm, whispery ASMR voice"},
    "lulu lolipop - high-pitched and bubbly.mp3": {"name": "Bubbly", "category": "character", "description": "High-pitched and bubbly female voice"},
    "rich,old storyteller.mp3": {"name": "Wise Elder", "category": "narrator", "description": "Rich, old wise storyteller"},
    "soothing asmr whisperer.mp3": {"name": "ASMR Whisper", "category": "asmr", "description": "Soothing ASMR whisperer"},
    "whispers from the deep dark.mp3": {"name": "Deep Dark Whisper", "category": "horror", "description": "Whispers from the deep dark - horror voice"},
}


class VoiceModel:
    """Database operations for voices."""
    
    @staticmethod
    async def register_system_voices(system_voices_dir: Path) -> int:
        """Register all system voices from the given directory.
        
        Returns the number of voices registered.
        """
        if not system_voices_dir.exists():
            return 0
        
        count = 0
        db = get_database()
        now = datetime.now(timezone.utc).isoformat()
        
        for voice_file in system_voices_dir.iterdir():
            if voice_file.suffix.lower() in ['.mp3', '.wav', '.ogg', '.flac']:
                voice_id = f"system_{voice_file.stem.replace(' ', '_').replace(',', '').lower()}"
                
                # Get display info from mapping or use filename
                voice_info = SYSTEM_VOICE_NAMES.get(voice_file.name, {
                    "name": voice_file.stem.title(),
                    "category": "general",
                    "description": f"System voice: {voice_file.stem}"
                })
                
                # Check if voice already exists
                existing = await db.fetch_one(
                    "SELECT id FROM voices WHERE id = ?",
                    (voice_id,)
                )
                
                if existing:
                    # Update existing voice
                    async with db.get_connection() as conn:
                        await conn.execute(
                            """
                            UPDATE voices SET 
                                display_name = ?, file_path = ?, description = ?,
                                category = ?, updated_at = ?
                            WHERE id = ?
                            """,
                            (voice_info["name"], str(voice_file), voice_info["description"],
                             voice_info["category"], now, voice_id)
                        )
                        await conn.commit()
                else:
                    # Insert new voice
                    async with db.get_connection() as conn:
                        await conn.execute(
                            """
                            INSERT INTO voices 
                            (id, name, display_name, file_path, is_system, description, category, created_at, updated_at)
                            VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)
                            """,
                            (voice_id, voice_file.stem, voice_info["name"], str(voice_file),
                             voice_info["description"], voice_info["category"], now, now)
                        )
                        await conn.commit()
                count += 1
        
        return count
    
    @staticmethod
    async def create(
        name: str,
        file_path: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        category: str = "custom",
        sample_rate: Optional[int] = None,
        duration_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Create a new user voice."""
        db = get_database()
        now = datetime.now(timezone.utc).isoformat()
        voice_id = f"user_{str(uuid.uuid4())[:8]}"
        
        async with db.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO voices 
                (id, name, display_name, file_path, is_system, description, category,
                 sample_rate, duration_seconds, created_at, updated_at)
                VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)
                """,
                (voice_id, name, display_name or name, file_path, description, category,
                 sample_rate, duration_seconds, now, now)
            )
            await conn.commit()
        
        return await VoiceModel.get_by_id(voice_id)
    
    @staticmethod
    async def get_by_id(voice_id: str) -> Optional[Dict[str, Any]]:
        """Get a voice by ID."""
        db = get_database()
        return await db.fetch_one(
            "SELECT * FROM voices WHERE id = ?",
            (voice_id,)
        )
    
    @staticmethod
    async def get_all(include_system: bool = True, include_user: bool = True) -> List[Dict[str, Any]]:
        """Get all voices."""
        db = get_database()
        
        conditions = []
        if include_system and not include_user:
            conditions.append("is_system = 1")
        elif include_user and not include_system:
            conditions.append("is_system = 0")
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        return await db.fetch_all(
            f"SELECT * FROM voices {where_clause} ORDER BY is_system DESC, display_name ASC"
        )
    
    @staticmethod
    async def get_system_voices() -> List[Dict[str, Any]]:
        """Get only system voices."""
        return await VoiceModel.get_all(include_system=True, include_user=False)
    
    @staticmethod
    async def get_user_voices() -> List[Dict[str, Any]]:
        """Get only user-uploaded voices."""
        return await VoiceModel.get_all(include_system=False, include_user=True)
    
    @staticmethod
    async def update(voice_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Update a voice (user voices only)."""
        db = get_database()
        
        # Don't allow updating system voices' core properties
        voice = await VoiceModel.get_by_id(voice_id)
        if not voice:
            return None
        
        allowed_fields = ['name', 'display_name', 'description', 'category']
        if not voice.get('is_system'):
            allowed_fields.extend(['file_path'])
        
        updates = []
        values = []
        
        for field in allowed_fields:
            if field in kwargs and kwargs[field] is not None:
                updates.append(f"{field} = ?")
                values.append(kwargs[field])
        
        if not updates:
            return voice
        
        updates.append("updated_at = ?")
        values.append(datetime.now(timezone.utc).isoformat())
        values.append(voice_id)
        
        async with db.get_connection() as conn:
            await conn.execute(
                f"UPDATE voices SET {', '.join(updates)} WHERE id = ?",
                tuple(values)
            )
            await conn.commit()
        
        return await VoiceModel.get_by_id(voice_id)
    
    @staticmethod
    async def delete(voice_id: str) -> bool:
        """Delete a voice (user voices only)."""
        db = get_database()
        
        # Don't delete system voices
        voice = await VoiceModel.get_by_id(voice_id)
        if not voice or voice.get('is_system'):
            return False
        
        async with db.get_connection() as conn:
            await conn.execute("DELETE FROM voices WHERE id = ?", (voice_id,))
            await conn.commit()
        
        return True
    
    @staticmethod
    async def get_by_category(category: str) -> List[Dict[str, Any]]:
        """Get voices by category."""
        db = get_database()
        return await db.fetch_all(
            "SELECT * FROM voices WHERE category = ? ORDER BY is_system DESC, display_name ASC",
            (category,)
        )
