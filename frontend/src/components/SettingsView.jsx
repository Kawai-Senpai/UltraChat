import { useState, useEffect } from 'react'
import { useToast } from '../contexts/ToastContext'
import { settingsAPI, modelsAPI, voiceAPI } from '../lib/api'
import { useApp } from '../contexts/AppContext'
import { 
  ArrowLeft, Save, RotateCcw, Settings, Sliders, Monitor, 
  Database, Info, Box, Thermometer, FileText, User, Zap,
  Mic, Volume2, Upload, Trash2, Check, Download
} from 'lucide-react'

export default function SettingsView({ onBack }) {
  const { toast } = useToast()
  const { localModels, loadLocalModels, currentProfile } = useApp()
  
  const [settings, setSettings] = useState({
    model: { default_model: '', use_torch_compile: false },
    chat_defaults: {
      temperature: 0.7,
      max_tokens: 2048,
      context_length: 4096,
    },
    ui: {
      stream_enabled: true,
      show_timestamps: true,
      compact_mode: false,
      tool_thinking: true,
    },
    voice: {
      tts_enabled: true,
      stt_enabled: true,
      tts_device: 'auto',
      tts_voice: '',  // Voice ID for TTS
      vad_aggressiveness: 2,
      chunk_max_words: 16,
      chunk_max_wait_s: 0.7,
      auto_load_tts: false,
    },
    speculative_decoding: {
      enabled: true,
      num_assistant_tokens: 4,
      assistant_tokens_schedule: 'heuristic',
    },
  })
  const [storagePath, setStoragePath] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [ttsVoices, setTtsVoices] = useState([])  // Available TTS voices
  const [sttModels, setSttModels] = useState({ installed: [], available: [] })  // STT models
  const [isDownloadingSTT, setIsDownloadingSTT] = useState(false)
  const [sttDownloadProgress, setSttDownloadProgress] = useState(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setIsLoading(true)
    try {
      await Promise.all([
        loadSettings(),
        loadLocalModels(),
        loadStoragePaths(),
        loadTtsVoices(),
        loadSttModels(),
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const loadSttModels = async () => {
    try {
      const [installed, available] = await Promise.all([
        voiceAPI.listSTTModels(),
        voiceAPI.listAvailableSTTModels(),
      ])
      setSttModels({
        installed: installed.models || [],
        available: available.models || [],
      })
    } catch (error) {
      console.error('Failed to load STT models:', error)
    }
  }

  const downloadSttModel = async (modelName) => {
    if (isDownloadingSTT) return
    
    setIsDownloadingSTT(true)
    setSttDownloadProgress({ name: modelName, percent: 0, message: 'Starting...' })
    
    try {
      // Stream returns an async iterator
      for await (const data of voiceAPI.downloadSTTModel(modelName, {})) {
        if (data.type === 'progress') {
          setSttDownloadProgress({ name: modelName, percent: data.percent || 0, message: data.message || 'Downloading...' })
        } else if (data.type === 'done') {
          toast.success(`Downloaded ${modelName}`)
          await loadSttModels()
          break
        } else if (data.type === 'error') {
          toast.error(data.message || 'Download failed')
          break
        }
      }
    } catch (error) {
      console.error('STT download error:', error)
      toast.error(`Download failed: ${error.message}`)
    } finally {
      setIsDownloadingSTT(false)
      setSttDownloadProgress(null)
    }
  }

  const loadTtsVoices = async () => {
    try {
      const data = await voiceAPI.listVoices()
      setTtsVoices(data.voices || [])
      // Also register system voices if none exist
      if (!data.voices?.length) {
        await voiceAPI.registerSystemVoices()
        const refreshed = await voiceAPI.listVoices()
        setTtsVoices(refreshed.voices || [])
      }
    } catch (error) {
      console.error('Failed to load TTS voices:', error)
    }
  }

  const loadSettings = async () => {
    try {
      const data = await settingsAPI.getSettings()
      setSettings({
        model: data.model || { default_model: '', use_torch_compile: false },
        chat_defaults: data.chat_defaults || {
          temperature: 0.7,
          max_tokens: 2048,
          context_length: 4096,
        },
        ui: data.ui || {
          stream_enabled: true,
          show_timestamps: true,
          compact_mode: false,
          tool_thinking: true,
        },
        voice: data.voice || {
          tts_enabled: true,
          stt_enabled: true,
          tts_device: 'auto',
          tts_voice: '',
          vad_aggressiveness: 2,
          chunk_max_words: 16,
          chunk_max_wait_s: 0.7,
          auto_load_tts: false,
        },
      })
    } catch (error) {
      console.error('Failed to load settings:', error)
    }
  }

  const loadStoragePaths = async () => {
    try {
      const data = await settingsAPI.getStoragePaths()
      setStoragePath(data.db_path || 'Unknown')
    } catch (error) {
      console.error('Failed to load storage paths:', error)
    }
  }

  const handleSave = async () => {
    setIsSaving(true)
    try {
      await settingsAPI.updateSettings(settings)
      toast.success('Settings saved successfully')
    } catch (error) {
      toast.error('Failed to save: ' + error.message)
    } finally {
      setIsSaving(false)
    }
  }

  const handleReset = async () => {
    if (!confirm('Reset all settings to defaults? This cannot be undone.')) return
    
    try {
      const data = await settingsAPI.resetSettings()
      setSettings({
        model: data.model || { default_model: '', use_torch_compile: false },
        chat_defaults: data.chat_defaults || {
          temperature: 0.7,
          max_tokens: 2048,
          context_length: 4096,
        },
        ui: data.ui || {
          stream_enabled: true,
          show_timestamps: true,
          compact_mode: false,
          tool_thinking: true,
        },
        voice: data.voice || {
          tts_enabled: true,
          stt_enabled: true,
          tts_device: 'auto',
          tts_voice: '',
          vad_aggressiveness: 2,
          chunk_max_words: 16,
          chunk_max_wait_s: 0.7,
          auto_load_tts: false,
        },
      })
      toast.success('Settings reset to defaults')
    } catch (error) {
      toast.error('Failed to reset: ' + error.message)
    }
  }

  const updateSetting = (section, key, value) => {
    setSettings(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [key]: value,
      },
    }))
  }

  if (isLoading) {
    return (
      <div className="flex flex-col h-full overflow-hidden bg-neutral-950">
        <header className="flex items-center gap-3 px-4 py-3 border-b border-white/10 bg-neutral-900/80">
          <div className="w-10 h-10 rounded-lg skeleton" />
          <div className="flex-1 space-y-2">
            <div className="h-4 w-24 skeleton rounded" />
            <div className="h-3 w-48 skeleton rounded" />
          </div>
        </header>
        <div className="flex-1 p-6 space-y-6">
          {[1, 2, 3].map(i => (
            <div key={i} className="p-5 bg-white/5 rounded-xl space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl skeleton" />
                <div className="space-y-2">
                  <div className="h-4 w-32 skeleton rounded" />
                  <div className="h-3 w-48 skeleton rounded" />
                </div>
              </div>
              <div className="space-y-3">
                <div className="h-10 skeleton rounded-lg" />
                <div className="h-10 skeleton rounded-lg" />
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full overflow-hidden bg-neutral-950">
      {/* Header */}
      <header className="flex items-center gap-3 px-4 py-3 border-b border-white/10 bg-neutral-900/80 backdrop-blur-sm">
        <button
          onClick={onBack}
          className="p-2 rounded-lg hover:bg-white/10 text-neutral-400 transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1">
          <h1 className="text-sm font-black text-white">Settings</h1>
          <p className="text-[10px] text-neutral-500">Configure application preferences</p>
        </div>
        <button
          onClick={handleSave}
          disabled={isSaving}
          className="flex items-center gap-2 px-4 py-2 bg-red-500 hover:bg-red-600
                     disabled:bg-neutral-800 disabled:text-neutral-600
                     text-white text-xs font-bold rounded-lg transition-all"
        >
          <Save className="w-4 h-4" />
          {isSaving ? 'Saving...' : 'Save Changes'}
        </button>
      </header>

      <div className="flex-1 overflow-y-auto p-4 md:p-6">
        <div className="max-w-3xl mx-auto space-y-6">
          
          {/* Profile Notice */}
          {currentProfile && (
            <div className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-xl animate-fadeIn">
              <div className="w-10 h-10 rounded-xl bg-red-500/20 flex items-center justify-center">
                <User className="w-5 h-5 text-red-400" />
              </div>
              <div className="flex-1">
                <h3 className="text-xs font-bold text-white">Profile-Specific Settings</h3>
                <p className="text-[10px] text-neutral-400">
                  These settings apply globally. For per-profile settings (model, temperature, prompts), 
                  edit your profile in the Profiles section.
                </p>
              </div>
            </div>
          )}

          {/* Model Settings */}
          <section className="p-5 bg-white/5 border border-white/10 rounded-xl">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 rounded-xl bg-blue-500/20 flex items-center justify-center">
                <Box className="w-5 h-5 text-blue-400" />
              </div>
              <div>
                <h3 className="text-xs font-black text-white">Default Model</h3>
                <p className="text-[10px] text-neutral-500">Model to load on startup</p>
              </div>
            </div>
            
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-neutral-300 mb-2">
                  Startup Model
                </label>
                <select
                  value={settings.model.default_model || ''}
                  onChange={(e) => updateSetting('model', 'default_model', e.target.value)}
                  className="w-full px-4 py-2.5 bg-neutral-900 border border-white/10 rounded-lg
                             text-xs text-white focus:outline-none focus:border-red-500/50 transition-colors"
                >
                  <option value="">None - select manually</option>
                  {localModels.map(m => (
                    <option key={m.model_id} value={m.model_id}>{m.model_id}</option>
                  ))}
                </select>
                <p className="text-[10px] text-neutral-500 mt-1.5">
                  This model will be automatically loaded when you start the app
                </p>
              </div>
            </div>
          </section>

          {/* Performance Settings */}
          <section className="p-5 bg-white/5 border border-white/10 rounded-xl">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 rounded-xl bg-orange-500/20 flex items-center justify-center">
                <Zap className="w-5 h-5 text-orange-400" />
              </div>
              <div>
                <h3 className="text-xs font-black text-white">Performance</h3>
                <p className="text-[10px] text-neutral-500">Optimize inference speed</p>
              </div>
            </div>
            
            <div className="space-y-3">
              <div className="p-3 bg-neutral-900/50 rounded-lg border border-white/5">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-2 h-2 rounded-full bg-green-500" />
                  <span className="text-xs font-bold text-white">Always Enabled</span>
                </div>
                <ul className="text-[10px] text-neutral-400 space-y-1 ml-4">
                  <li>• <span className="text-green-400">SDPA Attention</span> - Optimized attention for all GPUs</li>
                  <li>• <span className="text-green-400">KV Cache</span> - Faster autoregressive generation</li>
                </ul>
              </div>
              
              {/* Attention Implementation */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Zap className="w-4 h-4 text-neutral-500" />
                  <label className="text-xs font-bold text-neutral-300">Attention Implementation</label>
                </div>
                <select
                  value={settings.model.attention_implementation || 'auto'}
                  onChange={(e) => updateSetting('model', 'attention_implementation', e.target.value)}
                  className="w-full px-4 py-2.5 bg-neutral-900 border border-white/10 rounded-lg
                             text-xs text-white focus:outline-none focus:border-red-500/50"
                >
                  <option value="auto">Auto (use Flash Attention if available)</option>
                  <option value="flash_attention_2">Flash Attention 2 (fastest, requires flash_attn)</option>
                  <option value="sdpa">SDPA (PyTorch built-in, works everywhere)</option>
                  <option value="eager">Eager (slowest, most compatible)</option>
                </select>
                <p className="text-[10px] text-neutral-500 mt-1">
                  Flash Attention is fastest but requires the flash_attn package. SDPA is built into PyTorch and works on all systems. Requires model reload.
                </p>
              </div>
              
              <ToggleSetting
                label="torch.compile (Experimental)"
                description="JIT compile model for 20-40% faster inference. May cause issues on PyTorch 2.9.x. Only applies to fp16/fp32 models."
                checked={settings.model.use_torch_compile || false}
                onChange={(val) => updateSetting('model', 'use_torch_compile', val)}
              />
            </div>
          </section>

          {/* Chat Defaults */}
          <section className="p-5 bg-white/5 border border-white/10 rounded-xl">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center">
                <Sliders className="w-5 h-5 text-purple-400" />
              </div>
              <div>
                <h3 className="text-xs font-black text-white">Generation Settings</h3>
                <p className="text-[10px] text-neutral-500">Default parameters for AI responses</p>
              </div>
            </div>
            
            <div className="space-y-5">
              {/* Temperature */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Thermometer className="w-4 h-4 text-neutral-500" />
                    <label className="text-xs font-bold text-neutral-300">Temperature</label>
                  </div>
                  <span className="text-xs text-white font-mono px-2 py-0.5 bg-white/10 rounded">
                    {settings.chat_defaults.temperature.toFixed(1)}
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  value={settings.chat_defaults.temperature}
                  onChange={(e) => updateSetting('chat_defaults', 'temperature', parseFloat(e.target.value))}
                  className="w-full"
                />
                <div className="flex justify-between text-[10px] text-neutral-500 mt-1">
                  <span>Precise (0)</span>
                  <span>Balanced (1)</span>
                  <span>Creative (2)</span>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Max Tokens */}
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <FileText className="w-4 h-4 text-neutral-500" />
                    <label className="text-xs font-bold text-neutral-300">Max Tokens</label>
                  </div>
                  <input
                    type="number"
                    value={settings.chat_defaults.max_tokens}
                    onChange={(e) => updateSetting('chat_defaults', 'max_tokens', parseInt(e.target.value) || 2048)}
                    className="w-full px-4 py-2.5 bg-neutral-900 border border-white/10 rounded-lg
                               text-xs text-white focus:outline-none focus:border-red-500/50"
                  />
                  <p className="text-[10px] text-neutral-500 mt-1">Max response length</p>
                </div>
                
                {/* Context Length */}
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Database className="w-4 h-4 text-neutral-500" />
                    <label className="text-xs font-bold text-neutral-300">Context Length</label>
                  </div>
                  <input
                    type="number"
                    value={settings.chat_defaults.context_length}
                    onChange={(e) => updateSetting('chat_defaults', 'context_length', parseInt(e.target.value) || 4096)}
                    className="w-full px-4 py-2.5 bg-neutral-900 border border-white/10 rounded-lg
                               text-xs text-white focus:outline-none focus:border-red-500/50"
                  />
                  <p className="text-[10px] text-neutral-500 mt-1">Memory window size</p>
                </div>
              </div>
            </div>
          </section>

          {/* UI Settings */}
          <section className="p-5 bg-white/5 border border-white/10 rounded-xl">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 rounded-xl bg-green-500/20 flex items-center justify-center">
                <Monitor className="w-5 h-5 text-green-400" />
              </div>
              <div>
                <h3 className="text-xs font-black text-white">Interface</h3>
                <p className="text-[10px] text-neutral-500">Customize the chat experience</p>
              </div>
            </div>
            
            <div className="space-y-3">
              <ToggleSetting
                label="Enable streaming"
                description="Show AI responses word by word as they generate"
                checked={settings.ui.stream_enabled}
                onChange={(val) => updateSetting('ui', 'stream_enabled', val)}
              />
              
              <ToggleSetting
                label="Show timestamps"
                description="Display time for each message"
                checked={settings.ui.show_timestamps}
                onChange={(val) => updateSetting('ui', 'show_timestamps', val)}
              />
              
              <ToggleSetting
                label="Compact mode"
                description="Reduce spacing between messages"
                checked={settings.ui.compact_mode}
                onChange={(val) => updateSetting('ui', 'compact_mode', val)}
              />
            </div>
          </section>

          {/* Speculative Decoding Settings */}
          <section className="p-5 bg-white/5 border border-white/10 rounded-xl">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 rounded-xl bg-blue-500/20 flex items-center justify-center">
                <Zap className="w-5 h-5 text-blue-400" />
              </div>
              <div>
                <h3 className="text-xs font-black text-white">Speculative Decoding</h3>
                <p className="text-[10px] text-neutral-500">Speed up generation with a draft model</p>
              </div>
            </div>
            
            <div className="space-y-4">
              <ToggleSetting
                label="Enable speculative decoding"
                description="Use assistant model for faster generation when loaded"
                checked={settings.speculative_decoding?.enabled ?? true}
                onChange={(val) => updateSetting('speculative_decoding', 'enabled', val)}
              />
              
              {/* Number of assistant tokens (K value) */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Zap className="w-4 h-4 text-neutral-500" />
                    <label className="text-xs font-bold text-neutral-300">Draft Tokens (K)</label>
                  </div>
                  <span className="text-xs text-white font-mono px-2 py-0.5 bg-white/10 rounded">
                    {settings.speculative_decoding?.num_assistant_tokens ?? 4}
                  </span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="10"
                  step="1"
                  value={settings.speculative_decoding?.num_assistant_tokens ?? 4}
                  onChange={(e) => updateSetting('speculative_decoding', 'num_assistant_tokens', parseInt(e.target.value))}
                  className="w-full"
                />
                <div className="flex justify-between text-[10px] text-neutral-500 mt-1">
                  <span>Conservative (1)</span>
                  <span>Balanced (4-5)</span>
                  <span>Aggressive (10)</span>
                </div>
                <p className="text-[10px] text-neutral-500 mt-2">
                  Number of tokens the draft model proposes per step. Higher = faster but may reduce accuracy.
                </p>
              </div>
              
              {/* Token schedule */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Sliders className="w-4 h-4 text-neutral-500" />
                  <label className="text-xs font-bold text-neutral-300">Token Schedule</label>
                </div>
                <select
                  value={settings.speculative_decoding?.assistant_tokens_schedule ?? 'heuristic'}
                  onChange={(e) => updateSetting('speculative_decoding', 'assistant_tokens_schedule', e.target.value)}
                  className="w-full px-4 py-2.5 bg-neutral-900 border border-white/10 rounded-lg
                             text-xs text-white focus:outline-none focus:border-blue-500/50"
                >
                  <option value="constant">Constant - Fixed K value</option>
                  <option value="heuristic">Heuristic - Auto-adjust based on acceptance rate</option>
                </select>
                <p className="text-[10px] text-neutral-500 mt-1">
                  "Heuristic" automatically adjusts K based on how many tokens get accepted.
                </p>
              </div>
            </div>
          </section>

          {/* Voice Settings */}
          <section className="p-5 bg-white/5 border border-white/10 rounded-xl">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center">
                <Mic className="w-5 h-5 text-purple-400" />
              </div>
              <div>
                <h3 className="text-xs font-black text-white">Voice Chat</h3>
                <p className="text-[10px] text-neutral-500">TTS and STT configuration</p>
              </div>
            </div>
            
            <div className="space-y-4">
              {/* Enable toggles */}
              <div className="space-y-3">
                <ToggleSetting
                  label="Enable TTS"
                  description="Text-to-speech for AI responses"
                  checked={settings.voice?.tts_enabled ?? true}
                  onChange={(val) => updateSetting('voice', 'tts_enabled', val)}
                />
                
                <ToggleSetting
                  label="Enable STT"
                  description="Speech-to-text for voice input"
                  checked={settings.voice?.stt_enabled ?? true}
                  onChange={(val) => updateSetting('voice', 'stt_enabled', val)}
                />
                
                <ToggleSetting
                  label="Auto-load TTS on startup"
                  description="Load TTS model when backend starts"
                  checked={settings.voice?.auto_load_tts ?? false}
                  onChange={(val) => updateSetting('voice', 'auto_load_tts', val)}
                />
              </div>
              
              {/* TTS Settings */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-3 border-t border-white/5">
                {/* TTS Voice */}
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Volume2 className="w-4 h-4 text-neutral-500" />
                    <label className="text-xs font-bold text-neutral-300">TTS Voice</label>
                  </div>
                  <select
                    value={settings.voice?.tts_voice ?? ''}
                    onChange={(e) => updateSetting('voice', 'tts_voice', e.target.value)}
                    className="w-full px-4 py-2.5 bg-neutral-900 border border-white/10 rounded-lg
                               text-xs text-white focus:outline-none focus:border-purple-500/50"
                  >
                    <option value="">Default (Alba)</option>
                    {ttsVoices.filter(v => v.is_system).length > 0 && (
                      <optgroup label="System Voices">
                        {ttsVoices.filter(v => v.is_system).map(voice => (
                          <option key={voice.id} value={voice.id}>
                            {voice.display_name || voice.name}
                          </option>
                        ))}
                      </optgroup>
                    )}
                    {ttsVoices.filter(v => !v.is_system).length > 0 && (
                      <optgroup label="Custom Voices">
                        {ttsVoices.filter(v => !v.is_system).map(voice => (
                          <option key={voice.id} value={voice.id}>
                            {voice.display_name || voice.name}
                          </option>
                        ))}
                      </optgroup>
                    )}
                  </select>
                  <p className="text-[10px] text-neutral-500 mt-1">Pocket TTS voice for speech synthesis</p>
                </div>
                
                {/* TTS Info */}
                <div className="flex items-center">
                  <div className="px-4 py-3 bg-neutral-900/50 rounded-lg border border-white/5 w-full">
                    <div className="flex items-center gap-2 mb-1">
                      <Info className="w-3 h-3 text-purple-400" />
                      <span className="text-[10px] font-medium text-purple-400">Pocket TTS</span>
                    </div>
                    <p className="text-[10px] text-neutral-500">
                      Lightweight TTS that runs on CPU. Fast, low memory usage, supports voice cloning.
                    </p>
                  </div>
                </div>
              </div>
              
              {/* VAD Settings */}
              <div className="pt-3 border-t border-white/5">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Mic className="w-4 h-4 text-neutral-500" />
                    <label className="text-xs font-bold text-neutral-300">VAD Aggressiveness</label>
                  </div>
                  <span className="text-xs text-white font-mono px-2 py-0.5 bg-white/10 rounded">
                    {settings.voice?.vad_aggressiveness ?? 2}
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="3"
                  step="1"
                  value={settings.voice?.vad_aggressiveness ?? 2}
                  onChange={(e) => updateSetting('voice', 'vad_aggressiveness', parseInt(e.target.value))}
                  className="w-full"
                />
                <div className="flex justify-between text-[10px] text-neutral-500 mt-1">
                  <span>Less aggressive (0)</span>
                  <span>More aggressive (3)</span>
                </div>
                <p className="text-[10px] text-neutral-500 mt-1">Higher = filters more non-speech audio</p>
              </div>
              
              {/* STT Model Selection */}
              <div className="pt-3 border-t border-white/5">
                <div className="flex items-center gap-2 mb-3">
                  <Mic className="w-4 h-4 text-neutral-500" />
                  <label className="text-xs font-bold text-neutral-300">STT Model (Vosk)</label>
                </div>
                
                {/* Installed Models */}
                {sttModels.installed.length > 0 && (
                  <div className="mb-3">
                    <span className="text-[10px] text-neutral-500 uppercase tracking-wide mb-2 block">Installed</span>
                    <div className="space-y-1">
                      {sttModels.installed.map(model => (
                        <div key={model.name} className="flex items-center justify-between px-3 py-2 bg-neutral-900/50 rounded-lg">
                          <div className="flex items-center gap-2">
                            <Check className="w-3 h-3 text-green-400" />
                            <span className="text-xs text-white">{model.name}</span>
                          </div>
                          <span className="text-[10px] text-neutral-500">
                            {(model.size / 1024 / 1024).toFixed(0)}MB
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Available for Download */}
                <div>
                  <span className="text-[10px] text-neutral-500 uppercase tracking-wide mb-2 block">
                    {sttModels.installed.length > 0 ? 'More Models' : 'Available for Download'}
                  </span>
                  <div className="space-y-1 max-h-48 overflow-y-auto">
                    {sttModels.available
                      .filter(m => !m.installed)
                      .map(model => (
                        <div key={model.name} className="flex items-center justify-between px-3 py-2 bg-neutral-900/50 rounded-lg">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-white truncate">{model.name}</span>
                              <span className="text-[10px] px-1.5 py-0.5 bg-white/10 rounded text-neutral-400">
                                {model.language}
                              </span>
                            </div>
                            <p className="text-[10px] text-neutral-500 truncate">{model.description}</p>
                          </div>
                          <button
                            onClick={() => downloadSttModel(model.name)}
                            disabled={isDownloadingSTT}
                            className="ml-2 px-3 py-1.5 text-[10px] bg-purple-500/20 text-purple-400 rounded-lg
                                     hover:bg-purple-500/30 disabled:opacity-50 disabled:cursor-not-allowed
                                     transition-colors flex items-center gap-1.5 whitespace-nowrap font-medium"
                          >
                            {isDownloadingSTT && sttDownloadProgress?.name === model.name ? (
                              <span>{sttDownloadProgress.percent}%</span>
                            ) : (
                              <>
                                <Download className="w-3 h-3" />
                                <span>Download ({model.size_mb}MB)</span>
                              </>
                            )}
                          </button>
                        </div>
                      ))}
                  </div>
                  
                  {/* Download Progress */}
                  {sttDownloadProgress && (
                    <div className="mt-2 px-3 py-2 bg-purple-500/10 rounded-lg border border-purple-500/20">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] text-purple-400">Downloading {sttDownloadProgress.name}</span>
                        <span className="text-[10px] text-purple-400 font-mono">{sttDownloadProgress.percent}%</span>
                      </div>
                      <div className="w-full h-1 bg-purple-500/20 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-purple-500 rounded-full transition-all duration-300"
                          style={{ width: `${sttDownloadProgress.percent}%` }}
                        />
                      </div>
                      <p className="text-[10px] text-neutral-500 mt-1">{sttDownloadProgress.message}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </section>

          {/* Storage Info */}
          <section className="p-5 bg-white/5 border border-white/10 rounded-xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-yellow-500/20 flex items-center justify-center">
                <Database className="w-5 h-5 text-yellow-400" />
              </div>
              <div>
                <h3 className="text-xs font-black text-white">Storage</h3>
                <p className="text-[10px] text-neutral-500">Data location information</p>
              </div>
            </div>
            <div className="p-3 bg-neutral-900/50 rounded-lg">
              <div className="flex items-center gap-2 mb-1">
                <Info className="w-3.5 h-3.5 text-neutral-500" />
                <span className="text-[10px] text-neutral-500 uppercase tracking-wide">Database Path</span>
              </div>
              <code className="text-xs text-neutral-300 font-mono break-all">
                {storagePath}
              </code>
            </div>
          </section>

          {/* Reset */}
          <div className="flex items-center justify-between p-4 bg-red-500/5 border border-red-500/10 rounded-xl">
            <div>
              <h3 className="text-xs font-bold text-red-400">Danger Zone</h3>
              <p className="text-[10px] text-neutral-500">Reset all settings to their defaults</p>
            </div>
            <button
              onClick={handleReset}
              className="flex items-center gap-2 px-4 py-2 bg-red-500/20 hover:bg-red-500/30
                         text-red-400 text-xs font-medium rounded-lg transition-colors"
            >
              <RotateCcw className="w-4 h-4" />
              Reset All
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// Toggle Setting Component
function ToggleSetting({ label, description, checked, onChange }) {
  return (
    <label className="flex items-center justify-between p-3 bg-neutral-900/50 rounded-lg cursor-pointer 
                      hover:bg-neutral-900 transition-colors group">
      <div className="flex-1 pr-4">
        <span className="text-xs font-medium text-white block">{label}</span>
        <span className="text-[10px] text-neutral-500">{description}</span>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full 
                    border-2 border-transparent transition-colors duration-200 ease-in-out
                    ${checked ? 'bg-red-500' : 'bg-neutral-700'}`}
      >
        <span
          className={`pointer-events-none inline-block h-5 w-5 transform rounded-full 
                      bg-white shadow-lg ring-0 transition duration-200 ease-in-out
                      ${checked ? 'translate-x-5' : 'translate-x-0'}`}
        />
      </button>
    </label>
  )
}
