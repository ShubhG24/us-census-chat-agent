import { useState, useRef, useEffect, useMemo, memo, lazy, Suspense, useCallback } from 'react'
import { Message } from '../hooks/useChat'

const ReactMarkdown = lazy(() => import('react-markdown'))

const SQL_BLOCK_RE = /```sql[\s\S]*?```/gi

interface MessageBubbleProps {
  message: Message
  isLatest?: boolean
  theme: 'light' | 'dark'
}

export default memo(function MessageBubble({ message, isLatest, theme }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const isDark = theme === 'dark'
  const [copied, setCopied] = useState(false)
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const streamingDone = !message.isStreaming

  useEffect(() => {
    return () => {
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current)
    }
  }, [])

  const handleCopy = useCallback(async () => {
    if (message.sqlQuery) {
      try {
        await navigator.clipboard.writeText(message.sqlQuery)
        setCopied(true)
        if (copyTimerRef.current) clearTimeout(copyTimerRef.current)
        copyTimerRef.current = setTimeout(() => setCopied(false), 2000)
      } catch {
        // Clipboard not available
      }
    }
  }, [message.sqlQuery])

  const displayContent = useMemo(() => {
    if (!message.content) return ''
    if (message.sqlQuery) {
      return message.content.replace(SQL_BLOCK_RE, '').trim()
    }
    return message.content
  }, [message.content, message.sqlQuery])

  const hasThinkingStep = Boolean(message.sqlQuery || (message.statusUpdates && message.statusUpdates.length > 0))

  return (
    <div className={`flex msg-appear ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[85%] rounded-2xl px-4 py-3 ${
        isUser
          ? 'bg-indigo-500/90 text-white'
          : isDark
            ? 'bg-neutral-800/80 text-neutral-100 border border-neutral-700/50'
            : 'bg-white text-gray-800 border border-gray-200/80 shadow-md shadow-gray-200/40'
      }`}>
        {isUser ? (
          <p className="whitespace-pre-wrap leading-relaxed text-[15px]">{message.content}</p>
        ) : (
          <div className="markdown-content">
            {message.isStreaming && !message.content && !hasThinkingStep && (
              <div className="flex items-center gap-2 py-1">
                <div className="flex gap-1">
                  <div className="typing-dot w-1.5 h-1.5 bg-indigo-400 rounded-full" />
                  <div className="typing-dot w-1.5 h-1.5 bg-indigo-400 rounded-full" />
                  <div className="typing-dot w-1.5 h-1.5 bg-indigo-400 rounded-full" />
                </div>
                <span className={`text-sm ${isDark ? 'text-neutral-400' : 'text-gray-400'}`}>Thinking...</span>
              </div>
            )}

            {hasThinkingStep && (
              <ThinkingSection
                message={message}
                isDark={isDark}
                streamingDone={streamingDone}
                copied={copied}
                onCopy={handleCopy}
              />
            )}

            {displayContent && (
              <div className="content-appear">
                <Suspense fallback={<p className="text-sm">{displayContent}</p>}>
                  <ReactMarkdown>{displayContent}</ReactMarkdown>
                </Suspense>
                {message.isStreaming && isLatest && (
                  <span className="inline-block w-0.5 h-5 bg-indigo-500 ml-0.5 animate-pulse rounded-full" />
                )}
              </div>
            )}
          </div>
        )}

        <div className={`text-[10px] mt-2 ${
          isUser
            ? 'text-indigo-200'
            : isDark ? 'text-neutral-500' : 'text-gray-400'
        }`}>
          {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
    </div>
  )
})


function ThinkingSection({
  message,
  isDark,
  streamingDone,
  copied,
  onCopy,
}: {
  message: Message
  isDark: boolean
  streamingDone: boolean
  copied: boolean
  onCopy: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const contentRef = useRef<HTMLDivElement>(null)
  const isWorking = !streamingDone && !message.error

  const toggle = useCallback(() => setExpanded(prev => !prev), [])

  return (
    <div className="mb-3">
      {/* Summary bar — always visible */}
      <button
        type="button"
        onClick={toggle}
        className={`w-full cursor-pointer flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors duration-150 select-none ${
          isDark
            ? 'bg-neutral-700/40 hover:bg-neutral-700/70 text-neutral-400'
            : 'bg-gray-100 hover:bg-gray-150 text-gray-600 border border-gray-200/60'
        }`}
      >
        {isWorking ? (
          <svg className="w-3.5 h-3.5 animate-spin text-indigo-500 flex-shrink-0" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        ) : (
          <svg className={`w-3.5 h-3.5 transition-transform duration-200 ease-out flex-shrink-0 ${expanded ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        )}
        <span>{isWorking ? 'Working...' : 'Thought process'}</span>

        {message.statusUpdates && message.statusUpdates.length > 0 && (
          <div className="flex flex-wrap gap-1.5 ml-1">
            {message.statusUpdates.map((status, i) => {
              const isLast = i === message.statusUpdates!.length - 1
              const showSpinner = !streamingDone && isLast
              const hasFailed = streamingDone && !!message.error
              const isFailedStep = hasFailed && isLast
              const label = streamingDone && /running/i.test(status)
                ? isFailedStep
                  ? status.replace(/running/i, 'Query failed')
                  : status.replace(/running/i, 'Ran')
                : status
              return (
                <span
                  key={`${status}-${i}`}
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium transition-colors duration-300 ${
                    showSpinner
                      ? isDark ? 'bg-indigo-500/10 text-indigo-400' : 'bg-indigo-50 text-indigo-600'
                      : isFailedStep
                        ? isDark ? 'bg-red-500/10 text-red-400' : 'bg-red-50 text-red-600'
                        : isDark ? 'bg-emerald-500/10 text-emerald-400' : 'bg-emerald-50 text-emerald-600'
                  }`}
                >
                  {showSpinner ? (
                    <svg className="w-2.5 h-2.5 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                  ) : isFailedStep ? (
                    <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  ) : (
                    <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                  {label}
                </span>
              )
            })}
          </div>
        )}
      </button>

      {/* Animated collapsible content */}
      <div
        className="collapsible-body"
        style={{
          height: expanded ? contentRef.current?.scrollHeight ?? 'auto' : 0,
        }}
      >
        <div ref={contentRef}>
          {message.sqlQuery && (
            <div className={`mt-2 rounded-xl overflow-hidden ${isDark ? 'bg-black' : 'bg-[#f6f8fa]'}`}>
              <div className={`flex items-center justify-between px-4 py-2 ${
                isDark ? 'bg-[#2f2f2f]' : 'bg-[#e8ecf0]'
              }`}>
                <span className={`text-xs ${isDark ? 'text-[#b4b4b4]' : 'text-gray-500'}`}>SQL</span>
                <button
                  onClick={onCopy}
                  className={`text-xs flex items-center gap-1.5 transition-colors duration-150 ${
                    isDark ? 'text-[#b4b4b4] hover:text-white' : 'text-gray-500 hover:text-gray-900'
                  }`}
                  aria-label="Copy SQL query"
                >
                  {copied ? (
                    <>
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      Copied!
                    </>
                  ) : (
                    <>
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                      </svg>
                      Copy code
                    </>
                  )}
                </button>
              </div>
              <pre className={`sql-block px-4 py-3 overflow-x-auto text-[13px] leading-relaxed font-mono m-0 ${
                isDark ? 'bg-black text-[#f8f8f2]' : 'bg-[#f6f8fa] text-gray-800'
              }`}>
                <code className="sql-code">{message.sqlQuery}</code>
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
