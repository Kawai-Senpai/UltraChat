"""
UltraChat - Voice Manager
Handles TTS (Pocket TTS) and STT (Vosk) with streaming support.
"""

import os
import re
import gc
import time
import asyncio
import logging
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List, AsyncGenerator, Callable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

import numpy as np

logger = logging.getLogger("ultrachat.voice")

# Optional imports - gracefully handle missing packages
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available for voice features")

# Import Pocket TTS (installed as editable package)
try:
    from pocket_tts import TTSModel as PocketTTSModel
    POCKET_TTS_AVAILABLE = True
except ImportError as e:
    POCKET_TTS_AVAILABLE = False
    logger.warning(f"Pocket TTS not available: {e}")

try:
    from vosk import Model as VoskModel, KaldiRecognizer
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False
    logger.warning("Vosk STT not available")

# VAD is now handled in the frontend with @ricky0123/vad-react
VAD_AVAILABLE = False


# ============================================
# Data Classes
# ============================================

@dataclass
class VoiceSettings:
    """Voice configuration."""
    tts_enabled: bool = True
    stt_enabled: bool = True
    tts_device: str = "cpu"  # Pocket TTS runs best on CPU
    stt_device: str = "cpu"  # STT typically runs on CPU
    voice_prompt_path: Optional[str] = None  # Path to reference audio for cloning
    sample_rate: int = 24000
    vad_aggressiveness: int = 2  # 0-3, higher = more aggressive
    chunk_max_words: int = 16
    chunk_max_wait_s: float = 0.7


@dataclass
class TokenChunk:
    """A committed text chunk ready for TTS."""
    text: str
    is_final: bool = False


# ============================================
# Token Chunker
# ============================================

class TokenChunker:
    """
    Buffers LLM tokens and commits chunks to TTS when boundaries are hit.
    """
    _END_RE = re.compile(r"[.!?]\s*$")
    
    def __init__(
        self,
        max_words: int = 16,
        max_chars: int = 220,
        max_wait_s: float = 0.7
    ):
        self.buf = ""
        self.last_commit_t = time.time()
        self.max_words = max_words
        self.max_chars = max_chars
        self.max_wait_s = max_wait_s
    
    def feed(self, token_text: str) -> Optional[str]:
        """Feed a token. Returns committed chunk if ready, else None."""
        self.buf += token_text
        now = time.time()
        
        words = self.buf.strip().split()
        if (
            self._END_RE.search(self.buf) or
            "\n" in self.buf or
            len(words) >= self.max_words or
            len(self.buf) >= self.max_chars or
            (now - self.last_commit_t) >= self.max_wait_s
        ):
            chunk = self.buf.strip()
            self.buf = ""
            self.last_commit_t = now
            return chunk if chunk else None
        
        return None
    
    def flush(self) -> Optional[str]:
        """Flush remaining buffer."""
        chunk = self.buf.strip()
        self.buf = ""
        return chunk if chunk else None
    
    def reset(self):
        """Clear the buffer."""
        self.buf = ""
        self.last_commit_t = time.time()


# ============================================
# Audio Utilities
# ============================================

def wav_to_pcm16_bytes(wav_tensor) -> bytes:
    """Convert a torch tensor to PCM16 bytes."""
    if not TORCH_AVAILABLE:
        return b""
    
    x = wav_tensor.squeeze(0).detach()
    x = torch.clamp(x, -1.0, 1.0)
    pcm16 = (x * 32767.0).to(torch.int16).cpu().numpy()
    return pcm16.tobytes()


def pcm16_to_float32(pcm16_bytes: bytes) -> np.ndarray:
    """Convert PCM16 bytes to float32 numpy array."""
    pcm16 = np.frombuffer(pcm16_bytes, dtype=np.int16)
    return pcm16.astype(np.float32) / 32768.0


# ============================================
# Voice Manager
# ============================================

class VoiceManager:
    """
    Manages TTS and STT with:
    - Pocket TTS for TTS (streaming output, CPU-only, 100M params)
    - Vosk for STT (streaming input)
    - Frontend VAD with @ricky0123/vad-react
    """
    
    _instance: Optional['VoiceManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._settings = VoiceSettings()
        self._tts_model = None
        self._tts_voice_state = None  # Pocket TTS voice state
        self._stt_model = None
        self._stt_recognizer = None
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._stop_event = threading.Event()
        self._tts_lock = threading.Lock()
        self._voices_dir: Optional[Path] = None
        
        self._init_paths()
    
    def _init_paths(self):
        """Initialize voice storage paths."""
        from ..config import get_settings_manager
        settings = get_settings_manager()
        data_dir = settings.get_db_path().parent
        self._voices_dir = data_dir / "voices"
        self._voices_dir.mkdir(parents=True, exist_ok=True)
        self._stt_models_dir = data_dir / "stt_models"
        self._stt_models_dir.mkdir(parents=True, exist_ok=True)
        self._tts_cache_dir = data_dir / "tts_cache"
        self._tts_cache_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def voices_dir(self) -> Path:
        """Get voices directory."""
        return self._voices_dir
    
    @property
    def stt_models_dir(self) -> Path:
        """Get STT models directory."""
        return self._stt_models_dir
    
    @property
    def tts_cache_dir(self) -> Path:
        """Get TTS cache directory (for Pocket TTS models)."""
        return self._tts_cache_dir
    
    @property
    def is_tts_available(self) -> bool:
        """Check if TTS is available."""
        return POCKET_TTS_AVAILABLE
    
    @property
    def is_stt_available(self) -> bool:
        """Check if STT is available."""
        return VOSK_AVAILABLE
    
    @property
    def is_vad_available(self) -> bool:
        """Check if VAD is available."""
        return VAD_AVAILABLE
    
    @property
    def is_tts_loaded(self) -> bool:
        """Check if TTS model is loaded."""
        return self._tts_model is not None
    
    @property
    def is_stt_loaded(self) -> bool:
        """Check if STT model is loaded."""
        return self._stt_model is not None
    
    @property
    def tts_sample_rate(self) -> int:
        """Get TTS sample rate."""
        if self._tts_model and hasattr(self._tts_model, 'sample_rate'):
            return self._tts_model.sample_rate
        return self._settings.sample_rate
    
    def get_status(self) -> Dict[str, Any]:
        """Get voice system status."""
        stt_models = self.list_stt_models()
        return {
            "tts_available": self.is_tts_available,
            "stt_available": self.is_stt_available,
            "vad_available": self.is_vad_available,
            "tts_loaded": self.is_tts_loaded,
            "stt_loaded": self.is_stt_loaded,
            "sample_rate": self.tts_sample_rate,
            "stt_models": stt_models,
            "stt_models_dir": str(self._stt_models_dir) if self._stt_models_dir else None,
            "tts_cache_dir": str(self._tts_cache_dir) if self._tts_cache_dir else None,
        }
    
    def update_settings(self, **kwargs):
        """Update voice settings."""
        for key, value in kwargs.items():
            if hasattr(self._settings, key):
                setattr(self._settings, key, value)
    
    # ============================================
    # STT Model Management
    # ============================================
    
    def list_stt_models(self) -> List[Dict[str, Any]]:
        """List available STT models."""
        models = []
        if self._stt_models_dir and self._stt_models_dir.exists():
            for d in self._stt_models_dir.iterdir():
                if d.is_dir():
                    # Check for vosk model markers
                    is_vosk = (d / "am" / "final.mdl").exists() or (d / "model" / "am" / "final.mdl").exists()
                    size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
                    models.append({
                        "name": d.name,
                        "path": str(d),
                        "type": "vosk" if is_vosk else "unknown",
                        "size": size,
                    })
        return models
    
    async def download_stt_model(
        self,
        model_name: str = "vosk-model-small-en-us-0.15",
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Download a Vosk STT model from the official alphacep server.
        Yields progress events.
        """
        import zipfile
        import shutil
        import httpx
        
        # Official alphacep model URLs
        VOSK_MODELS = {
            "vosk-model-small-en-us-0.15": "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
            "vosk-model-en-us-0.22": "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip",
            "vosk-model-small-cn-0.22": "https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip",
            "vosk-model-small-de-0.15": "https://alphacephei.com/vosk/models/vosk-model-small-de-0.15.zip",
            "vosk-model-small-fr-0.22": "https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip",
            "vosk-model-small-es-0.42": "https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip",
            "vosk-model-small-ru-0.22": "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip",
            "vosk-model-small-ja-0.22": "https://alphacephei.com/vosk/models/vosk-model-small-ja-0.22.zip",
            "vosk-model-small-it-0.22": "https://alphacephei.com/vosk/models/vosk-model-small-it-0.22.zip",
        }
        
        model_url = VOSK_MODELS.get(model_name)
        if not model_url:
            yield {"type": "error", "message": f"Unknown model: {model_name}. Available: {list(VOSK_MODELS.keys())}"}
            return
        
        target_dir = self._stt_models_dir / model_name
        
        if target_dir.exists():
            yield {"type": "done", "path": str(target_dir), "message": "Model already exists"}
            return
        
        yield {"type": "progress", "percent": 0, "message": f"Downloading {model_name}..."}
        
        zip_path = self._stt_models_dir / f"{model_name}.zip"
        
        try:
            # Download with progress
            async with httpx.AsyncClient(timeout=600.0) as client:
                async with client.stream("GET", model_url) as response:
                    if response.status_code != 200:
                        yield {"type": "error", "message": f"Download failed: HTTP {response.status_code}"}
                        return
                    
                    total = int(response.headers.get("content-length", 0))
                    downloaded = 0
                    
                    with open(zip_path, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                percent = int((downloaded / total) * 100)
                                yield {"type": "progress", "percent": percent, "message": f"Downloading... {downloaded // 1024 // 1024}MB / {total // 1024 // 1024}MB"}
            
            yield {"type": "progress", "percent": 100, "message": "Extracting..."}
            
            # Extract the zip file
            loop = asyncio.get_running_loop()
            def _extract():
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    zf.extractall(self._stt_models_dir)
                zip_path.unlink()  # Remove zip after extraction
            
            await loop.run_in_executor(self._executor, _extract)
            
            yield {"type": "done", "path": str(target_dir), "message": "Download complete"}
            
        except Exception as e:
            # Cleanup on error
            if zip_path.exists():
                zip_path.unlink()
            yield {"type": "error", "message": str(e)}
    
    def delete_stt_model(self, model_name: str) -> bool:
        """Delete an STT model."""
        import shutil
        target_dir = self._stt_models_dir / model_name
        if target_dir.exists():
            shutil.rmtree(target_dir)
            return True
        return False
    
    # ============================================
    # Voice Management
    # ============================================
    
    def list_voices(self) -> List[Dict[str, Any]]:
        """List available voice files for cloning."""
        voices = []
        if self._voices_dir and self._voices_dir.exists():
            for f in self._voices_dir.iterdir():
                if f.suffix.lower() in ('.wav', '.mp3', '.flac', '.ogg'):
                    voices.append({
                        "name": f.stem,
                        "path": str(f),
                        "format": f.suffix[1:].upper(),
                        "size": f.stat().st_size,
                    })
        return voices
    
    async def save_voice(self, name: str, audio_bytes: bytes, format: str = "wav") -> Dict[str, Any]:
        """Save a voice file for cloning."""
        voice_path = self._voices_dir / f"{name}.{format}"
        voice_path.write_bytes(audio_bytes)
        return {
            "name": name,
            "path": str(voice_path),
            "format": format.upper(),
            "size": len(audio_bytes),
        }
    
    def delete_voice(self, name: str) -> bool:
        """Delete a voice file."""
        for f in self._voices_dir.iterdir():
            if f.stem == name:
                f.unlink()
                return True
        return False
    
    def set_voice(self, voice_path: Optional[str]):
        """Set the voice to use for TTS (path to reference audio)."""
        self._settings.voice_prompt_path = voice_path
    
    # ============================================
    # TTS
    # ============================================
    
    async def load_tts(self, voice_name: Optional[str] = None) -> bool:
        """Load Pocket TTS model.
        
        Args:
            voice_name: Preset voice name (alba, marius, etc.) or path to reference audio
        """
        if not self.is_tts_available:
            logger.error("Pocket TTS not installed")
            return False
        
        def _load():
            logger.info(f"Loading Pocket TTS model (cache: {self._tts_cache_dir})...")
            
            try:
                # Load Pocket TTS with custom cache directory
                model = PocketTTSModel.load_model(cache_dir=self._tts_cache_dir)
                self._tts_model = model
                
                # Set initial voice state
                voice = voice_name or self._settings.voice_prompt_path or "alba"
                self._tts_voice_state = model.get_state_for_audio_prompt(voice)
                
                logger.info(f"Pocket TTS loaded, sample_rate={model.sample_rate}")
                return True
            except Exception as e:
                logger.error(f"Failed to load Pocket TTS: {e}")
                import traceback
                traceback.print_exc()
                return False
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, _load)
    
    def unload_tts(self):
        """Unload TTS model."""
        if self._tts_model is not None:
            del self._tts_model
            self._tts_model = None
            self._tts_voice_state = None
            gc.collect()
            logger.info("TTS model unloaded")
    
    async def generate_speech(
        self,
        text: str,
        voice_path: Optional[str] = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Generate speech from text with streaming audio output.
        Yields PCM16 audio chunks.
        """
        if not self.is_tts_loaded:
            logger.error("TTS model not loaded")
            return
        
        self._stop_event.clear()
        
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
        
        def _worker():
            try:
                with self._tts_lock:
                    # Update voice state if a different voice is requested
                    voice_state = self._tts_voice_state
                    if voice_path:
                        voice_state = self._tts_model.get_state_for_audio_prompt(voice_path)
                    
                    # Pocket TTS has native streaming
                    for audio_chunk in self._tts_model.generate_audio_stream(
                        model_state=voice_state,
                        text_to_generate=text,
                        copy_state=True,  # Preserve state for reuse
                    ):
                        if self._stop_event.is_set():
                            break
                        # Convert to PCM16 bytes
                        audio_np = audio_chunk.cpu().numpy()
                        pcm_bytes = (audio_np * 32767).astype(np.int16).tobytes()
                        loop.call_soon_threadsafe(queue.put_nowait, pcm_bytes)
            except Exception as e:
                logger.error(f"TTS generation error: {e}")
                import traceback
                traceback.print_exc()
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)
        
        threading.Thread(target=_worker, daemon=True).start()
        
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk
    
    def stop_tts(self):
        """Stop current TTS generation."""
        self._stop_event.set()
    
    # ============================================
    # STT
    # ============================================
    
    async def load_stt(self, model_path: Optional[str] = None) -> bool:
        """Load STT model."""
        if not VOSK_AVAILABLE:
            logger.error("Vosk STT not installed")
            return False
        
        def _load():
            # Use default small model if no path provided
            if model_path is None:
                # Check for downloaded models
                models_dir = self._voices_dir.parent / "stt_models"
                if not models_dir.exists():
                    logger.error("No STT model found. Download a Vosk model first.")
                    return False
                
                # Find first available model
                model_dirs = [d for d in models_dir.iterdir() if d.is_dir()]
                if not model_dirs:
                    logger.error("No STT model found in stt_models directory")
                    return False
                
                model_path_to_use = str(model_dirs[0])
            else:
                model_path_to_use = model_path
            
            try:
                self._stt_model = VoskModel(model_path_to_use)
                self._stt_recognizer = KaldiRecognizer(
                    self._stt_model,
                    16000  # Vosk expects 16kHz audio
                )
                logger.info(f"Vosk STT loaded from {model_path_to_use}")
                return True
            except Exception as e:
                logger.error(f"Failed to load STT model: {e}")
                return False
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, _load)
    
    def unload_stt(self):
        """Unload STT model."""
        if self._stt_model is not None:
            del self._stt_model
            del self._stt_recognizer
            self._stt_model = None
            self._stt_recognizer = None
            logger.info("STT model unloaded")
    
    def process_audio_chunk(self, pcm16_bytes: bytes) -> Dict[str, Any]:
        """
        Process an audio chunk for STT.
        Returns partial or final transcription.
        """
        if not self.is_stt_loaded:
            return {"error": "STT not loaded"}
        
        if self._stt_recognizer.AcceptWaveform(pcm16_bytes):
            import json
            result = json.loads(self._stt_recognizer.Result())
            return {"type": "final", "text": result.get("text", "")}
        else:
            import json
            result = json.loads(self._stt_recognizer.PartialResult())
            return {"type": "partial", "text": result.get("partial", "")}
    
    def reset_stt(self):
        """Reset STT recognizer state."""
        if self._stt_recognizer:
            # Create new recognizer to reset state
            self._stt_recognizer = KaldiRecognizer(self._stt_model, 16000)
    
    # Note: VAD is now handled in the frontend with @ricky0123/vad-react


# ============================================
# Global Instance
# ============================================

_voice_manager: Optional[VoiceManager] = None


def get_voice_manager() -> VoiceManager:
    """Get the global voice manager instance."""
    global _voice_manager
    if _voice_manager is None:
        _voice_manager = VoiceManager()
    return _voice_manager


async def close_voice_manager():
    """Close and cleanup voice manager."""
    global _voice_manager
    if _voice_manager is not None:
        _voice_manager.unload_tts()
        _voice_manager.unload_stt()
        _voice_manager = None
