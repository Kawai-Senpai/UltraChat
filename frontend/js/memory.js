/**
 * UltraChat - Memory Module
 * Handles memory management.
 */

import { memoriesAPI } from './api.js';
import { getState, setState, subscribe } from './state.js';
import { $, $$, createElement, addClass, removeClass, show, hide, clearChildren, formatDate, truncate } from './utils/dom.js';
import { toast } from './utils/toast.js';
import { confirm } from './utils/modal.js';

// DOM Elements
let memoriesList;
let memoryContent;
let memoryCategory;
let memoryImportance;
let addMemoryBtn;
let memoryStats;
let filterCategory;

// Initialize memory module
export function initMemory() {
    // Get DOM elements
    memoriesList = $('memories-list');
    memoryContent = $('memory-content');
    memoryCategory = $('memory-category');
    memoryImportance = $('memory-importance');
    addMemoryBtn = $('btn-add-memory');
    memoryStats = $('memory-stats');
    filterCategory = $('filter-category');
    
    // Setup event listeners
    if (addMemoryBtn) {
        addMemoryBtn.addEventListener('click', addMemory);
    }
    
    if (filterCategory) {
        filterCategory.addEventListener('change', () => {
            loadMemories(filterCategory.value || null);
        });
    }
    
    // Subscribe to state changes
    subscribe('memories', renderMemories);
    
    // Listen for view changes
    window.addEventListener('viewChange', (e) => {
        if (e.detail.view === 'memory') {
            loadMemories();
            loadCategories();
            loadStats();
        }
    });
}

// Load memories
async function loadMemories(category = null) {
    try {
        const data = await memoriesAPI.listMemories(category);
        setState('memories', data.memories || []);
    } catch (error) {
        console.error('Failed to load memories:', error);
        toast.error('Failed to load memories');
    }
}

// Load categories
async function loadCategories() {
    try {
        const data = await memoriesAPI.getCategories();
        
        if (filterCategory && data.categories) {
            // Clear existing options except first
            while (filterCategory.options.length > 1) {
                filterCategory.remove(1);
            }
            
            // Add categories
            for (const cat of data.categories) {
                const option = createElement('option', {
                    value: cat.name,
                    textContent: `${cat.name} (${cat.count})`,
                });
                filterCategory.appendChild(option);
            }
        }
    } catch (error) {
        console.error('Failed to load categories:', error);
    }
}

// Load stats
async function loadStats() {
    try {
        const data = await memoriesAPI.getStats();
        renderStats(data);
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

// Render stats
function renderStats(data) {
    if (!memoryStats) return;
    
    clearChildren(memoryStats);
    
    const stats = [
        { label: 'Total Memories', value: data.total_count || 0, icon: '📝' },
        { label: 'Active', value: data.active_count || 0, icon: '✅' },
        { label: 'Categories', value: Object.keys(data.categories || {}).length, icon: '📂' },
        { label: 'Avg Importance', value: (data.avg_importance || 0).toFixed(1), icon: '⭐' },
    ];
    
    for (const stat of stats) {
        const card = createElement('div', { className: 'stat-card' }, [
            createElement('div', { className: 'stat-icon', textContent: stat.icon }),
            createElement('div', { className: 'stat-info' }, [
                createElement('div', { className: 'stat-value', textContent: stat.value }),
                createElement('div', { className: 'stat-label', textContent: stat.label }),
            ]),
        ]);
        memoryStats.appendChild(card);
    }
}

// Render memories
function renderMemories(memories) {
    if (!memoriesList) return;
    
    clearChildren(memoriesList);
    
    if (!memories || memories.length === 0) {
        const empty = createElement('div', {
            className: 'empty-state',
        }, [
            createElement('div', { className: 'empty-state-icon', textContent: '🧠' }),
            createElement('div', { className: 'empty-state-title', textContent: 'No memories yet' }),
            createElement('div', { className: 'empty-state-description', textContent: 'Add memories to help the AI remember important information' }),
        ]);
        memoriesList.appendChild(empty);
        return;
    }
    
    for (const memory of memories) {
        const item = createMemoryItem(memory);
        memoriesList.appendChild(item);
    }
}

// Create memory item
function createMemoryItem(memory) {
    const { id, content, category, importance, is_active, source, created_at } = memory;
    
    const item = createElement('div', {
        className: `memory-item ${is_active ? '' : 'inactive'}`,
        dataset: { memoryId: id },
    });
    
    // Header
    const header = createElement('div', { className: 'memory-header' });
    
    // Category badge
    const categoryBadge = createElement('span', {
        className: `badge badge-${category || 'other'}`,
        textContent: category || 'other',
    });
    header.appendChild(categoryBadge);
    
    // Importance stars
    const stars = createElement('span', {
        className: 'memory-importance',
        textContent: '★'.repeat(Math.min(importance || 5, 10)),
    });
    header.appendChild(stars);
    
    // Toggle
    const toggleBtn = createElement('button', {
        className: `btn-icon btn-sm ${is_active ? 'active' : ''}`,
        title: is_active ? 'Disable memory' : 'Enable memory',
        innerHTML: is_active ? '✓' : '○',
        onClick: async (e) => {
            e.stopPropagation();
            try {
                await memoriesAPI.toggleMemory(id);
                loadMemories(filterCategory?.value || null);
            } catch (error) {
                toast.error('Failed to toggle memory');
            }
        },
    });
    header.appendChild(toggleBtn);
    
    item.appendChild(header);
    
    // Content
    const contentEl = createElement('div', {
        className: 'memory-content',
        textContent: truncate(content, 200),
    });
    item.appendChild(contentEl);
    
    // Footer
    const footer = createElement('div', { className: 'memory-footer' });
    
    // Source
    if (source) {
        footer.appendChild(createElement('span', {
            className: 'memory-source',
            textContent: source === 'user' ? 'Manual' : 'Extracted',
        }));
    }
    
    // Date
    footer.appendChild(createElement('span', {
        className: 'memory-date',
        textContent: formatDate(created_at),
    }));
    
    // Delete button
    const deleteBtn = createElement('button', {
        className: 'btn-icon btn-sm btn-danger',
        title: 'Delete memory',
        innerHTML: '×',
        onClick: async (e) => {
            e.stopPropagation();
            const confirmed = await confirm({
                title: 'Delete Memory',
                message: 'Are you sure you want to delete this memory?',
                confirmText: 'Delete',
                danger: true,
            });
            if (confirmed) {
                try {
                    await memoriesAPI.deleteMemory(id);
                    loadMemories(filterCategory?.value || null);
                    toast.success('Memory deleted');
                } catch (error) {
                    toast.error('Failed to delete memory');
                }
            }
        },
    });
    footer.appendChild(deleteBtn);
    
    item.appendChild(footer);
    
    return item;
}

// Add memory
async function addMemory() {
    const content = memoryContent?.value?.trim();
    if (!content) {
        toast.warning('Please enter memory content');
        return;
    }
    
    const category = memoryCategory?.value || 'fact';
    const importance = parseInt(memoryImportance?.value || '5', 10);
    
    try {
        await memoriesAPI.createMemory({
            content,
            category,
            importance,
        });
        
        // Clear form
        if (memoryContent) memoryContent.value = '';
        
        // Reload
        loadMemories();
        loadStats();
        
        toast.success('Memory added');
    } catch (error) {
        console.error('Failed to add memory:', error);
        toast.error(error.message || 'Failed to add memory');
    }
}

export default { initMemory };
