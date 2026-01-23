"""
UltraChat - Voice Routes
WebSocket endpoints for voice chat (TTS + STT).
"""

import json
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse

from ..core import (
    get_voice_manager,
    TokenChunker,
    create_token_event,
    create_done_event,
    create_error_event,
    create_status_event,
)
from ..services import get_chat_service
from ..models import VoiceModel


router = APIRouter(prefix="/voice", tags=["voice"])
logger = logging.getLogger("ultrachat.voice.routes")


# ============================================
# REST Endpoints
# ============================================

@router.get("/status")
async def get_voice_status():
    """Get voice system status."""
    manager = get_voice_manager()
    return manager.get_status()


@router.post("/tts/load")
async def load_tts(voice_name: Optional[str] = None):
    """Load TTS model."""
    manager = get_voice_manager()
    
    if not manager.is_tts_available:
        raise HTTPException(
            status_code=503,
            detail="Pocket TTS not installed. Run: pip install -e ./backend/core/pocket_tts"
        )
    
    success = await manager.load_tts(voice_name=voice_name)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to load TTS model")
    
    return {"success": True, "sample_rate": manager.tts_sample_rate}


@router.post("/tts/unload")
async def unload_tts():
    """Unload TTS model."""
    manager = get_voice_manager()
    manager.unload_tts()
    return {"success": True}


@router.post("/stt/load")
async def load_stt(model_path: Optional[str] = None):
    """Load STT model."""
    manager = get_voice_manager()
    
    if not manager.is_stt_available:
        raise HTTPException(
            status_code=503,
            detail="Vosk STT not installed. Run: pip install vosk"
        )
    
    success = await manager.load_stt(model_path=model_path)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to load STT model")
    
    return {"success": True}


@router.post("/stt/unload")
async def unload_stt():
    """Unload STT model."""
    manager = get_voice_manager()
    manager.unload_stt()
    return {"success": True}


# ============================================
# STT Model Management
# ============================================

@router.get("/stt/models")
async def list_stt_models():
    """List available STT models."""
    manager = get_voice_manager()
    return {"models": manager.list_stt_models()}


@router.get("/stt/models/available")
async def list_available_stt_models():
    """List STT models available for download from alphacep.com."""
    # Official Vosk models from https://alphacephei.com/vosk/models
    available = [
        {
            "name": "vosk-model-small-en-us-0.15",
            "language": "English (US)",
            "size_mb": 40,
            "description": "Small English model, fast and accurate",
        },
        {
            "name": "vosk-model-en-us-0.22",
            "language": "English (US)",
            "size_mb": 1800,
            "description": "Large English model, highest accuracy",
        },
        {
            "name": "vosk-model-small-cn-0.22",
            "language": "Chinese",
            "size_mb": 42,
            "description": "Small Chinese model",
        },
        {
            "name": "vosk-model-small-de-0.15",
            "language": "German",
            "size_mb": 45,
            "description": "Small German model",
        },
        {
            "name": "vosk-model-small-fr-0.22",
            "language": "French",
            "size_mb": 41,
            "description": "Small French model",
        },
        {
            "name": "vosk-model-small-es-0.42",
            "language": "Spanish",
            "size_mb": 39,
            "description": "Small Spanish model",
        },
        {
            "name": "vosk-model-small-ru-0.22",
            "language": "Russian",
            "size_mb": 45,
            "description": "Small Russian model",
        },
        {
            "name": "vosk-model-small-ja-0.22",
            "language": "Japanese",
            "size_mb": 48,
            "description": "Small Japanese model",
        },
        {
            "name": "vosk-model-small-it-0.22",
            "language": "Italian",
            "size_mb": 48,
            "description": "Small Italian model",
        },
    ]
    
    manager = get_voice_manager()
    installed = {m["name"] for m in manager.list_stt_models()}
    
    for model in available:
        model["installed"] = model["name"] in installed
    
    return {"models": available}


@router.post("/stt/models/download")
async def download_stt_model(model_name: str):
    """
    Download an STT model. Returns SSE stream.
    """
    from fastapi.responses import StreamingResponse
    
    manager = get_voice_manager()
    
    async def generate():
        async for event in manager.download_stt_model(model_name):
            yield f"data: {json.dumps(event)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.delete("/stt/models/{model_name}")
async def delete_stt_model(model_name: str):
    """Delete an STT model."""
    manager = get_voice_manager()
    
    if not manager.delete_stt_model(model_name):
        raise HTTPException(status_code=404, detail="Model not found")
    
    return {"success": True}


# ============================================
# Voice Management (System + User Voices)
# ============================================

@router.get("/voices")
async def list_voices(include_system: bool = True, include_user: bool = True):
    """List available voices for TTS (system + user voices)."""
    voices = await VoiceModel.get_all(include_system=include_system, include_user=include_user)
    return {"voices": voices}


@router.get("/voices/system")
async def list_system_voices():
    """List system voices only."""
    voices = await VoiceModel.get_system_voices()
    return {"voices": voices}


@router.get("/voices/user")
async def list_user_voices():
    """List user-uploaded voices only."""
    voices = await VoiceModel.get_user_voices()
    return {"voices": voices}


@router.post("/voices/register-system")
async def register_system_voices():
    """Register/update system voices from the system_voices directory."""
    from ..config import get_settings_manager
    
    settings = get_settings_manager()
    data_dir = settings.get_db_path().parent
    system_voices_dir = data_dir / "system_voices"
    
    if not system_voices_dir.exists():
        return {"success": False, "message": f"System voices directory not found: {system_voices_dir}", "count": 0}
    
    count = await VoiceModel.register_system_voices(system_voices_dir)
    return {"success": True, "count": count, "directory": str(system_voices_dir)}


@router.post("/voices")
async def upload_voice(
    name: str = Form(...),
    description: str = Form(None),
    file: UploadFile = File(...)
):
    """Upload a custom voice file for cloning."""
    manager = get_voice_manager()
    
    # Validate file type
    allowed_types = {'.wav', '.mp3', '.flac', '.ogg'}
    ext = '.' + file.filename.split('.')[-1].lower() if '.' in file.filename else ''
    if ext not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}"
        )
    
    # Read and save to voices directory
    audio_bytes = await file.read()
    voice_info = await manager.save_voice(name, audio_bytes, ext[1:])
    
    # Register in database
    voice_record = await VoiceModel.create(
        name=name,
        file_path=voice_info['path'],
        display_name=name,
        description=description,
        category="custom"
    )
    
    return voice_record


@router.get("/voices/{voice_id}")
async def get_voice(voice_id: str):
    """Get voice details by ID."""
    voice = await VoiceModel.get_by_id(voice_id)
    if not voice:
        raise HTTPException(status_code=404, detail="Voice not found")
    return voice


@router.patch("/voices/{voice_id}")
async def update_voice(voice_id: str, updates: Dict[str, Any]):
    """Update voice details (user voices only)."""
    voice = await VoiceModel.update(voice_id, **updates)
    if not voice:
        raise HTTPException(status_code=404, detail="Voice not found")
    return voice


@router.delete("/voices/{voice_id}")
async def delete_voice(voice_id: str):
    """Delete a user voice."""
    voice = await VoiceModel.get_by_id(voice_id)
    if not voice:
        raise HTTPException(status_code=404, detail="Voice not found")
    
    if voice.get('is_system'):
        raise HTTPException(status_code=403, detail="Cannot delete system voices")
    
    # Delete file if it exists
    if voice.get('file_path'):
        file_path = Path(voice['file_path'])
        if file_path.exists():
            file_path.unlink()
    
    # Delete from database
    if not await VoiceModel.delete(voice_id):
        raise HTTPException(status_code=500, detail="Failed to delete voice")
    
    return {"success": True}


@router.post("/voices/{voice_id}/set")
async def set_active_voice(voice_id: str):
    """Set the active voice for TTS."""
    voice = await VoiceModel.get_by_id(voice_id)
    if not voice:
        raise HTTPException(status_code=404, detail="Voice not found")
    
    manager = get_voice_manager()
    manager.set_voice(voice['file_path'])
    return {"success": True, "voice": voice}


@router.post("/voices/clear")
async def clear_active_voice():
    """Clear the active voice (use default)."""
    manager = get_voice_manager()
    manager.set_voice(None)
    return {"success": True}


# ============================================
# WebSocket Endpoints
# ============================================

@router.websocket("/ws/tts")
async def websocket_tts(ws: WebSocket):
    """
    WebSocket for TTS streaming.
    
    Protocol:
    - Client sends: {"type": "start", "text": "...", "voice": "optional_voice_name"}
    - Client sends: {"type": "stop"} to cancel
    - Server sends: {"type": "format", "sr": 24000, "encoding": "pcm16", "channels": 1}
    - Server sends: binary PCM16 audio chunks
    - Server sends: {"type": "done"}
    - Server sends: {"type": "error", "message": "..."}
    """
    await ws.accept()
    manager = get_voice_manager()
    
    if not manager.is_tts_loaded:
        await ws.send_json({"type": "error", "message": "TTS not loaded"})
        await ws.close()
        return
    
    stop_event = asyncio.Event()
    
    async def control_loop():
        try:
            while True:
                msg = await ws.receive_json()
                if msg.get("type") == "stop":
                    stop_event.set()
                    manager.stop_tts()
        except WebSocketDisconnect:
            stop_event.set()
            manager.stop_tts()
    
    ctrl_task = asyncio.create_task(control_loop())
    
    try:
        # Send format info
        await ws.send_json({
            "type": "format",
            "sr": manager.tts_sample_rate,
            "encoding": "pcm16",
            "channels": 1
        })
        
        while True:
            try:
                req = await ws.receive_json()
            except WebSocketDisconnect:
                break
            
            if req.get("type") != "start":
                continue
            
            text = req.get("text", "").strip()
            if not text:
                await ws.send_json({"type": "error", "message": "Empty text"})
                continue
            
            voice = req.get("voice")
            voice_path = None
            if voice:
                voices = manager.list_voices()
                voice_info = next((v for v in voices if v['name'] == voice), None)
                if voice_info:
                    voice_path = voice_info['path']
            
            stop_event.clear()
            
            # Stream audio chunks
            async for audio_chunk in manager.generate_speech(text, voice_path=voice_path):
                if stop_event.is_set():
                    break
                await ws.send_bytes(audio_chunk)
            
            await ws.send_json({"type": "done"})
    
    finally:
        ctrl_task.cancel()


@router.websocket("/ws/stt")
async def websocket_stt(ws: WebSocket):
    """
    WebSocket for STT streaming.
    
    Protocol:
    - Client sends: binary PCM16 audio chunks (16kHz, mono)
    - Server sends: {"type": "partial", "text": "..."}
    - Server sends: {"type": "final", "text": "..."}
    - Client sends: {"type": "reset"} to reset recognizer
    """
    await ws.accept()
    manager = get_voice_manager()
    
    if not manager.is_stt_loaded:
        await ws.send_json({"type": "error", "message": "STT not loaded"})
        await ws.close()
        return
    
    # Initialize VAD if available
    if manager.is_vad_available:
        manager.init_vad()
    
    try:
        while True:
            message = await ws.receive()
            
            if message["type"] == "websocket.disconnect":
                break
            
            if "text" in message:
                # JSON message
                data = json.loads(message["text"])
                if data.get("type") == "reset":
                    manager.reset_stt()
                    await ws.send_json({"type": "reset_done"})
            
            elif "bytes" in message:
                # Audio data
                audio_bytes = message["bytes"]
                
                # Optional VAD filtering
                if manager._vad:
                    if not manager.is_speech(audio_bytes, sample_rate=16000):
                        continue  # Skip non-speech audio
                
                # Process audio
                result = manager.process_audio_chunk(audio_bytes)
                
                if "error" not in result and result.get("text"):
                    await ws.send_json(result)
    
    except WebSocketDisconnect:
        pass


@router.websocket("/ws/voice-chat")
async def websocket_voice_chat(ws: WebSocket):
    """
    Full voice chat WebSocket combining STT -> LLM -> TTS.
    
    Protocol:
    - Client sends: binary PCM16 audio (user speaking)
    - Client sends: {"type": "end_speech"} when user stops speaking
    - Client sends: {"type": "stop"} to cancel
    - Client sends: {"type": "config", "enable_thinking": false, "tools": [...]}
    - Server sends: {"type": "transcription", "text": "...", "final": bool}
    - Server sends: {"type": "llm_token", "token": "..."}
    - Server sends: {"type": "audio", "data": base64_pcm16}
    - Server sends: {"type": "done"}
    """
    await ws.accept()
    
    voice_manager = get_voice_manager()
    chat_service = get_chat_service()
    
    # Check prerequisites
    if not voice_manager.is_tts_loaded:
        await ws.send_json({"type": "error", "message": "TTS not loaded"})
        await ws.close()
        return
    
    if not voice_manager.is_stt_loaded:
        await ws.send_json({"type": "error", "message": "STT not loaded"})
        await ws.close()
        return
    
    # Session state
    config = {
        "enable_thinking": False,  # Disable thinking by default for voice (faster)
        "tools": [],
        "conversation_id": None,
        "profile_id": None,
    }
    stop_event = asyncio.Event()
    audio_buffer = bytearray()
    
    # Initialize VAD
    if voice_manager.is_vad_available:
        voice_manager.init_vad()
    
    async def process_speech():
        """Process accumulated speech and generate response."""
        nonlocal audio_buffer
        
        if not audio_buffer:
            return
        
        # Get final transcription
        result = voice_manager.process_audio_chunk(bytes(audio_buffer))
        audio_buffer.clear()
        voice_manager.reset_stt()
        
        user_text = result.get("text", "").strip()
        if not user_text:
            return
        
        await ws.send_json({"type": "transcription", "text": user_text, "final": True})
        
        # Send to LLM
        chunker = TokenChunker(
            max_words=voice_manager._settings.chunk_max_words,
            max_wait_s=voice_manager._settings.chunk_max_wait_s,
        )
        text_queue = asyncio.Queue()
        
        async def llm_to_tts():
            """Stream LLM tokens and chunk for TTS."""
            full_response = ""
            
            async for event in chat_service.send_message(
                conversation_id=config.get("conversation_id"),
                message=user_text,
                profile_id=config.get("profile_id"),
                stream=True,
                enable_thinking=config.get("enable_thinking", False),
                tools=config.get("tools") or None,
            ):
                if stop_event.is_set():
                    break
                
                # Parse SSE event
                if event.startswith("data: "):
                    try:
                        data = json.loads(event[6:])
                        event_type = data.get("type")
                        
                        if event_type == "token":
                            token = data.get("content", "")
                            full_response += token
                            await ws.send_json({"type": "llm_token", "token": token})
                            
                            # Chunk for TTS
                            chunk = chunker.feed(token)
                            if chunk:
                                await text_queue.put(chunk)
                        
                        elif event_type == "done":
                            # Flush remaining text
                            tail = chunker.flush()
                            if tail:
                                await text_queue.put(tail)
                            await text_queue.put(None)  # Sentinel
                            
                            # Update conversation ID for future turns
                            config["conversation_id"] = data.get("conversation_id")
                        
                        elif event_type == "error":
                            await ws.send_json({
                                "type": "error",
                                "message": data.get("message", "Unknown error")
                            })
                            await text_queue.put(None)
                    
                    except json.JSONDecodeError:
                        pass
        
        async def tts_worker():
            """Process text chunks and stream audio."""
            import base64
            
            while not stop_event.is_set():
                chunk = await text_queue.get()
                if chunk is None:
                    break
                
                async for audio_bytes in voice_manager.generate_speech(chunk):
                    if stop_event.is_set():
                        break
                    # Send as base64 for JSON transport
                    await ws.send_json({
                        "type": "audio",
                        "data": base64.b64encode(audio_bytes).decode('ascii')
                    })
        
        # Run LLM and TTS in parallel
        await asyncio.gather(
            llm_to_tts(),
            tts_worker(),
        )
        
        await ws.send_json({"type": "done"})
    
    try:
        await ws.send_json({
            "type": "ready",
            "tts_sample_rate": voice_manager.tts_sample_rate,
        })
        
        while True:
            message = await ws.receive()
            
            if message["type"] == "websocket.disconnect":
                break
            
            if "text" in message:
                data = json.loads(message["text"])
                msg_type = data.get("type")
                
                if msg_type == "config":
                    config.update({
                        "enable_thinking": data.get("enable_thinking", False),
                        "tools": data.get("tools", []),
                        "conversation_id": data.get("conversation_id"),
                        "profile_id": data.get("profile_id"),
                    })
                
                elif msg_type == "end_speech":
                    await process_speech()
                
                elif msg_type == "stop":
                    stop_event.set()
                    voice_manager.stop_tts()
            
            elif "bytes" in message:
                # Accumulate audio for STT
                audio_bytes = message["bytes"]
                audio_buffer.extend(audio_bytes)
                
                # Send partial transcription
                result = voice_manager.process_audio_chunk(audio_bytes)
                if result.get("text"):
                    await ws.send_json({
                        "type": "transcription",
                        "text": result.get("text"),
                        "final": result.get("type") == "final"
                    })
    
    except WebSocketDisconnect:
        pass
    finally:
        stop_event.set()
