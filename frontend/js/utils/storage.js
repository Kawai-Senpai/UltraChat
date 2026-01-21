/**
 * UltraChat - Local Storage Utilities
 * Handles persistent local storage.
 */

const STORAGE_PREFIX = 'ultrachat_';

// Get item from storage
export function getItem(key, defaultValue = null) {
    try {
        const item = localStorage.getItem(STORAGE_PREFIX + key);
        if (item === null) return defaultValue;
        return JSON.parse(item);
    } catch (e) {
        console.error('Storage get error:', e);
        return defaultValue;
    }
}

// Set item in storage
export function setItem(key, value) {
    try {
        localStorage.setItem(STORAGE_PREFIX + key, JSON.stringify(value));
        return true;
    } catch (e) {
        console.error('Storage set error:', e);
        return false;
    }
}

// Remove item from storage
export function removeItem(key) {
    try {
        localStorage.removeItem(STORAGE_PREFIX + key);
        return true;
    } catch (e) {
        console.error('Storage remove error:', e);
        return false;
    }
}

// Clear all app storage
export function clearAll() {
    try {
        const keys = Object.keys(localStorage);
        for (const key of keys) {
            if (key.startsWith(STORAGE_PREFIX)) {
                localStorage.removeItem(key);
            }
        }
        return true;
    } catch (e) {
        console.error('Storage clear error:', e);
        return false;
    }
}

// Storage keys
export const StorageKeys = {
    CURRENT_CONVERSATION: 'current_conversation',
    CURRENT_MODEL: 'current_model',
    CURRENT_PROFILE: 'current_profile',
    SIDEBAR_COLLAPSED: 'sidebar_collapsed',
    THEME: 'theme',
    STREAM_ENABLED: 'stream_enabled',
    SHOW_TIMESTAMPS: 'show_timestamps',
    COMPACT_MODE: 'compact_mode',
    RECENT_MODELS: 'recent_models',
    DRAFT_MESSAGE: 'draft_message',
};

// Get current state
export function getCurrentState() {
    return {
        conversationId: getItem(StorageKeys.CURRENT_CONVERSATION),
        model: getItem(StorageKeys.CURRENT_MODEL),
        profileId: getItem(StorageKeys.CURRENT_PROFILE),
        streamEnabled: getItem(StorageKeys.STREAM_ENABLED, true),
        showTimestamps: getItem(StorageKeys.SHOW_TIMESTAMPS, true),
        compactMode: getItem(StorageKeys.COMPACT_MODE, false),
    };
}

// Save current conversation
export function saveCurrentConversation(id) {
    setItem(StorageKeys.CURRENT_CONVERSATION, id);
}

// Save current model
export function saveCurrentModel(model) {
    setItem(StorageKeys.CURRENT_MODEL, model);
    
    // Update recent models
    const recent = getItem(StorageKeys.RECENT_MODELS, []);
    const filtered = recent.filter(m => m !== model);
    filtered.unshift(model);
    setItem(StorageKeys.RECENT_MODELS, filtered.slice(0, 5));
}

// Save current profile
export function saveCurrentProfile(id) {
    setItem(StorageKeys.CURRENT_PROFILE, id);
}

// Save draft message
export function saveDraft(conversationId, message) {
    const drafts = getItem('drafts', {});
    drafts[conversationId || 'new'] = message;
    setItem('drafts', drafts);
}

// Get draft message
export function getDraft(conversationId) {
    const drafts = getItem('drafts', {});
    return drafts[conversationId || 'new'] || '';
}

// Clear draft
export function clearDraft(conversationId) {
    const drafts = getItem('drafts', {});
    delete drafts[conversationId || 'new'];
    setItem('drafts', drafts);
}
