"""
UltraChat - Core Package
"""

from .streaming import (
    StreamEventType,
    StreamEvent,
    create_token_event,
    create_done_event,
    create_error_event,
    create_status_event,
    create_progress_event,
    create_metadata_event,
    StreamBuffer,
)

from .voice_manager import (
    VoiceManager,
    VoiceSettings,
    TokenChunker,
    get_voice_manager,
    close_voice_manager,
)

# Hugging Face/PyTorch is deliberately lazy. The remote provider stress lab can
# therefore run on a machine without a local inference runtime.
_HF_EXPORTS = {
    "HFModelManager", "ModelInfo", "DownloadProgress", "GenerationResult",
    "ModelError", "ModelNotFoundError", "ModelLoadError", "QuantizationError",
    "GPUError", "get_quantization_config", "FLASH_ATTN_AVAILABLE",
}


def _hf_module():
    try:
        from . import hf_model_manager
    except ImportError as exc:
        raise RuntimeError(
            "Local Hugging Face mode requires PyTorch and its model dependencies. "
            "Remote provider modes work without them."
        ) from exc
    return hf_model_manager


def get_model_manager():
    return _hf_module().get_model_manager()


async def close_model_manager():
    return await _hf_module().close_model_manager()


def __getattr__(name):
    if name in _HF_EXPORTS:
        return getattr(_hf_module(), name)
    raise AttributeError(name)

__all__ = [
    "HFModelManager",
    "ModelInfo",
    "DownloadProgress",
    "GenerationResult",
    "ModelError",
    "ModelNotFoundError",
    "ModelLoadError",
    "QuantizationError",
    "GPUError",
    "get_model_manager",
    "close_model_manager",
    "get_quantization_config",
    "FLASH_ATTN_AVAILABLE",
    "StreamEventType",
    "StreamEvent",
    "create_token_event",
    "create_done_event",
    "create_error_event",
    "create_status_event",
    "create_progress_event",
    "create_metadata_event",
    "StreamBuffer",
    "VoiceManager",
    "VoiceSettings",
    "TokenChunker",
    "get_voice_manager",
    "close_voice_manager",
]
