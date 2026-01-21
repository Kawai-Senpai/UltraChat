"""
UltraChat - Utility Helpers
Common utility functions.
"""

import re
from datetime import datetime
from typing import Optional


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to a maximum length."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def format_timestamp(iso_string: str, format: str = "%b %d, %Y %I:%M %p") -> str:
    """Format an ISO timestamp string."""
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt.strftime(format)
    except (ValueError, AttributeError):
        return iso_string


def format_duration(milliseconds: int) -> str:
    """Format milliseconds to human readable duration."""
    if milliseconds < 1000:
        return f"{milliseconds}ms"
    
    seconds = milliseconds / 1000
    if seconds < 60:
        return f"{seconds:.1f}s"
    
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}min"
    
    hours = minutes / 60
    return f"{hours:.1f}hr"


def format_token_count(count: int) -> str:
    """Format token count with appropriate suffix."""
    if count < 1000:
        return str(count)
    elif count < 1000000:
        return f"{count/1000:.1f}K"
    else:
        return f"{count/1000000:.1f}M"


def extract_title_from_message(content: str, max_length: int = 50) -> str:
    """Extract a title from message content."""
    # Remove markdown formatting
    content = re.sub(r'[#*_`\[\]()]', '', content)
    # Remove extra whitespace
    content = ' '.join(content.split())
    # Truncate
    return truncate_text(content, max_length)


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    # Remove invalid characters
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    # Replace spaces with underscores
    name = name.replace(' ', '_')
    # Limit length
    return name[:100]


def parse_model_name(full_name: str) -> dict:
    """Parse a model name into components."""
    # Format: name:tag or just name
    parts = full_name.split(':')
    name = parts[0]
    tag = parts[1] if len(parts) > 1 else 'latest'
    
    return {
        "full_name": full_name,
        "name": name,
        "tag": tag
    }


def estimate_tokens(text: str) -> int:
    """Rough estimate of token count (4 chars per token average)."""
    return len(text) // 4


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> list:
    """Split text into overlapping chunks."""
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap
    
    return chunks
