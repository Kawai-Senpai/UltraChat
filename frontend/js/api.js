/**
 * UltraChat - API Client
 * Handles all API communication with the backend.
 */

const API_BASE = '/api/v1';

class APIClient {
    constructor() {
        this.baseUrl = API_BASE;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
            ...options,
        };

        try {
            const response = await fetch(url, config);
            
            // Handle non-JSON responses
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.error || data.detail || 'Request failed');
                }
                
                return data;
            }
            
            if (!response.ok) {
                throw new Error(`Request failed: ${response.statusText}`);
            }
            
            return response;
        } catch (error) {
            console.error(`API Error [${endpoint}]:`, error);
            throw error;
        }
    }

    // GET request
    async get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    }

    // POST request
    async post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    // PATCH request
    async patch(endpoint, data) {
        return this.request(endpoint, {
            method: 'PATCH',
            body: JSON.stringify(data),
        });
    }

    // DELETE request
    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }

    // Stream request (for SSE)
    async stream(endpoint, data, onEvent) {
        const url = `${this.baseUrl}${endpoint}`;
        
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || error.detail || 'Stream request failed');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        try {
            while (true) {
                const { done, value } = await reader.read();
                
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                
                // Parse SSE events
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';
                
                let currentEvent = null;
                let currentData = null;
                
                for (const line of lines) {
                    if (line.startsWith('event:')) {
                        currentEvent = line.slice(6).trim();
                    } else if (line.startsWith('data:')) {
                        currentData = line.slice(5).trim();
                        
                        if (currentEvent && currentData) {
                            try {
                                const parsedData = JSON.parse(currentData);
                                onEvent(currentEvent, parsedData);
                            } catch (e) {
                                onEvent(currentEvent, { raw: currentData });
                            }
                            currentEvent = null;
                            currentData = null;
                        }
                    }
                }
            }
        } finally {
            reader.releaseLock();
        }
    }
}

// API Modules
const api = new APIClient();

// Chat API
export const chatAPI = {
    // Send message (streaming)
    async sendMessage(data, onEvent) {
        return api.stream('/chat/send', data, onEvent);
    },

    // Regenerate response
    async regenerate(data, onEvent) {
        return api.stream('/chat/regenerate', data, onEvent);
    },

    // Edit and continue
    async editAndContinue(messageId, content, model, onEvent) {
        return api.stream(`/chat/edit?message_id=${messageId}&model=${model || ''}`, { content }, onEvent);
    },

    // List conversations
    async listConversations(includeArchived = false, limit = 50, offset = 0) {
        return api.get(`/chat/conversations?include_archived=${includeArchived}&limit=${limit}&offset=${offset}`);
    },

    // Create conversation
    async createConversation(data) {
        return api.post('/chat/conversations', data);
    },

    // Get conversation
    async getConversation(id) {
        return api.get(`/chat/conversations/${id}`);
    },

    // Update conversation
    async updateConversation(id, data) {
        return api.patch(`/chat/conversations/${id}`, data);
    },

    // Delete conversation
    async deleteConversation(id) {
        return api.delete(`/chat/conversations/${id}`);
    },

    // Search conversations
    async searchConversations(query, limit = 20) {
        return api.get(`/chat/conversations/search/${encodeURIComponent(query)}?limit=${limit}`);
    },

    // Get message
    async getMessage(id) {
        return api.get(`/chat/messages/${id}`);
    },

    // Delete message
    async deleteMessage(id) {
        return api.delete(`/chat/messages/${id}`);
    },

    // Get conversation tree
    async getConversationTree(conversationId) {
        return api.get(`/chat/conversations/${conversationId}/tree`);
    },

    // Get message branches
    async getMessageBranches(messageId) {
        return api.get(`/chat/messages/${messageId}/branches`);
    },

    // Switch branch
    async switchBranch(messageId) {
        return api.post(`/chat/messages/${messageId}/switch`, {});
    },

    // Get siblings
    async getSiblings(messageId) {
        return api.get(`/chat/messages/${messageId}/siblings`);
    },

    // Navigate branches
    async navigateBranch(messageId, direction) {
        return api.post(`/chat/messages/${messageId}/navigate/${direction}`, {});
    },

    // Delete branch
    async deleteBranch(messageId) {
        return api.delete(`/chat/messages/${messageId}/branch`);
    },
};

// Models API
export const modelsAPI = {
    // Check Ollama status
    async checkStatus() {
        return api.get('/models/status');
    },

    // List models
    async listModels() {
        return api.get('/models');
    },

    // Get model info
    async getModelInfo(name) {
        return api.get(`/models/${encodeURIComponent(name)}`);
    },

    // Pull model (streaming)
    async pullModel(name, onEvent) {
        return api.stream('/models/pull', { name }, onEvent);
    },

    // Delete model
    async deleteModel(name) {
        return api.delete(`/models/${encodeURIComponent(name)}`);
    },

    // Set favorite
    async setFavorite(name, isFavorite = true) {
        return api.post(`/models/${encodeURIComponent(name)}/favorite?is_favorite=${isFavorite}`, {});
    },

    // Get favorites
    async getFavorites() {
        return api.get('/models/favorites/list');
    },

    // Get recent
    async getRecent(limit = 5) {
        return api.get(`/models/recent/list?limit=${limit}`);
    },
};

// Profiles API
export const profilesAPI = {
    // List profiles
    async listProfiles() {
        return api.get('/profiles');
    },

    // Create profile
    async createProfile(data) {
        return api.post('/profiles', data);
    },

    // Get default profile
    async getDefault() {
        return api.get('/profiles/default');
    },

    // Get templates
    async getTemplates() {
        return api.get('/profiles/templates');
    },

    // Get profile
    async getProfile(id) {
        return api.get(`/profiles/${id}`);
    },

    // Update profile
    async updateProfile(id, data) {
        return api.patch(`/profiles/${id}`, data);
    },

    // Delete profile
    async deleteProfile(id) {
        return api.delete(`/profiles/${id}`);
    },

    // Duplicate profile
    async duplicateProfile(id, newName = null) {
        return api.post(`/profiles/${id}/duplicate${newName ? `?new_name=${encodeURIComponent(newName)}` : ''}`, {});
    },

    // Set default
    async setDefault(id) {
        return api.post(`/profiles/${id}/set-default`, {});
    },
};

// Memories API
export const memoriesAPI = {
    // List memories
    async listMemories(category = null, activeOnly = true, limit = 100, offset = 0) {
        let url = `/memories?active_only=${activeOnly}&limit=${limit}&offset=${offset}`;
        if (category) url += `&category=${encodeURIComponent(category)}`;
        return api.get(url);
    },

    // Create memory
    async createMemory(data) {
        return api.post('/memories', data);
    },

    // Search memories
    async searchMemories(query, category = null, limit = 20) {
        let url = `/memories/search?query=${encodeURIComponent(query)}&limit=${limit}`;
        if (category) url += `&category=${encodeURIComponent(category)}`;
        return api.get(url);
    },

    // Get categories
    async getCategories() {
        return api.get('/memories/categories');
    },

    // Get stats
    async getStats() {
        return api.get('/memories/stats');
    },

    // Get context memories
    async getContextMemories(limit = 10) {
        return api.get(`/memories/context?limit=${limit}`);
    },

    // Get memory
    async getMemory(id) {
        return api.get(`/memories/${id}`);
    },

    // Update memory
    async updateMemory(id, data) {
        return api.patch(`/memories/${id}`, data);
    },

    // Delete memory
    async deleteMemory(id) {
        return api.delete(`/memories/${id}`);
    },

    // Toggle memory
    async toggleMemory(id) {
        return api.post(`/memories/${id}/toggle`, {});
    },

    // Bulk update importance
    async bulkUpdateImportance(ids, importance) {
        return api.post(`/memories/bulk/importance?importance=${importance}`, ids);
    },

    // Extract from conversation
    async extractMemory(conversationId, content, messageId = null, category = 'context', importance = 5) {
        let url = `/memories/extract?conversation_id=${conversationId}&content=${encodeURIComponent(content)}&category=${category}&importance=${importance}`;
        if (messageId) url += `&message_id=${messageId}`;
        return api.post(url, {});
    },
};

// Settings API
export const settingsAPI = {
    // Get settings
    async getSettings() {
        return api.get('/settings');
    },

    // Update settings
    async updateSettings(data) {
        return api.patch('/settings', data);
    },

    // Reset settings
    async resetSettings() {
        return api.post('/settings/reset', {});
    },

    // Get storage paths
    async getStoragePaths() {
        return api.get('/settings/storage/paths');
    },
};

export default api;
