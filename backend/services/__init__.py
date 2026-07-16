"""
UltraChat - Services Package
"""

from .profile_service import ProfileService, get_profile_service
from .memory_service import MemoryService, get_memory_service
from .message_tree import MessageTreeService, get_message_tree_service
from .tool_service import ToolService, get_tool_service
from .web_search_service import WebSearchService, get_web_search_service


def get_chat_service():
    """Load the PyTorch-backed service only when Local HF mode is used."""
    from .chat_service import get_chat_service as implementation
    return implementation()


def get_model_service():
    """Load model management only when a local-model endpoint is used."""
    from .model_service import get_model_service as implementation
    return implementation()


def __getattr__(name):
    if name == "ChatService":
        from .chat_service import ChatService
        return ChatService
    if name == "ModelService":
        from .model_service import ModelService
        return ModelService
    if name in {"RemoteChatService", "get_remote_chat_service"}:
        from .remote_chat_service import RemoteChatService, get_remote_chat_service
        return {"RemoteChatService": RemoteChatService, "get_remote_chat_service": get_remote_chat_service}[name]
    raise AttributeError(name)

__all__ = [
    "get_chat_service",
    "get_model_service",
    "ProfileService",
    "get_profile_service",
    "MemoryService",
    "get_memory_service",
    "MessageTreeService",
    "get_message_tree_service",
    "ToolService",
    "get_tool_service",
    "WebSearchService",
    "get_web_search_service",
]
