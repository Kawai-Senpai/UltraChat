"""
UltraChat - SSE Streaming Utilities
Server-Sent Events helpers for real-time streaming responses.
"""

import json
import asyncio
from typing import AsyncGenerator, Any, Dict, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class StreamEventType(str, Enum):
    """Types of streaming events."""
    TOKEN = "token"           # New token generated
    DONE = "done"             # Generation complete
    ERROR = "error"           # Error occurred
    STATUS = "status"         # Status update
    PROGRESS = "progress"     # Progress update (for downloads)
    METADATA = "metadata"     # Metadata about the response


@dataclass
class StreamEvent:
    """A single streaming event."""
    event: StreamEventType
    data: Any
    id: Optional[str] = None
    
    def to_sse(self) -> str:
        """Convert to SSE format."""
        lines = []
        
        if self.id:
            lines.append(f"id: {self.id}")
        
        lines.append(f"event: {self.event.value}")
        
        # Serialize data to JSON
        if isinstance(self.data, dict):
            data_str = json.dumps(self.data)
        elif isinstance(self.data, str):
            data_str = self.data
        else:
            data_str = json.dumps({"value": self.data})
        
        lines.append(f"data: {data_str}")
        lines.append("")  # Empty line to end event
        
        return "\n".join(lines) + "\n"


def create_token_event(token: str, message_id: Optional[str] = None) -> str:
    """Create a token streaming event."""
    return StreamEvent(
        event=StreamEventType.TOKEN,
        data={"token": token},
        id=message_id
    ).to_sse()


def create_done_event(
    message_id: str,
    total_tokens: Optional[int] = None,
    eval_duration: Optional[float] = None,
    context: Optional[list] = None
) -> str:
    """Create a completion event."""
    data = {"message_id": message_id}
    if total_tokens is not None:
        data["total_tokens"] = total_tokens
    if eval_duration is not None:
        data["eval_duration"] = eval_duration
    if context is not None:
        data["context"] = context
    
    return StreamEvent(
        event=StreamEventType.DONE,
        data=data,
        id=message_id
    ).to_sse()


def create_error_event(error: str, code: Optional[str] = None) -> str:
    """Create an error event."""
    data = {"error": error}
    if code:
        data["code"] = code
    
    return StreamEvent(
        event=StreamEventType.ERROR,
        data=data
    ).to_sse()


def create_status_event(status: str, details: Optional[Dict] = None) -> str:
    """Create a status event."""
    data = {"status": status}
    if details:
        data.update(details)
    
    return StreamEvent(
        event=StreamEventType.STATUS,
        data=data
    ).to_sse()


def create_progress_event(
    status: str,
    percent: Optional[float] = None,
    completed: Optional[int] = None,
    total: Optional[int] = None
) -> str:
    """Create a progress event (for downloads)."""
    data = {"status": status}
    if percent is not None:
        data["percent"] = round(percent, 2)
    if completed is not None:
        data["completed"] = completed
    if total is not None:
        data["total"] = total
    
    return StreamEvent(
        event=StreamEventType.PROGRESS,
        data=data
    ).to_sse()


def create_metadata_event(metadata: Dict[str, Any]) -> str:
    """Create a metadata event."""
    return StreamEvent(
        event=StreamEventType.METADATA,
        data=metadata
    ).to_sse()


async def heartbeat_generator(
    interval: float = 15.0
) -> AsyncGenerator[str, None]:
    """
    Generate periodic heartbeat events to keep connection alive.
    Use this in conjunction with actual data streams.
    """
    while True:
        await asyncio.sleep(interval)
        yield ": heartbeat\n\n"


class StreamBuffer:
    """
    Buffer for accumulating streamed content.
    Useful for building up the full response while streaming.
    """
    
    def __init__(self):
        self._content = []
        self._token_count = 0
    
    def add_token(self, token: str):
        """Add a token to the buffer."""
        self._content.append(token)
        self._token_count += 1
    
    @property
    def content(self) -> str:
        """Get the full accumulated content."""
        return "".join(self._content)
    
    @property
    def token_count(self) -> int:
        """Get the number of tokens received."""
        return self._token_count
    
    def clear(self):
        """Clear the buffer."""
        self._content.clear()
        self._token_count = 0
