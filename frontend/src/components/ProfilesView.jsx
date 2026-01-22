import { useState, useEffect } from 'react'
import { useApp } from '../contexts/AppContext'
import { useToast } from '../contexts/ToastContext'
import { profilesAPI } from '../lib/api'
import { 
  ArrowLeft, Plus, Trash2, Check, User, Edit3, X, 
  Sparkles, Code, BookOpen, Coffee, Briefcase, Palette, 
  GraduationCap, Heart, Shield, Zap
} from 'lucide-react'

const PROFILE_ICONS = [
  { icon: User, color: 'red' },
  { icon: Code, color: 'blue' },
  { icon: BookOpen, color: 'green' },
  { icon: Coffee, color: 'yellow' },
  { icon: Briefcase, color: 'purple' },
  { icon: Palette, color: 'pink' },
  { icon: GraduationCap, color: 'cyan' },
  { icon: Heart, color: 'red' },
  { icon: Shield, color: 'orange' },
  { icon: Zap, color: 'yellow' },
]

export default function ProfilesView({ onBack }) {
  const { profiles, loadProfiles, currentProfile, setCurrentProfile, localModels, loadLocalModels } = useApp()
  const { toast } = useToast()
  
  const [isLoading, setIsLoading] = useState(true)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [editingProfile, setEditingProfile] = useState(null)
  const [templates, setTemplates] = useState([])
  const [newProfile, setNewProfile] = useState({
    name: '',
    system_prompt: '',
    model: '',
    temperature: 0.7,
    max_tokens: 2048,
  })

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setIsLoading(true)
    try {
      await Promise.all([
        loadProfiles(),
        loadLocalModels(),
        loadTemplates(),
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const loadTemplates = async () => {
    try {
      const data = await profilesAPI.getTemplates()
      setTemplates(data.templates || [])
    } catch (error) {
      console.error('Failed to load templates:', error)
    }
  }

  const handleCreate = async () => {
    if (!newProfile.name.trim()) {
      toast.error('Name is required')
      return
    }

    try {
      await profilesAPI.createProfile(newProfile)
      toast.success('Profile created')
      setNewProfile({ name: '', system_prompt: '', model: '', temperature: 0.7, max_tokens: 2048 })
      setShowCreateForm(false)
      loadProfiles()
    } catch (error) {
      toast.error('Failed to create: ' + error.message)
    }
  }

  const handleUpdate = async () => {
    if (!editingProfile?.name?.trim()) {
      toast.error('Name is required')
      return
    }

    try {
      await profilesAPI.updateProfile(editingProfile.id, editingProfile)
      toast.success('Profile updated')
      setEditingProfile(null)
      loadProfiles()
    } catch (error) {
      toast.error('Failed to update: ' + error.message)
    }
  }

  const handleDelete = async (profile) => {
    if (profile.is_default) {
      toast.error('Cannot delete default profile')
      return
    }
    if (!confirm(`Delete "${profile.name}"? All associated settings will be lost.`)) return
    
    try {
      await profilesAPI.deleteProfile(profile.id)
      toast.success('Profile deleted')
      if (currentProfile?.id === profile.id) {
        const defaultProfile = profiles.find(p => p.is_default)
        if (defaultProfile) setCurrentProfile(defaultProfile)
      }
      loadProfiles()
    } catch (error) {
      toast.error('Failed to delete')
    }
  }

  const handleSelect = (profile) => {
    setCurrentProfile(profile)
    toast.success(`Switched to ${profile.name}`)
  }

  const handleUseTemplate = (template) => {
    setNewProfile({
      name: template.name,
      system_prompt: template.system_prompt,
      model: '',
      temperature: 0.7,
      max_tokens: 2048,
    })
    setShowCreateForm(true)
  }

  const getProfileIcon = (index) => {
    const iconData = PROFILE_ICONS[index % PROFILE_ICONS.length]
    return iconData
  }

  if (isLoading) {
    return (
      <div className="flex flex-col h-full overflow-hidden bg-neutral-950">
        <header className="flex items-center gap-3 px-4 py-3 border-b border-white/10 bg-neutral-900/80">
          <div className="w-10 h-10 rounded-lg skeleton" />
          <div className="flex-1 space-y-2">
            <div className="h-4 w-24 skeleton rounded" />
            <div className="h-3 w-48 skeleton rounded" />
          </div>
        </header>
        <div className="flex-1 p-6 space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="p-4 bg-white/5 rounded-xl flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl skeleton" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-32 skeleton rounded" />
                <div className="h-3 w-48 skeleton rounded" />
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full overflow-hidden bg-neutral-950">
      {/* Header */}
      <header className="flex items-center gap-3 px-4 py-3 border-b border-white/10 bg-neutral-900/80 backdrop-blur-sm">
        <button
          onClick={onBack}
          className="p-2 rounded-lg hover:bg-white/10 text-neutral-400 transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1">
          <h1 className="text-sm font-black text-white">Profiles</h1>
          <p className="text-[10px] text-neutral-500">AI personas with custom settings and personalities</p>
        </div>
        <button
          onClick={() => setShowCreateForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-red-500 hover:bg-red-600
                     text-white text-xs font-bold rounded-lg transition-all"
        >
          <Plus className="w-4 h-4" />
          Create Profile
        </button>
      </header>

      <div className="flex-1 overflow-y-auto p-4 md:p-6">
        <div className="max-w-3xl mx-auto space-y-6">
          
          {/* Info Banner */}
          <div className="flex items-start gap-4 p-4 bg-blue-500/10 border border-blue-500/20 rounded-xl">
            <div className="w-10 h-10 rounded-xl bg-blue-500/20 flex items-center justify-center flex-shrink-0">
              <Sparkles className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h3 className="text-xs font-bold text-white mb-1">How Profiles Work</h3>
              <p className="text-[10px] text-neutral-400 leading-relaxed">
                Each profile is a complete AI persona. When you switch profiles, everything changes: 
                the model used, temperature settings, system prompts, and conversation history. 
                Think of profiles as different AI assistants for different purposes.
              </p>
            </div>
          </div>
          
          {/* Create Form Modal */}
          {showCreateForm && (
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fadeIn">
              <div className="w-full max-w-lg bg-neutral-900 border border-white/10 rounded-2xl p-6 animate-fadeIn">
                <div className="flex items-center justify-between mb-5">
                  <h3 className="text-sm font-black text-white">Create Profile</h3>
                  <button
                    onClick={() => setShowCreateForm(false)}
                    className="p-2 rounded-lg hover:bg-white/10 text-neutral-400"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
                
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-bold text-neutral-300 mb-2">Profile Name</label>
                    <input
                      type="text"
                      value={newProfile.name}
                      onChange={(e) => setNewProfile(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="e.g., Code Assistant, Writing Helper"
                      className="w-full px-4 py-2.5 bg-neutral-950 border border-white/10 rounded-lg
                                 text-xs text-white placeholder-neutral-500
                                 focus:outline-none focus:border-red-500/50"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-xs font-bold text-neutral-300 mb-2">System Prompt</label>
                    <textarea
                      value={newProfile.system_prompt}
                      onChange={(e) => setNewProfile(prev => ({ ...prev, system_prompt: e.target.value }))}
                      placeholder="Describe how this AI should behave. e.g., 'You are a helpful coding assistant specializing in Python...'"
                      rows={4}
                      className="w-full px-4 py-2.5 bg-neutral-950 border border-white/10 rounded-lg
                                 text-xs text-white placeholder-neutral-500 resize-none
                                 focus:outline-none focus:border-red-500/50"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-bold text-neutral-300 mb-2">Model</label>
                      <select
                        value={newProfile.model}
                        onChange={(e) => setNewProfile(prev => ({ ...prev, model: e.target.value }))}
                        className="w-full px-4 py-2.5 bg-neutral-950 border border-white/10 rounded-lg
                                   text-xs text-white focus:outline-none focus:border-red-500/50"
                      >
                        <option value="">Use default</option>
                        {localModels.map(m => (
                          <option key={m.model_id} value={m.model_id}>{m.model_id}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-neutral-300 mb-2">
                        Temperature ({newProfile.temperature})
                      </label>
                      <input
                        type="range"
                        min="0"
                        max="2"
                        step="0.1"
                        value={newProfile.temperature}
                        onChange={(e) => setNewProfile(prev => ({ ...prev, temperature: parseFloat(e.target.value) }))}
                        className="w-full mt-2"
                      />
                    </div>
                  </div>

                  <div className="flex gap-3 pt-2">
                    <button
                      onClick={handleCreate}
                      className="flex-1 px-4 py-2.5 bg-red-500 hover:bg-red-600 text-white text-xs font-bold rounded-lg"
                    >
                      Create Profile
                    </button>
                    <button
                      onClick={() => setShowCreateForm(false)}
                      className="px-4 py-2.5 bg-white/10 hover:bg-white/20 text-white text-xs rounded-lg"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Edit Modal */}
          {editingProfile && (
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fadeIn">
              <div className="w-full max-w-lg bg-neutral-900 border border-white/10 rounded-2xl p-6 animate-fadeIn">
                <div className="flex items-center justify-between mb-5">
                  <h3 className="text-sm font-black text-white">Edit Profile</h3>
                  <button
                    onClick={() => setEditingProfile(null)}
                    className="p-2 rounded-lg hover:bg-white/10 text-neutral-400"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
                
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-bold text-neutral-300 mb-2">Profile Name</label>
                    <input
                      type="text"
                      value={editingProfile.name}
                      onChange={(e) => setEditingProfile(prev => ({ ...prev, name: e.target.value }))}
                      className="w-full px-4 py-2.5 bg-neutral-950 border border-white/10 rounded-lg
                                 text-xs text-white focus:outline-none focus:border-red-500/50"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-xs font-bold text-neutral-300 mb-2">System Prompt</label>
                    <textarea
                      value={editingProfile.system_prompt || ''}
                      onChange={(e) => setEditingProfile(prev => ({ ...prev, system_prompt: e.target.value }))}
                      rows={4}
                      className="w-full px-4 py-2.5 bg-neutral-950 border border-white/10 rounded-lg
                                 text-xs text-white resize-none focus:outline-none focus:border-red-500/50"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-bold text-neutral-300 mb-2">Model</label>
                      <select
                        value={editingProfile.model || ''}
                        onChange={(e) => setEditingProfile(prev => ({ ...prev, model: e.target.value }))}
                        className="w-full px-4 py-2.5 bg-neutral-950 border border-white/10 rounded-lg
                                   text-xs text-white focus:outline-none focus:border-red-500/50"
                      >
                        <option value="">Use default</option>
                        {localModels.map(m => (
                          <option key={m.model_id} value={m.model_id}>{m.model_id}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-neutral-300 mb-2">
                        Temperature ({editingProfile.temperature || 0.7})
                      </label>
                      <input
                        type="range"
                        min="0"
                        max="2"
                        step="0.1"
                        value={editingProfile.temperature || 0.7}
                        onChange={(e) => setEditingProfile(prev => ({ ...prev, temperature: parseFloat(e.target.value) }))}
                        className="w-full mt-2"
                      />
                    </div>
                  </div>

                  <div className="flex gap-3 pt-2">
                    <button
                      onClick={handleUpdate}
                      className="flex-1 px-4 py-2.5 bg-red-500 hover:bg-red-600 text-white text-xs font-bold rounded-lg"
                    >
                      Save Changes
                    </button>
                    <button
                      onClick={() => setEditingProfile(null)}
                      className="px-4 py-2.5 bg-white/10 hover:bg-white/20 text-white text-xs rounded-lg"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Templates */}
          {templates.length > 0 && !showCreateForm && (
            <div>
              <h3 className="text-xs font-black text-neutral-400 mb-3">Quick Start Templates</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {templates.map((template, idx) => (
                  <button
                    key={template.name}
                    onClick={() => handleUseTemplate(template)}
                    className="flex items-start gap-3 p-4 text-left bg-white/5 border border-white/10 
                               rounded-xl hover:bg-white/10 hover:border-white/20 transition-all group"
                  >
                    <div className="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center flex-shrink-0">
                      <Sparkles className="w-5 h-5 text-purple-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-bold text-white mb-1">{template.name}</div>
                      <div className="text-[10px] text-neutral-500 line-clamp-2">
                        {template.description || template.system_prompt?.slice(0, 80) + '...'}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Profiles List */}
          <div>
            <h3 className="text-xs font-black text-neutral-400 mb-3">Your Profiles</h3>
            
            {profiles.length === 0 ? (
              <div className="text-center py-12">
                <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-white/5 flex items-center justify-center">
                  <User className="w-8 h-8 text-neutral-600" />
                </div>
                <div className="text-sm font-medium text-neutral-400 mb-1">No profiles yet</div>
                <div className="text-xs text-neutral-500">Create your first profile to get started</div>
              </div>
            ) : (
              <div className="space-y-3">
                {profiles.map((profile, idx) => {
                  const iconData = getProfileIcon(idx)
                  const IconComponent = iconData.icon
                  const isActive = currentProfile?.id === profile.id
                  
                  return (
                    <div
                      key={profile.id}
                      className={`p-4 rounded-xl border transition-all ${
                        isActive
                          ? 'bg-red-500/10 border-red-500/30'
                          : 'bg-white/5 border-white/10 hover:bg-white/10'
                      }`}
                    >
                      <div className="flex items-start gap-4">
                        <div className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0
                          ${isActive ? 'bg-red-500/30' : 'bg-white/10'}`}>
                          <IconComponent className={`w-6 h-6 ${isActive ? 'text-red-400' : 'text-neutral-400'}`} />
                        </div>
                        
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-sm font-bold text-white">{profile.name}</span>
                            {profile.is_default && (
                              <span className="px-1.5 py-0.5 bg-white/10 text-neutral-400 text-[10px] rounded">
                                Default
                              </span>
                            )}
                            {isActive && (
                              <span className="flex items-center gap-1 px-1.5 py-0.5 bg-red-500/20 text-red-400 text-[10px] rounded">
                                <div className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
                                Active
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-neutral-500 line-clamp-2">
                            {profile.system_prompt || 'No system prompt defined'}
                          </p>
                          <div className="flex items-center gap-3 mt-2 text-[10px] text-neutral-500">
                            {profile.model && (
                              <span className="px-1.5 py-0.5 bg-white/5 rounded">{profile.model}</span>
                            )}
                            <span>Temp: {profile.temperature || 0.7}</span>
                          </div>
                        </div>
                        
                        <div className="flex items-center gap-1">
                          {!isActive && (
                            <button
                              onClick={() => handleSelect(profile)}
                              className="flex items-center gap-1.5 px-3 py-1.5 bg-green-500/20 hover:bg-green-500/30
                                         text-green-400 text-xs font-medium rounded-lg transition-colors"
                            >
                              <Check className="w-3.5 h-3.5" />
                              Use
                            </button>
                          )}
                          <button
                            onClick={() => setEditingProfile({ ...profile })}
                            className="p-2 rounded-lg hover:bg-white/10 text-neutral-400 transition-colors"
                            title="Edit"
                          >
                            <Edit3 className="w-4 h-4" />
                          </button>
                          {!profile.is_default && (
                            <button
                              onClick={() => handleDelete(profile)}
                              className="p-2 rounded-lg hover:bg-red-500/20 text-neutral-500 hover:text-red-400 transition-colors"
                              title="Delete"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
