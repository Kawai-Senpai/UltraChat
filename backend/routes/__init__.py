"""
UltraChat - Routes Package
"""

from .chat import router as chat_router
from .models import router as models_router
from .profiles import router as profiles_router
from .memory import router as memory_router
from .settings import router as settings_router

__all__ = [
    "chat_router",
    "models_router",
    "profiles_router",
    "memory_router",
    "settings_router",
]
