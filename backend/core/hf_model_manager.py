"""
UltraChat - HuggingFace Model Manager
Native PyTorch model management with quantization support.

Downloads go to LOCAL deterministic paths, NOT the HuggingFace cache.
"""

import os
import sys
import json
import gc
import shutil
import asyncio
import threading
import logging
import traceback
from pathlib import Path
from typing import Optional, Dict, Any, List, AsyncGenerator, Callable
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Disable HuggingFace cache - we control where models go
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TextIteratorStreamer,
    GenerationConfig,
    StoppingCriteria,
    StoppingCriteriaList,
)

# ============================================
# Colored Logging Setup
# ============================================

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for different log levels."""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green  
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        # Format the message
        message = super().format(record)
        # Add color
        return f"{color}{message}{self.RESET}"

# Create logger for this module
logger = logging.getLogger("ultrachat.models")
logger.setLevel(logging.DEBUG)

# Console handler with colors
if not logger.handlers:
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(ColoredFormatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    ))
    logger.addHandler(console_handler)
from huggingface_hub import (
    HfApi,
    hf_hub_download,
    snapshot_download,
    list_models,
    model_info as get_model_info,
)

from ..config import get_settings_manager


# ============================================
# Data Classes
# ============================================

@dataclass
class ModelInfo:
    """Information about a HuggingFace model."""
    model_id: str
    name: str
    size_bytes: int = 0
    quantization: Optional[str] = None  # "4bit", "8bit", "fp16", "fp32"
    downloaded_at: Optional[str] = None
    last_used_at: Optional[str] = None
    local_path: Optional[str] = None
    is_loaded: bool = False
    parameters: Optional[str] = None
    architecture: Optional[str] = None
    license: Optional[str] = None
    
    @property
    def size_formatted(self) -> str:
        size = self.size_bytes
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"


@dataclass
class DownloadProgress:
    """Model download progress."""
    status: str
    model_id: str
    current_file: Optional[str] = None
    completed_bytes: int = 0
    total_bytes: int = 0
    files_completed: int = 0
    files_total: int = 0
    
    @property
    def percent(self) -> float:
        if self.total_bytes > 0:
            return (self.completed_bytes / self.total_bytes) * 100
        return 0.0


@dataclass
class GenerationResult:
    """Result from model generation."""
    text: str
    tokens_generated: int
    tokens_prompt: int
    time_seconds: float
    finish_reason: str = "stop"


# ============================================
# Exceptions
# ============================================

class ModelError(Exception):
    """Base exception for model errors."""
    pass


class ModelNotFoundError(ModelError):
    """Model not found on HuggingFace or locally."""
    pass


class ModelLoadError(ModelError):
    """Failed to load model."""
    pass


class QuantizationError(ModelError):
    """Failed to quantize model."""
    pass


class GPUError(ModelError):
    """GPU-related error."""
    pass


# ============================================
# Quantization Configs
# ============================================

def get_quantization_config(quant_type: str, allow_cpu_offload: bool = True) -> Optional[BitsAndBytesConfig]:
    """
    Get BitsAndBytes quantization config.
    
    Args:
        quant_type: "4bit", "8bit", "fp16", "fp32", or None
        allow_cpu_offload: If True, enables CPU offload for when GPU memory is insufficient
    """
    # Determine compute dtype (bfloat16 if supported, otherwise float16)
    compute_dtype = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float16
    
    if quant_type == "4bit":
        return BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=compute_dtype,
            bnb_4bit_quant_type="nf4",  # Normalized float 4-bit (best quality)
            bnb_4bit_use_double_quant=True,  # Double quantization for memory savings
            llm_int8_enable_fp32_cpu_offload=allow_cpu_offload,  # Allow CPU offload if needed
        )
    elif quant_type == "8bit":
        return BitsAndBytesConfig(
            load_in_8bit=True,
            llm_int8_enable_fp32_cpu_offload=allow_cpu_offload,  # Allow CPU offload if needed
        )
    elif quant_type in ("fp16", "fp32", None):
        return None
    else:
        raise QuantizationError(f"Unknown quantization type: {quant_type}")


# ============================================
# Model Manager
# ============================================

class HFModelManager:
    """
    Manages HuggingFace models with:
    - Download with quantization
    - Model loading/unloading
    - Generation with streaming
    - GPU memory management
    """
    
    _instance: Optional['HFModelManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self._models_dir: Optional[Path] = None
        self._loaded_model: Optional[Any] = None
        self._loaded_tokenizer: Optional[Any] = None
        self._loaded_model_id: Optional[str] = None
        self._loaded_quantization: Optional[str] = None
        self._hf_api = HfApi()
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._generation_lock = threading.Lock()
        self._stop_event = threading.Event()
        
        self._init_paths()
    
    def _init_paths(self):
        """Initialize model storage paths."""
        settings = get_settings_manager()
        data_dir = settings.get_db_path().parent
        self._models_dir = data_dir / "models"
        self._models_dir.mkdir(parents=True, exist_ok=True)
        # Cache directory for raw HuggingFace downloads
        self._cache_dir = self._models_dir / "_cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def models_dir(self) -> Path:
        """Get models directory."""
        return self._models_dir
    
    @property
    def cache_dir(self) -> Path:
        """Get cache directory for raw downloads."""
        return self._cache_dir
    
    @property
    def device(self) -> str:
        """Get the best available device."""
        if torch.cuda.is_available():
            return "cuda"
        return "cpu"
    
    @property
    def gpu_info(self) -> Dict[str, Any]:
        """Get GPU information."""
        if not torch.cuda.is_available():
            return {"available": False}
        
        return {
            "available": True,
            "device_name": torch.cuda.get_device_name(0),
            "device_count": torch.cuda.device_count(),
            "memory_total": torch.cuda.get_device_properties(0).total_memory,
            "memory_allocated": torch.cuda.memory_allocated(0),
            "memory_cached": torch.cuda.memory_reserved(0),
            "memory_free": torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated(0),
        }
    
    def _get_model_local_path(self, model_id: str, quantization: Optional[str] = None) -> Path:
        """Get local path for a quantized model."""
        safe_name = model_id.replace("/", "__")
        if quantization:
            safe_name = f"{safe_name}__{quantization}"
        return self._models_dir / safe_name
    
    def _get_model_cache_path(self, model_id: str) -> Path:
        """Get cache path for raw HuggingFace download."""
        safe_name = model_id.replace("/", "__")
        return self._cache_dir / safe_name
    
    def _is_valid_model_dir(self, model_dir: Path) -> bool:
        """
        Check if a directory contains valid model files.
        A valid model directory must have at least:
        - config.json OR
        - *.safetensors files OR
        - *.bin files (pytorch_model.bin)
        """
        if not model_dir.exists() or not model_dir.is_dir():
            return False
        
        # Ignore incomplete downloads
        if (model_dir / ".download_incomplete").exists():
            return False
        
        # Check for essential model files
        has_config = (model_dir / "config.json").exists()
        has_tokenizer = (model_dir / "tokenizer.json").exists() or (model_dir / "tokenizer_config.json").exists()
        has_weights = self._has_complete_weights(model_dir)
        
        # Valid if has config AND weights AND tokenizer
        return has_config and has_weights and has_tokenizer
    
    def _get_quantization_from_marker(self, model_dir: Path) -> Optional[str]:
        """Check if model dir has a quantization marker file and return the quantization type."""
        for quant in ("4bit", "8bit"):
            marker = model_dir / f".quantization_{quant}"
            if marker.exists():
                return quant
        return None
    
    def _has_complete_weights(self, model_dir: Path) -> bool:
        """Check if model directory has complete weight files (all shards if indexed)."""
        index_files = [
            "model.safetensors.index.json",
            "pytorch_model.bin.index.json",
        ]
        for index_name in index_files:
            index_path = model_dir / index_name
            if index_path.exists():
                try:
                    data = json.loads(index_path.read_text(encoding="utf-8"))
                    weight_map = data.get("weight_map", {})
                    if not weight_map:
                        return False
                    required_files = set(weight_map.values())
                    for filename in required_files:
                        if not (model_dir / filename).exists():
                            return False
                    return True
                except Exception:
                    return False
        
        # Fallback: single-file models
        has_safetensors = any(model_dir.glob("*.safetensors"))
        has_bin = any(model_dir.glob("*.bin"))
        return has_safetensors or has_bin
    
    def _collect_model_files(self, src_dir: Path) -> List[tuple[Path, Path, int]]:
        """Collect all files from a model directory with sizes."""
        files: List[tuple[Path, Path, int]] = []
        for root, _, filenames in os.walk(src_dir):
            for filename in filenames:
                src_file = Path(root) / filename
                rel_path = src_file.relative_to(src_dir)
                try:
                    size = src_file.stat().st_size
                except OSError:
                    size = 0
                files.append((src_file, rel_path, size))
        return files
    
    def _link_or_copy_model_files(
        self,
        src_dir: Path,
        dest_dir: Path,
        model_id: str,
        status: str,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
        files_completed: int = 0,
        files_total: int = 0,
    ) -> None:
        """Link (or copy) model files with progress updates."""
        files = self._collect_model_files(src_dir)
        total_bytes = sum(size for _, _, size in files)
        completed_bytes = 0
        
        for src_file, rel_path, size in files:
            dest_file = dest_dir / rel_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                if dest_file.exists():
                    dest_file.unlink()
                os.link(src_file, dest_file)
            except Exception:
                shutil.copy2(src_file, dest_file)
            
            completed_bytes += size
            if progress_callback:
                progress_callback(DownloadProgress(
                    status=status,
                    model_id=model_id,
                    current_file=str(rel_path),
                    completed_bytes=completed_bytes,
                    total_bytes=total_bytes,
                    files_completed=files_completed,
                    files_total=files_total,
                ))
    
    # ============================================
    # Model Discovery
    # ============================================
    
    async def search_models(
        self,
        query: str,
        task: str = "text-generation",
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search HuggingFace for models."""
        def _search():
            models = list_models(
                search=query,
                task=task,
                sort="downloads",
                direction=-1,
                limit=limit,
            )
            results = []
            for model in models:
                results.append({
                    "model_id": model.id,
                    "author": model.author,
                    "downloads": model.downloads,
                    "likes": model.likes,
                    "pipeline_tag": model.pipeline_tag,
                    "tags": model.tags[:10] if model.tags else [],
                    "created_at": model.created_at.isoformat() if model.created_at else None,
                })
            return results
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, _search)
    
    async def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """Get detailed info about a HuggingFace model."""
        def _get_info():
            try:
                info = get_model_info(model_id)
                return {
                    "model_id": info.id,
                    "author": info.author,
                    "sha": info.sha,
                    "pipeline_tag": info.pipeline_tag,
                    "tags": info.tags,
                    "downloads": info.downloads,
                    "likes": info.likes,
                    "library_name": info.library_name,
                    "created_at": info.created_at.isoformat() if info.created_at else None,
                    "last_modified": info.last_modified.isoformat() if info.last_modified else None,
                    "card_data": info.card_data.__dict__ if info.card_data else None,
                    "siblings": [
                        {"filename": s.rfilename, "size": s.size}
                        for s in (info.siblings or [])
                    ][:20],
                }
            except Exception as e:
                raise ModelNotFoundError(f"Model not found: {model_id}") from e
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, _get_info)
    
    async def get_popular_models(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get popular text generation models."""
        return await self.search_models("", task="text-generation", limit=limit)
    
    # ============================================
    # Model Download with Multi-Quantization Support
    # ============================================
    
    async def download_model(
        self,
        model_id: str,
        quantizations: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
        keep_cache: bool = False,
    ) -> List[Path]:
        """
        Download a model from HuggingFace with multiple quantization options.
        
        Args:
            model_id: HuggingFace model ID (e.g., "meta-llama/Llama-2-7b-chat-hf")
            quantizations: List of quantization types: ["4bit", "8bit", "fp16"]
                          If None or empty, downloads fp32 (full precision)
            progress_callback: Callback for progress updates
            keep_cache: If True, keep the raw downloaded files after quantization
        
        Returns:
            List of paths to the downloaded/quantized models
        """
        # Normalize quantizations
        if not quantizations:
            quantizations = [None]  # Full precision
        
        cache_path = self._get_model_cache_path(model_id)
        output_paths = []
        
        def _download_and_quantize():
            nonlocal output_paths
            
            # Step 1: Download raw model to cache
            if progress_callback:
                progress_callback(DownloadProgress(
                    status="downloading",
                    model_id=model_id,
                ))
            
            # Check if already in cache
            if not cache_path.exists() or not any(cache_path.iterdir()):
                # Download to cache directory
                snapshot_download(
                    repo_id=model_id,
                    local_dir=str(cache_path),
                    local_dir_use_symlinks=False,
                )
            else:
                if progress_callback:
                    progress_callback(DownloadProgress(
                        status="using_cache",
                        model_id=model_id,
                    ))
            
            # Step 2: Create each quantized version
            for idx, quant in enumerate(quantizations):
                quant_label = quant if quant else "fp32"
                
                if progress_callback:
                    progress_callback(DownloadProgress(
                        status=f"quantizing_{quant_label}",
                        model_id=model_id,
                        files_completed=idx,
                        files_total=len(quantizations),
                    ))
                
                output_path = self._get_model_local_path(model_id, quant)
                
                # Skip if already exists and is valid
                if output_path.exists() and self._is_valid_model_dir(output_path):
                    logger.info(f"✅ {quant_label} version already exists, skipping...")
                    output_paths.append(output_path)
                    continue
                
                # Clean up any incomplete previous attempts
                if output_path.exists():
                    shutil.rmtree(output_path)
                
                output_path.mkdir(parents=True, exist_ok=True)
                incomplete_marker = output_path / ".download_incomplete"
                incomplete_marker.write_text(
                    f"Incomplete download for {model_id} ({quant_label})\n"
                    f"Started: {datetime.now().isoformat()}"
                )
                
                # For 4bit/8bit: Load with quantization and save as a separate model
                if quant in ("4bit", "8bit"):
                    model = None  # Track for cleanup
                    tokenizer = None
                    try:
                        logger.info(f"📦 Loading tokenizer from cache for {quant_label}...")
                        if progress_callback:
                            progress_callback(DownloadProgress(
                                status=f"loading_tokenizer_{quant_label}",
                                model_id=model_id,
                                files_completed=idx,
                                files_total=len(quantizations),
                            ))
                        tokenizer = AutoTokenizer.from_pretrained(
                            str(cache_path),
                            trust_remote_code=True,
                        )
                        # Set pad token if not set
                        if tokenizer.pad_token_id is None:
                            tokenizer.pad_token = tokenizer.eos_token
                        
                        logger.info(f"🔧 Loading model with {quant_label} quantization (this may take several minutes)...")
                        logger.info(f"   Using NF4 quantization with double quant and CPU offload enabled...")
                        if progress_callback:
                            progress_callback(DownloadProgress(
                                status=f"quantizing_{quant_label}",
                                model_id=model_id,
                                files_completed=idx,
                                files_total=len(quantizations),
                            ))
                        
                        logger.debug(f"   📥 Loading checkpoint shards...")
                        
                        # Calculate max memory to use - leave 1GB buffer on GPU
                        max_memory = None
                        if torch.cuda.is_available():
                            gpu_mem = torch.cuda.get_device_properties(0).total_memory
                            gpu_available = gpu_mem - torch.cuda.memory_allocated(0)
                            # Use 90% of available GPU memory, rest on CPU
                            gpu_use = int(gpu_available * 0.9)
                            max_memory = {0: gpu_use, "cpu": "32GB"}
                            logger.info(f"   📊 GPU memory limit: {gpu_use / 1024**3:.1f}GB")
                        
                        def is_oom_error(error: Exception) -> bool:
                            """Check if error is out of memory."""
                            msg = str(error).lower()
                            return "out of memory" in msg or ("cuda" in msg and "memory" in msg)
                        
                        # Try GPU-only first (like Qwen LoRa pattern), fallback to auto if OOM
                        try:
                            logger.info(f"   🎯 Attempting GPU-only load for quantization...")
                            quant_config = get_quantization_config(quant, allow_cpu_offload=False)
                            model = AutoModelForCausalLM.from_pretrained(
                                str(cache_path),
                                quantization_config=quant_config,
                                torch_dtype="auto",
                                device_map={"": 0},  # GPU-only, no meta tensors
                                trust_remote_code=True,
                                low_cpu_mem_usage=True,
                            )
                        except (RuntimeError, ValueError) as e:
                            if is_oom_error(e):
                                logger.warning(f"   ⚠️ GPU-only load failed (OOM). Falling back to CPU offload...")
                                gc.collect()
                                if torch.cuda.is_available():
                                    torch.cuda.empty_cache()
                                
                                quant_config = get_quantization_config(quant, allow_cpu_offload=True)
                                model = AutoModelForCausalLM.from_pretrained(
                                    str(cache_path),
                                    quantization_config=quant_config,
                                    torch_dtype="auto",
                                    device_map="auto",
                                    max_memory=max_memory,
                                    trust_remote_code=True,
                                    low_cpu_mem_usage=True,
                                )
                            else:
                                raise
                        
                        logger.debug(f"   ✅ Checkpoint shards loaded, model object created!")
                        
                        logger.info(f"✅ Model loaded and quantized!")
                        # Display memory usage
                        if torch.cuda.is_available():
                            allocated = torch.cuda.memory_allocated() / 1024**3
                            logger.info(f"   💾 GPU memory used: {allocated:.2f} GB")
                        
                        logger.info(f"💾 Saving {quant_label} model to disk (this may take a while for large models)...")
                        if progress_callback:
                            progress_callback(DownloadProgress(
                                status=f"saving_{quant_label}",
                                model_id=model_id,
                                files_completed=idx,
                                files_total=len(quantizations),
                            ))
                        
                        try:
                            model.save_pretrained(str(output_path), safe_serialization=True)
                            tokenizer.save_pretrained(str(output_path))
                            logger.info(f"✅ {quant_label} model saved successfully!")
                        except Exception as save_error:
                            error_str = str(save_error).lower()
                            if "meta" in error_str or "item" in error_str:
                                logger.warning(f"   ⚠️ Safe serialization failed (meta tensors), trying without safe_serialization...")
                                # Try without safe serialization (uses pickle instead of safetensors)
                                model.save_pretrained(str(output_path), safe_serialization=False)
                                tokenizer.save_pretrained(str(output_path))
                                logger.info(f"✅ {quant_label} model saved (pickle format)!")
                            else:
                                raise save_error
                        
                        # Create a marker file that tells the loader the quantization level
                        marker_file = output_path / f".quantization_{quant}"
                        marker_file.write_text(f"Quantized: {quant}\nCreated: {datetime.now().isoformat()}")
                        
                        # Mark download as complete
                        (output_path / ".download_complete").write_text(
                            f"Completed: {datetime.now().isoformat()}"
                        )
                        incomplete_marker.unlink(missing_ok=True)
                        
                        logger.info(f"✅ {quant_label} model saved to {output_path}")
                        output_paths.append(output_path)
                        
                    except Exception as quant_error:
                        logger.error(f"❌ Failed to quantize model: {quant_error}")
                        logger.error(traceback.format_exc())
                        raise QuantizationError(f"Failed to create {quant_label} version: {quant_error}")
                    finally:
                        # ALWAYS cleanup model from GPU on error or success
                        if model is not None:
                            del model
                        if tokenizer is not None:
                            del tokenizer
                        gc.collect()
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                            allocated = torch.cuda.memory_allocated() / 1024**3
                            logger.debug(f"   🧹 GPU memory after cleanup: {allocated:.2f} GB")
                    
                elif quant == "fp16":
                    logger.info(f"📦 Converting to FP16 (half precision)...")
                    if progress_callback:
                        progress_callback(DownloadProgress(
                            status="converting_fp16",
                            model_id=model_id,
                            files_completed=idx,
                            files_total=len(quantizations),
                        ))
                    
                    # Load tokenizer
                    tokenizer = AutoTokenizer.from_pretrained(
                        str(cache_path),
                        trust_remote_code=True,
                    )
                    
                    # Load model in fp16
                    model = AutoModelForCausalLM.from_pretrained(
                        str(cache_path),
                        torch_dtype=torch.float16,
                        device_map="cpu",  # Load to CPU for saving
                        trust_remote_code=True,
                        low_cpu_mem_usage=True,
                    )
                    
                    logger.info(f"💾 Saving FP16 version...")
                    if progress_callback:
                        progress_callback(DownloadProgress(
                            status="saving_fp16",
                            model_id=model_id,
                            files_completed=idx,
                            files_total=len(quantizations),
                        ))
                    model.save_pretrained(str(output_path))
                    tokenizer.save_pretrained(str(output_path))
                    
                    # Mark download as complete
                    (output_path / ".download_complete").write_text(
                        f"Completed: {datetime.now().isoformat()}"
                    )
                    incomplete_marker.unlink(missing_ok=True)
                    
                    logger.info(f"✅ FP16 version saved to {output_path}")
                    
                    # Free memory
                    del model
                    del tokenizer
                    gc.collect()
                    
                    output_paths.append(output_path)
                    
                else:
                    # Full precision (fp32) - just copy files
                    logger.info(f"📁 Copying FP32 model files...")
                    self._link_or_copy_model_files(
                        src_dir=cache_path,
                        dest_dir=output_path,
                        model_id=model_id,
                        status="copying_fp32",
                        progress_callback=progress_callback,
                        files_completed=idx,
                        files_total=len(quantizations),
                    )
                    
                    # Mark download as complete
                    (output_path / ".download_complete").write_text(
                        f"Completed: {datetime.now().isoformat()}"
                    )
                    incomplete_marker.unlink(missing_ok=True)
                    
                    logger.info(f"✅ FP32 version ready")
                    output_paths.append(output_path)
            
            # Step 3: Clean up cache if not keeping
            if not keep_cache and cache_path.exists():
                if progress_callback:
                    progress_callback(DownloadProgress(
                        status="cleaning_cache",
                        model_id=model_id,
                    ))
                shutil.rmtree(cache_path)
            
            # Report completion
            if progress_callback:
                progress_callback(DownloadProgress(
                    status="complete",
                    model_id=model_id,
                    files_completed=len(quantizations),
                    files_total=len(quantizations),
                ))
            
            return output_paths
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, _download_and_quantize)
    
    # Legacy single-quantization method for backwards compatibility
    async def download_model_single(
        self,
        model_id: str,
        quantization: Optional[str] = None,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None
    ) -> Path:
        """
        Download a model with a single quantization option.
        Backwards compatible wrapper around download_model.
        """
        quants = [quantization] if quantization else [None]
        paths = await self.download_model(model_id, quants, progress_callback, keep_cache=False)
        return paths[0] if paths else None
    
    # ============================================
    # Local Model Management
    # ============================================
    
    def list_local_models(self) -> List[ModelInfo]:
        """List all locally downloaded models."""
        models = []
        
        if not self._models_dir.exists():
            return models
        
        for model_dir in self._models_dir.iterdir():
            if model_dir.is_dir():
                # Skip the cache directory
                if model_dir.name == "_cache":
                    continue
                
                # Validate this is actually a model folder (has config.json or model files)
                if not self._is_valid_model_dir(model_dir):
                    continue
                    
                # Parse model name and quantization
                name = model_dir.name
                quantization = None
                
                if "__4bit" in name:
                    quantization = "4bit"
                    name = name.replace("__4bit", "")
                elif "__8bit" in name:
                    quantization = "8bit"
                    name = name.replace("__8bit", "")
                elif "__fp16" in name:
                    quantization = "fp16"
                    name = name.replace("__fp16", "")
                
                model_id = name.replace("__", "/")
                
                # Calculate size
                total_size = sum(
                    f.stat().st_size for f in model_dir.rglob("*") if f.is_file()
                )
                
                # Get modification time
                stat = model_dir.stat()
                downloaded_at = datetime.fromtimestamp(stat.st_ctime).isoformat()
                
                models.append(ModelInfo(
                    model_id=model_id,
                    name=model_id.split("/")[-1] if "/" in model_id else model_id,
                    size_bytes=total_size,
                    quantization=quantization,
                    downloaded_at=downloaded_at,
                    local_path=str(model_dir),
                    is_loaded=(self._loaded_model_id == model_id and 
                              self._loaded_quantization == quantization),
                ))
        
        return models
    
    def delete_local_model(self, model_id: str, quantization: Optional[str] = None) -> bool:
        """Delete a locally downloaded model."""
        local_path = self._get_model_local_path(model_id, quantization)
        
        if local_path.exists():
            # Unload if currently loaded
            if (self._loaded_model_id == model_id and 
                self._loaded_quantization == quantization):
                self.unload_model()
            
            shutil.rmtree(local_path)
            return True
        return False
    
    # ============================================
    # Model Loading
    # ============================================
    
    async def load_model(
        self,
        model_id: str,
        quantization: Optional[str] = None,
    ) -> bool:
        """Load a model into GPU memory."""
        # Check if already loaded
        if (self._loaded_model_id == model_id and 
            self._loaded_quantization == quantization and
            self._loaded_model is not None):
            return True
        
        def _load():
            # Unload current model first
            self.unload_model()
            
            # Get local path
            local_path = self._get_model_local_path(model_id, quantization)
            
            # Check if downloaded
            if not local_path.exists():
                raise ModelNotFoundError(
                    f"Model not found locally: {model_id}. Download it first."
                )
            
            # Check for quantization marker (for 4bit/8bit)
            marker_quant = self._get_quantization_from_marker(local_path)
            effective_quant = marker_quant or quantization
            
            logger.info(f"📦 Loading tokenizer for {model_id}...")
            
            # Load tokenizer
            self._loaded_tokenizer = AutoTokenizer.from_pretrained(
                str(local_path),
                trust_remote_code=True,
            )
            
            # Set pad token if not set
            if self._loaded_tokenizer.pad_token is None:
                self._loaded_tokenizer.pad_token = self._loaded_tokenizer.eos_token
            
            # Use effective quantization (from marker or parameter)
            logger.info(f"🔧 Loading model with {effective_quant or 'fp32'} precision...")
            
            # Determine compute dtype (bfloat16 if supported, otherwise float16)
            compute_dtype = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float16
            
            def build_load_kwargs(allow_offload: bool = False):
                """Build kwargs for model loading."""
                kwargs = {
                    "trust_remote_code": True,
                    "torch_dtype": "auto",
                    "low_cpu_mem_usage": True,
                }
                
                # Use GPU-only device map first, like the working Qwen LoRa code
                if allow_offload:
                    # Use auto device map with offloading
                    kwargs["device_map"] = "auto"
                else:
                    # Load everything to GPU 0 (no meta tensors)
                    kwargs["device_map"] = {"": 0}
                
                # For 4bit/8bit, ALWAYS pass quantization_config
                if effective_quant in ("4bit", "8bit"):
                    quant_config = get_quantization_config(effective_quant, allow_cpu_offload=allow_offload)
                    kwargs["quantization_config"] = quant_config
                elif effective_quant == "fp16":
                    kwargs["torch_dtype"] = torch.float16
                elif effective_quant == "fp32" or effective_quant is None:
                    kwargs["torch_dtype"] = torch.float32
                
                return kwargs
            
            def is_oom_error(error: Exception) -> bool:
                """Check if error is out of memory."""
                msg = str(error).lower()
                return "out of memory" in msg or "cuda" in msg and "memory" in msg
            
            # Try GPU-only first (no meta tensors), fallback to offload if OOM
            try:
                logger.info(f"   🎯 Attempting GPU-only load...")
                load_kwargs = build_load_kwargs(allow_offload=False)
                self._loaded_model = AutoModelForCausalLM.from_pretrained(
                    str(local_path),
                    **load_kwargs
                )
            except (RuntimeError, ValueError) as e:
                if is_oom_error(e):
                    logger.warning(f"   ⚠️ GPU-only load failed (OOM). Falling back to CPU offload...")
                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    
                    load_kwargs = build_load_kwargs(allow_offload=True)
                    self._loaded_model = AutoModelForCausalLM.from_pretrained(
                        str(local_path),
                        **load_kwargs
                    )
                else:
                    raise
            
            logger.info(f"✅ Model loaded successfully!")
            
            # Set to eval mode for inference
            self._loaded_model.eval()
            
            self._loaded_model_id = model_id
            self._loaded_quantization = effective_quant  # Use effective quantization
            
            return True
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, _load)
    
    def unload_model(self):
        """Unload the currently loaded model from memory."""
        if self._loaded_model is not None:
            del self._loaded_model
            self._loaded_model = None
        
        if self._loaded_tokenizer is not None:
            del self._loaded_tokenizer
            self._loaded_tokenizer = None
        
        self._loaded_model_id = None
        self._loaded_quantization = None
        
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def request_stop(self):
        """Request generation stop for the current model."""
        self._stop_event.set()
    
    @property
    def current_model(self) -> Optional[str]:
        """Get currently loaded model ID with quantization suffix."""
        if self._loaded_model_id is None:
            return None
        # Return model_id__quantization format for frontend compatibility
        if self._loaded_quantization:
            return f"{self._loaded_model_id}__{self._loaded_quantization}"
        return self._loaded_model_id
    
    @property
    def is_model_loaded(self) -> bool:
        """Check if a model is currently loaded."""
        return self._loaded_model is not None
    
    # ============================================
    # Generation
    # ============================================
    
    async def generate(
        self,
        prompt: str,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 50,
        repetition_penalty: float = 1.1,
        do_sample: bool = True,
        stream: bool = True,
    ) -> AsyncGenerator[str, None]:
        """
        Generate text with streaming.
        
        Yields tokens as they're generated.
        """
        if not self.is_model_loaded:
            raise ModelError("No model loaded. Load a model first.")

        self._stop_event.clear()

        class _StopOnEvent(StoppingCriteria):
            def __init__(self, stop_event: threading.Event):
                self.stop_event = stop_event

            def __call__(self, input_ids, scores, **kwargs):
                return self.stop_event.is_set()

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[Optional[str]] = asyncio.Queue()

        def _worker():
            try:
                with self._generation_lock, torch.inference_mode():
                    # Tokenize
                    inputs = self._loaded_tokenizer(
                        prompt,
                        return_tensors="pt",
                        padding=True,
                        truncation=True,
                        max_length=4096,
                    ).to(self.device)

                    # Create streamer
                    streamer = TextIteratorStreamer(
                        self._loaded_tokenizer,
                        skip_prompt=True,
                        skip_special_tokens=True,
                    )

                    # Generation config
                    gen_kwargs = {
                        "input_ids": inputs.input_ids,
                        "attention_mask": inputs.attention_mask,
                        "max_new_tokens": max_new_tokens,
                        "temperature": temperature if do_sample else 1.0,
                        "top_p": top_p if do_sample else 1.0,
                        "top_k": top_k if do_sample else 0,
                        "repetition_penalty": repetition_penalty,
                        "do_sample": do_sample,
                        "streamer": streamer,
                        "pad_token_id": self._loaded_tokenizer.pad_token_id,
                        "eos_token_id": self._loaded_tokenizer.eos_token_id,
                        "stopping_criteria": StoppingCriteriaList([_StopOnEvent(self._stop_event)]),
                    }

                    # Start generation in background thread
                    thread = threading.Thread(
                        target=self._loaded_model.generate,
                        kwargs=gen_kwargs,
                        daemon=True
                    )
                    thread.start()

                    # Stream tokens into async queue
                    for token in streamer:
                        loop.call_soon_threadsafe(queue.put_nowait, token)

                    thread.join()
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        threading.Thread(target=_worker, daemon=True).start()

        while True:
            token = await queue.get()
            if token is None:
                break
            yield token
    
    async def generate_complete(
        self,
        prompt: str,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 50,
        repetition_penalty: float = 1.1,
        do_sample: bool = True,
    ) -> GenerationResult:
        """Generate text without streaming (returns complete response)."""
        import time
        
        if not self.is_model_loaded:
            raise ModelError("No model loaded. Load a model first.")
        
        def _generate():
            start_time = time.time()
            
            with self._generation_lock, torch.inference_mode():
                # Tokenize
                inputs = self._loaded_tokenizer(
                    prompt,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=4096,
                ).to(self.device)
                
                prompt_tokens = inputs.input_ids.shape[1]
                
                # Generate
                outputs = self._loaded_model.generate(
                    input_ids=inputs.input_ids,
                    attention_mask=inputs.attention_mask,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature if do_sample else 1.0,
                    top_p=top_p if do_sample else 1.0,
                    top_k=top_k if do_sample else 0,
                    repetition_penalty=repetition_penalty,
                    do_sample=do_sample,
                    pad_token_id=self._loaded_tokenizer.pad_token_id,
                    eos_token_id=self._loaded_tokenizer.eos_token_id,
                )
                
                # Decode only new tokens
                generated_ids = outputs[0][inputs.input_ids.shape[1]:]
                text = self._loaded_tokenizer.decode(
                    generated_ids,
                    skip_special_tokens=True,
                )
                
                end_time = time.time()
                
                return GenerationResult(
                    text=text,
                    tokens_generated=len(generated_ids),
                    tokens_prompt=prompt_tokens,
                    time_seconds=end_time - start_time,
                )
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, _generate)
    
    # ============================================
    # Chat Format
    # ============================================
    
    def format_chat_prompt(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        enable_thinking: Optional[bool] = None,
        tools: Optional[list] = None
    ) -> str:
        """
        Format messages for chat.
        Uses the tokenizer's chat template if available.
        """
        if not self.is_model_loaded:
            raise ModelError("No model loaded.")
        
        # Try to use tokenizer's chat template
        if hasattr(self._loaded_tokenizer, 'apply_chat_template'):
            try:
                kwargs = {
                    "tokenize": False,
                    "add_generation_prompt": True,
                }

                if enable_thinking is not None:
                    kwargs["enable_thinking"] = enable_thinking

                if tools is not None:
                    kwargs["tools"] = tools

                formatted = self._loaded_tokenizer.apply_chat_template(
                    messages,
                    **kwargs,
                )
                return formatted
            except TypeError:
                # Tokenizer doesn't support enable_thinking/tools
                kwargs.pop("enable_thinking", None)
                kwargs.pop("tools", None)
                return self._loaded_tokenizer.apply_chat_template(
                    messages,
                    **kwargs,
                )
            except Exception:
                pass
        
        # Fallback: Simple format
        prompt_parts = []
        
        if system_prompt:
            prompt_parts.append(f"System: {system_prompt}\n\n")
        
        for msg in messages:
            role = msg.get("role", "user").capitalize()
            content = msg.get("content", "")
            prompt_parts.append(f"{role}: {content}\n")
        
        prompt_parts.append("Assistant: ")
        
        return "".join(prompt_parts)


# ============================================
# Global Instance
# ============================================

_manager: Optional[HFModelManager] = None


def get_model_manager() -> HFModelManager:
    """Get the global model manager instance."""
    global _manager
    if _manager is None:
        _manager = HFModelManager()
    return _manager


async def close_model_manager():
    """Clean up model manager resources."""
    global _manager
    if _manager:
        _manager.unload_model()
        _manager = None

