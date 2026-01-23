import hashlib
import logging
import time
from pathlib import Path
from typing import Optional

import requests
import safetensors.torch
import torch
from huggingface_hub import hf_hub_download
from torch import nn

PROJECT_ROOT = Path(__file__).parent.parent.parent

# Global cache directory - can be set by user
_CACHE_DIR: Optional[Path] = None

# Preset voice embeddings (available in both repos)
_voices_names = ["alba", "marius", "javert", "jean", "fantine", "cosette", "eponine", "azelma"]
PREDEFINED_VOICES = {
    # These preset voices work with the non-voice-cloning model
    # For voice cloning from user files, use the full model: kyutai/pocket-tts
    x: f"hf://kyutai/pocket-tts-without-voice-cloning/embeddings/{x}.safetensors@d4fdd22ae8c8e1cb3634e150ebeff1dab2d16df3"
    for x in _voices_names
}


def set_cache_directory(cache_dir: str | Path) -> Path:
    """Set custom cache directory for model downloads.
    
    Args:
        cache_dir: Path to cache directory. Will be created if it doesn't exist.
        
    Returns:
        The Path object for the cache directory.
    """
    global _CACHE_DIR
    _CACHE_DIR = Path(cache_dir)
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR


def get_cache_directory() -> Path:
    """Get the current cache directory.
    
    Returns:
        Path to the cache directory (custom or default ~/.cache/pocket_tts)
    """
    global _CACHE_DIR
    if _CACHE_DIR is not None:
        return _CACHE_DIR
    return make_cache_directory()


def make_cache_directory() -> Path:
    cache_dir = Path.home() / ".cache" / "pocket_tts"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def print_nb_parameters(model: nn.Module, model_name: str):
    logger = logging.getLogger(__name__)
    state_dict = model.state_dict()
    total = 0
    for key, value in state_dict.items():
        logger.info("%s: %,d", key, value.numel())
        total += value.numel()
    logger.info("Total number of parameters in %s: %,d", model_name, total)


def size_of_dict(state_dict: dict) -> int:
    total_size = 0
    for value in state_dict.values():
        if isinstance(value, torch.Tensor):
            total_size += value.numel() * value.element_size()
        elif isinstance(value, dict):
            total_size += size_of_dict(value)
    return total_size


class display_execution_time:
    def __init__(self, task_name: str, print_output: bool = True):
        self.task_name = task_name
        self.print_output = print_output
        self.start_time = None
        self.elapsed_time_ms = None
        self.logger = logging.getLogger(__name__)

    def __enter__(self):
        self.start_time = time.monotonic()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = time.monotonic()
        self.elapsed_time_ms = int((end_time - self.start_time) * 1000)
        if self.print_output:
            self.logger.info("%s took %d ms", self.task_name, self.elapsed_time_ms)
        return False  # Don't suppress exceptions


def download_if_necessary(file_path: str, cache_dir: Optional[Path] = None) -> Path:
    """Download a file if not already cached.
    
    Args:
        file_path: URL (http/https), HuggingFace path (hf://), or local path
        cache_dir: Optional custom cache directory. If None, uses global cache.
        
    Returns:
        Path to the cached/downloaded file.
    """
    if cache_dir is None:
        cache_dir = get_cache_directory()
    
    if file_path.startswith("http://") or file_path.startswith("https://"):
        cached_file = cache_dir / (
            hashlib.sha256(file_path.encode()).hexdigest() + "." + file_path.split(".")[-1]
        )
        if not cached_file.exists():
            logger = logging.getLogger(__name__)
            logger.info(f"Downloading {file_path} to {cached_file}")
            response = requests.get(file_path)
            response.raise_for_status()
            with open(cached_file, "wb") as f:
                f.write(response.content)
        return cached_file
    elif file_path.startswith("hf://"):
        file_path = file_path.removeprefix("hf://")
        splitted = file_path.split("/")
        repo_id = "/".join(splitted[:2])
        filename = "/".join(splitted[2:])
        if "@" in filename:
            filename, revision = filename.split("@")
        else:
            revision = None
        # Use custom cache directory for HuggingFace downloads
        cached_file = hf_hub_download(
            repo_id=repo_id, 
            filename=filename, 
            revision=revision,
            cache_dir=str(cache_dir)
        )
        return Path(cached_file)
    else:
        return Path(file_path)


def load_predefined_voice(voice_name: str) -> torch.Tensor:
    if voice_name not in PREDEFINED_VOICES:
        raise ValueError(
            f"Predefined voice '{voice_name}' not found"
            f", available voices are {list(PREDEFINED_VOICES)}."
        )
    voice_file = download_if_necessary(PREDEFINED_VOICES[voice_name])
    # There is only one tensor in the file.
    return safetensors.torch.load_file(voice_file)["audio_prompt"]
