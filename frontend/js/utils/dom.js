/**
 * UltraChat - DOM Utilities
 * Helper functions for DOM manipulation.
 */

// Create element with attributes and children
export function createElement(tag, attrs = {}, children = []) {
    const element = document.createElement(tag);
    
    for (const [key, value] of Object.entries(attrs)) {
        if (key === 'className') {
            element.className = value;
        } else if (key === 'dataset') {
            for (const [dataKey, dataValue] of Object.entries(value)) {
                element.dataset[dataKey] = dataValue;
            }
        } else if (key.startsWith('on') && typeof value === 'function') {
            const event = key.slice(2).toLowerCase();
            element.addEventListener(event, value);
        } else if (key === 'innerHTML') {
            element.innerHTML = value;
        } else if (key === 'textContent') {
            element.textContent = value;
        } else {
            element.setAttribute(key, value);
        }
    }
    
    for (const child of children) {
        if (typeof child === 'string') {
            element.appendChild(document.createTextNode(child));
        } else if (child instanceof Node) {
            element.appendChild(child);
        }
    }
    
    return element;
}

// Shorthand for getElementById
export function $(id) {
    return document.getElementById(id);
}

// Shorthand for querySelector
export function $$(selector, parent = document) {
    return parent.querySelector(selector);
}

// Shorthand for querySelectorAll
export function $$$(selector, parent = document) {
    return parent.querySelectorAll(selector);
}

// Add class to element
export function addClass(element, ...classes) {
    element.classList.add(...classes);
}

// Remove class from element
export function removeClass(element, ...classes) {
    element.classList.remove(...classes);
}

// Toggle class on element
export function toggleClass(element, className, force) {
    return element.classList.toggle(className, force);
}

// Check if element has class
export function hasClass(element, className) {
    return element.classList.contains(className);
}

// Show element
export function show(element) {
    removeClass(element, 'hidden');
}

// Hide element
export function hide(element) {
    addClass(element, 'hidden');
}

// Toggle visibility
export function toggle(element, visible) {
    toggleClass(element, 'hidden', !visible);
}

// Set multiple attributes
export function setAttributes(element, attrs) {
    for (const [key, value] of Object.entries(attrs)) {
        element.setAttribute(key, value);
    }
}

// Remove all children
export function clearChildren(element) {
    while (element.firstChild) {
        element.removeChild(element.firstChild);
    }
}

// Insert after element
export function insertAfter(newElement, referenceElement) {
    referenceElement.parentNode.insertBefore(newElement, referenceElement.nextSibling);
}

// Scroll to bottom of element
export function scrollToBottom(element, smooth = true) {
    element.scrollTo({
        top: element.scrollHeight,
        behavior: smooth ? 'smooth' : 'auto'
    });
}

// Check if element is scrolled to bottom
export function isScrolledToBottom(element, threshold = 50) {
    return element.scrollHeight - element.scrollTop - element.clientHeight < threshold;
}

// Debounce function
export function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Throttle function
export function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// Format date
export function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    
    // Less than a minute
    if (diff < 60000) {
        return 'Just now';
    }
    
    // Less than an hour
    if (diff < 3600000) {
        const mins = Math.floor(diff / 60000);
        return `${mins}m ago`;
    }
    
    // Less than a day
    if (diff < 86400000) {
        const hours = Math.floor(diff / 3600000);
        return `${hours}h ago`;
    }
    
    // Less than a week
    if (diff < 604800000) {
        const days = Math.floor(diff / 86400000);
        return `${days}d ago`;
    }
    
    // Format as date
    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
    });
}

// Format file size
export function formatSize(bytes) {
    if (bytes === 0) return '0 B';
    
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

// Truncate text
export function truncate(text, maxLength, suffix = '...') {
    if (text.length <= maxLength) return text;
    return text.slice(0, maxLength - suffix.length) + suffix;
}

// Escape HTML
export function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Copy to clipboard
export async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch (err) {
        // Fallback
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        const success = document.execCommand('copy');
        document.body.removeChild(textarea);
        return success;
    }
}

// Generate unique ID
export function generateId() {
    return `id-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

// Wait for element to exist
export function waitForElement(selector, timeout = 5000) {
    return new Promise((resolve, reject) => {
        const element = document.querySelector(selector);
        if (element) {
            return resolve(element);
        }
        
        const observer = new MutationObserver((mutations, obs) => {
            const el = document.querySelector(selector);
            if (el) {
                obs.disconnect();
                resolve(el);
            }
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
        
        setTimeout(() => {
            observer.disconnect();
            reject(new Error(`Element ${selector} not found within ${timeout}ms`));
        }, timeout);
    });
}
