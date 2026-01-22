import { useState, useEffect } from 'react'
import { useToast } from '../contexts/ToastContext'
import { useApp } from '../contexts/AppContext'
import { memoriesAPI } from '../lib/api'
import { 
  ArrowLeft, Plus, Trash2, Brain, Tag, Star, 
  Filter, X, Lightbulb, MessageSquare, Info, Settings, FileText
} from 'lucide-react'

const CATEGORY_CONFIG = {
  context: { icon: MessageSquare, color: 'blue', label: 'Context' },
  preference: { icon: Settings, color: 'purple', label: 'Preference' },
  instruction: { icon: FileText, color: 'green', label: 'Instruction' },
  fact: { icon: Info, color: 'yellow', label: 'Fact' },
}

export default function MemoryView({ onBack }) {
  const { toast } = useToast()
  const { currentProfile } = useApp()
  
  const [memories, setMemories] = useState([])
  const [categories, setCategories] = useState([])
  const [selectedCategory, setSelectedCategory] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [showAddForm, setShowAddForm] = useState(false)
  const [newMemory, setNewMemory] = useState({ content: '', category: 'context', importance: 5 })

  useEffect(() => {
    loadMemories()
    loadCategories()
  }, [selectedCategory])

  const loadMemories = async () => {
    setIsLoading(true)
    try {
      const data = await memoriesAPI.listMemories(selectedCategory || null)
      setMemories(data.memories || [])
    } catch (error) {
      toast.error('Failed to load memories')
    } finally {
      setIsLoading(false)
    }
  }

  const loadCategories = async () => {
    try {
      const data = await memoriesAPI.getCategories()
      setCategories(data.categories || [])
    } catch (error) {
      console.error('Failed to load categories:', error)
    }
  }

  const handleAdd = async () => {
    if (!newMemory.content.trim()) {
      toast.error('Content is required')
      return
    }

    try {
      await memoriesAPI.createMemory(newMemory)
      toast.success('Memory added')
      setNewMemory({ content: '', category: 'context', importance: 5 })
      setShowAddForm(false)
      loadMemories()
    } catch (error) {
      toast.error('Failed to add memory: ' + error.message)
    }
  }

  const handleDelete = async (memory) => {
    if (!confirm('Delete this memory?')) return
    
    try {
      await memoriesAPI.deleteMemory(memory.id)
      toast.success('Memory deleted')
      loadMemories()
    } catch (error) {
      toast.error('Failed to delete')
    }
  }

  const formatDate = (dateStr) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const getCategoryConfig = (category) => {
    return CATEGORY_CONFIG[category] || CATEGORY_CONFIG.context
  }

  const getImportanceColor = (importance) => {
    if (importance >= 8) return 'text-red-400'
    if (importance >= 5) return 'text-yellow-400'
    return 'text-neutral-400'
  }

  const allCategories = Object.keys(CATEGORY_CONFIG)

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
          <h1 className="text-sm font-black text-white">Memory</h1>
          <p className="text-[10px] text-neutral-500">Persistent context the AI remembers about you</p>
        </div>
        <button
          onClick={() => setShowAddForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-red-500 hover:bg-red-600
                     text-white text-xs font-bold rounded-lg transition-all"
        >
          <Plus className="w-4 h-4" />
          Add Memory
        </button>
      </header>

      <div className="flex-1 overflow-y-auto p-4 md:p-6">
        <div className="max-w-3xl mx-auto space-y-6">
          
          {/* Info Banner */}
          <div className="flex items-start gap-4 p-4 bg-purple-500/10 border border-purple-500/20 rounded-xl">
            <div className="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center flex-shrink-0">
              <Brain className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <h3 className="text-xs font-bold text-white mb-1">How Memory Works</h3>
              <p className="text-[10px] text-neutral-400 leading-relaxed">
                Memories are facts, preferences, and instructions that persist across conversations. 
                The AI uses them to provide personalized responses. Higher importance means 
                the memory is more likely to be included in context.
              </p>
            </div>
          </div>
          
          {/* Category Filter */}
          <div className="flex flex-wrap items-center gap-2">
            <Filter className="w-4 h-4 text-neutral-500" />
            <button
              onClick={() => setSelectedCategory('')}
              className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
                !selectedCategory 
                  ? 'bg-red-500 text-white' 
                  : 'bg-white/5 text-neutral-400 hover:bg-white/10'
              }`}
            >
              All
            </button>
            {allCategories.map(cat => {
              const config = getCategoryConfig(cat)
              return (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(cat === selectedCategory ? '' : cat)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg transition-colors ${
                    selectedCategory === cat
                      ? `bg-${config.color}-500/30 text-${config.color}-400`
                      : 'bg-white/5 text-neutral-400 hover:bg-white/10'
                  }`}
                >
                  <config.icon className="w-3 h-3" />
                  {config.label}
                </button>
              )
            })}
          </div>

          {/* Add Form Modal */}
          {showAddForm && (
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fadeIn">
              <div className="w-full max-w-lg bg-neutral-900 border border-white/10 rounded-2xl p-6 animate-fadeIn">
                <div className="flex items-center justify-between mb-5">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center">
                      <Lightbulb className="w-5 h-5 text-purple-400" />
                    </div>
                    <h3 className="text-sm font-black text-white">Add Memory</h3>
                  </div>
                  <button
                    onClick={() => setShowAddForm(false)}
                    className="p-2 rounded-lg hover:bg-white/10 text-neutral-400"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
                
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-bold text-neutral-300 mb-2">
                      What should I remember?
                    </label>
                    <textarea
                      value={newMemory.content}
                      onChange={(e) => setNewMemory(prev => ({ ...prev, content: e.target.value }))}
                      placeholder="e.g., 'My name is John and I prefer Python for backend development'"
                      rows={4}
                      className="w-full px-4 py-3 bg-neutral-950 border border-white/10 rounded-lg
                                 text-xs text-white placeholder-neutral-500 resize-none
                                 focus:outline-none focus:border-red-500/50"
                    />
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-bold text-neutral-300 mb-2">Category</label>
                      <select
                        value={newMemory.category}
                        onChange={(e) => setNewMemory(prev => ({ ...prev, category: e.target.value }))}
                        className="w-full px-4 py-2.5 bg-neutral-950 border border-white/10 rounded-lg
                                   text-xs text-white focus:outline-none focus:border-red-500/50"
                      >
                        {allCategories.map(cat => (
                          <option key={cat} value={cat}>{getCategoryConfig(cat).label}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-neutral-300 mb-2">
                        Importance ({newMemory.importance}/10)
                      </label>
                      <input
                        type="range"
                        min="1"
                        max="10"
                        value={newMemory.importance}
                        onChange={(e) => setNewMemory(prev => ({ ...prev, importance: parseInt(e.target.value) }))}
                        className="w-full mt-2"
                      />
                    </div>
                  </div>

                  <div className="flex gap-3 pt-2">
                    <button
                      onClick={handleAdd}
                      className="flex-1 px-4 py-2.5 bg-red-500 hover:bg-red-600 text-white text-xs font-bold rounded-lg"
                    >
                      Save Memory
                    </button>
                    <button
                      onClick={() => setShowAddForm(false)}
                      className="px-4 py-2.5 bg-white/10 hover:bg-white/20 text-white text-xs rounded-lg"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Memories List */}
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3, 4].map(i => (
                <div key={i} className="p-4 bg-white/5 rounded-xl border border-white/10">
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 rounded-xl skeleton" />
                    <div className="flex-1 space-y-2">
                      <div className="h-4 w-full skeleton rounded" />
                      <div className="h-4 w-2/3 skeleton rounded" />
                      <div className="flex gap-2 mt-2">
                        <div className="h-5 w-16 skeleton rounded" />
                        <div className="h-5 w-20 skeleton rounded" />
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : memories.length === 0 ? (
            <div className="text-center py-16">
              <div className="w-20 h-20 mx-auto mb-4 rounded-2xl bg-white/5 flex items-center justify-center">
                <Brain className="w-10 h-10 text-neutral-600" />
              </div>
              <div className="text-sm font-medium text-neutral-400 mb-1">No memories yet</div>
              <div className="text-xs text-neutral-500 mb-6">
                {selectedCategory 
                  ? `No memories in the "${getCategoryConfig(selectedCategory).label}" category`
                  : 'Add memories to help the AI remember important things about you'
                }
              </div>
              <button
                onClick={() => setShowAddForm(true)}
                className="inline-flex items-center gap-2 px-4 py-2 bg-red-500 hover:bg-red-600
                           text-white text-xs font-medium rounded-lg transition-all"
              >
                <Plus className="w-4 h-4" />
                Add Your First Memory
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {memories.map((memory) => {
                const config = getCategoryConfig(memory.category)
                const IconComponent = config.icon
                
                return (
                  <div
                    key={memory.id}
                    className="p-4 bg-white/5 border border-white/10 rounded-xl hover:bg-white/[0.07] 
                               transition-colors group"
                  >
                    <div className="flex items-start gap-4">
                      <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0
                        bg-${config.color}-500/20`}>
                        <IconComponent className={`w-5 h-5 text-${config.color}-400`} />
                      </div>
                      
                      <div className="flex-1 min-w-0">
                        <p className="text-xs text-neutral-200 leading-relaxed mb-3">
                          {memory.content}
                        </p>
                        
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 
                            bg-${config.color}-500/20 text-${config.color}-400 text-[10px] rounded`}>
                            <IconComponent className="w-3 h-3" />
                            {config.label}
                          </span>
                          
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 
                            bg-white/5 text-[10px] rounded ${getImportanceColor(memory.importance)}`}>
                            <Star className="w-3 h-3" />
                            {memory.importance}/10
                          </span>
                          
                          <span className="text-[10px] text-neutral-600">
                            {formatDate(memory.created_at)}
                          </span>
                        </div>
                      </div>
                      
                      <button
                        onClick={() => handleDelete(memory)}
                        className="p-2 rounded-lg hover:bg-red-500/20 text-neutral-500 hover:text-red-400
                                   opacity-0 group-hover:opacity-100 transition-all"
                        title="Delete memory"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
