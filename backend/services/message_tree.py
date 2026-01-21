"""
UltraChat - Message Tree Service
Business logic for message branching and tree navigation.
"""

from typing import Optional, Dict, Any, List

from ..models import MessageModel, ConversationModel


class MessageTreeService:
    """
    Handles message tree operations including:
    - Branch navigation
    - Tree visualization
    - Branch switching
    """
    
    async def get_tree_structure(
        self,
        conversation_id: str
    ) -> Dict[str, Any]:
        """
        Get the full tree structure of a conversation.
        Returns a nested structure of messages with their branches.
        """
        # Get all messages
        all_messages = await MessageModel.get_conversation_messages(
            conversation_id, active_only=False
        )
        
        if not all_messages:
            return {"root": None, "total_messages": 0, "total_branches": 0}
        
        # Build tree structure
        messages_by_parent = {}
        for msg in all_messages:
            parent_id = msg.get('parent_id')
            if parent_id not in messages_by_parent:
                messages_by_parent[parent_id] = []
            messages_by_parent[parent_id].append(msg)
        
        # Count branches (any node with more than one child)
        total_branches = sum(
            1 for children in messages_by_parent.values()
            if len(children) > 1
        )
        
        def build_node(msg):
            node = {
                "id": msg['id'],
                "role": msg['role'],
                "content": msg['content'][:100] + ('...' if len(msg['content']) > 100 else ''),
                "is_active": msg.get('is_active', True),
                "branch_index": msg.get('branch_index', 0),
                "created_at": msg['created_at'],
                "children": []
            }
            
            children = messages_by_parent.get(msg['id'], [])
            for child in sorted(children, key=lambda x: x.get('branch_index', 0)):
                node["children"].append(build_node(child))
            
            return node
        
        # Build from root messages
        root_messages = messages_by_parent.get(None, [])
        tree = [build_node(msg) for msg in sorted(root_messages, key=lambda x: x.get('branch_index', 0))]
        
        return {
            "roots": tree,
            "total_messages": len(all_messages),
            "total_branches": total_branches
        }
    
    async def get_branches_at(
        self,
        conversation_id: str,
        parent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get all branches at a specific point in the tree."""
        return await MessageModel.get_branch_info(parent_id, conversation_id)
    
    async def switch_to_branch(self, message_id: str) -> Dict[str, Any]:
        """Switch to a different branch."""
        message = await MessageModel.get_by_id(message_id)
        if not message:
            return {"success": False, "error": "Message not found"}
        
        success = await MessageModel.set_active_branch(message_id)
        if success:
            return {"success": True, "message": "Switched to branch"}
        return {"success": False, "error": "Failed to switch branch"}
    
    async def get_path_to_message(
        self,
        message_id: str
    ) -> List[Dict[str, Any]]:
        """Get the path from root to a specific message."""
        path = []
        current_id = message_id
        
        while current_id:
            msg = await MessageModel.get_by_id(current_id)
            if not msg:
                break
            path.insert(0, msg)
            current_id = msg.get('parent_id')
        
        return path
    
    async def get_siblings(
        self,
        message_id: str
    ) -> Dict[str, Any]:
        """Get all sibling messages (same parent)."""
        message = await MessageModel.get_by_id(message_id)
        if not message:
            return {"error": "Message not found"}
        
        parent_id = message.get('parent_id')
        conversation_id = message['conversation_id']
        
        branch_info = await MessageModel.get_branch_info(parent_id, conversation_id)
        
        # Find current message's index
        current_index = 0
        for i, branch in enumerate(branch_info['branches']):
            if branch['id'] == message_id:
                current_index = i
                break
        
        return {
            "siblings": branch_info['branches'],
            "current_index": current_index,
            "total": len(branch_info['branches'])
        }
    
    async def navigate_branches(
        self,
        message_id: str,
        direction: str  # "prev" or "next"
    ) -> Optional[Dict[str, Any]]:
        """Navigate to previous or next sibling branch."""
        siblings_info = await self.get_siblings(message_id)
        
        if "error" in siblings_info:
            return None
        
        siblings = siblings_info['siblings']
        current_index = siblings_info['current_index']
        
        if direction == "prev" and current_index > 0:
            new_message = siblings[current_index - 1]
        elif direction == "next" and current_index < len(siblings) - 1:
            new_message = siblings[current_index + 1]
        else:
            return None
        
        # Switch to this branch
        await MessageModel.set_active_branch(new_message['id'])
        return new_message
    
    async def delete_branch(
        self,
        message_id: str
    ) -> Dict[str, Any]:
        """
        Delete a message and all its descendants (a branch).
        Cannot delete if it's the only branch.
        """
        message = await MessageModel.get_by_id(message_id)
        if not message:
            return {"success": False, "error": "Message not found"}
        
        # Check if there are siblings
        siblings_info = await self.get_siblings(message_id)
        if siblings_info.get('total', 0) <= 1:
            return {"success": False, "error": "Cannot delete the only branch"}
        
        # If this is active, switch to another branch first
        if message.get('is_active'):
            siblings = siblings_info['siblings']
            current_index = siblings_info['current_index']
            
            # Find next best branch
            if current_index > 0:
                await MessageModel.set_active_branch(siblings[current_index - 1]['id'])
            else:
                await MessageModel.set_active_branch(siblings[current_index + 1]['id'])
        
        # Delete the branch
        success = await MessageModel.delete(message_id)
        if success:
            return {"success": True, "message": "Branch deleted"}
        return {"success": False, "error": "Failed to delete branch"}


# Global service instance
_message_tree_service: Optional[MessageTreeService] = None


def get_message_tree_service() -> MessageTreeService:
    """Get the global message tree service instance."""
    global _message_tree_service
    if _message_tree_service is None:
        _message_tree_service = MessageTreeService()
    return _message_tree_service
