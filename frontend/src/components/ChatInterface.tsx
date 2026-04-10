import { useEffect, useRef, useCallback } from 'react'
import { useChat } from '../hooks/useChat'
import MessageBubble from './MessageBubble'
import InputBar from './InputBar'
import WelcomeScreen from './WelcomeScreen'

interface ChatInterfaceProps {
  theme: 'light' | 'dark'
  conversationId: string | null
  conversationTitle: string | null
  onNeedConversation: (firstMessage: string) => string
  onConversationUpdated: (id: string, sessionId?: string) => void
  onDeleteConversation?: () => void
}

export default function ChatInterface({
  theme,
  conversationId,
  conversationTitle,
  onNeedConversation,
  onConversationUpdated,
  onDeleteConversation,
}: ChatInterfaceProps) {
  const {
    messages,
    isLoading,
    error: chatError,
    sendMessage,
    cancelRequest,
    clearMessages,
    exportChat,
  } = useChat({
    conversationId,
    onNeedConversation,
    onConversationUpdated,
  })

  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const isNearBottomRef = useRef(true)

  const hasConversation = messages.length > 0

  const checkIfNearBottom = useCallback(() => {
    const el = scrollContainerRef.current
    if (!el) return
    const threshold = 120
    isNearBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < threshold
  }, [])

  useEffect(() => {
    if (isNearBottomRef.current) {
      requestAnimationFrame(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
      })
    }
  }, [messages])

  const handleExampleClick = useCallback((question: string) => {
    sendMessage(question)
  }, [sendMessage])

  const handleDelete = useCallback(() => {
    clearMessages()
    onDeleteConversation?.()
  }, [clearMessages, onDeleteConversation])

  const isDark = theme === 'dark'

  return (
    <div className={`flex flex-col h-full rounded-2xl overflow-hidden transition-colors duration-300 ${
      isDark
        ? 'bg-neutral-900/90 backdrop-blur-xl border border-neutral-800 shadow-xl shadow-black/20'
        : 'bg-white/95 backdrop-blur-sm border border-gray-200/80 shadow-xl shadow-gray-300/30'
    }`}>
      {/* Chat header — only visible when there's an active conversation */}
      {hasConversation && (
        <div className={`flex items-center justify-between px-5 py-3 border-b ${
          isDark
            ? 'border-neutral-800 bg-neutral-900/50'
            : 'border-gray-200 bg-gray-50/80'
        }`}>
          <div className="flex items-center gap-2.5 min-w-0">
            <div className={`w-7 h-7 rounded-lg flex-shrink-0 flex items-center justify-center ${
              isDark ? 'bg-indigo-500/10 text-indigo-400' : 'bg-indigo-50 text-indigo-500'
            }`}>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5m.75-9l3-3 2.148 2.148A12.061 12.061 0 0116.5 7.605" />
              </svg>
            </div>
            <div className="min-w-0">
              <h2 className={`text-sm font-semibold leading-tight truncate ${isDark ? 'text-white' : 'text-gray-800'}`}>
                {conversationTitle || 'Census Assistant'}
              </h2>
              {isLoading && (
                <p className={`text-[11px] ${isDark ? 'text-neutral-400' : 'text-gray-500'}`}>
                  <span className="flex items-center gap-1">
                    <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-pulse" />
                    Analyzing...
                  </span>
                </p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-1 flex-shrink-0">
            <button
              onClick={exportChat}
              className={`p-2 rounded-lg transition-colors duration-150 ${
                isDark
                  ? 'text-neutral-400 hover:text-white hover:bg-neutral-800'
                  : 'text-gray-400 hover:text-gray-700 hover:bg-gray-100/50'
              }`}
              title="Export chat"
              aria-label="Export chat as JSON"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
            </button>
            <button
              onClick={handleDelete}
              className={`p-2 rounded-lg transition-colors duration-150 ${
                isDark
                  ? 'text-neutral-400 hover:text-white hover:bg-neutral-800'
                  : 'text-gray-400 hover:text-gray-700 hover:bg-gray-100/50'
              }`}
              title="Delete chat"
              aria-label="Delete chat history"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Messages area or WelcomeScreen */}
      <div
        ref={scrollContainerRef}
        onScroll={checkIfNearBottom}
        className="flex-1 overflow-y-auto px-5 py-4"
      >
        {!hasConversation ? (
          <WelcomeScreen
            theme={theme}
            onExampleClick={handleExampleClick}
            disabled={isLoading}
          />
        ) : (
          <div className="space-y-4" role="log" aria-live="polite" aria-label="Chat messages">
            {chatError && (
              <div role="alert" className={`px-4 py-3 rounded-xl text-sm ${
                isDark
                  ? 'bg-red-950/40 border border-red-900/50 text-red-400'
                  : 'bg-red-50 border border-red-200 text-red-600'
              }`}>
                {chatError}
              </div>
            )}
            {messages.map((message, index) => (
              <div key={message.id} className="message-item">
                <MessageBubble
                  message={message}
                  isLatest={index === messages.length - 1}
                  theme={theme}
                />
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className={`p-4 border-t ${
        isDark
          ? 'bg-neutral-900/50 border-neutral-800'
          : 'bg-gray-50/60 border-gray-200/80'
      }`}>
        <InputBar
          onSend={sendMessage}
          onCancel={cancelRequest}
          isLoading={isLoading}
          placeholder="Ask about US Census data..."
          theme={theme}
        />
        <p className={`text-center text-[11px] mt-2.5 ${isDark ? 'text-neutral-500' : 'text-gray-500'}`}>
          CensusAI uses 2020 ACS data by default · Enter to send · Shift+Enter for new line
        </p>
      </div>
    </div>
  )
}
