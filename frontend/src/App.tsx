import { useState, useEffect, useCallback } from 'react'
import ChatInterface from './components/ChatInterface'
import Sidebar from './components/Sidebar'
import { useTheme } from './hooks/useTheme'
import { useConversations } from './hooks/useConversations'

const getApiBaseUrl = () => {
  const env = import.meta.env.VITE_API_URL
  if (env) {
    return env.replace(/\/+$/, '')
  }
  return ''
}

const DEFAULT_GITHUB_REPO = 'https://github.com/ShubhG24/us-census-chat-agent'

const getGithubRepoUrl = () => {
  const fromEnv = import.meta.env.VITE_GITHUB_REPO_URL?.trim()
  return fromEnv || DEFAULT_GITHUB_REPO
}

function App() {
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isChecking, setIsChecking] = useState(true)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const { theme, toggleTheme } = useTheme()

  const {
    conversations,
    activeId,
    createConversation,
    switchConversation,
    deleteConversation,
    touchConversation,
    startNewChat,
  } = useConversations()

  useEffect(() => {
    checkHealth()
  }, [])

  const checkHealth = async () => {
    setIsChecking(true)
    try {
      const baseUrl = getApiBaseUrl()
      const response = await fetch(`${baseUrl}/health`)
      if (response.ok) {
        setIsConnected(true)
        setError(null)
      } else {
        setIsConnected(false)
        setError('Unable to connect to the server')
      }
    } catch {
      setIsConnected(false)
      setError('Unable to connect to the server. Please ensure the backend is running.')
    } finally {
      setIsChecking(false)
    }
  }

  const handleNeedConversation = useCallback((firstMessage: string): string => {
    return createConversation(firstMessage)
  }, [createConversation])

  const handleConversationUpdated = useCallback((id: string, sessionId?: string) => {
    touchConversation(id, sessionId)
  }, [touchConversation])

  const handleNewChat = useCallback(() => {
    startNewChat()
    setSidebarOpen(false)
  }, [startNewChat])

  const handleSwitchChat = useCallback((id: string) => {
    switchConversation(id)
    setSidebarOpen(false)
  }, [switchConversation])

  const isDark = theme === 'dark'

  const activeTitle = conversations.find(c => c.id === activeId)?.title ?? null

  return (
    <div className={`h-screen flex flex-col relative overflow-hidden transition-colors duration-500 ${
      isDark ? 'bg-neutral-950' : 'bg-gray-100'
    }`}>
      {/* Fluid background */}
      <div
        className={`fluid-bg ${isDark ? 'fluid-bg--dark' : 'fluid-bg--light'}`}
        aria-hidden="true"
      >
        <div className="fluid-blob fluid-blob--a" />
        <div className="fluid-blob fluid-blob--b" />
        <div className="fluid-blob fluid-blob--c" />
        <div className="fluid-blob fluid-blob--d" />
      </div>

      {/* Header */}
      <header className={`relative z-10 flex-shrink-0 border-b ${
        isDark
          ? 'bg-neutral-950/90 backdrop-blur-xl border-neutral-800'
          : 'bg-white border-gray-200'
      }`}>
        <div className="px-4 sm:px-6 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {/* Mobile hamburger */}
              <button
                onClick={() => setSidebarOpen(true)}
                className={`md:hidden p-2 rounded-lg transition-colors ${
                  isDark ? 'text-neutral-400 hover:bg-neutral-800' : 'text-gray-500 hover:bg-gray-100'
                }`}
                aria-label="Open sidebar"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>

              <div>
                <h1 className={`text-xl font-bold flex items-center gap-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                  Census<span className="gradient-text">AI</span>
                </h1>
                <p className={`text-sm hidden sm:block ${isDark ? 'text-slate-400' : 'text-gray-600'}`}>
                  Explore US population data with natural language
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 sm:gap-3">
              <a
                href={`${getApiBaseUrl()}/health`}
                title={isChecking ? 'Checking status...' : isConnected ? 'All systems online' : 'System issues — click for details'}
                aria-label="System status"
                className="flex items-center justify-center"
              >
                <span
                  className={`block w-2 h-2 rounded-full transition-all duration-500 ${
                    isChecking
                      ? 'bg-yellow-400 animate-pulse shadow-[0_0_6px_rgba(250,204,21,0.6)]'
                      : isConnected
                        ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]'
                        : 'bg-red-500 animate-pulse shadow-[0_0_6px_rgba(239,68,68,0.6)]'
                  }`}
                />
              </a>
              <a
                href={getGithubRepoUrl()}
                target="_blank"
                rel="noopener noreferrer"
                className={`p-2 sm:p-2.5 rounded-xl transition-all duration-200 ${
                  isDark
                    ? 'bg-neutral-900 hover:bg-neutral-800 text-neutral-300 hover:text-white'
                    : 'bg-gray-100 hover:bg-gray-200 text-gray-600 border border-gray-200'
                }`}
                title="View source on GitHub"
                aria-label="View source on GitHub"
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    fillRule="evenodd"
                    d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
                    clipRule="evenodd"
                  />
                </svg>
              </a>
              <button
                onClick={toggleTheme}
                className={`p-2 sm:p-2.5 rounded-xl transition-all duration-200 ${
                  isDark
                    ? 'bg-neutral-900 hover:bg-neutral-800 text-yellow-400'
                    : 'bg-gray-100 hover:bg-gray-200 text-gray-600 border border-gray-200'
                }`}
                title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
                aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
              >
                {isDark ? (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                  </svg>
                )}
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main: Sidebar + Chat */}
      <div className="relative z-10 flex flex-1 overflow-hidden">
        <Sidebar
          conversations={conversations}
          activeId={activeId}
          onNew={handleNewChat}
          onSwitch={handleSwitchChat}
          onDelete={deleteConversation}
          theme={theme}
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(c => !c)}
        />

        {/* Chat panel */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* Error banner */}
          {error && (
            <div className={`mx-4 mt-4 p-3 border rounded-xl flex items-center justify-between text-sm ${
              isDark
                ? 'bg-red-950/30 border-red-900/50 text-red-400'
                : 'bg-red-50/80 border-red-200/50 text-red-700'
            }`}>
              <div className="flex items-center gap-2">
                <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span>{error}</span>
              </div>
              <button
                onClick={checkHealth}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                  isDark
                    ? 'bg-red-950/50 hover:bg-red-900 text-red-400'
                    : 'bg-red-100 hover:bg-red-200 text-red-700'
                }`}
              >
                Retry
              </button>
            </div>
          )}

          <div className="flex-1 overflow-hidden p-4 sm:p-6">
            <div className="h-full max-w-4xl mx-auto">
              <ChatInterface
                theme={theme}
                conversationId={activeId}
                conversationTitle={activeTitle}
                onNeedConversation={handleNeedConversation}
                onConversationUpdated={handleConversationUpdated}
                onDeleteConversation={activeId ? () => deleteConversation(activeId) : undefined}
              />
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}

export default App
