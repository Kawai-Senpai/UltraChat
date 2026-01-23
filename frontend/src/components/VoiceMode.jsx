import { useState, useRef, useEffect, useCallback } from 'react'
import { useToast } from '../contexts/ToastContext'
import { voiceAPI } from '../lib/api'
import { useMicVAD, utils as vadUtils } from '@ricky0123/vad-react'
import { 
  Mic, MicOff, Volume2, VolumeX, Phone, PhoneOff, 
  Loader2, Settings2, Upload, Trash2, Check, X,
  Pause, Play, AlertCircle
} from 'lucide-react'

/**
 * VoiceMode - Real-time voice chat with TTS and STT
 * 
 * Props:
 * - isActive: boolean - whether voice mode is active
 * - onClose: () => void - callback when voice mode is closed
 * - conversationId: string - current conversation ID
 * - profileId: string - current profile ID
 * - enableThinking: boolean - whether thinking is enabled
 * - tools: string[] - enabled tools
 */
export default function VoiceMode({ 
  isActive, 
  onClose, 
  conversationId, 
  profileId,
  enableThinking = false,
  tools = []
}) {
  const { toast } = useToast()
  
  // Status
  const [status, setStatus] = useState('initializing') // initializing, ready, listening, processing, speaking, error
  const [voiceStatus, setVoiceStatus] = useState(null)
  const [errorMessage, setErrorMessage] = useState('')
  
  // Audio state
  const [isListening, setIsListening] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const [volume, setVolume] = useState(1.0)
  
  // Transcription
  const [partialTranscript, setPartialTranscript] = useState('')
  const [finalTranscript, setFinalTranscript] = useState('')
  
  // LLM response
  const [llmResponse, setLlmResponse] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  
  // Settings panel
  const [showSettings, setShowSettings] = useState(false)
  const [voices, setVoices] = useState([])
  const [activeVoice, setActiveVoice] = useState(null)
  const [uploadingVoice, setUploadingVoice] = useState(false)
  
  // Refs
  const wsRef = useRef(null)
  const audioContextRef = useRef(null)
  const nextPlayTimeRef = useRef(0)
  const vadActiveRef = useRef(false)
  
  // VAD Hook - handles microphone and voice activity detection
  const vad = useMicVAD({
    startOnLoad: false,
    onSpeechStart: () => {
      console.log('[VAD] Speech started')
      if (status === 'ready' || status === 'listening') {
        setStatus('listening')
        setIsListening(true)
      }
    },
    onSpeechEnd: async (audio) => {
      console.log('[VAD] Speech ended, audio length:', audio.length)
      setIsListening(false)
      
      // Convert Float32Array to PCM16 and send to backend
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        const pcm16 = new Int16Array(audio.length)
        for (let i = 0; i < audio.length; i++) {
          pcm16[i] = Math.max(-32768, Math.min(32767, Math.floor(audio[i] * 32768)))
        }
        
        // Send audio as binary
        wsRef.current.send(pcm16.buffer)
        
        // Signal end of speech
        wsRef.current.send(JSON.stringify({ type: 'speech_end' }))
        setStatus('processing')
      }
    },
    onVADMisfire: () => {
      console.log('[VAD] Misfire (too short)')
    },
    positiveSpeechThreshold: 0.6,
    negativeSpeechThreshold: 0.35,
    redemptionFrames: 8,
    frameSamples: 1536,
    preSpeechPadFrames: 10,
    minSpeechFrames: 4,
  })
  
  // Load voice status on mount
  useEffect(() => {
    if (isActive) {
      loadVoiceStatus()
      loadVoices()
    }
  }, [isActive])
  
  // Cleanup on unmount or deactivate
  useEffect(() => {
    if (!isActive) {
      cleanup()
    }
    return () => cleanup()
  }, [isActive])
  
  const loadVoiceStatus = async () => {
    try {
      const status = await voiceAPI.getStatus()
      setVoiceStatus(status)
      
      if (!status.tts_loaded || !status.stt_loaded) {
        setStatus('needs_setup')
      } else {
        setStatus('ready')
      }
    } catch (error) {
      setStatus('error')
      setErrorMessage('Failed to load voice status')
    }
  }
  
  const loadVoices = async () => {
    try {
      const result = await voiceAPI.listVoices()
      setVoices(result.voices || [])
    } catch (error) {
      console.error('Failed to load voices:', error)
    }
  }
  
  const loadTTS = async () => {
    setStatus('initializing')
    try {
      await voiceAPI.loadTTS('auto')
      toast.success('TTS loaded')
      await loadVoiceStatus()
    } catch (error) {
      toast.error('Failed to load TTS: ' + error.message)
      setStatus('error')
      setErrorMessage(error.message)
    }
  }
  
  const loadSTT = async () => {
    setStatus('initializing')
    try {
      await voiceAPI.loadSTT()
      toast.success('STT loaded')
      await loadVoiceStatus()
    } catch (error) {
      toast.error('Failed to load STT: ' + error.message)
      setStatus('error')
      setErrorMessage(error.message)
    }
  }
  
  const cleanup = () => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    // Stop VAD if running
    if (vad.listening) {
      vad.pause()
    }
    if (audioContextRef.current) {
      audioContextRef.current.close()
      audioContextRef.current = null
    }
    setIsListening(false)
    setPartialTranscript('')
    setFinalTranscript('')
    setLlmResponse('')
  }
  
  const startVoiceChat = async () => {
    try {
      setStatus('connecting')
      
      // Create WebSocket connection
      const ws = voiceAPI.createVoiceChatSocket()
      wsRef.current = ws
      
      ws.onopen = () => {
        // Send config
        ws.send(JSON.stringify({
          type: 'config',
          enable_thinking: enableThinking,
          tools: tools,
          conversation_id: conversationId,
          profile_id: profileId,
        }))
      }
      
      ws.onmessage = async (event) => {
        if (typeof event.data === 'string') {
          const data = JSON.parse(event.data)
          
          switch (data.type) {
            case 'ready':
              setStatus('ready')
              // Initialize audio context with correct sample rate
              audioContextRef.current = new AudioContext({ sampleRate: data.tts_sample_rate || 24000 })
              nextPlayTimeRef.current = audioContextRef.current.currentTime
              // Start VAD-based listening
              vad.start()
              setStatus('listening')
              break
              
            case 'transcription':
              if (data.final) {
                setFinalTranscript(data.text)
                setPartialTranscript('')
              } else {
                setPartialTranscript(data.text)
              }
              break
              
            case 'llm_token':
              setIsGenerating(true)
              setStatus('processing')
              setLlmResponse(prev => prev + data.token)
              break
              
            case 'audio':
              if (!isMuted) {
                // Decode base64 PCM16 and play
                const pcm16 = Uint8Array.from(atob(data.data), c => c.charCodeAt(0))
                await playAudioChunk(new Int16Array(pcm16.buffer))
              }
              setStatus('speaking')
              break
              
            case 'done':
              setIsGenerating(false)
              setStatus('ready')
              setLlmResponse('')
              setFinalTranscript('')
              break
              
            case 'error':
              toast.error(data.message)
              setStatus('error')
              setErrorMessage(data.message)
              break
          }
        }
      }
      
      ws.onerror = () => {
        setStatus('error')
        setErrorMessage('WebSocket connection failed')
      }
      
      ws.onclose = () => {
        if (status !== 'error') {
          setStatus('ready')
        }
        setIsListening(false)
      }
      
    } catch (error) {
      toast.error('Failed to start voice chat: ' + error.message)
      setStatus('error')
      setErrorMessage(error.message)
    }
  }
  
  const stopVoiceChat = () => {
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ type: 'stop' }))
    }
    cleanup()
    setStatus('ready')
  }
  
  // VAD-controlled listening - toggle VAD on/off for push-to-talk mode
  const toggleListening = () => {
    if (vad.listening) {
      vad.pause()
      setIsListening(false)
    } else {
      vad.start()
      setIsListening(true)
      setStatus('listening')
    }
  }
  
  const playAudioChunk = async (pcm16) => {
    if (!audioContextRef.current) return
    
    const ctx = audioContextRef.current
    const floats = new Float32Array(pcm16.length)
    for (let i = 0; i < pcm16.length; i++) {
      floats[i] = pcm16[i] / 32768
    }
    
    const buffer = ctx.createBuffer(1, floats.length, ctx.sampleRate)
    buffer.copyToChannel(floats, 0)
    
    const source = ctx.createBufferSource()
    source.buffer = buffer
    
    // Apply volume
    const gainNode = ctx.createGain()
    gainNode.gain.value = volume
    source.connect(gainNode)
    gainNode.connect(ctx.destination)
    
    // Schedule playback
    if (nextPlayTimeRef.current < ctx.currentTime) {
      nextPlayTimeRef.current = ctx.currentTime
    }
    source.start(nextPlayTimeRef.current)
    nextPlayTimeRef.current += buffer.duration
  }
  
  const handleVoiceUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    
    const name = prompt('Enter a name for this voice:')
    if (!name) return
    
    setUploadingVoice(true)
    try {
      await voiceAPI.uploadVoice(name, file)
      toast.success('Voice uploaded')
      await loadVoices()
    } catch (error) {
      toast.error('Upload failed: ' + error.message)
    } finally {
      setUploadingVoice(false)
    }
  }
  
  const handleSetVoice = async (voiceName) => {
    try {
      await voiceAPI.setActiveVoice(voiceName)
      setActiveVoice(voiceName)
      toast.success(`Voice set to ${voiceName}`)
    } catch (error) {
      toast.error('Failed to set voice: ' + error.message)
    }
  }
  
  const handleDeleteVoice = async (voiceName) => {
    if (!confirm(`Delete voice "${voiceName}"?`)) return
    
    try {
      await voiceAPI.deleteVoice(voiceName)
      toast.success('Voice deleted')
      await loadVoices()
      if (activeVoice === voiceName) {
        setActiveVoice(null)
      }
    } catch (error) {
      toast.error('Delete failed: ' + error.message)
    }
  }
  
  if (!isActive) return null
  
  return (
    <div className="fixed inset-0 bg-zinc-950/95 z-50 flex flex-col items-center justify-center">
      {/* Close button */}
      <button
        onClick={onClose}
        className="absolute top-4 right-4 p-2 text-zinc-400 hover:text-white transition-colors"
      >
        <X className="w-6 h-6" />
      </button>
      
      {/* Settings button */}
      <button
        onClick={() => setShowSettings(!showSettings)}
        className="absolute top-4 left-4 p-2 text-zinc-400 hover:text-white transition-colors"
      >
        <Settings2 className="w-6 h-6" />
      </button>
      
      {/* Status indicator */}
      <div className="absolute top-4 left-1/2 -translate-x-1/2 flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${
          status === 'listening' ? 'bg-green-500 animate-pulse' :
          status === 'processing' ? 'bg-yellow-500 animate-pulse' :
          status === 'speaking' ? 'bg-blue-500 animate-pulse' :
          status === 'error' ? 'bg-red-500' :
          status === 'ready' ? 'bg-green-500' :
          'bg-zinc-500'
        }`} />
        <span className="text-xs text-zinc-400 capitalize">{status}</span>
      </div>
      
      {/* Main content */}
      <div className="flex flex-col items-center gap-8 max-w-2xl w-full px-4">
        
        {/* Setup required */}
        {status === 'needs_setup' && (
          <div className="text-center space-y-4">
            <AlertCircle className="w-12 h-12 text-yellow-500 mx-auto" />
            <h2 className="text-xl font-medium text-white">Voice Setup Required</h2>
            <p className="text-zinc-400 text-sm">
              Load TTS and STT models to enable voice chat
            </p>
            <div className="flex gap-3 justify-center">
              {!voiceStatus?.tts_loaded && (
                <button
                  onClick={loadTTS}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm transition-colors"
                >
                  Load TTS
                </button>
              )}
              {!voiceStatus?.stt_loaded && (
                <button
                  onClick={loadSTT}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm transition-colors"
                >
                  Load STT
                </button>
              )}
            </div>
          </div>
        )}
        
        {/* Initializing */}
        {status === 'initializing' && (
          <div className="text-center space-y-4">
            <Loader2 className="w-12 h-12 text-blue-500 mx-auto animate-spin" />
            <p className="text-zinc-400">Loading voice models...</p>
          </div>
        )}
        
        {/* Error */}
        {status === 'error' && (
          <div className="text-center space-y-4">
            <AlertCircle className="w-12 h-12 text-red-500 mx-auto" />
            <p className="text-red-400">{errorMessage}</p>
            <button
              onClick={() => loadVoiceStatus()}
              className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg text-sm"
            >
              Retry
            </button>
          </div>
        )}
        
        {/* Ready / Active states */}
        {['ready', 'listening', 'processing', 'speaking', 'connecting'].includes(status) && (
          <>
            {/* Visualization area */}
            <div className="w-48 h-48 rounded-full bg-zinc-900 border-2 border-zinc-800 flex items-center justify-center relative">
              {status === 'listening' && (
                <div className="absolute inset-0 rounded-full border-4 border-green-500/30 animate-ping" />
              )}
              {status === 'speaking' && (
                <div className="absolute inset-0 rounded-full border-4 border-blue-500/30 animate-pulse" />
              )}
              
              <div className={`w-32 h-32 rounded-full flex items-center justify-center ${
                status === 'listening' ? 'bg-green-500/20' :
                status === 'speaking' ? 'bg-blue-500/20' :
                status === 'processing' ? 'bg-yellow-500/20' :
                'bg-zinc-800'
              }`}>
                {status === 'listening' ? (
                  <Mic className="w-12 h-12 text-green-500" />
                ) : status === 'speaking' ? (
                  <Volume2 className="w-12 h-12 text-blue-500" />
                ) : status === 'processing' ? (
                  <Loader2 className="w-12 h-12 text-yellow-500 animate-spin" />
                ) : (
                  <Phone className="w-12 h-12 text-zinc-500" />
                )}
              </div>
            </div>
            
            {/* Transcript display */}
            <div className="w-full min-h-[60px] text-center">
              {partialTranscript && (
                <p className="text-zinc-500 italic">{partialTranscript}</p>
              )}
              {finalTranscript && (
                <p className="text-white">{finalTranscript}</p>
              )}
              {llmResponse && (
                <p className="text-blue-400 mt-2">{llmResponse}</p>
              )}
            </div>
            
            {/* Controls */}
            <div className="flex items-center gap-4">
              {/* Mute button */}
              <button
                onClick={() => setIsMuted(!isMuted)}
                className={`p-3 rounded-full transition-colors ${
                  isMuted ? 'bg-red-500/20 text-red-500' : 'bg-zinc-800 text-zinc-400 hover:text-white'
                }`}
              >
                {isMuted ? <VolumeX className="w-6 h-6" /> : <Volume2 className="w-6 h-6" />}
              </button>
              
              {/* Main call button */}
              {status === 'ready' ? (
                <button
                  onClick={startVoiceChat}
                  className="p-6 rounded-full bg-green-600 hover:bg-green-500 text-white transition-colors"
                >
                  <Phone className="w-8 h-8" />
                </button>
              ) : (
                <button
                  onClick={stopVoiceChat}
                  className="p-6 rounded-full bg-red-600 hover:bg-red-500 text-white transition-colors"
                >
                  <PhoneOff className="w-8 h-8" />
                </button>
              )}
              
              {/* Toggle VAD listening */}
              <button
                onClick={toggleListening}
                className={`p-3 rounded-full transition-colors ${
                  vad.listening ? 'bg-green-500/20 text-green-500' : 'bg-zinc-800 text-zinc-400 hover:text-white'
                }`}
                title={vad.listening ? 'Mute microphone' : 'Unmute microphone'}
              >
                {vad.listening ? <Mic className="w-6 h-6" /> : <MicOff className="w-6 h-6" />}
              </button>
            </div>
            
            {/* VAD status indicator */}
            {vad.loading && (
              <p className="text-xs text-zinc-500 mt-2">Loading voice detection...</p>
            )}
            {vad.errored && (
              <p className="text-xs text-red-400 mt-2">VAD error: microphone access denied</p>
            )}
          </>
        )}
      </div>
      
      {/* Settings panel */}
      {showSettings && (
        <div className="absolute right-0 top-0 bottom-0 w-80 bg-zinc-900 border-l border-zinc-800 p-4 overflow-y-auto">
          <h3 className="text-lg font-medium text-white mb-4">Voice Settings</h3>
          
          {/* Volume slider */}
          <div className="mb-6">
            <label className="text-xs text-zinc-400 mb-2 block">Volume</label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={volume}
              onChange={(e) => setVolume(parseFloat(e.target.value))}
              className="w-full"
            />
          </div>
          
          {/* Voice selection */}
          <div className="mb-6">
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs text-zinc-400">Voice Cloning</label>
              <label className="cursor-pointer">
                <input
                  type="file"
                  accept=".wav,.mp3,.flac,.ogg"
                  onChange={handleVoiceUpload}
                  className="hidden"
                />
                <span className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1">
                  <Upload className="w-3 h-3" />
                  Upload
                </span>
              </label>
            </div>
            
            {uploadingVoice && (
              <div className="flex items-center gap-2 text-xs text-zinc-400 mb-2">
                <Loader2 className="w-3 h-3 animate-spin" />
                Uploading...
              </div>
            )}
            
            <div className="space-y-1">
              {/* Default voice option */}
              <button
                onClick={() => {
                  voiceAPI.clearActiveVoice()
                  setActiveVoice(null)
                }}
                className={`w-full flex items-center justify-between px-3 py-2 rounded text-sm ${
                  !activeVoice ? 'bg-blue-500/20 text-blue-400' : 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700'
                }`}
              >
                <span>Default Voice</span>
                {!activeVoice && <Check className="w-4 h-4" />}
              </button>
              
              {/* Custom voices */}
              {voices.map(voice => (
                <div
                  key={voice.name}
                  className={`flex items-center justify-between px-3 py-2 rounded text-sm ${
                    activeVoice === voice.name ? 'bg-blue-500/20 text-blue-400' : 'bg-zinc-800 text-zinc-300'
                  }`}
                >
                  <button
                    onClick={() => handleSetVoice(voice.name)}
                    className="flex-1 text-left"
                  >
                    {voice.name}
                  </button>
                  <div className="flex items-center gap-1">
                    {activeVoice === voice.name && <Check className="w-4 h-4" />}
                    <button
                      onClick={() => handleDeleteVoice(voice.name)}
                      className="p-1 text-zinc-500 hover:text-red-400"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
          
          {/* Model status */}
          <div className="mb-6">
            <label className="text-xs text-zinc-400 mb-2 block">Model Status</label>
            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-zinc-500">TTS</span>
                <span className={voiceStatus?.tts_loaded ? 'text-green-400' : 'text-zinc-500'}>
                  {voiceStatus?.tts_loaded ? `Loaded (${voiceStatus.tts_device})` : 'Not loaded'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-zinc-500">STT</span>
                <span className={voiceStatus?.stt_loaded ? 'text-green-400' : 'text-zinc-500'}>
                  {voiceStatus?.stt_loaded ? 'Loaded' : 'Not loaded'}
                </span>
              </div>
            </div>
          </div>
          
          {/* Load/unload buttons */}
          <div className="space-y-2">
            {!voiceStatus?.tts_loaded ? (
              <button
                onClick={loadTTS}
                className="w-full px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded text-sm"
              >
                Load TTS
              </button>
            ) : (
              <button
                onClick={() => voiceAPI.unloadTTS().then(loadVoiceStatus)}
                className="w-full px-3 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded text-sm"
              >
                Unload TTS
              </button>
            )}
            
            {!voiceStatus?.stt_loaded ? (
              <button
                onClick={loadSTT}
                className="w-full px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded text-sm"
              >
                Load STT
              </button>
            ) : (
              <button
                onClick={() => voiceAPI.unloadSTT().then(loadVoiceStatus)}
                className="w-full px-3 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded text-sm"
              >
                Unload STT
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
