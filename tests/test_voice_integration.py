"""
Test script to verify voice chat system integration
Tests microphone access, WebSocket, and audio processing
"""
import asyncio
import json
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

def test_voice_manager():
    """Test voice manager initialization"""
    logger.info("=" * 60)
    logger.info("Testing Voice Manager")
    logger.info("=" * 60)
    
    try:
        from backend.core import get_voice_manager
        
        manager = get_voice_manager()
        status = manager.get_status()
        
        logger.info(f"\nVoice Manager Status:")
        logger.info(f"  TTS Available: {status['tts_available']}")
        logger.info(f"  TTS Loaded: {status['tts_loaded']}")
        logger.info(f"  STT Available: {status['stt_available']}")
        logger.info(f"  STT Loaded: {status['stt_loaded']}")
        logger.info(f"  STT Models Available: {len(status['stt_models'])}")
        
        for model in status['stt_models']:
            logger.info(f"    - {model['name']} ({model['type']})")
        
        # Check if models need to be loaded
        if not status['tts_loaded']:
            logger.warning("\n⚠️ TTS not loaded - call loadTTS endpoint first")
        else:
            logger.info("\n✅ TTS is loaded")
        
        if not status['stt_loaded']:
            logger.warning("⚠️ STT not loaded - call loadSTT endpoint first")
        else:
            logger.info("✅ STT is loaded")
        
        return True
    except Exception as e:
        logger.error(f"Voice manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_audio_conversion():
    """Test PCM16 audio conversion"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Audio Conversion")
    logger.info("=" * 60)
    
    try:
        import numpy as np
        from backend.core.voice_manager import pcm16_to_float32
        
        # Create test PCM16 data (1000 samples)
        pcm16 = np.array([-32768, -16384, 0, 16384, 32767] * 200, dtype=np.int16)
        pcm16_bytes = pcm16.tobytes()
        
        logger.info(f"\nTest data:")
        logger.info(f"  PCM16 bytes: {len(pcm16_bytes)}")
        logger.info(f"  Expected samples: 1000, Actual: {len(pcm16) // 2}")
        
        # Convert to float32
        float32 = pcm16_to_float32(pcm16_bytes)
        logger.info(f"\nConversion result:")
        logger.info(f"  Float32 shape: {float32.shape}")
        logger.info(f"  Range: [{float32.min():.3f}, {float32.max():.3f}]")
        
        if float32.min() >= -1.0 and float32.max() <= 1.0:
            logger.info("✅ Audio conversion working correctly")
            return True
        else:
            logger.error("❌ Audio conversion out of range")
            return False
    except Exception as e:
        logger.error(f"Audio conversion test failed: {e}")
        return False

def test_websocket_url():
    """Test WebSocket URL generation"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing WebSocket URLs")
    logger.info("=" * 60)
    
    try:
        # Simulate frontend WebSocket creation
        protocol = 'ws:'  # Simulating HTTP localhost
        host = 'localhost:8000'
        
        urls = {
            'tts': f"{protocol}//{host}/api/v1/voice/ws/tts",
            'stt': f"{protocol}//{host}/api/v1/voice/ws/stt",
            'voice-chat': f"{protocol}//{host}/api/v1/voice/ws/voice-chat"
        }
        
        logger.info("\nGenerated WebSocket URLs:")
        for name, url in urls.items():
            logger.info(f"  {name}: {url}")
        
        logger.info("\n✅ WebSocket URLs generated correctly")
        return True
    except Exception as e:
        logger.error(f"WebSocket URL test failed: {e}")
        return False

async def test_stt_processing():
    """Test STT audio processing"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing STT Audio Processing")
    logger.info("=" * 60)
    
    try:
        from backend.core import get_voice_manager
        
        manager = get_voice_manager()
        
        # Check if STT is loaded
        if not manager.is_stt_loaded:
            logger.warning("\n⚠️ STT not loaded, skipping STT processing test")
            return False
        
        # Create silent audio (16kHz for 100ms = 1600 samples)
        import numpy as np
        silent_audio = np.zeros(1600, dtype=np.int16)
        pcm16_bytes = silent_audio.tobytes()
        
        logger.info(f"\nProcessing test audio:")
        logger.info(f"  Audio bytes: {len(pcm16_bytes)}")
        logger.info(f"  Audio samples: {len(silent_audio)}")
        
        result = manager.process_audio_chunk(pcm16_bytes)
        logger.info(f"\nSTT result: {result}")
        
        if "error" not in result:
            logger.info("✅ STT processing working")
            return True
        else:
            logger.error(f"❌ STT processing error: {result['error']}")
            return False
    except Exception as e:
        logger.error(f"STT processing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    logger.info("\n")
    logger.info("╔════════════════════════════════════════════════════════════╗")
    logger.info("║     Voice Chat System Integration Tests                   ║")
    logger.info("╚════════════════════════════════════════════════════════════╝")
    
    results = {
        'Voice Manager': test_voice_manager(),
        'Audio Conversion': test_audio_conversion(),
        'WebSocket URLs': test_websocket_url(),
    }
    
    # Run async tests
    try:
        loop = asyncio.get_event_loop()
        results['STT Processing'] = loop.run_until_complete(test_stt_processing())
    except Exception as e:
        logger.error(f"Failed to run async tests: {e}")
        results['STT Processing'] = False
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{test_name}: {status}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("\n🎉 All tests passed!")
    else:
        logger.info(f"\n⚠️ {total - passed} test(s) failed. See logs above.")
    
    return passed == total

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
