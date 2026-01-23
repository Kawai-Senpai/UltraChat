"""
UltraChat - Storage Utilities
File storage management.
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from ..config import get_settings_manager


class StorageManager:
    """
    Handles file-based storage operations.
    Used for exports, backups, and file-based data.
    """
    
    def __init__(self):
        self.manager = get_settings_manager()
    
    def get_data_dir(self) -> Path:
        """Get the main data directory."""
        return self.manager.get_db_path().parent
    
    def get_exports_dir(self) -> Path:
        """Get the exports directory."""
        path = self.manager.get_exports_path()
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def get_memories_dir(self) -> Path:
        """Get the memories directory."""
        path = self.manager.get_memories_path()
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    async def export_conversation(
        self,
        conversation: Dict[str, Any],
        format: str = "json"
    ) -> Path:
        """
        Export a conversation to file.
        Returns the path to the exported file.
        """
        exports_dir = self.get_exports_dir()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        
        # Create filename from conversation title or ID
        title = conversation.get('title', conversation.get('id', 'conversation'))
        safe_title = "".join(c if c.isalnum() or c in ' -_' else '' for c in title)
        safe_title = safe_title[:50]
        
        if format == "json":
            filename = f"{safe_title}_{timestamp}.json"
            filepath = exports_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(conversation, f, indent=2, ensure_ascii=False)
        
        elif format == "md":
            filename = f"{safe_title}_{timestamp}.md"
            filepath = exports_dir / filename
            
            content = self._conversation_to_markdown(conversation)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        
        elif format == "txt":
            filename = f"{safe_title}_{timestamp}.txt"
            filepath = exports_dir / filename
            
            content = self._conversation_to_text(conversation)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        return filepath
    
    def _conversation_to_markdown(self, conversation: Dict[str, Any]) -> str:
        """Convert conversation to Markdown format."""
        lines = []
        
        title = conversation.get('title', 'Conversation')
        lines.append(f"# {title}\n")
        
        if conversation.get('created_at'):
            lines.append(f"*Created: {conversation['created_at']}*\n")
        
        lines.append("---\n")
        
        for msg in conversation.get('messages', []):
            role = msg.get('role', 'unknown').title()
            content = msg.get('content', '')
            
            if role == 'User':
                lines.append(f"## 👤 User\n\n{content}\n")
            elif role == 'Assistant':
                lines.append(f"## 🤖 Assistant\n\n{content}\n")
            elif role == 'System':
                lines.append(f"## ⚙️ System\n\n{content}\n")
            
            lines.append("---\n")
        
        return "\n".join(lines)
    
    def _conversation_to_text(self, conversation: Dict[str, Any]) -> str:
        """Convert conversation to plain text format."""
        lines = []
        
        title = conversation.get('title', 'Conversation')
        lines.append(f"{title}")
        lines.append("=" * len(title))
        lines.append("")
        
        for msg in conversation.get('messages', []):
            role = msg.get('role', 'unknown').upper()
            content = msg.get('content', '')
            
            lines.append(f"[{role}]")
            lines.append(content)
            lines.append("")
            lines.append("-" * 40)
            lines.append("")
        
        return "\n".join(lines)
    
    async def export_all_conversations(
        self,
        conversations: List[Dict[str, Any]],
        format: str = "json"
    ) -> Path:
        """Export all conversations to a single file."""
        exports_dir = self.get_exports_dir()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        
        filename = f"all_conversations_{timestamp}.{format}"
        filepath = exports_dir / filename
        
        if format == "json":
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({"conversations": conversations}, f, indent=2, ensure_ascii=False)
        else:
            raise ValueError(f"Bulk export only supports JSON format")
        
        return filepath
    
    async def export_memories(self, memories: List[Dict[str, Any]]) -> Path:
        """Export all memories to JSON."""
        exports_dir = self.get_exports_dir()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        
        filename = f"memories_{timestamp}.json"
        filepath = exports_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({"memories": memories}, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    async def import_memories(self, filepath: Path) -> List[Dict[str, Any]]:
        """Import memories from JSON file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data.get('memories', [])
    
    def list_exports(self) -> List[Dict[str, Any]]:
        """List all export files."""
        exports_dir = self.get_exports_dir()
        exports = []
        
        for file in exports_dir.iterdir():
            if file.is_file():
                stat = file.stat()
                exports.append({
                    "name": file.name,
                    "path": str(file),
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat()
                })
        
        return sorted(exports, key=lambda x: x['created'], reverse=True)
    
    def delete_export(self, filename: str) -> bool:
        """Delete an export file."""
        exports_dir = self.get_exports_dir()
        filepath = exports_dir / filename
        
        if filepath.exists() and filepath.is_file():
            filepath.unlink()
            return True
        return False
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage usage statistics."""
        data_dir = self.get_data_dir()
        
        total_size = 0
        file_count = 0
        
        for root, dirs, files in os.walk(data_dir):
            for file in files:
                filepath = Path(root) / file
                total_size += filepath.stat().st_size
                file_count += 1
        
        return {
            "data_dir": str(data_dir),
            "total_size": total_size,
            "total_size_formatted": self._format_size(total_size),
            "file_count": file_count
        }
    
    def _format_size(self, size_bytes: int) -> str:
        """Format bytes to human readable."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"


# Global instance
_storage_manager: Optional[StorageManager] = None


def get_storage_manager() -> StorageManager:
    """Get the global storage manager instance."""
    global _storage_manager
    if _storage_manager is None:
        _storage_manager = StorageManager()
    return _storage_manager
