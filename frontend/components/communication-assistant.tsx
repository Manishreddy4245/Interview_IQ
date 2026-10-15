'use client'

import React, { useState, useEffect, useRef } from 'react'
import AnimatedMeshGradient from '@/components/animated-mesh-gradient'
import {
  BookOpenCheck,
  Sparkles,
  ShieldCheck,
  Send,
  Loader2,
  CheckCircle2,
  Lightbulb,
  Copy,
  Check,
  Layers,
  ArrowRight,
  MessageSquare,
  FileText,
  AlertCircle,
  Mic,
  MicOff,
  Square,
  RotateCcw,
  Volume2,
  Gauge,
  Clock,
  Hash,
  Award,
  ChevronRight,
  Info,
  HelpCircle,
  Play,
  TrendingUp,
} from 'lucide-react'
import {
  requestCommunicationCoach,
  transcribeAudio,
  type CommunicationCoachResponse,
  type CommunicationCoachRequest,
  type DimensionDetail,
  type TranscriptMetrics,
} from '@/lib/api'

interface CommunicationAssistantProps {
  initialContext?: string
  initialRole?: string
  sessionId?: string
}

type PracticeTask = 'question' | 'introduction' | 'improve_answer' | 'technical_concept'
type RecordingState = 'idle' | 'requesting_permission' | 'recording' | 'processing' | 'completed'

interface TaskTemplate {
  id: PracticeTask
  title: string
  description: string
  icon: React.ReactNode
  defaultPrompts: string[]
}

const PRACTICE_TASKS: TaskTemplate[] = [
  {
    id: 'question',
    title: 'Mock Interview Question',
    description: 'Practice structured delivery on behavioral and technical scenario questions.',
    icon: <MessageSquare style={{ width: '18px', height: '18px' }} />,
    defaultPrompts: [
      'Describe a complex technical challenge you faced and how you systematically diagnosed and resolved it.',
      'Tell me about a time you had an architectural disagreement with your team. How did you align on a solution?',
      'How do you balance technical debt reduction against aggressive feature delivery deadlines?',
    ],
  },
  {
    id: 'introduction',
    title: 'Professional Introduction',
    description: 'Deliver a compelling, concise 60–90 second overview of your background and impact.',
    icon: <Award style={{ width: '18px', height: '18px' }} />,
    defaultPrompts: [
      'Walk me through your background, key technical milestones, and the core focus of your engineering expertise.',
      'Give me your 60-second executive elevator pitch: who you are, what you specialize in, and what impact you deliver.',
    ],
  },
  {
    id: 'improve_answer',
    title: 'Improve an Existing Answer',
    description: 'Re-articulate a previous or draft answer to eliminate fluff and sharpen evidence.',
    icon: <RotateCcw style={{ width: '18px', height: '18px' }} />,
    defaultPrompts: [
      'I worked on a microservices migration where things were slow so we used Redis to cache data and it got much faster.',
      'Our team was missing sprint goals because requirements kept changing, so I talked to the product manager.',
    ],
  },
  {
    id: 'technical_concept',
    title: 'Explain a Technical Concept',
    description: 'Demonstrate clarity by breaking down a technical topic for interviewers or stakeholders.',
    icon: <Layers style={{ width: '18px', height: '18px' }} />,
    defaultPrompts: [
      'Explain database indexing and B-trees to a stakeholder with minimal database background.',
      'Explain the trade-offs between eventual consistency and strong consistency in distributed systems.',
      'Explain how HTTPS and TLS handshake protect data in transit from interception and tampering.',
    ],
  },
]

export default function CommunicationAssistant({
  initialContext = '',
  initialRole = 'Senior Full Stack Engineer',
  sessionId,
}: CommunicationAssistantProps) {
  // Task selection state
  const [selectedTask, setSelectedTask] = useState<PracticeTask>('question')
  const [taskPrompt, setTaskPrompt] = useState<string>(PRACTICE_TASKS[0].defaultPrompts[0])
  const [targetRole, setTargetRole] = useState(initialRole)

  // Speech & Transcript state
  const [recordingState, setRecordingState] = useState<RecordingState>('idle')
  const [recordingSeconds, setRecordingSeconds] = useState(0)
  const [transcript, setTranscript] = useState(initialContext)
  const [speechSupported, setSpeechSupported] = useState<boolean>(true)
  const [permissionError, setPermissionError] = useState<string | null>(null)

  // AI Review & UI state
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<CommunicationCoachResponse | null>(null)
  const [copied, setCopied] = useState(false)

  // Refs for audio & recognition
  const recognitionRef = useRef<any>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const timerIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const transcriptRef = useRef(transcript)
  transcriptRef.current = transcript

  // Check Web Speech API capability on mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const hasSpeech = Boolean(
        (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
      )
      setSpeechSupported(hasSpeech)
    }
  }, [])

  // Timer management
  useEffect(() => {
    if (recordingState === 'recording') {
      timerIntervalRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1)
      }, 1000)
    } else {
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current)
        timerIntervalRef.current = null
      }
    }

    return () => {
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current)
      }
    }
  }, [recordingState])

  // Cleanup media tracks and recognition on unmount
  useEffect(() => {
    return () => {
      stopMediaTracks()
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort()
        } catch {
          // ignore cleanup abort
        }
      }
    }
  }, [])

  const stopMediaTracks = () => {
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => {
        try {
          track.stop()
        } catch {
          // ignore
        }
      })
      mediaStreamRef.current = null
    }
  }

  // Switch task handler
  const handleTaskChange = (taskId: PracticeTask) => {
    setSelectedTask(taskId)
    const taskConfig = PRACTICE_TASKS.find((t) => t.id === taskId)
    if (taskConfig && taskConfig.defaultPrompts.length > 0) {
      setTaskPrompt(taskConfig.defaultPrompts[0])
    }
    setError(null)
  }

  // Start Speech Recording
  const handleStartRecording = async () => {
    setPermissionError(null)
    setError(null)
    setRecordingState('requesting_permission')

    try {
      // 1. Request microphone permission explicitly
      if (navigator?.mediaDevices?.getUserMedia) {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        mediaStreamRef.current = stream

        // Initialize MediaRecorder for reliable server-side Whisper transcription
        if (typeof MediaRecorder !== 'undefined') {
          audioChunksRef.current = []
          let options: MediaRecorderOptions | undefined = undefined
          if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
            options = { mimeType: 'audio/webm;codecs=opus' }
          } else if (MediaRecorder.isTypeSupported('audio/webm')) {
            options = { mimeType: 'audio/webm' }
          }
          const recorder = new MediaRecorder(stream, options)
          recorder.ondataavailable = (e) => {
            if (e.data && e.data.size > 0) {
              audioChunksRef.current.push(e.data)
            }
          }
          recorder.start(250)
          mediaRecorderRef.current = recorder
        }
      }

      // 2. Initialize Speech Recognition (for live interim preview where supported)
      const SpeechRecognitionClass =
        (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition

      if (!SpeechRecognitionClass) {
        setSpeechSupported(false)
        if (mediaRecorderRef.current) {
          setRecordingState('recording')
          setRecordingSeconds(0)
          return
        }
        stopMediaTracks()
        setRecordingState('idle')
        setPermissionError(
          'Microphone recording is unavailable in this browser environment. You can type or paste your spoken answer directly into the transcript box below.'
        )
        return
      }

      const recognition = new SpeechRecognitionClass()
      recognition.continuous = true
      recognition.interimResults = true
      recognition.lang = 'en-US'

      let localTranscriptBase = transcript.trim() ? transcript.trim() + ' ' : ''

      recognition.onresult = (event: any) => {
        let interimTranscript = ''
        let finalChunk = ''

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const item = event.results[i]
          if (item.isFinal) {
            finalChunk += item[0].transcript + ' '
          } else {
            interimTranscript += item[0].transcript
          }
        }

        if (finalChunk) {
          localTranscriptBase += finalChunk
        }

        const combined = (localTranscriptBase + interimTranscript).replace(/\s+/g, ' ').trim()
        setTranscript(combined)
      }

      recognition.onerror = (event: any) => {
        console.warn('Speech recognition notice:', event.error)
        if (event.error === 'not-allowed') {
          setPermissionError(
            'Microphone access was denied. Please allow microphone permissions in your browser or type your transcript directly below.'
          )
          handleStopRecording()
        } else if (event.error !== 'no-speech') {
          // Keep recording; user might be pausing
        }
      }

      recognition.onend = () => {
        // If still supposed to be recording, restart unless manually stopped
        if (recordingState === 'recording') {
          try {
            recognition.start()
          } catch {
            // ignore
          }
        }
      }

      recognitionRef.current = recognition
      recognition.start()
      setRecordingState('recording')
      setRecordingSeconds(0)
    } catch (err: any) {
      console.error('Microphone access failed:', err)
      stopMediaTracks()
      setRecordingState('idle')
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setPermissionError(
          'Microphone permission was blocked. Please enable microphone access in your browser or type your response in the box below.'
        )
      } else {
        setPermissionError(
          `Unable to access microphone: ${err.message || 'Unknown error'}. You can type your response directly below.`
        )
      }
    }
  }

  // Stop Speech Recording
  const handleStopRecording = () => {
    setRecordingState('processing')
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop()
      } catch {
        // ignore
      }
      recognitionRef.current = null
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      const recorder = mediaRecorderRef.current
      recorder.onstop = async () => {
        const chunks = audioChunksRef.current
        if (chunks.length > 0) {
          const audioBlob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' })
          if (audioBlob.size > 200) {
            try {
              const res = await transcribeAudio(audioBlob)
              if (res.transcript && res.transcript.trim()) {
                setTranscript((prev) => {
                  const cleanPrev = (prev || '').trim()
                  const cleanNew = res.transcript.trim()
                  if (!cleanPrev) return cleanNew
                  if (cleanPrev.toLowerCase().includes(cleanNew.toLowerCase())) return cleanPrev
                  if (cleanNew.toLowerCase().includes(cleanPrev.toLowerCase())) return cleanNew
                  return `${cleanPrev} ${cleanNew}`
                })
              }
            } catch (err: any) {
              console.warn('Communication coach audio transcription notice:', err)
            }
          }
        }
        setRecordingState('completed')
      }
      try {
        recorder.stop()
      } catch {}
      mediaRecorderRef.current = null
    } else {
      setTimeout(() => {
        setRecordingState('completed')
      }, 400)
    }

    stopMediaTracks()
  }

  // Cancel Speech Recording
  const handleCancelRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try {
        mediaRecorderRef.current.stop()
      } catch {}
      mediaRecorderRef.current = null
    }
    audioChunksRef.current = []

    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort()
      } catch {
        // ignore
      }
      recognitionRef.current = null
    }
    stopMediaTracks()
    setRecordingState('idle')
    setRecordingSeconds(0)
  }

  // Reset / Clear
  const handleResetPractice = () => {
    handleCancelRecording()
    setTranscript('')
    setResult(null)
    setError(null)
    setRecordingState('idle')
    setRecordingSeconds(0)
  }

  // Format MM:SS
  const formatTime = (secs: number) => {
    const mins = Math.floor(secs / 60)
    const rem = secs % 60
    return `${mins.toString().padStart(2, '0')}:${rem.toString().padStart(2, '0')}`
  }

  // Word count helper
  const wordCount = transcript.trim() ? transcript.trim().split(/\s+/).length : 0

  // Copy polished revision
  const handleCopyExample = () => {
    if (!result?.suggested_revision) return
    navigator.clipboard.writeText(result.suggested_revision)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Submit transcript for Groq AI review
  const handleSubmitReview = async () => {
    if (loading) return
    if (!transcript.trim() || wordCount < 4) {
      setError('Please provide a substantive spoken or typed response (at least 4 words).')
      return
    }

    try {
      setLoading(true)
      setError(null)

      const payload: CommunicationCoachRequest = {
        practice_task: selectedTask,
        task_prompt: taskPrompt.trim() || null,
        transcript: transcript.trim(),
        target_role: targetRole.trim() || null,
        session_id: sessionId || null,
        recording_duration_seconds: recordingSeconds > 0 ? recordingSeconds : null,
      }

      const response = await requestCommunicationCoach(payload)
      setResult(response)
    } catch (err: any) {
      console.error('Communication review failed:', err)
      let msg = err.message || 'Failed to generate communication review. Please check connection and try again.'
      if (
        msg.includes('429') ||
        msg.toLowerCase().includes('rate-limit') ||
        msg.toLowerCase().includes('rate limit') ||
        msg.toLowerCase().includes('quota')
      ) {
        msg = 'AI service is temporarily rate-limited. Please wait a few seconds before retrying. Your spoken transcript has not been lost.'
      }
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page-content" style={{ maxWidth: '1120px', margin: '0 auto', paddingBottom: '3.5rem' }}>
      {/* Hero Surface Banner */}
      <section className="hero-surface">
        <AnimatedMeshGradient />
        <div className="hero-content">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1.25rem' }}>
            <div>
              <div className="badge-row" style={{ marginBottom: '8px' }}>
                <span className="badge badge-accent">
                  <BookOpenCheck size={13} /> Module 07: Communication Coach
                </span>
                <span className="badge badge-neutral">
                  <Sparkles size={13} /> Isolated Speech Practice
                </span>
              </div>
              <h2>Speech Communication Coach</h2>
              <p className="intro-copy">
                Practice speaking mock interview answers, professional introductions, and technical concepts.
                Review live speech-to-text transcripts, filler words, and multi-dimensional AI communication feedback.
              </p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'flex-end' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '7px',
                  padding: '6px 14px',
                  background: '#ECFDF5',
                  borderRadius: '20px',
                  border: '1px solid #A7F3D0',
                  fontSize: '11px',
                  fontWeight: 650,
                  color: '#047857',
                  boxShadow: '0 1px 3px rgba(24, 39, 68, 0.04)',
                }}
              >
                <ShieldCheck style={{ width: '14px', height: '14px', color: '#047857' }} />
                <span>Isolated Practice • Zero Score Impact</span>
              </div>
              <span className="pill-badge neutral" style={{ fontSize: '10.5px' }}>
                Target: {targetRole}
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Main Practice Container */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
        {/* Step 1: Task Selection */}
        <div className="report-section-card" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="pill-badge terracotta" style={{ fontSize: '11px' }}>Step 1</span>
              <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: 'var(--foreground)' }}>
                Choose a Practice Task
              </h3>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <label style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600, textTransform: 'uppercase' }}>
                Target Role:
              </label>
              <input
                type="text"
                value={targetRole}
                onChange={(e) => setTargetRole(e.target.value)}
                placeholder="Target Role"
                style={{
                  padding: '5px 10px',
                  borderRadius: '8px',
                  border: '1px solid var(--border)',
                  background: '#fff',
                  fontSize: '12px',
                  color: 'var(--foreground)',
                  width: '200px',
                }}
              />
            </div>
          </div>

          {/* Task Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: '12px' }}>
            {PRACTICE_TASKS.map((task) => {
              const isSelected = selectedTask === task.id
              return (
                <button
                  key={task.id}
                  type="button"
                  onClick={() => handleTaskChange(task.id)}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'flex-start',
                    textAlign: 'left',
                    padding: '16px',
                    borderRadius: '12px',
                    border: isSelected ? '2px solid var(--accent)' : '1.5px solid var(--border)',
                    background: isSelected ? 'var(--accent-soft)' : '#fff',
                    boxShadow: isSelected ? '0 4px 16px rgba(79,70,181,0.14)' : 'var(--shadow-card)',
                    cursor: 'pointer',
                    transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
                    position: 'relative',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: isSelected ? 'var(--accent)' : 'var(--foreground)' }}>
                      <div
                        style={{
                          padding: '6px',
                          borderRadius: '8px',
                          background: isSelected ? '#E3E7FE' : '#F7F8FC',
                          color: 'var(--accent)',
                        }}
                      >
                        {task.icon}
                      </div>
                      <strong style={{ fontSize: '13px', fontWeight: 700 }}>{task.title}</strong>
                    </div>
                    {isSelected && (
                      <span style={{ fontSize: '10px', fontWeight: 700, color: 'var(--accent)', background: '#FFFFFF', padding: '2px 8px', borderRadius: '12px', border: '1px solid #D6DDF0' }}>
                        Selected
                      </span>
                    )}
                  </div>
                  <p style={{ margin: 0, fontSize: '11.5px', color: 'var(--muted)', lineHeight: 1.45 }}>
                    {task.description}
                  </p>
                </button>
              )
            })}
          </div>

          {/* Active Prompt Selector / Custom Prompt */}
          <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid var(--border)' }}>
            <label className="form-label" style={{ display: 'block', marginBottom: '8px' }}>
              Practice Prompt / Question:
            </label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '4px' }}>
                {PRACTICE_TASKS.find((t) => t.id === selectedTask)?.defaultPrompts.map((p, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setTaskPrompt(p)}
                    style={{
                      fontSize: '11px',
                      padding: '5px 12px',
                      borderRadius: '6px',
                      border: taskPrompt === p ? '1.5px solid var(--accent)' : '1px solid var(--border)',
                      background: taskPrompt === p ? 'var(--accent-soft)' : '#fff',
                      color: taskPrompt === p ? 'var(--accent)' : 'var(--muted)',
                      fontWeight: taskPrompt === p ? 700 : 500,
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      boxShadow: taskPrompt === p ? '0 2px 6px rgba(79, 70, 181, 0.12)' : 'none',
                    }}
                  >
                    Prompt {idx + 1}
                  </button>
                ))}
              </div>
              <textarea
                rows={2}
                value={taskPrompt}
                onChange={(e) => setTaskPrompt(e.target.value)}
                placeholder="Enter or customize the practice question/prompt..."
                className="form-textarea"
                style={{ fontSize: '12.5px', lineHeight: 1.45 }}
              />
            </div>
          </div>
        </div>

        {/* Step 2: Record Speech & Speech-to-Text */}
        <div className="report-section-card" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="pill-badge sand" style={{ fontSize: '11px' }}>Step 2</span>
              <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: 'var(--foreground)' }}>
                Record Speech or Review Transcript
              </h3>
            </div>

            {/* Privacy Guarantee Pill */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--muted)' }}>
              <ShieldCheck style={{ width: '14px', height: '14px', color: '#6e9a83' }} />
              <span>Client-side audio transcription • No audio uploaded</span>
            </div>
          </div>

          {/* Recording Controls Card */}
          <div
            style={{
              padding: '20px',
              borderRadius: '14px',
              background: recordingState === 'recording' ? '#fff5f8' : '#faf6fb',
              border: `1.5px solid ${recordingState === 'recording' ? '#f5cfdd' : 'var(--border)'}`,
              display: 'flex',
              flexDirection: 'column',
              gap: '14px',
              transition: 'all 0.25s ease',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
              {/* Record Button & State */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                {recordingState !== 'recording' ? (
                  <button
                    type="button"
                    onClick={handleStartRecording}
                    disabled={recordingState === 'requesting_permission'}
                    className="button button-primary"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '10px 20px',
                      borderRadius: '10px',
                      fontSize: '13px',
                      fontWeight: 700,
                    }}
                    aria-label="Start spoken recording"
                  >
                    {recordingState === 'requesting_permission' ? (
                      <>
                        <Loader2 className="animate-spin" style={{ width: '16px', height: '16px' }} />
                        <span>Requesting Microphone...</span>
                      </>
                    ) : (
                      <>
                        <Mic style={{ width: '16px', height: '16px' }} />
                        <span>Start Spoken Recording</span>
                      </>
                    )}
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleStopRecording}
                    className="button"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '10px 20px',
                      borderRadius: '10px',
                      fontSize: '13px',
                      fontWeight: 700,
                      background: '#b91c1c',
                      color: '#fff',
                      borderColor: '#991b1b',
                    }}
                    aria-label="Stop spoken recording"
                  >
                    <Square style={{ width: '15px', height: '15px', fill: 'currentColor' }} />
                    <span>Stop Recording</span>
                  </button>
                )}

                {/* Cancel / Reset Button */}
                {(recordingState === 'recording' || recordingSeconds > 0 || transcript.trim().length > 0) && (
                  <button
                    type="button"
                    onClick={handleResetPractice}
                    className="button button-secondary"
                    style={{ fontSize: '12px', padding: '8px 14px' }}
                    title="Clear transcript and reset practice"
                  >
                    <RotateCcw style={{ width: '13px', height: '13px' }} />
                    <span>Reset</span>
                  </button>
                )}
              </div>

              {/* Status and Timer */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                {recordingState === 'recording' && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span
                      style={{
                        display: 'inline-block',
                        width: '10px',
                        height: '10px',
                        borderRadius: '50%',
                        background: '#e11d48',
                        animation: 'pulse 1.2s infinite ease-in-out',
                      }}
                    />
                    <span style={{ fontSize: '12px', fontWeight: 700, color: '#e11d48' }}>
                      Listening &amp; Transcribing
                    </span>
                  </div>
                )}

                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    fontFamily: 'monospace',
                    fontSize: '13px',
                    fontWeight: 700,
                    color: recordingState === 'recording' ? 'var(--accent)' : 'var(--muted)',
                    background: '#fff',
                    padding: '6px 12px',
                    borderRadius: '8px',
                    border: '1px solid var(--border)',
                  }}
                >
                  <Clock style={{ width: '14px', height: '14px' }} />
                  <span>{formatTime(recordingSeconds)}</span>
                </div>

                <div
                  style={{
                    fontSize: '12px',
                    color: 'var(--muted)',
                    background: '#fff',
                    padding: '6px 12px',
                    borderRadius: '8px',
                    border: '1px solid var(--border)',
                  }}
                >
                  <strong style={{ color: 'var(--foreground)' }}>{wordCount}</strong> words
                </div>
              </div>
            </div>

            {/* Permission or Unsupported Notice */}
            {permissionError && (
              <div className="status-callout warning" style={{ margin: '6px 0 0' }}>
                <AlertCircle />
                <div>
                  <strong>Speech Recognition Notice</strong>
                  <p className="form-hint">{permissionError}</p>
                </div>
              </div>
            )}
          </div>

          {/* Editable Transcript Text Area */}
          <div style={{ marginTop: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <label className="form-label" style={{ margin: 0 }}>
                Spoken Transcript (Freely Editable Prior to Evaluation)
              </label>
              <span style={{ fontSize: '11px', color: 'var(--muted)' }}>
                Review, fix speech-to-text typos, or add technical specifics
              </span>
            </div>

            <textarea
              rows={6}
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              placeholder="Your spoken words will appear here in real-time as you speak... You can also type or paste an interview answer directly into this box."
              className="form-textarea"
              style={{
                fontFamily: 'Inter, sans-serif',
                fontSize: '13.5px',
                lineHeight: 1.6,
                background: '#fff',
                borderColor: recordingState === 'recording' ? 'var(--accent)' : 'var(--border)',
              }}
            />

            {error && (
              <div className="status-callout error" style={{ marginTop: '12px', marginBottom: '0' }}>
                <AlertCircle />
                <div>
                  <strong>Evaluation Notice</strong>
                  <p className="form-hint">{error}</p>
                </div>
              </div>
            )}

            {/* Submit Action Bar */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '14px', flexWrap: 'wrap', gap: '10px' }}>
              <div style={{ fontSize: '11.5px', color: 'var(--muted)' }}>
                {wordCount < 4 ? (
                  <span>Speak or type at least 4 words to unlock evaluation.</span>
                ) : (
                  <span>Ready for AI clarity, structure, and communication evaluation.</span>
                )}
              </div>

              <button
                type="button"
                onClick={handleSubmitReview}
                disabled={loading || wordCount < 4 || recordingState === 'recording'}
                className="button button-primary"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '10px 22px',
                  borderRadius: '10px',
                  fontSize: '13px',
                  fontWeight: 700,
                  opacity: wordCount < 4 || recordingState === 'recording' ? 0.6 : 1,
                  cursor: wordCount < 4 || recordingState === 'recording' ? 'not-allowed' : 'pointer',
                }}
              >
                {loading ? (
                  <>
                    <Loader2 className="animate-spin" style={{ width: '16px', height: '16px' }} />
                    <span>Analyzing Communication...</span>
                  </>
                ) : (
                  <>
                    <Sparkles style={{ width: '15px', height: '15px' }} />
                    <span>Submit for AI Communication Review</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Step 3: Review Results Dashboard */}
        {result && (
          <div className="report-hero-card" style={{ padding: '28px', marginTop: '0' }}>
            {/* Header: Overall Summary & Score */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px', borderBottom: '1px solid var(--border)', paddingBottom: '20px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px', flexWrap: 'wrap' }}>
                  <span className="pill-badge olive" style={{ fontSize: '10px' }}>
                    <CheckCircle2 style={{ width: '12px', height: '12px' }} />
                    Formative Evaluation Completed
                  </span>
                  {result.evaluation_mode === 'deterministic_fallback' ? (
                    <span className="pill-badge sand" style={{ fontSize: '10px' }} title="Evaluated via deterministic STAR rubrics while AI service is rate-limited">
                      Rule-Based Fallback (AI Rate-Limited)
                    </span>
                  ) : (
                    <span className="pill-badge terracotta" style={{ fontSize: '10px' }}>
                      Groq AI Powered
                    </span>
                  )}
                  <span style={{ fontSize: '11px', color: 'var(--muted)' }}>
                    Task: <strong>{PRACTICE_TASKS.find((t) => t.id === selectedTask)?.title}</strong>
                  </span>
                </div>
                <h3 style={{ margin: '0 0 8px 0', fontSize: '20px', fontWeight: 700, color: 'var(--foreground)' }}>
                  {result.evaluation_mode === 'deterministic_fallback'
                    ? 'Deterministic Communication Review'
                    : 'AI Communication Review'}
                </h3>
                <p style={{ margin: 0, fontSize: '13px', color: '#5f5363', lineHeight: 1.55, maxWidth: '720px' }}>
                  {result.summary || result.coaching_advice}
                </p>
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  onClick={handleResetPractice}
                  className="button button-secondary"
                  style={{ fontSize: '12px', padding: '8px 14px' }}
                >
                  <RotateCcw style={{ width: '13px', height: '13px' }} />
                  <span>Practice Another</span>
                </button>
              </div>
            </div>

            {/* Transcript-Derived Metrics Bar */}
            {result.transcript_metrics && (
              <div style={{ marginTop: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px' }}>
                  <Gauge style={{ width: '15px', height: '15px', color: 'var(--accent)' }} />
                  <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--foreground)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    Objective Transcript Metrics
                  </span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
                  {/* Words */}
                  <div style={{ padding: '12px 14px', background: '#fffaff', borderRadius: '10px', border: '1px solid var(--border)' }}>
                    <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>Total Words</div>
                    <div style={{ fontSize: '22px', fontWeight: 800, color: 'var(--accent)', marginTop: '2px' }}>
                      {result.transcript_metrics.word_count}
                    </div>
                  </div>

                  {/* Pace WPM */}
                  <div style={{ padding: '12px 14px', background: '#fffaff', borderRadius: '10px', border: '1px solid var(--border)' }}>
                    <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>Speaking Pace</div>
                    <div style={{ fontSize: '22px', fontWeight: 800, color: '#3b7556', marginTop: '2px' }}>
                      {result.transcript_metrics.words_per_minute ? `${result.transcript_metrics.words_per_minute} WPM` : 'N/A'}
                    </div>
                    <div style={{ fontSize: '10px', color: 'var(--muted)', marginTop: '2px' }}>
                      {result.transcript_metrics.speaking_duration_seconds
                        ? `${result.transcript_metrics.speaking_duration_seconds}s spoken duration`
                        : 'Duration not timed'}
                    </div>
                  </div>

                  {/* Filler Words */}
                  <div style={{ padding: '12px 14px', background: '#fffaff', borderRadius: '10px', border: '1px solid var(--border)' }}>
                    <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 600 }}>Identifiable Filler Words</div>
                    <div style={{ fontSize: '22px', fontWeight: 800, color: result.transcript_metrics.filler_word_count > 0 ? '#b45309' : '#3b7556', marginTop: '2px' }}>
                      {result.transcript_metrics.filler_word_count}
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '4px' }}>
                      {Object.keys(result.transcript_metrics.filler_words_detected || {}).length > 0 ? (
                        Object.entries(result.transcript_metrics.filler_words_detected).map(([w, cnt]) => (
                          <span
                            key={w}
                            style={{
                              fontSize: '9px',
                              padding: '2px 6px',
                              background: '#fff8ee',
                              border: '1px solid #f6deb8',
                              borderRadius: '4px',
                              color: '#8e5414',
                              fontWeight: 600,
                            }}
                          >
                            &quot;{w}&quot; × {cnt}
                          </span>
                        ))
                      ) : (
                        <span style={{ fontSize: '10px', color: '#2e7d56' }}>None detected</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* 5 Core Dimensions Feedback Grid */}
            {result.dimension_scores && (
              <div style={{ marginTop: '24px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '12px' }}>
                  <Award style={{ width: '15px', height: '15px', color: 'var(--accent)' }} />
                  <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--foreground)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    Evaluation Across 5 Core Dimensions
                  </span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '12px' }}>
                  {Object.entries(result.dimension_scores).map(([dimension, detail]) => {
                    const formattedTitle = dimension
                      .split('_')
                      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                      .join(' ')
                    const isGood = detail.score >= 7.5
                    return (
                      <div
                        key={dimension}
                        style={{
                          background: '#fffaff',
                          border: '1px solid var(--border)',
                          borderRadius: '12px',
                          padding: '14px 16px',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '6px',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontSize: '12.5px', fontWeight: 700, color: 'var(--foreground)' }}>
                            {formattedTitle}
                          </span>
                          <span
                            style={{
                              fontSize: '12px',
                              fontWeight: 800,
                              color: isGood ? '#059669' : '#DC2626',
                              background: isGood ? '#E6F9F0' : '#FEF2F2',
                              border: `1px solid ${isGood ? '#A7F3D0' : '#FECACA'}`,
                              padding: '2px 8px',
                              borderRadius: '12px',
                            }}
                          >
                            {detail.score}/10
                          </span>
                        </div>
                        <p style={{ margin: 0, fontSize: '11.5px', color: '#5f5363', lineHeight: 1.5 }}>
                          {detail.feedback}
                        </p>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* STAR Breakdown Grid */}
            {result.star_breakdown && (
              <div style={{ marginTop: '24px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '12px' }}>
                  <Layers style={{ width: '15px', height: '15px', color: 'var(--accent)' }} />
                  <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--foreground)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    STAR Framework Alignment
                  </span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px' }}>
                  <div style={{ padding: '14px', background: '#FFFFFF', borderRadius: '10px', border: '1.5px solid var(--border)', boxShadow: 'var(--shadow-card)' }}>
                    <div style={{ fontSize: '10.5px', fontWeight: 700, color: '#b45309', textTransform: 'uppercase', marginBottom: '4px' }}>
                      [S] Situation
                    </div>
                    <p style={{ margin: 0, fontSize: '12px', lineHeight: 1.45, color: 'var(--foreground)' }}>
                      {result.star_breakdown.situation}
                    </p>
                  </div>

                  <div style={{ padding: '14px', background: '#FFFFFF', borderRadius: '10px', border: '1.5px solid var(--border)', boxShadow: 'var(--shadow-card)' }}>
                    <div style={{ fontSize: '10.5px', fontWeight: 700, color: '#0284c7', textTransform: 'uppercase', marginBottom: '4px' }}>
                      [T] Task
                    </div>
                    <p style={{ margin: 0, fontSize: '12px', lineHeight: 1.45, color: 'var(--foreground)' }}>
                      {result.star_breakdown.task}
                    </p>
                  </div>

                  <div style={{ padding: '14px', background: '#FFFFFF', borderRadius: '10px', border: '1.5px solid var(--border)', boxShadow: 'var(--shadow-card)' }}>
                    <div style={{ fontSize: '10.5px', fontWeight: 700, color: '#16a34a', textTransform: 'uppercase', marginBottom: '4px' }}>
                      [A] Action
                    </div>
                    <p style={{ margin: 0, fontSize: '12px', lineHeight: 1.45, color: 'var(--foreground)' }}>
                      {result.star_breakdown.action}
                    </p>
                  </div>

                  <div style={{ padding: '14px', background: '#FFFFFF', borderRadius: '10px', border: '1.5px solid var(--border)', boxShadow: 'var(--shadow-card)' }}>
                    <div style={{ fontSize: '10.5px', fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase', marginBottom: '4px' }}>
                      [R] Result
                    </div>
                    <p style={{ margin: 0, fontSize: '12px', lineHeight: 1.45, color: 'var(--foreground)' }}>
                      {result.star_breakdown.result}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Strengths & Areas for Improvement Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginTop: '24px' }}>
              {/* Strengths */}
              <div style={{ padding: '16px 18px', background: '#f0fdf4', borderRadius: '12px', border: '1px solid #bbf7d0' }}>
                <h4 style={{ margin: '0 0 10px 0', fontSize: '12px', fontWeight: 700, color: '#166534', textTransform: 'uppercase', letterSpacing: '0.06em', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <CheckCircle2 style={{ width: '15px', height: '15px' }} />
                  Demonstrated Strengths
                </h4>
                <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '12px', color: '#14532d', lineHeight: 1.55 }}>
                  {(result.strengths || []).map((s, idx) => (
                    <li key={idx} style={{ marginBottom: '4px' }}>{s}</li>
                  ))}
                </ul>
              </div>

              {/* Areas for Improvement */}
              <div style={{ padding: '16px 18px', background: '#fff8ee', borderRadius: '12px', border: '1px solid #f6deb8' }}>
                <h4 style={{ margin: '0 0 10px 0', fontSize: '12px', fontWeight: 700, color: '#8e5414', textTransform: 'uppercase', letterSpacing: '0.06em', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <TrendingUp style={{ width: '15px', height: '15px' }} />
                  Areas to Tighten
                </h4>
                <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '12px', color: '#78350f', lineHeight: 1.55 }}>
                  {(result.areas_for_improvement || []).map((imp, idx) => (
                    <li key={idx} style={{ marginBottom: '4px' }}>{imp}</li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Suggested High-Impact Revision */}
            {result.suggested_revision && (
              <div style={{ marginTop: '24px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--foreground)', textTransform: 'uppercase', letterSpacing: '0.06em', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <FileText style={{ width: '15px', height: '15px', color: '#16a34a' }} />
                    Suggested High-Impact Response
                  </span>
                  <button
                    type="button"
                    onClick={handleCopyExample}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      background: 'none',
                      border: 'none',
                      color: copied ? '#2e7d56' : 'var(--muted)',
                      fontSize: '11px',
                      cursor: 'pointer',
                      padding: '3px 8px',
                      borderRadius: '4px',
                    }}
                  >
                    {copied ? <Check style={{ width: '13px', height: '13px' }} /> : <Copy style={{ width: '13px', height: '13px' }} />}
                    {copied ? 'Copied' : 'Copy Response'}
                  </button>
                </div>
                <div
                  style={{
                    padding: '16px 18px',
                    background: '#f6fdf9',
                    borderRadius: '12px',
                    border: '1px solid #bde6d3',
                    fontSize: '13px',
                    lineHeight: 1.6,
                    color: '#264e3a',
                    fontStyle: 'italic',
                  }}
                >
                  &ldquo;{result.suggested_revision}&rdquo;
                </div>
              </div>
            )}

            {/* Next Practice Drill Exercise */}
            {result.next_practice_exercise && (
              <div style={{ marginTop: '20px', padding: '16px 18px', background: 'var(--accent-soft)', borderRadius: '12px', border: '1px solid #D6DDF0' }}>
                <h4 style={{ margin: '0 0 6px 0', fontSize: '12px', fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.06em', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <ArrowRight style={{ width: '14px', height: '14px' }} />
                  Next Practice Drill
                </h4>
                <p style={{ margin: 0, fontSize: '12.5px', color: 'var(--foreground)', lineHeight: 1.5 }}>
                  {result.next_practice_exercise}
                </p>
              </div>
            )}

            {/* Acoustic Disclaimer Banner */}
            <div
              style={{
                marginTop: '24px',
                padding: '12px 16px',
                background: '#F8FAFD',
                borderRadius: '10px',
                border: '1px solid var(--border)',
                fontSize: '11px',
                color: 'var(--muted)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <ShieldCheck style={{ width: '16px', height: '16px', color: '#059669', flexShrink: 0 }} />
              <span>{result.disclaimer}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
