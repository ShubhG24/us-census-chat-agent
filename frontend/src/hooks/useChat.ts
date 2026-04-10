import { useState, useCallback, useRef, useEffect } from 'react'
import { loadMessages, saveMessages, loadSessionId, saveSessionId } from '../lib/storage'

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  isStreaming?: boolean
  sqlQuery?: string
  error?: string
  exampleQuestions?: string[]
  statusUpdates?: string[]
}

interface UseChatOptions {
  conversationId: string | null
  onNeedConversation?: (firstMessage: string) => string
  onConversationUpdated?: (id: string, sessionId?: string) => void
}

const getApiUrl = () => {
  const env = import.meta.env.VITE_API_URL
  if (env) {
    return `${env.replace(/\/+$/, '')}/api`
  }
  return '/api'
}

export function useChat({ conversationId, onNeedConversation, onConversationUpdated }: UseChatOptions) {
  const apiUrl = getApiUrl()
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const isLoadingRef = useRef(false)
  const conversationIdRef = useRef(conversationId)
  const messagesRef = useRef<Message[]>([])
  const justCreatedRef = useRef(false)

  useEffect(() => {
    conversationIdRef.current = conversationId
    if (justCreatedRef.current) {
      justCreatedRef.current = false
      return
    }
    if (conversationId) {
      const stored = loadMessages(conversationId)
      setMessages(stored)
      messagesRef.current = stored
      const restoredSession = loadSessionId(conversationId)
      setSessionId(restoredSession)
    } else {
      setMessages([])
      messagesRef.current = []
      setSessionId(null)
    }
    setError(null)
  }, [conversationId])

  const persistMessages = useCallback((msgs: Message[], convId: string | null) => {
    if (convId) {
      saveMessages(convId, msgs)
    }
  }, [])

  const addMessage = useCallback((message: Omit<Message, 'id' | 'timestamp'>) => {
    const newMessage: Message = {
      ...message,
      id: crypto.randomUUID(),
      timestamp: new Date(),
    }
    setMessages(prev => {
      const next = [...prev, newMessage]
      messagesRef.current = next
      return next
    })
    return newMessage.id
  }, [])

  const updateMessage = useCallback((id: string, updates: Partial<Message>) => {
    setMessages(prev => {
      const next = prev.map(msg => (msg.id === id ? { ...msg, ...updates } : msg))
      messagesRef.current = next
      return next
    })
  }, [])

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isLoadingRef.current) return

    let activeConvId = conversationIdRef.current
    if (!activeConvId && onNeedConversation) {
      const title = content.length > 40 ? content.slice(0, 40) + '...' : content
      justCreatedRef.current = true
      activeConvId = onNeedConversation(title)
      conversationIdRef.current = activeConvId
    }

    if (!activeConvId) return

    isLoadingRef.current = true
    setError(null)
    setIsLoading(true)

    addMessage({ role: 'user', content })

    const assistantId = addMessage({
      role: 'assistant',
      content: '',
      isStreaming: true,
    })

    abortControllerRef.current = new AbortController()

    try {
      const response = await fetch(`${apiUrl}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: content,
          session_id: sessionId,
        }),
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No response body')

      const decoder = new TextDecoder()
      let fullContent = ''
      let currentSqlQuery: string | undefined
      let statusUpdates: string[] = []
      let buffer = ''
      let rafHandle = 0
      let pendingContent = ''
      let hasError = false

      const cleanDisplay = (text: string) => {
        let out = text.replace(/```sql[\s\S]*?```/gi, '')
        out = out.replace(/```sql[\s\S]*$/gi, '')
        out = out.replace(/`{1,3}$/g, '')
        return out.trim()
      }

      const flushContent = () => {
        const display = cleanDisplay(fullContent)
        if (pendingContent !== display) {
          pendingContent = display
          updateMessage(assistantId, { content: display })
        }
        rafHandle = 0
      }

      const scheduleFlush = () => {
        if (!rafHandle) {
          rafHandle = requestAnimationFrame(flushContent)
        }
      }

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))

              switch (data.type) {
                case 'session':
                  setSessionId(data.session_id)
                  if (activeConvId) saveSessionId(activeConvId, data.session_id)
                  break

                case 'text':
                case 'text_delta':
                  fullContent += data.content
                  scheduleFlush()
                  break

                case 'status': {
                  const clean = data.content
                    .replace(/^\s*\*?\s*/, '')
                    .replace(/\s*\*?\s*$/, '')
                    .trim()
                  if (clean) {
                    statusUpdates = [...statusUpdates, clean]
                    updateMessage(assistantId, { statusUpdates })
                  }
                  break
                }

                case 'error':
                  fullContent += data.content
                  hasError = true
                  updateMessage(assistantId, {
                    content: fullContent,
                    error: data.content,
                  })
                  break

                case 'sql':
                  currentSqlQuery = data.query
                  updateMessage(assistantId, {
                    content: cleanDisplay(fullContent),
                    sqlQuery: currentSqlQuery,
                  })
                  break

                case 'done':
                  if (rafHandle) {
                    cancelAnimationFrame(rafHandle)
                    rafHandle = 0
                  }
                  updateMessage(assistantId, {
                    content: cleanDisplay(fullContent),
                    isStreaming: false,
                    sqlQuery: currentSqlQuery,
                    statusUpdates,
                    ...(hasError && { error: 'query_failed' }),
                  })
                  if (data.session_id) {
                    setSessionId(data.session_id)
                    if (activeConvId) saveSessionId(activeConvId, data.session_id)
                    onConversationUpdated?.(activeConvId!, data.session_id)
                  }
                  break
              }
            } catch {
              // skip invalid JSON
            }
          }
        }
      }

      if (buffer.startsWith('data: ')) {
        try {
          const data = JSON.parse(buffer.slice(6))
          if (data.type === 'done') {
            updateMessage(assistantId, { content: cleanDisplay(fullContent), isStreaming: false, sqlQuery: currentSqlQuery, statusUpdates })
          }
        } catch { /* ignore */ }
      }

      updateMessage(assistantId, { content: cleanDisplay(fullContent), isStreaming: false })
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        updateMessage(assistantId, {
          content: 'Request cancelled',
          isStreaming: false,
        })
      } else {
        const errorMessage = err instanceof Error ? err.message : 'An error occurred'
        setError(errorMessage)
        updateMessage(assistantId, {
          content: `I encountered an error: ${errorMessage}. Please try again.`,
          isStreaming: false,
          error: errorMessage,
        })
      }
    } finally {
      setIsLoading(false)
      isLoadingRef.current = false
      abortControllerRef.current = null
      // Persist after the stream finishes
      setTimeout(() => {
        persistMessages(messagesRef.current, conversationIdRef.current)
      }, 0)
    }
  }, [apiUrl, sessionId, addMessage, updateMessage, onNeedConversation, onConversationUpdated, persistMessages])

  const cancelRequest = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
  }, [])

  const clearMessages = useCallback(() => {
    setMessages([])
    messagesRef.current = []
    setSessionId(null)
    setError(null)
  }, [])

  const exportChat = useCallback(() => {
    if (messages.length === 0) return

    const exportData = {
      exportedAt: new Date().toISOString(),
      sessionId,
      messages: messages.map(msg => ({
        role: msg.role,
        content: msg.content,
        timestamp: msg.timestamp.toISOString(),
        ...(msg.sqlQuery && { sqlQuery: msg.sqlQuery }),
      })),
    }

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `census-chat-${new Date().toISOString().slice(0, 10)}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }, [messages, sessionId])

  return {
    messages,
    isLoading,
    sessionId,
    error,
    sendMessage,
    cancelRequest,
    clearMessages,
    exportChat,
  }
}
