/**
 * UltraChat - Profiles Module
 * Handles profile management.
 */

import { profilesAPI, modelsAPI } from './api.js';
import { getState, setState, subscribe } from './state.js';
import { $, $$, createElement, addClass, removeClass, show, hide, clearChildren } from './utils/dom.js';
import { toast } from './utils/toast.js';
import { confirm } from './utils/modal.js';

// DOM Elements
let profilesList;
let profileTemplates;
let createProfileForm;
let profileModelSelect;
let tempSlider;
let tempValue;

// Initialize profiles module
export function initProfiles() {
    // Get DOM elements
    profilesList = $('profiles-list');
    profileTemplates = $('profile-templates');
    createProfileForm = $('create-profile-form');
    profileModelSelect = $('profile-model');
    tempSlider = $('profile-temp');
    tempValue = $('temp-value');
    
    // Setup event listeners
    if (createProfileForm) {
        createProfileForm.addEventListener('submit', handleCreateProfile);
    }
    
    if (tempSlider && tempValue) {
        tempSlider.addEventListener('input', () => {
            tempValue.textContent = tempSlider.value;
        });
    }
    
    // Subscribe to state changes
    subscribe('profiles', renderProfiles);
    subscribe('currentProfileId', highlightCurrentProfile);
    
    // Listen for view changes
    window.addEventListener('viewChange', async (e) => {
        if (e.detail.view === 'profiles') {
            await loadProfiles();
            await loadTemplates();
            await loadModelsForSelect();
        }
    });
}

// Load profiles
async function loadProfiles() {
    try {
        const data = await profilesAPI.listProfiles();
        setState('profiles', data.profiles || []);
    } catch (error) {
        console.error('Failed to load profiles:', error);
        toast.error('Failed to load profiles');
    }
}

// Load templates
async function loadTemplates() {
    try {
        const data = await profilesAPI.getTemplates();
        renderTemplates(data.templates || []);
    } catch (error) {
        console.error('Failed to load templates:', error);
    }
}

// Load models for select
async function loadModelsForSelect() {
    try {
        const data = await modelsAPI.listModels();
        
        if (profileModelSelect && data.models) {
            clearChildren(profileModelSelect);
            
            // Add empty option
            const emptyOption = createElement('option', {
                value: '',
                textContent: 'Use default model',
            });
            profileModelSelect.appendChild(emptyOption);
            
            // Add models
            for (const model of data.models) {
                const option = createElement('option', {
                    value: model.name,
                    textContent: model.name,
                });
                profileModelSelect.appendChild(option);
            }
        }
    } catch (error) {
        console.error('Failed to load models:', error);
    }
}

// Render templates
function renderTemplates(templates) {
    if (!profileTemplates) return;
    
    clearChildren(profileTemplates);
    
    for (const template of templates) {
        const item = createElement('div', {
            className: 'template-item',
        }, [
            createElement('div', { className: 'template-icon', textContent: template.icon || '📝' }),
            createElement('div', { className: 'template-info' }, [
                createElement('div', { className: 'template-name', textContent: template.name }),
                createElement('div', { className: 'template-description', textContent: template.description }),
            ]),
        ]);
        
        item.addEventListener('click', () => applyTemplate(template));
        profileTemplates.appendChild(item);
    }
}

// Apply template
function applyTemplate(template) {
    const nameInput = $('profile-name');
    const systemInput = $('profile-system');
    const tempInput = $('profile-temp');
    
    if (nameInput) nameInput.value = template.name;
    if (systemInput) systemInput.value = template.system_prompt || '';
    if (tempInput && template.temperature !== undefined) {
        tempInput.value = template.temperature;
        if (tempValue) tempValue.textContent = template.temperature;
    }
    
    toast.info(`Template "${template.name}" applied`);
}

// Render profiles
function renderProfiles(profiles) {
    if (!profilesList) return;
    
    clearChildren(profilesList);
    
    if (!profiles || profiles.length === 0) {
        const empty = createElement('div', {
            className: 'empty-state',
        }, [
            createElement('div', { className: 'empty-state-icon', textContent: '👤' }),
            createElement('div', { className: 'empty-state-title', textContent: 'No profiles yet' }),
            createElement('div', { className: 'empty-state-description', textContent: 'Create a profile to save custom settings' }),
        ]);
        profilesList.appendChild(empty);
        return;
    }
    
    for (const profile of profiles) {
        const item = createProfileItem(profile);
        profilesList.appendChild(item);
    }
    
    highlightCurrentProfile(getState('currentProfileId'));
}

// Create profile item
function createProfileItem(profile) {
    const { id, name, description, model, temperature, is_default } = profile;
    
    const item = createElement('div', {
        className: `profile-item ${is_default ? 'default' : ''}`,
        dataset: { profileId: id },
    });
    
    // Click to select
    item.addEventListener('click', () => {
        setState('currentProfileId', id);
        toast.success(`Profile set to ${name}`);
    });
    
    // Info
    const info = createElement('div', { className: 'profile-info' });
    
    // Name row
    const nameRow = createElement('div', { className: 'profile-name' }, [
        is_default ? createElement('span', { className: 'default-badge', textContent: '✓ ' }) : null,
        document.createTextNode(name),
    ].filter(Boolean));
    info.appendChild(nameRow);
    
    // Meta
    const metaItems = [];
    if (model) metaItems.push(model);
    if (temperature !== undefined) metaItems.push(`temp: ${temperature}`);
    
    if (metaItems.length > 0) {
        const meta = createElement('div', {
            className: 'profile-meta',
            textContent: metaItems.join(' • '),
        });
        info.appendChild(meta);
    }
    
    item.appendChild(info);
    
    // Actions
    const actions = createElement('div', { className: 'profile-actions' });
    
    // Set default button
    if (!is_default) {
        const defaultBtn = createElement('button', {
            className: 'btn-icon btn-sm',
            title: 'Set as default',
            innerHTML: '★',
            onClick: async (e) => {
                e.stopPropagation();
                try {
                    await profilesAPI.setDefault(id);
                    loadProfiles();
                    toast.success('Default profile updated');
                } catch (error) {
                    toast.error('Failed to set default');
                }
            },
        });
        actions.appendChild(defaultBtn);
    }
    
    // Duplicate button
    const dupBtn = createElement('button', {
        className: 'btn-icon btn-sm',
        title: 'Duplicate profile',
        innerHTML: '📋',
        onClick: async (e) => {
            e.stopPropagation();
            try {
                await profilesAPI.duplicateProfile(id);
                loadProfiles();
                toast.success('Profile duplicated');
            } catch (error) {
                toast.error('Failed to duplicate');
            }
        },
    });
    actions.appendChild(dupBtn);
    
    // Delete button
    const deleteBtn = createElement('button', {
        className: 'btn-icon btn-sm btn-danger',
        title: 'Delete profile',
        innerHTML: '×',
        onClick: async (e) => {
            e.stopPropagation();
            const confirmed = await confirm({
                title: 'Delete Profile',
                message: `Are you sure you want to delete "${name}"?`,
                confirmText: 'Delete',
                danger: true,
            });
            if (confirmed) {
                try {
                    await profilesAPI.deleteProfile(id);
                    if (getState('currentProfileId') === id) {
                        setState('currentProfileId', null);
                    }
                    loadProfiles();
                    toast.success('Profile deleted');
                } catch (error) {
                    toast.error('Failed to delete');
                }
            }
        },
    });
    actions.appendChild(deleteBtn);
    
    item.appendChild(actions);
    
    return item;
}

// Highlight current profile
function highlightCurrentProfile(profileId) {
    const items = document.querySelectorAll('.profile-item');
    items.forEach(item => {
        removeClass(item, 'active');
        if (item.dataset.profileId === profileId) {
            addClass(item, 'active');
        }
    });
}

// Handle create profile
async function handleCreateProfile(e) {
    e.preventDefault();
    
    const name = $('profile-name')?.value?.trim();
    const systemPrompt = $('profile-system')?.value?.trim();
    const model = $('profile-model')?.value || null;
    const temperature = parseFloat($('profile-temp')?.value || '0.7');
    const maxTokens = parseInt($('profile-max-tokens')?.value || '4096', 10);
    
    if (!name) {
        toast.warning('Please enter a profile name');
        return;
    }
    
    try {
        await profilesAPI.createProfile({
            name,
            system_prompt: systemPrompt || null,
            model: model || null,
            temperature,
            max_tokens: maxTokens,
        });
        
        // Clear form
        createProfileForm.reset();
        if (tempValue) tempValue.textContent = '0.7';
        
        // Reload
        loadProfiles();
        
        toast.success('Profile created');
    } catch (error) {
        console.error('Failed to create profile:', error);
        toast.error(error.message || 'Failed to create profile');
    }
}

export default { initProfiles };
