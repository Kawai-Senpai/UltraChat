"""
Vosk STT Test - Menu-driven test program for Vosk speech-to-text.

Tests:
1. List available STT models
2. Download an STT model
3. Load STT model
4. Transcribe audio file
5. Delete STT model
"""

import os
import sys
import wave
import json
import asyncio

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from backend.core.voice_manager import get_voice_manager, VoiceManager

# Data directory for models
DATA_DIR = Path(__file__).parent.parent / "data"
MODELS_DIR = DATA_DIR / "stt_models"

# Available Vosk models for download from alphacep.com
AVAILABLE_MODELS = [
    {"id": "vosk-model-small-en-us-0.15", "language": "English (US)", "size": "40MB"},
    {"id": "vosk-model-en-us-0.22", "language": "English (US)", "size": "1.8GB"},
    {"id": "vosk-model-small-cn-0.22", "language": "Chinese", "size": "42MB"},
    {"id": "vosk-model-small-de-0.15", "language": "German", "size": "45MB"},
    {"id": "vosk-model-small-fr-0.22", "language": "French", "size": "41MB"},
    {"id": "vosk-model-small-es-0.42", "language": "Spanish", "size": "39MB"},
    {"id": "vosk-model-small-ru-0.22", "language": "Russian", "size": "45MB"},
    {"id": "vosk-model-small-ja-0.22", "language": "Japanese", "size": "48MB"},
    {"id": "vosk-model-small-it-0.22", "language": "Italian", "size": "48MB"},
]


def ensure_dirs():
    """Ensure the models directory exists."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)


def list_models():
    """List available Vosk models for download and installed models."""
    vm = get_voice_manager()
    
    # Get installed models
    installed = {m['name'] for m in vm.list_stt_models()}
    
    print("\n" + "="*60)
    print("AVAILABLE VOSK MODELS FOR DOWNLOAD")
    print("="*60)
    
    for i, model in enumerate(AVAILABLE_MODELS, 1):
        status = "✓ INSTALLED" if model['id'] in installed else ""
        print(f"  {i}. {model['id']} {status}")
        print(f"     Language: {model['language']}")
        print(f"     Size: {model['size']}")
        print()
    
    print("\n" + "="*60)
    print("INSTALLED MODELS")
    print("="*60)
    
    if installed:
        for name in sorted(installed):
            print(f"  - {name}")
    else:
        print("  (none)")
    
    return AVAILABLE_MODELS


def download_model(available_models):
    """Download a Vosk model."""
    print("\n" + "="*60)
    print("DOWNLOAD VOSK MODEL")
    print("="*60)
    
    for i, model in enumerate(available_models, 1):
        print(f"  {i}. {model['id']} ({model['size']})")
    
    try:
        choice = int(input("\nEnter model number to download (0 to cancel): "))
        if choice == 0:
            return
        
        if 1 <= choice <= len(available_models):
            model_id = available_models[choice - 1]['id']
            print(f"\nDownloading {model_id}...")
            print("(This may take a while depending on model size)")
            
            vm = get_voice_manager()
            
            async def do_download():
                last_percent = -1
                async for event in vm.download_stt_model(model_id):
                    if event['type'] == 'progress':
                        percent = event.get('percent', 0)
                        if percent != last_percent:
                            print(f"\r  Progress: {percent}% - {event.get('message', '')}", end='', flush=True)
                            last_percent = percent
                    elif event['type'] == 'done':
                        print(f"\n✓ Downloaded to: {event.get('path', 'unknown')}")
                        return True
                    elif event['type'] == 'error':
                        print(f"\n✗ Error: {event.get('message', 'Unknown error')}")
                        return False
                return False
            
            asyncio.run(do_download())
        else:
            print("Invalid choice")
    except ValueError:
        print("Invalid input")


def load_model():
    """Load an installed Vosk model."""
    print("\n" + "="*60)
    print("LOAD VOSK MODEL")
    print("="*60)
    
    if not MODELS_DIR.exists():
        print("No models directory found")
        return False
    
    installed = [d for d in MODELS_DIR.iterdir() if d.is_dir()]
    if not installed:
        print("No models installed")
        return False
    
    for i, model_dir in enumerate(installed, 1):
        print(f"  {i}. {model_dir.name}")
    
    try:
        choice = int(input("\nEnter model number to load (0 to cancel): "))
        if choice == 0:
            return False
        
        if 1 <= choice <= len(installed):
            model_path = str(installed[choice - 1])
            print(f"\nLoading {model_path}...")
            
            import asyncio
            vm = get_voice_manager()
            success = asyncio.run(vm.load_stt(model_path))
            
            if success:
                print("✓ Model loaded successfully")
                return True
            else:
                print("✗ Failed to load model")
                return False
        else:
            print("Invalid choice")
            return False
    except ValueError:
        print("Invalid input")
        return False


def transcribe_audio():
    """Transcribe an audio file."""
    print("\n" + "="*60)
    print("TRANSCRIBE AUDIO FILE")
    print("="*60)
    
    vm = get_voice_manager()
    
    if not vm.is_stt_loaded:
        print("No STT model loaded. Load one first.")
        return
    
    audio_path = input("Enter path to audio file (WAV, 16kHz mono): ").strip()
    if not audio_path:
        return
    
    audio_path = Path(audio_path)
    if not audio_path.exists():
        print(f"File not found: {audio_path}")
        return
    
    print(f"\nTranscribing {audio_path}...")
    
    try:
        # Read WAV file
        with wave.open(str(audio_path), 'rb') as wf:
            if wf.getnchannels() != 1:
                print("Error: Audio must be mono")
                return
            if wf.getsampwidth() != 2:
                print("Error: Audio must be 16-bit")
                return
            if wf.getframerate() != 16000:
                print(f"Warning: Sample rate is {wf.getframerate()}, expected 16000")
            
            # Read audio data
            audio_data = wf.readframes(wf.getnframes())
        
        # Transcribe
        import asyncio
        
        async def run_transcription():
            results = []
            async for result in vm.transcribe_stream(iter([audio_data])):
                results.append(result)
            return results
        
        results = asyncio.run(run_transcription())
        
        print("\n" + "-"*40)
        print("TRANSCRIPTION RESULTS:")
        print("-"*40)
        
        for r in results:
            if r.get('final'):
                print(f"[FINAL] {r.get('text', '')}")
            else:
                print(f"[PARTIAL] {r.get('text', '')}")
        
    except Exception as e:
        print(f"Error: {e}")


def delete_model():
    """Delete an installed Vosk model."""
    print("\n" + "="*60)
    print("DELETE VOSK MODEL")
    print("="*60)
    
    if not MODELS_DIR.exists():
        print("No models directory found")
        return
    
    installed = [d for d in MODELS_DIR.iterdir() if d.is_dir()]
    if not installed:
        print("No models installed")
        return
    
    for i, model_dir in enumerate(installed, 1):
        print(f"  {i}. {model_dir.name}")
    
    try:
        choice = int(input("\nEnter model number to delete (0 to cancel): "))
        if choice == 0:
            return
        
        if 1 <= choice <= len(installed):
            model_dir = installed[choice - 1]
            confirm = input(f"Delete {model_dir.name}? (y/n): ").strip().lower()
            
            if confirm == 'y':
                import shutil
                shutil.rmtree(model_dir)
                print(f"✓ Deleted {model_dir.name}")
            else:
                print("Cancelled")
        else:
            print("Invalid choice")
    except ValueError:
        print("Invalid input")


def main():
    """Main menu loop."""
    ensure_dirs()
    available_models = []
    
    while True:
        print("\n" + "="*60)
        print("VOSK STT TEST MENU")
        print("="*60)
        print("  1. List available/installed models")
        print("  2. Download a model")
        print("  3. Load a model")
        print("  4. Transcribe audio file")
        print("  5. Delete a model")
        print("  0. Exit")
        print("="*60)
        
        choice = input("Enter choice: ").strip()
        
        if choice == '0':
            print("Goodbye!")
            break
        elif choice == '1':
            available_models = list_models()
        elif choice == '2':
            if not available_models:
                available_models = list_models()
            download_model(available_models)
        elif choice == '3':
            load_model()
        elif choice == '4':
            transcribe_audio()
        elif choice == '5':
            delete_model()
        else:
            print("Invalid choice")


if __name__ == "__main__":
    main()
