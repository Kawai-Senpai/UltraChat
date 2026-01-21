"""
UltraChat - Pydantic Schemas
Request/Response models for API endpoints.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


# ============ Enums ============

class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class MemoryCategory(str, Enum):
    FACT = "fact"
    PREFERENCE = "preference"
    INSTRUCTION = "instruction"
    CONTEXT = "context"
    OTHER = "other"


# ============ Profile Schemas ============

class ProfileBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    top_k: int = Field(default=40, ge=1, le=100)
    max_tokens: int = Field(default=4096, ge=1, le=128000)
    context_length: int = Field(default=8192, ge=1, le=128000)
    model: Optional[str] = None


class ProfileCreate(ProfileBase):
    is_default: bool = False


class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    top_k: Optional[int] = Field(None, ge=1, le=100)
    max_tokens: Optional[int] = Field(None, ge=1, le=128000)
    context_length: Optional[int] = Field(None, ge=1, le=128000)
    model: Optional[str] = None
    is_default: Optional[bool] = None


class ProfileResponse(ProfileBase):
    id: str
    is_default: bool
    created_at: datetime
    updated_at: datetime


# ============ Message Schemas ============

class MessageBase(BaseModel):
    role: MessageRole
    content: str


class MessageCreate(MessageBase):
    parent_id: Optional[str] = None


class MessageResponse(MessageBase):
    id: str
    conversation_id: str
    parent_id: Optional[str] = None
    model: Optional[str] = None
    tokens_prompt: Optional[int] = None
    tokens_completion: Optional[int] = None
    duration_ms: Optional[int] = None
    is_active: bool = True
    branch_index: int = 0
    created_at: datetime
    children: Optional[List['MessageResponse']] = None


class MessageEdit(BaseModel):
    content: str


class MessageBranch(BaseModel):
    """Info about message branches at a given point."""
    parent_id: Optional[str]
    branches: List[MessageResponse]
    active_index: int


# ============ Conversation Schemas ============

class ConversationCreate(BaseModel):
    title: Optional[str] = None
    profile_id: Optional[str] = None
    model: Optional[str] = None


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    profile_id: Optional[str] = None
    model: Optional[str] = None
    pinned: Optional[bool] = None
    archived: Optional[bool] = None


class ConversationResponse(BaseModel):
    id: str
    title: Optional[str] = None
    profile_id: Optional[str] = None
    model: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    pinned: bool = False
    archived: bool = False
    message_count: Optional[int] = None
    last_message: Optional[str] = None


class ConversationDetail(ConversationResponse):
    messages: List[MessageResponse] = []
    profile: Optional[ProfileResponse] = None


# ============ Chat Schemas ============

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str
    parent_id: Optional[str] = None  # For branching
    model: Optional[str] = None
    profile_id: Optional[str] = None
    stream: bool = True
    options: Optional[Dict[str, Any]] = None
    # Feature toggles
    web_search: bool = False  # Enable web search
    use_memory: bool = True  # Use memory context


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    content: str
    model: str
    tokens_prompt: Optional[int] = None
    tokens_completion: Optional[int] = None
    duration_ms: Optional[int] = None


class RegenerateRequest(BaseModel):
    message_id: str
    model: Optional[str] = None
    options: Optional[Dict[str, Any]] = None


# ============ Memory Schemas ============

class MemoryCreate(BaseModel):
    content: str = Field(..., min_length=1)
    profile_id: Optional[str] = None  # Scope to profile
    category: MemoryCategory = MemoryCategory.OTHER
    importance: int = Field(default=5, ge=1, le=10)
    source_conversation_id: Optional[str] = None
    source_message_id: Optional[str] = None


class MemoryUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1)
    category: Optional[MemoryCategory] = None
    importance: Optional[int] = Field(None, ge=1, le=10)
    is_active: Optional[bool] = None
    profile_id: Optional[str] = None


class MemoryResponse(BaseModel):
    id: str
    content: str
    category: MemoryCategory
    importance: int
    source_conversation_id: Optional[str] = None
    source_message_id: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


# ============ Model Schemas ============

class ModelInfo(BaseModel):
    name: str
    size: int
    digest: str
    family: Optional[str] = None
    parameter_size: Optional[str] = None
    quantization_level: Optional[str] = None
    modified_at: Optional[str] = None
    is_favorite: bool = False
    use_count: int = 0
    last_used_at: Optional[datetime] = None


class ModelPullRequest(BaseModel):
    name: str = Field(..., min_length=1)


class ModelPullProgress(BaseModel):
    status: str
    digest: Optional[str] = None
    total: Optional[int] = None
    completed: Optional[int] = None
    percent: Optional[float] = None


# ============ Settings Schemas ============

class StorageSettingsUpdate(BaseModel):
    data_dir: Optional[str] = None
    memories_dir: Optional[str] = None
    exports_dir: Optional[str] = None


class OllamaSettingsUpdate(BaseModel):
    host: Optional[str] = None
    default_model: Optional[str] = None
    timeout: Optional[int] = None


class ChatDefaultsUpdate(BaseModel):
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    top_k: Optional[int] = Field(None, ge=1, le=100)
    max_tokens: Optional[int] = Field(None, ge=1, le=128000)
    context_length: Optional[int] = Field(None, ge=1, le=128000)


class UISettingsUpdate(BaseModel):
    theme: Optional[str] = None
    stream_enabled: Optional[bool] = None
    show_timestamps: Optional[bool] = None
    compact_mode: Optional[bool] = None
    code_theme: Optional[str] = None


class SettingsUpdate(BaseModel):
    storage: Optional[StorageSettingsUpdate] = None
    ollama: Optional[OllamaSettingsUpdate] = None
    chat_defaults: Optional[ChatDefaultsUpdate] = None
    ui: Optional[UISettingsUpdate] = None


class SettingsResponse(BaseModel):
    app_name: str
    version: str
    storage: Dict[str, Any]
    ollama: Dict[str, Any]
    chat_defaults: Dict[str, Any]
    ui: Dict[str, Any]


# ============ Generic Responses ============

class SuccessResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
    code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    has_more: bool
