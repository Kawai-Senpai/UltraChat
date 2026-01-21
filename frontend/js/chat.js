/**
 * UltraChat - Chat Module
 * Handles chat functionality.
 */

import { chatAPI, modelsAPI, profilesAPI } from './api.js';
import { getState, setState, subscribe } from './state.js';
import { $, $$, createElement, addClass, removeClass, show, hide, clearChildren, scrollToBottom, isScrolledToBottom, formatDate, truncate, debounce } from './utils/dom.js';
import { toast } from './utils/toast.js';
import { confirm } from './utils/modal.js';
import { renderMarkdown, highlightCode } from './utils/markdown.js';
import { saveDraft, getDraft, clearDraft } from './utils/storage.js';

// DOM Elements
let messagesContainer;
let messagesList;
let messageInput;
let sendButton;
let stopButton;
let welcomeMessage;
let chatTitle;
let currentModelBadge;
let currentProfileBadge;

// Abort controller for streaming
let abortController = null;

// Initialize chat module
export function initChat() {
    // Get DOM elements
    messagesContainer = $('messages-container');
    messagesList = $('messages-list');
    messageInput = $('message-input');
    sendButton = $('btn-send');
    stopButton = $('btn-stop');
    welcomeMessage = $('welcome-message');
    chatTitle = $('chat-title');
    currentModelBadge = $('current-model');
    currentProfileBadge = $('current-profile');
    
    // Setup event listeners
    setupInputHandlers();
    setupHintHandlers();
    
    // Subscribe to state changes
    subscribe('currentConversationId', loadConversation);
    subscribe('currentModel', updateModelBadge);
    subscribe('currentProfileId', updateProfileBadge);
    subscribe('isGenerating', updateGeneratingState);
    
    // Load initial conversation if exists
    const conversationId = getState('currentConversationId');
    if (conversationId) {
        loadConversation(conversationId);
    }
    
    // Restore draft
    const draft = getDraft(conversationId);
    if (draft) {
        messageInput.value = draft;
        autoResizeTextarea();
    }
}

// Setup input handlers
function setupInputHandlers() {
    // Send on Enter
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Auto-resize textarea
    messageInput.addEventListener('input', () => {
        autoResizeTextarea();
        // Save draft
        const conversationId = getState('currentConversationId');
        saveDraft(conversationId, messageInput.value);
    });
    
    // Send button
    sendButton.addEventListener('click', sendMessage);
    
    // Stop button
    stopButton.addEventListener('click', stopGeneration);
}

// Setup hint handlers
function setupHintHandlers() {
    const hints = document.querySelectorAll('.hint');
    hints.forEach(hint => {
        hint.addEventListener('click', () => {
            const prompt = hint.dataset.prompt;
            if (prompt) {
                messageInput.value = prompt;
                autoResizeTextarea();
                messageInput.focus();
            }
        });
    });
}

// Auto-resize textarea
function autoResizeTextarea() {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 200) + 'px';
}

// Load conversation
async function loadConversation(conversationId) {
    if (!conversationId) {
        clearMessages();
        show(welcomeMessage);
        chatTitle.textContent = 'New Chat';
        return;
    }
    
    try {
        const data = await chatAPI.getConversation(conversationId);
        
        if (data) {
            // Update state
            setState('messages', data.messages || []);
            
            // Update UI
            chatTitle.textContent = data.title || 'New Chat';
            
            if (data.model) {
                setState('currentModel', data.model);
            }
            
            if (data.profile_id) {
                setState('currentProfileId', data.profile_id);
            }
            
            // Render messages
            renderMessages(data.messages || []);
        }
    } catch (error) {
        console.error('Failed to load conversation:', error);
        toast.error('Failed to load conversation');
    }
}

// Clear messages
function clearMessages() {
    clearChildren(messagesList);
    setState('messages', []);
}

// Render messages
function renderMessages(messages) {
    clearChildren(messagesList);
    
    if (messages.length === 0) {
        show(welcomeMessage);
        messagesList.appendChild(welcomeMessage);
        return;
    }
    
    hide(welcomeMessage);
    
    for (const msg of messages) {
        const messageEl = createMessageElement(msg);
        messagesList.appendChild(messageEl);
    }
    
    scrollToBottom(messagesContainer);
}

// Create message element
function createMessageElement(message) {
    const { id, role, content, created_at, model, tokens_completion } = message;
    
    const showTimestamps = getState('settings').showTimestamps;
    
    const messageDiv = createElement('div', {
        className: `message ${role} message-appear`,
        dataset: { messageId: id },
    });
    
    // Avatar
    const avatar = createElement('div', {
        className: 'message-avatar',
        textContent: role === 'user' ? '👤' : '🤖',
    });
    messageDiv.appendChild(avatar);
    
    // Content container
    const contentDiv = createElement('div', { className: 'message-content' });
    
    // Header
    const header = createElement('div', { className: 'message-header' }, [
        createElement('span', { className: 'message-role', textContent: role }),
    ]);
    
    if (showTimestamps && created_at) {
        header.appendChild(createElement('span', {
            className: 'message-time',
            textContent: formatDate(created_at),
        }));
    }
    
    contentDiv.appendChild(header);
    
    // Body
    const body = createElement('div', {
        className: 'message-body',
        innerHTML: renderMarkdown(content),
    });
    contentDiv.appendChild(body);
    
    // Actions
    const actions = createElement('div', { className: 'message-actions' });
    
    // Copy button
    const copyBtn = createElement('button', {
        className: 'btn-icon btn-sm',
        title: 'Copy',
        innerHTML: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
        </svg>`,
        onClick: async () => {
            try {
                await navigator.clipboard.writeText(content);
                toast.success('Copied to clipboard');
            } catch (e) {
                toast.error('Failed to copy');
            }
        },
    });
    actions.appendChild(copyBtn);
    
    // Regenerate button (for assistant messages)
    if (role === 'assistant') {
        const regenBtn = createElement('button', {
            className: 'btn-icon btn-sm',
            title: 'Regenerate',
            innerHTML: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M23 4v6h-6"/>
                <path d="M1 20v-6h6"/>
                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
            </svg>`,
            onClick: () => regenerateMessage(id),
        });
        actions.appendChild(regenBtn);
    }
    
    // Edit button (for user messages)
    if (role === 'user') {
        const editBtn = createElement('button', {
            className: 'btn-icon btn-sm',
            title: 'Edit',
            innerHTML: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
            </svg>`,
            onClick: () => editMessage(id, content),
        });
        actions.appendChild(editBtn);
    }
    
    contentDiv.appendChild(actions);
    messageDiv.appendChild(contentDiv);
    
    // Highlight code blocks
    highlightCode(messageDiv);
    
    return messageDiv;
}

// Send message
async function sendMessage() {
    const content = messageInput.value.trim();
    if (!content || getState('isGenerating')) return;
    
    // Get toggle states
    const webSearchToggle = document.getElementById('toggle-web-search');
    const memoryToggle = document.getElementById('toggle-memory');
    const webSearch = webSearchToggle ? webSearchToggle.checked : false;
    const useMemory = memoryToggle ? memoryToggle.checked : true;
    
    // Clear input
    messageInput.value = '';
    autoResizeTextarea();
    clearDraft(getState('currentConversationId'));
    
    // Hide welcome message
    hide(welcomeMessage);
    
    // Add user message to UI
    const userMessage = {
        id: `temp-${Date.now()}`,
        role: 'user',
        content,
        created_at: new Date().toISOString(),
    };
    addMessageToUI(userMessage);
    
    // Create assistant message placeholder
    const assistantMessage = {
        id: `temp-assistant-${Date.now()}`,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
    };
    const assistantEl = addMessageToUI(assistantMessage);
    const bodyEl = assistantEl.querySelector('.message-body');
    addClass(bodyEl, 'cursor-blink');
    
    // Set generating state
    setState('isGenerating', true);
    abortController = new AbortController();
    
    try {
        await chatAPI.sendMessage(
            {
                conversation_id: getState('currentConversationId'),
                message: content,
                model: getState('currentModel'),
                profile_id: getState('currentProfileId'),
                stream: getState('settings').streamEnabled,
                web_search: webSearch,
                use_memory: useMemory,
            },
            (event, data) => handleStreamEvent(event, data, assistantEl, bodyEl)
        );
    } catch (error) {
        console.error('Send message error:', error);
        toast.error(error.message || 'Failed to send message');
        bodyEl.textContent = 'Error: ' + (error.message || 'Failed to generate response');
        removeClass(bodyEl, 'cursor-blink');
    } finally {
        setState('isGenerating', false);
        removeClass(bodyEl, 'cursor-blink');
        highlightCode(assistantEl);
    }
}

// Handle stream events
function handleStreamEvent(event, data, messageEl, bodyEl) {
    switch (event) {
        case 'token':
            // Append token
            const currentText = bodyEl.getAttribute('data-raw') || '';
            const newText = currentText + data.token;
            bodyEl.setAttribute('data-raw', newText);
            bodyEl.innerHTML = renderMarkdown(newText);
            
            // Auto-scroll if at bottom
            if (isScrolledToBottom(messagesContainer)) {
                scrollToBottom(messagesContainer, false);
            }
            break;
            
        case 'done':
            // Update message ID
            if (data.message_id) {
                messageEl.dataset.messageId = data.message_id;
            }
            
            // Update conversation state
            if (data.conversation_id && !getState('currentConversationId')) {
                setState('currentConversationId', data.conversation_id);
            }
            
            // Refresh conversation list
            window.dispatchEvent(new CustomEvent('refreshConversations'));
            break;
            
        case 'status':
            if (data.status === 'generating' && data.conversation_id) {
                setState('currentConversationId', data.conversation_id);
            }
            break;
            
        case 'error':
            toast.error(data.message || 'An error occurred');
            bodyEl.textContent = 'Error: ' + (data.message || 'Failed to generate response');
            break;
    }
}

// Add message to UI
function addMessageToUI(message) {
    const messageEl = createMessageElement(message);
    messagesList.appendChild(messageEl);
    scrollToBottom(messagesContainer);
    return messageEl;
}

// Stop generation
function stopGeneration() {
    if (abortController) {
        abortController.abort();
        abortController = null;
    }
    setState('isGenerating', false);
}

// Regenerate message
async function regenerateMessage(messageId) {
    if (getState('isGenerating')) return;
    
    // Create new assistant message placeholder
    const assistantMessage = {
        id: `temp-regen-${Date.now()}`,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
    };
    const assistantEl = addMessageToUI(assistantMessage);
    const bodyEl = assistantEl.querySelector('.message-body');
    addClass(bodyEl, 'cursor-blink');
    
    setState('isGenerating', true);
    
    try {
        await chatAPI.regenerate(
            {
                message_id: messageId,
                model: getState('currentModel'),
            },
            (event, data) => handleStreamEvent(event, data, assistantEl, bodyEl)
        );
    } catch (error) {
        console.error('Regenerate error:', error);
        toast.error(error.message || 'Failed to regenerate');
        bodyEl.textContent = 'Error: ' + (error.message || 'Failed to regenerate');
    } finally {
        setState('isGenerating', false);
        removeClass(bodyEl, 'cursor-blink');
        highlightCode(assistantEl);
    }
}

// Edit message
async function editMessage(messageId, currentContent) {
    // For now, just put content in input
    messageInput.value = currentContent;
    autoResizeTextarea();
    messageInput.focus();
    
    toast.info('Edit the message and send to create a new branch');
}

// Update generating state
function updateGeneratingState(isGenerating) {
    if (isGenerating) {
        show(stopButton);
        hide(sendButton);
        messageInput.disabled = true;
    } else {
        hide(stopButton);
        show(sendButton);
        messageInput.disabled = false;
        messageInput.focus();
    }
}

// Update model badge
function updateModelBadge(model) {
    if (currentModelBadge) {
        currentModelBadge.textContent = model || 'No model';
    }
}

// Update profile badge
function updateProfileBadge(profileId) {
    if (currentProfileBadge) {
        currentProfileBadge.textContent = profileId ? 'Custom' : 'Default';
    }
}

// Create new chat
export function newChat() {
    setState('currentConversationId', null);
    setState('messages', []);
    clearMessages();
    show(welcomeMessage);
    if (welcomeMessage.parentNode !== messagesList) {
        messagesList.appendChild(welcomeMessage);
    }
    chatTitle.textContent = 'New Chat';
    messageInput.value = '';
    messageInput.focus();
}

export default { initChat, newChat, loadConversation };
