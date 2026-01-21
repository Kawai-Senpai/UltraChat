/**
 * UltraChat - Modal Utilities
 * Modal dialog management.
 */

import { createElement, $, show, hide, addClass, removeClass } from './dom.js';

let currentModal = null;

// Create and show a modal
export function showModal(options) {
    const {
        title = '',
        content = '',
        actions = [],
        closeable = true,
        size = 'md', // sm, md, lg
        onClose = null,
    } = options;
    
    closeModal(); // Close any existing modal
    
    const container = $('modal-container');
    if (!container) return null;
    
    // Create modal structure
    const modal = createElement('div', {
        className: `modal modal-${size}`,
        onClick: (e) => e.stopPropagation(),
    });
    
    // Header
    const header = createElement('div', { className: 'modal-header' }, [
        createElement('h3', { className: 'modal-title', textContent: title }),
    ]);
    
    if (closeable) {
        const closeBtn = createElement('button', {
            className: 'btn-icon',
            innerHTML: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>`,
            onClick: () => closeModal(onClose),
        });
        header.appendChild(closeBtn);
    }
    
    modal.appendChild(header);
    
    // Body
    const body = createElement('div', { className: 'modal-body' });
    if (typeof content === 'string') {
        body.innerHTML = content;
    } else if (content instanceof Node) {
        body.appendChild(content);
    }
    modal.appendChild(body);
    
    // Footer (if actions provided)
    if (actions.length > 0) {
        const footer = createElement('div', { className: 'modal-footer' });
        
        for (const action of actions) {
            const btn = createElement('button', {
                className: `btn ${action.primary ? 'btn-primary' : 'btn-secondary'} ${action.danger ? 'btn-danger' : ''}`,
                textContent: action.text,
                onClick: async (e) => {
                    if (action.onClick) {
                        const result = await action.onClick(e);
                        if (result !== false) {
                            closeModal(onClose);
                        }
                    } else {
                        closeModal(onClose);
                    }
                },
            });
            footer.appendChild(btn);
        }
        
        modal.appendChild(footer);
    }
    
    // Add to container
    container.innerHTML = '';
    container.appendChild(modal);
    show(container);
    
    // Close on backdrop click
    if (closeable) {
        container.onclick = () => closeModal(onClose);
    }
    
    // Close on escape
    const escHandler = (e) => {
        if (e.key === 'Escape' && closeable) {
            closeModal(onClose);
            document.removeEventListener('keydown', escHandler);
        }
    };
    document.addEventListener('keydown', escHandler);
    
    currentModal = { modal, container, onClose, escHandler };
    
    return modal;
}

// Close modal
export function closeModal(callback) {
    const container = $('modal-container');
    if (!container) return;
    
    hide(container);
    container.innerHTML = '';
    
    if (currentModal?.escHandler) {
        document.removeEventListener('keydown', currentModal.escHandler);
    }
    
    if (callback) callback();
    currentModal = null;
}

// Confirm dialog
export function confirm(options) {
    const {
        title = 'Confirm',
        message = 'Are you sure?',
        confirmText = 'Confirm',
        cancelText = 'Cancel',
        danger = false,
    } = options;
    
    return new Promise((resolve) => {
        showModal({
            title,
            content: `<p class="text-sm text-secondary">${message}</p>`,
            actions: [
                {
                    text: cancelText,
                    onClick: () => {
                        resolve(false);
                        return true;
                    },
                },
                {
                    text: confirmText,
                    primary: !danger,
                    danger: danger,
                    onClick: () => {
                        resolve(true);
                        return true;
                    },
                },
            ],
            onClose: () => resolve(false),
        });
    });
}

// Prompt dialog
export function prompt(options) {
    const {
        title = 'Input',
        message = '',
        placeholder = '',
        defaultValue = '',
        confirmText = 'OK',
        cancelText = 'Cancel',
    } = options;
    
    return new Promise((resolve) => {
        const content = createElement('div', {}, [
            message ? createElement('p', { className: 'text-sm text-secondary mb-4', textContent: message }) : null,
            createElement('input', {
                type: 'text',
                className: 'input',
                placeholder,
                value: defaultValue,
                id: 'modal-prompt-input',
            }),
        ].filter(Boolean));
        
        showModal({
            title,
            content,
            actions: [
                {
                    text: cancelText,
                    onClick: () => {
                        resolve(null);
                        return true;
                    },
                },
                {
                    text: confirmText,
                    primary: true,
                    onClick: () => {
                        const input = $('modal-prompt-input');
                        resolve(input?.value || '');
                        return true;
                    },
                },
            ],
            onClose: () => resolve(null),
        });
        
        // Focus input
        setTimeout(() => {
            const input = $('modal-prompt-input');
            if (input) input.focus();
        }, 100);
    });
}

export default { showModal, closeModal, confirm, prompt };
