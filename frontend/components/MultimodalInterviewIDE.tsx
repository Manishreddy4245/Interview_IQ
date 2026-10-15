'use client'

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import dynamic from 'next/dynamic'
import {
  Play,
  CheckCircle2,
  XCircle,
  Code2,
  Database,
  Terminal,
  Copy,
  RotateCcw,
  Sparkles,
  Clock,
  HardDrive,
  Check,
  Loader2,
  Table,
  FileCode,
  AlertCircle,
  BookOpen,
  ListFilter,
  CheckSquare,
  Maximize2,
  Columns,
  GripVertical,
  ChevronLeft,
  ChevronRight,
  Award,
} from 'lucide-react'
import {
  QuestionItem,
  TestCase,
  TestCaseResult,
  CodeExecutionResponse,
  CodeSubmissionResult,
  SQLExecutionResponse,
  SQLSubmissionResult,
  SupportedLanguage,
  SQLFixtureMetadata,
  getSupportedLanguages,
  executeCode,
  submitCodeSolution,
  getSqlSchema,
  executeSql,
  submitSqlSolution,
  submitQuestionAnswer,
  saveQuestionDraft,
  getSessionDrafts,
} from '@/lib/api'
import {
  normalizeProblemData,
  NormalizedProblem,
  ProblemExample,
} from '@/lib/problem_catalog'

// Dynamically import Monaco Editor to avoid SSR window issues
const Editor = dynamic(() => import('@monaco-editor/react'), {
  ssr: false,
  loading: () => (
    <div className="monaco-loading-placeholder">
      <Loader2 className="animate-spin" size={24} />
      <span>Loading VS Code Monaco Editor...</span>
    </div>
  ),
})

interface MultimodalInterviewIDEProps {
  question: QuestionItem
  sessionId: string
  modeOverride?: 'coding' | 'sql'
  initialDrafts?: Record<string, Record<string, { code: string; version: number; updated_at: string }>>
  onDraftSaved?: (
    questionId: string,
    language: string,
    draft: { code: string; version: number; updated_at: string },
  ) => void
  onAnswerSaved?: (answerData: {
    answer_text?: string
    code?: string
    language?: string
    sql_query?: string
    execution_result?: any
  }) => void
  onEvaluationTriggered?: () => void
  onSubmitSolution?: (solutionData: {
    code?: string
    language?: string
    sql_query?: string
    answer_text?: string
    execution_result?: any
  }) => Promise<void> | void
  isSubmitting?: boolean
  isEvaluating?: boolean
  // Navigation props
  onNavigateNext?: () => void
  onNavigatePrevious?: () => void
  hasNextQuestion?: boolean
  hasPreviousQuestion?: boolean
  isLastQuestion?: boolean
  isNavigating?: boolean
  onFinishInterview?: () => void
}

// Known genuine language display names mapping fallback
export const KNOWN_LANGUAGE_NAMES: Record<string, string> = {
  python: 'Python 3',
  javascript: 'JavaScript (Node.js)',
  typescript: 'TypeScript',
  cpp: 'C++',
  java: 'Java',
  c: 'C',
  csharp: 'C#',
  go: 'Go',
  rust: 'Rust',
  kotlin: 'Kotlin',
  php: 'PHP',
  ruby: 'Ruby',
  swift: 'Swift',
  scala: 'Scala',
  sql: 'SQL',
}

// Fallback runtime options genuinely verified against Piston execution engine & SQLite sandbox
export const GENUINE_SUPPORTED_RUNTIMES: SupportedLanguage[] = [
  { id: 'python', key: 'python', name: 'Python 3', label: 'Python 3', version: '3.10.0', monaco_language: 'python' },
  { id: 'javascript', key: 'javascript', name: 'JavaScript (Node.js)', label: 'JavaScript (Node.js)', version: '18.15.0', monaco_language: 'javascript' },
  { id: 'typescript', key: 'typescript', name: 'TypeScript', label: 'TypeScript', version: '5.0.3', monaco_language: 'typescript' },
  { id: 'cpp', key: 'cpp', name: 'C++', label: 'C++', version: '10.2.0', monaco_language: 'cpp' },
  { id: 'java', key: 'java', name: 'Java', label: 'Java', version: '15.0.2', monaco_language: 'java' },
  { id: 'c', key: 'c', name: 'C', label: 'C', version: '10.2.0', monaco_language: 'c' },
  { id: 'csharp', key: 'csharp', name: 'C#', label: 'C#', version: '6.12.0', monaco_language: 'csharp' },
  { id: 'go', key: 'go', name: 'Go', label: 'Go', version: '1.16.2', monaco_language: 'go' },
  { id: 'rust', key: 'rust', name: 'Rust', label: 'Rust', version: '1.68.2', monaco_language: 'rust' },
  { id: 'kotlin', key: 'kotlin', name: 'Kotlin', label: 'Kotlin', version: '1.8.20', monaco_language: 'kotlin' },
  { id: 'php', key: 'php', name: 'PHP', label: 'PHP', version: '8.2.3', monaco_language: 'php' },
  { id: 'ruby', key: 'ruby', name: 'Ruby', label: 'Ruby', version: '3.0.1', monaco_language: 'ruby' },
  { id: 'swift', key: 'swift', name: 'Swift', label: 'Swift', version: '5.3.3', monaco_language: 'swift' },
  { id: 'scala', key: 'scala', name: 'Scala', label: 'Scala', version: '3.2.2', monaco_language: 'scala' },
  { id: 'sql', key: 'sql', name: 'SQL', label: 'SQL', version: '3.53.2', monaco_language: 'sql', is_sql: true },
]

export interface FormattedLanguageOption {
  id: string
  name: string
  version: string
  displayLabel: string
  isSql?: boolean
}

/**
 * Format language option to guarantee readable name and version label:
 * e.g. "Python 3 — (3.10.0)", "JavaScript (Node.js) — (18.15.0)"
 */
export function formatLanguageDisplayOption(lang: SupportedLanguage): FormattedLanguageOption {
  const rawId = (lang.id || lang.key || '').trim().toLowerCase()
  const id = rawId || 'python'

  let name = (lang.name || lang.label || '').trim()
  if (!name) {
    name = KNOWN_LANGUAGE_NAMES[id] || (id ? id.charAt(0).toUpperCase() + id.slice(1) : 'Unknown Language')
    console.warn(`[InterviewIQ Language Selector] Missing readable name for runtime '${id}', fell back to '${name}'.`)
  }

  const version = (lang.version || '').trim()
  const displayLabel = version ? `${name} — (${version})` : name

  return {
    id,
    name,
    version,
    displayLabel,
    isSql: Boolean(lang.is_sql || id === 'sql'),
  }
}

export function MultimodalInterviewIDE({
  question,
  sessionId,
  modeOverride,
  initialDrafts,
  onDraftSaved,
  onAnswerSaved,
  onEvaluationTriggered,
  onSubmitSolution,
  isSubmitting,
  isEvaluating,
  onNavigateNext,
  onNavigatePrevious,
  hasNextQuestion,
  hasPreviousQuestion,
  isLastQuestion,
  isNavigating,
  onFinishInterview,
}: MultimodalInterviewIDEProps) {
  // Determine initial workspace mode based on modeOverride or question
  const initialMode =
    modeOverride
      ? modeOverride
      : question.question_type === 'sql'
      ? 'sql'
      : 'coding'

  const [workspaceMode, setWorkspaceMode] = useState<'coding' | 'sql'>(initialMode)
  const [languages, setLanguages] = useState<SupportedLanguage[]>([])
  const [selectedLanguage, setSelectedLanguage] = useState<string>(initialMode === 'sql' ? 'sql' : 'python')

  // Autosave tracking state
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [lastSavedTime, setLastSavedTime] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Tracking refs for out-of-order write protection and fast flushing
  const draftVersionsRef = useRef<Record<string, Record<string, number>>>({})
  const backendDraftsRef = useRef<Record<string, Record<string, { code: string; version: number; updated_at: string }>>>(
    initialDrafts || {},
  )
  const pendingSaveTimerRef = useRef<NodeJS.Timeout | null>(null)
  const activeQIdRef = useRef<string>(question.id)
  const activeLangRef = useRef<string>(initialMode === 'sql' ? 'sql' : 'python')
  const activeCodeRef = useRef<string>('')
  const activeSqlRef = useRef<string>('')

  // LeetCode-style Split-Pane state (40% problem description, 60% code editor)
  const [splitRatio, setSplitRatio] = useState<number>(40)
  const [isDragging, setIsDragging] = useState<boolean>(false)
  const splitContainerRef = useRef<HTMLDivElement>(null)
  const [copiedSnippetId, setCopiedSnippetId] = useState<string | null>(null)

  // Problem definition normalized for the active question
  const problem: NormalizedProblem = useMemo(() => {
    return normalizeProblemData(question, selectedLanguage)
  }, [question, selectedLanguage])

  // Separate candidate-visible sample test cases from hidden benchmark cases
  const visibleTestCases = useMemo(() => {
    const visible = problem.test_cases.filter((tc) => !tc.is_hidden)
    return visible.length > 0 ? visible : problem.test_cases
  }, [problem.test_cases])

  // Left pane active tab: 'description' | 'examples' | 'constraints' | 'testcases' | 'schema'
  const [leftTab, setLeftTab] = useState<'description' | 'examples' | 'constraints' | 'testcases' | 'schema'>('description')

  // Code memory per question and per language
  const [codeStore, setCodeStore] = useState<Record<string, Record<string, string>>>({})
  const [sqlStore, setSqlStore] = useState<Record<string, string>>({})

  // Current active code & sql
  const [code, setCode] = useState<string>('')
  const [sqlQuery, setSqlQuery] = useState<string>('')
  const [customStdin, setCustomStdin] = useState<string>('')
  const [customCaseInputs, setCustomCaseInputs] = useState<Record<number, string>>({})
  const [lastExecutedCaseIdx, setLastExecutedCaseIdx] = useState<number | null>(null)

  // Bottom pane execution states
  const [activeTab, setActiveTab] = useState<'output' | 'tests' | 'stdin' | 'schema'>('output')
  const [selectedTestCaseIdx, setSelectedTestCaseIdx] = useState<number>(0)
  const [isRunning, setIsRunning] = useState<boolean>(false)
  const [isEvaluatingTests, setIsEvaluatingTests] = useState<boolean>(false)
  const [executionResponse, setExecutionResponse] = useState<CodeExecutionResponse | null>(null)
  const [submissionResult, setSubmissionResult] = useState<CodeSubmissionResult | null>(null)

  // SQL execution states
  const [isSqlRunning, setIsSqlRunning] = useState<boolean>(false)
  const [isSqlEvaluating, setIsSqlEvaluating] = useState<boolean>(false)
  const [sqlResponse, setSqlResponse] = useState<SQLExecutionResponse | null>(null)
  const [sqlSubmission, setSqlSubmission] = useState<SQLSubmissionResult | null>(null)
  const [sqlFixture, setSqlFixture] = useState<SQLFixtureMetadata | null>(null)

  // UI preferences
  const [editorTheme, setEditorTheme] = useState<'vs-dark' | 'light'>('vs-dark')
  const [copySuccess, setCopySuccess] = useState<boolean>(false)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)

  const editorRef = useRef<any>(null)

  // Resolve saved draft code by priority: in-memory store -> backend draft -> localStorage recovery
  const resolveDraftCode = useCallback(
    (qId: string, lang: string): string | null => {
      // 1. In-memory codeStore
      if (codeStore[qId]?.[lang]) {
        return codeStore[qId][lang]
      }
      // 2. Authenticated backend drafts
      const backendDraft = backendDraftsRef.current[qId]?.[lang]
      if (backendDraft && typeof backendDraft.code === 'string') {
        return backendDraft.code
      }
      // 3. Local browser storage recovery layer
      if (typeof window !== 'undefined' && window.localStorage) {
        try {
          const item = window.localStorage.getItem(`interviewiq_draft_${sessionId}_${qId}_${lang}`)
          if (item) {
            const parsed = JSON.parse(item)
            if (parsed && typeof parsed.code === 'string') {
              return parsed.code
            }
          }
        } catch {}
      }
      return null
    },
    [codeStore, sessionId],
  )

  const resolveDraftSql = useCallback(
    (qId: string): string | null => {
      if (sqlStore[qId]) {
        return sqlStore[qId]
      }
      const backendDraft = backendDraftsRef.current[qId]?.['sql']
      if (backendDraft && typeof backendDraft.code === 'string') {
        return backendDraft.code
      }
      if (typeof window !== 'undefined' && window.localStorage) {
        try {
          const item = window.localStorage.getItem(`interviewiq_draft_${sessionId}_${qId}_sql`)
          if (item) {
            const parsed = JSON.parse(item)
            if (parsed && typeof parsed.code === 'string') {
              return parsed.code
            }
          }
        } catch {}
      }
      return null
    },
    [sqlStore, sessionId],
  )

  // Perform backend persistence with version tracking and local fallback
  const performSave = useCallback(
    async (qId: string, lang: string, codeToSave: string) => {
      if (!sessionId || !qId || !lang) return
      setSaveStatus('saving')
      setSaveError(null)

      const nextVersion = (draftVersionsRef.current[qId]?.[lang] || 0) + 1
      draftVersionsRef.current[qId] = {
        ...(draftVersionsRef.current[qId] || {}),
        [lang]: nextVersion,
      }

      // Temporary local recovery layer
      if (typeof window !== 'undefined' && window.localStorage) {
        try {
          window.localStorage.setItem(
            `interviewiq_draft_${sessionId}_${qId}_${lang}`,
            JSON.stringify({
              code: codeToSave,
              version: nextVersion,
              updated_at: new Date().toISOString(),
            }),
          )
        } catch {}
      }

      try {
        const res = await saveQuestionDraft(sessionId, qId, {
          language: lang,
          code: codeToSave,
          version: nextVersion,
          updated_at: new Date().toISOString(),
        })

        if (!backendDraftsRef.current[qId]) {
          backendDraftsRef.current[qId] = {}
        }
        backendDraftsRef.current[qId][lang] = {
          code: codeToSave,
          version: res.version,
          updated_at: res.updated_at,
        }

        setSaveStatus('saved')
        setLastSavedTime(
          new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        )
        if (onDraftSaved) {
          onDraftSaved(qId, lang, {
            code: codeToSave,
            version: res.version,
            updated_at: res.updated_at,
          })
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Save failed'
        console.error(`[Autosave] Error saving draft for ${qId}/${lang}:`, err)
        setSaveStatus('error')
        setSaveError(msg)
      }
    },
    [sessionId, onDraftSaved],
  )

  const flushAutosave = useCallback(async () => {
    if (pendingSaveTimerRef.current) {
      clearTimeout(pendingSaveTimerRef.current)
      pendingSaveTimerRef.current = null
    }
    const currentC = workspaceMode === 'sql' ? activeSqlRef.current : activeCodeRef.current
    if (activeQIdRef.current && activeLangRef.current && currentC) {
      try {
        await performSave(activeQIdRef.current, activeLangRef.current, currentC)
      } catch (err) {
        console.warn('[InterviewIQ IDE] Autosave flush failed before navigation:', err)
      }
    }
  }, [workspaceMode, performSave])

  const handleNavNext = async () => {
    if (isNavigating) return
    await flushAutosave()
    if (onNavigateNext) {
      onNavigateNext()
    }
  }

  const handleNavPrevious = async () => {
    if (isNavigating) return
    await flushAutosave()
    if (onNavigatePrevious) {
      onNavigatePrevious()
    }
  }

  const handleFinish = async () => {
    if (isNavigating) return
    await flushAutosave()
    if (onFinishInterview) {
      onFinishInterview()
    }
  }

  const scheduleAutosave = useCallback(
    (qId: string, lang: string, newCode: string) => {
      if (pendingSaveTimerRef.current) {
        clearTimeout(pendingSaveTimerRef.current)
      }
      setSaveStatus('saving')
      pendingSaveTimerRef.current = setTimeout(() => {
        performSave(qId, lang, newCode)
      }, 750)
    },
    [performSave],
  )

  // Load supported languages
  useEffect(() => {
    let mounted = true
    getSupportedLanguages()
      .then((data) => {
        if (mounted && data.languages && data.languages.length > 0) {
          setLanguages(data.languages)
        }
      })
      .catch((err) => {
        console.error('Failed to load supported languages:', err)
      })
    return () => {
      mounted = false
    }
  }, [])

  // Hydrate session drafts on mount if available
  useEffect(() => {
    if (!sessionId) return
    let active = true

    if (initialDrafts && Object.keys(initialDrafts).length > 0) {
      backendDraftsRef.current = {
        ...backendDraftsRef.current,
        ...initialDrafts,
      }
    }

    getSessionDrafts(sessionId)
      .then((res) => {
        if (!active || !res || !res.drafts) return
        backendDraftsRef.current = {
          ...backendDraftsRef.current,
          ...res.drafts,
        }
        const currLang = activeLangRef.current
        const currQId = activeQIdRef.current
        const existingDraft = res.drafts[currQId]?.[currLang]?.code
        if (existingDraft) {
          if (currLang === 'sql') {
            setSqlQuery(existingDraft)
            activeSqlRef.current = existingDraft
          } else {
            setCode(existingDraft)
            activeCodeRef.current = existingDraft
          }
        }
      })
      .catch((err) => {
        console.warn('[InterviewIQ IDE] Could not fetch session drafts on mount:', err)
      })

    return () => {
      active = false
    }
  }, [sessionId, initialDrafts])

  // Flush pending save on unmount
  useEffect(() => {
    return () => {
      if (pendingSaveTimerRef.current) {
        clearTimeout(pendingSaveTimerRef.current)
        pendingSaveTimerRef.current = null
        const currentC = activeLangRef.current === 'sql' ? activeSqlRef.current : activeCodeRef.current
        if (activeQIdRef.current && activeLangRef.current && currentC) {
          performSave(activeQIdRef.current, activeLangRef.current, currentC)
        }
      }
    }
  }, [performSave])

  // Auto-switch mode and load question templates/fixtures when question or modeOverride changes
  useEffect(() => {
    // Flush pending save for previous question before switching
    if (pendingSaveTimerRef.current) {
      clearTimeout(pendingSaveTimerRef.current)
      pendingSaveTimerRef.current = null
      const currentC = activeLangRef.current === 'sql' ? activeSqlRef.current : activeCodeRef.current
      if (activeQIdRef.current && activeLangRef.current && currentC) {
        performSave(activeQIdRef.current, activeLangRef.current, currentC)
      }
    }

    activeQIdRef.current = question.id

    const isProblemSql = modeOverride
      ? modeOverride === 'sql'
      : (problem.is_sql || question.question_type === 'sql')

    if (isProblemSql) {
      setWorkspaceMode('sql')
      setSelectedLanguage('sql')
      activeLangRef.current = 'sql'
      setLeftTab('description')
      setActiveTab('output')
      const fixtureKey = question.sql_fixture || problem.sql_fixture || 'employees_departments'
      getSqlSchema(fixtureKey)
        .then((meta) => setSqlFixture(meta))
        .catch(() => {})
      const savedSql =
        resolveDraftSql(question.id) ||
        (typeof question.code_template === 'string' ? question.code_template : null) ||
        problem.starter_templates.sql
      setSqlQuery(savedSql)
      activeSqlRef.current = savedSql
    } else {
      setWorkspaceMode('coding')
      const targetLang = selectedLanguage === 'sql' ? 'python' : selectedLanguage
      setSelectedLanguage(targetLang)
      activeLangRef.current = targetLang
      setLeftTab('description')
      const savedCode =
        resolveDraftCode(question.id, targetLang) ||
        (typeof question.code_template === 'string' ? question.code_template : null) ||
        problem.starter_templates[targetLang] ||
        problem.starter_templates.python ||
        `// Solution in ${targetLang}\n`
      setCode(savedCode)
      activeCodeRef.current = savedCode
    }

    // Set initial custom stdin to first sample test case input if available
    const initialSampleInput =
      (problem.test_cases && problem.test_cases.length > 0
        ? problem.test_cases[0].input
        : problem.examples && problem.examples.length > 0
        ? problem.examples[0].input
        : '') || ''
    setCustomStdin(initialSampleInput)

    // Reset temporary outputs and custom case overrides on question switch
    setCustomCaseInputs({})
    setLastExecutedCaseIdx(null)
    setExecutionResponse(null)
    setSubmissionResult(null)
    setSqlResponse(null)
    setSqlSubmission(null)
    setStatusMessage(null)
    setSelectedTestCaseIdx(0)
  }, [question.id, question.question_type])

  // Update code when selected language changes
  const handleLanguageChange = (langId: string) => {
    // Flush pending save for current language before switching
    if (pendingSaveTimerRef.current) {
      clearTimeout(pendingSaveTimerRef.current)
      pendingSaveTimerRef.current = null
      const currentC = workspaceMode === 'sql' ? activeSqlRef.current : activeCodeRef.current
      if (activeQIdRef.current && activeLangRef.current && currentC) {
        performSave(activeQIdRef.current, activeLangRef.current, currentC)
      }
    }

    if (langId === 'sql') {
      setWorkspaceMode('sql')
      setSelectedLanguage('sql')
      activeLangRef.current = 'sql'
      setActiveTab('output')
      if (!sqlFixture) {
        getSqlSchema(question.sql_fixture || 'employees_departments').then((m) =>
          setSqlFixture(m),
        )
      }
      const existingSql = resolveDraftSql(question.id) || problem.starter_templates.sql
      setSqlQuery(existingSql)
      activeSqlRef.current = existingSql
      return
    }

    if (workspaceMode === 'sql') {
      setWorkspaceMode('coding')
    }

    setSelectedLanguage(langId)
    activeLangRef.current = langId
    const existing = resolveDraftCode(question.id, langId)
    if (existing) {
      setCode(existing)
      activeCodeRef.current = existing
    } else {
      const template =
        problem.starter_templates[langId] ||
        languages.find((l) => (l.id || l.key) === langId)?.starter_template ||
        `// Solution for ${problem.title} in ${langId}\n`
      setCode(template)
      activeCodeRef.current = template
    }
  }

  // Handle Monaco code change
  const handleEditorChange = (value: string | undefined) => {
    const newCode = value || ''
    if (workspaceMode === 'coding') {
      setCode(newCode)
      activeCodeRef.current = newCode
      setCodeStore((prev) => ({
        ...prev,
        [question.id]: {
          ...(prev[question.id] || {}),
          [selectedLanguage]: newCode,
        },
      }))
      scheduleAutosave(question.id, selectedLanguage, newCode)
    } else {
      setSqlQuery(newCode)
      activeSqlRef.current = newCode
      setSqlStore((prev) => ({
        ...prev,
        [question.id]: newCode,
      }))
      scheduleAutosave(question.id, 'sql', newCode)
    }
  }

  // Draggable divider resizer logic
  const handlePointerDownDivider = (e: React.PointerEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  useEffect(() => {
    if (!isDragging) return

    const handlePointerMove = (e: PointerEvent) => {
      if (!splitContainerRef.current) return
      const rect = splitContainerRef.current.getBoundingClientRect()
      const clientX = e.clientX
      const newRatio = ((clientX - rect.left) / rect.width) * 100
      // Clamp split ratio between 26% and 74%
      if (newRatio >= 26 && newRatio <= 74) {
        setSplitRatio(Math.round(newRatio * 10) / 10)
      }
    }

    const handlePointerUp = () => {
      setIsDragging(false)
    }

    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('pointerup', handlePointerUp)
    return () => {
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerup', handlePointerUp)
    }
  }, [isDragging])

  // Setup Monaco editor completions & shortcuts on mount
  const handleEditorDidMount = (editor: any, monaco: any) => {
    editorRef.current = editor

    // Add keyboard shortcuts
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => {
      if (workspaceMode === 'coding') {
        handleRunCode()
      } else {
        handleRunSql()
      }
    })

    // Register SQL Autocomplete Suggestions if not already present
    monaco.languages.registerCompletionItemProvider('sql', {
      provideCompletionItems: () => {
        const suggestions = [
          'SELECT', 'FROM', 'WHERE', 'JOIN', 'INNER JOIN', 'LEFT JOIN', 'RIGHT JOIN',
          'GROUP BY', 'HAVING', 'ORDER BY', 'LIMIT', 'COUNT', 'AVG', 'SUM', 'MIN',
          'MAX', 'DISTINCT', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'OVER',
          'PARTITION BY', 'ROW_NUMBER', 'RANK', 'DENSE_RANK', 'COALESCE',
        ].map((kw) => ({
          label: kw,
          kind: monaco.languages.CompletionItemKind.Keyword,
          insertText: kw,
        }))
        return { suggestions }
      },
    })
  }

  // Run Code against Custom Stdin or Active Sample Case
  const handleRunCode = async (overrideStdin?: string | React.MouseEvent) => {
    if (isRunning) return
    setIsRunning(true)
    setStatusMessage(null)

    let stdinToUse = ''
    if (typeof overrideStdin === 'string') {
      stdinToUse = overrideStdin
    } else if (activeTab === 'stdin') {
      stdinToUse = customStdin
    } else if (visibleTestCases.length > 0 && visibleTestCases[selectedTestCaseIdx]) {
      stdinToUse = customCaseInputs[selectedTestCaseIdx] ?? (visibleTestCases[selectedTestCaseIdx].input || '')
      setLastExecutedCaseIdx(selectedTestCaseIdx)
    } else {
      stdinToUse = customStdin.trim() || problem.examples[0]?.input || ''
    }

    try {
      const res = await executeCode({
        language: selectedLanguage,
        code,
        stdin: stdinToUse,
        question_id: question.id,
        function_name: problem.function_name,
        session_id: sessionId,
      })
      setExecutionResponse(res)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Execution failed'
      setExecutionResponse({
        stdout: '',
        stderr: msg,
        output: msg,
        exit_code: 1,
        status: 'error',
        error: msg,
      })
    } finally {
      setIsRunning(false)
    }
  }

  // Submit Code Solution against Test Cases
  const handleSubmitCode = async () => {
    if (isEvaluatingTests) return
    setIsEvaluatingTests(true)
    setActiveTab('tests')
    setStatusMessage(null)

    // Flush pending save immediately
    if (pendingSaveTimerRef.current) {
      clearTimeout(pendingSaveTimerRef.current)
      pendingSaveTimerRef.current = null
    }
    performSave(question.id, selectedLanguage, code)

    try {
      const casesToRun = problem.test_cases.length > 0 ? problem.test_cases : undefined
      const res = await submitCodeSolution({
        question_id: question.id,
        language: selectedLanguage,
        code,
        session_id: sessionId,
        test_cases: casesToRun,
      })
      setSubmissionResult(res)

      // Persist answer in active session & database or adaptive pipeline
      const solutionPayload = {
        code,
        language: selectedLanguage,
        answer_mode: 'coding',
        answer_text: `[DSA Solution in ${selectedLanguage} - ${res.passed_tests}/${res.total_tests} Tests Passed]`,
        execution_result: res,
      }

      if (onSubmitSolution) {
        await onSubmitSolution(solutionPayload)
      } else {
        await submitQuestionAnswer(sessionId, {
          question_id: question.id,
          ...solutionPayload,
        })
      }

      setStatusMessage(
        res.all_passed
          ? 'Solution verified! All test cases passed successfully.'
          : `${res.passed_tests} of ${res.total_tests} test cases passed.`,
      )

      if (onAnswerSaved) {
        onAnswerSaved(solutionPayload)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Submission failed'
      setStatusMessage(`Submission error: ${msg}`)
    } finally {
      setIsEvaluatingTests(false)
    }
  }

  // Run SQL Query
  const handleRunSql = async () => {
    if (isSqlRunning) return
    setIsSqlRunning(true)
    setActiveTab('output')
    setStatusMessage(null)

    try {
      const res = await executeSql({
        query: sqlQuery,
        question_id: question.sql_fixture || problem.sql_fixture || question.id,
      })
      setSqlResponse(res)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'SQL query failed'
      setSqlResponse({
        columns: [],
        rows: [],
        row_count: 0,
        execution_time_ms: 0,
        status: 'error',
        error: msg,
      })
    } finally {
      setIsSqlRunning(false)
    }
  }

  // Submit SQL Solution
  const handleSubmitSql = async () => {
    if (isSqlEvaluating) return
    setIsSqlEvaluating(true)
    setActiveTab('tests')
    setStatusMessage(null)

    // Flush pending save immediately
    if (pendingSaveTimerRef.current) {
      clearTimeout(pendingSaveTimerRef.current)
      pendingSaveTimerRef.current = null
    }
    performSave(question.id, 'sql', sqlQuery)

    try {
      const res = await submitSqlSolution({
        question_id: question.id,
        query: sqlQuery,
        session_id: sessionId,
        expected_query: question.expected_sql_query || undefined,
        fixture_key: question.sql_fixture || problem.sql_fixture || undefined,
      })
      setSqlSubmission(res)

      // Persist answer in active session & database or adaptive pipeline
      const sqlPayload = {
        sql_query: sqlQuery,
        answer_mode: 'sql',
        answer_text: `[SQL Query Solution - ${res.is_correct ? 'Correct Result Set' : 'Result Set Mismatch'}]`,
        execution_result: res,
      }

      if (onSubmitSolution) {
        await onSubmitSolution(sqlPayload)
      } else {
        await submitQuestionAnswer(sessionId, {
          question_id: question.id,
          ...sqlPayload,
        })
      }

      setStatusMessage(
        res.is_correct
          ? 'SQL solution verified! Correct query result set returned.'
          : 'Query executed but result set did not match expected benchmark.',
      )

      if (onAnswerSaved) {
        onAnswerSaved(sqlPayload)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'SQL submission failed'
      setStatusMessage(`SQL Submission error: ${msg}`)
    } finally {
      setIsSqlEvaluating(false)
    }
  }

  // Copy code to clipboard
  const handleCopyCode = async () => {
    const textToCopy = workspaceMode === 'coding' ? code : sqlQuery
    await navigator.clipboard.writeText(textToCopy)
    setCopySuccess(true)
    setTimeout(() => setCopySuccess(false), 2000)
  }

  // Copy individual text snippet (Input, Output, Stderr, etc.)
  const handleCopySnippet = async (text: string, id: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedSnippetId(id)
      setTimeout(() => {
        setCopiedSnippetId((curr) => (curr === id ? null : curr))
      }, 2000)
    } catch (err) {
      console.error('Failed to copy snippet:', err)
    }
  }

  // Reset code to starter template
  const handleResetCode = () => {
    if (workspaceMode === 'coding') {
      const template =
        problem.starter_templates[selectedLanguage] ||
        problem.starter_templates.python ||
        `// Solution for ${problem.title}\n`
      setCode(template)
    } else {
      const sqlStarter =
        typeof question.code_template === 'string'
          ? question.code_template
          : problem.starter_templates.sql || '-- Write your SQL query below\n'
      setSqlQuery(sqlStarter)
    }
  }

  // Monaco Language mapping
  const currentMonacoLanguage =
    workspaceMode === 'sql' || selectedLanguage === 'sql'
      ? 'sql'
      : languages.find((l) => (l.id || l.key) === selectedLanguage)?.monaco_language ||
        (selectedLanguage === 'cpp' ? 'cpp' : selectedLanguage === 'csharp' ? 'csharp' : selectedLanguage)

  // Difficulty badge class helper
  const difficultyClass =
    problem.difficulty.toLowerCase() === 'easy'
      ? 'easy'
      : problem.difficulty.toLowerCase() === 'hard'
      ? 'hard'
      : 'medium'

  return (
    <div className="multimodal-ide-container leetcode-layout">
      {/* Top IDE Toolbar */}
      <div className="ide-toolbar">
        {/* Workspace Mode Tabs */}
        <div className="ide-mode-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={workspaceMode === 'coding'}
            className={`ide-mode-tab ${workspaceMode === 'coding' ? 'active' : ''}`}
            onClick={() => {
              setWorkspaceMode('coding')
              if (selectedLanguage === 'sql') {
                setSelectedLanguage('python')
                const saved = codeStore[question.id]?.['python'] || problem.starter_templates.python
                setCode(saved)
              }
              setActiveTab('output')
            }}
          >
            <Code2 size={14} />
            <span>DSA Coding IDE</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={workspaceMode === 'sql'}
            className={`ide-mode-tab ${workspaceMode === 'sql' ? 'active' : ''}`}
            onClick={() => {
              setWorkspaceMode('sql')
              setSelectedLanguage('sql')
              setActiveTab('output')
              if (!sqlFixture) {
                getSqlSchema(question.sql_fixture || problem.sql_fixture || 'employees_departments').then((m) =>
                  setSqlFixture(m),
                )
              }
            }}
          >
            <Database size={14} />
            <span>SQL Sandbox</span>
          </button>
        </div>

        {/* Problem Quick Badge & Title */}
        <div className="ide-problem-tag-bar">
          <span className={`ide-diff-pill ${difficultyClass}`}>
            {problem.difficulty}
          </span>
          <span className="ide-problem-header-title" title={problem.title}>
            {problem.title}
          </span>
        </div>

        {/* Right-Aligned Toolbar Controls */}
        <div className="ide-toolbar-controls-right">
          {/* Language Selector */}
          <div className="ide-language-picker">
            <span className="ide-control-label">Language:</span>
            <select
              id="ide-language-select"
              aria-label="Select Programming Language Runtime"
              className="ide-select"
              value={selectedLanguage}
              onChange={(e) => handleLanguageChange(e.target.value)}
              disabled={isRunning || isEvaluatingTests || isSqlRunning || isSqlEvaluating}
            >
              {(languages.length > 0 ? languages : GENUINE_SUPPORTED_RUNTIMES).map((lang) => {
                const opt = formatLanguageDisplayOption(lang)
                return (
                  <option key={opt.id} value={opt.id}>
                    {opt.displayLabel}
                  </option>
                )
              })}
            </select>
          </div>

          {/* Autosave Status Badge */}
          <div
            id="ide-autosave-status"
            className={`ide-autosave-indicator status-${saveStatus}`}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '11px',
              padding: '4px 10px',
              borderRadius: '6px',
              background:
                saveStatus === 'error'
                  ? 'rgba(239, 68, 68, 0.12)'
                  : saveStatus === 'saving'
                  ? 'rgba(99, 102, 241, 0.12)'
                  : saveStatus === 'saved'
                  ? 'rgba(34, 197, 94, 0.12)'
                  : 'rgba(255, 255, 255, 0.04)',
              border:
                saveStatus === 'error'
                  ? '1px solid rgba(239, 68, 68, 0.35)'
                  : saveStatus === 'saving'
                  ? '1px solid rgba(99, 102, 241, 0.35)'
                  : saveStatus === 'saved'
                  ? '1px solid rgba(34, 197, 94, 0.35)'
                  : '1px solid rgba(255, 255, 255, 0.08)',
              transition: 'all 0.2s ease',
            }}
          >
            {saveStatus === 'saving' && (
              <>
                <Loader2 className="animate-spin" size={12} color="#818cf8" />
                <span style={{ color: '#a5b4fc', fontWeight: 600 }}>Saving...</span>
              </>
            )}
            {saveStatus === 'saved' && (
              <>
                <CheckCircle2 size={12} color="#22c55e" />
                <span style={{ color: '#86efac', fontWeight: 600 }}>
                  Saved{lastSavedTime ? ` (${lastSavedTime})` : ''}
                </span>
              </>
            )}
            {saveStatus === 'error' && (
              <>
                <AlertCircle size={12} color="#ef4444" />
                <span style={{ color: '#fca5a5', fontWeight: 600 }}>
                  {saveError || 'Save failed'}
                </span>
                <button
                  type="button"
                  id="ide-retry-save-btn"
                  onClick={() => {
                    const currentC = workspaceMode === 'sql' ? sqlQuery : code
                    performSave(question.id, selectedLanguage, currentC)
                  }}
                  style={{
                    marginLeft: '4px',
                    background: '#ef4444',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '4px',
                    padding: '2px 8px',
                    fontSize: '10px',
                    cursor: 'pointer',
                    fontWeight: 700,
                  }}
                  title="Retry saving draft"
                >
                  Retry
                </button>
              </>
            )}
            {saveStatus === 'idle' && (
              <span style={{ color: '#94a3b8', fontSize: '11px', fontWeight: 500 }}>Ready</span>
            )}
          </div>

          {/* SQL Fixture Info (SQL mode) */}
          {workspaceMode === 'sql' && (
            <div className="ide-fixture-tag">
              <Table size={13} />
              <span>Fixture: {question.sql_fixture || problem.sql_fixture || 'employees_departments'}</span>
            </div>
          )}

          {/* Action Buttons */}
          <div className="ide-actions">
            <button
              type="button"
              className="ide-btn ide-btn-secondary"
              onClick={() => setEditorTheme(editorTheme === 'vs-dark' ? 'light' : 'vs-dark')}
              title="Toggle Editor Theme"
            >
              {editorTheme === 'vs-dark' ? '🌙 Dark' : '☀️ Light'}
            </button>

            <button
              type="button"
              className="ide-btn ide-btn-secondary"
              onClick={handleCopyCode}
              title="Copy code to clipboard"
            >
              {copySuccess ? <Check size={13} color="#16a34a" /> : <Copy size={13} />}
              <span>{copySuccess ? 'Copied' : 'Copy'}</span>
            </button>

            <button
              type="button"
              className="ide-btn ide-btn-secondary"
              onClick={handleResetCode}
              title="Reset code to starter template"
            >
              <RotateCcw size={13} />
              <span>Reset</span>
            </button>

            {workspaceMode === 'coding' ? (
              <>
                <button
                  type="button"
                  className="ide-btn ide-btn-run"
                  onClick={handleRunCode}
                  disabled={isRunning || isEvaluatingTests}
                  title="Run code against sample or custom input (Ctrl+Enter)"
                >
                  {isRunning ? (
                    <Loader2 className="animate-spin" size={13} />
                  ) : (
                    <Play size={13} />
                  )}
                  <span>{isRunning ? 'Running...' : 'Run Code'}</span>
                </button>

                <button
                  type="button"
                  className="ide-btn ide-btn-submit"
                  onClick={handleSubmitCode}
                  disabled={isRunning || isEvaluatingTests || isSubmitting}
                  title="Evaluate against all problem test cases"
                >
                  {isEvaluatingTests ? (
                    <Loader2 className="animate-spin" size={13} />
                  ) : (
                    <CheckCircle2 size={13} />
                  )}
                  <span>{isEvaluatingTests ? 'Evaluating...' : 'Submit Solution'}</span>
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  className="ide-btn ide-btn-run"
                  onClick={handleRunSql}
                  disabled={isSqlRunning || isSqlEvaluating}
                  title="Execute query in isolated SQLite sandbox (Ctrl+Enter)"
                >
                  {isSqlRunning ? (
                    <Loader2 className="animate-spin" size={13} />
                  ) : (
                    <Play size={13} />
                  )}
                  <span>{isSqlRunning ? 'Running...' : 'Run Query'}</span>
                </button>

                <button
                  type="button"
                  className="ide-btn ide-btn-submit"
                  onClick={handleSubmitSql}
                  disabled={isSqlRunning || isSqlEvaluating || isSubmitting}
                  title="Evaluate query against benchmark result set"
                >
                  {isSqlEvaluating ? (
                    <Loader2 className="animate-spin" size={13} />
                  ) : (
                    <CheckCircle2 size={13} />
                  )}
                  <span>{isSqlEvaluating ? 'Evaluating...' : 'Submit Query'}</span>
                </button>
              </>
            )}

            {/* Interview Question Navigation Controls */}
            {(onNavigatePrevious || onNavigateNext) && (
              <div
                className="ide-nav-actions"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  marginLeft: '8px',
                  borderLeft: '1px solid rgba(255, 255, 255, 0.15)',
                  paddingLeft: '8px',
                }}
              >
                {onNavigatePrevious && (
                  <button
                    type="button"
                    id="ide-prev-question-btn"
                    className="ide-btn ide-btn-secondary"
                    onClick={handleNavPrevious}
                    disabled={!hasPreviousQuestion || isNavigating}
                    title="Navigate to previous question without submitting"
                  >
                    <ChevronLeft size={13} />
                    <span>Previous</span>
                  </button>
                )}

                {onNavigateNext && (
                  isLastQuestion ? (
                    onFinishInterview ? (
                      <button
                        type="button"
                        id="ide-finish-interview-btn"
                        className="ide-btn ide-btn-primary"
                        style={{ background: '#4f46e5', color: '#ffffff' }}
                        onClick={handleFinish}
                        disabled={isNavigating}
                        title="Complete interview and generate performance report"
                      >
                        {isNavigating ? <Loader2 className="animate-spin" size={13} /> : <Award size={13} />}
                        <span>Complete Session</span>
                      </button>
                    ) : (
                      <button
                        type="button"
                        id="ide-next-question-btn"
                        className="ide-btn ide-btn-secondary"
                        disabled={true}
                        title="This is the final question in the interview"
                        style={{ opacity: 0.6 }}
                      >
                        <span>Next</span>
                        <ChevronRight size={13} />
                      </button>
                    )
                  ) : (
                    <button
                      type="button"
                      id="ide-next-question-btn"
                      className="ide-btn ide-btn-primary"
                      style={{ background: '#2563eb', color: '#ffffff', fontWeight: 600 }}
                      onClick={handleNavNext}
                      disabled={isNavigating}
                      title="Autosave and advance to next question without submitting"
                    >
                      <span>Next</span>
                      {isNavigating ? <Loader2 className="animate-spin" size={13} /> : <ChevronRight size={13} />}
                    </button>
                  )
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Status Callout Banner */}
      {statusMessage && (
        <div
          className={`ide-status-banner ${
            statusMessage.includes('verified') || statusMessage.includes('passed')
              ? 'success'
              : 'info'
          }`}
        >
          <CheckCircle2 size={14} />
          <span>{statusMessage}</span>
        </div>
      )}

      {/* Responsive Split Container: Left Pane (Problem Statement) | Divider | Right Pane (Editor & Output) */}
      <div className="ide-split-container" ref={splitContainerRef}>
        {/* =================================================================== */}
        {/* LEFT PANE: LeetCode-Style Problem Statement Panel                    */}
        {/* =================================================================== */}
        <div
          className="ide-left-pane"
          style={{ width: `calc(${splitRatio}% - 4px)` }}
          id="ide-problem-panel"
        >
          {/* Problem Header Info */}
          <div className="ide-left-header">
            <div className="ide-problem-title-row">
              <span className={`ide-diff-badge ${difficultyClass}`}>
                {problem.difficulty}
              </span>
              <h2 className="ide-problem-title">{problem.title}</h2>
            </div>
            <div className="ide-problem-meta-row">
              <span className="ide-skill-badge">{problem.assessed_skill}</span>
              {question.question_type && (
                <span className="ide-mode-badge">{question.question_type.toUpperCase()}</span>
              )}
            </div>
          </div>

          {/* Left Pane Navigation Tabs */}
          <div className="ide-left-tabs" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={leftTab === 'description'}
              className={`ide-left-tab ${leftTab === 'description' ? 'active' : ''}`}
              onClick={() => setLeftTab('description')}
            >
              <BookOpen size={13} />
              <span>Description</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={leftTab === 'examples'}
              className={`ide-left-tab ${leftTab === 'examples' ? 'active' : ''}`}
              onClick={() => setLeftTab('examples')}
            >
              <FileCode size={13} />
              <span>Examples ({problem.examples.length})</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={leftTab === 'constraints'}
              className={`ide-left-tab ${leftTab === 'constraints' ? 'active' : ''}`}
              onClick={() => setLeftTab('constraints')}
            >
              <ListFilter size={13} />
              <span>Constraints ({problem.constraints.length})</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={leftTab === 'testcases'}
              className={`ide-left-tab ${leftTab === 'testcases' ? 'active' : ''}`}
              onClick={() => setLeftTab('testcases')}
            >
              <CheckSquare size={13} />
              <span>Test Cases ({problem.test_cases.length})</span>
            </button>
            {workspaceMode === 'sql' && (
              <button
                type="button"
                role="tab"
                aria-selected={leftTab === 'schema'}
                className={`ide-left-tab ${leftTab === 'schema' ? 'active' : ''}`}
                onClick={() => setLeftTab('schema')}
              >
                <Table size={13} />
                <span>DB Schema</span>
              </button>
            )}
          </div>

          {/* Left Pane Tab Content with Independent Scroll */}
          <div className="ide-left-content">
            {/* TAB: Description */}
            {leftTab === 'description' && (
              <div className="ide-panel-section">
                <div className="ide-prose-description">
                  {problem.description.split('\n\n').map((paragraph, pIdx) => (
                    <p key={pIdx}>{paragraph}</p>
                  ))}
                </div>

                {/* Execution Contract Callout */}
                <div className="ide-contract-hint-card">
                  <div className="ide-contract-header">
                    <Sparkles size={14} color="#818cf8" />
                    <strong>What should my code return or print?</strong>
                    <span className="ide-contract-badge">{problem.execution_contract?.toUpperCase() || 'FUNCTION'}</span>
                  </div>
                  <p className="ide-contract-text">
                    {problem.execution_hint || (
                      problem.execution_contract === 'stdio'
                        ? 'Read input from standard input (stdin) and print your computed result to standard output (stdout).'
                        : problem.execution_contract === 'sql'
                        ? 'Write a standard SQL query returning the required relational columns and rows.'
                        : 'Implement the configured function or method and return the result. Capturing return values is automated.'
                    )}
                  </p>
                </div>

                {/* Input & Output Format Specifications */}
                <div className="ide-spec-card">
                  <h4 className="ide-spec-title">Input Format</h4>
                  <p className="ide-spec-text">{problem.input_format}</p>
                  <h4 className="ide-spec-title" style={{ marginTop: '10px' }}>Expected Output Format</h4>
                  <p className="ide-spec-text">{problem.output_format}</p>
                </div>

                {/* Dedicated Sample Examples in Description */}
                <div className="ide-summary-examples">
                  <div className="ide-block-header-row" style={{ marginBottom: '8px' }}>
                    <h4 className="ide-subheading" style={{ margin: 0 }}>Sample Examples:</h4>
                    {problem.examples.length > 0 && (
                      <button
                        type="button"
                        className="ide-btn-text"
                        onClick={() => setLeftTab('examples')}
                      >
                        View in Examples Tab ({problem.examples.length}) →
                      </button>
                    )}
                  </div>

                  {problem.examples.length === 0 ? (
                    <div className="ide-empty-examples-card">
                      <AlertCircle size={15} />
                      <span>Sample examples are not configured for this question.</span>
                    </div>
                  ) : (
                    problem.examples.map((ex, idx) => (
                      <div key={idx} className="ide-example-card">
                        <div className="ide-example-card-header">
                          <span className="ide-example-card-title">Example {idx + 1}</span>
                          <button
                            type="button"
                            className="ide-btn-text"
                            onClick={() => {
                              setCustomStdin(ex.input)
                              setActiveTab('stdin')
                            }}
                            title="Load this example input into custom stdin"
                          >
                            Use as Custom Input →
                          </button>
                        </div>

                        <div className="ide-example-block">
                          <div className="ide-block-header-row">
                            <span className="ide-code-lbl">Input</span>
                            <button
                              type="button"
                              className="ide-copy-btn"
                              onClick={() => handleCopySnippet(ex.input, `desc-ex-in-${idx}`)}
                              title="Copy Input"
                            >
                              {copiedSnippetId === `desc-ex-in-${idx}` ? (
                                <Check size={12} color="#16a34a" />
                              ) : (
                                <Copy size={12} />
                              )}
                              <span>{copiedSnippetId === `desc-ex-in-${idx}` ? 'Copied' : 'Copy'}</span>
                            </button>
                          </div>
                          <pre className="ide-example-code">{ex.input}</pre>
                        </div>

                        <div className="ide-example-block">
                          <div className="ide-block-header-row">
                            <span className="ide-code-lbl">Expected Output</span>
                            <button
                              type="button"
                              className="ide-copy-btn"
                              onClick={() => handleCopySnippet(ex.output, `desc-ex-out-${idx}`)}
                              title="Copy Expected Output"
                            >
                              {copiedSnippetId === `desc-ex-out-${idx}` ? (
                                <Check size={12} color="#16a34a" />
                              ) : (
                                <Copy size={12} />
                              )}
                              <span>{copiedSnippetId === `desc-ex-out-${idx}` ? 'Copied' : 'Copy'}</span>
                            </button>
                          </div>
                          <pre className="ide-example-code">{ex.output}</pre>
                        </div>

                        {ex.explanation && (
                          <div className="ide-example-block">
                            <span className="ide-code-lbl">Explanation</span>
                            <p className="ide-example-explanation">{ex.explanation}</p>
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>

                {/* Constraints Snippet */}
                {problem.constraints.length > 0 && (
                  <div className="ide-summary-constraints">
                    <h4 className="ide-subheading">Constraints:</h4>
                    <ul className="ide-constraints-list">
                      {problem.constraints.map((c, cIdx) => (
                        <li key={cIdx}>
                          <code>{c}</code>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Evaluation Rubric */}
                {question.rubric && (
                  <div className="ide-rubric-card">
                    <span className="ide-rubric-badge">Scoring Rubric</span>
                    <p>{question.rubric}</p>
                  </div>
                )}
              </div>
            )}

            {/* TAB: Examples */}
            {leftTab === 'examples' && (
              <div className="ide-panel-section">
                <div className="ide-contract-hint-card" style={{ marginBottom: '16px' }}>
                  <div className="ide-contract-header">
                    <Sparkles size={14} color="#818cf8" />
                    <strong>What should my code return or print?</strong>
                    <span className="ide-contract-badge">{problem.execution_contract?.toUpperCase() || 'FUNCTION'}</span>
                  </div>
                  <p className="ide-contract-text">
                    {problem.execution_hint || (
                      problem.execution_contract === 'stdio'
                        ? 'Read input from standard input (stdin) and print your computed result to standard output (stdout).'
                        : problem.execution_contract === 'sql'
                        ? 'Write a standard SQL query returning the required relational columns and rows.'
                        : 'Implement the configured function or method and return the result. Capturing return values is automated.'
                    )}
                  </p>
                </div>

                <div className="ide-block-header-row" style={{ marginBottom: '12px' }}>
                  <h3 className="ide-section-heading" style={{ margin: 0 }}>Configured Problem Examples</h3>
                  <span className="ide-tc-count-tag">{problem.examples.length} Configured</span>
                </div>

                {problem.examples.length === 0 ? (
                  <div className="ide-empty-examples-card">
                    <AlertCircle size={15} />
                    <span>Sample examples are not configured for this question.</span>
                  </div>
                ) : (
                  problem.examples.map((ex, idx) => (
                    <div key={idx} className="ide-example-card">
                      <div className="ide-example-card-header">
                        <span className="ide-example-card-title">Example {idx + 1}</span>
                        <button
                          type="button"
                          className="ide-btn-text"
                          onClick={() => {
                            setCustomStdin(ex.input)
                            setActiveTab('stdin')
                          }}
                          title="Load this example input into custom stdin"
                        >
                          Use as Custom Input →
                        </button>
                      </div>

                      <div className="ide-example-block">
                        <div className="ide-block-header-row">
                          <span className="ide-code-lbl">Input</span>
                          <button
                            type="button"
                            className="ide-copy-btn"
                            onClick={() => handleCopySnippet(ex.input, `ex-tab-in-${idx}`)}
                            title="Copy Input"
                          >
                            {copiedSnippetId === `ex-tab-in-${idx}` ? (
                              <Check size={12} color="#16a34a" />
                            ) : (
                              <Copy size={12} />
                            )}
                            <span>{copiedSnippetId === `ex-tab-in-${idx}` ? 'Copied' : 'Copy'}</span>
                          </button>
                        </div>
                        <pre className="ide-example-code">{ex.input}</pre>
                      </div>

                      <div className="ide-example-block">
                        <div className="ide-block-header-row">
                          <span className="ide-code-lbl">Expected Output</span>
                          <button
                            type="button"
                            className="ide-copy-btn"
                            onClick={() => handleCopySnippet(ex.output, `ex-tab-out-${idx}`)}
                            title="Copy Expected Output"
                          >
                            {copiedSnippetId === `ex-tab-out-${idx}` ? (
                              <Check size={12} color="#16a34a" />
                            ) : (
                              <Copy size={12} />
                            )}
                            <span>{copiedSnippetId === `ex-tab-out-${idx}` ? 'Copied' : 'Copy'}</span>
                          </button>
                        </div>
                        <pre className="ide-example-code">{ex.output}</pre>
                      </div>

                      {ex.explanation && (
                        <div className="ide-example-block">
                          <span className="ide-code-lbl">Explanation</span>
                          <p className="ide-example-explanation">{ex.explanation}</p>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}

            {/* TAB: Constraints */}
            {leftTab === 'constraints' && (
              <div className="ide-panel-section">
                <h3 className="ide-section-heading">Operational &amp; Algorithmic Constraints</h3>
                <ul className="ide-constraints-list full">
                  {problem.constraints.map((c, idx) => (
                    <li key={idx} className="ide-constraint-item">
                      <code>{c}</code>
                    </li>
                  ))}
                </ul>
                <div className="ide-complexity-hint">
                  <Sparkles size={14} color="#6366F1" />
                  <span>Aim for an optimal time complexity solution adhering to the given input bounds.</span>
                </div>
              </div>
            )}

            {/* TAB: Test Cases */}
            {leftTab === 'testcases' && (
              <div className="ide-panel-section">
                <div className="ide-tc-header-row">
                  <h3 className="ide-section-heading">Configured Test Cases</h3>
                  <span className="ide-tc-count-tag">{problem.test_cases.length} Total</span>
                </div>

                {!problem.test_cases_available ? (
                  <div className="ide-unavailable-callout">
                    <AlertCircle size={16} />
                    <div>
                      <strong>Test cases unavailable</strong>
                      <p>
                        This question currently does not have structured test cases configured in its question definition.
                        You can test your code using the &ldquo;Custom Input (stdin)&rdquo; tab.
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="ide-tc-preview-list">
                    {problem.test_cases.map((tc, idx) => (
                      <div key={tc.id || idx} className="ide-tc-preview-card">
                        <div className="ide-tc-preview-top">
                          <span className="ide-tc-num">
                            Test Case #{idx + 1} {tc.is_hidden && <span className="ide-hidden-pill">Hidden Benchmark</span>}
                          </span>
                          {!tc.is_hidden && (
                            <button
                              type="button"
                              className="ide-btn-text"
                              onClick={() => {
                                setCustomStdin(tc.input)
                                setActiveTab('stdin')
                              }}
                            >
                              Load Input →
                            </button>
                          )}
                        </div>
                        {!tc.is_hidden ? (
                          <>
                            <div className="ide-tc-preview-field">
                              <div className="ide-tc-header-row-inline">
                                <span className="ide-field-label">Input:</span>
                                <button
                                  type="button"
                                  className="ide-copy-btn mini"
                                  onClick={() => handleCopySnippet(tc.input, `tc-prev-in-${idx}`)}
                                  title="Copy Input"
                                >
                                  {copiedSnippetId === `tc-prev-in-${idx}` ? <Check size={11} color="#16a34a" /> : <Copy size={11} />}
                                  <span>{copiedSnippetId === `tc-prev-in-${idx}` ? 'Copied' : 'Copy'}</span>
                                </button>
                              </div>
                              <pre className="ide-tc-code">{tc.input}</pre>
                            </div>
                            <div className="ide-tc-preview-field">
                              <div className="ide-tc-header-row-inline">
                                <span className="ide-field-label">Expected Output:</span>
                                <button
                                  type="button"
                                  className="ide-copy-btn mini"
                                  onClick={() => handleCopySnippet(tc.expected_output, `tc-prev-out-${idx}`)}
                                  title="Copy Expected Output"
                                >
                                  {copiedSnippetId === `tc-prev-out-${idx}` ? <Check size={11} color="#16a34a" /> : <Copy size={11} />}
                                  <span>{copiedSnippetId === `tc-prev-out-${idx}` ? 'Copied' : 'Copy'}</span>
                                </button>
                              </div>
                              <pre className="ide-tc-code">
                                {tc.is_hidden
                                  ? '[Hidden Test Case - Verified upon submission]'
                                  : (tc.expected_output !== undefined && tc.expected_output !== null && String(tc.expected_output).trim() !== ''
                                    ? tc.expected_output
                                    : '[Awaiting Oracle Output]')}
                              </pre>
                            </div>
                            {tc.explanation && (
                              <p className="ide-tc-explanation">
                                <em>Note:</em> {tc.explanation}
                              </p>
                            )}
                          </>
                        ) : (
                          <p className="ide-tc-hidden-desc">
                            Hidden private test case evaluated upon solution submission.
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* TAB: SQL Database Schema (SQL mode) */}
            {leftTab === 'schema' && workspaceMode === 'sql' && (
              <div className="ide-panel-section">
                <h3 className="ide-section-heading">Relational Schema &amp; Sample Datasets</h3>
                {sqlFixture ? (
                  <div className="ide-fixture-tables">
                    {sqlFixture.tables.map((t, idx) => (
                      <div key={idx} className="ide-schema-card">
                        <div className="ide-schema-card-header">
                          <Table size={14} />
                          <span className="ide-schema-table-name">Table: <code>{t.table_name || t.name}</code></span>
                          <span className="ide-schema-row-badge">{t.row_count ?? (t.sample_rows?.length || 0)} rows</span>
                        </div>
                        <div className="ide-columns-tag-cloud">
                          {t.columns.map((c, cIdx) => (
                            <span key={cIdx} className="ide-col-chip">
                              <strong>{c.name}</strong>: <em>{c.type}</em>
                            </span>
                          ))}
                        </div>
                        {t.sample_rows && t.sample_rows.length > 0 && (
                          <div className="ide-table-container mini">
                            <table className="ide-sql-table">
                              <thead>
                                <tr>
                                  {t.columns.map((col, cIdx) => (
                                    <th key={cIdx}>{col.name}</th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {t.sample_rows.slice(0, 4).map((row, rIdx) => (
                                  <tr key={rIdx}>
                                    {t.columns.map((col, cIdx) => (
                                      <td key={cIdx}>{row[col.name] != null ? String(row[col.name]) : 'NULL'}</td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="ide-loading-schema">
                    <Loader2 className="animate-spin" size={18} />
                    <span>Loading SQLite relational fixtures...</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* =================================================================== */}
        {/* DRAGGABLE DIVIDER RESIZER                                           */}
        {/* =================================================================== */}
        <div
          className={`ide-split-divider ${isDragging ? 'is-dragging' : ''}`}
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize problem description and code editor panes"
          onPointerDown={handlePointerDownDivider}
          title="Drag left or right to resize panes"
        >
          <div className="ide-split-handle" />
        </div>

        {/* =================================================================== */}
        {/* RIGHT PANE: Code Editor & Execution Bottom Panel                    */}
        {/* =================================================================== */}
        <div
          className="ide-right-pane"
          style={{ width: `calc(${100 - splitRatio}% - 4px)`, flex: '1 1 0%', minWidth: 0 }}
        >
          {/* Editor Body */}
          <div className="ide-editor-wrapper">
            <Editor
              height="100%"
              language={currentMonacoLanguage}
              value={workspaceMode === 'coding' ? code : sqlQuery}
              theme={editorTheme}
              onChange={handleEditorChange}
              onMount={handleEditorDidMount}
              options={{
                fontSize: 13,
                fontFamily:
                  "'Fira Code', 'Cascadia Code', 'JetBrains Mono', Consolas, Menlo, monospace",
                minimap: { enabled: false },
                lineNumbers: 'on',
                scrollBeyondLastLine: false,
                automaticLayout: true,
                tabSize: 4,
                wordWrap: 'on',
                bracketPairColorization: { enabled: true },
                autoClosingBrackets: 'always',
                autoClosingQuotes: 'always',
                formatOnPaste: true,
                formatOnType: true,
                suggestOnTriggerCharacters: true,
                quickSuggestions: { other: true, comments: false, strings: true },
                folding: true,
                renderWhitespace: 'selection',
              }}
            />
          </div>

          {/* Bottom Collapsible Panel: Output / Test Cases / Custom Stdin / Schema */}
          <div className="ide-bottom-panel">
            <div className="ide-bottom-tabs">
              <button
                type="button"
                className={`ide-bottom-tab ${activeTab === 'output' ? 'active' : ''}`}
                onClick={() => setActiveTab('output')}
              >
                <Terminal size={13} />
                <span>Execution Output</span>
              </button>

              {workspaceMode === 'coding' && (
                <>
                  <button
                    type="button"
                    className={`ide-bottom-tab ${activeTab === 'tests' ? 'active' : ''}`}
                    onClick={() => setActiveTab('tests')}
                  >
                    <CheckCircle2 size={13} />
                    <span>
                      Test Cases{' '}
                      {submissionResult && `(${submissionResult.passed_tests}/${submissionResult.total_tests})`}
                    </span>
                  </button>

                  <button
                    type="button"
                    className={`ide-bottom-tab ${activeTab === 'stdin' ? 'active' : ''}`}
                    onClick={() => setActiveTab('stdin')}
                  >
                    <FileCode size={13} />
                    <span>Custom Input (stdin)</span>
                  </button>
                </>
              )}

              {workspaceMode === 'sql' && (
                <>
                  <button
                    type="button"
                    className={`ide-bottom-tab ${activeTab === 'schema' ? 'active' : ''}`}
                    onClick={() => setActiveTab('schema')}
                  >
                    <Table size={13} />
                    <span>Database Schema</span>
                  </button>

                  <button
                    type="button"
                    className={`ide-bottom-tab ${activeTab === 'tests' ? 'active' : ''}`}
                    onClick={() => setActiveTab('tests')}
                  >
                    <CheckCircle2 size={13} />
                    <span>
                      Query Evaluation {sqlSubmission && (sqlSubmission.is_correct ? '✓ Passed' : '✗ Failed')}
                    </span>
                  </button>
                </>
              )}
            </div>

            {/* Tab Contents */}
            <div className="ide-bottom-content">
              {/* Output Tab */}
              {activeTab === 'output' && (
                <div className="ide-tab-pane">
                  {workspaceMode === 'coding' ? (
                    executionResponse ? (
                      <div className="ide-output-view">
                        <div className="ide-output-meta">
                          <span className={`ide-badge ${executionResponse.status}`}>
                            Status: {executionResponse.status.toUpperCase()}
                          </span>
                          {executionResponse.execution_time_ms != null && (
                            <span className="ide-meta-item">
                              <Clock size={12} /> {executionResponse.execution_time_ms.toFixed(1)} ms
                            </span>
                          )}
                          {executionResponse.memory_kb != null && (
                            <span className="ide-meta-item">
                              <HardDrive size={12} /> {(executionResponse.memory_kb / 1024).toFixed(2)} MB
                            </span>
                          )}
                          <span className="ide-meta-item">Exit Code: {executionResponse.exit_code}</span>
                        </div>

                        {executionResponse.error && (
                          <div className="ide-output-section error">
                            <div className="ide-block-header-row">
                              <span className="ide-output-label error">Execution / Compiler Error:</span>
                              <button
                                type="button"
                                className="ide-copy-btn mini"
                                onClick={() => handleCopySnippet(executionResponse.error || '', 'out-err')}
                                title="Copy Error"
                              >
                                {copiedSnippetId === 'out-err' ? <Check size={11} color="#16a34a" /> : <Copy size={11} />}
                                <span>{copiedSnippetId === 'out-err' ? 'Copied' : 'Copy'}</span>
                              </button>
                            </div>
                            <pre className="ide-code-block stderr">{executionResponse.error}</pre>
                          </div>
                        )}

                        {executionResponse.stderr && (
                          <div className="ide-output-section">
                            <div className="ide-block-header-row">
                              <span className="ide-output-label error">Standard Error / Compiler Diagnostics:</span>
                              <button
                                type="button"
                                className="ide-copy-btn mini"
                                onClick={() => handleCopySnippet(executionResponse.stderr || '', 'out-stderr')}
                                title="Copy Diagnostics"
                              >
                                {copiedSnippetId === 'out-stderr' ? <Check size={11} color="#16a34a" /> : <Copy size={11} />}
                                <span>{copiedSnippetId === 'out-stderr' ? 'Copied' : 'Copy'}</span>
                              </button>
                            </div>
                            <pre className="ide-code-block stderr">{executionResponse.stderr}</pre>
                          </div>
                        )}

                        {executionResponse.stdout && (
                          <div className="ide-output-section">
                            <div className="ide-block-header-row">
                              <span className="ide-output-label">Standard Output:</span>
                              <button
                                type="button"
                                className="ide-copy-btn mini"
                                onClick={() => handleCopySnippet(executionResponse.stdout || '', 'out-stdout')}
                                title="Copy Output"
                              >
                                {copiedSnippetId === 'out-stdout' ? <Check size={11} color="#16a34a" /> : <Copy size={11} />}
                                <span>{copiedSnippetId === 'out-stdout' ? 'Copied' : 'Copy'}</span>
                              </button>
                            </div>
                            <pre className="ide-code-block stdout">{executionResponse.stdout}</pre>
                          </div>
                        )}

                        {!executionResponse.stdout && !executionResponse.stderr && !executionResponse.error && (
                          executionResponse.status === 'success' && executionResponse.exit_code === 0 ? (
                            <p className="ide-empty-output">Program executed cleanly with no stdout/stderr output.</p>
                          ) : (
                            <p className="ide-empty-output error">
                              Program finished with status <strong>{executionResponse.status.toUpperCase()}</strong> (exit code {executionResponse.exit_code}). No stdout or stderr was generated.
                            </p>
                          )
                        )}
                      </div>
                    ) : (
                      <div className="ide-output-placeholder">
                        <Terminal size={20} />
                        <p>Click &ldquo;Run Code&rdquo; or press <code>Ctrl+Enter</code> to execute against sample or custom input.</p>
                      </div>
                    )
                  ) : sqlResponse ? (
                    <div className="ide-output-view">
                      <div className="ide-output-meta">
                        <span className={`ide-badge ${sqlResponse.status}`}>
                          Status: {sqlResponse.status.toUpperCase()}
                        </span>
                        <span className="ide-meta-item">
                          <Clock size={12} /> {sqlResponse.execution_time_ms.toFixed(1)} ms
                        </span>
                        <span className="ide-meta-item">Rows Returned: {sqlResponse.row_count}</span>
                      </div>

                      {sqlResponse.error && (
                        <div className="ide-output-section">
                          <span className="ide-output-label error">SQL Error:</span>
                          <pre className="ide-code-block stderr">{sqlResponse.error}</pre>
                        </div>
                      )}

                      {sqlResponse.columns && sqlResponse.columns.length > 0 ? (
                        <div className="ide-table-container">
                          <table className="ide-sql-table">
                            <thead>
                              <tr>
                                {sqlResponse.columns.map((col, idx) => (
                                  <th key={idx}>{col}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {sqlResponse.rows.map((row, rIdx) => (
                                <tr key={rIdx}>
                                  {row.map((cell, cIdx) => (
                                    <td key={cIdx}>{cell === null ? 'NULL' : String(cell)}</td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        !sqlResponse.error && (
                          <p className="ide-empty-output">Query executed successfully (0 rows returned).</p>
                        )
                      )}
                    </div>
                  ) : (
                    <div className="ide-output-placeholder">
                      <Database size={20} />
                      <p>Click &ldquo;Run Query&rdquo; or press <code>Ctrl+Enter</code> to execute SQL against the sandbox.</p>
                    </div>
                  )}
                </div>
              )}

              {/* Test Cases Tab (DSA Mode) */}
              {activeTab === 'tests' && workspaceMode === 'coding' && (
                <div className="ide-tab-pane">
                  {!problem.test_cases_available ? (
                    <div className="ide-unavailable-callout">
                      <AlertCircle size={16} />
                      <div>
                        <strong>Test cases unavailable</strong>
                        <p>
                          Test cases are not configured on this question definition.
                          Please use the &ldquo;Custom Input (stdin)&rdquo; tab to run and verify your code.
                        </p>
                      </div>
                    </div>
                  ) : submissionResult ? (
                    <div className="ide-test-results">
                      {/* Summary Banner */}
                      <div className="ide-test-summary">
                        <div className="ide-test-score">
                          <span className={`score-badge ${submissionResult.all_passed ? 'passed' : 'failed'}`}>
                            {submissionResult.all_passed ? 'ALL PASSED' : 'TESTS FAILED'}
                          </span>
                          <span className="ide-score-ratio">
                            Passed: {submissionResult.passed_tests} / {submissionResult.total_tests}
                          </span>
                          <span className="ide-score-failed">
                            Failed: {submissionResult.total_tests - submissionResult.passed_tests}
                          </span>
                        </div>

                        {submissionResult.estimated_time_complexity && (
                          <div className="ide-complexity-badges">
                            <span className="pill-badge neutral">
                              Est. Time: {submissionResult.estimated_time_complexity}
                            </span>
                            {submissionResult.estimated_space_complexity && (
                              <span className="pill-badge neutral">
                                Est. Space: {submissionResult.estimated_space_complexity}
                              </span>
                            )}
                          </div>
                        )}

                        <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px', alignItems: 'center' }}>
                          <button
                            type="button"
                            className="ide-btn-text"
                            onClick={() => setSubmissionResult(null)}
                            title="Switch back to sample test cases and custom argument inspector"
                            style={{ fontSize: '12px' }}
                          >
                            Inspect Sample Inputs
                          </button>
                        </div>
                      </div>

                      {/* Case Selectors */}
                      <div className="ide-tc-pill-bar">
                        {submissionResult.results.map((tc, idx) => (
                          <button
                            key={tc.test_case_id || idx}
                            type="button"
                            className={`ide-tc-pill ${idx === selectedTestCaseIdx ? 'active' : ''} ${tc.passed ? 'passed' : 'failed'}`}
                            onClick={() => setSelectedTestCaseIdx(idx)}
                          >
                            {tc.passed ? (
                              <CheckCircle2 size={12} color="#16a34a" />
                            ) : (
                              <XCircle size={12} color="#dc2626" />
                            )}
                            <span>Case {idx + 1} {tc.is_hidden ? '(Hidden)' : ''}</span>
                          </button>
                        ))}
                      </div>

                      {/* Selected Case Detail Card */}
                      {submissionResult.results[selectedTestCaseIdx] && (
                        <div className={`ide-test-card ${submissionResult.results[selectedTestCaseIdx].passed ? 'passed' : 'failed'}`}>
                          <div className="ide-test-card-header">
                            <span className="ide-test-card-title">
                              Case #{selectedTestCaseIdx + 1} Detail{' '}
                              {submissionResult.results[selectedTestCaseIdx].is_hidden && '(Hidden Benchmark Case)'}
                            </span>
                            <span className={`ide-test-status-pill ${submissionResult.results[selectedTestCaseIdx].passed ? 'pass' : 'fail'}`}>
                              {submissionResult.results[selectedTestCaseIdx].passed
                                ? 'PASSED'
                                : submissionResult.results[selectedTestCaseIdx].error?.toLowerCase().includes('timeout')
                                ? 'TIMEOUT'
                                : submissionResult.results[selectedTestCaseIdx].error?.toLowerCase().includes('compil')
                                ? 'COMPILATION ERROR'
                                : submissionResult.results[selectedTestCaseIdx].error?.toLowerCase().includes('syntax')
                                ? 'SYNTAX ERROR'
                                : submissionResult.results[selectedTestCaseIdx].error
                                ? 'RUNTIME ERROR'
                                : 'WRONG ANSWER'}
                            </span>
                          </div>

                          {!submissionResult.results[selectedTestCaseIdx].is_hidden ? (
                            <div className="ide-test-card-details">
                              <div className="ide-tc-col">
                                <div className="ide-tc-header-row-inline">
                                  <span className="ide-tc-lbl">Input:</span>
                                  <button
                                    type="button"
                                    className="ide-copy-btn mini"
                                    onClick={() => handleCopySnippet(submissionResult.results[selectedTestCaseIdx].input || '', `res-in-${selectedTestCaseIdx}`)}
                                    title="Copy Input"
                                  >
                                    {copiedSnippetId === `res-in-${selectedTestCaseIdx}` ? <Check size={11} color="#16a34a" /> : <Copy size={11} />}
                                    <span>{copiedSnippetId === `res-in-${selectedTestCaseIdx}` ? 'Copied' : 'Copy'}</span>
                                  </button>
                                </div>
                                <pre className="ide-tc-code">{submissionResult.results[selectedTestCaseIdx].input || '(empty)'}</pre>
                              </div>

                              <div className="ide-tc-col">
                                <div className="ide-tc-header-row-inline">
                                  <span className="ide-tc-lbl">Expected Output:</span>
                                  <button
                                    type="button"
                                    className="ide-copy-btn mini"
                                    onClick={() => handleCopySnippet(submissionResult.results[selectedTestCaseIdx].expected_output || '', `res-exp-${selectedTestCaseIdx}`)}
                                    title="Copy Expected Output"
                                  >
                                    {copiedSnippetId === `res-exp-${selectedTestCaseIdx}` ? <Check size={11} color="#16a34a" /> : <Copy size={11} />}
                                    <span>{copiedSnippetId === `res-exp-${selectedTestCaseIdx}` ? 'Copied' : 'Copy'}</span>
                                  </button>
                                </div>
                                <pre className="ide-tc-code">{submissionResult.results[selectedTestCaseIdx].expected_output}</pre>
                              </div>

                              <div className="ide-tc-col">
                                <div className="ide-tc-header-row-inline">
                                  <span className="ide-tc-lbl">Actual Output:</span>
                                  <button
                                    type="button"
                                    className="ide-copy-btn mini"
                                    onClick={() => handleCopySnippet(submissionResult.results[selectedTestCaseIdx].actual_output || '', `res-act-${selectedTestCaseIdx}`)}
                                    title="Copy Actual Output"
                                  >
                                    {copiedSnippetId === `res-act-${selectedTestCaseIdx}` ? <Check size={11} color="#16a34a" /> : <Copy size={11} />}
                                    <span>{copiedSnippetId === `res-act-${selectedTestCaseIdx}` ? 'Copied' : 'Copy'}</span>
                                  </button>
                                </div>
                                <pre className="ide-tc-code">{submissionResult.results[selectedTestCaseIdx].actual_output || '(no output)'}</pre>
                              </div>
                            </div>
                          ) : (
                            <p className="ide-tc-hidden-desc">
                              Hidden test case output is kept private to prevent hardcoding. Status:{' '}
                              <strong>{submissionResult.results[selectedTestCaseIdx].passed ? 'PASSED' : 'OUTPUT MISMATCH'}</strong>
                            </p>
                          )}

                          {submissionResult.results[selectedTestCaseIdx].error && (
                            <div className="ide-tc-error">
                              <div className="ide-block-header-row">
                                <span><strong>Error / Exception:</strong></span>
                                <button
                                  type="button"
                                  className="ide-copy-btn mini"
                                  onClick={() => handleCopySnippet(submissionResult.results[selectedTestCaseIdx].error || '', `tc-err-${selectedTestCaseIdx}`)}
                                  title="Copy Error"
                                >
                                  {copiedSnippetId === `tc-err-${selectedTestCaseIdx}` ? <Check size={11} color="#16a34a" /> : <Copy size={11} />}
                                  <span>{copiedSnippetId === `tc-err-${selectedTestCaseIdx}` ? 'Copied' : 'Copy'}</span>
                                </button>
                              </div>
                              <pre className="ide-code-block stderr" style={{ marginTop: '6px' }}>
                                {submissionResult.results[selectedTestCaseIdx].error}
                              </pre>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="ide-sample-cases-view">
                      <div className="ide-test-summary">
                        <div className="ide-test-score">
                          <span className="pill-badge neutral">
                            Sample Test Cases ({visibleTestCases.length})
                          </span>
                          <span className="ide-score-ratio" style={{ color: '#94a3b8' }}>
                            Inspect and customize arguments for test execution
                          </span>
                        </div>
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                          <button
                            type="button"
                            className="ide-btn ide-btn-run"
                            onClick={() => handleRunCode()}
                            disabled={isRunning || isEvaluatingTests}
                            style={{ padding: '4px 10px', fontSize: '12px' }}
                          >
                            <Play size={12} />
                            <span>Run Case #{selectedTestCaseIdx + 1}</span>
                          </button>
                        </div>
                      </div>

                      {/* Pill selector for visible test cases */}
                      <div className="ide-tc-pill-bar">
                        {visibleTestCases.map((tc, idx) => {
                          const isEdited = customCaseInputs[idx] !== undefined && customCaseInputs[idx] !== tc.input
                          return (
                            <button
                              key={tc.id || idx}
                              type="button"
                              className={`ide-tc-pill ${idx === selectedTestCaseIdx ? 'active' : ''}`}
                              onClick={() => setSelectedTestCaseIdx(idx)}
                            >
                              <span>Case {idx + 1}</span>
                              {isEdited && <span style={{ fontSize: '10px', opacity: 0.7 }}>(custom)</span>}
                            </button>
                          )
                        })}
                      </div>

                      {/* Active Case Details & Argument Editor */}
                      {visibleTestCases[selectedTestCaseIdx] && (
                        <div className="ide-test-card" style={{ marginTop: '12px', border: '1px solid var(--border-color, #334155)' }}>
                          <div className="ide-test-card-header">
                            <span className="ide-test-card-title">
                              Case #{selectedTestCaseIdx + 1} Inputs &amp; Expected Output
                            </span>
                            {customCaseInputs[selectedTestCaseIdx] !== undefined &&
                              customCaseInputs[selectedTestCaseIdx] !== visibleTestCases[selectedTestCaseIdx].input && (
                                <button
                                  type="button"
                                  className="ide-btn-text"
                                  onClick={() => {
                                    setCustomCaseInputs((prev) => {
                                      const next = { ...prev }
                                      delete next[selectedTestCaseIdx]
                                      return next
                                    })
                                  }}
                                  title="Reset arguments to declared sample test case input"
                                >
                                  Reset to Sample Input
                                </button>
                              )}
                          </div>

                          <div className="ide-test-card-details">
                            {/* Input Arguments Field */}
                            <div className="ide-tc-col" style={{ flex: 1.2 }}>
                              <div className="ide-tc-header-row-inline">
                                <span className="ide-tc-lbl">Input (Arguments):</span>
                                <span style={{ fontSize: '11px', color: '#64748b' }}>Editable</span>
                              </div>
                              <textarea
                                className="ide-stdin-textarea"
                                style={{ minHeight: '80px', fontFamily: 'monospace', fontSize: '13px' }}
                                value={
                                  customCaseInputs[selectedTestCaseIdx] ??
                                  visibleTestCases[selectedTestCaseIdx].input ??
                                  ''
                                }
                                onChange={(e) => {
                                  const val = e.target.value
                                  setCustomCaseInputs((prev) => ({
                                    ...prev,
                                    [selectedTestCaseIdx]: val,
                                  }))
                                }}
                                placeholder="Enter arguments for this test case..."
                                rows={3}
                              />
                            </div>

                            {/* Expected Output */}
                            <div className="ide-tc-col">
                              <div className="ide-tc-header-row-inline">
                                <span className="ide-tc-lbl">Expected Output:</span>
                              </div>
                              <pre className="ide-tc-code" style={{ minHeight: '80px' }}>
                                {visibleTestCases[selectedTestCaseIdx].is_hidden
                                  ? '[Hidden Test Case - Verified upon submission]'
                                  : (visibleTestCases[selectedTestCaseIdx].expected_output !== undefined &&
                                     visibleTestCases[selectedTestCaseIdx].expected_output !== null &&
                                     String(visibleTestCases[selectedTestCaseIdx].expected_output).trim() !== ''
                                    ? visibleTestCases[selectedTestCaseIdx].expected_output
                                    : '[Awaiting Oracle Output]')}
                              </pre>
                            </div>

                            {/* Actual Output if executed against this case */}
                            {lastExecutedCaseIdx === selectedTestCaseIdx && executionResponse && (
                              <div className="ide-tc-col">
                                <div className="ide-tc-header-row-inline">
                                  <span className="ide-tc-lbl">Actual Output:</span>
                                  {executionResponse.exit_code === 0 && !executionResponse.error ? (
                                    visibleTestCases[selectedTestCaseIdx].expected_output &&
                                    executionResponse.output.trim().replace(/\s+/g, '') ===
                                    visibleTestCases[selectedTestCaseIdx].expected_output.trim().replace(/\s+/g, '') ? (
                                      <span style={{ fontSize: '11px', color: '#16a34a', fontWeight: 600 }}>MATCH</span>
                                    ) : (
                                      <span style={{ fontSize: '11px', color: '#f59e0b', fontWeight: 600 }}>MISMATCH</span>
                                    )
                                  ) : (
                                    <span style={{ fontSize: '11px', color: '#ef4444', fontWeight: 600 }}>ERROR</span>
                                  )}
                                </div>
                                <pre
                                  className={`ide-tc-code ${
                                    executionResponse.exit_code !== 0 || executionResponse.error ? 'stderr' : ''
                                  }`}
                                  style={{ minHeight: '80px' }}
                                >
                                  {executionResponse.error || executionResponse.output || '(no output)'}
                                </pre>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Custom Input Tab (DSA Mode) */}
              {activeTab === 'stdin' && workspaceMode === 'coding' && (
                <div className="ide-tab-pane">
                  <div className="ide-stdin-view">
                    <div className="ide-stdin-header">
                      <span className="ide-output-label">Standard Input (stdin):</span>
                      {problem.test_cases.length > 0 && (
                        <div className="ide-quick-input-pills">
                          <span className="ide-quick-lbl">Load sample:</span>
                          {problem.test_cases.slice(0, 3).map((tc, idx) => (
                            <button
                              key={idx}
                              type="button"
                              className="ide-btn-pill-small"
                              onClick={() => setCustomStdin(tc.input)}
                            >
                              Case {idx + 1}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                    <textarea
                      id="ide-custom-stdin"
                      className="ide-stdin-textarea"
                      value={customStdin}
                      onChange={(e) => setCustomStdin(e.target.value)}
                      placeholder="Type custom standard input or arguments to pass to your solution..."
                      rows={5}
                    />
                    <div className="ide-stdin-footer">
                      <button
                        type="button"
                        className="ide-btn ide-btn-run"
                        onClick={handleRunCode}
                        disabled={isRunning || isEvaluatingTests}
                      >
                        <Play size={12} />
                        <span>Run Code with this Input</span>
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Database Schema Tab (SQL Mode) */}
              {activeTab === 'schema' && workspaceMode === 'sql' && (
                <div className="ide-tab-pane">
                  {sqlFixture ? (
                    <div className="ide-fixture-view">
                      <div className="ide-fixture-header">
                        <strong>Active SQLite Fixture: <code>{sqlFixture.fixture_key}</code></strong>
                        <span>({sqlFixture.tables.length} Tables Available)</span>
                      </div>
                      <div className="ide-fixture-grid">
                        {sqlFixture.tables.map((tbl, idx) => (
                          <div key={idx} className="ide-table-card">
                            <span className="ide-table-name">Table: <code>{tbl.table_name || tbl.name}</code></span>
                            <ul className="ide-column-list">
                              {tbl.columns.map((col, cIdx) => (
                                <li key={cIdx}>
                                  <code>{col.name}</code> <span className="ide-col-type">({col.type})</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <p className="ide-empty-output">Loading database schema metadata...</p>
                  )}
                </div>
              )}

              {/* Test Evaluation Tab (SQL Mode) */}
              {activeTab === 'tests' && workspaceMode === 'sql' && (
                <div className="ide-tab-pane">
                  {sqlSubmission ? (
                    <div className="ide-test-results">
                      <div className="ide-test-summary">
                        <span className={`score-badge ${sqlSubmission.is_correct ? 'passed' : 'failed'}`}>
                          {sqlSubmission.is_correct ? 'CORRECT RESULT' : 'RESULT MISMATCH'}
                        </span>
                        <span>
                          {sqlSubmission.is_correct
                            ? 'Candidate query produces exactly the expected benchmark results.'
                            : 'Query results differed from expected solution rows or columns.'}
                        </span>
                      </div>

                      {sqlSubmission.optimization_feedback && (
                        <div className="ide-opt-feedback">
                          <Sparkles size={14} />
                          <div>
                            <strong>Optimization &amp; Style Feedback:</strong>
                            <p>{sqlSubmission.optimization_feedback}</p>
                          </div>
                        </div>
                      )}

                      {sqlSubmission.columns && sqlSubmission.columns.length > 0 && (
                        <div className="ide-table-container">
                          <table className="ide-sql-table">
                            <thead>
                              <tr>
                                {sqlSubmission.columns.map((c, i) => (
                                  <th key={i}>{c}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {sqlSubmission.actual_rows.map((row, rIdx) => (
                                <tr key={rIdx}>
                                  {row.map((val, cIdx) => (
                                    <td key={cIdx}>{val === null ? 'NULL' : String(val)}</td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="ide-output-placeholder">
                      <CheckCircle2 size={20} />
                      <p>Click &ldquo;Submit Query&rdquo; to test your SQL query against the benchmark solution.</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
