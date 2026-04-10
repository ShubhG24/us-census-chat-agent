import { useState, useRef, useEffect } from 'react'

interface InputBarProps {
  onSend: (message: string) => void
  onCancel: () => void
  isLoading: boolean
  disabled?: boolean
  placeholder?: string
  theme: 'light' | 'dark'
}

export default function InputBar({ onSend, onCancel, isLoading, disabled, placeholder, theme }: InputBarProps) {
  const [input, setInput] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const isDark = theme === 'dark'

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`
    }
  }, [input])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (input.trim() && !isLoading && !disabled) {
      onSend(input.trim())
      setInput('')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="relative">
      <div className={`relative flex items-end gap-2 p-2 rounded-xl transition-all duration-200 ${
        isDark
          ? 'bg-neutral-800/80 border border-neutral-700 focus-within:border-indigo-500/50 focus-within:shadow-[0_0_0_3px_rgba(99,102,241,0.1)]'
          : 'bg-white border border-gray-200 focus-within:border-indigo-300 focus-within:shadow-[0_0_0_3px_rgba(99,102,241,0.08)] shadow-sm'
      }`}>
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={isLoading || disabled}
            aria-label="Ask a question about US Census data"
            rows={1}
            className={`w-full px-3 py-2.5 bg-transparent resize-none focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed text-[15px] leading-relaxed ${
              isDark
                ? 'text-white placeholder-neutral-500'
                : 'text-gray-800 placeholder-gray-400'
            }`}
            style={{ maxHeight: '120px' }}
          />
        </div>

        <div className="flex items-center gap-2 pb-1.5 pr-1">
          {isLoading ? (
            <button
              type="button"
              onClick={onCancel}
              aria-label="Cancel request"
              title="Cancel request"
              className={`flex items-center justify-center w-9 h-9 rounded-full transition-colors duration-150 ${
                isDark
                  ? 'bg-red-950/50 hover:bg-red-900/50 text-red-400'
                  : 'bg-red-50 hover:bg-red-100 text-red-500'
              }`}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim() || disabled}
              aria-label="Send message"
              title="Send (Enter)"
              className="flex items-center justify-center w-9 h-9 rounded-full bg-indigo-600 text-white hover:bg-indigo-500 active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-150"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 10.5L12 3m0 0l7.5 7.5M12 3v18" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {isLoading && (
        <div className={`absolute -bottom-0.5 left-0 right-0 h-0.5 rounded-full overflow-hidden ${
          isDark ? 'bg-neutral-800' : 'bg-gray-100'
        }`}>
          <div
            className="h-full bg-indigo-500"
            style={{ width: '40%', animation: 'shimmer 1.5s ease-in-out infinite' }}
          />
        </div>
      )}
    </form>
  )
}
