import { useState, useEffect } from 'react'
import { useApp } from '../contexts/AppContext'
import { chatAPI } from '../lib/api'
import { useToast } from '../contexts/ToastContext'
import { 
  Menu, X, Plus, MessageSquare, Box, Settings, Brain, User, Trash2, 
  Search, ChevronDown, Zap, Clock
} from 'lucide-react'

export default function Sidebar({ isOpen, onNavigate, currentView, onToggle }) {
  const { 
    conversations, loadConversations, currentConversation, loadConversation, 
    setMessages, currentProfile, profiles, setCurrentProfile
  } = useApp()
  const { toast } = useToast()
  const [searchQuery, setSearchQuery] = useState('')
  const [hoveredId, setHoveredId] = useState(null)
  const [showProfileDropdown, setShowProfileDropdown] = useState(false)

  useEffect(() => {
    loadConversations()
  }, [loadConversations])

  const handleNewChat = () => {
    loadConversation(null)
    setMessages([])
    onNavigate('chat')
  }

  const handleSelectConversation = (conv) => {
    loadConversation(conv.id)
    onNavigate('chat')
  }

  const handleDeleteConversation = async (e, conv) => {
    e.stopPropagation()
    if (!confirm(`Delete "${conv.title || 'Untitled'}"?`)) return
    
    try {
      await chatAPI.deleteConversation(conv.id)
      toast.success('Conversation deleted')
      loadConversations()
      if (currentConversation?.id === conv.id) {
        loadConversation(null)
      }
    } catch (error) {
      toast.error('Failed to delete conversation')
    }
  }

  const handleProfileChange = (profile) => {
    setCurrentProfile(profile)
    setShowProfileDropdown(false)
    toast.success(`Switched to ${profile.name}`)
  }

  // Group conversations by date
  const groupedConversations = groupByDate(conversations)

  // Filter conversations
  const filteredGroups = searchQuery
    ? { 'Search Results': conversations.filter(c => 
        c.title?.toLowerCase().includes(searchQuery.toLowerCase())
      )}
    : groupedConversations

  const navItems = [
    { id: 'models', label: 'Models', icon: Box, description: 'Download & manage' },
    { id: 'memory', label: 'Memory', icon: Brain, description: 'AI remembers' },
    { id: 'profiles', label: 'Profiles', icon: User, description: 'AI personas' },
    { id: 'settings', label: 'Settings', icon: Settings, description: 'Preferences' },
  ]

  return (
    <aside 
      className={`
        fixed md:relative inset-y-0 left-0 z-50
        w-72 h-full bg-neutral-900/95 backdrop-blur-sm border-r border-white/10
        flex flex-col
        transform transition-transform duration-300 ease-out
        ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
      `}
    >
      {/* Header with Profile Switcher */}
      <div className="p-4 border-b border-white/10">
        {/* Brand */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-red-500/20 flex items-center justify-center">
              <Zap className="w-4 h-4 text-red-400" />
            </div>
            <span className="text-sm font-black text-white">UltraChat</span>
          </div>
          <button 
            onClick={onToggle}
            className="md:hidden p-2 rounded-lg hover:bg-white/10 text-neutral-400 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Profile Switcher */}
        <div className="relative">
          <button
            onClick={() => setShowProfileDropdown(!showProfileDropdown)}
            className="w-full flex items-center gap-3 p-2.5 bg-white/5 hover:bg-white/10 
                       border border-white/10 rounded-lg transition-colors group"
          >
            <div className="w-8 h-8 rounded-full bg-red-500/20 flex items-center justify-center">
              <User className="w-4 h-4 text-red-400" />
            </div>
            <div className="flex-1 text-left min-w-0">
              <div className="text-xs font-bold text-white truncate">
                {currentProfile?.name || 'Default'}
              </div>
              <div className="text-[10px] text-neutral-500 truncate">
                {currentProfile?.system_prompt?.slice(0, 30) || 'No system prompt'}...
              </div>
            </div>
            <ChevronDown className={`w-4 h-4 text-neutral-400 transition-transform ${showProfileDropdown ? 'rotate-180' : ''}`} />
          </button>

          {/* Profile Dropdown */}
          {showProfileDropdown && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-neutral-900 border border-white/10 
                            rounded-lg shadow-xl z-50 max-h-64 overflow-y-auto animate-fadeIn">
              {profiles.map(profile => (
                <button
                  key={profile.id}
                  onClick={() => handleProfileChange(profile)}
                  className={`w-full flex items-center gap-3 p-3 hover:bg-white/10 transition-colors
                    ${currentProfile?.id === profile.id ? 'bg-red-500/10' : ''}`}
                >
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center
                    ${currentProfile?.id === profile.id ? 'bg-red-500/30' : 'bg-white/10'}`}>
                    <User className={`w-4 h-4 ${currentProfile?.id === profile.id ? 'text-red-400' : 'text-neutral-400'}`} />
                  </div>
                  <div className="flex-1 text-left">
                    <div className="text-xs font-medium text-white">{profile.name}</div>
                    {profile.is_default && (
                      <span className="text-[10px] text-neutral-500">Default</span>
                    )}
                  </div>
                  {currentProfile?.id === profile.id && (
                    <div className="w-2 h-2 rounded-full bg-red-500 animate-pulseGlow" />
                  )}
                </button>
              ))}
              <button
                onClick={() => { setShowProfileDropdown(false); onNavigate('profiles') }}
                className="w-full flex items-center gap-3 p-3 border-t border-white/10 
                           hover:bg-white/10 text-red-400 transition-colors"
              >
                <Plus className="w-4 h-4" />
                <span className="text-xs font-medium">Manage Profiles</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* New Chat Button */}
      <div className="p-4">
        <button
          onClick={handleNewChat}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 
                     bg-red-500 hover:bg-red-600 text-white text-xs font-bold 
                     rounded-lg transition-all hover:scale-[1.02] active:scale-[0.98]"
        >
          <Plus className="w-4 h-4" />
          New Chat
        </button>
      </div>

      {/* Search */}
      <div className="px-4 pb-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-500" />
          <input
            type="text"
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg
                       text-xs text-white placeholder-neutral-500
                       focus:outline-none focus:border-red-500/50 transition-colors"
          />
        </div>
      </div>

      {/* Conversations List */}
      <div className="flex-1 overflow-y-auto px-3">
        {Object.entries(filteredGroups).map(([group, convs]) => (
          convs.length > 0 && (
            <div key={group} className="mb-4">
              <div className="flex items-center gap-2 px-2 py-2">
                <Clock className="w-3 h-3 text-neutral-600" />
                <span className="text-[10px] font-bold text-neutral-500 uppercase tracking-wider">
                  {group}
                </span>
              </div>
              <div className="space-y-0.5">
                {convs.map(conv => (
                  <div
                    key={conv.id}
                    onClick={() => handleSelectConversation(conv)}
                    onMouseEnter={() => setHoveredId(conv.id)}
                    onMouseLeave={() => setHoveredId(null)}
                    className={`
                      w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left
                      transition-all group cursor-pointer
                      ${currentConversation?.id === conv.id 
                        ? 'bg-red-500/20 text-white' 
                        : 'text-neutral-400 hover:bg-white/5 hover:text-white'}
                    `}
                  >
                    <MessageSquare className={`w-4 h-4 flex-shrink-0 ${currentConversation?.id === conv.id ? 'text-red-400' : ''}`} />
                    <span className="flex-1 truncate text-xs">
                      {conv.title || 'Untitled'}
                    </span>
                    {hoveredId === conv.id && (
                      <button
                        onClick={(e) => handleDeleteConversation(e, conv)}
                        className="p-1.5 rounded-md hover:bg-red-500/20 text-red-400 
                                   opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )
        ))}
        
        {conversations.length === 0 && (
          <div className="text-center py-12">
            <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-white/5 flex items-center justify-center">
              <MessageSquare className="w-6 h-6 text-neutral-600" />
            </div>
            <div className="text-xs text-neutral-500 font-medium">No conversations</div>
            <div className="text-[10px] text-neutral-600 mt-1">Start a new chat above</div>
          </div>
        )}
      </div>

      {/* Navigation Footer */}
      <div className="p-3 border-t border-white/10 space-y-1">
        {navItems.map(item => (
          <button
            key={item.id}
            onClick={() => onNavigate(item.id)}
            className={`
              w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs
              transition-all
              ${currentView === item.id
                ? 'bg-white/10 text-white'
                : 'text-neutral-400 hover:bg-white/5 hover:text-white'}
            `}
          >
            <item.icon className="w-4 h-4" />
            <div className="flex-1 text-left">
              <div className="font-medium">{item.label}</div>
              <div className="text-[10px] text-neutral-500">{item.description}</div>
            </div>
          </button>
        ))}
      </div>
    </aside>
  )
}

// Helper to group conversations by date
function groupByDate(conversations) {
  const groups = {
    'Today': [],
    'Yesterday': [],
    'This Week': [],
    'This Month': [],
    'Older': [],
  }
  
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  const weekAgo = new Date(today)
  weekAgo.setDate(weekAgo.getDate() - 7)
  const monthAgo = new Date(today)
  monthAgo.setMonth(monthAgo.getMonth() - 1)
  
  for (const conv of conversations) {
    const date = new Date(conv.updated_at || conv.created_at)
    
    if (date >= today) {
      groups['Today'].push(conv)
    } else if (date >= yesterday) {
      groups['Yesterday'].push(conv)
    } else if (date >= weekAgo) {
      groups['This Week'].push(conv)
    } else if (date >= monthAgo) {
      groups['This Month'].push(conv)
    } else {
      groups['Older'].push(conv)
    }
  }
  
  // Remove empty groups
  return Object.fromEntries(
    Object.entries(groups).filter(([_, v]) => v.length > 0)
  )
}
