import { useState, useRef, useEffect } from 'react'
import { useApp } from '../contexts/AppContext'
import { useToast } from '../contexts/ToastContext'
import { chatAPI, modelsAPI } from '../lib/api'
import ReactMarkdown from 'react-markdown'
import { 
  Menu, Send, Square, User, Bot, Sparkles, 
  Code, Lightbulb, Wand2, MessageSquare, Zap, Copy, Check,
  ChevronDown, Loader2, Box
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
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const abortControllerRef = useRef(null)
  const dropdownRef = useRef(null)

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
    setLoadingModelId(modelKey)
    setShowModelDropdown(false)
    
    try {
      await modelsAPI.loadModel(model.model_id, model.quantization)
      setLoadedModel(modelKey)
      toast.success(`Loaded ${model.model_id} (${model.quantization || 'fp32'})`)
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

  const handleSend = async () => {
    if (!input.trim() || isGenerating) return
    if (!loadedModel) {
      toast.error('No model loaded. Go to Models and load one first.')
      return
    }

    const userMessage = input.trim()
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
      
      const requestData = {
        message: userMessage,
        conversation_id: currentConversation?.id || null,
        model: loadedModel,
        profile_id: currentProfile?.id || null,
      }

      let fullContent = ''
      let conversationId = currentConversation?.id

      for await (const { event, data } of chatAPI.sendMessage(requestData)) {
        if (event === 'start') {
          conversationId = data.conversation_id
        } else if (event === 'token') {
          fullContent += data.token || data.content || ''
          setStreamingContent(fullContent)
        } else if (event === 'done') {
          // Reload the conversation to get proper message IDs
          if (conversationId) {
            await loadConversation(conversationId)
            await loadConversations()
          }
        } else if (event === 'error') {
          throw new Error(data.error || 'Generation failed')
        }
      }
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

  const handleStop = () => {
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
                  className="absolute top-full left-0 mt-1 w-64 max-h-64 overflow-y-auto bg-neutral-900 border border-white/10 rounded-lg shadow-2xl z-[100] animate-fadeIn"
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
                      {localModels.map((model) => {
                        const modelKey = getModelKey(model)
                        const isLoaded = loadedModel === modelKey
                        const isLoading = loadingModelId === modelKey
                        const shortName = model.model_id.split('/').pop()
                        
                        return (
                          <div
                            key={modelKey}
                            onClick={() => {
                              if (!isLoaded && !isLoading) {
                                handleLoadModel(model)
                              }
                            }}
                            className={`flex items-center gap-2 px-3 py-2.5 transition-all select-none ${
                              isLoaded 
                                ? 'bg-green-500/10 text-green-400' 
                                : isLoading
                                  ? 'bg-blue-500/10 text-blue-400 cursor-wait'
                                  : 'hover:bg-white/10 text-neutral-300 active:bg-white/20 cursor-pointer'
                            }`}
                          >
                            {isLoading ? (
                              <Loader2 className="w-4 h-4 animate-spin text-blue-400 flex-shrink-0" />
                            ) : isLoaded ? (
                              <Check className="w-4 h-4 text-green-400 flex-shrink-0" />
                            ) : (
                              <Box className="w-4 h-4 text-neutral-500 flex-shrink-0" />
                            )}
                            <div className="flex-1 min-w-0">
                              <div className="text-xs font-medium truncate">{shortName}</div>
                              <div className="flex items-center gap-2 text-[10px] text-neutral-500">
                                <span className="px-1 py-0.5 bg-white/5 rounded">{model.quantization || 'default'}</span>
                                <span>{model.size_formatted}</span>
                              </div>
                            </div>
                          </div>
                        )
                      })}
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
                  <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0
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
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            
            {/* Streaming Message */}
            {streamingContent && (
              <MessageBubble 
                message={{
                  id: 'streaming',
                  role: 'assistant',
                  content: streamingContent,
                }}
                isStreaming
              />
            )}
            
            {/* Typing indicator when generating starts */}
            {isGenerating && !streamingContent && (
              <div className="flex gap-4">
                <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center">
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
                           min-h-[48px] max-h-[200px] transition-all"
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
          
          <p className="text-[10px] text-neutral-600 text-center mt-2">
            Press <kbd className="px-1 py-0.5 bg-white/5 rounded text-neutral-500">Enter</kbd> to send, 
            <kbd className="px-1 py-0.5 bg-white/5 rounded text-neutral-500 ml-1">Shift+Enter</kbd> for new line
          </p>
        </div>
      </div>
    </div>
  )
}

// Message Bubble Component
function MessageBubble({ message, isStreaming }) {
  const isUser = message.role === 'user'
  const [copied, setCopied] = useState(false)
  
  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  
  return (
    <div className={`flex gap-4 animate-fadeIn ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div className={`
        flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center
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
            inline-block px-4 py-3 rounded-2xl text-sm
            ${isUser 
              ? 'bg-red-500 text-white rounded-tr-sm' 
              : 'bg-white/5 border border-white/10 text-neutral-200 rounded-tl-sm'}
          `}>
            {isUser ? (
              <p className="whitespace-pre-wrap">{message.content}</p>
            ) : (
              <div className="prose prose-sm prose-invert max-w-none">
                <ReactMarkdown>{message.content}</ReactMarkdown>
                {isStreaming && (
                  <span className="inline-block w-2 h-5 bg-red-400 animate-pulse ml-0.5 align-middle" />
                )}
              </div>
            )}
          </div>
          
          {/* Copy button for assistant messages */}
          {!isUser && !isStreaming && (
            <button
              onClick={handleCopy}
              className="absolute -bottom-6 left-0 flex items-center gap-1 px-2 py-1 
                         text-[10px] text-neutral-500 hover:text-neutral-300
                         opacity-0 group-hover:opacity-100 transition-opacity"
            >
              {copied ? (
                <>
                  <Check className="w-3 h-3 text-green-400" />
                  <span className="text-green-400">Copied!</span>
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3" />
                  <span>Copy</span>
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
