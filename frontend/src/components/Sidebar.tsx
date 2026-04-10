import { memo, useEffect, useRef } from 'react'
import type { ConversationMeta } from '../lib/storage'

interface SidebarProps {
  conversations: ConversationMeta[]
  activeId: string | null
  onNew: () => void
  onSwitch: (id: string) => void
  onDelete: (id: string) => void
  theme: 'light' | 'dark'
  isOpen: boolean
  onClose: () => void
  collapsed?: boolean
  onToggleCollapse?: () => void
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 7) return `${days}d ago`
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function MobileDrawer({ onClose, children }: { onClose: () => void; children: React.ReactNode }) {
  const drawerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()

      if (e.key === 'Tab' && drawerRef.current) {
        const focusable = drawerRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
        if (focusable.length === 0) return
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    const firstBtn = drawerRef.current?.querySelector<HTMLElement>('button')
    firstBtn?.focus()

    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true" aria-label="Conversation sidebar">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} aria-hidden="true" />
      <div ref={drawerRef} className="relative z-10 h-full sidebar-enter">
        {children}
      </div>
    </div>
  )
}

export default memo(function Sidebar({
  conversations,
  activeId,
  onNew,
  onSwitch,
  onDelete,
  theme,
  isOpen,
  onClose,
  collapsed = false,
  onToggleCollapse,
}: SidebarProps) {
  const isDark = theme === 'dark'

  const sidebarContent = (
    <div className={`flex flex-col h-full w-[260px] border-r ${
      isDark
        ? 'bg-neutral-900/95 border-neutral-800'
        : 'bg-gray-50/90 border-gray-200'
    }`}>
      {/* Collapse toggle */}
      {onToggleCollapse && (
        <div className={`hidden md:flex justify-end px-3 pt-2`}>
          <button
            onClick={onToggleCollapse}
            className={`p-1.5 rounded-md transition-colors duration-150 ${
              isDark
                ? 'hover:bg-neutral-800 text-neutral-500 hover:text-neutral-300'
                : 'hover:bg-gray-200 text-gray-400 hover:text-gray-600'
            }`}
            aria-label="Collapse sidebar"
            title="Collapse sidebar"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 5v14" />
            </svg>
          </button>
        </div>
      )}

      {/* New chat */}
      <div className="px-3 pt-1.5 pb-2">
        <button
          onClick={() => { onNew(); onClose(); }}
          className={`w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors duration-150 ${
            isDark
              ? 'bg-neutral-800 hover:bg-neutral-700 text-neutral-200 border border-neutral-700'
              : 'bg-white hover:bg-gray-50 text-gray-700 border border-gray-300 shadow-sm'
          }`}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Chat
        </button>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto px-2 pb-3">
        {conversations.length === 0 ? (
          <p className={`text-xs text-center mt-8 ${isDark ? 'text-neutral-500' : 'text-gray-400'}`}>
            No conversations yet
          </p>
        ) : (
          <div className="space-y-0.5">
            {conversations.map(conv => {
              const isActive = conv.id === activeId
              return (
                <div
                  key={conv.id}
                  className="group relative"
                >
                  <button
                    onClick={() => { onSwitch(conv.id); onClose(); }}
                    className={`w-full text-left px-3 py-2.5 rounded-lg transition-colors duration-100 flex flex-col gap-0.5 pr-9 ${
                      isActive
                        ? isDark
                          ? 'bg-indigo-500/15 text-white'
                          : 'bg-indigo-50 text-indigo-900'
                        : isDark
                          ? 'text-neutral-300 hover:bg-neutral-800/60'
                          : 'text-gray-700 hover:bg-gray-100'
                    }`}
                  >
                    <span className={`text-sm truncate block leading-tight ${isActive ? 'font-semibold' : ''}`}>
                      {conv.title}
                    </span>
                    {conv.preview && (
                      <span className={`text-[11px] truncate block leading-snug ${
                        isActive
                          ? isDark ? 'text-indigo-300/50' : 'text-indigo-600/50'
                          : isDark ? 'text-neutral-500' : 'text-gray-400'
                      }`}>
                        {conv.preview}
                      </span>
                    )}
                    <span className={`text-[10px] ${
                      isActive
                        ? isDark ? 'text-indigo-400/60' : 'text-indigo-500/60'
                        : isDark ? 'text-neutral-500' : 'text-gray-400'
                    }`}>
                      {relativeTime(conv.updatedAt)}
                    </span>
                  </button>

                  {/* Delete button */}
                  <button
                    onClick={(e) => { e.stopPropagation(); onDelete(conv.id); }}
                    className={`absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus:opacity-100 transition-opacity duration-100 ${
                      isDark
                        ? 'hover:bg-neutral-700 text-neutral-500 hover:text-red-400'
                        : 'hover:bg-gray-200 text-gray-400 hover:text-red-500'
                    }`}
                    title="Delete conversation"
                    aria-label="Delete conversation"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )

  return (
    <>
      {/* Desktop: collapsible inline sidebar */}
      <div className="hidden md:flex flex-shrink-0 relative">
        <div
          className={`overflow-hidden transition-all duration-300 ease-in-out ${
            collapsed ? 'w-0' : 'w-[260px]'
          }`}
        >
          {sidebarContent}
        </div>

        {/* Expand button when collapsed */}
        {collapsed && onToggleCollapse && (
          <button
            onClick={onToggleCollapse}
            className={`absolute top-3 left-2 z-10 p-2 rounded-lg transition-colors duration-150 ${
              isDark
                ? 'hover:bg-neutral-800 text-neutral-400 hover:text-neutral-200'
                : 'hover:bg-gray-200 text-gray-400 hover:text-gray-700'
            }`}
            aria-label="Expand sidebar"
            title="Expand sidebar"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 5v14" />
            </svg>
          </button>
        )}
      </div>

      {/* Mobile: overlay drawer */}
      {isOpen && (
        <MobileDrawer onClose={onClose}>
          {sidebarContent}
        </MobileDrawer>
      )}
    </>
  )
})
