"""
UltraChat - Database Connection and Initialization
Async SQLite database management.
"""

import aiosqlite
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from ..config import get_settings_manager


class Database:
    """
    Async SQLite database manager.
    Handles connections and schema initialization.
    """
    
    _instance: Optional['Database'] = None
    _db_path: Optional[Path] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._db_path is None:
            self._db_path = get_settings_manager().get_db_path()
    
    @asynccontextmanager
    async def get_connection(self):
        """Get a database connection context."""
        conn = await aiosqlite.connect(self._db_path)
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            await conn.close()
    
    async def initialize(self):
        """Create all database tables if they don't exist."""
        async with self.get_connection() as db:
            # Profiles table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    system_prompt TEXT,
                    temperature REAL DEFAULT 0.7,
                    top_p REAL DEFAULT 0.9,
                    top_k INTEGER DEFAULT 40,
                    max_tokens INTEGER DEFAULT 4096,
                    context_length INTEGER DEFAULT 8192,
                    model TEXT,
                    is_default INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Conversations table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    profile_id TEXT,
                    model TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    pinned INTEGER DEFAULT 0,
                    archived INTEGER DEFAULT 0,
                    FOREIGN KEY (profile_id) REFERENCES profiles(id)
                )
            """)
            
            # Messages table with tree support
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    parent_id TEXT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    model TEXT,
                    tokens_prompt INTEGER,
                    tokens_completion INTEGER,
                    duration_ms INTEGER,
                    is_active INTEGER DEFAULT 1,
                    branch_index INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
                    FOREIGN KEY (parent_id) REFERENCES messages(id)
                )
            """)
            
            # Memory table - scoped to profiles
            await db.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    profile_id TEXT,
                    content TEXT NOT NULL,
                    category TEXT,
                    importance INTEGER DEFAULT 5,
                    source_conversation_id TEXT,
                    source_message_id TEXT,
                    embedding BLOB,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (profile_id) REFERENCES profiles(id),
                    FOREIGN KEY (source_conversation_id) REFERENCES conversations(id),
                    FOREIGN KEY (source_message_id) REFERENCES messages(id)
                )
            """)
            
            # Model registry - cached model info
            await db.execute("""
                CREATE TABLE IF NOT EXISTS models (
                    name TEXT PRIMARY KEY,
                    size INTEGER,
                    digest TEXT,
                    family TEXT,
                    parameter_size TEXT,
                    quantization_level TEXT,
                    modified_at TEXT,
                    last_used_at TEXT,
                    use_count INTEGER DEFAULT 0,
                    is_favorite INTEGER DEFAULT 0
                )
            """)
            
            # Create indexes for performance
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_conversation 
                ON messages(conversation_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_parent 
                ON messages(parent_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_updated 
                ON conversations(updated_at DESC)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_category 
                ON memories(category)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_profile 
                ON memories(profile_id)
            """)
            
            await db.commit()
    
    async def execute(self, query: str, params: tuple = ()) -> aiosqlite.Cursor:
        """Execute a query and return cursor."""
        async with self.get_connection() as db:
            cursor = await db.execute(query, params)
            await db.commit()
            return cursor
    
    async def fetch_one(self, query: str, params: tuple = ()) -> Optional[dict]:
        """Fetch a single row."""
        async with self.get_connection() as db:
            cursor = await db.execute(query, params)
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    async def fetch_all(self, query: str, params: tuple = ()) -> list:
        """Fetch all rows."""
        async with self.get_connection() as db:
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


# Global database instance
_db: Optional[Database] = None


def get_database() -> Database:
    """Get the global database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db


async def init_database():
    """Initialize the database."""
    db = get_database()
    await db.initialize()
