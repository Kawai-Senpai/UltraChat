"""
UltraChat - Constants and Defaults
All default values and constants for the application.
"""

# API Configuration
API_VERSION = "v1"
API_PREFIX = f"/api/{API_VERSION}"

# HuggingFace / Model Defaults
DEFAULT_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"  # Small, fast, good for testing
DEFAULT_QUANTIZATION = "fp32"  # Default quantization for downloads (original)

# Chat Defaults
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TOP_P = 0.9
DEFAULT_TOP_K = 50
DEFAULT_MAX_TOKENS = 2048
DEFAULT_CONTEXT_LENGTH = 4096
DEFAULT_REPETITION_PENALTY = 1.1

# Profile Defaults
DEFAULT_PROFILE_NAME = "Default"
DEFAULT_SYSTEM_PROMPT = "You are a helpful, intelligent assistant. Be concise, accurate, and friendly."

# Storage Defaults
DEFAULT_DATA_DIR = "data"
DEFAULT_DB_NAME = "ultrachat.db"
DEFAULT_MEMORIES_DIR = "memories"
DEFAULT_EXPORTS_DIR = "exports"
DEFAULT_MODELS_DIR = "models"

# UI Defaults
DEFAULT_THEME = "dark"
MAX_CONVERSATIONS_SIDEBAR = 50
MAX_MESSAGES_PER_LOAD = 50

# Model Download
MODEL_DOWNLOAD_TIMEOUT = 7200  # 2 hours max for model downloads

# Memory
MAX_MEMORY_ITEMS = 1000
MEMORY_RELEVANCE_THRESHOLD = 0.5

# Speculative Decoding Defaults
DEFAULT_NUM_ASSISTANT_TOKENS = 4  # K value: how many tokens draft model proposes per step
DEFAULT_ASSISTANT_TOKENS_SCHEDULE = "heuristic"  # "constant" or "heuristic" (auto-adjusts K)
DEFAULT_SPECULATIVE_ENABLED = True  # Enable speculative decoding when assistant model is loaded

# Attention Implementation Defaults
DEFAULT_ATTENTION_IMPLEMENTATION = "auto"  # "auto", "flash_attention_2", "sdpa", "eager"
