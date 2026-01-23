"""
Pocket TTS Test - Menu-driven test program for Pocket TTS text-to-speech.

Tests:
1. Check TTS availability
2. Load TTS model
3. Generate speech (non-streaming)
4. Generate speech (streaming)
5. List preset voices
6. Clone voice from file
7. Unload TTS model
"""

import os
import sys
import wave
import time

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path

# Data directory for outputs
DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR = DATA_DIR / "exports" / "tts_test"
VOICES_DIR = DATA_DIR / "voices"
TTS_CACHE_DIR = DATA_DIR / "tts_cache"

# Try to import Pocket TTS (installed as editable package)
try:
    from pocket_tts import TTSModel
    POCKET_TTS_AVAILABLE = True
except ImportError as e:
    POCKET_TTS_AVAILABLE = False
    print(f"Pocket TTS not available: {e}")


def ensure_dirs():
    """Ensure output directories exist."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# Global model state
tts_model = None
voice_state = None


def check_availability():
    """Check TTS availability and dependencies."""
    print("\n" + "="*60)
    print("TTS AVAILABILITY CHECK")
    print("="*60)
    
    print(f"  Pocket TTS available: {'✓' if POCKET_TTS_AVAILABLE else '✗'}")
    
    try:
        import torch
        print(f"\n  PyTorch version: {torch.__version__}")
        print(f"  Note: Pocket TTS runs on CPU (no GPU speedup)")
    except ImportError:
        print("  PyTorch not available!")


def load_model():
    """Load TTS model."""
    global tts_model, voice_state
    
    print("\n" + "="*60)
    print("LOAD POCKET TTS MODEL")
    print("="*60)
    
    if not POCKET_TTS_AVAILABLE:
        print("Pocket TTS not available!")
        return
    
    if tts_model is not None:
        print("TTS already loaded")
        unload = input("Unload current model? (y/n): ").strip().lower()
        if unload == 'y':
            tts_model = None
            voice_state = None
            print("Unloaded")
        else:
            return
    
    print("\nLoading Pocket TTS model...")
    print("(This may take a while on first run as models are downloaded)")
    print(f"Cache directory: {TTS_CACHE_DIR}")
    
    try:
        start = time.time()
        # Use custom cache directory for model downloads
        tts_model = TTSModel.load_model(cache_dir=TTS_CACHE_DIR)
        elapsed = time.time() - start
        
        print(f"✓ Model loaded in {elapsed:.1f}s")
        print(f"  Sample rate: {tts_model.sample_rate}")
        print(f"  Device: {tts_model.device}")
        
        # Set default voice
        print("\nSetting default voice (alba)...")
        voice_state = tts_model.get_state_for_audio_prompt("alba")
        print("✓ Default voice set")
        
    except Exception as e:
        print(f"✗ Failed to load model: {e}")
        import traceback
        traceback.print_exc()


def list_preset_voices():
    """List available preset voices."""
    print("\n" + "="*60)
    print("PRESET VOICES")
    print("="*60)
    
    # From pocket_tts.utils.utils.PREDEFINED_VOICES
    preset_voices = ["alba", "marius", "javert", "jean", "fantine", "cosette", "eponine", "azelma"]
    
    print("Available preset voices:")
    for i, voice in enumerate(preset_voices, 1):
        print(f"  {i}. {voice}")
    
    print("\nCustom voices (in data/voices/):")
    voices = list(VOICES_DIR.glob("*.wav")) + list(VOICES_DIR.glob("*.mp3"))
    if voices:
        for v in voices:
            size = v.stat().st_size / 1024
            print(f"  - {v.name} ({size:.1f} KB)")
    else:
        print("  (none)")
    
    return preset_voices


def set_voice(preset_voices):
    """Set the voice to use."""
    global voice_state
    
    print("\n" + "="*60)
    print("SET VOICE")
    print("="*60)
    
    if tts_model is None:
        print("Load TTS model first!")
        return
    
    print("1. Use preset voice")
    print("2. Clone from audio file")
    print("0. Cancel")
    
    choice = input("\nChoice: ").strip()
    
    if choice == '1':
        print("\nPreset voices:")
        for i, voice in enumerate(preset_voices, 1):
            print(f"  {i}. {voice}")
        
        voice_choice = input("\nEnter number: ").strip()
        try:
            idx = int(voice_choice) - 1
            if 0 <= idx < len(preset_voices):
                voice_name = preset_voices[idx]
                print(f"\nSetting voice to {voice_name}...")
                voice_state = tts_model.get_state_for_audio_prompt(voice_name)
                print(f"✓ Voice set to {voice_name}")
            else:
                print("Invalid choice")
        except ValueError:
            print("Invalid input")
    
    elif choice == '2':
        voices = list(VOICES_DIR.glob("*.wav")) + list(VOICES_DIR.glob("*.mp3"))
        if not voices:
            print(f"\nNo voice files found in {VOICES_DIR}")
            print("Add WAV or MP3 files (5-30s of speech) to use for cloning.")
            return
        
        print("\nAvailable voice files:")
        for i, v in enumerate(voices, 1):
            print(f"  {i}. {v.name}")
        
        voice_choice = input("\nEnter number: ").strip()
        try:
            idx = int(voice_choice) - 1
            if 0 <= idx < len(voices):
                voice_path = voices[idx]
                print(f"\nCloning voice from {voice_path.name}...")
                voice_state = tts_model.get_state_for_audio_prompt(str(voice_path))
                print(f"✓ Voice cloned from {voice_path.name}")
            else:
                print("Invalid choice")
        except ValueError:
            print("Invalid input")


def generate_speech():
    """Generate speech from text (non-streaming)."""
    global voice_state
    
    print("\n" + "="*60)
    print("GENERATE SPEECH (NON-STREAMING)")
    print("="*60)
    
    if tts_model is None:
        print("Load TTS model first!")
        return
    
    if voice_state is None:
        print("No voice state set. Using default voice...")
        voice_state = tts_model.get_state_for_audio_prompt("alba")
    
    text = input("Enter text to synthesize: ").strip()
    if not text:
        print("No text entered")
        return
    
    print(f"\nGenerating speech...")
    print(f"  Text: {text[:50]}{'...' if len(text) > 50 else ''}")
    
    try:
        import numpy as np
        
        start = time.time()
        audio = tts_model.generate_audio(
            model_state=voice_state,
            text_to_generate=text,
            copy_state=True
        )
        elapsed = time.time() - start
        
        # Save to file
        output_path = OUTPUT_DIR / f"tts_output_{int(time.time())}.wav"
        
        audio_np = audio.cpu().numpy()
        sample_rate = tts_model.sample_rate
        
        # Convert to int16
        audio_int16 = (audio_np * 32767).astype(np.int16)
        
        with wave.open(str(output_path), 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_int16.tobytes())
        
        duration = len(audio_np) / sample_rate
        rtf = elapsed / duration if duration > 0 else 0
        
        print(f"\n✓ Generated in {elapsed:.2f}s")
        print(f"  Duration: {duration:.2f}s")
        print(f"  RTF: {rtf:.2f}x real-time")
        print(f"  Saved to: {output_path}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


def generate_speech_streaming():
    """Generate speech from text (streaming)."""
    global voice_state
    
    print("\n" + "="*60)
    print("GENERATE SPEECH (STREAMING)")
    print("="*60)
    
    if tts_model is None:
        print("Load TTS model first!")
        return
    
    if voice_state is None:
        print("No voice state set. Using default voice...")
        voice_state = tts_model.get_state_for_audio_prompt("alba")
    
    text = input("Enter text to synthesize: ").strip()
    if not text:
        print("No text entered")
        return
    
    print(f"\nGenerating speech (streaming)...")
    print(f"  Text: {text[:50]}{'...' if len(text) > 50 else ''}")
    
    try:
        import numpy as np
        
        start = time.time()
        chunks = []
        chunk_count = 0
        first_chunk_time = None
        
        for audio_chunk in tts_model.generate_audio_stream(
            model_state=voice_state,
            text_to_generate=text,
            copy_state=True
        ):
            if first_chunk_time is None:
                first_chunk_time = time.time() - start
            chunk_count += 1
            chunks.append(audio_chunk.cpu().numpy())
            print(f"  Chunk {chunk_count} received")
        
        elapsed = time.time() - start
        
        if not chunks:
            print("No audio generated")
            return
        
        # Concatenate chunks
        audio_np = np.concatenate(chunks)
        
        # Save to file
        output_path = OUTPUT_DIR / f"tts_stream_{int(time.time())}.wav"
        sample_rate = tts_model.sample_rate
        
        # Convert to int16
        audio_int16 = (audio_np * 32767).astype(np.int16)
        
        with wave.open(str(output_path), 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_int16.tobytes())
        
        duration = len(audio_np) / sample_rate
        
        print(f"\n✓ Streaming complete in {elapsed:.2f}s")
        print(f"  Total chunks: {chunk_count}")
        print(f"  First chunk latency: {first_chunk_time:.3f}s")
        print(f"  Duration: {duration:.2f}s")
        print(f"  Saved to: {output_path}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


def unload_model():
    """Unload TTS model."""
    global tts_model, voice_state
    
    print("\n" + "="*60)
    print("UNLOAD TTS MODEL")
    print("="*60)
    
    if tts_model is None:
        print("No TTS model loaded")
        return
    
    confirm = input("Unload TTS model? (y/n): ").strip().lower()
    if confirm == 'y':
        tts_model = None
        voice_state = None
        import gc
        gc.collect()
        print("✓ Model unloaded")
    else:
        print("Cancelled")


def main():
    """Main menu loop."""
    ensure_dirs()
    preset_voices = ["alba", "marius", "javert", "jean", "fantine", "cosette", "eponine", "azelma"]
    
    while True:
        print("\n" + "="*60)
        print("POCKET TTS TEST MENU")
        print("="*60)
        print("  1. Check availability")
        print("  2. Load TTS model")
        print("  3. Generate speech (non-streaming)")
        print("  4. Generate speech (streaming)")
        print("  5. List preset voices")
        print("  6. Set voice (preset or clone)")
        print("  7. Unload TTS model")
        print("  0. Exit")
        print("="*60)
        
        choice = input("Enter choice: ").strip()
        
        if choice == '0':
            print("Goodbye!")
            break
        elif choice == '1':
            check_availability()
        elif choice == '2':
            load_model()
        elif choice == '3':
            generate_speech()
        elif choice == '4':
            generate_speech_streaming()
        elif choice == '5':
            preset_voices = list_preset_voices()
        elif choice == '6':
            set_voice(preset_voices)
        elif choice == '7':
            unload_model()
        else:
            print("Invalid choice")


if __name__ == "__main__":
    main()
