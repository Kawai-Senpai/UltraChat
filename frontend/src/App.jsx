import { useState, useEffect, useRef, useCallback } from 'react'
import Sidebar from './components/Sidebar'
import ChatView from './components/ChatView'
import ModelsView from './components/ModelsView'
import SettingsView from './components/SettingsView'
import MemoryView from './components/MemoryView'
import ProfilesView from './components/ProfilesView'
import Toast from './components/ui/Toast'
import { ToastProvider } from './contexts/ToastContext'
import { AppProvider } from './contexts/AppContext'

function App() {
  const [currentView, setCurrentView] = useState('chat')
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const handleNavigation = useCallback((view) => {
    setCurrentView(view)
    setSidebarOpen(false) // Close sidebar on mobile after navigation
  }, [])

  const toggleSidebar = useCallback(() => {
    setSidebarOpen(prev => !prev)
  }, [])

  const closeSidebar = useCallback(() => {
    setSidebarOpen(false)
  }, [])

  return (
    <AppProvider>
      <ToastProvider>
        <div className="flex h-screen w-screen overflow-hidden bg-neutral-950">
          {/* Sidebar Overlay (mobile) */}
          {sidebarOpen && (
            <div 
              className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden"
              onClick={closeSidebar}
            />
          )}

          {/* Sidebar */}
          <Sidebar 
            isOpen={sidebarOpen}
            onNavigate={handleNavigation}
            currentView={currentView}
            onToggle={toggleSidebar}
          />

          {/* Main Content */}
          <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
            {currentView === 'chat' && (
              <ChatView onToggleSidebar={toggleSidebar} />
            )}
            {currentView === 'models' && (
              <ModelsView onBack={() => handleNavigation('chat')} />
            )}
            {currentView === 'settings' && (
              <SettingsView onBack={() => handleNavigation('chat')} />
            )}
            {currentView === 'memory' && (
              <MemoryView onBack={() => handleNavigation('chat')} />
            )}
            {currentView === 'profiles' && (
              <ProfilesView onBack={() => handleNavigation('chat')} />
            )}
          </main>

          {/* Toast Container */}
          <Toast />
        </div>
      </ToastProvider>
    </AppProvider>
  )
}

export default App
