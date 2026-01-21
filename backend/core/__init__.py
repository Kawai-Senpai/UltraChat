"""
UltraChat - Core Package
"""

from .ollama_client import (
    OllamaClient,
    OllamaError,
    OllamaConnectionError,
    OllamaModelError,
    ModelInfo,
    PullProgress,
    get_ollama_client,
    close_ollama_client,
)

from .streaming import (
    StreamEventType,
    StreamEvent,
    create_token_event,
    create_done_event,
    create_error_event,
    create_status_event,
    create_progress_event,
    create_metadata_event,
    StreamBuffer,
)

__all__ = [
    "OllamaClient",
    "OllamaError",
    "OllamaConnectionError",
    "OllamaModelError",
    "ModelInfo",
    "PullProgress",
    "get_ollama_client",
    "close_ollama_client",
    "StreamEventType",
    "StreamEvent",
    "create_token_event",
    "create_done_event",
    "create_error_event",
    "create_status_event",
    "create_progress_event",
    "create_metadata_event",
    "StreamBuffer",
]
