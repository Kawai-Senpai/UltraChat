import { useState, useEffect } from 'react'
import { useApp } from '../contexts/AppContext'
import { useToast } from '../contexts/ToastContext'
import { modelsAPI, voiceAPI } from '../lib/api'
import { 
  ArrowLeft, RefreshCw, Download, Sparkles, Trash2, Search, 
  Cpu, HardDrive, Zap, Box, Check, X, Loader2, Star, Archive,
  Mic, Volume2, Globe
} from 'lucide-react'

const QUANT_OPTIONS = [
  { value: 'original', label: 'Original', desc: 'Full precision', color: 'red' },
  { value: '4bit', label: '4-bit', desc: 'Smallest, fastest', color: 'green' },
  { value: '8bit', label: '8-bit', desc: 'Balanced', color: 'blue' },
  { value: 'fp16', label: 'FP16', desc: 'High quality', color: 'purple' },
]

const LOAD_QUANT_OPTIONS = [
  { value: 'original', label: 'Original' },
  { value: '4bit', label: '4-bit' },
  { value: '8bit', label: '8-bit' },
  { value: 'fp16', label: 'FP16' },
]

export default function ModelsView({ onBack }) {
  const { gpuInfo, loadedModel, setLoadedModel, localModels, loadLocalModels, loadSystemStatus } = useApp()
  const { toast } = useToast()
  
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [isSearching, setIsSearching] = useState(false)
  const [isDownloading, setIsDownloading] = useState(false)
  const [downloadProgress, setDownloadProgress] = useState(null)
  const [selectedQuants, setSelectedQuants] = useState(['original']) // Array of selected quantizations
  const [keepCache, setKeepCache] = useState(false)
  const [loadingModel, setLoadingModel] = useState(null)
  const [loadQuantSelections, setLoadQuantSelections] = useState({})
  
  // Voice models state
  const [voiceStatus, setVoiceStatus] = useState(null)
  const [availableSTTModels, setAvailableSTTModels] = useState([])
  const [downloadingSTT, setDownloadingSTT] = useState(null)
  const [sttDownloadProgress, setSTTDownloadProgress] = useState(null)

  useEffect(() => {
    loadLocalModels()
    loadSystemStatus()
    loadVoiceStatus()
  }, [loadLocalModels, loadSystemStatus])
  
  const loadVoiceStatus = async () => {
    try {
      const status = await voiceAPI.getStatus()
      setVoiceStatus(status)
      const available = await voiceAPI.listAvailableSTTModels()
      setAvailableSTTModels(available.models || [])
    } catch (error) {
      console.error('Failed to load voice status:', error)
    }
  }
  
  const handleDownloadSTT = async (modelName) => {
    setDownloadingSTT(modelName)
    setSTTDownloadProgress({ status: 'starting', model_name: modelName })
    
    try {
      for await (const { event, data } of voiceAPI.downloadSTTModel(modelName)) {
        if (event === 'status' || event === 'progress') {
          setSTTDownloadProgress(prev => ({ ...prev, ...data }))
        } else if (event === 'done') {
          toast.success(`Downloaded ${modelName}`)
          await loadVoiceStatus()
        } else if (event === 'error') {
          throw new Error(data.error || data.message || 'Download failed')
        }
      }
    } catch (error) {
      toast.error('STT download failed: ' + error.message)
    } finally {
      setDownloadingSTT(null)
      setSTTDownloadProgress(null)
    }
  }
  
  const handleDeleteSTT = async (modelName) => {
    if (!confirm(`Delete ${modelName}?`)) return
    
    try {
      await voiceAPI.deleteSTTModel(modelName)
      toast.success('STT model deleted')
      await loadVoiceStatus()
    } catch (error) {
      toast.error('Failed to delete: ' + error.message)
    }
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    
    setIsSearching(true)
    try {
      const data = await modelsAPI.searchModels(searchQuery)
      setSearchResults(data.models || [])
    } catch (error) {
      toast.error('Search failed: ' + error.message)
    } finally {
      setIsSearching(false)
    }
  }

  const toggleQuant = (quant) => {
    setSelectedQuants(prev => {
      if (prev.includes(quant)) {
        // Don't allow empty selection
        if (prev.length === 1) return prev
        return prev.filter(q => q !== quant)
      }
      return [...prev, quant]
    })
  }

  const handleDownload = async (modelId) => {
    if (selectedQuants.length === 0) {
      toast.error('Select at least one quantization option')
      return
    }
    const displayQuants = selectedQuants.map(q => q === 'original' ? 'original' : q)
    setIsDownloading(true)
    setDownloadProgress({ status: 'starting', model_id: modelId, quantizations: displayQuants })
    
    try {
      for await (const { event, data } of modelsAPI.downloadModel(modelId, selectedQuants, keepCache)) {
        if (event === 'status' || event === 'progress' || event === 'heartbeat') {
          setDownloadProgress(prev => ({ 
            ...prev, 
            ...data, 
            quantizations: data?.quantizations || prev?.quantizations || displayQuants 
          }))
        } else if (event === 'complete' || event === 'done') {
          toast.success(`Downloaded ${modelId} with ${displayQuants.length} option(s)`)
          loadLocalModels()
        } else if (event === 'error') {
          throw new Error(data.error || 'Download failed')
        }
      }
    } catch (error) {
      toast.error('Download failed: ' + error.message)
    } finally {
      setIsDownloading(false)
      setDownloadProgress(null)
    }
  }

  // Create unique key for a model (combines model_id and quantization)
  const getModelKey = (model) => {
    return model.quantization ? `${model.model_id}__${model.quantization}` : model.model_id
  }

  const handleLoad = async (model) => {
    const modelKey = getModelKey(model)
    const requestedQuant = getLoadQuantization(model)
    const loadQuant = requestedQuant === 'original' ? null : requestedQuant
    setLoadingModel(modelKey)
    try {
      const result = await modelsAPI.loadModel(model.model_id, loadQuant)
      const loadedKey = result?.quantization ? `${result.model_id}__${result.quantization}` : result?.model_id
      setLoadedModel(loadedKey || modelKey)
      toast.success(`Loaded ${result?.model_id || model.model_id} (${result?.quantization || 'original'})`)
      loadSystemStatus()
    } catch (error) {
      toast.error('Failed to load: ' + error.message)
    } finally {
      setLoadingModel(null)
    }
  }

  const getLoadQuantization = (model) => {
    const modelKey = getModelKey(model)
    if (loadQuantSelections[modelKey]) return loadQuantSelections[modelKey]
    return model.quantization || 'original'
  }

  const setLoadQuantization = (model, value) => {
    const modelKey = getModelKey(model)
    setLoadQuantSelections(prev => ({
      ...prev,
      [modelKey]: value,
    }))
  }

  const hasExactLoadedEntry = loadedModel
    ? localModels.some(model => getModelKey(model) === loadedModel)
    : false

  const handleUnload = async () => {
    try {
      await modelsAPI.unloadModel()
      setLoadedModel(null)
      toast.success('Model unloaded')
      loadSystemStatus()
    } catch (error) {
      toast.error('Failed to unload: ' + error.message)
    }
  }

  const handleDelete = async (model) => {
    if (!confirm(`Delete ${model.model_id}?`)) return
    
    try {
      await modelsAPI.deleteModel(model.model_id, model.quantization)
      toast.success('Model deleted')
      loadLocalModels()
    } catch (error) {
      toast.error('Failed to delete: ' + error.message)
    }
  }

  const formatSize = (value) => {
    // If it's already a formatted string, return it
    if (typeof value === 'string') return value
    // If it's a number, format it
    if (typeof value === 'number' && !isNaN(value) && value > 0) {
      const gb = value / (1024 * 1024 * 1024)
      if (gb >= 1) return `${gb.toFixed(1)} GB`
      const mb = value / (1024 * 1024)
      return `${mb.toFixed(0)} MB`
    }
    return null
  }

  // GPU memory is returned as strings from the API
  const memoryFreeStr = gpuInfo?.memoryFree || formatSize(gpuInfo?.gpu?.memory_free)
  const memoryTotalStr = gpuInfo?.memoryTotal || formatSize(gpuInfo?.gpu?.memory_total)

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
          <h1 className="text-sm font-black text-white">Models</h1>
          <p className="text-[10px] text-neutral-500">Download and manage AI models from HuggingFace</p>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-4 md:p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          
          {/* GPU Status Card */}
          <div className="p-5 bg-white/5 border border-white/10 rounded-xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-green-500/20 flex items-center justify-center">
                <Cpu className="w-5 h-5 text-green-400" />
              </div>
              <div>
                <h3 className="text-xs font-black text-white">System Status</h3>
                <p className="text-[10px] text-neutral-500">GPU and memory information</p>
              </div>
            </div>
            
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {/* GPU Name */}
              <div className="p-3 bg-white/5 rounded-lg">
                <div className="flex items-center gap-2 mb-1">
                  <Cpu className="w-3.5 h-3.5 text-neutral-500" />
                  <span className="text-[10px] text-neutral-500 uppercase tracking-wide">GPU</span>
                </div>
                <div className="text-xs font-medium text-white truncate">
                  {gpuInfo?.name || 'Detecting...'}
                </div>
              </div>
              
              {/* VRAM */}
              <div className="p-3 bg-white/5 rounded-lg">
                <div className="flex items-center gap-2 mb-1">
                  <HardDrive className="w-3.5 h-3.5 text-neutral-500" />
                  <span className="text-[10px] text-neutral-500 uppercase tracking-wide">VRAM</span>
                </div>
                <div className="text-xs font-medium text-white">
                  {gpuInfo?.available === false ? (
                    <span className="text-yellow-400">No GPU detected</span>
                  ) : memoryFreeStr ? (
                    <>{memoryFreeStr} free / {memoryTotalStr}</>
                  ) : (
                    <span className="text-neutral-500">Loading...</span>
                  )}
                </div>
              </div>
              
              {/* Loaded Model */}
              <div className="p-3 bg-white/5 rounded-lg">
                <div className="flex items-center gap-2 mb-1">
                  <Zap className="w-3.5 h-3.5 text-neutral-500" />
                  <span className="text-[10px] text-neutral-500 uppercase tracking-wide">Active Model</span>
                </div>
                {loadedModel ? (
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-green-400 truncate flex-1">{loadedModel}</span>
                    <button
                      onClick={handleUnload}
                      className="p-1 rounded hover:bg-red-500/20 text-red-400 transition-colors"
                      title="Unload model"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <span className="text-xs text-neutral-500 italic">No model loaded</span>
                )}
              </div>
            </div>
          </div>

          {/* Search HuggingFace */}
          <div className="p-5 bg-white/5 border border-white/10 rounded-xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-yellow-500/20 flex items-center justify-center">
                <Search className="w-5 h-5 text-yellow-400" />
              </div>
              <div>
                <h3 className="text-xs font-black text-white">Search HuggingFace</h3>
                <p className="text-[10px] text-neutral-500">Find and download text generation models</p>
              </div>
            </div>
            
            <div className="flex flex-col sm:flex-row gap-2 mb-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-500" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                  placeholder="Search models (e.g., Qwen, Llama, Mistral)"
                  className="w-full pl-10 pr-4 py-2.5 bg-neutral-900 border border-white/10 rounded-lg
                             text-xs text-white placeholder-neutral-500
                             focus:outline-none focus:border-red-500/50 transition-colors"
                />
              </div>
              <button
                onClick={handleSearch}
                disabled={isSearching || !searchQuery.trim()}
                className="flex items-center justify-center gap-2 px-5 py-2.5 bg-red-500 hover:bg-red-600 
                           disabled:bg-neutral-800 disabled:text-neutral-600
                           text-white text-xs font-bold rounded-lg transition-all"
              >
                {isSearching ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Search className="w-4 h-4" />
                )}
                Search
              </button>
            </div>

            {/* Multi-Quantization Selector */}
            <div className="mb-4 p-3 bg-neutral-900/50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] text-neutral-500 uppercase tracking-wide font-bold">
                  Quantization Options (select multiple)
                </span>
                <label className="flex items-center gap-2 text-[10px] text-neutral-400 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={keepCache}
                    onChange={(e) => setKeepCache(e.target.checked)}
                    className="w-3.5 h-3.5"
                  />
                  <Archive className="w-3 h-3" />
                  Keep cache
                </label>
              </div>
              <div className="flex flex-wrap gap-2">
                {QUANT_OPTIONS.map(opt => {
                  const isSelected = selectedQuants.includes(opt.value)
                  return (
                    <button
                      key={opt.value}
                      onClick={() => toggleQuant(opt.value)}
                      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all
                        ${isSelected 
                          ? `bg-${opt.color}-500/30 text-${opt.color}-400 border border-${opt.color}-500/50` 
                          : 'bg-white/5 text-neutral-400 border border-white/10 hover:bg-white/10'
                        }`}
                    >
                      {isSelected && <Check className="w-3 h-3" />}
                      <span>{opt.label}</span>
                      <span className="text-[10px] opacity-60">{opt.desc}</span>
                    </button>
                  )
                })}
              </div>
              {selectedQuants.length > 1 && (
                <p className="mt-2 text-[10px] text-neutral-500">
                  Will download once, then create {selectedQuants.length} quantized versions
                </p>
              )}
            </div>

            {/* Search Results */}
            {searchResults.length > 0 && (
              <div className="space-y-2 max-h-64 overflow-y-auto pr-2">
                {searchResults.map((model) => (
                  <div
                    key={model.model_id}
                    className="flex items-center justify-between p-3 bg-neutral-900/80 border border-white/5 
                               rounded-lg hover:border-white/10 transition-colors"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <Box className="w-4 h-4 text-neutral-500 flex-shrink-0" />
                        <span className="text-xs font-medium text-white truncate">
                          {model.model_id}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 mt-1 ml-6 text-[10px] text-neutral-500">
                        <span className="flex items-center gap-1">
                          <Download className="w-3 h-3" />
                          {model.downloads?.toLocaleString() || 0}
                        </span>
                        <span className="flex items-center gap-1">
                          <Star className="w-3 h-3" />
                          {model.likes || 0}
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={() => handleDownload(model.model_id)}
                      disabled={isDownloading}
                      className="flex items-center gap-2 px-3 py-1.5 bg-green-500/20 hover:bg-green-500/30
                                 text-green-400 text-xs font-medium rounded-lg transition-colors 
                                 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <Download className="w-3.5 h-3.5" />
                      Download
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Download Progress */}
            {downloadProgress && (
              <div className="mt-4 p-4 bg-neutral-900/80 border border-white/10 rounded-lg animate-fadeIn">
                <div className="flex items-center justify-between text-xs mb-3">
                  <div className="flex items-center gap-2">
                    <Loader2 className="w-4 h-4 text-red-400 animate-spin" />
                    <span className="text-white font-medium truncate">{downloadProgress.model_id}</span>
                  </div>
                  <span className="text-neutral-400 capitalize">
                    {downloadProgress.status?.replace(/_/g, ' ')}
                  </span>
                </div>
                
                {/* Quantization progress */}
                {downloadProgress.quantizations && downloadProgress.quantizations.length > 1 && (
                  <div className="flex flex-wrap gap-1.5 mb-3">
                    {downloadProgress.quantizations.map((q, idx) => (
                      <span
                        key={q}
                        className={`px-2 py-0.5 text-[10px] rounded ${
                          idx < (downloadProgress.files_completed || 0)
                            ? 'bg-green-500/20 text-green-400'
                            : idx === (downloadProgress.files_completed || 0)
                              ? 'bg-red-500/20 text-red-400 animate-pulse'
                              : 'bg-white/5 text-neutral-500'
                        }`}
                      >
                        {q}
                      </span>
                    ))}
                  </div>
                )}
                
                <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-red-500 transition-all duration-300"
                    style={{ 
                      width: `${
                        typeof downloadProgress.percent === 'number' && downloadProgress.percent > 0
                          ? downloadProgress.percent
                          : downloadProgress.files_total > 0 
                            ? ((downloadProgress.files_completed || 0) / downloadProgress.files_total * 100) 
                            : 10  // Indeterminate progress
                      }%`
                    }}
                  />
                </div>
                <div className="flex justify-between text-[10px] text-neutral-500 mt-2">
                  <span className="flex-1">
                    {downloadProgress.message || downloadProgress.status?.replace(/_/g, ' ') || 'Processing...'}
                  </span>
                  {downloadProgress.files_total > 0 && (
                    <span className="ml-2">{downloadProgress.files_completed || 0}/{downloadProgress.files_total}</span>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Local Models */}
          <div className="p-5 bg-white/5 border border-white/10 rounded-xl">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-blue-500/20 flex items-center justify-center">
                  <Box className="w-5 h-5 text-blue-400" />
                </div>
                <div>
                  <h3 className="text-xs font-black text-white">Downloaded Models</h3>
                  <p className="text-[10px] text-neutral-500">{localModels.length} model(s) available</p>
                </div>
              </div>
              <button
                onClick={loadLocalModels}
                className="p-2 rounded-lg hover:bg-white/10 text-neutral-400 transition-colors"
                title="Refresh"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>

            {localModels.length === 0 ? (
              <div className="text-center py-12">
                <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-white/5 flex items-center justify-center">
                  <Box className="w-8 h-8 text-neutral-600" />
                </div>
                <div className="text-sm font-medium text-neutral-400 mb-1">No models downloaded</div>
                <div className="text-xs text-neutral-500">Search and download a model above to get started</div>
              </div>
            ) : (
              <div className="grid gap-3">
                {localModels.map((model) => {
                  const modelKey = getModelKey(model)
                  const isLoaded = loadedModel === modelKey || (!hasExactLoadedEntry && !model.quantization && loadedModel?.startsWith(`${model.model_id}__`))
                  const isLoading = loadingModel === modelKey

                  return (
                    <div
                      key={modelKey}
                      className={`p-4 rounded-lg border transition-all ${
                        isLoaded
                          ? 'bg-green-500/10 border-green-500/30'
                          : 'bg-neutral-900/50 border-white/5 hover:border-white/10'
                      }`}
                    >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-bold text-white truncate">{model.model_id}</span>
                          {isLoaded && (
                            <span className="flex items-center gap-1 px-1.5 py-0.5 bg-green-500/20 rounded text-[10px] text-green-400">
                              <Check className="w-3 h-3" />
                              Loaded
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-3 text-[10px] text-neutral-500">
                          <span className="px-1.5 py-0.5 bg-white/10 rounded">{model.quantization || 'original'}</span>
                          <span>{formatSize(model.size)}</span>
                        </div>
                        <div className="mt-2 flex items-center gap-2">
                          <span className="text-[10px] text-neutral-500 uppercase tracking-wide">Load as</span>
                          <select
                            value={getLoadQuantization(model)}
                            onChange={(e) => setLoadQuantization(model, e.target.value)}
                            disabled={!!model.quantization}
                            className="bg-neutral-900 border border-white/10 rounded px-2 py-1 text-[10px] text-neutral-200
                                       focus:outline-none focus:border-red-500/50 disabled:opacity-60"
                          >
                            {(model.quantization ? [
                              { value: model.quantization, label: model.quantization }
                            ] : LOAD_QUANT_OPTIONS).map(opt => (
                              <option key={opt.value} value={opt.value}>
                                {opt.label}
                              </option>
                            ))}
                          </select>
                          {model.quantization && (
                            <span className="text-[10px] text-neutral-500">Fixed</span>
                          )}
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-1">
                        {isLoaded ? (
                          <button
                            onClick={handleUnload}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30
                                       text-red-400 text-xs font-medium rounded-lg transition-colors"
                          >
                            <X className="w-3.5 h-3.5" />
                            Unload
                          </button>
                        ) : (
                          <button
                            onClick={() => handleLoad(model)}
                            disabled={isLoading}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-green-500/20 hover:bg-green-500/30
                                       text-green-400 text-xs font-medium rounded-lg transition-colors
                                       disabled:opacity-50"
                          >
                            {isLoading ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <Sparkles className="w-3.5 h-3.5" />
                            )}
                            {isLoading ? 'Loading...' : 'Load'}
                          </button>
                        )}
                        <button
                          onClick={() => handleDelete(model)}
                          disabled={isLoaded}
                          className="p-2 rounded-lg hover:bg-red-500/20 text-neutral-500 hover:text-red-400
                                     transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                          title="Delete model"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                  )
                })}
              </div>
            )}
          </div>
          
          {/* Voice Models Section */}
          <div className="p-5 bg-white/5 border border-white/10 rounded-xl">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center">
                  <Mic className="w-5 h-5 text-purple-400" />
                </div>
                <div>
                  <h3 className="text-xs font-black text-white">Voice Models</h3>
                  <p className="text-[10px] text-neutral-500">TTS and STT models for voice chat</p>
                </div>
              </div>
              <button
                onClick={loadVoiceStatus}
                className="p-2 rounded-lg hover:bg-white/10 text-neutral-400 transition-colors"
                title="Refresh"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>
            
            {/* Voice Status */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
              <div className="p-3 bg-neutral-900/50 rounded-lg">
                <div className="flex items-center gap-2 mb-1">
                  <Volume2 className="w-3.5 h-3.5 text-neutral-500" />
                  <span className="text-[10px] text-neutral-500 uppercase tracking-wide">TTS (Chatterbox)</span>
                </div>
                <div className="text-xs text-white">
                  {voiceStatus?.tts_available ? (
                    voiceStatus?.tts_loaded ? (
                      <span className="text-green-400">Loaded ({voiceStatus.tts_device})</span>
                    ) : (
                      <span className="text-yellow-400">Available (not loaded)</span>
                    )
                  ) : (
                    <span className="text-red-400">Not installed</span>
                  )}
                </div>
                {!voiceStatus?.tts_available && (
                  <p className="text-[10px] text-neutral-500 mt-1">
                    Run: pip install chatterbox-tts
                  </p>
                )}
              </div>
              
              <div className="p-3 bg-neutral-900/50 rounded-lg">
                <div className="flex items-center gap-2 mb-1">
                  <Mic className="w-3.5 h-3.5 text-neutral-500" />
                  <span className="text-[10px] text-neutral-500 uppercase tracking-wide">STT (Vosk)</span>
                </div>
                <div className="text-xs text-white">
                  {voiceStatus?.stt_available ? (
                    voiceStatus?.stt_loaded ? (
                      <span className="text-green-400">Loaded</span>
                    ) : (
                      <span className="text-yellow-400">Available (not loaded)</span>
                    )
                  ) : (
                    <span className="text-red-400">Not installed</span>
                  )}
                </div>
                {!voiceStatus?.stt_available && (
                  <p className="text-[10px] text-neutral-500 mt-1">
                    Run: pip install vosk
                  </p>
                )}
              </div>
            </div>
            
            {/* STT Models */}
            <div className="border-t border-white/5 pt-4">
              <h4 className="text-[10px] text-neutral-500 uppercase tracking-wide mb-3">
                STT Models ({voiceStatus?.stt_models?.length || 0} downloaded)
              </h4>
              
              {/* Downloaded STT Models */}
              {voiceStatus?.stt_models?.length > 0 && (
                <div className="space-y-2 mb-4">
                  {voiceStatus.stt_models.map(model => (
                    <div
                      key={model.name}
                      className="flex items-center justify-between p-3 bg-neutral-900/50 rounded-lg"
                    >
                      <div className="flex items-center gap-2">
                        <Globe className="w-4 h-4 text-purple-400" />
                        <span className="text-xs text-white">{model.name}</span>
                        <span className="text-[10px] text-neutral-500">
                          {formatSize(model.size)}
                        </span>
                      </div>
                      <button
                        onClick={() => handleDeleteSTT(model.name)}
                        className="p-1.5 rounded hover:bg-red-500/20 text-neutral-500 hover:text-red-400"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              
              {/* Available STT Models to Download */}
              <h4 className="text-[10px] text-neutral-500 uppercase tracking-wide mb-2">
                Available for Download
              </h4>
              <div className="space-y-2">
                {availableSTTModels.map(model => (
                  <div
                    key={model.name}
                    className="flex items-center justify-between p-3 bg-neutral-900/30 rounded-lg"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <Globe className="w-4 h-4 text-neutral-500" />
                        <span className="text-xs text-white">{model.name}</span>
                        {model.installed && (
                          <span className="text-[10px] text-green-400 flex items-center gap-1">
                            <Check className="w-3 h-3" /> Installed
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 mt-1 ml-6 text-[10px] text-neutral-500">
                        <span>{model.language}</span>
                        <span>~{model.size_mb} MB</span>
                      </div>
                      <p className="text-[10px] text-neutral-600 ml-6 mt-0.5">{model.description}</p>
                    </div>
                    
                    {!model.installed && (
                      <button
                        onClick={() => handleDownloadSTT(model.name)}
                        disabled={downloadingSTT !== null}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-500/20 hover:bg-purple-500/30
                                   text-purple-400 text-xs font-medium rounded-lg transition-colors
                                   disabled:opacity-50"
                      >
                        {downloadingSTT === model.name ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Download className="w-3.5 h-3.5" />
                        )}
                        {downloadingSTT === model.name ? 'Downloading...' : 'Download'}
                      </button>
                    )}
                  </div>
                ))}
              </div>
              
              {/* STT Download Progress */}
              {sttDownloadProgress && (
                <div className="mt-3 p-3 bg-neutral-900/50 border border-purple-500/20 rounded-lg animate-fadeIn">
                  <div className="flex items-center gap-2 text-xs text-purple-400">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Downloading {sttDownloadProgress.model_name}...</span>
                  </div>
                  {sttDownloadProgress.message && (
                    <p className="text-[10px] text-neutral-500 mt-1">{sttDownloadProgress.message}</p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
