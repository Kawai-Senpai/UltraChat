"""
UltraChat - Chat ORM Models
Database operations for conversations and messages.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from .database import get_database


class ConversationModel:
    """Database operations for conversations."""
    
    @staticmethod
    async def create(
        title: Optional[str] = None,
        profile_id: Optional[str] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new conversation."""
        db = get_database()
        now = datetime.utcnow().isoformat()
        conv_id = str(uuid.uuid4())
        
        async with db.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO conversations (id, title, profile_id, model, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (conv_id, title, profile_id, model, now, now)
            )
            await conn.commit()
        
        return await ConversationModel.get_by_id(conv_id)
    
    @staticmethod
    async def get_by_id(conv_id: str) -> Optional[Dict[str, Any]]:
        """Get a conversation by ID."""
        db = get_database()
        return await db.fetch_one(
            "SELECT * FROM conversations WHERE id = ?",
            (conv_id,)
        )
    
    @staticmethod
    async def get_all(
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get all conversations, ordered by updated_at."""
        db = get_database()
        
        query = """
            SELECT c.*, 
                   COUNT(m.id) as message_count,
                   (SELECT content FROM messages 
                    WHERE conversation_id = c.id 
                    ORDER BY created_at DESC LIMIT 1) as last_message
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
        """
        
        if not include_archived:
            query += " WHERE c.archived = 0"
        
        query += """
            GROUP BY c.id
            ORDER BY c.pinned DESC, c.updated_at DESC
            LIMIT ? OFFSET ?
        """
        
        return await db.fetch_all(query, (limit, offset))
    
    @staticmethod
    async def update(conv_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Update a conversation."""
        db = get_database()
        
        # Build update query dynamically
        allowed_fields = ['title', 'profile_id', 'model', 'pinned', 'archived']
        updates = []
        values = []
        
        for field in allowed_fields:
            if field in kwargs and kwargs[field] is not None:
                updates.append(f"{field} = ?")
                values.append(kwargs[field])
        
        if not updates:
            return await ConversationModel.get_by_id(conv_id)
        
        updates.append("updated_at = ?")
        values.append(datetime.utcnow().isoformat())
        values.append(conv_id)
        
        async with db.get_connection() as conn:
            await conn.execute(
                f"UPDATE conversations SET {', '.join(updates)} WHERE id = ?",
                tuple(values)
            )
            await conn.commit()
        
        return await ConversationModel.get_by_id(conv_id)
    
    @staticmethod
    async def delete(conv_id: str) -> bool:
        """Delete a conversation and all its messages."""
        db = get_database()
        
        async with db.get_connection() as conn:
            # Delete messages first (foreign key)
            await conn.execute(
                "DELETE FROM messages WHERE conversation_id = ?",
                (conv_id,)
            )
            # Delete conversation
            cursor = await conn.execute(
                "DELETE FROM conversations WHERE id = ?",
                (conv_id,)
            )
            await conn.commit()
            return cursor.rowcount > 0
    
    @staticmethod
    async def touch(conv_id: str):
        """Update the updated_at timestamp."""
        db = get_database()
        async with db.get_connection() as conn:
            await conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), conv_id)
            )
            await conn.commit()
    
    @staticmethod
    async def search(query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search conversations by title or message content."""
        db = get_database()
        search_term = f"%{query}%"
        
        return await db.fetch_all(
            """
            SELECT DISTINCT c.*, 
                   COUNT(m.id) as message_count
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE c.title LIKE ? OR m.content LIKE ?
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            LIMIT ?
            """,
            (search_term, search_term, limit)
        )


class MessageModel:
    """Database operations for messages with tree support."""
    
    @staticmethod
    async def create(
        conversation_id: str,
        role: str,
        content: str,
        parent_id: Optional[str] = None,
        model: Optional[str] = None,
        thinking: Optional[str] = None,
        raw_content: Optional[str] = None,
        tokens_prompt: Optional[int] = None,
        tokens_completion: Optional[int] = None,
        duration_ms: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create a new message."""
        db = get_database()
        now = datetime.utcnow().isoformat()
        msg_id = str(uuid.uuid4())
        
        # Calculate branch index if this is a branch
        branch_index = 0
        if parent_id:
            siblings = await MessageModel.get_children(parent_id)
            branch_index = len(siblings)
        
        async with db.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO messages 
                (id, conversation_id, parent_id, role, content, thinking, raw_content, model, 
                 tokens_prompt, tokens_completion, duration_ms, branch_index, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (msg_id, conversation_id, parent_id, role, content, thinking, raw_content, model,
                 tokens_prompt, tokens_completion, duration_ms, branch_index, now)
            )

            # Make this branch active, deactivate siblings
            if parent_id is None:
                await conn.execute(
                    """
                    UPDATE messages
                    SET is_active = 0
                    WHERE conversation_id = ? AND parent_id IS NULL AND id != ?
                    """,
                    (conversation_id, msg_id)
                )
            else:
                await conn.execute(
                    """
                    UPDATE messages
                    SET is_active = 0
                    WHERE conversation_id = ? AND parent_id = ? AND id != ?
                    """,
                    (conversation_id, parent_id, msg_id)
                )

            await conn.execute(
                "UPDATE messages SET is_active = 1 WHERE id = ?",
                (msg_id,)
            )

            await conn.commit()
        
        # Update conversation timestamp
        await ConversationModel.touch(conversation_id)
        
        return await MessageModel.get_by_id(msg_id)
    
    @staticmethod
    async def get_by_id(msg_id: str) -> Optional[Dict[str, Any]]:
        """Get a message by ID."""
        db = get_database()
        return await db.fetch_one(
            "SELECT * FROM messages WHERE id = ?",
            (msg_id,)
        )
    
    @staticmethod
    async def get_conversation_messages(
        conversation_id: str,
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Get all messages in a conversation."""
        db = get_database()
        
        query = "SELECT * FROM messages WHERE conversation_id = ?"
        params = [conversation_id]
        
        if active_only:
            query += " AND is_active = 1"
        
        query += " ORDER BY created_at ASC"
        
        return await db.fetch_all(query, tuple(params))
    
    @staticmethod
    async def get_active_thread(conversation_id: str) -> List[Dict[str, Any]]:
        """
        Get the currently active message thread (following active branches).
        Returns messages in chronological order.
        """
        messages = await MessageModel.get_conversation_messages(
            conversation_id, 
            active_only=True
        )
        
        # Build thread by following parent chain
        # Start from root messages (no parent) and follow active children
        thread = []
        msg_by_id = {m['id']: m for m in messages}
        msg_by_parent = {}
        
        for m in messages:
            parent = m.get('parent_id')
            if parent not in msg_by_parent:
                msg_by_parent[parent] = []
            msg_by_parent[parent].append(m)
        
        # Find root messages and traverse
        def traverse(parent_id):
            children = msg_by_parent.get(parent_id, [])
            # Sort by branch_index and get active one
            active = [c for c in children if c.get('is_active', True)]
            if active:
                # Take the first active child
                msg = active[0]
                thread.append(msg)
                traverse(msg['id'])
        
        traverse(None)
        return thread
    
    @staticmethod
    async def get_children(parent_id: str) -> List[Dict[str, Any]]:
        """Get all child messages (branches) of a message."""
        db = get_database()
        return await db.fetch_all(
            """
            SELECT * FROM messages 
            WHERE parent_id = ?
            ORDER BY branch_index ASC, created_at ASC
            """,
            (parent_id,)
        )
    
    @staticmethod
    async def get_branch_info(parent_id: Optional[str], conversation_id: str) -> Dict[str, Any]:
        """Get branching information at a given point."""
        db = get_database()
        
        if parent_id:
            branches = await db.fetch_all(
                """
                SELECT * FROM messages 
                WHERE parent_id = ?
                ORDER BY branch_index ASC
                """,
                (parent_id,)
            )
        else:
            # Root level branches
            branches = await db.fetch_all(
                """
                SELECT * FROM messages 
                WHERE conversation_id = ? AND parent_id IS NULL
                ORDER BY branch_index ASC
                """,
                (conversation_id,)
            )
        
        active_index = 0
        for i, b in enumerate(branches):
            if b.get('is_active', True):
                active_index = i
                break
        
        return {
            "parent_id": parent_id,
            "branches": branches,
            "active_index": active_index,
            "count": len(branches)
        }
    
    @staticmethod
    async def set_active_branch(message_id: str) -> bool:
        """
        Set a message as the active branch.
        Deactivates siblings and activates this branch.
        """
        db = get_database()
        
        message = await MessageModel.get_by_id(message_id)
        if not message:
            return False
        
        parent_id = message.get('parent_id')
        conversation_id = message['conversation_id']
        
        async with db.get_connection() as conn:
            # Deactivate all siblings
            if parent_id:
                await conn.execute(
                    "UPDATE messages SET is_active = 0 WHERE parent_id = ?",
                    (parent_id,)
                )
            else:
                await conn.execute(
                    """
                    UPDATE messages SET is_active = 0 
                    WHERE conversation_id = ? AND parent_id IS NULL
                    """,
                    (conversation_id,)
                )
            
            # Activate this message and all its descendants
            await conn.execute(
                "UPDATE messages SET is_active = 1 WHERE id = ?",
                (message_id,)
            )
            
            # Recursively activate first child of each level
            async def activate_children(msg_id):
                children = await db.fetch_all(
                    """
                    SELECT id FROM messages 
                    WHERE parent_id = ? 
                    ORDER BY branch_index ASC LIMIT 1
                    """,
                    (msg_id,)
                )
                for child in children:
                    await conn.execute(
                        "UPDATE messages SET is_active = 1 WHERE id = ?",
                        (child['id'],)
                    )
                    await activate_children(child['id'])
            
            await activate_children(message_id)
            await conn.commit()
        
        return True
    
    @staticmethod
    async def update(msg_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Update a message."""
        db = get_database()
        
        allowed_fields = ['content', 'is_active']
        updates = []
        values = []
        
        for field in allowed_fields:
            if field in kwargs:
                updates.append(f"{field} = ?")
                values.append(kwargs[field])
        
        if not updates:
            return await MessageModel.get_by_id(msg_id)
        
        values.append(msg_id)
        
        async with db.get_connection() as conn:
            await conn.execute(
                f"UPDATE messages SET {', '.join(updates)} WHERE id = ?",
                tuple(values)
            )
            await conn.commit()
        
        return await MessageModel.get_by_id(msg_id)
    
    @staticmethod
    async def delete(msg_id: str) -> bool:
        """Delete a message and all its children."""
        db = get_database()
        
        # Recursively delete children first
        children = await MessageModel.get_children(msg_id)
        for child in children:
            await MessageModel.delete(child['id'])
        
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM messages WHERE id = ?",
                (msg_id,)
            )
            await conn.commit()
            return cursor.rowcount > 0
