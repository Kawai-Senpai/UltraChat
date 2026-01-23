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
    thinking: Optional[str] = None
    raw_content: Optional[str] = None
    tool_calls: Optional[str] = None  # JSON string of tool calls performed
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
    enable_thinking: Optional[bool] = None  # Enable/disable model thinking if supported
    # Tool toggles
    tools: Optional[List[str]] = None  # Enabled tool names: ["web_search", "wikipedia", "web_fetch", "calculator"]


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
    model_id: str
    name: str
    size: int
    size_formatted: Optional[str] = None
    quantization: Optional[str] = None  # "4bit", "8bit", "fp16", "fp32"
    downloaded_at: Optional[str] = None
    local_path: Optional[str] = None
    is_loaded: bool = False
    is_favorite: bool = False
    use_count: int = 0
    last_used_at: Optional[datetime] = None


class HFModelSearchResult(BaseModel):
    model_id: str
    author: Optional[str] = None
    downloads: Optional[int] = None
    likes: Optional[int] = None
    pipeline_tag: Optional[str] = None
    tags: List[str] = []
    created_at: Optional[str] = None


class ModelDownloadRequest(BaseModel):
    model_id: str = Field(..., min_length=1)
    quantization: Optional[str] = None  # "4bit", "8bit", "fp16", or None


class ModelLoadRequest(BaseModel):
    model_id: str = Field(..., min_length=1)
    quantization: Optional[str] = None


class ModelDownloadProgress(BaseModel):
    status: str
    model_id: str
    current_file: Optional[str] = None
    completed_bytes: int = 0
    total_bytes: int = 0
    percent: Optional[float] = None


# ============ Settings Schemas ============

class StorageSettingsUpdate(BaseModel):
    data_dir: Optional[str] = None
    memories_dir: Optional[str] = None
    exports_dir: Optional[str] = None
    models_dir: Optional[str] = None


class ModelSettingsUpdate(BaseModel):
    default_model: Optional[str] = None
    default_quantization: Optional[str] = None
    auto_load_last: Optional[bool] = None
    use_torch_compile: Optional[bool] = None


class ChatDefaultsUpdate(BaseModel):
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    top_k: Optional[int] = Field(None, ge=1, le=100)
    max_tokens: Optional[int] = Field(None, ge=1, le=128000)
    context_length: Optional[int] = Field(None, ge=1, le=128000)
    repetition_penalty: Optional[float] = Field(None, ge=1.0, le=2.0)


class UISettingsUpdate(BaseModel):
    theme: Optional[str] = None
    stream_enabled: Optional[bool] = None
    show_timestamps: Optional[bool] = None
    compact_mode: Optional[bool] = None
    code_theme: Optional[str] = None


class SettingsUpdate(BaseModel):
    storage: Optional[StorageSettingsUpdate] = None
    model: Optional[ModelSettingsUpdate] = None
    chat_defaults: Optional[ChatDefaultsUpdate] = None
    ui: Optional[UISettingsUpdate] = None


class SettingsResponse(BaseModel):
    app_name: str
    version: str
    storage: Dict[str, Any]
    model: Dict[str, Any]
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
