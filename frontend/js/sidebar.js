/**
 * UltraChat - Sidebar Module
 * Handles sidebar navigation and conversation list.
 */

import { chatAPI, modelsAPI, profilesAPI } from './api.js';
import { getState, setState, subscribe } from './state.js';
import { $, $$, createElement, addClass, removeClass, show, hide, clearChildren, formatDate, truncate, debounce } from './utils/dom.js';
import { toast } from './utils/toast.js';
import { confirm, prompt } from './utils/modal.js';
import { newChat } from './chat.js';

// DOM Elements
let sidebar;
let sidebarToggle;
let conversationsList;
let searchInput;
let newChatBtn;
let loadingIndicator;

// Initialize sidebar module
export function initSidebar() {
    // Get DOM elements
    sidebar = $('sidebar');
    sidebarToggle = $('toggle-sidebar');
    conversationsList = $('conversations-list');
    searchInput = $('search-conversations');
    newChatBtn = $('new-chat-btn');
    loadingIndicator = $('sidebar-loading');
    
    // Setup event listeners
    setupSidebarToggle();
    setupSearch();
    setupNewChat();
    
    // Subscribe to state changes
    subscribe('conversations', renderConversations);
    subscribe('currentConversationId', highlightCurrentConversation);
    
    // Listen for refresh event
    window.addEventListener('refreshConversations', loadConversations);
    
    // Load initial data
    loadConversations();
}

// Setup sidebar toggle
function setupSidebarToggle() {
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', toggleSidebar);
    }
    
    // Keyboard shortcut (Ctrl/Cmd + B)
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
            e.preventDefault();
            toggleSidebar();
        }
    });
}

// Toggle sidebar
function toggleSidebar() {
    if (sidebar) {
        sidebar.classList.toggle('collapsed');
        setState('sidebarOpen', !sidebar.classList.contains('collapsed'));
    }
}

// Setup search
function setupSearch() {
    if (!searchInput) return;
    
    const debouncedSearch = debounce(async (query) => {
        if (!query.trim()) {
            loadConversations();
            return;
        }
        
        try {
            const results = await chatAPI.searchConversations(query);
            renderConversations(results.conversations || []);
        } catch (error) {
            console.error('Search error:', error);
        }
    }, 300);
    
    searchInput.addEventListener('input', (e) => {
        debouncedSearch(e.target.value);
    });
}

// Setup new chat button
function setupNewChat() {
    if (!newChatBtn) return;
    
    newChatBtn.addEventListener('click', () => {
        newChat();
        highlightCurrentConversation(null);
    });
}

// Load conversations
async function loadConversations() {
    try {
        if (loadingIndicator) show(loadingIndicator);
        
        const data = await chatAPI.listConversations();
        setState('conversations', data.conversations || []);
        
    } catch (error) {
        console.error('Failed to load conversations:', error);
        toast.error('Failed to load conversations');
    } finally {
        if (loadingIndicator) hide(loadingIndicator);
    }
}

// Render conversations list
function renderConversations(conversations) {
    if (!conversationsList) return;
    
    clearChildren(conversationsList);
    
    if (!conversations || conversations.length === 0) {
        const empty = createElement('div', {
            className: 'empty-state',
        }, [
            createElement('div', { className: 'empty-state-icon', textContent: '💬' }),
            createElement('div', { className: 'empty-state-title', textContent: 'No conversations' }),
            createElement('div', { className: 'empty-state-description', textContent: 'Start a new chat to begin' }),
        ]);
        conversationsList.appendChild(empty);
        return;
    }
    
    // Group by date
    const groups = groupByDate(conversations);
    
    for (const [label, items] of Object.entries(groups)) {
        // Group header
        const header = createElement('div', {
            className: 'conversation-group-header',
            textContent: label,
        });
        conversationsList.appendChild(header);
        
        // Conversations
        for (const conv of items) {
            const item = createConversationItem(conv);
            conversationsList.appendChild(item);
        }
    }
    
    highlightCurrentConversation(getState('currentConversationId'));
}

// Group conversations by date
function groupByDate(conversations) {
    const groups = {
        'Today': [],
        'Yesterday': [],
        'This Week': [],
        'This Month': [],
        'Older': [],
    };
    
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const weekAgo = new Date(today);
    weekAgo.setDate(weekAgo.getDate() - 7);
    const monthAgo = new Date(today);
    monthAgo.setMonth(monthAgo.getMonth() - 1);
    
    for (const conv of conversations) {
        const date = new Date(conv.updated_at || conv.created_at);
        
        if (date >= today) {
            groups['Today'].push(conv);
        } else if (date >= yesterday) {
            groups['Yesterday'].push(conv);
        } else if (date >= weekAgo) {
            groups['This Week'].push(conv);
        } else if (date >= monthAgo) {
            groups['This Month'].push(conv);
        } else {
            groups['Older'].push(conv);
        }
    }
    
    // Remove empty groups
    for (const key of Object.keys(groups)) {
        if (groups[key].length === 0) {
            delete groups[key];
        }
    }
    
    return groups;
}

// Create conversation item
function createConversationItem(conversation) {
    const { id, title, preview, model, updated_at, message_count, is_pinned, is_archived } = conversation;
    
    const item = createElement('div', {
        className: `conversation-item ${is_pinned ? 'pinned' : ''} ${is_archived ? 'archived' : ''}`,
        dataset: { conversationId: id },
    });
    
    // Click to open
    item.addEventListener('click', () => {
        setState('currentConversationId', id);
    });
    
    // Content
    const content = createElement('div', { className: 'conversation-content' });
    
    // Title
    const titleEl = createElement('div', { className: 'conversation-title' }, [
        is_pinned ? createElement('span', { textContent: '📌 ' }) : null,
        document.createTextNode(truncate(title || 'New Chat', 30)),
    ].filter(Boolean));
    content.appendChild(titleEl);
    
    // Preview
    if (preview) {
        const previewEl = createElement('div', {
            className: 'conversation-preview',
            textContent: truncate(preview, 50),
        });
        content.appendChild(previewEl);
    }
    
    // Meta
    const meta = createElement('div', { className: 'conversation-meta' }, [
        createElement('span', { textContent: formatDate(updated_at) }),
        model ? createElement('span', { className: 'badge', textContent: model.split(':')[0] }) : null,
    ].filter(Boolean));
    content.appendChild(meta);
    
    item.appendChild(content);
    
    // Actions dropdown
    const actions = createElement('div', { className: 'conversation-actions' });
    
    const menuBtn = createElement('button', {
        className: 'btn-icon btn-sm',
        innerHTML: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/>
        </svg>`,
        onClick: (e) => {
            e.stopPropagation();
            showConversationMenu(e, conversation);
        },
    });
    actions.appendChild(menuBtn);
    
    item.appendChild(actions);
    
    return item;
}

// Show conversation context menu
function showConversationMenu(event, conversation) {
    const { id, is_pinned, is_archived } = conversation;
    
    // Remove any existing menu
    const existingMenu = document.querySelector('.context-menu');
    if (existingMenu) existingMenu.remove();
    
    const menu = createElement('div', {
        className: 'context-menu',
    });
    
    // Position menu
    const rect = event.target.getBoundingClientRect();
    menu.style.left = `${rect.left}px`;
    menu.style.top = `${rect.bottom + 4}px`;
    
    // Menu items
    const items = [
        {
            icon: '✏️',
            text: 'Rename',
            onClick: async () => {
                const newTitle = await prompt({
                    title: 'Rename Conversation',
                    message: 'Enter a new title:',
                    defaultValue: conversation.title,
                });
                if (newTitle) {
                    try {
                        await chatAPI.updateConversation(id, { title: newTitle });
                        loadConversations();
                        toast.success('Conversation renamed');
                    } catch (e) {
                        toast.error('Failed to rename');
                    }
                }
            },
        },
        {
            icon: is_pinned ? '📍' : '📌',
            text: is_pinned ? 'Unpin' : 'Pin',
            onClick: async () => {
                try {
                    await chatAPI.updateConversation(id, { is_pinned: !is_pinned });
                    loadConversations();
                } catch (e) {
                    toast.error('Failed to update');
                }
            },
        },
        {
            icon: is_archived ? '📂' : '📁',
            text: is_archived ? 'Unarchive' : 'Archive',
            onClick: async () => {
                try {
                    await chatAPI.updateConversation(id, { is_archived: !is_archived });
                    loadConversations();
                    toast.success(is_archived ? 'Conversation unarchived' : 'Conversation archived');
                } catch (e) {
                    toast.error('Failed to update');
                }
            },
        },
        { divider: true },
        {
            icon: '🗑️',
            text: 'Delete',
            danger: true,
            onClick: async () => {
                const confirmed = await confirm({
                    title: 'Delete Conversation',
                    message: 'Are you sure you want to delete this conversation? This cannot be undone.',
                    confirmText: 'Delete',
                    danger: true,
                });
                if (confirmed) {
                    try {
                        await chatAPI.deleteConversation(id);
                        if (getState('currentConversationId') === id) {
                            newChat();
                        }
                        loadConversations();
                        toast.success('Conversation deleted');
                    } catch (e) {
                        toast.error('Failed to delete');
                    }
                }
            },
        },
    ];
    
    for (const item of items) {
        if (item.divider) {
            menu.appendChild(createElement('div', { className: 'context-menu-divider' }));
        } else {
            const menuItem = createElement('div', {
                className: `context-menu-item ${item.danger ? 'danger' : ''}`,
            }, [
                createElement('span', { textContent: item.icon }),
                createElement('span', { textContent: item.text }),
            ]);
            menuItem.addEventListener('click', () => {
                menu.remove();
                item.onClick();
            });
            menu.appendChild(menuItem);
        }
    }
    
    document.body.appendChild(menu);
    
    // Close on click outside
    const closeMenu = (e) => {
        if (!menu.contains(e.target)) {
            menu.remove();
            document.removeEventListener('click', closeMenu);
        }
    };
    setTimeout(() => {
        document.addEventListener('click', closeMenu);
    }, 0);
}

// Highlight current conversation
function highlightCurrentConversation(conversationId) {
    const items = document.querySelectorAll('.conversation-item');
    items.forEach(item => {
        removeClass(item, 'active');
        if (item.dataset.conversationId === conversationId) {
            addClass(item, 'active');
        }
    });
}

export default { initSidebar };
