"""
UltraChat - Application Settings
Configurable settings with environment variable support and persistent storage.
"""

import os
import json
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from .constants import (
    DEFAULT_MODEL,
    DEFAULT_QUANTIZATION,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DEFAULT_TOP_K,
    DEFAULT_MAX_TOKENS,
    DEFAULT_CONTEXT_LENGTH,
    DEFAULT_REPETITION_PENALTY,
    DEFAULT_DATA_DIR,
    DEFAULT_DB_NAME,
    DEFAULT_MEMORIES_DIR,
    DEFAULT_EXPORTS_DIR,
    DEFAULT_MODELS_DIR,
    DEFAULT_THEME,
)


class StorageSettings(BaseModel):
    """Storage path configuration."""
    data_dir: str = DEFAULT_DATA_DIR
    db_name: str = DEFAULT_DB_NAME
    memories_dir: str = DEFAULT_MEMORIES_DIR
    exports_dir: str = DEFAULT_EXPORTS_DIR
    models_dir: str = DEFAULT_MODELS_DIR
    
    @property
    def db_path(self) -> str:
        return str(Path(self.data_dir) / self.db_name)
    
    @property
    def memories_path(self) -> str:
        return str(Path(self.data_dir) / self.memories_dir)
    
    @property
    def exports_path(self) -> str:
        return str(Path(self.data_dir) / self.exports_dir)
    
    @property
    def models_path(self) -> str:
        return str(Path(self.data_dir) / self.models_dir)


class ModelSettings(BaseModel):
    """Model configuration."""
    default_model: str = DEFAULT_MODEL
    default_quantization: str = DEFAULT_QUANTIZATION
    auto_load_last: bool = True  # Auto-load last used model on startup


class ChatDefaults(BaseModel):
    """Default chat parameters."""
    temperature: float = DEFAULT_TEMPERATURE
    top_p: float = DEFAULT_TOP_P
    top_k: int = DEFAULT_TOP_K
    max_tokens: int = DEFAULT_MAX_TOKENS
    context_length: int = DEFAULT_CONTEXT_LENGTH
    repetition_penalty: float = DEFAULT_REPETITION_PENALTY


class UISettings(BaseModel):
    """UI configuration."""
    theme: str = DEFAULT_THEME
    stream_enabled: bool = True
    show_timestamps: bool = True
    compact_mode: bool = False
    code_theme: str = "monokai"


class AppSettings(BaseSettings):
    """Main application settings."""
    app_name: str = "UltraChat"
    version: str = "1.0.0"
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = 8000
    
    # Sub-settings (loaded from config file)
    storage: StorageSettings = StorageSettings()
    model: ModelSettings = ModelSettings()
    chat_defaults: ChatDefaults = ChatDefaults()
    ui: UISettings = UISettings()
    
    class Config:
        env_prefix = "ULTRACHAT_"


class SettingsManager:
    """
    Manages application settings with persistence.
    Settings are stored in a JSON file within the data directory.
    """
    
    _instance: Optional['SettingsManager'] = None
    _settings: Optional[AppSettings] = None
    _config_path: Optional[Path] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._settings is None:
            self._load_settings()
    
    def _get_config_path(self) -> Path:
        """Get the configuration file path."""
        # First check for environment variable
        custom_dir = os.environ.get("ULTRACHAT_DATA_DIR")
        if custom_dir:
            base_dir = Path(custom_dir)
        else:
            # Default to data directory next to backend
            base_dir = Path(__file__).parent.parent.parent / "data"
        
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir / "config.json"
    
    def _load_settings(self):
        """Load settings from file or create defaults."""
        self._config_path = self._get_config_path()
        
        if self._config_path.exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._settings = AppSettings(**data)
            except Exception as e:
                print(f"Warning: Could not load config: {e}. Using defaults.")
                self._settings = AppSettings()
        else:
            self._settings = AppSettings()
            self._save_settings()
        
        # Ensure directories exist
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Create necessary directories."""
        storage = self._settings.storage
        
        # Make paths absolute relative to config file location
        base_dir = self._config_path.parent
        
        dirs_to_create = [
            base_dir,
            base_dir / storage.memories_dir,
            base_dir / storage.exports_dir,
        ]
        
        for dir_path in dirs_to_create:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def _save_settings(self):
        """Persist settings to file."""
        if self._config_path and self._settings:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._settings.model_dump(), f, indent=2)
    
    @property
    def settings(self) -> AppSettings:
        """Get current settings."""
        return self._settings
    
    def get(self, key: str, default=None):
        """Get a setting value by key (supports dot notation)."""
        keys = key.split(".")
        value = self._settings.model_dump()
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def update(self, **kwargs) -> AppSettings:
        """Update settings and persist."""
        current_data = self._settings.model_dump()
        
        # Deep merge updates
        for key, value in kwargs.items():
            if key in current_data:
                if isinstance(current_data[key], dict) and isinstance(value, dict):
                    current_data[key].update(value)
                else:
                    current_data[key] = value
        
        self._settings = AppSettings(**current_data)
        self._save_settings()
        self._ensure_directories()
        return self._settings
    
    def get_absolute_path(self, relative_path: str) -> Path:
        """Convert a relative storage path to absolute."""
        if Path(relative_path).is_absolute():
            return Path(relative_path)
        return self._config_path.parent / relative_path
    
    def get_db_path(self) -> Path:
        """Get absolute database path."""
        return self.get_absolute_path(self._settings.storage.db_name)
    
    def get_memories_path(self) -> Path:
        """Get absolute memories directory path."""
        return self.get_absolute_path(self._settings.storage.memories_dir)
    
    def get_exports_path(self) -> Path:
        """Get absolute exports directory path."""
        return self.get_absolute_path(self._settings.storage.exports_dir)
    
    def get_models_path(self) -> Path:
        """Get absolute models directory path."""
        return self.get_absolute_path(self._settings.storage.models_dir)
    
    def reset_to_defaults(self) -> AppSettings:
        """Reset all settings to defaults."""
        self._settings = AppSettings()
        self._save_settings()
        return self._settings


# Global settings instance
def get_settings() -> AppSettings:
    """Get the global settings instance."""
    return SettingsManager().settings


def get_settings_manager() -> SettingsManager:
    """Get the settings manager instance."""
    return SettingsManager()
