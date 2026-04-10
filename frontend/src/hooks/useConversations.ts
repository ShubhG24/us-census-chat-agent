import { useState, useCallback, useRef } from 'react'
import {
  ConversationMeta,
  loadConversations,
  saveConversations,
  deleteMessages,
} from '../lib/storage'

export function useConversations() {
  const [conversations, setConversations] = useState<ConversationMeta[]>(() => {
    return loadConversations()
  })

  const [activeId, setActiveId] = useState<string | null>(() => {
    const loaded = loadConversations()
    return loaded.length > 0 ? loaded[0].id : null
  })

  const activeIdRef = useRef(activeId)
  activeIdRef.current = activeId

  const update = useCallback((fn: (prev: ConversationMeta[]) => ConversationMeta[]) => {
    setConversations(prev => {
      const next = fn(prev)
      saveConversations(next)
      return next
    })
  }, [])

  const createConversation = useCallback((title = 'New Chat'): string => {
    const id = crypto.randomUUID()
    const now = new Date().toISOString()
    const meta: ConversationMeta = {
      id,
      title,
      createdAt: now,
      updatedAt: now,
      sessionId: null,
    }
    update(prev => [meta, ...prev])
    setActiveId(id)
    return id
  }, [update])

  const switchConversation = useCallback((id: string) => {
    setActiveId(id)
  }, [])

  const deleteConversation = useCallback((id: string) => {
    deleteMessages(id)
    update(prev => prev.filter(c => c.id !== id))
    if (activeIdRef.current === id) {
      setConversations(curr => {
        setActiveId(curr.length > 0 ? curr[0].id : null)
        return curr
      })
    }
  }, [update])

  const updateTitle = useCallback((id: string, title: string) => {
    update(prev => prev.map(c =>
      c.id === id ? { ...c, title } : c
    ))
  }, [update])

  const touchConversation = useCallback((id: string, sessionId?: string) => {
    const now = new Date().toISOString()
    update(prev => prev.map(c =>
      c.id === id
        ? { ...c, updatedAt: now, ...(sessionId !== undefined && { sessionId }) }
        : c
    ))
  }, [update])

  const startNewChat = useCallback(() => {
    setActiveId(null)
  }, [])

  return {
    conversations,
    activeId,
    createConversation,
    switchConversation,
    deleteConversation,
    updateTitle,
    touchConversation,
    startNewChat,
  }
}
