import { useState, useRef, useEffect, useCallback } from 'react'
import { useToast } from '../contexts/ToastContext'
import { voiceAPI } from '../lib/api'
import VoiceChatSession from './VoiceChatSession'
import { 
  Mic, MicOff, Volume2, VolumeX, Phone, PhoneOff, 
  Loader2, Settings2, Upload, Trash2, Check, X,
  Pause, Play, AlertCircle, Download
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
  const [voiceChatActive, setVoiceChatActive] = useState(false)
  
  // Audio state
  const [isListening, setIsListening] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const [volume, setVolume] = useState(1.0)
  const [micLevel, setMicLevel] = useState(0)
  
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
  
  // Audio devices
  const [audioDevices, setAudioDevices] = useState({ inputs: [], outputs: [] })
  const [selectedInputDevice, setSelectedInputDevice] = useState('')
  const [selectedOutputDevice, setSelectedOutputDevice] = useState('')
  
  // Load voice status on mount
  useEffect(() => {
    if (isActive) {
      loadVoiceStatus()
      loadVoices()
      loadAudioDevices()
    }
  }, [isActive])
  
  // Load available audio devices
  const loadAudioDevices = async () => {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices()
      const inputs = devices.filter(d => d.kind === 'audioinput')
      const outputs = devices.filter(d => d.kind === 'audiooutput')
      setAudioDevices({ inputs, outputs })
      
      // Set defaults if not selected
      if (!selectedInputDevice && inputs.length > 0) {
        setSelectedInputDevice(inputs[0].deviceId)
      }
      if (!selectedOutputDevice && outputs.length > 0) {
        setSelectedOutputDevice(outputs[0].deviceId)
      }
    } catch (error) {
      console.error('Failed to enumerate audio devices:', error)
    }
  }
  
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
        // Auto-load TTS and STT
        setStatus('initializing')
        await autoLoadVoiceModels(status)
      } else {
        setStatus('ready')
      }
    } catch (error) {
      setStatus('error')
      setErrorMessage('Failed to load voice status')
    }
  }
  
  const autoLoadVoiceModels = async (currentStatus) => {
    try {
      // Load TTS if not loaded
      if (!currentStatus?.tts_loaded) {
        toast.info('Loading TTS model...')
        try {
          await voiceAPI.loadTTS()  // Will use default 'alba' voice
          toast.success('TTS loaded')
        } catch (err) {
          console.error('TTS load failed:', err)
          toast.error('TTS failed to load: ' + err.message)
        }
      }
      
      // Load STT if not loaded (will auto-download small English model if needed)
      if (!currentStatus?.stt_loaded) {
        // First check if any STT model is installed
        const sttModels = await voiceAPI.listSTTModels()
        
        if (!sttModels.models?.length) {
          // No models installed - download small English model
          toast.info('Downloading STT model (first time setup)...')
          try {
            for await (const event of voiceAPI.downloadSTTModel('vosk-model-small-en-us-0.15', {})) {
              if (event.type === 'done') {
                toast.success('STT model downloaded')
                break
              } else if (event.type === 'error') {
                toast.error('STT download failed: ' + event.message)
                break
              }
            }
          } catch (err) {
            console.error('STT download failed:', err)
            toast.error('Failed to download STT model')
          }
        }
        
        // Now try to load STT
        toast.info('Loading STT model...')
        try {
          await voiceAPI.loadSTT()
          toast.success('STT loaded')
        } catch (err) {
          console.error('STT load failed:', err)
          toast.error('STT failed to load: ' + err.message)
        }
      }
      
      // Re-check status
      const newStatus = await voiceAPI.getStatus()
      setVoiceStatus(newStatus)
      
      if (newStatus.tts_loaded && newStatus.stt_loaded) {
        setStatus('ready')
      } else {
        setStatus('needs_setup')
      }
    } catch (error) {
      console.error('Auto-load failed:', error)
      setStatus('error')
      setErrorMessage('Failed to initialize voice: ' + error.message)
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
      await voiceAPI.loadTTS()
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
    setVoiceChatActive(false)
    setIsListening(false)
    setPartialTranscript('')
    setFinalTranscript('')
    setLlmResponse('')
    setMicLevel(0)
  }
  
  const startVoiceChat = async () => {
    try {
      // Request microphone permission first
      try {
        const s = await navigator.mediaDevices.getUserMedia({ audio: true })
        s.getTracks().forEach(t => t.stop())
      } catch (err) {
        console.error('Microphone permission denied:', err)
        toast.error('Microphone access denied. Please allow microphone access and try again.')
        setStatus('error')
        setErrorMessage('Microphone access denied')
        return
      }
      
      // Start the voice chat session (mounts the VoiceChatSession component)
      setVoiceChatActive(true)
      setStatus('connecting')
    } catch (error) {
      toast.error('Failed to start voice chat: ' + error.message)
      setStatus('error')
      setErrorMessage(error.message)
    }
  }
  
  const stopVoiceChat = () => {
    setVoiceChatActive(false)
    cleanup()
    setStatus('ready')
  }
  
  // Callback handlers for VoiceChatSession
  const handleTranscript = (text, isFinal) => {
    if (isFinal) {
      setFinalTranscript(text)
      setPartialTranscript('')
    } else {
      setPartialTranscript(text)
    }
  }
  
  const handleLLMToken = (token) => {
    setIsGenerating(true)
    setLlmResponse(prev => prev + token)
  }
  
  const handleAudio = () => {
    setStatus('speaking')
  }
  
  const handleDone = () => {
    setIsGenerating(false)
    setLlmResponse('')
    setFinalTranscript('')
  }
  
  const handleError = (message) => {
    toast.error(message)
    setStatus('error')
    setErrorMessage(message)
  }
  
  const handleStatusChange = (newStatus) => {
    setStatus(newStatus)
    if (newStatus === 'listening') {
      setIsListening(true)
    } else {
      setIsListening(false)
    }
  }
  
  // Voice management functions
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

  const micLevelPct = voiceChatActive
    ? Math.max(0, Math.min(100, Math.round(micLevel * 250)))
    : 0
  
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
            {/* Status message */}
            <div className="text-center mb-4">
              {!voiceChatActive && status === 'ready' && (
                <p className="text-zinc-400 text-sm">Click the green button to start voice chat</p>
              )}
              {voiceChatActive && status === 'ready' && (
                <p className="text-green-400 text-sm">🎤 Voice chat active - speak when ready</p>
              )}
              {status === 'listening' && (
                <p className="text-green-400 text-sm animate-pulse">🎙️ Listening... speak now</p>
              )}
              {status === 'processing' && (
                <p className="text-yellow-400 text-sm">⏳ Processing your speech...</p>
              )}
              {status === 'speaking' && (
                <p className="text-blue-400 text-sm">🔊 AI is speaking...</p>
              )}
              {status === 'connecting' && (
                <p className="text-zinc-400 text-sm">Connecting...</p>
              )}
            </div>
            
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
                voiceChatActive ? 'bg-green-500/10' :
                'bg-zinc-800'
              }`}>
                {status === 'listening' ? (
                  <Mic className="w-12 h-12 text-green-500" />
                ) : status === 'speaking' ? (
                  <Volume2 className="w-12 h-12 text-blue-500" />
                ) : status === 'processing' ? (
                  <Loader2 className="w-12 h-12 text-yellow-500 animate-spin" />
                ) : voiceChatActive ? (
                  <Mic className="w-12 h-12 text-green-400 animate-pulse" />
                ) : (
                  <Phone className="w-12 h-12 text-zinc-500" />
                )}
              </div>
            </div>
            
            {/* Transcript display */}
            <div className="w-full min-h-16 text-center px-4">
              {!voiceChatActive && !partialTranscript && !finalTranscript && !llmResponse && (
                <p className="text-zinc-600 text-xs">Transcripts will appear here</p>
              )}
              {partialTranscript && (
                <p className="text-zinc-500 italic text-sm">{partialTranscript}</p>
              )}
              {finalTranscript && (
                <p className="text-white text-sm">{finalTranscript}</p>
              )}
              {llmResponse && (
                <p className="text-blue-400 mt-2 text-sm">{llmResponse}</p>
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
              {!voiceChatActive ? (
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
              
              {/* Mic status indicator */}
              <div
                className={`p-3 rounded-full ${
                  isListening ? 'bg-green-500/20 text-green-500' : 'bg-zinc-800 text-zinc-400'
                }`}
              >
                {isListening ? <Mic className="w-6 h-6" /> : <MicOff className="w-6 h-6" />}
              </div>
            </div>
            
            {/* Voice chat session - mounts VAD only when active */}
            {voiceChatActive && (
              <VoiceChatSession
                onTranscript={handleTranscript}
                onLLMToken={handleLLMToken}
                onAudio={handleAudio}
                onDone={handleDone}
                onError={handleError}
                onStatusChange={handleStatusChange}
                onMicLevel={setMicLevel}
                conversationId={conversationId}
                profileId={profileId}
                enableThinking={enableThinking}
                tools={tools}
                inputDeviceId={selectedInputDevice}
                outputDeviceId={selectedOutputDevice}
                volume={volume}
              />
            )}
          </>
        )}
      </div>
      
      {/* Settings panel - Redesigned to match brand */}
      {showSettings && (
        <div className="absolute right-0 top-0 bottom-0 w-80 bg-neutral-950 border-l border-white/10 overflow-y-auto">
          {/* Header */}
          <div className="p-5 border-b border-white/10">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-black text-white">Voice Settings</h3>
              <button
                onClick={() => setShowSettings(false)}
                className="p-1.5 rounded-lg hover:bg-white/10 text-neutral-400 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
          
          <div className="p-5 space-y-6">
            {/* Mic Level Visualizer - Enhanced */}
            <div>
              <label className="text-xs font-bold text-white mb-3 block">Microphone Status</label>
              <div className="flex items-center gap-2">
                <Mic className="w-4 h-4 text-neutral-500" />
                <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden">
                  <div 
                    className={`h-full transition-all duration-100 ${
                      isListening ? 'bg-green-500' : voiceChatActive ? 'bg-blue-500/70' : 'bg-neutral-700'
                    }`}
                    style={{ 
                      width: `${micLevelPct}%`,
                      animation: isListening ? 'pulse 0.4s ease-in-out infinite' : 'none'
                    }}
                  />
                </div>
                <span className="text-[10px] text-neutral-500 w-20 text-right font-mono">
                  {isListening ? '🎤 Active' : voiceChatActive ? '🔄 Ready' : '⏸️ Off'}
                </span>
              </div>
              <p className="text-[10px] text-neutral-500 mt-2">
                {!voiceChatActive && 'Start voice chat to begin'}
                {voiceChatActive && !isListening && 'Listening for speech...'}
                {isListening && '✨ Speech detected - listening!'}
              </p>
            </div>
            
            {/* Input Device */}
            <div>
              <label className="text-xs font-bold text-white mb-3 block">Input Device</label>
              <select
                value={selectedInputDevice}
                onChange={(e) => setSelectedInputDevice(e.target.value)}
                className="w-full px-0 py-2 bg-transparent border-0 border-b border-white/20 
                         text-white text-xs focus:border-red-500 focus:outline-none transition-colors"
              >
                {audioDevices.inputs.map(device => (
                  <option key={device.deviceId} value={device.deviceId} className="bg-neutral-900">
                    {device.label || `Microphone ${device.deviceId.slice(0, 8)}`}
                  </option>
                ))}
              </select>
            </div>
            
            {/* Output Device */}
            <div>
              <label className="text-xs font-bold text-white mb-3 block">Output Device</label>
              <select
                value={selectedOutputDevice}
                onChange={(e) => setSelectedOutputDevice(e.target.value)}
                className="w-full px-0 py-2 bg-transparent border-0 border-b border-white/20 
                         text-white text-xs focus:border-red-500 focus:outline-none transition-colors"
              >
                {audioDevices.outputs.map(device => (
                  <option key={device.deviceId} value={device.deviceId} className="bg-neutral-900">
                    {device.label || `Speaker ${device.deviceId.slice(0, 8)}`}
                  </option>
                ))}
              </select>
            </div>
            
            {/* Volume Control */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <label className="text-xs font-bold text-white">Output Volume</label>
                <span className="text-xs text-red-400 font-mono">{Math.round(volume * 100)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={volume}
                onChange={(e) => setVolume(parseFloat(e.target.value))}
                className="w-full accent-red-500"
              />
            </div>
            
            {/* Divider */}
            <div className="border-t border-white/10" />
            
            {/* TTS Voice Selection */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <label className="text-xs font-bold text-white">TTS Voice</label>
                <label className="cursor-pointer text-[10px] text-red-400 hover:text-red-300 flex items-center gap-1">
                  <input
                    type="file"
                    accept=".wav,.mp3,.flac,.ogg"
                    onChange={handleVoiceUpload}
                    className="hidden"
                  />
                  <Upload className="w-3 h-3" />
                  Clone Voice
                </label>
              </div>
              
              {uploadingVoice && (
                <div className="flex items-center gap-2 text-[10px] text-neutral-400 mb-3">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Uploading voice sample...
                </div>
              )}
              
              <div className="space-y-1 max-h-32 overflow-y-auto">
                {/* Preset voices */}
                {['alba', 'marius', 'jean', 'fantine'].map(voiceName => (
                  <button
                    key={voiceName}
                    onClick={() => handleSetVoice(voiceName)}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs transition-colors ${
                      activeVoice === voiceName 
                        ? 'bg-red-500/20 text-red-400 border border-red-500/30' 
                        : 'bg-white/5 text-neutral-300 hover:bg-white/10 border border-transparent'
                    }`}
                  >
                    <span className="capitalize">{voiceName}</span>
                    {activeVoice === voiceName && <Check className="w-3 h-3" />}
                  </button>
                ))}
                
                {/* Custom voices */}
                {voices.filter(v => !['alba', 'marius', 'jean', 'fantine'].includes(v.name)).map(voice => (
                  <div
                    key={voice.name}
                    className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs ${
                      activeVoice === voice.name 
                        ? 'bg-red-500/20 text-red-400 border border-red-500/30' 
                        : 'bg-white/5 text-neutral-300 border border-transparent'
                    }`}
                  >
                    <button
                      onClick={() => handleSetVoice(voice.name)}
                      className="flex-1 text-left"
                    >
                      {voice.name}
                    </button>
                    <div className="flex items-center gap-1">
                      {activeVoice === voice.name && <Check className="w-3 h-3" />}
                      <button
                        onClick={() => handleDeleteVoice(voice.name)}
                        className="p-1 text-neutral-500 hover:text-red-400 transition-colors"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            
            {/* Divider */}
            <div className="border-t border-white/10" />
            
            {/* Model Status */}
            <div>
              <label className="text-xs font-bold text-white mb-3 block">Model Status</label>
              <div className="space-y-2">
                <div className="flex items-center justify-between p-3 bg-white/5 rounded-lg">
                  <div className="flex items-center gap-2">
                    <Volume2 className="w-4 h-4 text-neutral-500" />
                    <span className="text-xs text-neutral-300">TTS</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {voiceStatus?.tts_loaded ? (
                      <>
                        <span className="text-[10px] text-green-400">Loaded</span>
                        <div className="w-2 h-2 rounded-full bg-green-500" />
                      </>
                    ) : (
                      <>
                        <span className="text-[10px] text-neutral-500">Not loaded</span>
                        <div className="w-2 h-2 rounded-full bg-neutral-600" />
                      </>
                    )}
                  </div>
                </div>
                <div className="flex items-center justify-between p-3 bg-white/5 rounded-lg">
                  <div className="flex items-center gap-2">
                    <Mic className="w-4 h-4 text-neutral-500" />
                    <span className="text-xs text-neutral-300">STT</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {voiceStatus?.stt_loaded ? (
                      <>
                        <span className="text-[10px] text-green-400">Loaded</span>
                        <div className="w-2 h-2 rounded-full bg-green-500" />
                      </>
                    ) : (
                      <>
                        <span className="text-[10px] text-neutral-500">Not loaded</span>
                        <div className="w-2 h-2 rounded-full bg-neutral-600" />
                      </>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
