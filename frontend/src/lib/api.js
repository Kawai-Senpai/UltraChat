// API base URL - uses Vite proxy in development
const API_BASE = '/api/v1'

class ApiClient {
  async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`
    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    }

    try {
      const response = await fetch(url, config)
      const contentType = response.headers.get('content-type')
      
      if (contentType?.includes('application/json')) {
        const data = await response.json()
        if (!response.ok) {
          throw new Error(data.error || data.detail || 'Request failed')
        }
        return data
      }
      
      if (!response.ok) {
        throw new Error(`Request failed: ${response.statusText}`)
      }
      
      return response
    } catch (error) {
      console.error(`API Error [${endpoint}]:`, error)
      throw error
    }
  }

  get(endpoint) {
    return this.request(endpoint, { method: 'GET' })
  }

  post(endpoint, data) {
    return this.request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  patch(endpoint, data) {
    return this.request(endpoint, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  }

  delete(endpoint) {
    return this.request(endpoint, { method: 'DELETE' })
  }

  // SSE streaming
  async *stream(endpoint, data, options = {}) {
    const url = `${API_BASE}${endpoint}`
    
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
      signal: options.signal,
    })

    if (!response.ok) {
      let errorMessage = 'Stream request failed'
      try {
        const error = await response.json()
        // Handle different error formats
        if (typeof error.error === 'string') {
          errorMessage = error.error
        } else if (typeof error.detail === 'string') {
          errorMessage = error.detail
        } else if (Array.isArray(error.detail)) {
          // FastAPI validation errors
          errorMessage = error.detail.map(e => e.msg || e.message || JSON.stringify(e)).join(', ')
        } else if (typeof error.message === 'string') {
          errorMessage = error.message
        } else {
          errorMessage = JSON.stringify(error)
        }
      } catch {
        errorMessage = `HTTP ${response.status}: ${response.statusText}`
      }
      throw new Error(errorMessage)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        
        let currentEvent = null
        
        for (const line of lines) {
          if (line.startsWith('event:')) {
            currentEvent = line.slice(6).trim()
          } else if (line.startsWith('data:')) {
            const data = line.slice(5).trim()
            if (currentEvent && data) {
              try {
                yield { event: currentEvent, data: JSON.parse(data) }
              } catch {
                yield { event: currentEvent, data: { raw: data } }
              }
              currentEvent = null
            }
          }
        }
      }
    } finally {
      reader.releaseLock()
    }
  }
}

const api = new ApiClient()

// Chat API
export const chatAPI = {
  sendMessage: (data, options) => api.stream('/chat/send', data, options),
  regenerate: (data, options) => api.stream('/chat/regenerate', data, options),
  editMessage: (messageId, content, model = null, options) => {
    const params = new URLSearchParams({ message_id: messageId })
    if (model) params.set('model', model)
    return api.stream(`/chat/edit?${params.toString()}`, { content }, options)
  },
  listConversations: (includeArchived = false, limit = 50, offset = 0) => 
    api.get(`/chat/conversations?include_archived=${includeArchived}&limit=${limit}&offset=${offset}`),
  createConversation: (data) => api.post('/chat/conversations', data),
  getConversation: (id) => api.get(`/chat/conversations/${id}`),
  updateConversation: (id, data) => api.patch(`/chat/conversations/${id}`, data),
  deleteConversation: (id) => api.delete(`/chat/conversations/${id}`),
  searchConversations: (query, limit = 20) => 
    api.get(`/chat/conversations/search/${encodeURIComponent(query)}?limit=${limit}`),
  deleteMessage: (id) => api.delete(`/chat/messages/${id}`),
  getSiblings: (messageId) => api.get(`/chat/messages/${messageId}/siblings`),
  navigateBranch: (messageId, direction) => api.post(`/chat/messages/${messageId}/navigate/${direction}`, {}),
  switchBranch: (messageId) => api.post(`/chat/messages/${messageId}/switch`, {}),
  stopGeneration: () => api.post('/chat/stop', {}),
}

// Models API
export const modelsAPI = {
  getStatus: () => api.get('/models/status'),
  listModels: () => api.get('/models/local'),
  searchModels: (query, limit = 20) => 
    api.get(`/models/search?q=${encodeURIComponent(query)}&limit=${limit}`),
  getPopularModels: (limit = 20) => api.get(`/models/popular?limit=${limit}`),
  // Updated to support multiple quantizations
  downloadModel: (modelId, quantizations, keepCache = false) => 
    api.stream('/models/download', { 
      model_id: modelId, 
      quantizations: Array.isArray(quantizations) ? quantizations : [quantizations].filter(Boolean),
      keep_cache: keepCache
    }),
  deleteModel: (modelId, quantization = null) => 
    api.post('/models/delete', { model_id: modelId, quantization }),
  loadModel: (modelId, quantization = null) => 
    api.post('/models/load', { model_id: modelId, quantization }),
  unloadModel: () => api.post('/models/unload', {}),
  setFavorite: (modelId, isFavorite = true) => 
    api.post(`/models/${encodeURIComponent(modelId)}/favorite?is_favorite=${isFavorite}`, {}),
}

// Profiles API
export const profilesAPI = {
  listProfiles: () => api.get('/profiles'),
  createProfile: (data) => api.post('/profiles', data),
  getProfile: (id) => api.get(`/profiles/${id}`),
  updateProfile: (id, data) => api.patch(`/profiles/${id}`, data),
  deleteProfile: (id) => api.delete(`/profiles/${id}`),
  getDefault: () => api.get('/profiles/default'),
  getTemplates: () => api.get('/profiles/templates'),
}

// Memory API
export const memoriesAPI = {
  listMemories: (category = null, limit = 50) => {
    const params = new URLSearchParams({ limit: limit.toString() })
    if (category) params.set('category', category)
    return api.get(`/memories?${params}`)
  },
  createMemory: (data) => api.post('/memories', data),
  getMemory: (id) => api.get(`/memories/${id}`),
  updateMemory: (id, data) => api.patch(`/memories/${id}`, data),
  deleteMemory: (id) => api.delete(`/memories/${id}`),
  getCategories: () => api.get('/memories/categories/list'),
  getStats: () => api.get('/memories/stats'),
}

// Settings API
export const settingsAPI = {
  getSettings: () => api.get('/settings'),
  updateSettings: (data) => api.patch('/settings', data),
  resetSettings: () => api.post('/settings/reset', {}),
  getStoragePaths: () => api.get('/settings/storage/paths'),
}

export default api
