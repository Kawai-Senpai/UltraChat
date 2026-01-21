"""
UltraChat - Model Service
Business logic for model management.
"""

from typing import Optional, Dict, Any, List, AsyncGenerator

from ..core import (
    get_ollama_client,
    OllamaError,
    OllamaConnectionError,
    create_progress_event,
    create_done_event,
    create_error_event,
    create_status_event,
)
from ..models import ModelRegistry


def format_size(size_bytes: int) -> str:
    """Format bytes to human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


class ModelService:
    """
    Handles model operations including:
    - Listing available models
    - Downloading/pulling models
    - Deleting models
    - Model information and tracking
    """
    
    def __init__(self):
        self.ollama = get_ollama_client()
    
    async def check_connection(self) -> bool:
        """Check if Ollama is running."""
        return await self.ollama.check_connection()
    
    async def check_connection_with_info(self) -> Dict[str, Any]:
        """Check if Ollama is running and get version info."""
        try:
            connected = await self.ollama.check_connection()
            version = await self.ollama.get_version() if connected else None
            
            return {
                "connected": connected,
                "version": version,
                "message": "Ollama is running" if connected else "Cannot connect to Ollama"
            }
        except Exception as e:
            return {
                "connected": False,
                "version": None,
                "message": f"Error connecting to Ollama: {str(e)}"
            }
    
    async def list_models(self, sync: bool = True) -> List[Dict[str, Any]]:
        """
        List all available local models.
        If sync=True, also syncs with the model registry.
        """
        try:
            models = await self.ollama.list_models()
            
            # Convert to dicts
            model_dicts = []
            for m in models:
                details = m.details or {}
                model_dict = {
                    "name": m.name,
                    "size": m.size,
                    "size_formatted": format_size(m.size),
                    "digest": m.digest,
                    "modified_at": m.modified_at,
                    "family": details.get("family"),
                    "parameter_size": details.get("parameter_size"),
                    "quantization_level": details.get("quantization_level"),
                    "details": details
                }
                model_dicts.append(model_dict)
            
            # Sync with registry
            if sync and model_dicts:
                await ModelRegistry.sync_with_ollama(model_dicts)
                
                # Merge registry data (favorites, usage stats)
                registry_models = await ModelRegistry.get_all()
                registry_map = {m['name']: m for m in registry_models}
                
                for model in model_dicts:
                    reg = registry_map.get(model['name'], {})
                    model['is_favorite'] = reg.get('is_favorite', False)
                    model['use_count'] = reg.get('use_count', 0)
                    model['last_used_at'] = reg.get('last_used_at')
            
            return model_dicts
            
        except OllamaConnectionError:
            return []
        except OllamaError:
            return []
    
    async def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a model."""
        try:
            info = await self.ollama.show_model(model_name)
            
            # Add registry info
            registry = await ModelRegistry.get_by_name(model_name)
            if registry:
                info['is_favorite'] = registry.get('is_favorite', False)
                info['use_count'] = registry.get('use_count', 0)
                info['last_used_at'] = registry.get('last_used_at')
            
            return info
        except OllamaError:
            return None
    
    async def pull_model(self, model_name: str) -> AsyncGenerator[str, None]:
        """
        Download/pull a model with progress updates.
        Yields SSE formatted events.
        """
        try:
            yield create_status_event("starting", {"model": model_name})
            
            current_layer = None
            
            async for progress in self.ollama.pull_model(model_name):
                # Track layer being downloaded
                if progress.digest and progress.digest != current_layer:
                    current_layer = progress.digest
                    yield create_status_event("downloading_layer", {
                        "digest": progress.digest[:12] if progress.digest else None
                    })
                
                # Yield progress
                yield create_progress_event(
                    status=progress.status,
                    percent=progress.percent,
                    completed=progress.completed,
                    total=progress.total
                )
            
            # Sync with registry after successful pull
            models = await self.list_models(sync=True)
            
            yield create_done_event(
                message_id=model_name,
                total_tokens=None
            )
            
        except OllamaConnectionError as e:
            yield create_error_event(str(e), "connection_error")
        except OllamaError as e:
            yield create_error_event(str(e), "pull_error")
        except Exception as e:
            yield create_error_event(str(e), "unknown_error")
    
    async def delete_model(self, model_name: str) -> Dict[str, Any]:
        """Delete a local model."""
        try:
            success = await self.ollama.delete_model(model_name)
            
            if success:
                # Remove from registry
                await ModelRegistry.delete(model_name)
                return {"success": True, "message": f"Model '{model_name}' deleted"}
            else:
                return {"success": False, "error": "Failed to delete model"}
                
        except OllamaConnectionError as e:
            return {"success": False, "error": str(e)}
        except OllamaError as e:
            return {"success": False, "error": str(e)}
    
    async def set_favorite(self, model_name: str, is_favorite: bool) -> bool:
        """Set or unset a model as favorite."""
        return await ModelRegistry.set_favorite(model_name, is_favorite)
    
    async def get_favorites(self) -> List[Dict[str, Any]]:
        """Get favorite models."""
        return await ModelRegistry.get_favorites()
    
    async def get_recent(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recently used models."""
        return await ModelRegistry.get_recent(limit)


# Global service instance
_model_service: Optional[ModelService] = None


def get_model_service() -> ModelService:
    """Get the global model service instance."""
    global _model_service
    if _model_service is None:
        _model_service = ModelService()
    return _model_service
