"""
UltraChat - Settings Routes
API endpoints for application settings.
"""

from fastapi import APIRouter

from ..models.schemas import SettingsUpdate, SettingsResponse
from ..config import get_settings, get_settings_manager


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
async def get_settings_endpoint():
    """Get current application settings."""
    settings = get_settings()
    manager = get_settings_manager()
    
    return {
        "app_name": settings.app_name,
        "version": settings.version,
        "storage": {
            **settings.storage.model_dump(),
            "db_path": str(manager.get_db_path()),
            "memories_path": str(manager.get_memories_path()),
            "exports_path": str(manager.get_exports_path()),
            "models_path": str(manager.get_models_path()),
        },
        "model": settings.model.model_dump(),
        "chat_defaults": settings.chat_defaults.model_dump(),
        "ui": settings.ui.model_dump(),
    }


@router.patch("")
async def update_settings(data: SettingsUpdate):
    """Update application settings."""
    manager = get_settings_manager()
    
    update_data = {}
    
    if data.storage:
        update_data['storage'] = data.storage.model_dump(exclude_unset=True)
    
    if data.model:
        update_data['model'] = data.model.model_dump(exclude_unset=True)
    
    if data.chat_defaults:
        update_data['chat_defaults'] = data.chat_defaults.model_dump(exclude_unset=True)
    
    if data.ui:
        update_data['ui'] = data.ui.model_dump(exclude_unset=True)
    
    new_settings = manager.update(**update_data)
    
    return {
        "success": True,
        "settings": {
            "app_name": new_settings.app_name,
            "version": new_settings.version,
            "storage": new_settings.storage.model_dump(),
            "model": new_settings.model.model_dump(),
            "chat_defaults": new_settings.chat_defaults.model_dump(),
            "ui": new_settings.ui.model_dump(),
        }
    }


@router.post("/reset")
async def reset_settings():
    """Reset all settings to defaults."""
    manager = get_settings_manager()
    new_settings = manager.reset_to_defaults()
    
    return {
        "success": True,
        "message": "Settings reset to defaults",
        "settings": {
            "app_name": new_settings.app_name,
            "version": new_settings.version,
            "storage": new_settings.storage.model_dump(),
            "model": new_settings.model.model_dump(),
            "chat_defaults": new_settings.chat_defaults.model_dump(),
            "ui": new_settings.ui.model_dump(),
        }
    }


@router.get("/storage/paths")
async def get_storage_paths():
    """Get current storage paths."""
    manager = get_settings_manager()
    
    return {
        "db_path": str(manager.get_db_path()),
        "memories_path": str(manager.get_memories_path()),
        "exports_path": str(manager.get_exports_path()),
        "models_path": str(manager.get_models_path()),
    }
