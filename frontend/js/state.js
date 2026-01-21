/**
 * UltraChat - Application State
 * Centralized state management.
 */

import { getItem, setItem, StorageKeys, saveCurrentConversation, saveCurrentModel, saveCurrentProfile } from './utils/storage.js';

// Global state
const state = {
    // Current context
    currentConversationId: null,
    currentModel: null,
    currentProfileId: null,
    
    // Data
    conversations: [],
    messages: [],
    models: [],
    profiles: [],
    memories: [],
    
    // UI state
    isGenerating: false,
    sidebarOpen: true,
    currentView: 'chat',
    
    // Settings
    settings: {
        streamEnabled: true,
        showTimestamps: true,
        compactMode: false,
    },
    
    // Listeners
    _listeners: {},
};

// Subscribe to state changes
export function subscribe(key, callback) {
    if (!state._listeners[key]) {
        state._listeners[key] = [];
    }
    state._listeners[key].push(callback);
    
    // Return unsubscribe function
    return () => {
        state._listeners[key] = state._listeners[key].filter(cb => cb !== callback);
    };
}

// Notify listeners
function notify(key, value) {
    const listeners = state._listeners[key] || [];
    for (const callback of listeners) {
        callback(value);
    }
}

// Get state
export function getState(key) {
    return key ? state[key] : state;
}

// Set state
export function setState(key, value) {
    const oldValue = state[key];
    state[key] = value;
    
    // Persist certain state to storage
    if (key === 'currentConversationId') {
        saveCurrentConversation(value);
    } else if (key === 'currentModel') {
        saveCurrentModel(value);
    } else if (key === 'currentProfileId') {
        saveCurrentProfile(value);
    } else if (key === 'settings') {
        setItem('settings', value);
    }
    
    notify(key, value);
    
    return oldValue;
}

// Initialize state from storage
export function initState() {
    state.currentConversationId = getItem(StorageKeys.CURRENT_CONVERSATION);
    state.currentModel = getItem(StorageKeys.CURRENT_MODEL);
    state.currentProfileId = getItem(StorageKeys.CURRENT_PROFILE);
    state.settings = {
        streamEnabled: getItem(StorageKeys.STREAM_ENABLED, true),
        showTimestamps: getItem(StorageKeys.SHOW_TIMESTAMPS, true),
        compactMode: getItem(StorageKeys.COMPACT_MODE, false),
    };
}

// Clear state
export function clearState() {
    state.currentConversationId = null;
    state.currentModel = null;
    state.currentProfileId = null;
    state.conversations = [];
    state.messages = [];
    state.isGenerating = false;
}

export default state;
