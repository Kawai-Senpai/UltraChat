import { useRef, useEffect, useCallback } from 'react'
import { useMicVAD } from '@ricky0123/vad-react'
import { voiceAPI } from '../lib/api'

// Comprehensive logging utility
const log = {
  debug: (msg, data) => console.log(`[VoiceChat-DEBUG] ${msg}`, data || ''),
  info: (msg, data) => console.info(`[VoiceChat-INFO] ${msg}`, data || ''),
  warn: (msg, data) => console.warn(`[VoiceChat-WARN] ${msg}`, data || ''),
  error: (msg, data) => console.error(`[VoiceChat-ERROR] ${msg}`, data || ''),
}

const vadLog = {
  debug: (msg, data) => console.log(`[VAD-DEBUG] ${msg}`, data || ''),
  info: (msg, data) => console.info(`[VAD-INFO] ${msg}`, data || ''),
  warn: (msg, data) => console.warn(`[VAD-WARN] ${msg}`, data || ''),
  error: (msg, data) => console.error(`[VAD-ERROR] ${msg}`, data || ''),
}

/**
 * VoiceChatSession - Component that handles VAD and WebSocket communication
 * Only mounts when voice chat is active to prevent premature mic access
 * 
 * Production-ready implementation with:
 * - Robust VAD initialization with error handling
 * - Proper microphone permissions handling
 * - Optimized audio streaming
 * - Detailed logging for all operations
 */
export default function VoiceChatSession({ 
  onTranscript, 
  onLLMToken, 
  onAudio, 
  onDone, 
  onError, 
  onStatusChange,
  onMicLevel,
  conversationId,
  profileId,
  enableThinking,
  tools,
  inputDeviceId,
  volume = 1.0,
}) {
  const wsRef = useRef(null)
  const audioContextRef = useRef(null)
  const nextPlayTimeRef = useRef(0)
  const gainNodeRef = useRef(null)
  const wsInitializedRef = useRef(false)
  
  // Initialize WebSocket connection
  const initWebSocket = useCallback(async () => {
    return new Promise((resolve, reject) => {
      try {
        log.info('=== WebSocket Initialization Starting ===')
        const ws = voiceAPI.createVoiceChatSocket()
        wsRef.current = ws
        
        const wsTimeout = setTimeout(() => {
          if (ws.readyState !== WebSocket.OPEN) {
            log.error('WebSocket connection timeout after 5 seconds')
            reject(new Error('WebSocket connection timeout'))
          }
        }, 5000)
        
        ws.onopen = () => {
          clearTimeout(wsTimeout)
          log.info('✅ WebSocket connected')
          log.debug('WebSocket ready state:', ws.readyState)
          
          // Send config immediately
          const configMsg = {
            type: 'config',
            enable_thinking: enableThinking,
            tools: tools || [],
            conversation_id: conversationId,
            profile_id: profileId,
          }
          
          log.debug('Sending config message:', JSON.stringify(configMsg, null, 2))
          ws.send(JSON.stringify(configMsg))
          log.info('✅ Config sent to backend')
          resolve()
        }
        
        ws.onmessage = async (event) => {
          try {
            if (typeof event.data === 'string') {
              const data = JSON.parse(event.data)
              log.debug('WebSocket message received:', data.type)
              
              switch (data.type) {
                case 'ready':
                  log.info('✅ Backend ready')
                  log.info('TTS sample rate:', data.tts_sample_rate)
                  onStatusChange('ready')
                  // Initialize audio context with correct sample rate
                  if (!audioContextRef.current) {
                    const AudioContextClass = window.AudioContext || window.webkitAudioContext
                    audioContextRef.current = new AudioContextClass({ 
                      sampleRate: data.tts_sample_rate || 24000 
                    })
                    nextPlayTimeRef.current = audioContextRef.current.currentTime
                    log.info('AudioContext created with sample rate:', audioContextRef.current.sampleRate)
                  }
                  break
                  
                case 'transcription':
                  log.info('Transcription received:', {
                    text: data.text,
                    final: data.final,
                    length: data.text?.length
                  })
                  onTranscript(data.text, data.final)
                  break
                  
                case 'llm_token':
                  log.debug('LLM token received:', data.token)
                  onLLMToken(data.token)
                  break
                  
                case 'audio':
                  log.debug('Audio chunk received, size:', data.data.length)
                  playAudio(data.data)
                  break
                  
                case 'done':
                  log.info('✅ Response complete')
                  onDone()
                  onStatusChange('ready')
                  break
                  
                case 'error':
                  log.error('Backend error message:', data.message)
                  onError(data.message)
                  break
                  
                default:
                  log.warn('Unknown message type:', data.type)
              }
            }
          } catch (error) {
            log.error('Message processing error:', error)
          }
        }
        
        ws.onerror = (error) => {
          log.error('WebSocket error:', error)
          onError('WebSocket connection error')
          reject(error)
        }
        
        ws.onclose = () => {
          log.info('WebSocket closed')
        }
      } catch (error) {
        log.error('WebSocket init error:', error)
        reject(error)
      }
    })
  }, [enableThinking, tools, conversationId, profileId, onStatusChange, onTranscript, onLLMToken, onError, onDone])

  useEffect(() => {
    if (wsInitializedRef.current) {
      log.debug('WebSocket already initialized, skipping')
      return
    }

    wsInitializedRef.current = true
    log.info('Initializing WebSocket on session start...')
    initWebSocket().catch((error) => {
      log.error('WebSocket initialization failed:', error)
    })
  }, [initWebSocket])
  
  // Play received audio
  const playAudio = useCallback((base64PCM16) => {
    try {
      log.debug('Playing audio chunk, base64 length:', base64PCM16.length)
      
      if (!audioContextRef.current) {
        log.warn('AudioContext not ready, skipping audio playback')
        return
      }
      
      // Decode base64 PCM16
      log.debug('Decoding base64 audio...')
      const pcmData = atob(base64PCM16)
      log.debug('Decoded PCM data length:', pcmData.length)
      
      const pcm16 = new Int16Array(pcmData.length / 2)
      for (let i = 0; i < pcm16.length; i++) {
        pcm16[i] = (pcmData.charCodeAt(i * 2) | (pcmData.charCodeAt(i * 2 + 1) << 8))
      }
      log.debug('PCM16 samples:', pcm16.length)
      
      // Convert to Float32
      const float32 = new Float32Array(pcm16.length)
      for (let i = 0; i < pcm16.length; i++) {
        float32[i] = pcm16[i] / 32768
      }
      log.debug('Float32 converted, range:', [float32[0], float32[Math.floor(float32.length/2)], float32[float32.length-1]])
      
      // Create and play audio buffer
      onStatusChange('speaking')
      const buffer = audioContextRef.current.createBuffer(1, float32.length, audioContextRef.current.sampleRate)
      buffer.copyToChannel(float32, 0)
      log.debug('Audio buffer created, duration:', buffer.duration, 's')
      
      const source = audioContextRef.current.createBufferSource()
      source.buffer = buffer
      
      // Create gain node for volume control
      if (!gainNodeRef.current) {
        gainNodeRef.current = audioContextRef.current.createGain()
        gainNodeRef.current.connect(audioContextRef.current.destination)
        log.debug('Gain node created and connected')
      }
      
      const vol = Math.max(0, Math.min(1, volume))
      gainNodeRef.current.gain.value = vol
      log.debug('Volume set to:', vol)
      
      source.connect(gainNodeRef.current)
      
      // Schedule playback
      const startTime = Math.max(audioContextRef.current.currentTime, nextPlayTimeRef.current)
      source.start(startTime)
      nextPlayTimeRef.current = startTime + buffer.duration
      log.info('✅ Audio playback started at:', startTime)
    } catch (error) {
      log.error('Audio playback error:', error)
    }
  }, [volume, onStatusChange])
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      log.info('=== VoiceChatSession cleanup ===')
      
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        log.info('Closing WebSocket')
        wsRef.current.close()
      }
      
      if (audioContextRef.current) {
        try {
          log.info('Closing AudioContext')
          audioContextRef.current.close()
        } catch (e) {
          log.warn('Error closing AudioContext:', e)
        }
      }
      
      log.info('=== Cleanup complete ===')
    }
  }, [])
  
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2 text-xs text-green-400">
        <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
        <span>✅ Voice session active - waiting for voice detection</span>
      </div>
      <VADInitializer 
        wsRef={wsRef}
        onStatusChange={onStatusChange}
        onError={onError}
        onMicLevel={onMicLevel}
        inputDeviceId={inputDeviceId}
      />
    </div>
  )
}

/**
 * VADInitializer - Separate component to properly use the useMicVAD hook
 * Handles Voice Activity Detection initialization and speech callbacks
 */
function VADInitializer({ wsRef, onStatusChange, onError, onMicLevel, inputDeviceId }) {
  const vadRef = useRef(null)
  const onStatusChangeRef = useRef(onStatusChange)
  const onErrorRef = useRef(onError)
  const onMicLevelRef = useRef(onMicLevel)
  const lastMicUpdateRef = useRef(0)

  useEffect(() => {
    onStatusChangeRef.current = onStatusChange
  }, [onStatusChange])

  useEffect(() => {
    onErrorRef.current = onError
  }, [onError])

  useEffect(() => {
    onMicLevelRef.current = onMicLevel
  }, [onMicLevel])
  
  // Configure VAD callbacks - these are stable
  const handleSpeechStart = useCallback(() => {
    vadLog.info('🎤 Speech detected - listening')
    onStatusChangeRef.current?.('listening')
  }, [])
  
  const handleSpeechEnd = useCallback(async (audio) => {
    vadLog.info('Speech ended', {
      audioSamples: audio.length,
      audioDuration_ms: Math.round(audio.length / 16),
    })
    
    if (!wsRef.current) {
      vadLog.error('WebSocket ref not available')
      return
    }
    
    if (wsRef.current.readyState !== WebSocket.OPEN) {
      vadLog.warn('WebSocket not open, state:', wsRef.current.readyState)
      onErrorRef.current?.('WebSocket not connected')
      return
    }
    
    try {
      onStatusChangeRef.current?.('processing')
      vadLog.debug('Converting Float32 audio to PCM16...')
      
      // Convert Float32Array to PCM16 with proper scaling
      const pcm16 = new Int16Array(audio.length)
      let min = 0, max = 0
      
      for (let i = 0; i < audio.length; i++) {
        const s = Math.max(-1, Math.min(1, audio[i]))
        const sample = s < 0 ? s * 0x8000 : s * 0x7FFF
        pcm16[i] = sample
        if (sample < min) min = sample
        if (sample > max) max = sample
      }
      
      vadLog.debug('PCM16 range:', { min, max, samples: pcm16.length })
      
      // Send audio as binary
      vadLog.info('Sending audio to backend', {
        bytes: pcm16.byteLength,
        samples: pcm16.length
      })
      wsRef.current.send(pcm16.buffer)
      
      // Signal end of speech
      vadLog.debug('Sending end_speech signal')
      wsRef.current.send(JSON.stringify({ type: 'end_speech' }))
      vadLog.info('✅ Audio sent successfully')
    } catch (error) {
      vadLog.error('Error sending audio:', error)
      onErrorRef.current?.('Failed to send audio: ' + error.message)
    }
  }, [wsRef])
  
  const handleVADMisfire = useCallback(() => {
    vadLog.debug('False positive - audio too short')
  }, [])

  const handleFrameProcessed = useCallback((_, frame) => {
    if (!frame?.length) return
    let sum = 0
    for (let i = 0; i < frame.length; i++) {
      const s = frame[i]
      sum += s * s
    }
    const rms = Math.sqrt(sum / frame.length)
    const now = performance.now()
    if (now - lastMicUpdateRef.current < 60) return
    lastMicUpdateRef.current = now
    onMicLevelRef.current?.(rms)
  }, [])

  const getStream = useCallback(async () => {
    vadLog.info('Requesting microphone stream for VAD...')
    const constraints = {
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        ...(inputDeviceId ? { deviceId: { ideal: inputDeviceId } } : {}),
      },
    }
    vadLog.debug('VAD getStream constraints:', constraints)
    const stream = await navigator.mediaDevices.getUserMedia(constraints)
    const track = stream.getAudioTracks()[0]
    if (track) {
      vadLog.info('VAD stream track settings:', track.getSettings())
    }
    return stream
  }, [inputDeviceId])
  
  // Initialize VAD with stable callbacks
  const vad = useMicVAD({
    startOnLoad: true, // Start immediately to avoid lifecycle issues
    getStream,
    baseAssetPath: 'https://cdn.jsdelivr.net/npm/@ricky0123/vad-web@0.0.29/dist/',
    onnxWASMBasePath: 'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.22.0/dist/',
    onSpeechStart: handleSpeechStart,
    onSpeechEnd: handleSpeechEnd,
    onVADMisfire: handleVADMisfire,
    onFrameProcessed: handleFrameProcessed,
    // Sensitivity thresholds - start with sane defaults
    positiveSpeechThreshold: 0.3,
    negativeSpeechThreshold: 0.25,
    redemptionMs: 1400,
    preSpeechPadMs: 800,
    minSpeechMs: 400,
  })
  
  vadRef.current = vad
  
  useEffect(() => {
    vadLog.debug('VAD instance configured:', {
      positiveSpeechThreshold: 0.3,
      negativeSpeechThreshold: 0.25,
      redemptionMs: 1400,
      preSpeechPadMs: 800,
      minSpeechMs: 400,
      baseAssetPath: 'https://cdn.jsdelivr.net/npm/@ricky0123/vad-web@0.0.29/dist/',
      onnxWASMBasePath: 'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.22.0/dist/',
    })
  }, [])
  
  useEffect(() => {
    vadRef.current = vad
  }, [vad])

  useEffect(() => {
    if (!vad) return
    vadLog.info('VAD instance available, checking status...')
    vadLog.debug('VAD state:', {
      loading: vad.loading,
      errored: vad.errored,
      listening: vad.listening,
      userSpeaking: vad.userSpeaking,
    })

    if (vad.errored) {
      vadLog.error('VAD errored:', vad.errored)
      onErrorRef.current?.(`VAD error: ${vad.errored.message || String(vad.errored)}`)
    }
  }, [vad?.errored, vad?.loading, vad?.listening, vad?.userSpeaking])

  useEffect(() => {
    return () => {
      const v = vadRef.current
      if (v?.listening) {
        try {
          vadLog.info('Stopping VAD listening')
          v.pause()
          vadLog.info('✅ VAD paused')
        } catch (error) {
          vadLog.error('Error stopping VAD:', error)
        }
      }
    }
  }, [])
  
  if (vad?.loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-yellow-400">
        <div className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
        <span>🔄 Loading voice detection...</span>
      </div>
    )
  }

  if (vad?.errored) {
    return (
      <div className="flex flex-col items-center gap-2 p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
        <div className="text-xs text-red-400">
          <strong>VAD Error:</strong>
          <p className="mt-1">{vad.errored?.message || String(vad.errored)}</p>
        </div>
        <p className="text-[10px] text-red-400/70">
          Voice detection failed to load. Check console for asset loading errors.
        </p>
      </div>
    )
  }

  if (!vad?.listening) {
    return (
      <div className="flex items-center gap-2 text-xs text-yellow-400">
        <div className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
        <span>🔄 Starting voice detection...</span>
      </div>
    )
  }
  
  return (
    <div className="flex items-center gap-2 text-xs text-blue-400">
      <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
      <span>✅ Voice detection active - speak now</span>
    </div>
  )
}
