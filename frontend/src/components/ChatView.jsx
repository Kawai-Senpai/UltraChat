import { useState, useRef, useEffect } from 'react'
import { useApp } from '../contexts/AppContext'
import { useToast } from '../contexts/ToastContext'
import { chatAPI, modelsAPI } from '../lib/api'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import { 
  Menu, Send, Square, User, Bot, Sparkles, 
  Code, Lightbulb, Wand2, MessageSquare, Zap, Copy, Check,
  ChevronDown, Loader2, Box, Brain, Globe, Pencil, RotateCcw, ChevronLeft, ChevronRight, X,
  BookOpen, Link, Calculator, Settings2
} from 'lucide-react'

export default function ChatView({ onToggleSidebar }) {
  const { 
    currentConversation, 
    messages, 
    setMessages, 
    isGenerating, 
    setIsGenerating,
    loadedModel,
    setLoadedModel,
    currentProfile,
    setCurrentConversation,
    loadConversations,
    loadConversation,
    localModels,
    loadLocalModels,
    loadSystemStatus,
  } = useApp()
  const { toast } = useToast()
  
  const [input, setInput] = useState('')
  const [streamingContent, setStreamingContent] = useState('')
  const [showModelDropdown, setShowModelDropdown] = useState(false)
  const [loadingModelId, setLoadingModelId] = useState(null)
  const [enableThinking, setEnableThinking] = useState(true)
  const [useWebSearch, setUseWebSearch] = useState(false)
  const [useWikipedia, setUseWikipedia] = useState(false)
  const [useWebFetch, setUseWebFetch] = useState(false)
  const [useCalculator, setUseCalculator] = useState(false)
  const [useMemory, setUseMemory] = useState(true)
  const [showToolsPanel, setShowToolsPanel] = useState(false)
  const [editingMessageId, setEditingMessageId] = useState(null)
  const [editContent, setEditContent] = useState('')
  const [branchCutoffIndex, setBranchCutoffIndex] = useState(null)
  const [loadQuantSelections, setLoadQuantSelections] = useState({})
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const abortControllerRef = useRef(null)
  const dropdownRef = useRef(null)

  const LOAD_QUANT_OPTIONS = [
    { value: 'original', label: 'Original' },
    { value: '4bit', label: '4-bit' },
    { value: '8bit', label: '8-bit' },
    { value: 'fp16', label: 'FP16' },
  ]

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

  // Load models on mount
  useEffect(() => {
    loadLocalModels()
  }, [loadLocalModels])

  // Close dropdown when clicking outside (use click instead of mousedown)
  useEffect(() => {
    const handleClickOutside = (event) => {
      // Small delay to allow button clicks to process first
      setTimeout(() => {
        if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
          setShowModelDropdown(false)
        }
      }, 0)
    }
    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  }, [])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  // Get model key for comparison
  const getModelKey = (model) => {
    return model.quantization ? `${model.model_id}__${model.quantization}` : model.model_id
  }

  // Handle model loading from dropdown
  const handleLoadModel = async (model) => {
    const modelKey = getModelKey(model)
    const requestedQuant = getLoadQuantization(model)
    const loadQuant = requestedQuant === 'original' ? null : requestedQuant
    setLoadingModelId(modelKey)
    setShowModelDropdown(false)
    
    try {
      const result = await modelsAPI.loadModel(model.model_id, loadQuant)
      const loadedKey = result?.quantization ? `${result.model_id}__${result.quantization}` : result?.model_id
      setLoadedModel(loadedKey || modelKey)
      toast.success(`Loaded ${result?.model_id || model.model_id} (${result?.quantization || 'original'})`)
      await loadSystemStatus()
    } catch (error) {
      toast.error('Failed to load model: ' + error.message)
    } finally {
      setLoadingModelId(null)
    }
  }

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const [toolEvents, setToolEvents] = useState([])

  const processStream = async (streamIterator) => {
    let fullContent = ''
    let conversationId = currentConversation?.id

    for await (const { event, data } of streamIterator) {
      // Debug: log all events
      console.log('[SSE Event]', event, JSON.stringify(data).slice(0, 200))
      
      if (event === 'start') {
        console.log('[SSE] Start event received')
        conversationId = data.conversation_id
      } else if (event === 'status') {
        if (data?.conversation_id) {
          conversationId = data.conversation_id
          setCurrentConversation(prev => {
            if (prev?.id === data.conversation_id) return prev
            return { ...(prev || {}), id: data.conversation_id }
          })
        }
        // Tool thinking stream - accumulate thinking for next tool call
        if (data?.status === 'tool_thinking_delta' && data?.delta) {
          console.log('[SSE] Tool thinking delta received:', data.delta.slice(0, 50))
          const round = data.round || 1
          setToolEvents(prev => {
            const updated = [...prev]
            // Find or create a pending thinking accumulator for this round
            const reverseIndex = [...updated].reverse().findIndex(
              (item) => item.type === 'thinking_pending' && item.round === round
            )
            if (reverseIndex !== -1) {
              const targetIndex = updated.length - 1 - reverseIndex
              updated[targetIndex] = {
                ...updated[targetIndex],
                thinking: (updated[targetIndex].thinking || '') + data.delta,
              }
              return updated
            }
            return [
              ...updated,
              {
                id: `thinking-pending-${round}-${Date.now()}`,
                type: 'thinking_pending',
                round,
                thinking: data.delta,
                timestamp: Date.now(),
              }
            ]
          })
        }

        if (data?.status === 'tool_call' && data?.tool) {
          console.log('[SSE] Tool call received:', data.tool, data.arguments)
          const round = data.round || 1
          setToolEvents(prev => {
            const updated = [...prev]
            // Find any pending thinking for this round and attach to the tool call
            let thinkingContent = ''
            const thinkingIndex = updated.findIndex(
              (item) => item.type === 'thinking_pending' && item.round === round
            )
            if (thinkingIndex !== -1) {
              thinkingContent = updated[thinkingIndex].thinking || ''
              updated.splice(thinkingIndex, 1) // Remove the pending thinking item
            }
            updated.push({
              id: `${data.tool}-${round}-${Date.now()}`,
              type: 'call',
              tool: data.tool,
              arguments: data.arguments || {},
              thinking: thinkingContent, // Attach thinking to the tool call
              round,
              timestamp: Date.now(),
            })
            return updated
          })
        }

        if (data?.status === 'tool_result' && data?.tool) {
          console.log('[SSE] Tool result received:', data.tool, data.result?.slice(0, 100))
          setToolEvents(prev => {
            const updated = [...prev]
            const reverseIndex = [...updated].reverse().findIndex(
              (item) => item.type === 'call' && item.tool === data.tool && !item.result
            )
            if (reverseIndex !== -1) {
              const targetIndex = updated.length - 1 - reverseIndex
              updated[targetIndex] = {
                ...updated[targetIndex],
                result: data.result || data.result_preview || '',
                status: 'complete',
              }
              return updated
            }
            return [
              ...updated,
              {
                id: `${data.tool}-result-${data.round || 1}-${Date.now()}`,
                type: 'result',
                tool: data.tool,
                result: data.result || data.result_preview || '',
                round: data.round || 1,
                timestamp: Date.now(),
              }
            ]
          })
        }
      } else if (event === 'token') {
        console.log('[SSE] Token received:', (data.token || data.content || '').slice(0, 30))
        fullContent += data.token || data.content || ''
        setStreamingContent(fullContent)
      } else if (event === 'done') {
        console.log('[SSE] Done event received:', data)
        if (data?.conversation_id) {
          conversationId = data.conversation_id
          setCurrentConversation(prev => {
            if (prev?.id === data.conversation_id) return prev
            return { ...(prev || {}), id: data.conversation_id }
          })
        }
        if (conversationId) {
          await loadConversation(conversationId)
          await loadConversations()
        }
        setToolEvents([])
      } else if (event === 'error') {
        console.log('[SSE] Error event received:', data)
        throw new Error(data.error || 'Generation failed')
      }
    }
  }

  const handleSend = async () => {
    if (!input.trim() || isGenerating) return
    if (!loadedModel) {
      toast.error('No model loaded. Go to Models and load one first.')
      return
    }

    const userMessage = input.trim()
    setToolEvents([])
    setInput('')
    setIsGenerating(true)
    setStreamingContent('')

    // Add user message to UI immediately
    const tempUserMsg = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: userMessage,
      created_at: new Date().toISOString(),
    }
    setMessages(prev => [...prev, tempUserMsg])

    try {
      abortControllerRef.current = new AbortController()

      const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null
      
      // Build enabled tools list
      const enabledTools = []
      if (useWebSearch) enabledTools.push('web_search')
      if (useWikipedia) enabledTools.push('wikipedia')
      if (useWebFetch) enabledTools.push('web_fetch')
      if (useCalculator) enabledTools.push('calculator')
      
      const requestData = {
        message: userMessage,
        conversation_id: currentConversation?.id || null,
        parent_id: lastMessage?.id || null,
        model: loadedModel,
        profile_id: currentProfile?.id || null,
        web_search: useWebSearch,
        use_memory: useMemory,
        enable_thinking: enableThinking,
        tools: enabledTools.length > 0 ? enabledTools : null,
      }

      const streamIterator = chatAPI.sendMessage(requestData, {
        signal: abortControllerRef.current?.signal,
      })
      await processStream(streamIterator)
    } catch (error) {
      if (error.name !== 'AbortError') {
        toast.error(error.message || 'Failed to send message')
        // Remove the temp user message on error
        setMessages(prev => prev.filter(m => m.id !== tempUserMsg.id))
      }
    } finally {
      setIsGenerating(false)
      setStreamingContent('')
      abortControllerRef.current = null
    }
  }

  const handleEditStart = (message) => {
    setEditingMessageId(message.id)
    setEditContent(message.content)
    const index = messages.findIndex(m => m.id === message.id)
    setBranchCutoffIndex(index >= 0 ? index : null)
  }

  const handleEditCancel = () => {
    setEditingMessageId(null)
    setEditContent('')
    setBranchCutoffIndex(null)
  }

  const handleEditSave = async (messageId) => {
    if (!editContent.trim()) {
      toast.error('Message cannot be empty')
      return
    }
    if (!loadedModel) {
      toast.error('No model loaded. Go to Models and load one first.')
      return
    }

    setToolEvents([])
    setIsGenerating(true)
    setStreamingContent('')

    try {
      abortControllerRef.current = new AbortController()
      const streamIterator = chatAPI.editMessage(
        messageId,
        editContent,
        loadedModel,
        { signal: abortControllerRef.current?.signal }
      )
      await processStream(streamIterator)
    } catch (error) {
      if (error.name !== 'AbortError') {
        toast.error(error.message || 'Failed to edit message')
      }
    } finally {
      setIsGenerating(false)
      setStreamingContent('')
      abortControllerRef.current = null
      setEditingMessageId(null)
      setEditContent('')
      setBranchCutoffIndex(null)
    }
  }

  const handleRegenerate = async (messageId) => {
    if (!loadedModel) {
      toast.error('No model loaded. Go to Models and load one first.')
      return
    }

    const index = messages.findIndex(m => m.id === messageId)
    const parentIndex = index > 0 ? index - 1 : index
    setBranchCutoffIndex(parentIndex >= 0 ? parentIndex : null)

    setToolEvents([])
    setIsGenerating(true)
    setStreamingContent('')

    try {
      abortControllerRef.current = new AbortController()
      const streamIterator = chatAPI.regenerate(
        { message_id: messageId, model: loadedModel },
        { signal: abortControllerRef.current?.signal }
      )
      await processStream(streamIterator)
    } catch (error) {
      if (error.name !== 'AbortError') {
        toast.error(error.message || 'Failed to regenerate response')
      }
    } finally {
      setIsGenerating(false)
      setStreamingContent('')
      abortControllerRef.current = null
      setBranchCutoffIndex(null)
    }
  }

  const handleBranchNavigate = async (messageId, direction) => {
    try {
      await chatAPI.navigateBranch(messageId, direction)
      if (currentConversation?.id) {
        await loadConversation(currentConversation.id)
        await loadConversations()
      }
    } catch (error) {
      toast.error(error.message || 'Failed to switch branch')
    }
  }

  const handleStop = () => {
    try {
      chatAPI.stopGeneration()
    } catch {
      // Ignore stop errors
    }
    abortControllerRef.current?.abort()
    setIsGenerating(false)
    setStreamingContent('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const hints = [
    { 
      icon: Lightbulb, 
      text: 'Explain a concept', 
      prompt: 'Explain quantum computing in simple terms',
      color: 'yellow'
    },
    { 
      icon: Code, 
      text: 'Write code', 
      prompt: 'Write a Python script that reads a CSV and plots a chart',
      color: 'blue'
    },
    { 
      icon: Wand2, 
      text: 'Brainstorm ideas', 
      prompt: 'Help me brainstorm ideas for a mobile app',
      color: 'purple'
    },
    { 
      icon: MessageSquare, 
      text: 'Analyze text', 
      prompt: 'Summarize and analyze the following text:',
      color: 'green'
    },
  ]

  const displayedMessages = branchCutoffIndex !== null
    ? messages.slice(0, branchCutoffIndex + 1)
    : messages

  return (
    <div className="flex flex-col h-full bg-neutral-950">
      {/* Header */}
      <header className="flex items-center gap-3 px-4 py-3 border-b border-white/10 bg-neutral-900/80 backdrop-blur-sm overflow-visible relative z-50">
        <button
          onClick={onToggleSidebar}
          className="md:hidden p-2 rounded-lg hover:bg-white/10 text-neutral-400 transition-colors"
        >
          <Menu className="w-5 h-5" />
        </button>
        
        <div className="flex-1 min-w-0 overflow-visible">
          <h1 className="text-sm font-black text-white truncate">
            {currentConversation?.title || 'New Chat'}
          </h1>
          <div className="flex items-center gap-2 mt-0.5 overflow-visible">
            {/* Model Selector Dropdown */}
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setShowModelDropdown(!showModelDropdown)}
                disabled={loadingModelId !== null}
                className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full transition-all cursor-pointer ${
                  loadedModel 
                    ? 'bg-green-500/10 border border-green-500/20 hover:bg-green-500/20' 
                    : 'bg-yellow-500/10 border border-yellow-500/20 hover:bg-yellow-500/20'
                }`}
              >
                {loadingModelId ? (
                  <Loader2 className="w-3 h-3 text-blue-400 animate-spin" />
                ) : loadedModel ? (
                  <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                ) : (
                  <div className="w-1.5 h-1.5 rounded-full bg-yellow-400" />
                )}
                <span className={`text-[10px] font-medium truncate max-w-24 ${
                  loadedModel ? 'text-green-400' : 'text-yellow-400'
                }`}>
                  {loadingModelId ? 'Loading...' : loadedModel ? loadedModel.split('__')[0].split('/').pop() : 'Select model'}
                </span>
                <ChevronDown className={`w-3 h-3 transition-transform ${
                  showModelDropdown ? 'rotate-180' : ''
                } ${loadedModel ? 'text-green-400' : 'text-yellow-400'}`} />
              </button>
              
              {/* Dropdown Menu */}
              {showModelDropdown && (
                <div 
                  className="absolute top-full left-0 mt-1 w-64 max-h-72 overflow-y-auto bg-neutral-900 border border-white/10 rounded-lg shadow-2xl z-50 animate-fadeIn"
                  onMouseDown={(e) => e.stopPropagation()}
                >
                  {localModels.length === 0 ? (
                    <div className="p-3 text-center">
                      <Box className="w-6 h-6 mx-auto mb-2 text-neutral-600" />
                      <p className="text-[10px] text-neutral-500">No models downloaded</p>
                      <p className="text-[10px] text-neutral-600">Go to Models tab to download</p>
                    </div>
                  ) : (
                    <div className="py-1">
                      {(() => {
                        const hasExactLoadedEntry = loadedModel
                          ? localModels.some((model) => getModelKey(model) === loadedModel)
                          : false

                        return localModels.map((model) => {
                          const modelKey = getModelKey(model)
                          const isLoaded = loadedModel === modelKey || (!hasExactLoadedEntry && !model.quantization && loadedModel?.startsWith(`${model.model_id}__`))
                          const isLoading = loadingModelId === modelKey
                          const shortName = model.model_id.split('/').pop()
                          
                          return (
                            <div
                              key={modelKey}
                              className={`px-3 py-2.5 transition-all select-none ${
                                isLoaded 
                                  ? 'bg-green-500/10' 
                                  : isLoading
                                    ? 'bg-blue-500/10'
                                    : 'hover:bg-white/5'
                              }`}
                            >
                              <div className="flex items-center gap-2">
                                {isLoading ? (
                                  <Loader2 className="w-4 h-4 animate-spin text-blue-400 shrink-0" />
                                ) : isLoaded ? (
                                  <Check className="w-4 h-4 text-green-400 shrink-0" />
                                ) : (
                                  <Box className="w-4 h-4 text-neutral-500 shrink-0" />
                                )}
                                <div className="flex-1 min-w-0">
                                  <div className={`text-xs font-medium truncate ${isLoaded ? 'text-green-400' : 'text-neutral-300'}`}>{shortName}</div>
                                  <div className="flex items-center gap-2 text-[10px] text-neutral-500">
                                    <span className="px-1 py-0.5 bg-white/5 rounded">{model.quantization || 'original'}</span>
                                    <span>{model.size_formatted}</span>
                                  </div>
                                </div>
                              </div>
                              {!isLoaded && (
                                <div className="mt-2 flex items-center gap-2 pl-6">
                                  <select
                                    value={getLoadQuantization(model)}
                                    onChange={(e) => {
                                      e.stopPropagation()
                                      setLoadQuantization(model, e.target.value)
                                    }}
                                    onClick={(e) => e.stopPropagation()}
                                    disabled={!!model.quantization}
                                    className="bg-neutral-800 border border-white/10 rounded px-1.5 py-0.5 text-[10px] text-neutral-200
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
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation()
                                      if (!isLoading) handleLoadModel(model)
                                    }}
                                    disabled={isLoading}
                                    className="px-2 py-0.5 bg-green-500/20 hover:bg-green-500/30 text-green-400 text-[10px] font-medium rounded transition-colors disabled:opacity-50"
                                  >
                                    {isLoading ? 'Loading...' : 'Load'}
                                  </button>
                                </div>
                              )}
                            </div>
                          )
                        })
                      })()}
                    </div>
                  )}
                </div>
              )}
            </div>
            
            {currentProfile && (
              <div className="flex items-center gap-1 px-2 py-0.5 bg-white/5 border border-white/10 rounded-full">
                <User className="w-3 h-3 text-neutral-400" />
                <span className="text-[10px] text-neutral-400">{currentProfile.name}</span>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 && !streamingContent ? (
          // Welcome Screen
          <div className="flex flex-col items-center justify-center h-full p-6 animate-fadeIn">
            {/* Hero */}
            <div className="relative mb-8">
              <div className="w-20 h-20 rounded-2xl bg-red-500/20 flex items-center justify-center">
                <Zap className="w-10 h-10 text-red-400" />
              </div>
              <div className="absolute -top-1 -right-1 w-6 h-6 rounded-full bg-green-500/20 flex items-center justify-center">
                <Sparkles className="w-3 h-3 text-green-400" />
              </div>
            </div>
            
            <h2 className="text-2xl md:text-3xl font-black text-white mb-3 text-center">
              Welcome to UltraChat
            </h2>
            <p className="text-sm text-neutral-400 mb-2 text-center max-w-md">
              Your local AI assistant powered by state-of-the-art language models.
            </p>
            {!loadedModel && (
              <p className="text-xs text-yellow-400/80 mb-8 text-center">
                ⚠️ Load a model from the Models page to start chatting
              </p>
            )}
            
            {/* Quick Start Hints */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg w-full">
              {hints.map((hint, i) => (
                <button
                  key={i}
                  onClick={() => setInput(hint.prompt)}
                  disabled={!loadedModel}
                  className="group flex items-start gap-3 p-4 text-left 
                             bg-white/5 hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed
                             border border-white/10 hover:border-white/20 
                             rounded-xl transition-all duration-200"
                >
                  <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0
                    ${hint.color === 'yellow' ? 'bg-yellow-500/20' : ''}
                    ${hint.color === 'blue' ? 'bg-blue-500/20' : ''}
                    ${hint.color === 'purple' ? 'bg-purple-500/20' : ''}
                    ${hint.color === 'green' ? 'bg-green-500/20' : ''}
                  `}>
                    <hint.icon className={`w-4 h-4
                      ${hint.color === 'yellow' ? 'text-yellow-400' : ''}
                      ${hint.color === 'blue' ? 'text-blue-400' : ''}
                      ${hint.color === 'purple' ? 'text-purple-400' : ''}
                      ${hint.color === 'green' ? 'text-green-400' : ''}
                    `} />
                  </div>
                  <div>
                    <span className="text-xs font-bold text-white block mb-0.5">{hint.text}</span>
                    <span className="text-[10px] text-neutral-500 line-clamp-1">{hint.prompt}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        ) : (
          // Messages List
          <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
            {displayedMessages.map((msg) => (
              <MessageBubble
                key={msg.id}
                message={msg}
                isEditing={editingMessageId === msg.id}
                editContent={editContent}
                setEditContent={setEditContent}
                onEditStart={handleEditStart}
                onEditCancel={handleEditCancel}
                onEditSave={handleEditSave}
                onRegenerate={handleRegenerate}
                onBranchNavigate={handleBranchNavigate}
                toolEvents={[]}
              />
            ))}
            
            {/* Live Tool Events */}
            {toolEvents && toolEvents.length > 0 && (
              <div className="space-y-2">
                {toolEvents.map((item, index) => (
                  <ToolEventBubble key={item.id || `${item.tool}-${index}`} item={item} live />
                ))}
              </div>
            )}
            
            {/* Streaming Message */}
            {streamingContent && (
              <MessageBubble 
                message={{
                  id: 'streaming',
                  role: 'assistant',
                  content: streamingContent,
                }}
                isStreaming
                toolEvents={[]}
              />
            )}
            
            {/* Typing indicator when generating starts */}
            {isGenerating && !streamingContent && (!toolEvents || toolEvents.length === 0) && (
              <div className="flex gap-4">
                <div className="shrink-0 w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center">
                  <Bot className="w-4 h-4 text-neutral-400" />
                </div>
                <div className="flex items-center gap-1 px-4 py-3 bg-white/5 rounded-2xl rounded-tl-sm">
                  <div className="w-2 h-2 rounded-full bg-neutral-500 typing-dot" />
                  <div className="w-2 h-2 rounded-full bg-neutral-500 typing-dot" />
                  <div className="w-2 h-2 rounded-full bg-neutral-500 typing-dot" />
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="border-t border-white/10 p-4 bg-neutral-900/80 backdrop-blur-sm">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-end gap-3">
            <div className="flex-1 relative">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={loadedModel ? "Type your message..." : "Load a model to start chatting..."}
                disabled={!loadedModel || isGenerating}
                rows={1}
                className="w-full px-4 py-3 pr-12 bg-white/5 border border-white/10 rounded-xl
                           text-sm text-white placeholder-neutral-500 resize-none
                           focus:outline-none focus:border-red-500/50
                           disabled:opacity-50 disabled:cursor-not-allowed
                           min-h-12 max-h-50 transition-all"
                style={{ height: 'auto', minHeight: '48px' }}
                onInput={(e) => {
                  e.target.style.height = 'auto'
                  e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px'
                }}
              />
            </div>
            
            {isGenerating ? (
              <button
                onClick={handleStop}
                className="flex items-center justify-center w-12 h-12 
                           bg-red-500 hover:bg-red-600 text-white rounded-xl
                           transition-all hover:scale-105 active:scale-95"
              >
                <Square className="w-4 h-4" fill="currentColor" />
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!input.trim() || !loadedModel}
                className="flex items-center justify-center w-12 h-12 
                           bg-red-500 hover:bg-red-600 disabled:bg-neutral-800 disabled:text-neutral-600
                           text-white rounded-xl transition-all
                           hover:scale-105 active:scale-95
                           disabled:cursor-not-allowed disabled:hover:scale-100"
              >
                <Send className="w-4 h-4" />
              </button>
            )}
          </div>
          
          <div className="flex flex-wrap items-center justify-between gap-2 mt-3">
            <div className="flex flex-wrap items-center gap-2">
              <TogglePill
                label="Thinking"
                icon={Lightbulb}
                active={enableThinking}
                onClick={() => setEnableThinking(prev => !prev)}
                description="Enable/disable model thinking"
              />
              <TogglePill
                label="Memory"
                icon={Brain}
                active={useMemory}
                onClick={() => setUseMemory(prev => !prev)}
                description="Use saved memory context"
              />
              
              {/* Collapsible Tools Section */}
              <div className="relative">
                <button
                  onClick={() => setShowToolsPanel(prev => !prev)}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-medium transition-all ${
                    (useWebSearch || useWikipedia || useWebFetch || useCalculator)
                      ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                      : 'bg-white/5 text-neutral-400 border border-white/10 hover:bg-white/10'
                  }`}
                >
                  <Settings2 className="w-3 h-3" />
                  <span>Tools</span>
                  {(useWebSearch || useWikipedia || useWebFetch || useCalculator) && (
                    <span className="w-4 h-4 flex items-center justify-center bg-purple-500/30 rounded-full text-[8px]">
                      {[useWebSearch, useWikipedia, useWebFetch, useCalculator].filter(Boolean).length}
                    </span>
                  )}
                  <ChevronDown className={`w-3 h-3 transition-transform ${showToolsPanel ? 'rotate-180' : ''}`} />
                </button>
                
                {showToolsPanel && (
                  <div className="absolute bottom-full left-0 mb-2 p-2 bg-neutral-900 border border-white/10 rounded-lg shadow-2xl z-50 min-w-48 animate-fadeIn">
                    <div className="text-[10px] text-neutral-500 uppercase tracking-wide mb-2 px-1">Agent Tools</div>
                    <div className="space-y-1">
                      <ToolToggleItem
                        label="Web Search"
                        icon={Globe}
                        active={useWebSearch}
                        onClick={() => setUseWebSearch(prev => !prev)}
                        description="DuckDuckGo search"
                      />
                      <ToolToggleItem
                        label="Wikipedia"
                        icon={BookOpen}
                        active={useWikipedia}
                        onClick={() => setUseWikipedia(prev => !prev)}
                        description="Wikipedia search"
                      />
                      <ToolToggleItem
                        label="Web Fetch"
                        icon={Link}
                        active={useWebFetch}
                        onClick={() => setUseWebFetch(prev => !prev)}
                        description="Fetch webpage content"
                      />
                      <ToolToggleItem
                        label="Calculator"
                        icon={Calculator}
                        active={useCalculator}
                        onClick={() => setUseCalculator(prev => !prev)}
                        description="Math calculations"
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
            <p className="text-[10px] text-neutral-600 text-center">
              Press <kbd className="px-1 py-0.5 bg-white/5 rounded text-neutral-500">Enter</kbd> to send, 
              <kbd className="px-1 py-0.5 bg-white/5 rounded text-neutral-500 ml-1">Shift+Enter</kbd> for new line
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

const parseThinkingContent = (raw = '', explicitThinking = '') => {
  if (!raw && !explicitThinking) return { thinking: '', answer: '' }

  const withoutToolCalls = raw.replace(/<tool_call>[\s\S]*?<\/tool_call>/gi, '').trim()

  if (explicitThinking) {
    return { thinking: explicitThinking, answer: withoutToolCalls }
  }

  const blockPattern = /<(think|thinking)>([\s\S]*?)<\/(think|thinking)>/gi
  const openMatch = withoutToolCalls.match(/<(think|thinking)>/i)
  const closeMatch = withoutToolCalls.match(/<\/(think|thinking)>/i)

  let thinkingChunks = []
  let answer = withoutToolCalls.replace(blockPattern, (_m, _t1, content) => {
    thinkingChunks.push(content)
    return ''
  })

  if (openMatch && !closeMatch) {
    const openTag = openMatch[0]
    const start = withoutToolCalls.toLowerCase().indexOf(openTag.toLowerCase())
    const before = withoutToolCalls.slice(0, start)
    const after = withoutToolCalls.slice(start + openTag.length)
    return {
      thinking: after.trim(),
      answer: before.trim(),
    }
  }

  return {
    thinking: thinkingChunks.join('\n\n').trim(),
    answer: answer.trim(),
  }
}

const parseToolCalls = (toolCalls) => {
  if (!toolCalls) return []
  if (Array.isArray(toolCalls)) return toolCalls
  try {
    const parsed = JSON.parse(toolCalls)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

// Message Bubble Component
function MessageBubble({ 
  message, 
  isStreaming, 
  isEditing, 
  editContent, 
  setEditContent,
  onEditStart,
  onEditCancel,
  onEditSave,
  onRegenerate,
  onBranchNavigate,
  toolEvents,
}) {
  const isUser = message.role === 'user'
  const [copied, setCopied] = useState(false)
  const [branchInfo, setBranchInfo] = useState(null)
  const [isBranchLoading, setIsBranchLoading] = useState(false)
  const { thinking, answer } = parseThinkingContent(message.content, message.thinking)
  const [showThinking, setShowThinking] = useState(isStreaming)

  const storedToolCalls = parseToolCalls(message.tool_calls)
  // Merge thinking into tool calls - don't create separate thinking events
  const storedToolEvents = storedToolCalls.map((call, index) => {
    const round = call.round || index + 1
    return {
      id: `stored-${call.name}-${round}`,
      type: 'call',
      tool: call.name,
      arguments: call.arguments || {},
      result: call.result || '',
      thinking: call.thinking || '', // Attach thinking to the tool call
      round,
      status: call.result ? 'complete' : 'running',
    }
  })
  const toolTimelineItems = (toolEvents && toolEvents.length > 0)
    ? toolEvents
    : storedToolEvents
  
  
  useEffect(() => {
    const loadBranches = async () => {
      if (isStreaming || !message?.id || message.id === 'streaming') return
      try {
        const data = await chatAPI.getSiblings(message.id)
        setBranchInfo(data)
      } catch {
        // Ignore branch errors
      }
    }

    loadBranches()
  }, [message?.id, isUser, isStreaming])

  const handleCopy = async () => {
    const toCopy = isUser ? message.content : (answer || message.content)
    await navigator.clipboard.writeText(toCopy)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleNavigate = async (direction) => {
    if (!message?.id) return
    setIsBranchLoading(true)
    try {
      await onBranchNavigate(message.id, direction)
      const data = await chatAPI.getSiblings(message.id)
      setBranchInfo(data)
    } finally {
      setIsBranchLoading(false)
    }
  }
  
  return (
    <div className="space-y-3">
      {/* Tool calls displayed BEFORE the message bubble */}
      {!isUser && toolTimelineItems.length > 0 && (
        <div className="ml-12 space-y-2">
          {toolTimelineItems.filter(item => item.type === 'call').map((item, index) => (
            <ToolEventBubble key={item.id || `${item.tool}-${index}`} item={item} />
          ))}
        </div>
      )}
      
      <div className={`flex gap-4 animate-fadeIn ${isUser ? 'flex-row-reverse' : ''}`}>
        {/* Avatar */}
        <div className={`
          shrink-0 w-8 h-8 rounded-lg flex items-center justify-center
          ${isUser ? 'bg-red-500/20' : 'bg-white/10'}
        `}>
          {isUser ? (
            <User className="w-4 h-4 text-red-400" />
          ) : (
            <Bot className="w-4 h-4 text-neutral-400" />
          )}
        </div>
        
        {/* Content */}
        <div className={`flex-1 min-w-0 max-w-[85%] ${isUser ? 'flex justify-end' : ''}`}>
          <div className="relative group">
            <div className={`
              inline-block px-4 py-3 rounded-2xl text-xs
              ${isUser 
                ? 'bg-red-500 text-white rounded-tr-sm' 
                : 'bg-white/5 border border-white/10 text-neutral-200 rounded-tl-sm'}
            `}>
              {isUser ? (
                isEditing ? (
                  <div className="space-y-2">
                    <textarea
                      value={editContent}
                      onChange={(e) => setEditContent(e.target.value)}
                      rows={3}
                      className="w-full bg-white/5 border border-white/10 rounded-lg p-2 text-xs text-white resize-none
                                 focus:outline-none focus:border-red-500/50"
                    />
                    <div className="flex items-center gap-2">
                      <button
                      onClick={() => onEditSave(message.id)}
                      title="Save & Regenerate"
                      className="p-2 rounded-md bg-red-500 text-white hover:bg-red-600"
                    >
                      <Check className="w-3 h-3" />
                    </button>
                    <button
                      onClick={onEditCancel}
                      title="Cancel"
                      className="p-2 rounded-md bg-white/10 text-neutral-300 hover:bg-white/20"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              ) : (
                <p className="whitespace-pre-wrap">{message.content}</p>
              )
            ) : (
              <div className="space-y-3">
                {thinking && (
                  <div className="border border-white/10 rounded-lg bg-white/3">
                    <button
                      onClick={() => setShowThinking(prev => !prev)}
                      className="w-full flex items-center justify-between px-3 py-2 text-[10px] text-neutral-400 hover:text-neutral-200"
                    >
                      <span className="font-medium">Thinking</span>
                      <ChevronDown className={`w-3 h-3 transition-transform ${showThinking ? 'rotate-180' : ''}`} />
                    </button>
                    {showThinking && (
                      <div className="px-3 pb-3 text-[11px] text-neutral-300 whitespace-pre-wrap">
                        {thinking}
                      </div>
                    )}
                  </div>
                )}
                <div className="prose prose-invert max-w-none text-xs prose-li:my-0.5 prose-ul:my-1 prose-ol:my-1 prose-p:my-1.5 prose-headings:my-2">
                  <ReactMarkdown 
                    remarkPlugins={[remarkGfm, remarkMath]} 
                    rehypePlugins={[rehypeKatex]}
                  >
                    {answer || ''}
                  </ReactMarkdown>
                  {isStreaming && (
                    <span className="inline-block w-2 h-5 bg-red-400 animate-pulse ml-0.5 align-middle" />
                  )}
                </div>
              </div>
            )}
          </div>

          {!isStreaming && !isEditing && (
            <div className="mt-2 flex items-center gap-3 text-[10px] text-neutral-500 opacity-0 group-hover:opacity-100 transition-opacity">
              {isUser ? (
                <button
                  onClick={() => onEditStart(message)}
                  title="Edit"
                  className="hover:text-white"
                >
                  <Pencil className="w-3 h-3" />
                </button>
              ) : (
                <>
                  <button
                    onClick={() => onRegenerate(message.id)}
                    title="Regenerate"
                    className="hover:text-white"
                  >
                    <RotateCcw className="w-3 h-3" />
                  </button>
                  <button
                    onClick={handleCopy}
                    title={copied ? 'Copied' : 'Copy'}
                    className="hover:text-white"
                  >
                    {copied ? (
                      <Check className="w-3 h-3 text-green-400" />
                    ) : (
                      <Copy className="w-3 h-3" />
                    )}
                  </button>
                </>
              )}
              {branchInfo?.total > 1 && (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleNavigate('prev')}
                    disabled={isBranchLoading || branchInfo.current_index === 0}
                    title="Previous branch"
                    className="hover:text-white disabled:opacity-40"
                  >
                    <ChevronLeft className="w-3 h-3" />
                  </button>
                  <span className="text-neutral-400">
                    {branchInfo.current_index + 1}/{branchInfo.total}
                  </span>
                  <button
                    onClick={() => handleNavigate('next')}
                    disabled={isBranchLoading || branchInfo.current_index === branchInfo.total - 1}
                    title="Next branch"
                    className="hover:text-white disabled:opacity-40"
                  >
                    <ChevronRight className="w-3 h-3" />
                  </button>
                </div>
              )}
            </div>
          )}
          
        </div>
      </div>
    </div>
    </div>
  )
}

function TogglePill({ label, icon: Icon, active, onClick, description }) {
  return (
    <button
      onClick={onClick}
      title={description}
      className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-medium transition-colors
        ${active ? 'bg-red-500/20 text-red-300 border border-red-500/30' : 'bg-white/5 text-neutral-400 border border-white/10 hover:bg-white/10'}`}
    >
      <Icon className="w-3 h-3" />
      {label}
    </button>
  )
}

function ToolToggleItem({ label, icon: Icon, active, onClick, description }) {
  return (
    <button
      onClick={onClick}
      title={description}
      className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-[10px] font-medium transition-colors text-left ${
        active 
          ? 'bg-purple-500/20 text-purple-300' 
          : 'text-neutral-400 hover:bg-white/5 hover:text-neutral-200'
      }`}
    >
      <div className={`w-5 h-5 rounded flex items-center justify-center ${
        active ? 'bg-purple-500/30' : 'bg-white/5'
      }`}>
        <Icon className="w-3 h-3" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="truncate">{label}</div>
        <div className="text-[8px] text-neutral-500 truncate">{description}</div>
      </div>
      <div className={`w-3 h-3 rounded-sm border transition-colors ${
        active ? 'bg-purple-500 border-purple-500' : 'border-neutral-600'
      }`}>
        {active && <Check className="w-3 h-3 text-white" />}
      </div>
    </button>
  )
}

const TOOL_ICON_MAP = {
  web_search: Globe,
  wikipedia: BookOpen,
  web_fetch: Link,
  calculator: Calculator,
  thinking: Brain,
}

const getToolSummary = (item) => {
  const args = item.arguments || {}
  switch (item.tool) {
    case 'web_search':
      return args.query ? `"${args.query}"` : 'Searching...'
    case 'wikipedia':
      return args.query ? `"${args.query}"` : 'Searching...'
    case 'web_fetch':
      return args.url ? args.url.slice(0, 50) + (args.url.length > 50 ? '...' : '') : 'Fetching...'
    case 'calculator':
      return args.expression || 'Calculating...'
    default:
      return item.tool
  }
}

const TOOL_LABELS = {
  web_search: 'Web Search',
  wikipedia: 'Wikipedia',
  web_fetch: 'Web Fetch',
  calculator: 'Calculator',
}

function ToolEventBubble({ item, live = false }) {
  // Only expand thinking by default if still running (live), collapse when complete
  const [showThinking, setShowThinking] = useState(live)
  const [showResult, setShowResult] = useState(false)
  const Icon = TOOL_ICON_MAP[item.tool] || Settings2
  const hasThinking = Boolean(item.thinking?.trim())
  const hasResult = Boolean(item.result)
  const isRunning = !hasResult && (item.status === 'running' || live)
  const isPendingThinking = item.type === 'thinking_pending'
  
  // Collapse thinking when tool completes (has result)
  useEffect(() => {
    if (hasResult && showThinking) {
      setShowThinking(false)
    }
  }, [hasResult])
  
  // Skip rendering standalone thinking items that aren't pending
  if (item.type === 'thinking' && !item.tool) {
    return null
  }
  
  // For pending thinking, show a special "Thinking..." indicator
  if (isPendingThinking) {
    return (
      <div className="flex gap-3 animate-fadeIn">
        <div className="shrink-0 w-7 h-7 rounded-lg bg-purple-500/15 flex items-center justify-center">
          <Lightbulb className="w-3.5 h-3.5 text-purple-400" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-medium text-purple-300">Thinking...</span>
            <Loader2 className="w-3 h-3 text-purple-400 animate-spin" />
          </div>
          {item.thinking?.trim() && (
            <div className="mt-1 p-2 bg-purple-500/10 border border-purple-500/20 rounded-lg text-[10px] text-neutral-300 whitespace-pre-wrap">
              {item.thinking.trim()}
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="flex gap-3 animate-fadeIn">
      {/* Tool Icon */}
      <div className={`shrink-0 w-7 h-7 rounded-lg flex items-center justify-center ${
        hasResult ? 'bg-green-500/15' : 'bg-purple-500/15'
      }`}>
        {isRunning ? (
          <Loader2 className="w-3.5 h-3.5 text-purple-400 animate-spin" />
        ) : (
          <Icon className={`w-3.5 h-3.5 ${hasResult ? 'text-green-400' : 'text-purple-400'}`} />
        )}
      </div>
      
      {/* Tool Card */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium text-neutral-200">
            {TOOL_LABELS[item.tool] || item.tool}
          </span>
          {item.round > 1 && (
            <span className="text-[9px] text-neutral-500 bg-white/5 px-1.5 py-0.5 rounded">
              #{item.round}
            </span>
          )}
          {isRunning && (
            <span className="text-[9px] text-purple-400">Running...</span>
          )}
          {hasResult && !isRunning && (
            <span className="text-[9px] text-green-400">✓</span>
          )}
        </div>
        
        {/* Tool query/expression */}
        <div className="text-[10px] text-neutral-400 truncate mt-0.5">
          {getToolSummary(item)}
        </div>
        
        {/* Expandable sections */}
        <div className="flex items-center gap-3 mt-1.5">
          {hasThinking && (
            <button
              onClick={() => setShowThinking(prev => !prev)}
              className="flex items-center gap-1 text-[9px] text-purple-300 hover:text-purple-200"
            >
              <Lightbulb className="w-3 h-3" />
              <span>{showThinking ? 'Hide thinking' : 'Show thinking'}</span>
            </button>
          )}
          {hasResult && (
            <button
              onClick={() => setShowResult(prev => !prev)}
              className="flex items-center gap-1 text-[9px] text-green-300 hover:text-green-200"
            >
              <ChevronDown className={`w-3 h-3 transition-transform ${showResult ? 'rotate-180' : ''}`} />
              <span>{showResult ? 'Hide result' : 'Show result'}</span>
            </button>
          )}
        </div>
        
        {/* Thinking content */}
        {hasThinking && showThinking && (
          <div className="mt-2 p-2 bg-purple-500/10 border border-purple-500/20 rounded-lg text-[10px] text-neutral-300 whitespace-pre-wrap">
            {item.thinking?.trim()}
          </div>
        )}
        
        {/* Result content */}
        {hasResult && showResult && (
          <div className="mt-2 p-2 bg-green-500/10 border border-green-500/20 rounded-lg text-[10px] text-neutral-300 whitespace-pre-wrap max-h-60 overflow-auto">
            {item.result}
          </div>
        )}
      </div>
    </div>
  )
}
