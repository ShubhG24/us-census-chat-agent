import type { Message } from '../hooks/useChat'

export interface ConversationMeta {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  sessionId: string | null
  preview?: string
}

interface SerializedMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  sqlQuery?: string
  error?: string
  statusUpdates?: string[]
}

const CONVERSATIONS_KEY = 'census-conversations'
const MESSAGES_PREFIX = 'census-msgs-'
const SESSION_PREFIX = 'census-sid-'
const MAX_CONVERSATIONS = 50

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

function write(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Storage full or unavailable
  }
}

function remove(key: string): void {
  try {
    localStorage.removeItem(key)
  } catch {
    // Unavailable
  }
}

export function loadConversations(): ConversationMeta[] {
  const list = read<ConversationMeta[]>(CONVERSATIONS_KEY, [])
  return list.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
}

export function saveConversations(list: ConversationMeta[]): void {
  const pruned = list
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
    .slice(0, MAX_CONVERSATIONS)

  const removed = list.slice(MAX_CONVERSATIONS)
  for (const c of removed) {
    remove(`${MESSAGES_PREFIX}${c.id}`)
  }

  write(CONVERSATIONS_KEY, pruned)
}

export function loadMessages(conversationId: string): Message[] {
  const raw = read<SerializedMessage[]>(`${MESSAGES_PREFIX}${conversationId}`, [])
  return raw.map(m => ({
    ...m,
    timestamp: new Date(m.timestamp),
  }))
}

export function saveMessages(conversationId: string, messages: Message[]): void {
  const serialized: SerializedMessage[] = messages
    .filter(m => !m.isStreaming)
    .map(m => ({
      id: m.id,
      role: m.role,
      content: m.content,
      timestamp: m.timestamp.toISOString(),
      ...(m.sqlQuery && { sqlQuery: m.sqlQuery }),
      ...(m.error && { error: m.error }),
      ...(m.statusUpdates?.length && { statusUpdates: m.statusUpdates }),
    }))
  write(`${MESSAGES_PREFIX}${conversationId}`, serialized)

  const firstAssistant = serialized.find(m => m.role === 'assistant' && m.content)
  if (firstAssistant) {
    const list = read<ConversationMeta[]>(CONVERSATIONS_KEY, [])
    const conv = list.find(c => c.id === conversationId)
    if (conv) {
      conv.preview = firstAssistant.content.slice(0, 80).replace(/\n/g, ' ')
      write(CONVERSATIONS_KEY, list)
    }
  }
}

export function deleteMessages(conversationId: string): void {
  remove(`${MESSAGES_PREFIX}${conversationId}`)
  remove(`${SESSION_PREFIX}${conversationId}`)
}

export function loadSessionId(conversationId: string): string | null {
  return read<string | null>(`${SESSION_PREFIX}${conversationId}`, null)
}

export function saveSessionId(conversationId: string, sessionId: string): void {
  write(`${SESSION_PREFIX}${conversationId}`, sessionId)
}

export function cleanEmptyConversations(list: ConversationMeta[]): ConversationMeta[] {
  return list.filter(c => {
    const msgs = read<SerializedMessage[]>(`${MESSAGES_PREFIX}${c.id}`, [])
    if (msgs.length === 0) {
      remove(`${MESSAGES_PREFIX}${c.id}`)
      return false
    }
    return true
  })
}
