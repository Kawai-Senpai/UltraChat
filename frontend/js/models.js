/**
 * UltraChat - Models Module
 * Handles model management and selection.
 */

import { modelsAPI } from './api.js';
import { getState, setState, subscribe } from './state.js';
import { $, $$, createElement, addClass, removeClass, show, hide, clearChildren, formatSize } from './utils/dom.js';
import { toast } from './utils/toast.js';
import { confirm } from './utils/modal.js';

// DOM Elements
let modelsList;
let pullModelInput;
let pullButton;
let pullProgress;
let refreshButton;

// Initialize models module
export function initModels() {
    // Get DOM elements
    modelsList = $('models-list');
    pullModelInput = $('pull-model-name');
    pullButton = $('btn-pull-model');
    pullProgress = $('pull-progress');
    refreshButton = $('btn-refresh-models');
    
    // Setup event listeners
    if (pullButton) {
        pullButton.addEventListener('click', pullModel);
    }
    
    if (refreshButton) {
        refreshButton.addEventListener('click', loadModels);
    }
    
    if (pullModelInput) {
        pullModelInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                pullModel();
            }
        });
    }
    
    // Subscribe to state changes
    subscribe('models', renderModels);
    subscribe('currentModel', highlightCurrentModel);
    
    // Listen for view changes
    window.addEventListener('viewChange', (e) => {
        if (e.detail.view === 'models') {
            loadModels();
        }
    });
}

// Load models
async function loadModels() {
    try {
        const data = await modelsAPI.listModels();
        setState('models', data.models || []);
    } catch (error) {
        console.error('Failed to load models:', error);
        toast.error('Failed to load models');
    }
}

// Render models
function renderModels(models) {
    if (!modelsList) return;
    
    clearChildren(modelsList);
    
    if (!models || models.length === 0) {
        const empty = createElement('div', {
            className: 'empty-state',
        }, [
            createElement('div', { className: 'empty-state-icon', textContent: '📦' }),
            createElement('div', { className: 'empty-state-title', textContent: 'No models found' }),
            createElement('div', { className: 'empty-state-description', textContent: 'Download a model to get started' }),
        ]);
        modelsList.appendChild(empty);
        return;
    }
    
    for (const model of models) {
        const item = createModelItem(model);
        modelsList.appendChild(item);
    }
    
    highlightCurrentModel(getState('currentModel'));
}

// Create model item
function createModelItem(model) {
    const { name, size, modified_at, parameter_size, quantization_level, is_favorite } = model;
    
    const item = createElement('div', {
        className: 'model-item',
        dataset: { modelName: name },
    });
    
    // Click to select
    item.addEventListener('click', () => {
        setState('currentModel', name);
        toast.success(`Model set to ${name}`);
    });
    
    // Model info
    const info = createElement('div', { className: 'model-info' });
    
    // Name row
    const nameRow = createElement('div', { className: 'model-name' }, [
        is_favorite ? createElement('span', { textContent: '⭐ ' }) : null,
        document.createTextNode(name),
    ].filter(Boolean));
    info.appendChild(nameRow);
    
    // Meta row
    const metaItems = [];
    if (size) metaItems.push(formatSize(size));
    if (parameter_size) metaItems.push(parameter_size);
    if (quantization_level) metaItems.push(quantization_level);
    
    if (metaItems.length > 0) {
        const meta = createElement('div', {
            className: 'model-meta',
            textContent: metaItems.join(' • '),
        });
        info.appendChild(meta);
    }
    
    item.appendChild(info);
    
    // Actions
    const actions = createElement('div', { className: 'model-actions' });
    
    // Favorite button
    const favBtn = createElement('button', {
        className: `btn-icon btn-sm ${is_favorite ? 'active' : ''}`,
        title: is_favorite ? 'Remove from favorites' : 'Add to favorites',
        innerHTML: `<svg width="14" height="14" viewBox="0 0 24 24" fill="${is_favorite ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
        </svg>`,
        onClick: async (e) => {
            e.stopPropagation();
            try {
                await modelsAPI.setFavorite(name, !is_favorite);
                loadModels();
            } catch (error) {
                toast.error('Failed to update favorite');
            }
        },
    });
    actions.appendChild(favBtn);
    
    // Delete button
    const deleteBtn = createElement('button', {
        className: 'btn-icon btn-sm btn-danger',
        title: 'Delete model',
        innerHTML: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
        </svg>`,
        onClick: async (e) => {
            e.stopPropagation();
            const confirmed = await confirm({
                title: 'Delete Model',
                message: `Are you sure you want to delete "${name}"? This cannot be undone.`,
                confirmText: 'Delete',
                danger: true,
            });
            if (confirmed) {
                try {
                    await modelsAPI.deleteModel(name);
                    loadModels();
                    toast.success('Model deleted');
                } catch (error) {
                    toast.error('Failed to delete model');
                }
            }
        },
    });
    actions.appendChild(deleteBtn);
    
    item.appendChild(actions);
    
    return item;
}

// Highlight current model
function highlightCurrentModel(modelName) {
    const items = document.querySelectorAll('.model-item');
    items.forEach(item => {
        removeClass(item, 'active');
        if (item.dataset.modelName === modelName) {
            addClass(item, 'active');
        }
    });
}

// Pull model
async function pullModel() {
    const name = pullModelInput?.value?.trim();
    if (!name) {
        toast.warning('Please enter a model name');
        return;
    }
    
    // Show progress
    if (pullProgress) {
        show(pullProgress);
    }
    if (pullButton) {
        pullButton.disabled = true;
    }
    
    try {
        await modelsAPI.pullModel(name, (event, data) => {
            if (event === 'progress') {
                updatePullProgress(data);
            } else if (event === 'done') {
                toast.success(`Model ${name} downloaded successfully`);
                loadModels();
            } else if (event === 'error') {
                toast.error(data.message || 'Failed to download model');
            }
        });
    } catch (error) {
        console.error('Pull model error:', error);
        toast.error(error.message || 'Failed to download model');
    } finally {
        if (pullProgress) {
            hide(pullProgress);
        }
        if (pullButton) {
            pullButton.disabled = false;
        }
        if (pullModelInput) {
            pullModelInput.value = '';
        }
    }
}

// Update pull progress
function updatePullProgress(data) {
    if (!pullProgress) return;
    
    const progressFill = pullProgress.querySelector('.progress-fill');
    const progressText = pullProgress.querySelector('.progress-text');
    
    if (data.total && data.completed) {
        const percent = Math.round((data.completed / data.total) * 100);
        if (progressFill) {
            progressFill.style.width = `${percent}%`;
        }
        if (progressText) {
            progressText.textContent = `Downloading... ${percent}%`;
        }
    } else if (data.status) {
        if (progressText) {
            progressText.textContent = data.status;
        }
    }
}

export default { initModels };
