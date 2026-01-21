/**
 * UltraChat - Main Application Entry
 * Initializes all modules and handles global events.
 */

import { initState, getState, setState } from './state.js';
import { initChat, newChat } from './chat.js';
import { initSidebar } from './sidebar.js';
import { initSettings } from './settings.js';
import { initModels } from './models.js';
import { initMemory } from './memory.js';
import { initProfiles } from './profiles.js';
import { modelsAPI, settingsAPI } from './api.js';
import { toast } from './utils/toast.js';
import { $, show, hide, addClass, removeClass } from './utils/dom.js';

// Current view
let currentView = 'chat';

// Application initialization
async function init() {
    console.log('UltraChat initializing...');
    
    // Initialize state from storage
    initState();
    
    // Check Ollama connection
    await checkOllamaStatus();
    
    // Initialize modules
    initChat();
    initSidebar();
    initSettings();
    initModels();
    initMemory();
    initProfiles();
    
    // Setup view navigation
    setupViewNavigation();
    
    // Setup global keyboard shortcuts
    setupKeyboardShortcuts();
    
    // Load initial model if none selected
    if (!getState('currentModel')) {
        await loadDefaultModel();
    }
    
    console.log('UltraChat initialized successfully');
}

// Check Ollama status
async function checkOllamaStatus() {
    const statusBanner = $('ollama-status');
    
    try {
        const status = await modelsAPI.checkStatus();
        
        if (status.connected) {
            if (statusBanner) {
                statusBanner.classList.add('connected');
                statusBanner.classList.remove('error');
                const statusText = statusBanner.querySelector('.status-text');
                if (statusText) {
                    statusText.textContent = `Ollama connected (v${status.version || 'unknown'})`;
                }
            }
        } else {
            throw new Error('Not connected');
        }
    } catch (error) {
        console.error('Ollama not connected:', error);
        
        if (statusBanner) {
            statusBanner.classList.remove('connected');
            statusBanner.classList.add('error');
            const statusText = statusBanner.querySelector('.status-text');
            if (statusText) {
                statusText.textContent = 'Ollama is not running. Please start Ollama.';
            }
        }
        
        toast.warning('Ollama is not running. Please start Ollama to chat.');
    }
}

// Setup view navigation
function setupViewNavigation() {
    const navItems = {
        'nav-models': 'models',
        'nav-memory': 'memory',
        'nav-profiles': 'profiles',
        'nav-settings': 'settings',
    };
    
    for (const [btnId, viewName] of Object.entries(navItems)) {
        const btn = $(btnId);
        if (btn) {
            btn.addEventListener('click', () => switchView(viewName));
        }
    }
    
    // Toggle sidebar button
    const toggleSidebar = $('toggle-sidebar');
    if (toggleSidebar) {
        toggleSidebar.addEventListener('click', () => {
            const sidebar = $('sidebar');
            if (sidebar) {
                sidebar.classList.toggle('mobile-open');
            }
        });
    }
}

// Switch view
function switchView(viewName) {
    const views = document.querySelectorAll('.view');
    views.forEach(view => {
        removeClass(view, 'active');
    });
    
    const targetView = $(`view-${viewName}`);
    if (targetView) {
        addClass(targetView, 'active');
        currentView = viewName;
    }
    
    // Update nav item active state
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        removeClass(item, 'active');
    });
    
    const activeNavItem = $(`nav-${viewName}`);
    if (activeNavItem) {
        addClass(activeNavItem, 'active');
    }
    
    // Dispatch view change event
    window.dispatchEvent(new CustomEvent('viewChange', { detail: { view: viewName } }));
}

// Expose switchView globally for back buttons
window.switchToChat = () => switchView('chat');

// Load default model
async function loadDefaultModel() {
    try {
        const data = await modelsAPI.listModels();
        
        if (data.models && data.models.length > 0) {
            // Use first available model
            const firstModel = data.models[0];
            setState('currentModel', firstModel.name);
        }
    } catch (error) {
        console.error('Failed to load default model:', error);
    }
}

// Setup keyboard shortcuts
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd + N: New chat
        if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
            e.preventDefault();
            newChat();
            switchView('chat');
        }
        
        // Ctrl/Cmd + /: Focus input
        if ((e.ctrlKey || e.metaKey) && e.key === '/') {
            e.preventDefault();
            const input = $('message-input');
            if (input) input.focus();
        }
        
        // Escape: Close panels or switch to chat
        if (e.key === 'Escape') {
            if (currentView !== 'chat') {
                switchView('chat');
            }
        }
        
        // Ctrl/Cmd + 1-5: Quick view switch
        if ((e.ctrlKey || e.metaKey) && e.key >= '1' && e.key <= '5') {
            e.preventDefault();
            const views = ['chat', 'models', 'memory', 'profiles', 'settings'];
            const index = parseInt(e.key) - 1;
            if (views[index]) {
                switchView(views[index]);
            }
        }
    });
}

// Start application when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

// Export for console debugging
window.UltraChat = {
    getState,
    setState,
    newChat,
    switchView,
};
