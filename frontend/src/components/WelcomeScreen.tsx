import { memo } from 'react'

interface WelcomeScreenProps {
  theme: 'light' | 'dark'
  onExampleClick: (question: string) => void
  disabled?: boolean
}

const EXAMPLES = [
  {
    category: 'Population',
    label: 'Population of California',
    question: 'What is the population of California?',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
  {
    category: 'Income',
    label: 'Highest median household income',
    question: 'Which state has the highest median household income?',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    category: 'Housing',
    label: 'Renter vs owner-occupied in LA County',
    question: 'How many households are renter-occupied vs owner-occupied in Los Angeles County?',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1" />
      </svg>
    ),
  },
  {
    category: 'Demographics',
    label: 'Racial breakdown of Texas',
    question: 'What is the racial breakdown of Texas?',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    category: 'Education',
    label: 'College degree rates by state',
    question: 'Which states have the highest percentage of residents with a bachelor\'s degree or higher?',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 14l9-5-9-5-9 5 9 5zm0 0l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z" />
      </svg>
    ),
  },
  {
    category: 'Poverty',
    label: 'Top 10 states by poverty rate',
    question: 'What are the top 10 states by poverty rate?',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
  },
]

export default memo(function WelcomeScreen({ theme, onExampleClick, disabled }: WelcomeScreenProps) {
  const isDark = theme === 'dark'

  return (
    <div className="flex flex-col items-center justify-center h-full px-4 select-none">
      <div className="mb-8 text-center">
        <div className={`inline-flex items-center justify-center w-12 h-12 rounded-2xl mb-4 ${
          isDark ? 'bg-indigo-500/10' : 'bg-indigo-50'
        }`}>
          <svg className={`w-6 h-6 ${isDark ? 'text-indigo-400' : 'text-indigo-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h2 className={`text-xl font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
          What can I help you explore?
        </h2>
        <p className={`text-sm ${isDark ? 'text-neutral-500' : 'text-gray-500'}`}>
          2020 &amp; 2019 ACS data · Population, income, housing, education &amp; more
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full max-w-xl">
        {EXAMPLES.map((ex) => (
          <button
            key={ex.question}
            onClick={() => onExampleClick(ex.question)}
            disabled={disabled}
            className={`group flex flex-col gap-1.5 px-4 py-3 rounded-xl text-left transition-all duration-150 border disabled:opacity-50 disabled:cursor-not-allowed ${
              isDark
                ? 'border-neutral-800 hover:border-neutral-700 hover:bg-neutral-800/60 active:bg-neutral-800'
                : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50 active:bg-gray-100 shadow-sm'
            }`}
          >
            <span className={`inline-flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider ${
              isDark ? 'text-neutral-500 group-hover:text-indigo-400' : 'text-gray-400 group-hover:text-indigo-600'
            }`}>
              <span className={`transition-colors duration-150 ${
                isDark ? 'text-neutral-600 group-hover:text-indigo-400' : 'text-gray-400 group-hover:text-indigo-500'
              }`}>
                {ex.icon}
              </span>
              {ex.category}
            </span>
            <span className={`text-[13px] leading-snug ${
              isDark ? 'text-neutral-300 group-hover:text-neutral-100' : 'text-gray-600 group-hover:text-gray-900'
            }`}>
              {ex.label}
            </span>
          </button>
        ))}
      </div>
    </div>
  )
})
