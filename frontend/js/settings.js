/**
 * UltraChat - Settings Module
 * Handles settings management.
 */

import { settingsAPI, modelsAPI } from './api.js';
import { getState, setState, subscribe } from './state.js';
import { $, $$, createElement, addClass, removeClass, show, hide, clearChildren } from './utils/dom.js';
import { toast } from './utils/toast.js';

// DOM Elements
let ollamaHostInput;
let defaultModelSelect;
let temperatureSlider;
let temperatureValue;
let maxTokensInput;
let contextLengthInput;
let streamToggle;
let timestampsToggle;
let compactToggle;
let saveButton;
let resetButton;
let storagePath;

// Initialize settings module
export function initSettings() {
    // Get DOM elements
    ollamaHostInput = $('setting-ollama-host');
    defaultModelSelect = $('setting-default-model');
    temperatureSlider = $('setting-temperature');
    temperatureValue = $('setting-temp-value');
    maxTokensInput = $('setting-max-tokens');
    contextLengthInput = $('setting-context-length');
    streamToggle = $('setting-stream');
    timestampsToggle = $('setting-timestamps');
    compactToggle = $('setting-compact');
    saveButton = $('btn-save-settings');
    resetButton = $('btn-reset-settings');
    storagePath = $('storage-path');
    
    // Setup event listeners
    if (temperatureSlider && temperatureValue) {
        temperatureSlider.addEventListener('input', () => {
            temperatureValue.textContent = temperatureSlider.value;
        });
    }
    
    if (saveButton) {
        saveButton.addEventListener('click', saveSettings);
    }
    
    if (resetButton) {
        resetButton.addEventListener('click', resetSettings);
    }
    
    // Listen for view changes
    window.addEventListener('viewChange', async (e) => {
        if (e.detail.view === 'settings') {
            await loadSettings();
            await loadModelsForSelect();
            await loadStoragePaths();
        }
    });
}

// Load settings
async function loadSettings() {
    try {
        const data = await settingsAPI.getSettings();
        populateSettings(data);
    } catch (error) {
        console.error('Failed to load settings:', error);
        toast.error('Failed to load settings');
    }
}

// Populate settings form
function populateSettings(settings) {
    if (ollamaHostInput && settings.ollama_host) {
        ollamaHostInput.value = settings.ollama_host;
    }
    
    if (defaultModelSelect && settings.default_model) {
        defaultModelSelect.value = settings.default_model;
    }
    
    if (temperatureSlider && settings.chat_defaults?.temperature !== undefined) {
        temperatureSlider.value = settings.chat_defaults.temperature;
        if (temperatureValue) {
            temperatureValue.textContent = settings.chat_defaults.temperature;
        }
    }
    
    if (maxTokensInput && settings.chat_defaults?.max_tokens) {
        maxTokensInput.value = settings.chat_defaults.max_tokens;
    }
    
    if (contextLengthInput && settings.chat_defaults?.context_length) {
        contextLengthInput.value = settings.chat_defaults.context_length;
    }
    
    if (streamToggle && settings.ui?.stream_enabled !== undefined) {
        streamToggle.checked = settings.ui.stream_enabled;
    }
    
    if (timestampsToggle && settings.ui?.show_timestamps !== undefined) {
        timestampsToggle.checked = settings.ui.show_timestamps;
    }
    
    if (compactToggle && settings.ui?.compact_mode !== undefined) {
        compactToggle.checked = settings.ui.compact_mode;
    }
}

// Load models for select
async function loadModelsForSelect() {
    try {
        const data = await modelsAPI.listModels();
        
        if (defaultModelSelect && data.models) {
            clearChildren(defaultModelSelect);
            
            // Add empty option
            const emptyOption = createElement('option', {
                value: '',
                textContent: 'No default model',
            });
            defaultModelSelect.appendChild(emptyOption);
            
            // Add models
            for (const model of data.models) {
                const option = createElement('option', {
                    value: model.name,
                    textContent: model.name,
                });
                defaultModelSelect.appendChild(option);
            }
        }
    } catch (error) {
        console.error('Failed to load models:', error);
    }
}

// Load storage paths
async function loadStoragePaths() {
    try {
        const data = await settingsAPI.getStoragePaths();
        
        if (storagePath) {
            if (data.db_path) {
                storagePath.textContent = data.db_path;
            } else {
                storagePath.textContent = 'Unknown';
            }
        }
    } catch (error) {
        console.error('Failed to load storage paths:', error);
        if (storagePath) {
            storagePath.textContent = 'Failed to load';
        }
    }
}

// Save settings
async function saveSettings() {
    const settings = {
        ollama_host: ollamaHostInput?.value || null,
        default_model: defaultModelSelect?.value || null,
        chat_defaults: {
            temperature: parseFloat(temperatureSlider?.value || '0.7'),
            max_tokens: parseInt(maxTokensInput?.value || '4096', 10),
            context_length: parseInt(contextLengthInput?.value || '8192', 10),
        },
        ui: {
            stream_enabled: streamToggle?.checked ?? true,
            show_timestamps: timestampsToggle?.checked ?? true,
            compact_mode: compactToggle?.checked ?? false,
        },
    };
    
    try {
        await settingsAPI.updateSettings(settings);
        
        // Update local state
        setState('settings', {
            streamEnabled: settings.ui.stream_enabled,
            showTimestamps: settings.ui.show_timestamps,
            compactMode: settings.ui.compact_mode,
        });
        
        toast.success('Settings saved');
    } catch (error) {
        console.error('Failed to save settings:', error);
        toast.error(error.message || 'Failed to save settings');
    }
}

// Reset settings
async function resetSettings() {
    try {
        const data = await settingsAPI.resetSettings();
        populateSettings(data);
        toast.success('Settings reset to defaults');
    } catch (error) {
        console.error('Failed to reset settings:', error);
        toast.error(error.message || 'Failed to reset settings');
    }
}

export default { initSettings };
