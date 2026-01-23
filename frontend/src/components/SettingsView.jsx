import { useState, useEffect } from 'react'
import { useToast } from '../contexts/ToastContext'
import { settingsAPI, modelsAPI } from '../lib/api'
import { useApp } from '../contexts/AppContext'
import { 
  ArrowLeft, Save, RotateCcw, Settings, Sliders, Monitor, 
  Database, Info, Box, Thermometer, FileText, User
} from 'lucide-react'

export default function SettingsView({ onBack }) {
  const { toast } = useToast()
  const { localModels, loadLocalModels, currentProfile } = useApp()
  
  const [settings, setSettings] = useState({
    model: { default_model: '' },
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
  })
  const [storagePath, setStoragePath] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

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
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const loadSettings = async () => {
    try {
      const data = await settingsAPI.getSettings()
      setSettings({
        model: data.model || { default_model: '' },
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
        model: data.model || { default_model: '' },
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
