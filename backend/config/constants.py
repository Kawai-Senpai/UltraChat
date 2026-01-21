"""
UltraChat - Constants and Defaults
All default values and constants for the application.
"""

# API Configuration
API_VERSION = "v1"
API_PREFIX = f"/api/{API_VERSION}"

# Ollama Defaults
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"

# Chat Defaults
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TOP_P = 0.9
DEFAULT_TOP_K = 40
DEFAULT_MAX_TOKENS = 4096
DEFAULT_CONTEXT_LENGTH = 8192

# Profile Defaults
DEFAULT_PROFILE_NAME = "Default"
DEFAULT_SYSTEM_PROMPT = "You are a helpful, intelligent assistant. Be concise, accurate, and friendly."

# Storage Defaults
DEFAULT_DATA_DIR = "data"
DEFAULT_DB_NAME = "ultrachat.db"
DEFAULT_MEMORIES_DIR = "memories"
DEFAULT_EXPORTS_DIR = "exports"

# UI Defaults
DEFAULT_THEME = "dark"
MAX_CONVERSATIONS_SIDEBAR = 50
MAX_MESSAGES_PER_LOAD = 50

# Model Download
MODEL_PULL_TIMEOUT = 3600  # 1 hour max for model downloads

# Memory
MAX_MEMORY_ITEMS = 1000
MEMORY_RELEVANCE_THRESHOLD = 0.5
