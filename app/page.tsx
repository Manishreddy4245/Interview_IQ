'use client'

import { useEffect, useRef, useState } from 'react'
import {
  BarChart3,
  BookOpenCheck,
  CalendarDays,
  Check,
  ChevronRight,
  CircleHelp,
  Clock3,
  FileText,
  LayoutDashboard,
  Menu,
  Mic,
  MicOff,
  MonitorPlay,
  MoreHorizontal,
  Play,
  Settings,
  ShieldCheck,
  Sparkles,
  Video,
  VideoOff,
  X,
} from 'lucide-react'

const navItems = [
  { label: 'Overview', icon: LayoutDashboard },
  { label: 'Start Interview', icon: MonitorPlay },
  { label: 'Interview History', icon: CalendarDays, disabled: true },
  { label: 'Communication Coach', icon: BookOpenCheck, disabled: true },
  { label: 'Skill Gap Analysis', icon: BarChart3, disabled: true },
  { label: 'Reports', icon: FileText, disabled: true },
]

function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark">IQ</span>
      <span>InterviewIQ</span>
    </div>
  )
}

function AppSidebar({ active, onNavigate }: { active: string; onNavigate: (label: string) => void }) {
  return (
    <aside className="sidebar">
      <Brand />
      <nav aria-label="Primary navigation" className="nav-list">
        <p className="eyebrow nav-label">Workspace</p>
        {navItems.map(({ label, icon: Icon, disabled }) => (
          <button
            key={label}
            className={`nav-item ${active === label ? 'is-active' : ''}`}
            disabled={disabled}
            onClick={() => onNavigate(label)}
            title={disabled ? 'Available after your first interview' : undefined}
          >
            <Icon aria-hidden="true" />
            <span>{label}</span>
            {disabled && <span className="nav-soon">Soon</span>}
          </button>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <button className="nav-item" disabled title="Settings are not available in this foundation">
          <Settings aria-hidden="true" />
          <span>Settings</span>
        </button>
        <div className="sidebar-note">
          <ShieldCheck aria-hidden="true" />
          <span>Your practice space is private.</span>
        </div>
      </div>
    </aside>
  )
}

function Topbar({ title, onMenu }: { title: string; onMenu: () => void }) {
  return (
    <header className="topbar">
      <button className="mobile-menu" onClick={onMenu} aria-label="Open navigation"><Menu /></button>
      <div>
        <p className="topbar-kicker">Candidate workspace</p>
        <h1>{title}</h1>
      </div>
      <div className="topbar-actions">
        <button className="icon-button" aria-label="Help"><CircleHelp /></button>
        <div className="avatar" aria-label="Candidate account">JD</div>
      </div>
    </header>
  )
}

function Overview({ onStart }: { onStart: () => void }) {
  return (
    <div className="page-content">
      <section className="welcome-row">
        <div>
          <p className="eyebrow">Monday, October 12, 2026</p>
          <h2>Prepare with intention.</h2>
          <p className="intro-copy">A focused space to sharpen your answers, build confidence, and understand how you communicate under pressure.</p>
        </div>
        <div className="welcome-actions">
          <button className="button button-primary" onClick={onStart}><Play data-icon="inline-start" /> Start an interview</button>
          <button className="button button-secondary" disabled>Review history <span className="coming-soon">Coming soon</span></button>
        </div>
      </section>

      <section className="insight-grid" aria-label="Interview evaluation areas">
        <article className="info-card">
          <span className="card-icon terracotta"><Sparkles /></span>
          <div><h3>Adaptive questions</h3><p>Practice with questions that respond to your experience and target role.</p></div>
        </article>
        <article className="info-card">
          <span className="card-icon olive"><Mic /></span>
          <div><h3>Communication clarity</h3><p>Build awareness of pacing, structure, and the story behind your answers.</p></div>
        </article>
        <article className="info-card">
          <span className="card-icon sand"><ShieldCheck /></span>
          <div><h3>Interview integrity</h3><p>Keep your practice environment focused, transparent, and private.</p></div>
        </article>
      </section>

      <section className="recent-section">
        <div className="section-heading"><div><p className="eyebrow">Your progress</p><h2>Recent sessions</h2></div><button className="text-button" disabled>View all <ChevronRight /></button></div>
        <div className="empty-state">
          <div className="empty-icon"><Clock3 /></div>
          <h3>No interviews yet</h3>
          <p>Your completed practice sessions will appear here. Start when you&apos;re ready.</p>
          <button className="button button-secondary" onClick={onStart}>Set up your first session <ChevronRight data-icon="inline-end" /></button>
        </div>
      </section>
    </div>
  )
}

function InterviewRoom({ onExit }: { onExit: () => void }) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [deviceState, setDeviceState] = useState<'idle' | 'ready' | 'denied'>('idle')
  const [recording, setRecording] = useState(false)
  const [elapsed, setElapsed] = useState(0)

  const requestDevices = async () => {
    if (!navigator.mediaDevices?.getUserMedia) { setDeviceState('denied'); return }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
      streamRef.current = stream
      if (videoRef.current) videoRef.current.srcObject = stream
      setDeviceState('ready')
    } catch { setDeviceState('denied') }
  }

  useEffect(() => {
    if (!recording) return
    const timer = window.setInterval(() => setElapsed((value) => value + 1), 1000)
    return () => window.clearInterval(timer)
  }, [recording])

  useEffect(() => () => streamRef.current?.getTracks().forEach((track) => track.stop()), [])

  const formatTime = `${String(Math.floor(elapsed / 60)).padStart(2, '0')}:${String(elapsed % 60).padStart(2, '0')}`

  return (
    <div className="room-page">
      <div className="room-header"><div><p className="eyebrow">Practice session</p><h2>Tell me about your experience.</h2></div><button className="icon-button" onClick={onExit} aria-label="Exit interview"><X /></button></div>
      <div className="room-layout">
        <section className="camera-panel">
          <div className="camera-frame">
            <video ref={videoRef} autoPlay muted playsInline aria-label="Camera preview" />
            {deviceState === 'idle' && <div className="camera-overlay"><Video aria-hidden="true" /><h3>Camera and microphone are off</h3><p>Allow access when you&apos;re ready to begin. Nothing is recorded until you start.</p><button className="button button-primary" onClick={requestDevices}>Enable camera &amp; mic</button></div>}
            {deviceState === 'denied' && <div className="camera-overlay"><VideoOff aria-hidden="true" /><h3>Device access unavailable</h3><p>Check your browser permissions and camera connection, then try again.</p><button className="button button-secondary" onClick={requestDevices}>Try again</button></div>}
            {deviceState === 'ready' && <div className="camera-status"><span className="status-dot" /> Camera ready</div>}
          </div>
          <div className="room-controls"><span className={`recording-time ${recording ? 'is-recording' : ''}`}>{recording && <span className="status-dot" />}{formatTime}</span><div className="control-group"><button className="round-control" aria-label={deviceState === 'ready' ? 'Microphone on' : 'Microphone unavailable'} disabled={deviceState !== 'ready'}><Mic /></button><button className="round-control" aria-label={deviceState === 'ready' ? 'Camera on' : 'Camera unavailable'} disabled={deviceState !== 'ready'}><Video /></button></div><button className="button button-primary" disabled={deviceState !== 'ready'} onClick={() => setRecording((value) => !value)}>{recording ? 'Pause practice' : 'Start practice'}</button></div>
        </section>
        <aside className="question-panel"><div className="question-progress"><span>Question 01</span><span>1 of 5</span></div><div className="progress-track"><span /></div><div className="question-copy"><p className="eyebrow">Behavioral</p><h3>Tell me about a time you had to solve a difficult problem with limited information.</h3><p>Take a moment to structure your answer. We&apos;ll review your response after the session.</p></div><div className="transcript-box"><div className="transcript-heading"><span>Live transcript</span><span className="transcript-muted">Waiting to begin</span></div><p>Your spoken answer will appear here once practice begins.</p></div><button className="exit-link" onClick={onExit}>Exit practice</button></aside>
      </div>
    </div>
  )
}

export default function Page() {
  const [active, setActive] = useState('Overview')
  const [mobileNav, setMobileNav] = useState(false)
  const isRoom = active === 'Start Interview'
  return <div className="app-shell"><AppSidebar active={active} onNavigate={setActive} /><div className={`mobile-nav ${mobileNav ? 'open' : ''}`}><AppSidebar active={active} onNavigate={(label) => { setActive(label); setMobileNav(false) }} /></div><div className="main-shell"><Topbar title={isRoom ? 'Start interview' : 'Overview'} onMenu={() => setMobileNav(true)} />{isRoom ? <InterviewRoom onExit={() => setActive('Overview')} /> : <Overview onStart={() => setActive('Start Interview')} />}</div></div>
}
