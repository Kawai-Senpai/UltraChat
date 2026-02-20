import { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { modelsAPI, chatAPI, profilesAPI } from '../lib/api'

const AppContext = createContext(null)

export function AppProvider({ children }) {
  // System state
  const [gpuInfo, setGpuInfo] = useState(null)
  const [loadedModel, setLoadedModel] = useState(null)
  const [assistantModel, setAssistantModel] = useState(null)
  const [localModels, setLocalModels] = useState([])
  
  // Chat state
  const [conversations, setConversations] = useState([])
  const [currentConversation, setCurrentConversation] = useState(null)
  const [messages, setMessages] = useState([])
  const [isGenerating, setIsGenerating] = useState(false)
  
  // Profile state
  const [profiles, setProfiles] = useState([])
  const [currentProfile, setCurrentProfile] = useState(null)
  
  // Load initial data
  useEffect(() => {
    loadSystemStatus()
    loadConversations()
    loadProfiles()
  }, [])

  const loadSystemStatus = useCallback(async () => {
    try {
      const status = await modelsAPI.getStatus()
      setGpuInfo({
        available: status.gpu_available,
        name: status.gpu_name,
        memoryTotal: status.gpu_memory_total, // Already formatted string like "8.0 GB"
        memoryFree: status.gpu_memory_free,   // Already formatted string
        gpu: status.gpu, // Raw GPU info object
      })
      setLoadedModel(status.current_model)
      setAssistantModel(status.current_assistant_model)
    } catch (error) {
      console.error('Failed to load system status:', error)
    }
  }, [])

  const loadLocalModels = useCallback(async () => {
    try {
      const data = await modelsAPI.listModels()
      setLocalModels(data.models || [])
    } catch (error) {
      console.error('Failed to load local models:', error)
    }
  }, [])

  const loadConversations = useCallback(async () => {
    try {
      const data = await chatAPI.listConversations()
      setConversations(data.conversations || [])
    } catch (error) {
      console.error('Failed to load conversations:', error)
    }
  }, [])

  const loadProfiles = useCallback(async () => {
    try {
      const data = await profilesAPI.listProfiles()
      setProfiles(data.profiles || [])
      // Set default profile
      const defaultProfile = data.profiles?.find(p => p.is_default)
      if (defaultProfile) {
        setCurrentProfile(defaultProfile)
      }
    } catch (error) {
      console.error('Failed to load profiles:', error)
    }
  }, [])

  const loadConversation = useCallback(async (conversationId) => {
    if (!conversationId) {
      setCurrentConversation(null)
      setMessages([])
      return
    }
    
    try {
      const data = await chatAPI.getConversation(conversationId)
      setCurrentConversation(data)
      setMessages(data.messages || [])
    } catch (error) {
      console.error('Failed to load conversation:', error)
    }
  }, [])

  const value = {
    // System
    gpuInfo,
    loadedModel,
    setLoadedModel,
    assistantModel,
    setAssistantModel,
    localModels,
    loadLocalModels,
    loadSystemStatus,
    
    // Chat
    conversations,
    setConversations,
    currentConversation,
    setCurrentConversation,
    messages,
    setMessages,
    isGenerating,
    setIsGenerating,
    loadConversations,
    loadConversation,
    
    // Profiles
    profiles,
    setProfiles,
    currentProfile,
    setCurrentProfile,
    loadProfiles,
  }

  return (
    <AppContext.Provider value={value}>
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  const context = useContext(AppContext)
  if (!context) {
    throw new Error('useApp must be used within AppProvider')
  }
  return context
}
