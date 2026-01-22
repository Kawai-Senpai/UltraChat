"""
UltraChat - Model Service
Business logic for HuggingFace model management with PyTorch.
"""

import torch
from typing import Optional, Dict, Any, List, AsyncGenerator

from ..core import (
    get_model_manager,
    ModelError,
    ModelNotFoundError,
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


def normalize_quantization_value(quantization: Optional[str]) -> Optional[str]:
    """Normalize quantization inputs. Returns None for full precision/original."""
    if quantization is None:
        return None

    if isinstance(quantization, str):
        normalized = quantization.strip().lower()
        if normalized in ("fp32", "original", "full", "none", "default"):
            return None
        if normalized in ("4bit", "8bit", "fp16"):
            return normalized
        return normalized

    return quantization


def normalize_quantization_list(quantizations: Optional[List[str]]) -> List[Optional[str]]:
    """Normalize quantization list and remove duplicates while preserving order."""
    normalized: List[Optional[str]] = []
    if quantizations:
        for quant in quantizations:
            value = normalize_quantization_value(quant)
            if value not in normalized:
                normalized.append(value)
    if not normalized:
        normalized = [None]
    return normalized


def quantization_label(quantization: Optional[str]) -> str:
    """Human-friendly quantization label for UI."""
    return "original" if quantization is None else str(quantization)


class ModelService:
    """
    Handles HuggingFace model operations including:
    - Searching and browsing HF models
    - Downloading with quantization
    - Loading/unloading models
    - GPU management
    """
    
    def __init__(self):
        self.manager = get_model_manager()
    
    async def get_status(self) -> Dict[str, Any]:
        """Get system status including GPU info."""
        gpu_info = self.manager.gpu_info
        
        return {
            "gpu": gpu_info,
            "gpu_available": gpu_info.get("available", False),
            "gpu_name": gpu_info.get("device_name") if gpu_info.get("available") else None,
            "gpu_memory_total": format_size(gpu_info.get("memory_total", 0)) if gpu_info.get("available") else None,
            "gpu_memory_free": format_size(gpu_info.get("memory_free", 0)) if gpu_info.get("available") else None,
            "current_model": self.manager.current_model,
            "is_model_loaded": self.manager.is_model_loaded,
            "device": self.manager.device,
            "pytorch_version": torch.__version__,
            "cuda_version": torch.version.cuda if torch.cuda.is_available() else None,
        }
    
    async def search_models(
        self,
        query: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search HuggingFace for text generation models."""
        try:
            return await self.manager.search_models(query, limit=limit)
        except Exception as e:
            return []
    
    async def get_popular_models(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get popular text generation models from HuggingFace."""
        try:
            return await self.manager.get_popular_models(limit=limit)
        except Exception as e:
            return []
    
    async def get_hf_model_info(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed info about a HuggingFace model."""
        try:
            return await self.manager.get_model_info(model_id)
        except ModelNotFoundError:
            return None
        except Exception:
            return None
    
    async def list_local_models(self) -> List[Dict[str, Any]]:
        """List all locally downloaded models."""
        models = self.manager.list_local_models()
        
        # Get registry data for favorites, usage stats
        registry_models = await ModelRegistry.get_all()
        registry_map = {m['name']: m for m in registry_models}
        
        model_dicts = []
        for m in models:
            model_dict = {
                "model_id": m.model_id,
                "name": m.name,
                "size": m.size_bytes,
                "size_formatted": m.size_formatted,
                "quantization": m.quantization,
                "downloaded_at": m.downloaded_at,
                "local_path": m.local_path,
                "is_loaded": m.is_loaded,
            }
            
            # Add registry data
            reg_key = f"{m.model_id}__{m.quantization}" if m.quantization else m.model_id
            reg = registry_map.get(reg_key, {})
            model_dict['is_favorite'] = reg.get('is_favorite', False)
            model_dict['use_count'] = reg.get('use_count', 0)
            model_dict['last_used_at'] = reg.get('last_used_at')
            
            model_dicts.append(model_dict)
        
        return model_dicts
    
    async def download_model(
        self,
        model_id: str,
        quantizations: Optional[List[str]] = None,
        keep_cache: bool = False,
    ) -> AsyncGenerator[str, None]:
        """
        Download a model from HuggingFace with multiple quantization options.
        Yields SSE formatted events.
        
        Args:
            model_id: HuggingFace model ID
            quantizations: List of quantization types ["4bit", "8bit", "fp16"]
                          If None, downloads full precision (fp32)
            keep_cache: If True, keep the raw downloaded files
        """
        import asyncio
        import time
        from queue import Queue, Empty
        
        # Normalize - if single string passed, convert to list
        if isinstance(quantizations, str):
            quantizations = [quantizations]
        quantizations = normalize_quantization_list(quantizations)
        display_quants = [quantization_label(q) for q in quantizations]
        
        # Queue for progress events from the download thread
        progress_queue = Queue()
        download_complete = False
        download_error = None
        download_result = None
        
        try:
            yield create_status_event("starting", {
                "model_id": model_id,
                "quantizations": display_quants,
                "keep_cache": keep_cache,
            })
            
            def progress_callback(progress):
                """Called from download thread to report progress."""
                progress_queue.put({
                    "status": progress.status,
                    "model_id": progress.model_id,
                    "current_file": progress.current_file,
                    "completed_bytes": progress.completed_bytes,
                    "total_bytes": progress.total_bytes,
                    "files_completed": progress.files_completed,
                    "files_total": progress.files_total,
                    "percent": progress.percent,
                })
            
            # Start the download in background
            async def run_download():
                nonlocal download_complete, download_error, download_result
                try:
                    download_result = await self.manager.download_model(
                        model_id=model_id,
                        quantizations=quantizations,
                        progress_callback=progress_callback,
                        keep_cache=keep_cache,
                    )
                except Exception as e:
                    download_error = e
                finally:
                    download_complete = True
            
            # Start download task
            download_task = asyncio.create_task(run_download())
            
            # Poll for progress while download runs
            last_status = ""
            last_percent = None
            last_emit_time = time.monotonic()
            last_files_completed = 0
            last_files_total = len(quantizations) if quantizations else 1
            heartbeat_interval = 10.0  # Send heartbeat every 10 seconds to keep connection alive
            
            while not download_complete:
                # Check for progress updates
                try:
                    while True:
                        progress = progress_queue.get_nowait()
                        status = progress.get("status", "")
                        percent = progress.get("percent", 0)
                        files_completed = progress.get("files_completed", last_files_completed)
                        files_total = progress.get("files_total", last_files_total)
                        
                        # Track the latest values
                        last_files_completed = files_completed
                        last_files_total = files_total
                        
                        # Only yield if status changed, percent advanced, or periodic heartbeat
                        emit_due_to_time = (time.monotonic() - last_emit_time) > 2.0
                        percent_changed = (percent is not None and percent != last_percent)
                        is_progress_status = any(k in status for k in ("quantiz", "copying", "downloading", "saving", "converting", "loading"))
                        if status != last_status or (is_progress_status and percent_changed) or emit_due_to_time:
                            last_status = status
                            last_percent = percent
                            last_emit_time = time.monotonic()
                            
                            # Map status to user-friendly messages
                            message = self._get_progress_message(status, progress)
                            
                            yield create_status_event(status, {
                                "model_id": model_id,
                                "message": message,
                                "quantizations": display_quants,
                                "files_completed": files_completed,
                                "files_total": files_total,
                                "percent": progress.get("percent", 0),
                            })
                except Empty:
                    pass
                
                # Send heartbeat if no events for a while (keeps SSE connection alive)
                if (time.monotonic() - last_emit_time) > heartbeat_interval:
                    last_emit_time = time.monotonic()
                    # Determine current phase based on last status
                    if "quantiz" in last_status or "loading" in last_status:
                        heartbeat_msg = "Model loading and quantization in progress (this can take several minutes)..."
                    elif "saving" in last_status:
                        heartbeat_msg = "Saving quantized model to disk..."
                    else:
                        heartbeat_msg = "Processing..."
                    
                    yield create_status_event("heartbeat", {
                        "model_id": model_id,
                        "message": heartbeat_msg,
                        "quantizations": display_quants,
                        "files_completed": last_files_completed,
                        "files_total": last_files_total,
                    })
                
                # Small delay to prevent busy loop
                await asyncio.sleep(0.5)
            
            # Wait for download task to complete
            await download_task
            
            if download_error:
                raise download_error
            
            # Add each quantized version to registry
            for quant in (quantizations or [None]):
                reg_key = f"{model_id}__{quant}" if quant else model_id
                await ModelRegistry.upsert(
                    name=reg_key,
                    size=0,  # Will be updated on load
                    digest=quant or "fp32",
                )
            
            yield create_done_event(
                message_id=model_id,
                total_tokens=len(download_result) if download_result else 0
            )
            
        except ModelError as e:
            import traceback
            print(f"❌ Model error: {e}")
            traceback.print_exc()
            yield create_error_event(str(e), "model_error")
        except Exception as e:
            import traceback
            print(f"❌ Download error: {e}")
            traceback.print_exc()
            yield create_error_event(str(e), "download_error")
    
    def _get_progress_message(self, status: str, progress: dict) -> str:
        """Convert status code to user-friendly message."""
        messages = {
            "downloading": "📥 Downloading model files from HuggingFace...",
            "using_cache": "📦 Using cached download, skipping download...",
            "quantizing_4bit": "🔧 Preparing 4-bit configuration...",
            "quantizing_8bit": "🔧 Preparing 8-bit configuration...",
            "quantizing_fp16": "🔧 Converting to FP16 format...",
            "quantizing_fp32": "📁 Copying full precision model...",
            "copying_4bit": "📦 Copying model files for 4-bit (linking when possible)...",
            "copying_8bit": "📦 Copying model files for 8-bit (linking when possible)...",
            "copying_fp32": "📁 Copying full precision model files...",
            "loading_tokenizer_4bit": "📦 Loading tokenizer for 4-bit...",
            "loading_tokenizer_8bit": "📦 Loading tokenizer for 8-bit...",
            "loading_4bit": "🔧 Loading model with 4-bit quantization...",
            "loading_8bit": "🔧 Loading model with 8-bit quantization...",
            "saving_4bit": "💾 Saving 4-bit quantized model...",
            "saving_8bit": "💾 Saving 8-bit quantized model...",
            "converting_fp16": "🔧 Loading FP16 model for conversion...",
            "saving_fp16": "💾 Saving FP16 model to disk...",
            "cleaning_cache": "🧹 Cleaning up cache files...",
            "complete": "✅ Model download complete!",
        }
        
        files_info = ""
        if progress.get("files_total", 0) > 0:
            files_info = f" ({progress['files_completed']}/{progress['files_total']} variants)"
        
        return messages.get(status, f"Processing: {status}") + files_info
    
    async def delete_model(
        self,
        model_id: str,
        quantization: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete a locally downloaded model."""
        try:
            normalized_quant = normalize_quantization_value(quantization)
            success = self.manager.delete_local_model(model_id, normalized_quant)
            
            if success:
                # Remove from registry
                reg_key = f"{model_id}__{normalized_quant}" if normalized_quant else model_id
                await ModelRegistry.delete(reg_key)
                return {"success": True, "message": f"Model '{model_id}' deleted"}
            else:
                return {"success": False, "error": "Model not found"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def load_model(
        self,
        model_id: str,
        quantization: Optional[str] = None
    ) -> Dict[str, Any]:
        """Load a model into GPU memory."""
        try:
            normalized_quant = normalize_quantization_value(quantization)
            print(f"🔄 Loading model {model_id} with quantization {normalized_quant}...")
            success = await self.manager.load_model(model_id, normalized_quant)
            print(f"   Load result: {success}")
            
            if success:
                # Record usage
                reg_key = f"{model_id}__{normalized_quant}" if normalized_quant else model_id
                try:
                    await ModelRegistry.record_usage(reg_key)
                except Exception as reg_err:
                    print(f"   Registry error (non-fatal): {reg_err}")
                
                print(f"✅ Model loaded successfully!")
                return {
                    "success": True,
                    "message": f"Model '{model_id}' loaded",
                    "model_id": model_id,
                    "quantization": normalized_quant,
                    "device": self.manager.device
                }
            else:
                print(f"❌ Load returned False")
                return {"success": False, "error": "Failed to load model"}
                
        except ModelNotFoundError as e:
            print(f"❌ Model not found: {e}")
            return {"success": False, "error": str(e)}
        except ModelError as e:
            print(f"❌ Model error: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    async def unload_model(self) -> Dict[str, Any]:
        """Unload the current model from memory."""
        try:
            self.manager.unload_model()
            return {"success": True, "message": "Model unloaded"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_loaded_model(self) -> Optional[Dict[str, Any]]:
        """Get info about the currently loaded model."""
        if not self.manager.is_model_loaded:
            return None
        
        return {
            "model_id": self.manager.current_model,
            "is_loaded": True,
            "device": self.manager.device,
        }
    
    async def set_favorite(self, model_id: str, is_favorite: bool) -> bool:
        """Set or unset a model as favorite."""
        return await ModelRegistry.set_favorite(model_id, is_favorite)
    
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
