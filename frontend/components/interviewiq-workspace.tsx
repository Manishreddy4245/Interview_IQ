'use client'

import { useEffect, useRef, useState, useCallback, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import AnimatedMeshGradient from '@/components/animated-mesh-gradient'
import CandidateDecisionDashboard from '@/components/candidate-decision-dashboard'
import CommunicationAssistant from '@/components/communication-assistant'
import { MultimodalInterviewIDE } from '@/components/MultimodalInterviewIDE'
import { useAuth } from '@/lib/auth-context'
import {
  Activity,
  AlertCircle,
  BarChart3,
  BookOpenCheck,
  CalendarDays,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  CircleHelp,
  Clock3,
  Code2,
  FileCheck2,
  FileText,
  FileUp,
  LayoutDashboard,
  Loader2,
  LogOut,
  Menu,
  Mic,
  MonitorPlay,
  Play,
  RotateCcw,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Upload,
  Video,
  VideoOff,
  Volume2,
  VolumeX,
  MicOff,
  Square,
  X,
  Printer,
  Award,
  UserCheck,
  Copy,
  Check,
  Search,
  Database,
  Plus,
  Target,
  Edit3,
  BookOpen,
  Layers,
  CheckSquare,
} from 'lucide-react'
import {
  createInterviewSession,
  submitQuestionAnswer,
  evaluateAnswer,
  transcribeAudio,
  logIntegrityEvent,
  getIntegrityTimeline,
  submitIntegrityReview,
  submitCandidateExplanation,
  submitReviewerDecision,
  getGroqHealth,
  getDatabaseHealth,
  analyzeResume,
  startInterviewFromResume,
  generateFinalReport,
  getFinalReport,
  getAvailableReports,
  generateNextQuestion,
  submitAndAdaptQuestion,
  getSessionCompetencies,
  switchDemoRole,
  getAuthUser,
  getMyResume,
  updateResumeSkills,
  selectTargetRole,
  getSupportedRoles,
  type RoleDefinition,
  type InterviewSessionResponse,
  type AnswerEvaluationResponse,
  type SubmitAndAdaptResponse,
  type IntegrityEventRecord,
  type IntegrityEventType,
  type HumanReviewAuditEntry,
  type CandidateExplanationEntry,
  type ReviewerDecisionEntry,
  type GroqHealthResponse,
  type DatabaseHealthResponse,
  type ResumeAnalysisResult,
  type SkillEvidenceCategory,
  type InterviewReportResponse,
  type AvailableReportItem,
  type SessionCompetencyState,
  type NextQuestionResponse,
  type UserProfile,
  type PotentialCommunicationEventRecord,
} from '@/lib/api'
import {
  FaceVisibilityTracker,
  runPreflightFaceCheck,
  type FaceDetectionResult,
} from '@/lib/face-detector'
import {
  ExternalCommunicationDetector,
  type CommunicationIncidentResult,
} from '@/lib/communication-detector'

const navItems = [
  { label: 'Overview', icon: LayoutDashboard },
  { label: 'Coding Interview', icon: Code2, disabled: false },
  { label: 'Verbal Interview', icon: Mic, disabled: false },
  { label: 'Skill Gap Analysis', icon: BarChart3, disabled: false },
  { label: 'Interview History', icon: Clock3, disabled: false },
  { label: 'Reports', icon: FileText, disabled: false },
  { label: 'Candidate Intelligence', icon: Award, disabled: false },
  { label: 'Communication Coach', icon: BookOpenCheck, disabled: false },
]

function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark">IQ</span>
      <span>InterviewIQ</span>
    </div>
  )
}

function AppSidebar({
  active,
  onNavigate,
  currentRole,
  onLogout,
}: {
  active: string
  onNavigate: (label: string) => void
  currentRole: 'candidate' | 'reviewer' | 'admin'
  onLogout: () => void
}) {
  const filteredNavItems = navItems.filter((item) => {
    if (currentRole === 'candidate') {
      return item.label !== 'Candidate Intelligence'
    }
    if (currentRole === 'reviewer') {
      return (
        item.label === 'Candidate Intelligence' ||
        item.label === 'Reports' ||
        item.label === 'Interview History' ||
        item.label === 'Communication Coach' ||
        item.label === 'Overview'
      )
    }
    return true
  })

  return (
    <aside className="sidebar">
      <Brand />
      <nav aria-label="Primary navigation" className="nav-list">
        <p className="eyebrow nav-label">
          {currentRole === 'reviewer'
            ? 'Reviewer Portal'
            : currentRole === 'admin'
            ? 'Admin Workspace'
            : 'Student Workspace'}
        </p>
        {filteredNavItems.map(({ label, icon: Icon, disabled }) => (
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
        <button
          className="nav-item"
          onClick={onLogout}
          style={{ color: '#DC2626' }}
          title="Sign out of InterviewIQ"
        >
          <LogOut aria-hidden="true" style={{ width: '16px', height: '16px' }} />
          <span>Sign Out</span>
        </button>
        <div className="sidebar-note">
          <ShieldCheck aria-hidden="true" />
          <span>Session encrypted &amp; role-isolated.</span>
        </div>
      </div>
    </aside>
  )
}

function Topbar({
  title,
  onMenu,
  currentRole,
  userName,
  onSwitchRole,
  onLogout,
}: {
  title: string
  onMenu: () => void
  currentRole: 'candidate' | 'reviewer' | 'admin'
  userName: string
  onSwitchRole: (role: 'candidate' | 'reviewer' | 'admin') => void
  onLogout: () => void
}) {
  const roleBadgeBg = currentRole === 'reviewer' ? '#F0F9FF' : currentRole === 'admin' ? '#F5F3FF' : '#ECFDF5'
  const roleBadgeBorder = currentRole === 'reviewer' ? '#BAE6FD' : currentRole === 'admin' ? '#DDD6FE' : '#A7F3D0'
  const roleBadgeColor = currentRole === 'reviewer' ? '#0284c7' : currentRole === 'admin' ? '#7c3aed' : '#059669'

  const displayName = userName && userName !== 'Alex Mercer' ? userName : 'Student'

  return (
    <header className="topbar">
      <button className="mobile-menu" onClick={onMenu} aria-label="Open navigation"><Menu /></button>
      <div>
        <p className="topbar-kicker">
          {currentRole === 'reviewer'
            ? 'Reviewer & Hiring Manager workspace'
            : currentRole === 'admin'
            ? 'Administrative security workspace'
            : 'Student Job Preparation Platform'}
        </p>
        <h1>{title}</h1>
      </div>
      <div className="topbar-actions" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        {/* Role Badge */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: roleBadgeBg,
            border: `1px solid ${roleBadgeBorder}`,
            borderRadius: '20px',
            padding: '4px 10px',
          }}
          title={`Verified server-enforced role: ${currentRole.toUpperCase()}`}
        >
          <UserCheck style={{ width: '14px', height: '14px', color: roleBadgeColor }} />
          <span style={{ fontSize: '11px', color: roleBadgeColor, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            {currentRole === 'candidate' ? 'Student' : currentRole}
          </span>
        </div>

        <button
          onClick={onLogout}
          className="button button-secondary"
          style={{ minHeight: '32px', padding: '0 10px', fontSize: '12px', gap: '6px' }}
          title="Sign out of InterviewIQ"
        >
          <LogOut style={{ width: '13px', height: '13px' }} />
          <span>Sign Out</span>
        </button>

        <div
          className="avatar"
          aria-label={`${displayName} (${currentRole})`}
          title={`${displayName} • Verified Role: ${currentRole.toUpperCase()}`}
          style={{
            borderColor: roleBadgeColor,
          }}
        >
          {displayName
            .split(' ')
            .map((n) => n[0])
            .slice(0, 2)
            .join('')
            .toUpperCase() || 'ST'}
        </div>
      </div>
    </header>
  )
}

function Overview({
  userName = 'Student',
  currentRole = 'candidate',
  onStartTechnical,
  onStartVideo,
  onViewReport,
  onNavigate,
  activeSession,
  onResumeInterview,
}: {
  userName?: string
  currentRole?: 'candidate' | 'reviewer' | 'admin'
  onStartTechnical: () => void
  onStartVideo: () => void
  onViewReport?: (sessionId: string) => void
  onNavigate?: (label: string) => void
  activeSession?: InterviewSessionResponse | null
  onResumeInterview?: () => void
}) {
  const [sessions, setSessions] = useState<AvailableReportItem[]>([])
  const [latestResume, setLatestResume] = useState<ResumeAnalysisResult | null>(null)
  const [loadingData, setLoadingData] = useState(true)

  const displayName = userName && userName !== 'Alex Mercer' ? userName : 'Student'

  useEffect(() => {
    let isMounted = true
    async function loadData() {
      try {
        setLoadingData(true)
        const [reportsData, resumeData] = await Promise.allSettled([
          getAvailableReports(),
          getMyResume(),
        ])
        if (isMounted) {
          if (reportsData.status === 'fulfilled') {
            setSessions(reportsData.value || [])
          } else {
            setSessions([])
          }
          if (resumeData.status === 'fulfilled' && resumeData.value) {
            setLatestResume(resumeData.value)
          } else {
            setLatestResume(null)
          }
        }
      } catch {
        if (isMounted) {
          setSessions([])
          setLatestResume(null)
        }
      } finally {
        if (isMounted) {
          setLoadingData(false)
        }
      }
    }
    loadData()
    return () => {
      isMounted = false
    }
  }, [currentRole])

  const totalSessions = sessions.length
  const reportsReadyCount = sessions.filter(
    (s) => s.report_status === 'Report Ready' || s.overall_score != null,
  ).length
  const scoredSessions = sessions.filter(
    (s) => typeof s.overall_score === 'number' && !isNaN(s.overall_score),
  )
  const avgScore =
    scoredSessions.length > 0
      ? Math.round(
          scoredSessions.reduce((acc, s) => acc + (s.overall_score || 0), 0) /
            scoredSessions.length,
        )
      : null
  const latestTrack = latestResume?.target_role || sessions[0]?.role || 'Full Stack Engineer'

  const demonstratedCount = latestResume?.skill_evaluations?.filter(
    (e) => e.category === 'Demonstrated in resume',
  ).length || 0

  const validationNeededCount = latestResume?.skill_evaluations?.filter(
    (e) => e.requires_interview_validation,
  ).length || 0

  return (
    <div className="page-content">
      {/* Active Session Continuation Banner */}
      {activeSession && (
        <section
          style={{
            marginBottom: '20px',
            padding: '16px 20px',
            background: 'linear-gradient(135deg, #EEF2FF 0%, #E0E7FF 100%)',
            border: '1.5px solid #C7D2FE',
            borderRadius: '12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '12px',
          }}
          aria-label="Active interview in progress"
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div
              style={{
                width: '40px',
                height: '40px',
                borderRadius: '10px',
                background: '#4338A8',
                color: '#fff',
                display: 'grid',
                placeItems: 'center',
              }}
            >
              <Code2 size={20} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <strong style={{ fontSize: '14px', color: '#1E1B4B' }}>
                  Interview Session in Progress
                </strong>
                <span className="pill-badge olive" style={{ fontSize: '10px' }}>
                  Active
                </span>
              </div>
              <p style={{ margin: '2px 0 0', fontSize: '12px', color: '#4338CA' }}>
                Role: <strong>{activeSession.role}</strong> • {activeSession.questions.length} question(s) loaded
              </p>
            </div>
          </div>
          <button
            className="button button-primary"
            onClick={onResumeInterview || onStartTechnical}
            style={{ minHeight: '36px', fontSize: '12px' }}
          >
            <Play size={14} /> Resume Active Interview
          </button>
        </section>
      )}

      {/* Welcome Hero Section */}
      <section className="overview-welcome-card" aria-label="Welcome section">
        <AnimatedMeshGradient />
        <div className="overview-welcome-inner" style={{ position: 'relative', zIndex: 1 }}>
          <div>
            <div className="badge-row" style={{ marginBottom: '8px' }}>
              <span className="badge badge-accent">
                <LayoutDashboard size={13} /> Student Dashboard
              </span>
              <span className="badge badge-neutral">
                <Target size={13} /> Target: {latestTrack}
              </span>
            </div>
            <p className="welcome-tag">Welcome back,</p>
            <h2>{displayName}</h2>
            <p>
              Your personalized job-preparation platform. Master real interview competencies with resume-grounded skill extraction, role gap analysis, and sequential adaptive technical interviews.
            </p>
          </div>
          <div className="overview-actions">
            {latestResume ? (
              <button
                className="button button-primary"
                onClick={onStartTechnical}
                title="Launch sequential adaptive interview"
              >
                <Code2 data-icon="inline-start" /> Launch Adaptive Interview
              </button>
            ) : (
              <button
                className="button button-primary"
                onClick={() => onNavigate && onNavigate('Skill Gap Analysis')}
                title="Upload resume to begin skill gap analysis"
              >
                <FileUp data-icon="inline-start" /> Upload Resume
              </button>
            )}
            <button
              className="button button-secondary"
              onClick={() => onNavigate && onNavigate('Skill Gap Analysis')}
            >
              <BarChart3 data-icon="inline-start" /> Resume &amp; Skill Gaps
            </button>
          </div>
        </div>
      </section>

      {/* STATE 1: Brand New Student — Interactive 5-Step Workflow Roadmap */}
      {!latestResume && sessions.length === 0 && !loadingData && (
        <section
          className="dashboard-card"
          style={{ marginTop: '20px', padding: '24px' }}
          aria-label="Getting started roadmap"
        >
          <div style={{ marginBottom: '16px' }}>
            <span className="eyebrow" style={{ color: 'var(--accent)' }}>Getting Started</span>
            <h3 style={{ margin: '4px 0 0', fontSize: '18px', fontWeight: 700 }}>
              Your 5-Step Job Preparation Workflow
            </h3>
            <p style={{ margin: '6px 0 0', fontSize: '13px', color: 'var(--muted)' }}>
              Follow the sequential stages to identify your technical gaps and practice role-specific adaptive interview questions.
            </p>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
              gap: '14px',
              marginTop: '16px',
            }}
          >
            {[
              {
                step: '01',
                title: 'Upload Resume',
                desc: 'Parse technical skills, projects, education, and experience from your PDF.',
                active: true,
              },
              {
                step: '02',
                title: 'Target Role',
                desc: 'Select from standardized job roles with defined competency benchmarks.',
                active: false,
              },
              {
                step: '03',
                title: 'Initial Gap Analysis',
                desc: 'Compare resume evidence against required role competencies and proficiencies.',
                active: false,
              },
              {
                step: '04',
                title: 'Adaptive Interview',
                desc: 'Answer sequential questions adapting to your demonstrated strengths and weaknesses.',
                active: false,
              },
              {
                step: '05',
                title: 'Updated Plan',
                desc: 'Receive updated post-interview gap report, feedback, and study plan.',
                active: false,
              },
            ].map((item) => (
              <div
                key={item.step}
                style={{
                  padding: '16px',
                  borderRadius: '10px',
                  border: item.active ? '1.5px solid var(--accent)' : '1px solid var(--border)',
                  background: item.active ? 'var(--accent-soft)' : '#FAFCFF',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 800,
                      color: item.active ? 'var(--accent)' : 'var(--muted)',
                    }}
                  >
                    STEP {item.step}
                  </span>
                  {item.active && <span className="pill-badge olive" style={{ fontSize: '9px' }}>Current</span>}
                </div>
                <strong style={{ fontSize: '13px', color: 'var(--foreground)' }}>{item.title}</strong>
                <p style={{ margin: 0, fontSize: '11.5px', color: 'var(--muted)', lineHeight: 1.45 }}>
                  {item.desc}
                </p>
              </div>
            ))}
          </div>

          <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'flex-start' }}>
            <button
              className="button button-primary"
              onClick={() => onNavigate && onNavigate('Skill Gap Analysis')}
              style={{ minHeight: '38px', fontSize: '12px' }}
            >
              <FileUp size={14} /> Upload Your Resume to Begin
            </button>
          </div>
        </section>
      )}

      {/* STATE 2: Resume Uploaded & Processed — Profile Summary Card */}
      {latestResume && (
        <section
          className="dashboard-card"
          style={{ marginTop: '20px', padding: '20px' }}
          aria-label="Current preparation profile"
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <span className="eyebrow" style={{ color: '#2e7d56' }}>Resume Analyzed &amp; Connected</span>
                <span className="pill-badge olive" style={{ fontSize: '10px' }}>
                  {latestResume.saved_to_db ? 'Atlas Verified' : 'Session Stored'}
                </span>
              </div>
              <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 700 }}>
                Target Role: {latestResume.target_role} ({latestResume.experience_level})
              </h3>
              <p style={{ margin: '4px 0 0', fontSize: '12.5px', color: 'var(--muted)' }}>
                {latestResume.extracted_skills.length} skills extracted • {demonstratedCount} verified in resume • {validationNeededCount} needing interview validation
              </p>
            </div>

            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <button
                className="button button-secondary"
                onClick={() => onNavigate && onNavigate('Skill Gap Analysis')}
                style={{ minHeight: '34px', fontSize: '11.5px' }}
              >
                <Edit3 size={13} /> Review / Correct Skills
              </button>
              <button
                className="button button-primary"
                onClick={onStartTechnical}
                style={{ minHeight: '34px', fontSize: '11.5px' }}
              >
                <Code2 size={13} /> Start Adaptive Interview
              </button>
            </div>
          </div>

          {/* Top Extracted Skills Preview */}
          <div style={{ marginTop: '16px', paddingTop: '14px', borderTop: '1px solid var(--border)' }}>
            <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--muted)', display: 'block', marginBottom: '8px' }}>
              Extracted Resume Skills:
            </span>
            <div className="skill-chips">
              {latestResume.extracted_skills.slice(0, 10).map((skill, idx) => (
                <span key={idx} className="skill-chip">{skill}</span>
              ))}
              {latestResume.extracted_skills.length > 10 && (
                <span
                  className="skill-chip"
                  style={{ background: 'transparent', border: '1px dashed var(--border)', cursor: 'pointer' }}
                  onClick={() => onNavigate && onNavigate('Skill Gap Analysis')}
                >
                  +{latestResume.extracted_skills.length - 10} more
                </span>
              )}
            </div>
          </div>
        </section>
      )}

      {/* Two Practice Modes Portals: Coding Interview and Verbal Interview */}
      <section className="section-pair-grid" style={{ marginTop: '20px' }} aria-label="Assessment and Practice Sections">
        {/* Coding Interview Card */}
        <article className="section-portal-card" id="coding-interview-portal">
          <div>
            <div className="section-portal-top">
              <div className="section-portal-icon code">
                <Code2 />
              </div>
              <div>
                <span className="welcome-tag" style={{ fontSize: '9px', marginBottom: '2px', display: 'block' }}>
                  Monaco IDE &amp; Compiler Sandbox
                </span>
                <h3>Coding Interview</h3>
              </div>
            </div>
            <p>
              Interactive coding IDE with LeetCode-style algorithmic challenges, supported language selector (Python, JS, TS, C++, Java), automated test cases, and compiler execution. Strictly programming problems.
            </p>
            <div className="section-portal-features">
              <span className="feature-badge">LeetCode Problems</span>
              <span className="feature-badge">Monaco Code Editor</span>
              <span className="feature-badge">Run &amp; Submit Code</span>
              <span className="feature-badge">Test Case Evaluation</span>
            </div>
          </div>
          <button className="button button-primary" onClick={onStartTechnical} style={{ width: '100%' }}>
            <Code2 style={{ width: '14px', height: '14px' }} />
            Launch Coding Interview
          </button>
        </article>

        {/* Verbal Interview Card */}
        <article className="section-portal-card" id="verbal-interview-portal">
          <div>
            <div className="section-portal-top">
              <div className="section-portal-icon video" style={{ background: '#EEF2FF', color: 'var(--accent)' }}>
                <Mic />
              </div>
              <div>
                <span className="welcome-tag" style={{ fontSize: '9px', marginBottom: '2px', display: 'block' }}>
                  Spoken &amp; Natural Language
                </span>
                <h3>Verbal Interview</h3>
              </div>
            </div>
            <p>
              Verbal conceptual interview covering technical concepts, system architecture, resume projects, behavioral scenarios, and communication coaching. (Never requires writing or submitting source code).
            </p>
            <div className="section-portal-features">
              <span className="feature-badge">Speech-to-Text Transcription</span>
              <span className="feature-badge">Written Response Option</span>
              <span className="feature-badge">Conceptual Rubrics</span>
              <span className="feature-badge">Communication Coaching</span>
            </div>
          </div>
          <button className="button button-primary" onClick={onStartVideo} style={{ width: '100%' }}>
            <Mic style={{ width: '14px', height: '14px' }} />
            Enter Verbal Interview
          </button>
        </article>
      </section>

      {/* Lower Layout: Recent Activity on left, Real Quick Stats on right */}
      <section className="dashboard-columns" style={{ marginTop: '20px' }} aria-label="Dashboard metrics and activity">
        {/* Recent Activity */}
        <article className="dashboard-card">
          <div className="dashboard-card-header">
            <h3>
              <Clock3 style={{ width: '16px', height: '16px', color: 'var(--accent)' }} />
              Interview History
            </h3>
            {onNavigate && (
              <button
                className="header-action"
                onClick={() => onNavigate('Interview History')}
                disabled={sessions.length === 0}
                title={sessions.length === 0 ? 'No activity records available' : 'View all interview history'}
              >
                <span>View all history ({sessions.length})</span>
                <ChevronRight style={{ width: '14px', height: '14px' }} />
              </button>
            )}
          </div>

          {loadingData ? (
            <div className="activity-empty">
              <Loader2 className="animate-spin" style={{ width: '22px', height: '22px', color: 'var(--accent)' }} />
              <p style={{ margin: '8px 0 0', fontSize: '12px', color: 'var(--muted)' }}>Loading your session records...</p>
            </div>
          ) : sessions.length === 0 ? (
            <div className="activity-empty">
              <div className="activity-empty-icon">
                <Clock3 />
              </div>
              <h4>No interview sessions yet</h4>
              <p>Your completed interviews, scores, and improvement recommendations will appear here.</p>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'center' }}>
                <button
                  className="button button-primary"
                  onClick={onStartTechnical}
                  style={{ minHeight: '34px', fontSize: '11.5px', padding: '0 12px' }}
                >
                  <Code2 style={{ width: '13px', height: '13px' }} /> Start Technical Interview
                </button>
              </div>
            </div>
          ) : (
            <div className="activity-list">
              {sessions.slice(0, 5).map((session) => {
                const dateLabel = session.created_at
                  ? new Date(session.created_at).toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                    })
                  : 'Recent'
                const isReportReady = session.report_status === 'Report Ready'
                const isCompleted = session.status === 'completed'
                const hasScore = typeof session.overall_score === 'number'
                const isCoding = session.interview_mode === 'CODING'

                return (
                  <div
                    key={session.session_id}
                    className={`activity-row ${onViewReport ? 'is-clickable' : ''}`}
                    onClick={() => onViewReport && onViewReport(session.session_id)}
                    title={`Session: ${session.session_id} • Click to open details`}
                  >
                    <div className="activity-icon">
                      {isCoding ? <Code2 style={{ width: '16px', height: '16px' }} /> : <FileText style={{ width: '16px', height: '16px' }} />}
                    </div>
                    <div className="activity-info">
                      <div className="activity-title" style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                        <span>{session.role || 'Technical Interview'}</span>
                        {session.interview_mode && (
                          <span className="pill-badge neutral" style={{ fontSize: '10px' }}>
                            {isCoding ? 'Coding' : 'Verbal'}
                          </span>
                        )}
                        {session.is_persisted === false && (
                          <span className="pill-badge sand" style={{ fontSize: '10px' }} title="Running in temporary active memory">
                            Active Memory
                          </span>
                        )}
                      </div>
                      <div className="activity-meta">
                        <span>{dateLabel}</span>
                        <span>•</span>
                        <span>ID: {session.session_id.slice(0, 8)}...</span>
                        {hasScore && (
                          <>
                            <span>•</span>
                            <span style={{ fontWeight: 600, color: 'var(--accent)' }}>Score: {session.overall_score}/100</span>
                          </>
                        )}
                      </div>
                    </div>
                    <div>
                      {isReportReady ? (
                        <span className="status-badge ready">Report Ready</span>
                      ) : isCompleted ? (
                        <span className="status-badge completed">Completed</span>
                      ) : (
                        <span className="status-badge progress">In Progress</span>
                      )}
                    </div>
                    {onViewReport && (
                      <ChevronRight style={{ width: '15px', height: '15px', color: 'var(--muted)', flexShrink: 0 }} />
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </article>

        {/* Real Quick Stats */}
        <article className="dashboard-card">
          <div className="dashboard-card-header">
            <h3>
              <BarChart3 style={{ width: '16px', height: '16px', color: 'var(--accent)' }} />
              Performance Stats
            </h3>
          </div>

          <div className="quick-stats-grid">
            {/* Real KPI 1: Total Sessions */}
            <div className="stat-card">
              <div className="stat-card-header">
                <span className="stat-card-label">Total Sessions</span>
                <span className="stat-card-icon"><Activity style={{ width: '15px', height: '15px' }} /></span>
              </div>
              <div className="stat-card-val">{loadingData ? '—' : totalSessions}</div>
              <div className="stat-card-sub">Recorded interviews</div>
            </div>

            {/* Real KPI 2: Evaluated Reports */}
            <div className="stat-card">
              <div className="stat-card-header">
                <span className="stat-card-label">Reports Ready</span>
                <span className="stat-card-icon"><FileCheck2 style={{ width: '15px', height: '15px' }} /></span>
              </div>
              <div className="stat-card-val">{loadingData ? '—' : reportsReadyCount}</div>
              <div className="stat-card-sub">Evaluated dossiers</div>
            </div>

            {/* Real KPI 3: Average Score */}
            <div className="stat-card">
              <div className="stat-card-header">
                <span className="stat-card-label">Average Score</span>
                <span className="stat-card-icon"><Award style={{ width: '15px', height: '15px' }} /></span>
              </div>
              <div className="stat-card-val">
                {loadingData ? '—' : avgScore !== null ? `${avgScore}%` : '—'}
              </div>
              <div className="stat-card-sub">
                {avgScore !== null ? 'Evaluated answers' : 'No evaluations yet'}
              </div>
            </div>

            {/* Real KPI 4: Target Track */}
            <div className="stat-card">
              <div className="stat-card-header">
                <span className="stat-card-label">Target Role</span>
                <span className="stat-card-icon"><TrendingUp style={{ width: '15px', height: '15px' }} /></span>
              </div>
              <div className="stat-card-val" style={{ fontSize: '14px', lineHeight: 1.25, fontWeight: 700, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {latestTrack}
              </div>
              <div className="stat-card-sub">Preparation focus</div>
            </div>
          </div>
        </article>
      </section>
    </div>
  )
}

function InterviewSetup({
  onSessionReady,
  onCancel,
  targetMode = 'CODING',
  initialStream,
}: {
  onSessionReady: (session: InterviewSessionResponse, stream?: MediaStream | null) => void
  onCancel: () => void
  targetMode?: 'CODING' | 'VERBAL'
  initialStream?: MediaStream | null
}) {
  const isCoding = targetMode === 'CODING'
  const isVideo = targetMode === 'CODING' || targetMode === 'VERBAL' || !isCoding

  const [role, setRole] = useState('Full Stack Developer')
  const [experienceLevel, setExperienceLevel] = useState('Mid-Level')
  const [difficulty, setDifficulty] = useState('Medium')
  const [focusAreas, setFocusAreas] = useState(
    isCoding
      ? 'Data Structures & Algorithms, Arrays, Hash Maps, Dynamic Programming'
      : 'Technical Architecture, System Design, Communication, Behavioral Scenarios'
  )
  const [questionCount, setQuestionCount] = useState(5)
  const [durationMinutes, setDurationMinutes] = useState(30)
  const [jobDescription, setJobDescription] = useState('')
  const [isAdaptive, setIsAdaptive] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [groqStatus, setGroqStatus] = useState<GroqHealthResponse | null>(null)
  const [dbStatus, setDbStatus] = useState<DatabaseHealthResponse | null>(null)

  // Mandatory Video Proctoring Preflight State (For Proctored Coding & Verbal Interviews)
  const [preflightStream, setPreflightStream] = useState<MediaStream | null>(initialStream || null)
  const [cameraState, setCameraState] = useState<'idle' | 'requesting' | 'ready' | 'denied' | 'error'>('idle')
  const [cameraErrorMessage, setCameraErrorMessage] = useState<string | null>(null)
  const [faceCheckStatus, setFaceCheckStatus] = useState<{
    verified: boolean
    message: string
    checking: boolean
    faceCount: number
    durationMs: number
  }>({
    verified: false,
    message: isVideo ? 'Camera access and candidate face visibility check required before starting.' : '',
    checking: false,
    faceCount: 0,
    durationMs: 0,
  })
  const preflightVideoRef = useRef<HTMLVideoElement | null>(null)
  const hasTransferredStreamRef = useRef(false)

  const setPreflightVideoRef = useCallback((node: HTMLVideoElement | null) => {
    preflightVideoRef.current = node
    if (node && preflightStream) {
      node.muted = true
      node.playsInline = true
      node.autoplay = true
      if (node.srcObject !== preflightStream) {
        node.srcObject = preflightStream
      }
      node.play().catch(() => {})
    }
  }, [preflightStream])

  useEffect(() => {
    let isMounted = true
    getGroqHealth()
      .then((data) => { if (isMounted) setGroqStatus(data) })
      .catch(() => { if (isMounted) setGroqStatus({ configured: false, status: 'unreachable', detail: 'Backend health check unreachable' }) })

    getDatabaseHealth()
      .then((data) => { if (isMounted) setDbStatus(data) })
      .catch(() => { if (isMounted) setDbStatus({ status: 'unreachable', detail: 'Database health check unreachable', database: 'interviewiq' }) })

    return () => {
      isMounted = false
    }
  }, [])

  // If a live stream is provided from parent, initialize with it immediately
  useEffect(() => {
    if (!initialStream) return
    const vTracks = initialStream.getVideoTracks()
    const isLive = vTracks.length > 0 && vTracks.some((t) => t.readyState === 'live' && t.enabled)
    if (!isLive) return

    setPreflightStream(initialStream)
    setCameraState('ready')
    if (preflightVideoRef.current) {
      preflightVideoRef.current.muted = true
      preflightVideoRef.current.playsInline = true
      preflightVideoRef.current.autoplay = true
      preflightVideoRef.current.srcObject = initialStream
      preflightVideoRef.current.play().then(() => {
        if (preflightVideoRef.current) {
          performFaceCheck(preflightVideoRef.current)
        }
      }).catch(() => {})
    }
  }, [initialStream])

  // Clean up preflight stream if unmounted without starting session (e.g. user cancelled or exited)
  useEffect(() => {
    return () => {
      if (preflightStream && !hasTransferredStreamRef.current) {
        preflightStream.getTracks().forEach((t) => t.stop())
      }
    }
  }, [preflightStream])

  const performFaceCheck = async (videoEl: HTMLVideoElement) => {
    setFaceCheckStatus({
      verified: false,
      message: 'Analyzing camera stream — checking for candidate face visibility...',
      checking: true,
      faceCount: 0,
      durationMs: 0,
    })

    const checkResult = await runPreflightFaceCheck(videoEl, 1500, 300)

    if (checkResult.ready || checkResult.status === 'verified') {
      setFaceCheckStatus({
        verified: true,
        message: 'Candidate visibility verified: 1 face confirmed consistently. Camera ready.',
        checking: false,
        faceCount: 1,
        durationMs: checkResult.consecutiveDurationMs,
      })
    } else if (checkResult.status === 'initializing') {
      setFaceCheckStatus({
        verified: false,
        message: 'Camera video stream is still initializing frames. Please wait a moment and re-verify.',
        checking: false,
        faceCount: 0,
        durationMs: 0,
      })
    } else if (checkResult.status === 'multiple_faces' || checkResult.currentFaceCount > 1) {
      setFaceCheckStatus({
        verified: false,
        message: 'Multiple people detected — only the candidate should be visible during this interview.',
        checking: false,
        faceCount: checkResult.currentFaceCount,
        durationMs: 0,
      })
    } else if (checkResult.status === 'error' || checkResult.error) {
      setFaceCheckStatus({
        verified: false,
        message: `Detection limitation: ${checkResult.error || 'Face detection engine unavailable.'}`,
        checking: false,
        faceCount: 0,
        durationMs: 0,
      })
    } else {
      // Confirmed genuine failure: video frames ready with 0 detected faces
      setFaceCheckStatus({
        verified: false,
        message: 'Candidate not visible — please position your face directly in the camera frame and re-run check.',
        checking: false,
        faceCount: 0,
        durationMs: 0,
      })
    }
  }

  const requestPreflightCamera = async () => {
    if (preflightStream && preflightVideoRef.current && cameraState === 'ready') {
      await performFaceCheck(preflightVideoRef.current)
      return
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraState('denied')
      setCameraErrorMessage('Your browser does not support camera media devices (navigator.mediaDevices.getUserMedia unavailable).')
      setFaceCheckStatus({
        verified: false,
        message: 'Camera device unavailable. A working video camera is mandatory for video interviews.',
        checking: false,
        faceCount: 0,
        durationMs: 0,
      })
      return
    }

    setCameraState('requesting')
    setCameraErrorMessage(null)
    setFaceCheckStatus({
      verified: false,
      message: 'Requesting camera & microphone access from browser...',
      checking: true,
      faceCount: 0,
      durationMs: 0,
    })

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
        audio: true,
      })
      setPreflightStream(stream)
      if (preflightVideoRef.current) {
        preflightVideoRef.current.srcObject = stream
        try {
          await preflightVideoRef.current.play()
        } catch {}
      }
      setCameraState('ready')

      // Monitor video track life
      stream.getVideoTracks().forEach((track) => {
        track.onended = () => {
          setCameraState('error')
          setCameraErrorMessage('Camera feed disconnected or video track ended.')
          setFaceCheckStatus({
            verified: false,
            message: 'Camera stream disconnected. Please restore camera stream to proceed.',
            checking: false,
            faceCount: 0,
            durationMs: 0,
          })
        }
      })

      // Run real preflight face verification (require 1 face consistently)
      if (preflightVideoRef.current) {
        await performFaceCheck(preflightVideoRef.current)
      }
    } catch (err: unknown) {
      setCameraState('denied')
      const msg = err instanceof Error ? err.message : 'Permission denied or camera device busy.'
      setCameraErrorMessage(`Camera permission was denied or device is unavailable: ${msg}`)
      setFaceCheckStatus({
        verified: false,
        message: 'Camera access denied. Video proctoring is mandatory for this interview.',
        checking: false,
        faceCount: 0,
        durationMs: 0,
      })
    }
  }

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!role.trim()) {
      setError('Target job role is required.')
      return
    }
    if (!focusAreas.trim()) {
      setError('Focus areas and assessed skills are required.')
      return
    }

    // Gating for proctored interviews: Mandatory camera and candidate face verification
    if (isVideo) {
      if (cameraState !== 'ready' || !faceCheckStatus.verified || !preflightStream) {
        setError('Camera permission and candidate face verification are mandatory for this interview. Please enable your camera and complete the visibility check before starting.')
        return
      }
    }

    setLoading(true)
    setError(null)

    try {
      const session = await createInterviewSession({
        role: role.trim(),
        experience_level: experienceLevel,
        difficulty: difficulty,
        focus_areas: focusAreas.trim(),
        question_count: questionCount,
        adaptive: isAdaptive,
        duration_minutes: durationMinutes,
        job_description: jobDescription.trim() || undefined,
        interview_mode: targetMode,
      })
      hasTransferredStreamRef.current = true
      onSessionReady(session, preflightStream)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to generate interview questions'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="room-page">
      <section className="room-hero">
        <AnimatedMeshGradient />
        <div className="room-header">
          <div>
            <div className="badge-row" style={{ marginBottom: '8px' }}>
              <span className="badge badge-accent">
                {isCoding ? <Code2 size={13} /> : <Mic size={13} />}
                {isCoding ? 'Coding Interview Setup' : 'Verbal Interview Setup'}
              </span>
              <span className="badge badge-neutral">
                <Sparkles size={13} /> AI Adaptive Questioning
              </span>
            </div>
            <h2>{isCoding ? 'Configure your coding interview session.' : 'Configure your verbal interview session.'}</h2>
            <p className="intro-copy" style={{ marginTop: '8px' }}>
              {isCoding
                ? 'Generate algorithmic programming challenges tailored to your target role and difficulty. Solve and execute code directly in the IDE.'
                : 'Generate natural-language interview questions assessing conceptual depth, system architecture, and communication skills.'}
            </p>
          </div>
          <button className="icon-button" onClick={onCancel} aria-label="Exit setup"><X /></button>
        </div>
      </section>

      <div className="form-card">
        {groqStatus && !groqStatus.configured && (
          <div className="status-callout warning" role="alert">
            <AlertCircle />
            <div>
              <strong>Groq API Key Unconfigured</strong>
              <p className="form-hint">{groqStatus.detail} Set <code>GROQ_API_KEY</code> in <code>backend/.env</code> to generate adaptive AI questions and evaluations.</p>
            </div>
          </div>
        )}

        {dbStatus && dbStatus.status !== 'connected' && (
          <div className="status-callout info">
            <AlertCircle />
            <div>
              <strong>
                {dbStatus.status === 'unconfigured'
                  ? 'Active Memory Mode (MongoDB Atlas Unconfigured)'
                  : 'Active Memory Mode (MongoDB Atlas Unreachable)'}
              </strong>
              <p className="form-hint">
                {dbStatus.status === 'unconfigured'
                  ? <>Sessions will run live in backend active memory. Provide <code>MONGODB_URI</code> to enable permanent cloud persistence.</>
                  : <>{dbStatus.detail || 'MongoDB Atlas connection failed'}. Sessions will temporarily run in backend active memory.</>}
              </p>
            </div>
          </div>
        )}

        {error && (
          <div className="status-callout error" role="alert">
            <AlertCircle />
            <div>
              <strong>Generation Error</strong>
              <p className="form-hint">{error}</p>
            </div>
          </div>
        )}

        <form onSubmit={handleGenerate} className="form-grid">
          <div className="form-field">
            <label htmlFor="role-input" className="form-label">Target Job Role</label>
            <input
              id="role-input"
              className="form-input"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              placeholder="e.g. Senior Frontend Engineer"
              disabled={loading}
              required
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div className="form-field">
              <label htmlFor="exp-select" className="form-label">Experience Level</label>
              <select
                id="exp-select"
                className="form-select"
                value={experienceLevel}
                onChange={(e) => setExperienceLevel(e.target.value)}
                disabled={loading}
              >
                <option value="Entry-Level">Entry-Level</option>
                <option value="Mid-Level">Mid-Level</option>
                <option value="Senior">Senior</option>
                <option value="Lead">Lead / Staff</option>
              </select>
            </div>

            <div className="form-field">
              <label htmlFor="diff-select" className="form-label">Difficulty</label>
              <select
                id="diff-select"
                className="form-select"
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value)}
                disabled={loading}
              >
                <option value="Easy">Easy</option>
                <option value="Medium">Medium</option>
                <option value="Hard">Hard</option>
              </select>
            </div>
          </div>

          <div className="form-field">
            <label htmlFor="focus-input" className="form-label">Focus Areas &amp; Skills</label>
            <input
              id="focus-input"
              className="form-input"
              value={focusAreas}
              onChange={(e) => setFocusAreas(e.target.value)}
              placeholder="e.g. React, Algorithms, Architecture, Communication"
              disabled={loading}
              required
            />
            <p className="form-hint">Enter key technical or behavioral competencies to guide question synthesis.</p>
          </div>

          <div className="form-row">
            <div className="form-field">
              <label htmlFor="duration-select" className="form-label">Interview Duration</label>
              <select
                id="duration-select"
                className="form-select"
                value={durationMinutes}
                onChange={(e) => setDurationMinutes(Number(e.target.value))}
                disabled={loading}
              >
                <option value={15}>15 Minutes (Brief Assessment)</option>
                <option value={30}>30 Minutes (Standard Technical)</option>
                <option value={45}>45 Minutes (Extended In-Depth)</option>
                <option value={60}>60 Minutes (Full Loop Interview)</option>
              </select>
              <p className="form-hint">Drives server-side time-aware question pacing and depth bands.</p>
            </div>

            <div className="form-field">
              <label htmlFor="count-select" className="form-label">Number of Questions</label>
              <select
                id="count-select"
                className="form-select"
                value={questionCount}
                onChange={(e) => setQuestionCount(Number(e.target.value))}
                disabled={loading}
              >
                <option value={3}>3 Questions (Fast Practice)</option>
                <option value={4}>4 Questions (Standard)</option>
                <option value={5}>5 Questions (Comprehensive)</option>
              </select>
            </div>
          </div>

          <div className="form-field">
            <label htmlFor="jd-input" className="form-label">Job Description / Requirements (Optional)</label>
            <textarea
              id="jd-input"
              className="form-input"
              rows={2}
              value={jobDescription}
              onChange={(e) => setJobDescription(e.target.value)}
              placeholder="Paste key role requirements or job description excerpt..."
              disabled={loading}
              style={{ minHeight: '60px', resize: 'vertical' }}
            />
            <p className="form-hint">Grounds follow-up questions in genuine company requirements without hallucination.</p>
          </div>

          <div className="form-field" style={{ background: 'var(--accent-soft)', border: '1px solid #D6DDF0', borderRadius: '10px', padding: '12px 14px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer', margin: 0 }}>
              <input
                type="checkbox"
                checked={isAdaptive}
                onChange={(e) => setIsAdaptive(e.target.checked)}
                disabled={loading}
                style={{ width: '16px', height: '16px', cursor: 'pointer', accentColor: 'var(--accent)' }}
              />
              <span style={{ fontSize: '12px', fontWeight: 650, color: 'var(--foreground)' }}>
                Enable Dynamic Interview Adaptation
              </span>
            </label>
            <p className="form-hint" style={{ marginTop: '4px', marginBottom: 0 }}>
              Sequentially selects next questions based on evaluated answer evidence and dynamically adapts difficulty.
            </p>
          </div>

          {isVideo && (
            <div className="report-section-card" style={{ padding: '16px', background: '#F8FAFC', border: '1.5px solid var(--border)', borderRadius: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Video style={{ width: '14px', height: '14px', color: 'var(--accent)' }} />
                  Mandatory Video Proctoring &amp; Face Verification
                </span>
                <span className={`pill-badge ${faceCheckStatus.verified ? 'olive' : cameraState === 'denied' || cameraState === 'error' ? 'terracotta' : 'sand'}`} style={{ fontSize: '10px' }}>
                  {faceCheckStatus.verified ? '✓ Verified Ready' : cameraState === 'ready' ? 'Face Check Pending' : 'Camera Required'}
                </span>
              </div>
              <p className="form-hint" style={{ marginBottom: '12px' }}>
                Video proctoring is mandatory for this interview. Explicit camera permission and confirmed candidate visibility are required before the interview can start. Video is processed locally in your browser for session integrity and never uploaded.
              </p>

              <div style={{ position: 'relative', width: '100%', height: cameraState === 'ready' ? '200px' : '90px', background: '#1D2742', borderRadius: '10px', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <video
                  ref={setPreflightVideoRef}
                  autoPlay
                  muted
                  playsInline
                  aria-label="Preflight camera preview"
                  style={{ width: '100%', height: '100%', objectFit: 'cover', transform: 'scaleX(-1)', display: cameraState === 'ready' ? 'block' : 'none' }}
                />
                {cameraState !== 'ready' && (
                  <div style={{ textAlign: 'center', color: '#94A3B8', padding: '16px' }}>
                    {cameraState === 'denied' || cameraState === 'error' ? (
                      <div style={{ color: '#F87171' }}>
                        <VideoOff style={{ width: '24px', height: '24px', margin: '0 auto 6px' }} />
                        <p style={{ margin: 0, fontSize: '12px', fontWeight: 600 }}>Camera access unavailable</p>
                      </div>
                    ) : (
                      <div>
                        <Video style={{ width: '24px', height: '24px', margin: '0 auto 6px', color: '#818CF8' }} />
                        <p style={{ margin: 0, fontSize: '12px' }}>Camera in standby</p>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {cameraErrorMessage && (
                <div className="status-callout error" style={{ marginTop: '10px', marginBottom: 0 }} role="alert">
                  <AlertCircle style={{ width: '14px', height: '14px', flexShrink: 0 }} />
                  <p style={{ margin: 0, fontSize: '11.5px' }}>{cameraErrorMessage}</p>
                </div>
              )}

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px', marginTop: '12px' }}>
                <div style={{ fontSize: '11.5px', color: faceCheckStatus.verified ? '#166534' : 'var(--muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  {faceCheckStatus.checking ? (
                    <Loader2 className="animate-spin" style={{ width: '14px', height: '14px', color: 'var(--accent)' }} />
                  ) : faceCheckStatus.verified ? (
                    <CheckCircle2 style={{ width: '14px', height: '14px', color: '#166534' }} />
                  ) : (
                    <AlertCircle style={{ width: '14px', height: '14px', color: '#D97706' }} />
                  )}
                  <span>{faceCheckStatus.message}</span>
                </div>

                {cameraState !== 'ready' ? (
                  <button
                    type="button"
                    className="button button-primary"
                    style={{ fontSize: '11px', padding: '6px 14px', minHeight: '32px' }}
                    onClick={requestPreflightCamera}
                    disabled={cameraState === 'requesting'}
                  >
                    {cameraState === 'requesting' ? (
                      <>
                        <Loader2 className="animate-spin" style={{ width: '13px', height: '13px', marginRight: '6px' }} />
                        Accessing Camera...
                      </>
                    ) : (
                      <>
                        <Video style={{ width: '13px', height: '13px', marginRight: '6px' }} />
                        {cameraState === 'denied' || cameraState === 'error' ? 'Retry Camera Access' : 'Enable Camera & Verify Face'}
                      </>
                    )}
                  </button>
                ) : !faceCheckStatus.verified ? (
                  <button
                    type="button"
                    className="button button-secondary"
                    style={{ fontSize: '11px', padding: '6px 14px', minHeight: '32px' }}
                    onClick={requestPreflightCamera}
                    disabled={faceCheckStatus.checking}
                  >
                    <RotateCcw style={{ width: '12px', height: '12px', marginRight: '4px' }} />
                    Re-verify Candidate Face
                  </button>
                ) : null}
              </div>
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '14px' }}>
            <button type="button" className="button button-secondary" onClick={onCancel} disabled={loading}>
              Cancel
            </button>
            <button
              type="submit"
              className="button button-primary"
              disabled={loading || (isVideo && (!faceCheckStatus.verified || cameraState !== 'ready'))}
              title={isVideo && !faceCheckStatus.verified ? "Camera and candidate face verification required before starting" : undefined}
            >
              {loading ? (
                <>
                  <Loader2 className="animate-spin" style={{ width: '15px', height: '15px' }} />
                  {isAdaptive ? 'Initializing Adaptive Interview...' : 'Generating Questions...'}
                </>
              ) : (
                <>
                  <Sparkles style={{ width: '15px', height: '15px' }} />
                  {isAdaptive ? 'Begin Adaptive Session' : 'Generate Questions & Begin'}
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function InterviewRoom({
  onExit,
  initialSession,
  onViewReport,
  initialMode = 'technical',
  targetInterviewMode,
  initialStream,
  onStreamChange,
}: {
  onExit: () => void
  initialSession?: InterviewSessionResponse | null
  onViewReport?: (sessionId: string) => void
  initialMode?: 'technical' | 'video'
  targetInterviewMode?: 'CODING' | 'VERBAL'
  initialStream?: MediaStream | null
  onStreamChange?: (stream: MediaStream | null) => void
}) {
  const [session, setSession] = useState<InterviewSessionResponse | null>(initialSession || null)
  const defaultRoomMode =
    targetInterviewMode === 'CODING' || initialSession?.interview_mode === 'CODING'
      ? 'technical'
      : targetInterviewMode === 'VERBAL' || initialSession?.interview_mode === 'VERBAL'
      ? 'video'
      : initialMode
  const [roomMode, setRoomMode] = useState<'technical' | 'video'>(defaultRoomMode)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [competencyState, setCompetencyState] = useState<SessionCompetencyState | null>(
    initialSession?.competency_state || null,
  )
  const [generatingNext, setGeneratingNext] = useState(false)
  const [nextQuestionError, setNextQuestionError] = useState<string | null>(null)

  const isCodingSession =
    session?.interview_mode === 'CODING' ||
    targetInterviewMode === 'CODING' ||
    (!session && defaultRoomMode === 'technical')
  const isVerbalSession =
    session?.interview_mode === 'VERBAL' ||
    targetInterviewMode === 'VERBAL' ||
    (!session && defaultRoomMode === 'video')
  const isAmbiguousSession = Boolean(
    session?.is_unreliable_mode || session?.interview_mode === 'AMBIGUOUS'
  )
  const isProctoredSession = Boolean(
    isCodingSession ||
    isVerbalSession ||
    session?.interview_mode === 'CODING' ||
    session?.interview_mode === 'VERBAL' ||
    roomMode === 'video'
  )

  const computeRemainingSeconds = (sess: InterviewSessionResponse | null): number => {
    if (!sess) return 1800
    const totalSec = (sess.duration_minutes || 30) * 60
    const startMs = new Date(sess.created_at).getTime()
    if (isNaN(startMs)) return totalSec
    const elapsedSec = Math.max(0, Math.floor((Date.now() - startMs) / 1000))
    return Math.max(0, totalSec - elapsedSec)
  }

  const [sessionRemaining, setSessionRemaining] = useState<number>(() =>
    initialSession ? computeRemainingSeconds(initialSession) : 1800
  )

  useEffect(() => {
    if (!session) return
    setSessionRemaining(computeRemainingSeconds(session))
    const interval = window.setInterval(() => {
      setSessionRemaining(computeRemainingSeconds(session))
    }, 1000)
    return () => window.clearInterval(interval)
  }, [session])

  const formatSessionTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const getSessionTimeBand = (seconds: number): 'comprehensive' | 'focused' | 'concise' | 'expired' => {
    if (seconds <= 0) return 'expired'
    if (seconds > 600) return 'comprehensive'
    if (seconds >= 300) return 'focused'
    return 'concise'
  }
  const currentBand = getSessionTimeBand(sessionRemaining)
  const isSessionExpired = sessionRemaining <= 0

  useEffect(() => {
    if (initialSession) {
      setSession(initialSession)
      if (initialSession.interview_mode === 'CODING') {
        setRoomMode('technical')
      } else if (initialSession.interview_mode === 'VERBAL') {
        setRoomMode('video')
      }
      setCurrentIndex(0)
      if (initialSession.competency_state) {
        setCompetencyState(initialSession.competency_state)
      }
      const rawAnswers = (initialSession as any).answers
      if (rawAnswers && typeof rawAnswers === 'object') {
        const restoredAnswers: Record<string, { text: string; time: string }> = {}
        const restoredEvaluations: Record<string, AnswerEvaluationResponse> = {}
        Object.entries(rawAnswers).forEach(([qId, data]: [string, any]) => {
          if (data && typeof data === 'object') {
            if (data.answer_text) {
              restoredAnswers[qId] = {
                text: data.answer_text,
                time: data.submitted_at
                  ? new Date(data.submitted_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                  : '',
              }
            }
            if (data.evaluation) {
              restoredEvaluations[qId] = {
                session_id: initialSession.session_id,
                question_id: qId,
                ...data.evaluation,
                evaluated_at: data.evaluated_at || new Date().toISOString(),
                saved_to_db: initialSession.saved_to_db,
                db_status: initialSession.db_status,
              }
            }
          }
        })
        setAnswers(restoredAnswers)
        setEvaluations(restoredEvaluations)
      }
    }
  }, [initialSession])

  // Media preview state
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const streamRef = useRef<MediaStream | null>(initialStream || null)
  const [activeStream, setActiveStream] = useState<MediaStream | null>(initialStream || null)
  const [deviceState, setDeviceState] = useState<'idle' | 'requesting' | 'initializing' | 'ready' | 'interrupted' | 'denied' | 'error'>('idle')
  const [videoFrameActive, setVideoFrameActive] = useState(false)
  const [cameraErrorMessage, setCameraErrorMessage] = useState<string | null>(null)
  const [isCameraInterrupted, setIsCameraInterrupted] = useState(false)
  const [candidateAbsentAlert, setCandidateAbsentAlert] = useState(false)
  const [multiplePeopleAlert, setMultiplePeopleAlert] = useState(false)
  const [activeCommAlert, setActiveCommAlert] = useState<string | null>(null)
  const [faceDetectorNotice, setFaceDetectorNotice] = useState<string | null>(null)
  const [isCameraCollapsed, setIsCameraCollapsed] = useState(false)
  const [isTimelineLoading, setIsTimelineLoading] = useState(false)
  const [timelineError, setTimelineError] = useState<string | null>(null)
  const trackerRef = useRef<FaceVisibilityTracker | null>(null)
  const commDetectorRef = useRef<ExternalCommunicationDetector>(new ExternalCommunicationDetector())
  const [recording, setRecording] = useState(false)
  const [elapsed, setElapsed] = useState(0)

  // Answer state
  const [answerText, setAnswerText] = useState('')
  const [answers, setAnswers] = useState<Record<string, { text: string; time: string }>>({})
  const [submitting, setSubmitting] = useState(false)
  const [submitMessage, setSubmitMessage] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Voice & Speech Recognition state
  const [ttsSupported, setTtsSupported] = useState(false)
  const [isAiSpeaking, setIsAiSpeaking] = useState(false)
  const [autoSpeakEnabled, setAutoSpeakEnabled] = useState(true)
  const [speechSupported, setSpeechSupported] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [interimTranscript, setInterimTranscript] = useState('')
  const [micPermissionError, setMicPermissionError] = useState<string | null>(null)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [transcriptionError, setTranscriptionError] = useState<string | null>(null)
  const [generatingReport, setGeneratingReport] = useState(false)
  const [reportError, setReportError] = useState<string | null>(null)
  const [showIdeInVideo, setShowIdeInVideo] = useState(false)
  const [adapting, setAdapting] = useState(false)
  const [adaptationNotice, setAdaptationNotice] = useState<string | null>(null)
  const [isSessionComplete, setIsSessionComplete] = useState(false)
  const [selectedMcOption, setSelectedMcOption] = useState<string | null>(null)
  const [selectedAnswerMode, setSelectedAnswerMode] = useState<string | null>(null)
  const [isNavigating, setIsNavigating] = useState(false)

  const currentQuestion = session?.questions?.[currentIndex]
  const rawQType = (currentQuestion?.question_type || '').toLowerCase()
  const isRawCoding =
    rawQType === 'coding' || rawQType === 'coding_dsa' || rawQType === 'dsa' || rawQType === 'code'
  const isRawSql = rawQType === 'sql'
  const isRawSystemDesign = rawQType === 'system_design'
  const isRawMultipleChoice = rawQType === 'multiple_choice'

  const availableModes: string[] = useMemo(() => {
    if (currentQuestion?.available_modes && currentQuestion.available_modes.length > 0) {
      return currentQuestion.available_modes
    }
    if (isRawCoding) return ['coding', 'verbal']
    if (isRawSql) return ['sql', 'verbal']
    if (isRawSystemDesign) return ['system_design', 'verbal']
    if (isRawMultipleChoice) return ['multiple_choice', 'verbal']
    return ['verbal']
  }, [currentQuestion, isRawCoding, isRawSql, isRawSystemDesign, isRawMultipleChoice])

  const recommendedMode: string = useMemo(() => {
    if (currentQuestion?.recommended_mode) return currentQuestion.recommended_mode
    if (isRawCoding) return 'coding'
    if (isRawSql) return 'sql'
    if (isRawSystemDesign) return 'system_design'
    if (isRawMultipleChoice) return 'multiple_choice'
    return 'verbal'
  }, [currentQuestion, isRawCoding, isRawSql, isRawSystemDesign, isRawMultipleChoice])

  const activeMode: string = useMemo(() => {
    if (selectedAnswerMode && availableModes.includes(selectedAnswerMode)) {
      return selectedAnswerMode
    }
    return recommendedMode
  }, [selectedAnswerMode, availableModes, recommendedMode])

  const isCodingMode = activeMode === 'coding'
  const isSqlMode = activeMode === 'sql'
  const isSystemDesignMode = activeMode === 'system_design'
  const isMultipleChoiceMode = activeMode === 'multiple_choice'
  const isVerbalMode = activeMode === 'verbal'

  const handleAnswerSavedFromIde = useCallback((data: {
    answer_text?: string
    code?: string
    language?: string
    sql_query?: string
    execution_result?: any
  }) => {
    if (!session) return
    const currentQ = session.questions[currentIndex]
    if (!currentQ) return

    if (data.code || data.sql_query) {
      latestSolutionDataRef.current[currentQ.id] = {
        code: data.code,
        language: data.language,
        sql_query: data.sql_query,
      }
    }
    setAnswers((prev) => ({
      ...prev,
      [currentQ.id]: {
        text: data.answer_text || (data.code ? `[Code Solution in ${data.language}]` : '[SQL Query Solution]'),
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    }))
    if (data.answer_text && !answerText.trim()) {
      setAnswerText(data.answer_text)
    }
  }, [session, currentIndex, answerText])

  const latestSolutionDataRef = useRef<Record<string, { code?: string; language?: string; sql_query?: string }>>({})

  const recognitionRef = useRef<any>(null)
  const isListeningRef = useRef<boolean>(false)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])

  // Phase 3: Evaluation state
  const [evaluations, setEvaluations] = useState<Record<string, AnswerEvaluationResponse>>({})
  const [evaluating, setEvaluating] = useState(false)
  const [evalError, setEvalError] = useState<string | null>(null)

  // Phase 4: Integrity Intelligence Timeline state
  const [timelineEvents, setTimelineEvents] = useState<IntegrityEventRecord[]>([])
  const [showTimeline, setShowTimeline] = useState(false)

  const currentQuestionIdRef = useRef<string | null>(null)

  useEffect(() => {
    currentQuestionIdRef.current = session?.questions[currentIndex]?.id || null
  }, [session, currentIndex])

  useEffect(() => {
    if (typeof window !== 'undefined') {
      if ('speechSynthesis' in window) {
        setTtsSupported(true)
      }
      const hasSpeechRec = Boolean((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition)
      setSpeechSupported(hasSpeechRec)
    }
  }, [])

  const logEvent = useCallback(
    async (
      eventType: IntegrityEventType,
      details?: Record<string, unknown>,
      questionIdOverride?: string | null,
    ) => {
      if (!session) return
      const activeQId = questionIdOverride !== undefined ? questionIdOverride : currentQuestionIdRef.current
      try {
        const severity = details?.severity as string | undefined
        const duration_seconds = details?.duration_seconds as number | undefined
        const detection_source = details?.detection_source as string | undefined
        const detection_confidence = details?.confidence as number | undefined
        const status = details?.status as string | undefined
        const record = await logIntegrityEvent(session.session_id, {
          event_type: eventType,
          question_id: activeQId,
          details,
          severity,
          duration_seconds,
          detection_source,
          detection_confidence,
          status,
        })
        setTimelineEvents((prev) => {
          const existingIdx = prev.findIndex((p) => p.event_id === record.event_id)
          if (existingIdx >= 0) {
            const next = [...prev]
            next[existingIdx] = record
            return next
          }
          return [...prev, record]
        })
      } catch {
        // Soft fail on telemetry event log without blocking candidate flow
      }
    },
    [session],
  )

  const attachStreamToVideo = useCallback(async (videoEl: HTMLVideoElement, stream: MediaStream) => {
    try {
      videoEl.muted = true
      videoEl.playsInline = true
      videoEl.autoplay = true

      if (videoEl.srcObject !== stream) {
        videoEl.srcObject = stream
      }

      const playPromise = videoEl.play()
      if (playPromise !== undefined) {
        await playPromise
      }

      if (videoEl.videoWidth > 0 && videoEl.videoHeight > 0) {
        setVideoFrameActive(true)
        setDeviceState('ready')
        setIsCameraInterrupted(false)
        setCameraErrorMessage(null)
      } else {
        setDeviceState('initializing')
        const onFrameReady = () => {
          if (videoEl.videoWidth > 0 && videoEl.videoHeight > 0) {
            setVideoFrameActive(true)
            setDeviceState('ready')
            setIsCameraInterrupted(false)
            setCameraErrorMessage(null)
            cleanupListeners()
          }
        }
        const cleanupListeners = () => {
          videoEl.removeEventListener('loadedmetadata', onFrameReady)
          videoEl.removeEventListener('loadeddata', onFrameReady)
          videoEl.removeEventListener('playing', onFrameReady)
          videoEl.removeEventListener('timeupdate', onFrameReady)
          videoEl.removeEventListener('resize', onFrameReady)
        }
        videoEl.addEventListener('loadedmetadata', onFrameReady)
        videoEl.addEventListener('loadeddata', onFrameReady)
        videoEl.addEventListener('playing', onFrameReady)
        videoEl.addEventListener('timeupdate', onFrameReady)
        videoEl.addEventListener('resize', onFrameReady)
      }
    } catch (err: unknown) {
      if ((err as Error)?.name !== 'AbortError') {
        const msg = err instanceof Error ? err.message : 'Camera preview playback failed'
        console.warn('Video playback error:', err)
        setCameraErrorMessage(msg)
        setDeviceState('error')
      }
    }
  }, [])

  const setVideoRef = useCallback(
    (node: HTMLVideoElement | null) => {
      videoRef.current = node
      if (node && activeStream) {
        const vTracks = activeStream.getVideoTracks()
        const isLive = vTracks.length > 0 && vTracks.some((t) => t.readyState === 'live' && t.enabled)
        if (isLive) {
          attachStreamToVideo(node, activeStream)
        }
      }
    },
    [activeStream, attachStreamToVideo],
  )

  useEffect(() => {
    if (initialStream && initialStream !== activeStream) {
      const vTracks = initialStream.getVideoTracks()
      const isLive = vTracks.length > 0 && vTracks.some((t) => t.readyState === 'live' && t.enabled)
      if (isLive) {
        setActiveStream(initialStream)
        streamRef.current = initialStream
      }
    }
  }, [initialStream, activeStream])

  const requestDevices = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setDeviceState('denied')
      setIsCameraInterrupted(true)
      setCameraErrorMessage('Your browser does not support camera media devices (navigator.mediaDevices.getUserMedia unavailable).')
      logEvent('camera_mic_denied', { reason: 'navigator.mediaDevices.getUserMedia unavailable', severity: 'warning' })
      return
    }
    setDeviceState('requesting')
    setCameraErrorMessage(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
        audio: true,
      })
      streamRef.current = stream
      setActiveStream(stream)
      onStreamChange?.(stream)
      if (videoRef.current) {
        await attachStreamToVideo(videoRef.current, stream)
      }
      setIsCameraInterrupted(false)
      logEvent('camera_mic_granted', { video: true, audio: true, severity: 'info' })
      logEvent('stream_recovered', { note: 'Camera stream connected or re-established', severity: 'info' })

      // Detect stream interruptions
      stream.getVideoTracks().forEach((track) => {
        track.onended = () => {
          setIsCameraInterrupted(true)
          setVideoFrameActive(false)
          setDeviceState('interrupted')
          setCameraErrorMessage('Camera feed disconnected or video track ended.')
          logEvent('video_track_ended', { kind: 'video', label: track.label, severity: 'warning' })
          logEvent('stream_interrupted', { reason: 'Video track ended or disconnected', severity: 'warning' })
        }
        track.onmute = () => {
          setIsCameraInterrupted(true)
          setVideoFrameActive(false)
          setDeviceState('interrupted')
          setCameraErrorMessage('Camera stream was muted or paused by hardware/browser.')
          logEvent('stream_interrupted', { reason: 'Video track muted', severity: 'warning' })
        }
        track.onunmute = () => {
          setIsCameraInterrupted(false)
          setCameraErrorMessage(null)
          if (videoRef.current && videoRef.current.videoWidth > 0 && videoRef.current.videoHeight > 0) {
            setVideoFrameActive(true)
            setDeviceState('ready')
          }
        }
      })
      stream.getAudioTracks().forEach((track) => {
        track.onended = () => {
          logEvent('media_track_ended', { kind: 'audio', label: track.label, severity: 'info' })
        }
      })
    } catch (err: unknown) {
      setDeviceState('denied')
      setIsCameraInterrupted(true)
      const msg = err instanceof Error ? err.message : 'Camera permission denied or device busy.'
      setCameraErrorMessage(`Camera permission was denied or device is unavailable: ${msg}`)
      logEvent('camera_mic_denied', { reason: msg, severity: 'warning' })
    }
  }

  // Handle activeStream connection and track monitoring
  useEffect(() => {
    if (!activeStream) return
    streamRef.current = activeStream
    const vTracks = activeStream.getVideoTracks()
    const isLive = vTracks.length > 0 && vTracks.some((t) => t.readyState === 'live' && t.enabled)

    if (!isLive) {
      setIsCameraInterrupted(true)
      setVideoFrameActive(false)
      setDeviceState('interrupted')
      setCameraErrorMessage('Camera stream tracks have ended or are not active.')
      return
    }

    if (videoRef.current) {
      attachStreamToVideo(videoRef.current, activeStream)
    }

    vTracks.forEach((track) => {
      track.onended = () => {
        setIsCameraInterrupted(true)
        setVideoFrameActive(false)
        setDeviceState('interrupted')
        setCameraErrorMessage('Camera feed disconnected or video track ended.')
        logEvent('video_track_ended', { kind: 'video', label: track.label, severity: 'warning' })
        logEvent('stream_interrupted', { reason: 'Video track ended or disconnected', severity: 'warning' })
      }
      track.onmute = () => {
        setIsCameraInterrupted(true)
        setVideoFrameActive(false)
        setDeviceState('interrupted')
        setCameraErrorMessage('Camera stream was muted or paused by hardware/browser.')
        logEvent('stream_interrupted', { reason: 'Video track muted', severity: 'warning' })
      }
      track.onunmute = () => {
        setIsCameraInterrupted(false)
        setCameraErrorMessage(null)
        if (videoRef.current && videoRef.current.videoWidth > 0 && videoRef.current.videoHeight > 0) {
          setVideoFrameActive(true)
          setDeviceState('ready')
        }
      }
    })
    activeStream.getAudioTracks().forEach((track) => {
      track.onended = () => {
        logEvent('media_track_ended', { kind: 'audio', label: track.label, severity: 'info' })
      }
    })
  }, [activeStream, attachStreamToVideo, logEvent])

  const answerTextRef = useRef(answerText)
  answerTextRef.current = answerText
  const interimTranscriptRef = useRef(interimTranscript)
  interimTranscriptRef.current = interimTranscript

  // Continuous Face Visibility & Secondary Person Tracking for Proctored Interview
  useEffect(() => {
    if (!isProctoredSession || !session) {
      if (trackerRef.current) {
        trackerRef.current.stop()
        trackerRef.current = null
      }
      return
    }

    if (!videoRef.current || deviceState !== 'ready' || !videoFrameActive || isCameraInterrupted) {
      if (trackerRef.current) {
        trackerRef.current.stop()
        trackerRef.current = null
      }
      return
    }

    const tracker = new FaceVisibilityTracker({
      sampleIntervalMs: 600,
      absenceThresholdMs: 5000,
      multipleFaceThresholdMs: 2500,
      minConfidence: 0.5,
      onAnomaly: (anomaly) => {
        if (anomaly.type === 'face_not_detected' || anomaly.type === 'candidate_out_of_frame') {
          setCandidateAbsentAlert(true)
          logEvent(anomaly.type, {
            duration_seconds: anomaly.duration,
            confidence: anomaly.confidence,
            detection_source: anomaly.details?.source,
            severity: 'warning',
            status: 'active',
          })
        } else if (anomaly.type === 'candidate_visibility_recovered') {
          setCandidateAbsentAlert(false)
          logEvent('candidate_visibility_recovered', {
            duration_seconds: anomaly.duration,
            severity: 'info',
            status: 'resolved',
          })
        } else if (anomaly.type === 'multiple_faces_detected') {
          setMultiplePeopleAlert(true)
          logEvent('multiple_faces_detected', {
            count: anomaly.details?.count,
            duration_seconds: anomaly.duration,
            confidence: anomaly.confidence,
            detection_source: anomaly.details?.source,
            severity: 'warning',
            status: 'active',
          })
        } else if (anomaly.type === 'multiple_faces_resolved') {
          setMultiplePeopleAlert(false)
          logEvent('multiple_faces_resolved', {
            duration_seconds: anomaly.duration,
            severity: 'info',
            status: 'resolved',
          })
        } else if (anomaly.type === 'detector_unavailable') {
          setFaceDetectorNotice('Face detection service unavailable or restricted by browser.')
          logEvent('detector_unavailable', {
            reason: anomaly.details?.reason,
            severity: 'informational',
            status: 'unresolved',
          })
        }
      },
      onFaceStatusChange: (result) => {
        if (result.source !== 'unavailable') {
          setFaceDetectorNotice(null)
        }
        // Continuous multimodal external communication analysis
        const commIncident = commDetectorRef.current.evaluate({
          facesDetected: result.facesCount,
          isSpeechActive: isListeningRef.current,
          currentTranscript: (answerTextRef.current || '') + ' ' + (interimTranscriptRef.current || ''),
          questionId: currentQuestionIdRef.current,
        })
        if (commIncident) {
          if (commIncident.status === 'active') {
            setActiveCommAlert(commIncident.warningMessage)
            logEvent('possible_external_communication', {
              duration_seconds: commIncident.durationSeconds,
              detection_source: commIncident.evidenceSource,
              confidence: commIncident.confidence,
              severity: 'warning',
              status: 'active',
            })
          } else if (commIncident.status === 'resolved') {
            setActiveCommAlert(null)
            logEvent('possible_external_communication', {
              duration_seconds: commIncident.durationSeconds,
              severity: 'info',
              status: 'resolved',
            })
          }
        }
      },
    })

    trackerRef.current = tracker
    tracker.start(videoRef.current)

    return () => {
      tracker.stop()
      trackerRef.current = null
    }
  }, [isProctoredSession, session?.session_id, deviceState, logEvent])

  // Timer effect
  useEffect(() => {
    if (!recording) return
    const timer = window.setInterval(() => setElapsed((value) => value + 1), 1000)
    return () => window.clearInterval(timer)
  }, [recording])

  // Track Page Visibility & Window Focus API events safely with cleanup
  useEffect(() => {
    if (!session) return

    const handleVisibilityChange = () => {
      if (document.hidden) {
        logEvent('tab_hidden', { context: 'Browser tab switched away or minimized' })
      } else {
        logEvent('tab_visible', { context: 'Browser tab returned to foreground' })
      }
    }

    const handleWindowBlur = () => {
      logEvent('window_blur', { context: 'Interview browser window lost focus' })
    }

    const handleWindowFocus = () => {
      logEvent('window_focus', { context: 'Interview browser window regained focus' })
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('blur', handleWindowBlur)
    window.addEventListener('focus', handleWindowFocus)

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('blur', handleWindowBlur)
      window.removeEventListener('focus', handleWindowFocus)
    }
  }, [session, logEvent])

  // Note: Media stream lifecycle is retained across component remounts and mode switches
  // and cleaned up when explicitly exiting the interview or logging out.

  // Text-to-Speech logic
  const stopAiSpeech = useCallback(() => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel()
      setIsAiSpeaking(false)
    }
  }, [])

  const speakQuestion = useCallback((text: string) => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.rate = 0.95
    utterance.lang = 'en-US'
    utterance.onstart = () => setIsAiSpeaking(true)
    utterance.onend = () => setIsAiSpeaking(false)
    utterance.onerror = () => setIsAiSpeaking(false)
    window.speechSynthesis.speak(utterance)
  }, [])

  // Auto-speak question when navigating questions if autoSpeakEnabled
  useEffect(() => {
    if (autoSpeakEnabled && session?.questions[currentIndex]) {
      speakQuestion(session.questions[currentIndex].text)
    } else {
      stopAiSpeech()
    }
    return () => {
      stopAiSpeech()
    }
  }, [currentIndex, autoSpeakEnabled, session, speakQuestion, stopAiSpeech])

  // Stop speech synthesis & speech recognition on component unmount
  useEffect(() => {
    return () => {
      stopAiSpeech()
      if (recognitionRef.current) {
        isListeningRef.current = false
        try {
          recognitionRef.current.abort()
        } catch {}
      }
    }
  }, [stopAiSpeech])

  // Speech Recognition & Server-side Audio Recording logic
  const stopListening = useCallback(() => {
    isListeningRef.current = false
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop()
      } catch {}
    }
    setIsListening(false)
    setInterimTranscript('')
    setRecording(false)
    logEvent('practice_paused', { elapsed_seconds: elapsed })

    // Stop MediaRecorder and trigger high-accuracy Whisper transcription
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      const recorder = mediaRecorderRef.current
      recorder.onstop = async () => {
        const chunks = audioChunksRef.current
        if (chunks.length > 0) {
          const audioBlob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' })
          if (audioBlob.size > 200) {
            setIsTranscribing(true)
            setTranscriptionError(null)
            try {
              const res = await transcribeAudio(audioBlob, {
                sessionId: session?.session_id,
                questionId: session?.questions[currentIndex]?.id,
              })
              if (res.transcript && res.transcript.trim()) {
                setAnswerText((prev) => {
                  const cleanPrev = prev.trim()
                  const cleanNew = res.transcript.trim()
                  if (!cleanPrev) return cleanNew
                  // Avoid duplication if client Web Speech API already captured identical or similar text
                  if (cleanPrev.toLowerCase().includes(cleanNew.toLowerCase())) {
                    return cleanPrev
                  }
                  if (cleanNew.toLowerCase().includes(cleanPrev.toLowerCase())) {
                    return cleanNew
                  }
                  return `${cleanPrev} ${cleanNew}`
                })
              }
            } catch (err: any) {
              console.warn('Server transcription error:', err)
              setTranscriptionError(
                err.message || 'Server audio transcription unavailable. Your answer is preserved and can be edited.'
              )
            } finally {
              setIsTranscribing(false)
            }
          }
        }
      }
      try {
        recorder.stop()
      } catch {}
      mediaRecorderRef.current = null
    }
  }, [elapsed, logEvent, session, currentIndex])

  const startListening = async () => {
    setMicPermissionError(null)
    setTranscriptionError(null)
    stopAiSpeech()

    if (deviceState !== 'ready') {
      await requestDevices()
    }

    // Initialize MediaRecorder for high-reliability server-side Whisper transcription
    try {
      let audioStream = streamRef.current
      if (!audioStream || audioStream.getAudioTracks().length === 0) {
        if (typeof navigator !== 'undefined' && navigator.mediaDevices?.getUserMedia) {
          audioStream = await navigator.mediaDevices.getUserMedia({ audio: true })
          if (!streamRef.current) streamRef.current = audioStream
        }
      }

      if (audioStream && audioStream.getAudioTracks().length > 0 && typeof MediaRecorder !== 'undefined') {
        audioChunksRef.current = []
        let options: MediaRecorderOptions | undefined = undefined
        if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
          options = { mimeType: 'audio/webm;codecs=opus' }
        } else if (MediaRecorder.isTypeSupported('audio/webm')) {
          options = { mimeType: 'audio/webm' }
        } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
          options = { mimeType: 'audio/mp4' }
        }

        const recorder = new MediaRecorder(audioStream, options)
        recorder.ondataavailable = (e) => {
          if (e.data && e.data.size > 0) {
            audioChunksRef.current.push(e.data)
          }
        }
        recorder.start(250)
        mediaRecorderRef.current = recorder
        setRecording(true)
      }
    } catch (recErr: any) {
      console.warn('MediaRecorder setup notice:', recErr)
      if (recErr.name === 'NotAllowedError' || recErr.name === 'PermissionDeniedError') {
        setMicPermissionError('Microphone access was denied. Please allow microphone permissions in your browser or type your response.')
      }
    }

    if (!speechSupported) {
      setRecording(true)
      logEvent('practice_started', { elapsed_seconds: elapsed, mode: 'media_recorder' })
      return
    }

    const SpeechRecognitionAPI = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SpeechRecognitionAPI) return

    try {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort()
        } catch {}
      }
      const recognition = new SpeechRecognitionAPI()
      recognition.continuous = true
      recognition.interimResults = true
      recognition.lang = 'en-US'

      recognition.onstart = () => {
        setIsListening(true)
        isListeningRef.current = true
        setRecording(true)
        logEvent('practice_started', { elapsed_seconds: elapsed, mode: 'speech_recognition' })
      }

      recognition.onresult = (event: any) => {
        let interim = ''
        let finalChunk = ''
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const transcriptPart = event.results[i][0].transcript
          if (event.results[i].isFinal) {
            finalChunk += transcriptPart
          } else {
            interim += transcriptPart
          }
        }
        setInterimTranscript(interim)
        if (finalChunk) {
          setAnswerText((prev) => {
            const trimmed = prev.trim()
            const spacer = trimmed.length > 0 ? ' ' : ''
            return trimmed + spacer + finalChunk.trim()
          })
        }
      }

      recognition.onerror = (event: any) => {
        if (event.error === 'not-allowed') {
          setMicPermissionError('Microphone access was denied. Please allow microphone permissions in your browser address bar.')
          logEvent('camera_mic_denied', { reason: 'speech_recognition_not_allowed' })
        } else if (event.error !== 'no-speech') {
          setMicPermissionError(`Speech recognition notification: ${event.error}. You can also type your response.`)
        }
        setIsListening(false)
        isListeningRef.current = false
      }

      recognition.onend = () => {
        if (isListeningRef.current) {
          try {
            recognition.start()
          } catch {
            setIsListening(false)
            isListeningRef.current = false
          }
        } else {
          setIsListening(false)
          setInterimTranscript('')
        }
      }

      recognitionRef.current = recognition
      recognition.start()
    } catch {
      setMicPermissionError('Unable to activate speech recognition. You can type your response manually.')
      setIsListening(false)
      isListeningRef.current = false
    }
  }

  const handleRetryAnswer = () => {
    stopListening()
    setAnswerText('')
    setInterimTranscript('')
    setTranscriptionError(null)
    setSubmitMessage(null)
    setSubmitError(null)
    setEvalError(null)
  }

  // Sync answerText, selectedAnswerMode, and evaluation state when navigating questions
  useEffect(() => {
    if (!session) return
    const currentQ = session.questions[currentIndex]
    if (currentQ && answers[currentQ.id]) {
      setAnswerText(answers[currentQ.id].text)
    } else {
      setAnswerText('')
    }
    setSelectedAnswerMode(currentQ?.recommended_mode || null)
    setInterimTranscript('')
    setSubmitMessage(null)
    setSubmitError(null)
    setEvalError(null)
  }, [currentIndex, session, answers])

  const formatTime = `${String(Math.floor(elapsed / 60)).padStart(2, '0')}:${String(elapsed % 60).padStart(2, '0')}`

  const handleTogglePractice = () => {
    if (recording) {
      stopListening()
    } else {
      startListening()
    }
  }

  const handleSubmitAnswer = async () => {
    if (!session || submitting || evaluating) return
    if (isSessionExpired) {
      setSubmitError('Interview session time has expired. Cannot submit additional answers.')
      return
    }
    const currentQ = session.questions[currentIndex]
    if (!currentQ || !answerText.trim()) return

    stopListening()
    stopAiSpeech()
    setSubmitting(true)
    setSubmitMessage(null)
    setSubmitError(null)

    try {
      const res = await submitQuestionAnswer(session.session_id, {
        question_id: currentQ.id,
        answer_text: answerText.trim(),
        answer_mode: activeMode,
      })
      setAnswers((prev) => ({
        ...prev,
        [currentQ.id]: {
          text: answerText.trim(),
          time: new Date(res.submitted_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      }))
      setSubmitMessage(res.message)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to submit answer'
      setSubmitError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  const handleEvaluateAnswer = async () => {
    if (!session || submitting || evaluating) return
    if (isSessionExpired) {
      setEvalError('Interview session time has expired. Cannot submit additional answers.')
      return
    }
    const currentQ = session.questions[currentIndex]
    if (!currentQ) return

    stopListening()
    stopAiSpeech()

    const textToEvaluate = answerText.trim()
    if (!textToEvaluate) {
      setEvalError('Please speak or type your response before requesting evaluation.')
      return
    }

    setEvaluating(true)
    setEvalError(null)

    const isCoding = activeMode === 'coding' || isCodingMode
    const isSql = activeMode === 'sql' || isSqlMode
    const sol = latestSolutionDataRef.current[currentQ.id]
    const resolvedMode = isCoding ? 'coding' : isSql ? 'sql' : activeMode
    const resolvedCode = isCoding ? (sol?.code || (session.drafts?.[currentQ.id] ? Object.values(session.drafts[currentQ.id])[0]?.code : undefined)) : undefined
    const resolvedLang = isCoding ? (sol?.language || (session.drafts?.[currentQ.id] ? Object.keys(session.drafts[currentQ.id])[0] : 'python')) : undefined
    const resolvedSql = isSql ? (sol?.sql_query || session.drafts?.[currentQ.id]?.['sql']?.code) : undefined

    try {
      // First ensure answer is recorded in the session database
      if (!answers[currentQ.id] || answers[currentQ.id].text !== textToEvaluate) {
        await submitQuestionAnswer(session.session_id, {
          question_id: currentQ.id,
          answer_text: textToEvaluate,
          code: resolvedCode,
          language: resolvedLang,
          sql_query: resolvedSql,
          answer_mode: resolvedMode,
        })
        setAnswers((prev) => ({
          ...prev,
          [currentQ.id]: {
            text: textToEvaluate,
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        }))
      }

      // Execute AI evaluation & communication coaching
      const evalRes = await evaluateAnswer(session.session_id, currentQ.id, {
        answer_text: textToEvaluate,
        code: resolvedCode,
        language: resolvedLang,
        sql_query: resolvedSql,
        answer_mode: resolvedMode,
      })
      setEvaluations((prev) => ({
        ...prev,
        [currentQ.id]: evalRes,
      }))

      // Update competencies state with newly evaluated evidence
      try {
        const comp = await getSessionCompetencies(session.session_id)
        setCompetencyState(comp)
      } catch {
        // Soft fail without blocking
      }
    } catch (err: unknown) {
      let msg = err instanceof Error ? err.message : 'Failed to evaluate answer'
      if (
        msg.includes('429') ||
        msg.toLowerCase().includes('rate-limit') ||
        msg.toLowerCase().includes('rate limit') ||
        msg.toLowerCase().includes('quota')
      ) {
        msg = 'AI service is temporarily rate-limited. Please wait a few seconds before retrying. Your response has been safely saved.'
      }
      setEvalError(msg)
    } finally {
      setEvaluating(false)
    }
  }

  const handleAdaptiveSubmission = async (solutionPayload?: {
    code?: string
    language?: string
    sql_query?: string
    answer_text?: string
    execution_result?: any
    answer_mode?: string
  }) => {
    if (!session || submitting || evaluating || adapting) return
    if (isSessionExpired) {
      setSubmitError('Interview session time has expired. Cannot submit additional answers.')
      return
    }
    const currentQ = session.questions[currentIndex]
    if (!currentQ) return

    const isCoding = (solutionPayload?.answer_mode === 'coding') || isCodingMode || activeMode === 'coding'
    const isSql = (solutionPayload?.answer_mode === 'sql') || isSqlMode || activeMode === 'sql'
    const resolvedMode = solutionPayload?.answer_mode || (isCoding ? 'coding' : isSql ? 'sql' : activeMode)
    const sol = latestSolutionDataRef.current[currentQ.id]
    const codeToSubmit = solutionPayload?.code || (isCoding ? (sol?.code || (session.drafts?.[currentQ.id] ? Object.values(session.drafts[currentQ.id])[0]?.code : undefined)) : undefined)
    const langToSubmit = solutionPayload?.language || (isCoding ? (sol?.language || (session.drafts?.[currentQ.id] ? Object.keys(session.drafts[currentQ.id])[0] : 'python')) : undefined)
    const sqlToSubmit = solutionPayload?.sql_query || (isSql ? (sol?.sql_query || session.drafts?.[currentQ.id]?.['sql']?.code) : undefined)

    let textToSubmit = solutionPayload?.answer_text || answerText.trim()
    if (!textToSubmit && (isCoding || isSql)) {
      if (codeToSubmit) {
        textToSubmit = `[Solution in ${langToSubmit || 'code'}]`
      } else if (sqlToSubmit) {
        textToSubmit = '[SQL Query Solution]'
      }
    }

    if (!textToSubmit && !codeToSubmit && !sqlToSubmit) {
      setSubmitError('Please provide your response before submitting.')
      return
    }

    stopListening()
    stopAiSpeech()
    setSubmitting(true)
    setAdapting(true)
    setSubmitMessage(null)
    setSubmitError(null)
    setEvalError(null)
    setAdaptationNotice('Evaluating submitted solution and adapting next question...')

    try {
      const res = await submitAndAdaptQuestion(session.session_id, {
        question_id: currentQ.id,
        answer_text: textToSubmit,
        code: codeToSubmit,
        language: langToSubmit,
        sql_query: sqlToSubmit,
        execution_result: solutionPayload?.execution_result,
        remaining_seconds: sessionRemaining,
        answer_mode: resolvedMode,
      })

      // Record answer & evaluation locally
      setAnswers((prev) => ({
        ...prev,
        [currentQ.id]: {
          text: textToSubmit,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      }))

      if (res.evaluation) {
        setEvaluations((prev) => ({
          ...prev,
          [currentQ.id]: res.evaluation!,
        }))
      }

      if (res.competency_state) {
        setCompetencyState(res.competency_state)
      }

      // Check next question vs completion
      if (res.next_question) {
        setSession((prev) => {
          if (!prev) return prev
          const exists = prev.questions.some((q) => q.id === res.next_question!.id)
          const updated = exists ? prev.questions : [...prev.questions, res.next_question!]
          return {
            ...prev,
            questions: updated,
            active_question_id: res.next_question!.id,
            competency_state: res.competency_state || prev.competency_state,
          }
        })
        // Move to the next question
        setCurrentIndex((prev) => prev + 1)
        setAnswerText('')
        const decInfo = res.adaptive_decision?.action
          ? ` • ML Adaptive Engine: ${res.adaptive_decision.action.replace(/_/g, ' ')} (${res.adaptive_decision.next_difficulty.toUpperCase()})`
          : ''
        setAdaptationNotice(
          `Question evaluated (${res.evaluation?.overall_score ?? 0}/100). Next adaptive question loaded.${decInfo}`
        )
      } else if (res.is_complete) {
        setIsSessionComplete(true)
        setAdaptationNotice('All interview questions completed! You can now finalize and generate your performance report.')
      } else {
        setSubmitMessage('Solution submitted and evaluated successfully.')
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to submit and adapt'
      setSubmitError(msg)
      setAdaptationNotice(null)
    } finally {
      setSubmitting(false)
      setAdapting(false)
    }
  }

  const handleCompleteAndReport = async () => {
    if (!session || generatingReport) return
    setGeneratingReport(true)
    setReportError(null)
    stopAiSpeech()
    stopListening()

    try {
      await generateFinalReport(session.session_id)
      logEvent('session_completed', { elapsed_seconds: elapsed, target: 'final_report' })
      if (onViewReport) {
        onViewReport(session.session_id)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to finalize report'
      if (onViewReport) {
        onViewReport(session.session_id)
      } else {
        setReportError(msg)
      }
    } finally {
      setGeneratingReport(false)
    }
  }

  const handleGenerateNextQuestion = async () => {
    if (!session || generatingNext) return
    if (isSessionExpired) {
      setNextQuestionError('Interview session time has expired. No further questions can be generated.')
      return
    }
    setGeneratingNext(true)
    setNextQuestionError(null)

    try {
      const res = await generateNextQuestion(session.session_id, sessionRemaining)
      setSession((prev) => {
        if (!prev) return prev
        const exists = prev.questions.some((q) => q.id === res.question.id)
        const updatedQuestions = exists ? prev.questions : [...prev.questions, res.question]
        return {
          ...prev,
          questions: updatedQuestions,
          competency_state: res.competency_state || prev.competency_state,
        }
      })
      if (res.competency_state) {
        setCompetencyState(res.competency_state)
      }
      // Navigate to the newly added question
      setCurrentIndex(session.questions.length)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to generate next adaptive question'
      setNextQuestionError(msg)
    } finally {
      setGeneratingNext(false)
    }
  }

  const handleNavigateNext = async () => {
    if (isNavigating || generatingNext || generatingReport || !session) return
    setIsNavigating(true)
    try {
      const targetCount = session.target_question_count || 5
      if (currentIndex < session.questions.length - 1) {
        setCurrentIndex((prev) => prev + 1)
      } else if (session.is_adaptive && session.questions.length < targetCount && !isSessionExpired) {
        await handleGenerateNextQuestion()
      } else {
        await handleCompleteAndReport()
      }
    } finally {
      setTimeout(() => setIsNavigating(false), 250)
    }
  }

  const handleNavigatePrevious = () => {
    if (isNavigating || currentIndex <= 0) return
    setIsNavigating(true)
    try {
      setCurrentIndex((prev) => Math.max(0, prev - 1))
    } finally {
      setTimeout(() => setIsNavigating(false), 250)
    }
  }

  const handleExitPractice = () => {
    logEvent('session_completed', { elapsed_seconds: elapsed })
    onExit()
  }

  const formatTimelineLabel = (eventType: IntegrityEventType): string => {
    switch (eventType) {
      case 'tab_hidden':
        return 'Browser tab switched to background'
      case 'tab_visible':
        return 'Browser tab returned to foreground'
      case 'window_blur':
        return 'Browser window lost focus'
      case 'window_focus':
        return 'Browser window regained focus'
      case 'camera_mic_granted':
        return 'Camera & microphone stream connected'
      case 'camera_mic_denied':
      case 'camera_permission_denied':
        return 'Camera or microphone access denied'
      case 'camera_unavailable':
        return 'Camera device unavailable'
      case 'media_track_ended':
      case 'video_track_ended':
      case 'video_track_stopped':
        return 'Video stream interrupted or ended'
      case 'stream_interrupted':
        return 'Camera stream interrupted'
      case 'stream_recovered':
        return 'Camera stream recovered'
      case 'face_not_detected':
        return 'Face not detected in camera frame'
      case 'candidate_out_of_frame':
        return 'Candidate out of camera frame'
      case 'candidate_visibility_recovered':
        return 'Candidate face visibility recovered'
      case 'multiple_faces_detected':
        return 'Multiple people detected in camera frame'
      case 'multiple_faces_resolved':
        return 'Single candidate frame restored'
      case 'possible_external_communication':
        return 'Possible external communication detected'
      case 'communication_alert_cleared':
        return 'External communication condition cleared'
      case 'detector_unavailable':
      case 'detection_service_unavailable':
        return 'Detection service unavailable or limited'
      case 'practice_started':
      case 'interview_started':
        return 'Interview session started'
      case 'practice_paused':
      case 'interview_paused':
        return 'Interview session paused'
      case 'interview_resumed':
        return 'Interview session resumed'
      case 'session_completed':
      case 'interview_completed':
        return 'Interview session completed'
      case 'interview_terminated':
        return 'Interview session terminated'
      default:
        return String(eventType).replace(/_/g, ' ')
    }
  }

  if (!session) {
    return (
      <InterviewSetup
        targetMode={targetInterviewMode || (isVerbalSession ? 'VERBAL' : 'CODING')}
        initialStream={activeStream}
        onSessionReady={(newSession, stream) => {
          setSession(newSession)
          if (stream) {
            setActiveStream(stream)
            streamRef.current = stream
            setDeviceState('initializing')
            onStreamChange?.(stream)
          }
          if (newSession.interview_mode === 'CODING') {
            setRoomMode('technical')
          } else if (newSession.interview_mode === 'VERBAL') {
            setRoomMode('video')
          }
        }}
        onCancel={onExit}
      />
    )
  }

  if (!currentQuestion) {
    return (
      <InterviewSetup
        targetMode={targetInterviewMode || (isVerbalSession ? 'VERBAL' : 'CODING')}
        initialStream={activeStream}
        onSessionReady={(newSession, stream) => {
          setSession(newSession)
          if (stream) {
            setActiveStream(stream)
            streamRef.current = stream
            setDeviceState('initializing')
            onStreamChange?.(stream)
          }
          if (newSession.interview_mode === 'CODING') {
            setRoomMode('technical')
          } else if (newSession.interview_mode === 'VERBAL') {
            setRoomMode('video')
          }
        }}
        onCancel={onExit}
      />
    )
  }

  const targetQuestionCount = session.target_question_count || 5
  const isAdaptive = Boolean(session.is_adaptive)
  const isLastQuestion = isAdaptive
    ? (session.questions.length >= targetQuestionCount && currentIndex === session.questions.length - 1)
    : (currentIndex === session.questions.length - 1)
  const isFirstQuestion = currentIndex === 0
  const hasSubmittedCurrent = Boolean(answers[currentQuestion.id])
  const currentEvaluation = evaluations[currentQuestion.id]

  return (
    <div className="room-page">
      <section className="room-hero">
        <AnimatedMeshGradient />
        <div className="room-header">
          <div>
            <div className="badge-row" style={{ marginBottom: '8px' }}>
              <span className="badge badge-accent">
                {isCodingSession ? <Code2 size={13} /> : <Mic size={13} />}
                {isCodingSession ? 'Coding Interview Studio' : 'Verbal Interview Studio'}
              </span>
              <span className="pill-badge neutral" style={{ fontWeight: 600 }}>Role: {session.role}</span>
              <span className="pill-badge neutral">{session.experience_level}</span>
              {session.is_adaptive && (
                <span className="pill-badge sand" style={{ fontSize: '10px' }}>Adaptive Mode</span>
              )}
              <span className={`pill-badge ${session.saved_to_db ? 'olive' : 'neutral'}`}>
                {session.saved_to_db ? 'Atlas Persisted' : 'Active Memory'}
              </span>
              <span
                className={`pill-badge ${
                  isSessionExpired
                    ? 'terracotta'
                    : currentBand === 'concise'
                    ? 'terracotta'
                    : currentBand === 'focused'
                    ? 'sand'
                    : 'olive'
                }`}
                style={{
                  fontWeight: 700,
                  fontSize: '11px',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
                title={
                  isSessionExpired
                    ? 'Interview session time has expired'
                    : `Remaining: ${formatSessionTime(sessionRemaining)} (${currentBand.toUpperCase()} Band)`
                }
              >
                ⏱ {isSessionExpired ? 'Session Expired (0:00)' : `${formatSessionTime(sessionRemaining)} Left`}
                <span style={{ fontSize: '9px', opacity: 0.85 }}>[{currentBand.toUpperCase()}]</span>
              </span>
            </div>
            <h2>{isCodingSession ? 'Coding Interview' : 'Verbal Interview'}</h2>
            <p className="intro-copy" style={{ marginTop: '8px' }}>
              {isCodingSession
                ? 'Solve LeetCode-style algorithmic challenges in Monaco IDE with language selection, automated test cases, and real-time compiler execution.'
                : 'Practice delivering verbal responses assessing conceptual depth, system architecture, resume projects, and communication skills.'}
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <button className="icon-button" onClick={handleExitPractice} aria-label="Exit session"><X /></button>
          </div>
        </div>
      </section>

      {isAmbiguousSession && (
        <div
          className="status-callout warning"
          style={{
            margin: '16px 24px',
            padding: '16px',
            borderRadius: '12px',
            background: '#FEF2F2',
            border: '1.5px solid #FCA5A5',
            color: '#991B1B',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '12px',
          }}
          role="alert"
        >
          <AlertCircle style={{ width: '20px', height: '20px', flexShrink: 0, marginTop: '2px' }} />
          <div style={{ flex: 1 }}>
            <strong style={{ fontSize: '14px', display: 'block', marginBottom: '4px' }}>
              Inconsistent or Legacy Interview Session Detected
            </strong>
            <p style={{ margin: 0, fontSize: '13px', lineHeight: 1.5 }}>
              This interview session contains conflicting question types or unverified session mode metadata. Submissions are restricted to preserve evaluation integrity. Please restart a clean Coding Interview or Verbal Interview.
            </p>
            <div style={{ marginTop: '12px', display: 'flex', gap: '8px' }}>
              <button
                type="button"
                className="button button-primary"
                style={{ fontSize: '12px', padding: '6px 14px' }}
                onClick={() => {
                  setSession(null)
                  onExit()
                }}
              >
                Restart Fresh Interview Session
              </button>
            </div>
          </div>
        </div>
      )}

      <div className={`room-layout ${isCodingSession ? 'technical-view' : 'video-view'}`}>
        {isProctoredSession && (
          <section className={`camera-panel ${isCameraCollapsed ? 'is-collapsed' : ''}`}>
            <div
              className="camera-header-controls"
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '8px 14px',
                background: 'var(--surface-sunken)',
                borderBottom: '1px solid var(--border)',
              }}
            >
              <span style={{ fontSize: '11px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Video style={{ width: '13px', height: '13px', color: 'var(--accent)' }} />
                <span>Live Proctoring Video</span>
              </span>
              <button
                type="button"
                className="camera-collapse-btn"
                onClick={() => setIsCameraCollapsed((v) => !v)}
                aria-label={isCameraCollapsed ? 'Expand video preview' : 'Minimize video preview'}
                title={isCameraCollapsed ? 'Expand video preview' : 'Minimize video preview (monitoring remains active)'}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: '2px 6px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: '11px',
                  color: 'var(--muted)',
                }}
              >
                {isCameraCollapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
                <span>{isCameraCollapsed ? 'Expand' : 'Minimize'}</span>
              </button>
            </div>

            <div className="camera-frame">
              <video ref={setVideoRef} autoPlay muted playsInline aria-label="Camera preview" />
              {deviceState === 'idle' && (
                <div className="camera-overlay">
                  <Video aria-hidden="true" />
                  <h3>Camera and microphone are off</h3>
                  <p>Allow access when you&apos;re ready to begin. Video is mandatory for integrity monitoring.</p>
                  <button className="button button-primary" onClick={requestDevices}>Enable camera &amp; mic</button>
                </div>
              )}
              {deviceState === 'requesting' && (
                <div className="camera-overlay">
                  <Loader2 className="spinning" aria-hidden="true" style={{ width: '24px', height: '24px', margin: '0 auto 6px', color: '#818CF8' }} />
                  <h3 style={{ fontSize: '13px', margin: '0 0 4px' }}>Requesting Camera Access...</h3>
                  <p style={{ fontSize: '11px', margin: 0, color: '#94A3B8' }}>Please allow camera permissions in your browser prompt.</p>
                </div>
              )}
              {(deviceState === 'initializing' || (!videoFrameActive && deviceState === 'ready' && !isCameraInterrupted)) && (
                <div className="camera-status" style={{ background: 'rgba(30, 41, 59, 0.9)', color: '#94a3b8' }}>
                  <span className="status-dot" style={{ background: '#f59e0b' }} /> Initializing Proctoring Stream...
                </div>
              )}
              {(deviceState === 'denied' || deviceState === 'error') && !isCameraInterrupted && (
                <div className="camera-overlay">
                  <VideoOff aria-hidden="true" />
                  <h3>Device access unavailable</h3>
                  <p>{cameraErrorMessage || 'Check your browser permissions and camera connection, then try again.'}</p>
                  <button className="button button-secondary" onClick={requestDevices}>Try again</button>
                </div>
              )}
              {isCameraInterrupted && (
                <div className="camera-overlay" style={{ background: 'rgba(15, 23, 42, 0.92)' }}>
                  <VideoOff style={{ width: '28px', height: '28px', color: '#F87171', margin: '0 auto 8px' }} />
                  <h3 style={{ color: '#FEE2E2', fontSize: '13px', margin: '0 0 4px' }}>Camera Stream Interrupted</h3>
                  <p style={{ color: '#CBD5E1', fontSize: '11px', margin: '0 0 10px', maxWidth: '240px' }}>
                    {cameraErrorMessage || 'Video is mandatory for this interview. Please reconnect your camera or click retry to continue.'}
                  </p>
                  <button className="button button-primary" onClick={requestDevices} style={{ fontSize: '11px', padding: '4px 12px' }}>
                    Retry Camera Access
                  </button>
                </div>
              )}
              {deviceState === 'ready' && videoFrameActive && !isCameraInterrupted && (
                <>
                  {isListening ? (
                    <div className="camera-status" style={{ background: 'rgba(220, 38, 38, 0.9)', color: '#fff' }}>
                      <span className="status-dot" style={{ background: '#fff' }} /> Live Speech Recognition Active
                    </div>
                  ) : isAiSpeaking ? (
                    <div className="camera-status" style={{ background: 'rgba(67, 56, 168, 0.9)', color: '#fff' }}>
                      <span className="status-dot" style={{ background: '#c7d2fe' }} /> AI Interviewer Speaking...
                    </div>
                  ) : (
                    <div className="camera-status">
                      <span className="status-dot" /> Proctoring Stream Active
                    </div>
                  )}
                </>
              )}
            </div>

            {candidateAbsentAlert && (
              <div className="proctoring-banner warning" role="alert">
                <AlertCircle size={14} style={{ flexShrink: 0 }} />
                <span>Candidate not visible — please return to the camera frame.</span>
              </div>
            )}
            {multiplePeopleAlert && (
              <div className="proctoring-banner danger" role="alert">
                <AlertCircle size={14} style={{ flexShrink: 0 }} />
                <span>
                  Multiple people detected. Only the candidate should be visible during this interview. The presence of another person may be flagged as a potential integrity concern and may be considered during malpractice review.
                </span>
              </div>
            )}
            {activeCommAlert && (
              <div className="proctoring-banner warning" role="alert">
                <AlertCircle size={14} style={{ flexShrink: 0 }} />
                <span>{activeCommAlert}</span>
              </div>
            )}
            {faceDetectorNotice && (
              <div className="proctoring-banner info" role="status">
                <CircleHelp size={14} style={{ flexShrink: 0 }} />
                <span>{faceDetectorNotice}</span>
              </div>
            )}

            <div className="room-controls">
              <span className={`recording-time ${recording || isListening ? 'is-recording' : ''}`}>
                {(recording || isListening) && <span className="status-dot" />}
                {isListening ? `Speaking: ${formatTime}` : `Elapsed: ${formatTime}`}
              </span>
              <div className="control-group">
                <button
                  type="button"
                  className="round-control"
                  aria-label={deviceState === 'ready' ? (isListening ? 'Microphone listening' : 'Microphone ready') : 'Microphone unavailable'}
                  disabled={deviceState !== 'ready' || isCameraInterrupted}
                  onClick={isListening ? stopListening : startListening}
                  style={isListening ? { color: '#dc2626', borderColor: '#fca5a5' } : {}}
                  title={isListening ? 'Mute/Pause microphone' : 'Microphone enable/mute control'}
                >
                  <Mic />
                </button>
                <button
                  type="button"
                  className="round-control"
                  aria-label={deviceState === 'ready' && !isCameraInterrupted ? 'Camera active' : 'Camera unavailable'}
                  disabled={deviceState !== 'ready' || isCameraInterrupted}
                >
                  <Video />
                </button>
              </div>

              {!isCodingSession ? (
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  {!isListening ? (
                    <button
                      type="button"
                      className="button button-primary"
                      style={{ minHeight: '36px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '6px' }}
                      onClick={startListening}
                      disabled={deviceState === 'denied' || isCameraInterrupted}
                    >
                      <Mic style={{ width: '13px', height: '13px' }} />
                      Start Speaking
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="button"
                      style={{
                        minHeight: '36px',
                        fontSize: '11px',
                        background: '#dc2626',
                        color: '#fff',
                        border: '1px solid #b91c1c',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                      }}
                      onClick={stopListening}
                    >
                      <Square style={{ width: '13px', height: '13px' }} />
                      Stop Answer
                    </button>
                  )}
                  <button
                    type="button"
                    className="button button-secondary"
                    style={{ minHeight: '36px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '6px' }}
                    onClick={handleRetryAnswer}
                    disabled={!answerText && !interimTranscript}
                    title="Clear current transcription and restart answer"
                  >
                    <RotateCcw style={{ width: '13px', height: '13px' }} />
                    Retry Answer
                  </button>
                </div>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginLeft: 'auto' }}>
                  <span className="pill-badge olive" style={{ fontSize: '10px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                    <ShieldCheck style={{ width: '12px', height: '12px' }} />
                    <span>Live Proctoring Active</span>
                  </span>
                </div>
              )}
            </div>

            {!isCodingSession && micPermissionError && (
              <div className="status-callout error" style={{ margin: '12px 17px 0' }} role="alert">
                <AlertCircle style={{ width: '14px', height: '14px' }} />
                <div style={{ flex: 1, fontSize: '11px' }}>
                  <strong>Microphone Notice</strong>
                  <p style={{ margin: '2px 0 0' }}>{micPermissionError}</p>
                </div>
              </div>
            )}

            {!isCodingSession && (
              <div
                style={{
                  margin: '12px 17px 0',
                  padding: '9px 12px',
                  background: 'var(--surface-sunken)',
                  borderRadius: '8px',
                  border: '1px solid var(--border)',
                  fontSize: '11px',
                  color: 'var(--muted)',
                  lineHeight: 1.45,
                }}
              >
                <strong style={{ color: 'var(--foreground)' }}>Speech Transcription Engine:</strong> Features real-time browser preview and reliable server-side Groq Whisper transcription upon answer completion. Audio is securely processed and never permanently retained. You can edit your response or type manually at any time.
              </div>
            )}

            {/* Phase 4: Toggle Integrity Timeline button */}
            <div style={{ padding: '0 17px 14px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <button
                type="button"
                className="text-button"
                onClick={async () => {
                  const nextShow = !showTimeline
                  setShowTimeline(nextShow)
                  if (nextShow) {
                    setIsTimelineLoading(true)
                    setTimelineError(null)
                    try {
                      const res = await getIntegrityTimeline(session.session_id)
                      setTimelineEvents(res.events || [])
                    } catch (err: any) {
                      setTimelineError(err.message || 'Failed to fetch timeline')
                    } finally {
                      setIsTimelineLoading(false)
                    }
                  }
                }}
                style={{ cursor: 'pointer', fontSize: '11px', marginTop: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                <ShieldCheck style={{ width: '13px', height: '13px' }} />
                {showTimeline ? 'Hide Integrity Timeline' : `Integrity Timeline (${timelineEvents.length})`}
              </button>
              {showTimeline && (
                <button
                  type="button"
                  className="text-button"
                  onClick={async () => {
                    setIsTimelineLoading(true)
                    setTimelineError(null)
                    try {
                      const res = await getIntegrityTimeline(session.session_id)
                      setTimelineEvents(res.events || [])
                    } catch (err: any) {
                      setTimelineError(err.message || 'Failed to refresh timeline')
                    } finally {
                      setIsTimelineLoading(false)
                    }
                  }}
                  disabled={isTimelineLoading}
                  style={{ cursor: 'pointer', fontSize: '10px', marginTop: '12px', display: 'flex', alignItems: 'center', gap: '4px' }}
                >
                  <RotateCcw style={{ width: '11px', height: '11px' }} className={isTimelineLoading ? 'animate-spin' : ''} />
                  <span>Refresh</span>
                </button>
              )}
            </div>

            {/* Phase 4: Integrity Intelligence Timeline Card */}
            {showTimeline && (
              <div className="timeline-card" style={{ margin: '0 17px 17px', borderRadius: '12px', padding: '16px' }} role="region" aria-label="Integrity Timeline">
                <div className="timeline-header">
                  <div>
                    <h4 style={{ margin: 0, fontSize: '13px', fontWeight: 700 }}>Observable Session Events</h4>
                    <p className="timeline-disclaimer">
                      Neutral timeline of observed browser visibility, media status, and proctoring telemetry. Events are not labeled as proof of cheating.
                    </p>
                  </div>
                  <span className="pill-badge neutral">{timelineEvents.length} events</span>
                </div>

                {timelineError && (
                  <p style={{ margin: '6px 0', fontSize: '11px', color: '#dc2626' }}>{timelineError}</p>
                )}

                {isTimelineLoading ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '12px 0', fontSize: '11px', color: 'var(--muted)' }}>
                    <Loader2 className="animate-spin" size={14} />
                    <span>Loading integrity timeline events...</span>
                  </div>
                ) : timelineEvents.length === 0 ? (
                  <p style={{ margin: 0, fontSize: '11px', color: 'var(--muted)' }}>No browser presence or proctoring events recorded yet.</p>
                ) : (
                  <ul className="timeline-list">
                    {timelineEvents.map((evt, idx) => (
                      <li key={evt.event_id || idx} className="timeline-item">
                        <span className="timeline-time">
                          {new Date(evt.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </span>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                          <span className="timeline-desc">{formatTimelineLabel(evt.event_type)}</span>
                          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                            {evt.duration_seconds && (
                              <span style={{ fontSize: '9.5px', color: 'var(--muted)' }}>
                                Duration: {evt.duration_seconds}s
                              </span>
                            )}
                            {evt.detection_source && (
                              <span style={{ fontSize: '9.5px', color: 'var(--muted)' }}>
                                Source: {evt.detection_source}
                              </span>
                            )}
                            {evt.status && (
                              <span className={`pill-badge ${evt.status === 'resolved' ? 'olive' : evt.severity === 'warning' ? 'sand' : 'neutral'}`} style={{ fontSize: '8.5px', padding: '1px 5px' }}>
                                {evt.status}
                              </span>
                            )}
                          </div>
                        </div>
                        <span className="pill-badge neutral" style={{ fontSize: '9px', marginLeft: 'auto' }}>
                          {evt.event_type}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </section>
        )}

        <aside className="question-panel">
          <div className="question-progress">
            <span>
              {isCodingSession ? 'Coding Problem' : 'Verbal Question'} • Question 0{currentIndex + 1}
            </span>
            <span>{currentIndex + 1} of {session.target_question_count || session.questions.length}</span>
          </div>

          <div className="progress-track">
            <span style={{ width: `${((currentIndex + 1) / (session.target_question_count || session.questions.length)) * 100}%` }} />
          </div>

          {/* Question Index Navigator */}
          {session.questions.length > 1 && (
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '14px' }}>
              {session.questions.map((q, idx) => (
                <button
                  key={q.id || idx}
                  type="button"
                  className={`pill-badge ${idx === currentIndex ? 'terracotta' : answers[q.id] ? 'olive' : 'neutral'}`}
                  style={{
                    cursor: 'pointer',
                    border: '1px solid var(--border)',
                    fontSize: '11px',
                    padding: '3px 10px',
                  }}
                  onClick={() => setCurrentIndex(idx)}
                  title={`Navigate to Question ${idx + 1}`}
                >
                  Question {idx + 1} {answers[q.id] ? '✓' : ''}
                </button>
              ))}
            </div>
          )}

          {/* Unified AI Voice & Question Display for both Technical and Video modes */}
          <div className="voice-interviewer-card" role="region" aria-label="AI Interviewer Question">
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '12px',
                paddingBottom: '10px',
                borderBottom: '1px solid rgba(67, 56, 168, 0.12)',
                flexWrap: 'wrap',
                gap: '8px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="badge badge-accent" style={{ fontSize: '11px' }}>
                  <Volume2 style={{ width: '12px', height: '12px' }} />
                  AI Interviewer (Spoken Audio)
                </span>
                {isAiSpeaking ? (
                  <span className="voice-speaking-indicator">
                    <span className="voice-soundwave"><span /><span /><span /><span /></span>
                    Speaking question aloud...
                  </span>
                ) : (
                  <span className="pill-badge neutral" style={{ fontSize: '10px' }}>
                    {ttsSupported ? 'Voice Ready' : 'Text Fallback Mode'}
                  </span>
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <button
                  type="button"
                  className="button button-secondary"
                  style={{ minHeight: '26px', fontSize: '10px', padding: '2px 9px', display: 'flex', alignItems: 'center', gap: '4px' }}
                  onClick={() => speakQuestion(currentQuestion.text)}
                  disabled={isAiSpeaking}
                  title="Listen to the question spoken aloud again"
                >
                  <Volume2 style={{ width: '12px', height: '12px' }} />
                  Replay Question
                </button>
                <button
                  type="button"
                  className="icon-button"
                  style={{ width: '26px', height: '26px' }}
                  onClick={() => {
                    if (autoSpeakEnabled) {
                      stopAiSpeech()
                      setAutoSpeakEnabled(false)
                    } else {
                      setAutoSpeakEnabled(true)
                      speakQuestion(currentQuestion.text)
                    }
                  }}
                  title={autoSpeakEnabled ? 'Mute AI voice auto-playback' : 'Enable AI voice auto-playback'}
                  aria-label={autoSpeakEnabled ? 'Mute AI voice auto-playback' : 'Enable AI voice auto-playback'}
                >
                  {autoSpeakEnabled ? <Volume2 style={{ width: '13px', height: '13px' }} /> : <VolumeX style={{ width: '13px', height: '13px' }} />}
                </button>
              </div>
            </div>

            <div className="badge-row" style={{ marginBottom: '10px' }}>
              <span className="pill-badge terracotta">{currentQuestion.assessed_skill}</span>
              <span className="pill-badge olive">{currentQuestion.difficulty}</span>
              {currentQuestion.time_band && (
                <span
                  className={`pill-badge ${
                    currentQuestion.time_band === 'concise'
                      ? 'terracotta'
                      : currentQuestion.time_band === 'focused'
                      ? 'sand'
                      : 'olive'
                  }`}
                  style={{ fontSize: '10px', textTransform: 'capitalize' }}
                >
                  ⏱ {currentQuestion.time_band} Band
                </span>
              )}
              {currentQuestion.question_type && (
                <span className="pill-badge neutral" style={{ fontSize: '10px', fontWeight: 650 }}>
                  Type: {currentQuestion.question_type.toUpperCase()}
                </span>
              )}
              <span className="pill-badge accent" style={{ fontSize: '10px', fontWeight: 700 }}>
                Active Mode: {activeMode.toUpperCase()}
              </span>
              {session.is_adaptive && (
                <span className="pill-badge sand" style={{ fontSize: '10px' }}>Adapted Tier</span>
              )}
            </div>
            <h3>{currentQuestion.text}</h3>
            {currentQuestion.selection_rationale && (
              <div className="rationale-card" role="note" aria-label="Question Selection Rationale">
                <strong>Selection Rationale:</strong> {currentQuestion.selection_rationale}
              </div>
            )}
            <div className="rubric-card">
              <strong>Evaluation rubric:</strong> {currentQuestion.rubric}
            </div>

            {/* Module 01: Competency Evidence Tracker */}
            {competencyState && competencyState.skills && Object.keys(competencyState.skills).length > 0 && (
              <div className="competency-tracker" role="region" aria-label="Assessed Competencies">
                <div className="competency-tracker-header">
                  <span style={{ fontSize: '11px', fontWeight: 700, color: '#5f5363', textTransform: 'uppercase', letterSpacing: '.06em' }}>
                    Assessed Competencies
                  </span>
                  <span style={{ fontSize: '10px', color: 'var(--muted)' }}>
                    Evidence Tracker
                  </span>
                </div>
                <div className="competency-tracker-grid">
                  {Object.entries(competencyState.skills).map(([skillName, skillData]) => {
                    const label =
                      skillData.status === 'demonstrated'
                        ? 'Demonstrated'
                        : skillData.status === 'needs_further_assessment'
                        ? 'Needs Assessment'
                        : 'Not Assessed'
                    return (
                      <span
                        key={skillName}
                        className={`competency-chip ${skillData.status}`}
                        title={`${skillName}: ${label} (${skillData.questions_evaluated} evaluated answers)`}
                      >
                        <span>{skillName}</span>
                        <span style={{ fontSize: '9px', opacity: 0.85 }}>({label})</span>
                      </span>
                    )
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Module 01: Answer Mode Selector */}
          <div
            className="answer-mode-selector-bar"
            role="region"
            aria-label="Answer Mode Selection"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '12px',
              padding: '12px 16px',
              background: '#FFFFFF',
              border: '1px solid var(--border)',
              borderRadius: '10px',
              marginTop: '12px',
              marginBottom: '6px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '12px', fontWeight: 700, color: '#334155', textTransform: 'uppercase', letterSpacing: '.05em' }}>
                Answer Mode:
              </span>
              <span style={{ fontSize: '11px', color: 'var(--muted)' }}>
                Choose how you want to solve and submit this question
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              {availableModes.map((mode) => {
                const isSelected = activeMode === mode
                const isRec = recommendedMode === mode

                const modeMeta: Record<string, { label: string; icon: any; desc: string }> = {
                  coding: { label: 'Coding Mode', icon: Code2, desc: 'Interactive IDE with sandbox compiler & test cases' },
                  sql: { label: 'SQL Mode', icon: Database, desc: 'Query editor & authorized SQLite relational sandbox' },
                  system_design: { label: 'System Design Mode', icon: Layers, desc: 'Architectural specifications, schemas, scaling & trade-offs' },
                  verbal: { label: 'Verbal / Spoken Mode', icon: Mic, desc: 'Spoken transcription or structured written explanation' },
                  multiple_choice: { label: 'Multiple Choice Mode', icon: CheckSquare, desc: 'Concept verification option cards' },
                }

                const meta = modeMeta[mode] || { label: `${mode.toUpperCase()} Mode`, icon: Code2, desc: '' }
                const ModeIcon = meta.icon

                return (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setSelectedAnswerMode(mode)}
                    disabled={submitting || evaluating || adapting}
                    title={meta.desc}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '6px 12px',
                      borderRadius: '6px',
                      fontSize: '12px',
                      fontWeight: isSelected ? 700 : 500,
                      border: isSelected ? '1.5px solid var(--accent)' : '1px solid #E2E8F0',
                      background: isSelected ? 'var(--accent-soft)' : '#F8FAFC',
                      color: isSelected ? 'var(--accent)' : '#475569',
                      cursor: submitting || evaluating || adapting ? 'not-allowed' : 'pointer',
                      transition: 'all 120ms ease',
                    }}
                  >
                    <ModeIcon size={14} />
                    <span>{meta.label}</span>
                    {isRec && (
                      <span
                        style={{
                          fontSize: '9px',
                          fontWeight: 700,
                          padding: '1px 5px',
                          borderRadius: '4px',
                          background: isSelected ? 'var(--accent)' : '#E2E8F0',
                          color: isSelected ? '#FFFFFF' : '#475569',
                          textTransform: 'uppercase',
                          letterSpacing: '.04em',
                        }}
                      >
                        Recommended
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>

          {/* ========================================================= */}
          {/* CONDITIONAL WORKSPACES STRICTLY BASED ON ACTIVE ANSWER MODE */}
          {/* ========================================================= */}

          {/* 1. CODING & SQL QUESTIONS -> Professional Multimodal IDE */}
          {(isCodingMode || isSqlMode) && (
            <div className="technical-workspace-wrapper" style={{ width: '100%', minWidth: 0, marginTop: '8px' }}>
              <MultimodalInterviewIDE
                key={`${currentQuestion.id}-${activeMode}`}
                question={currentQuestion}
                sessionId={session.session_id}
                modeOverride={isSqlMode ? 'sql' : 'coding'}
                initialDrafts={session.drafts}
                onDraftSaved={(qId, lang, draft) => {
                  latestSolutionDataRef.current[qId] = {
                    ...latestSolutionDataRef.current[qId],
                    code: draft.code,
                    language: lang,
                  }
                  setSession((prev) => {
                    if (!prev) return prev
                    return {
                      ...prev,
                      drafts: {
                        ...(prev.drafts || {}),
                        [qId]: {
                          ...((prev.drafts && prev.drafts[qId]) || {}),
                          [lang]: draft,
                        },
                      },
                    }
                  })
                }}
                onAnswerSaved={handleAnswerSavedFromIde}
                onEvaluationTriggered={handleEvaluateAnswer}
                onSubmitSolution={handleAdaptiveSubmission}
                isSubmitting={submitting || adapting}
                isEvaluating={evaluating || adapting}
                onNavigateNext={handleNavigateNext}
                onNavigatePrevious={handleNavigatePrevious}
                hasNextQuestion={!isLastQuestion}
                hasPreviousQuestion={!isFirstQuestion}
                isLastQuestion={isLastQuestion}
                isNavigating={isNavigating || generatingNext}
                onFinishInterview={handleCompleteAndReport}
              />
              {adapting && (
                <div
                  className="status-callout info"
                  style={{
                    marginTop: '12px',
                    padding: '10px 14px',
                    borderRadius: '8px',
                    background: '#EEF2FF',
                    border: '1px solid #C7D2FE',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    fontSize: '12px',
                    color: '#3730A3',
                  }}
                >
                  <Loader2 className="animate-spin" size={16} />
                  <span>Evaluating code submission against configured test cases and adapting next question...</span>
                </div>
              )}
            </div>
          )}

          {/* 2. SYSTEM DESIGN QUESTIONS -> Architectural Proposal Studio */}
          {isSystemDesignMode && (
            <div className="system-design-workspace" style={{ width: '100%', minWidth: 0, marginTop: '8px' }}>
              <div
                style={{
                  padding: '12px 16px',
                  background: '#F8FAFC',
                  border: '1px solid #E2E8F0',
                  borderRadius: '8px',
                  marginBottom: '14px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                  <Database size={15} color="var(--accent)" />
                  <strong style={{ fontSize: '12.5px', color: '#1E293B' }}>System Architecture &amp; Design Rubric</strong>
                </div>
                <p style={{ margin: '0 0 8px', fontSize: '11.5px', color: '#475569', lineHeight: 1.5 }}>
                  Structure your proposal systematically: functional &amp; non-functional scope, high-level architecture, core services &amp; APIs, data models &amp; storage choices, scalability bottlenecks, and resilience trade-offs.
                </p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  <span className="pill-badge neutral" style={{ fontSize: '10px' }}>1. Scope &amp; Scale Estimation</span>
                  <span className="pill-badge neutral" style={{ fontSize: '10px' }}>2. High-Level Architecture</span>
                  <span className="pill-badge neutral" style={{ fontSize: '10px' }}>3. Data Storage &amp; Schemas</span>
                  <span className="pill-badge neutral" style={{ fontSize: '10px' }}>4. Partitioning &amp; Caching</span>
                  <span className="pill-badge neutral" style={{ fontSize: '10px' }}>5. Failure Modes &amp; Trade-offs</span>
                </div>
              </div>

              <div className="answer-box">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <label htmlFor="design-answer-input" className="form-label" style={{ margin: 0 }}>
                    Architectural Design Specification
                  </label>
                  <span style={{ fontSize: '11px', color: 'var(--muted)' }}>
                    {answerText.trim() ? answerText.trim().split(/\s+/).filter(Boolean).length : 0} words
                  </span>
                </div>

                <textarea
                  id="design-answer-input"
                  className="form-textarea"
                  rows={10}
                  placeholder="### 1. Requirements & Scope&#10;- Functional requirements&#10;- Non-functional requirements (Scale, Latency, Availability)&#10;&#10;### 2. High-Level Architecture&#10;- Client -> CDN -> Load Balancer -> API Services&#10;&#10;### 3. Data Storage & Schemas&#10;- Relational vs NoSQL, Caching Strategy&#10;&#10;### 4. Scalability & Bottlenecks&#10;- Horizontal partitioning, sharding, message queues&#10;&#10;### 5. Trade-offs & Resilience&#10;- CAP theorem choices, circuit breakers, recovery"
                  value={answerText}
                  onChange={(e) => setAnswerText(e.target.value)}
                  disabled={submitting || evaluating || adapting}
                />

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', marginTop: '10px' }}>
                  <div>
                    {submitMessage && (
                      <span style={{ fontSize: '11px', color: '#166534', display: 'flex', alignItems: 'center', gap: '5px' }}>
                        <CheckCircle2 style={{ width: '13px', height: '13px' }} /> {submitMessage}
                      </span>
                    )}
                    {submitError && (
                      <span style={{ fontSize: '11px', color: '#9c2a2a', display: 'flex', alignItems: 'center', gap: '5px' }}>
                        <AlertCircle style={{ width: '13px', height: '13px' }} /> {submitError}
                      </span>
                    )}
                  </div>

                  <div style={{ display: 'flex', gap: '8px', marginLeft: 'auto', flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      className="button button-secondary"
                      style={{ minHeight: '36px', fontSize: '11px' }}
                      onClick={handleRetryAnswer}
                      disabled={!answerText.trim()}
                    >
                      <RotateCcw style={{ width: '13px', height: '13px' }} />
                      Clear
                    </button>

                    <button
                      type="button"
                      className="button button-primary"
                      style={{ minHeight: '36px', fontSize: '11px' }}
                      onClick={() => handleAdaptiveSubmission({ answer_text: answerText })}
                      disabled={submitting || evaluating || adapting || !answerText.trim()}
                    >
                      {adapting ? (
                        <>
                          <Loader2 className="animate-spin" style={{ width: '13px', height: '13px' }} />
                          Submitting &amp; Adapting...
                        </>
                      ) : (
                        <>
                          <Send style={{ width: '13px', height: '13px' }} />
                          Submit System Design &amp; Continue
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* 3. MULTIPLE CHOICE QUESTIONS -> Selection Cards Studio */}
          {isMultipleChoiceMode && (
            <div className="mcq-workspace" style={{ width: '100%', minWidth: 0, marginTop: '8px' }}>
              <div className="answer-box">
                <label className="form-label" style={{ marginBottom: '12px' }}>
                  Select the best option:
                </label>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {(currentQuestion.options && currentQuestion.options.length > 0
                    ? currentQuestion.options
                    : ['Option A', 'Option B', 'Option C', 'Option D']
                  ).map((opt: string, oIdx: number) => {
                    const isSelected = selectedMcOption === opt || answerText.trim() === opt
                    return (
                      <button
                        key={oIdx}
                        type="button"
                        onClick={() => {
                          setSelectedMcOption(opt)
                          setAnswerText(opt)
                        }}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '12px',
                          padding: '12px 16px',
                          borderRadius: '8px',
                          border: isSelected ? '2px solid var(--accent)' : '1px solid var(--border)',
                          background: isSelected ? 'var(--accent-soft)' : '#FFFFFF',
                          cursor: 'pointer',
                          textAlign: 'left',
                          transition: 'all 120ms ease',
                        }}
                      >
                        <span
                          style={{
                            fontWeight: 700,
                            minWidth: '24px',
                            color: isSelected ? 'var(--accent)' : 'var(--muted)',
                          }}
                        >
                          {String.fromCharCode(65 + oIdx)}.
                        </span>
                        <span style={{ fontSize: '13px', color: 'var(--foreground)' }}>{opt}</span>
                      </button>
                    )
                  })}
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '16px' }}>
                  <button
                    type="button"
                    className="button button-primary"
                    style={{ minHeight: '36px', fontSize: '11px' }}
                    onClick={() => handleAdaptiveSubmission({ answer_text: answerText || selectedMcOption || '' })}
                    disabled={submitting || evaluating || adapting || (!answerText && !selectedMcOption)}
                  >
                    {adapting ? (
                      <>
                        <Loader2 className="animate-spin" style={{ width: '13px', height: '13px' }} />
                        Submitting &amp; Adapting...
                      </>
                    ) : (
                      <>
                        <Send style={{ width: '13px', height: '13px' }} />
                        Submit Answer &amp; Continue
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* 4. VERBAL QUESTIONS -> Spoken Voice & Text Response Studio */}
          {isVerbalMode && (
            <div className="verbal-workspace-wrapper" style={{ width: '100%', minWidth: 0, marginTop: '8px' }}>
              <div className="answer-box">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <label htmlFor="answer-input" className="form-label" style={{ margin: 0 }}>
                    {roomMode === 'video' ? 'Spoken Answer Live Transcript' : 'Your Verbal Response'}
                  </label>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {isListening && (
                      <span className="live-listening-badge">
                        <span className="pulse-mic-dot" /> Listening...
                      </span>
                    )}
                    <span style={{ fontSize: '11px', color: 'var(--muted)' }}>
                      {answerText.trim() ? answerText.trim().split(/\s+/).filter(Boolean).length : 0} words
                    </span>
                  </div>
                </div>

                {/* Real-time interim preview box */}
                {interimTranscript && (
                  <div className="live-interim-box" aria-live="polite">
                    <span className="live-interim-label">Recognizing:</span>
                    <span className="live-interim-text"> &ldquo;{interimTranscript}&rdquo;</span>
                  </div>
                )}

                {isTranscribing && (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '7px 12px',
                      background: 'rgba(67, 56, 168, 0.08)',
                      color: '#4338ca',
                      borderRadius: '6px',
                      fontSize: '11px',
                      fontWeight: 500,
                      marginBottom: '8px',
                    }}
                  >
                    <Loader2 className="animate-spin" style={{ width: '13px', height: '13px' }} />
                    <span>Transcribing audio recording via Groq Whisper...</span>
                  </div>
                )}

                {transcriptionError && (
                  <div
                    className="status-callout error"
                    style={{ marginBottom: '8px', padding: '6px 10px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '8px' }}
                    role="alert"
                  >
                    <AlertCircle style={{ width: '13px', height: '13px', flexShrink: 0 }} />
                    <span style={{ flex: 1 }}>{transcriptionError}</span>
                    <button
                      type="button"
                      className="icon-button"
                      style={{ width: '18px', height: '18px', padding: 0 }}
                      onClick={() => setTranscriptionError(null)}
                      aria-label="Dismiss error"
                    >
                      <X style={{ width: '11px', height: '11px' }} />
                    </button>
                  </div>
                )}

                <textarea
                  id="answer-input"
                  className="form-textarea"
                  rows={6}
                  placeholder={
                    roomMode === 'video'
                      ? 'Speak clearly into your microphone or click "Start Speaking". Your spoken response will transcribe live and finish with server-side Groq Whisper. You can edit, format, or type manually at any time.'
                      : 'Structure your verbal response using the STAR method: Situation, Task, Action, and Result...'
                  }
                  value={answerText}
                  onChange={(e) => setAnswerText(e.target.value)}
                  disabled={submitting || evaluating || adapting}
                />

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', marginTop: '10px' }}>
                  <div>
                    {submitMessage && (
                      <span style={{ fontSize: '11px', color: '#166534', display: 'flex', alignItems: 'center', gap: '5px' }}>
                        <CheckCircle2 style={{ width: '13px', height: '13px' }} /> {submitMessage}
                      </span>
                    )}
                    {submitError && (
                      <span style={{ fontSize: '11px', color: '#9c2a2a', display: 'flex', alignItems: 'center', gap: '5px' }}>
                        <AlertCircle style={{ width: '13px', height: '13px' }} /> {submitError}
                      </span>
                    )}
                    {evalError && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: '11px', color: '#9c2a2a', display: 'flex', alignItems: 'center', gap: '5px' }}>
                          <AlertCircle style={{ width: '13px', height: '13px' }} /> {evalError}
                        </span>
                        <button
                          type="button"
                          className="button button-secondary"
                          style={{ minHeight: '24px', fontSize: '10px', padding: '1px 8px' }}
                          onClick={handleEvaluateAnswer}
                          disabled={evaluating}
                        >
                          Retry Evaluation
                        </button>
                      </div>
                    )}
                  </div>

                  <div style={{ display: 'flex', gap: '8px', marginLeft: 'auto', flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      className="button button-secondary"
                      style={{ minHeight: '36px', fontSize: '11px' }}
                      onClick={handleRetryAnswer}
                      disabled={!answerText && !interimTranscript}
                    >
                      <RotateCcw style={{ width: '13px', height: '13px' }} />
                      Clear / Retry
                    </button>

                    <button
                      type="button"
                      className="button button-secondary"
                      style={{ minHeight: '36px', fontSize: '11px' }}
                      onClick={handleEvaluateAnswer}
                      disabled={submitting || evaluating || adapting || !answerText.trim()}
                    >
                      {evaluating ? (
                        <>
                          <Loader2 className="animate-spin" style={{ width: '13px', height: '13px' }} />
                          Evaluating...
                        </>
                      ) : (
                        <>
                          <Sparkles style={{ width: '13px', height: '13px' }} />
                          {currentEvaluation ? 'Re-evaluate with Coach' : 'Evaluate with AI Coach'}
                        </>
                      )}
                    </button>

                    <button
                      type="button"
                      className="button button-primary"
                      style={{ minHeight: '36px', fontSize: '11px' }}
                      onClick={() => handleAdaptiveSubmission({ answer_text: answerText, answer_mode: activeMode })}
                      disabled={submitting || evaluating || adapting || !answerText.trim()}
                    >
                      {adapting ? (
                        <>
                          <Loader2 className="animate-spin" style={{ width: '13px', height: '13px' }} />
                          Submitting &amp; Adapting...
                        </>
                      ) : (
                        <>
                          <Send style={{ width: '13px', height: '13px' }} />
                          Submit Answer &amp; Continue
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Phase 3 & 6: AI Answer Evaluation & Spoken Voice Communication Coach Card */}
          {currentEvaluation && (
            <div className="eval-card" role="region" aria-label="Evaluation Results">
              <div className="eval-header">
                <div>
                  <div className="badge-row" style={{ marginBottom: '4px' }}>
                    <span className="eyebrow" style={{ color: 'var(--accent)' }}>AI Evaluation</span>
                    <span className={`pill-badge ${currentEvaluation.saved_to_db ? 'olive' : 'neutral'}`}>
                      {currentEvaluation.saved_to_db ? 'Atlas Stored' : 'Active Memory'}
                    </span>
                  </div>
                  <h4 style={{ margin: 0, fontSize: '15px', fontWeight: 700 }}>Performance Assessment</h4>
                </div>
                <div className="score-badge" aria-label={`Overall Score ${currentEvaluation.overall_score} out of 100`}>
                  <span className="score-val">{currentEvaluation.overall_score}</span>
                  <span className="score-denom">/ 100</span>
                </div>
              </div>

              {/* Criterion scores breakdown */}
              <div>
                <p className="form-label" style={{ marginBottom: '8px' }}>Competency Criteria</p>
                <div className="criterion-grid">
                  <div className="criterion-item">
                    <div className="criterion-top">
                      <span>Relevance</span>
                      <span className="criterion-score">{currentEvaluation.criterion_scores.relevance.score}/10</span>
                    </div>
                    <p className="criterion-feedback">{currentEvaluation.criterion_scores.relevance.feedback}</p>
                  </div>

                  <div className="criterion-item">
                    <div className="criterion-top">
                      <span>Technical Depth</span>
                      <span className="criterion-score">{currentEvaluation.criterion_scores.technical_depth.score}/10</span>
                    </div>
                    <p className="criterion-feedback">{currentEvaluation.criterion_scores.technical_depth.feedback}</p>
                  </div>

                  <div className="criterion-item">
                    <div className="criterion-top">
                      <span>Completeness</span>
                      <span className="criterion-score">{currentEvaluation.criterion_scores.completeness.score}/10</span>
                    </div>
                    <p className="criterion-feedback">{currentEvaluation.criterion_scores.completeness.feedback}</p>
                  </div>

                  <div className="criterion-item">
                    <div className="criterion-top">
                      <span>Structure &amp; Flow</span>
                      <span className="criterion-score">{currentEvaluation.criterion_scores.structure_flow.score}/10</span>
                    </div>
                    <p className="criterion-feedback">{currentEvaluation.criterion_scores.structure_flow.feedback}</p>
                  </div>

                  <div className="criterion-item">
                    <div className="criterion-top">
                      <span>Clarity &amp; Conciseness</span>
                      <span className="criterion-score">{currentEvaluation.criterion_scores.clarity_conciseness.score}/10</span>
                    </div>
                    <p className="criterion-feedback">{currentEvaluation.criterion_scores.clarity_conciseness.feedback}</p>
                  </div>

                  {currentEvaluation.criterion_scores.star_structure && (
                    <div className="criterion-item">
                      <div className="criterion-top">
                        <span>STAR Framework</span>
                        <span className="criterion-score">{currentEvaluation.criterion_scores.star_structure.score}/10</span>
                      </div>
                      <p className="criterion-feedback">{currentEvaluation.criterion_scores.star_structure.feedback}</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Communication Coach Box */}
              <div className="coach-box">
                <div className="coach-heading">
                  <Sparkles />
                  <span>Communication Coach</span>
                </div>
                <p className="coach-copy">{currentEvaluation.coaching_summary}</p>
                <p className="form-hint" style={{ color: '#8e7a84' }}>
                  *Coaching evaluated based on verbal transcript content, logical structure, clarity, and conciseness.
                </p>
              </div>

              {/* Strengths & Improvement Areas */}
              <div className="eval-lists">
                <div className="eval-list-group">
                  <h4>Key Strengths</h4>
                  <ul className="eval-list">
                    {currentEvaluation.strengths.map((str, i) => (
                      <li key={i}>{str}</li>
                    ))}
                  </ul>
                </div>

                <div className="eval-list-group">
                  <h4>Areas to Improve</h4>
                  <ul className="eval-list">
                    {currentEvaluation.areas_for_improvement.map((area, i) => (
                      <li key={i}>{area}</li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Actionable Suggestions */}
              {currentEvaluation.actionable_suggestions.length > 0 && (
                <div>
                  <p className="form-label" style={{ marginBottom: '6px' }}>Actionable Recommendations</p>
                  <ul className="eval-list">
                    {currentEvaluation.actionable_suggestions.map((sug, i) => (
                      <li key={i}>{sug}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Stronger Example Answer Card */}
              {currentEvaluation.stronger_example_answer && (
                <div className="example-answer-card">
                  <div className="example-answer-header">
                    <Sparkles style={{ width: '13px', height: '13px', color: 'var(--accent)' }} />
                    <span>Stronger Example Answer (Demonstration Model)</span>
                    <span className="pill-badge neutral" style={{ marginLeft: 'auto', fontSize: '9px' }}>AI Model Example</span>
                  </div>
                  <p className="example-answer-text">
                    {currentEvaluation.stronger_example_answer}
                  </p>
                  <p className="example-answer-disclaimer">
                    *Illustrative benchmark demonstration. This example was synthesized by the AI coach to demonstrate ideal structure, technical specificity, and conciseness.
                  </p>
                </div>
              )}

              {/* Recommended Practice Drill Card */}
              {currentEvaluation.recommended_practice && (
                <div className="practice-card-box">
                  <div className="practice-card-header">
                    <BookOpenCheck style={{ width: '13px', height: '13px', color: '#166534' }} />
                    <span>Targeted Practice Drill</span>
                  </div>
                  <p className="practice-card-copy">
                    {currentEvaluation.recommended_practice}
                  </p>
                </div>
              )}

              {/* Acoustic Analysis Disclaimer */}
              <div
                style={{
                  marginTop: '12px',
                  padding: '9px 12px',
                  borderRadius: '8px',
                  background: 'rgba(99, 102, 241, 0.05)',
                  border: '1px solid rgba(99, 102, 241, 0.16)',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '8px',
                }}
                role="note"
                aria-label="Acoustic Delivery Notice"
              >
                <MicOff style={{ width: '14px', height: '14px', color: 'var(--accent)', marginTop: '1px', flexShrink: 0 }} />
                <span style={{ fontSize: '11px', lineHeight: 1.45, color: 'var(--muted)' }}>
                  {currentEvaluation.acoustic_disclaimer ||
                    'Pronunciation, pitch, vocal confidence, and acoustic voice-quality analysis were not performed; evaluation is based on verbal transcript content, logical structure, and clarity.'}
                </span>
              </div>

              {/* Decision Support Advisory Notice */}
              <div
                style={{
                  marginTop: '10px',
                  padding: '9px 12px',
                  borderRadius: '8px',
                  background: 'rgba(166, 93, 131, 0.05)',
                  border: '1px solid rgba(166, 93, 131, 0.16)',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '8px',
                }}
                role="note"
                aria-label="Decision Support Advisory"
              >
                <ShieldCheck style={{ width: '14px', height: '14px', color: 'var(--accent)', marginTop: '1px', flexShrink: 0 }} />
                <span style={{ fontSize: '11px', lineHeight: 1.45, color: 'var(--muted)' }}>
                  {currentEvaluation.decision_support_disclaimer ||
                    'AI evaluation provides advisory feedback and coaching evidence. It is a decision support signal, not an automated or definitive hiring decision.'}
                </span>
              </div>
            </div>
          )}

          <div className="question-nav-bar">
            <button
              type="button"
              className="button button-secondary"
              style={{ minHeight: '36px', fontSize: '11px' }}
              disabled={isFirstQuestion || isNavigating}
              onClick={handleNavigatePrevious}
            >
              <ChevronLeft style={{ width: '14px', height: '14px' }} /> Previous
            </button>

            {!isLastQuestion ? (
              <button
                type="button"
                className="button button-secondary"
                style={{ minHeight: '36px', fontSize: '11px' }}
                disabled={isNavigating || generatingNext}
                onClick={handleNavigateNext}
                title="Navigate to next question without submitting"
              >
                {generatingNext ? (
                  <>
                    <Loader2 className="animate-spin" style={{ width: '13px', height: '13px' }} />
                    Generating Next Question...
                  </>
                ) : (
                  <>
                    Next <ChevronRight style={{ width: '14px', height: '14px' }} />
                  </>
                )}
              </button>
            ) : (
              <button
                type="button"
                className="button button-primary"
                style={{ minHeight: '36px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '6px' }}
                onClick={handleCompleteAndReport}
                disabled={generatingReport || isNavigating}
              >
                {generatingReport ? (
                  <>
                    <Loader2 className="animate-spin" style={{ width: '13px', height: '13px' }} />
                    Generating Report...
                  </>
                ) : (
                  <>
                    <Award style={{ width: '13px', height: '13px' }} />
                    Finalize &amp; View Performance Report
                  </>
                )}
              </button>
            )}
          </div>

          {adaptationNotice && (
            <div
              className="status-callout info"
              style={{
                marginTop: '12px',
                padding: '9px 12px',
                borderRadius: '8px',
                background: '#EEF2FF',
                border: '1px solid #C7D2FE',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '11.5px',
                color: '#3730A3',
              }}
            >
              <Sparkles style={{ width: '14px', height: '14px', color: 'var(--accent)', flexShrink: 0 }} />
              <span>{adaptationNotice}</span>
            </div>
          )}

          {nextQuestionError && (
            <div className="status-callout error" style={{ marginTop: '12px' }} role="alert">
              <AlertCircle style={{ width: '14px', height: '14px' }} />
              <div style={{ flex: 1 }}>
                <strong>Adaptation Error</strong>
                <p className="form-hint" style={{ margin: '2px 0 6px' }}>{nextQuestionError}</p>
                <button
                  type="button"
                  className="button button-secondary"
                  style={{ minHeight: '28px', fontSize: '10px', padding: '2px 10px' }}
                  onClick={handleGenerateNextQuestion}
                  disabled={generatingNext}
                >
                  Retry Next Question
                </button>
              </div>
            </div>
          )}

          {onViewReport && (
            <div style={{ marginTop: '16px', paddingTop: '14px', borderTop: '1px solid var(--border)' }}>
              <button
                type="button"
                className="button button-primary"
                style={{ width: '100%', minHeight: '38px', fontSize: '11px' }}
                onClick={handleCompleteAndReport}
                disabled={generatingReport}
              >
                {generatingReport ? (
                  <>
                    <Loader2 className="animate-spin" style={{ width: '14px', height: '14px' }} />
                    Generating Final Report...
                  </>
                ) : (
                  <>
                    <FileText style={{ width: '14px', height: '14px' }} />
                    Complete Session &amp; View Final Report
                  </>
                )}
              </button>
              {reportError && (
                <p style={{ margin: '6px 0 0', fontSize: '11px', color: '#9c2a2a' }}>{reportError}</p>
              )}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '16px' }}>
            <button className="exit-link" onClick={() => setSession(null)}>
              <RotateCcw style={{ width: '12px', height: '12px', display: 'inline', marginRight: '4px' }} />
              Reset session setup
            </button>
            <button className="exit-link" onClick={handleExitPractice}>Exit practice</button>
          </div>
        </aside>
      </div>
    </div>
  )
}

function SkillGapView({
  onStartInterview,
}: {
  onStartInterview: (session: InterviewSessionResponse) => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [targetRole, setTargetRole] = useState('Full Stack Engineer')
  const [experienceLevel, setExperienceLevel] = useState('Mid-Level')
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<ResumeAnalysisResult | null>(null)
  const [activeCategory, setActiveCategory] = useState<string>('All')
  const [startingSession, setStartingSession] = useState(false)
  const [useAdaptive, setUseAdaptive] = useState(true)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Role Catalog state
  const [supportedRoles, setSupportedRoles] = useState<RoleDefinition[]>([])
  const [loadingRoles, setLoadingRoles] = useState(false)
  const [updatingRole, setUpdatingRole] = useState(false)
  const [roleUpdateSuccess, setRoleUpdateSuccess] = useState<string | null>(null)

  // Skill Correction state
  const [editedSkills, setEditedSkills] = useState<string[]>([])
  const [newSkillInput, setNewSkillInput] = useState('')
  const [savingSkills, setSavingSkills] = useState(false)
  const [skillSaveSuccess, setSkillSaveSuccess] = useState<string | null>(null)

  // Load existing resume analysis & supported roles on mount
  useEffect(() => {
    let isMounted = true
    async function init() {
      try {
        setLoadingRoles(true)
        const [rolesRes, existingResumeRes] = await Promise.allSettled([
          getSupportedRoles(),
          getMyResume(),
        ])
        if (isMounted) {
          if (rolesRes.status === 'fulfilled' && rolesRes.value) {
            setSupportedRoles(rolesRes.value)
          }
          if (existingResumeRes.status === 'fulfilled' && existingResumeRes.value) {
            const res = existingResumeRes.value
            setAnalysis(res)
            if (res.target_role) setTargetRole(res.target_role)
            if (res.experience_level) setExperienceLevel(res.experience_level)
            setEditedSkills(res.extracted_skills || [])
          }
        }
      } catch {
        // Soft fail
      } finally {
        if (isMounted) setLoadingRoles(false)
      }
    }
    init()
    return () => {
      isMounted = false
    }
  }, [])

  // Sync editedSkills when analysis changes
  useEffect(() => {
    if (analysis) {
      setEditedSkills(analysis.extracted_skills || [])
    }
  }, [analysis])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0]
    if (!selected) return

    if (!selected.name.toLowerCase().endsWith('.pdf')) {
      setError('Please select a valid PDF file (.pdf).')
      setFile(null)
      return
    }

    if (selected.size > 5 * 1024 * 1024) {
      setError(`File exceeds 5MB size limit (${(selected.size / (1024 * 1024)).toFixed(1)}MB).`)
      setFile(null)
      return
    }

    setError(null)
    setFile(selected)
  }

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    const dropped = e.dataTransfer.files?.[0]
    if (!dropped) return

    if (!dropped.name.toLowerCase().endsWith('.pdf')) {
      setError('Please drop a valid PDF document (.pdf).')
      return
    }

    if (dropped.size > 5 * 1024 * 1024) {
      setError(`File exceeds 5MB size limit (${(dropped.size / (1024 * 1024)).toFixed(1)}MB).`)
      return
    }

    setError(null)
    setFile(dropped)
  }

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) {
      setError('Please select or upload a PDF resume.')
      return
    }

    if (!targetRole.trim()) {
      setError('Target job role is required.')
      return
    }

    setAnalyzing(true)
    setError(null)
    setRoleUpdateSuccess(null)
    setSkillSaveSuccess(null)

    try {
      const result = await analyzeResume(file, targetRole.trim(), experienceLevel)
      setAnalysis(result)
      setEditedSkills(result.extracted_skills || [])
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to analyze resume'
      setError(msg)
    } finally {
      setAnalyzing(false)
    }
  }

  const handleAddSkill = () => {
    const trimmed = newSkillInput.trim()
    if (!trimmed) return
    if (editedSkills.some((s) => s.toLowerCase() === trimmed.toLowerCase())) {
      setNewSkillInput('')
      return
    }
    setEditedSkills((prev) => [...prev, trimmed])
    setNewSkillInput('')
  }

  const handleRemoveSkill = (skillToRemove: string) => {
    setEditedSkills((prev) => prev.filter((s) => s !== skillToRemove))
  }

  const handleSaveSkillCorrections = async () => {
    if (!analysis) return
    setSavingSkills(true)
    setError(null)
    setSkillSaveSuccess(null)
    try {
      const updated = await updateResumeSkills(analysis.analysis_id, editedSkills)
      setAnalysis(updated)
      setEditedSkills(updated.extracted_skills || [])
      setSkillSaveSuccess('Skill corrections successfully saved to your preparation profile.')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to save skill corrections'
      setError(msg)
    } finally {
      setSavingSkills(false)
    }
  }

  const handleSelectRoleAndAnalyzeGaps = async (roleName: string, expLevel: string) => {
    if (!analysis) return
    setUpdatingRole(true)
    setError(null)
    setRoleUpdateSuccess(null)
    try {
      const updated = await selectTargetRole(analysis.analysis_id, roleName, expLevel)
      setAnalysis(updated)
      setTargetRole(roleName)
      setExperienceLevel(expLevel)
      setRoleUpdateSuccess(`Target role updated to "${roleName}". Initial skill gap analysis refreshed.`)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update target role'
      setError(msg)
    } finally {
      setUpdatingRole(false)
    }
  }

  const handleStartPracticeWithQuestions = async () => {
    if (!analysis) return
    setStartingSession(true)
    try {
      const session = await startInterviewFromResume(analysis.analysis_id, {
        adaptive: useAdaptive,
      })
      onStartInterview(session)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to launch interview session'
      setError(msg)
      setStartingSession(false)
    }
  }

  const filteredEvaluations =
    analysis?.skill_evaluations.filter((ev) => {
      if (activeCategory === 'All') return true
      return ev.category === activeCategory
    }) || []

  const categories = [
    'All',
    'Demonstrated in resume',
    'Mentioned but insufficiently evidenced',
    'Not demonstrated in resume',
    'Requires interview validation',
  ]

  const getCategoryBadgeClass = (category: string) => {
    switch (category) {
      case 'Demonstrated in resume':
        return 'pill-badge olive'
      case 'Mentioned but insufficiently evidenced':
        return 'pill-badge terracotta'
      case 'Not demonstrated in resume':
        return 'pill-badge sand'
      case 'Requires interview validation':
        return 'pill-badge neutral'
      default:
        return 'pill-badge neutral'
    }
  }

  return (
    <div className="skill-gap-page">
      <section className="room-hero">
        <AnimatedMeshGradient />
        <div className="room-header">
          <div>
            <div className="badge-row" style={{ marginBottom: '8px' }}>
              <span className="badge badge-accent">
                <TrendingUp size={13} /> Resume &amp; Skill Gap Intelligence
              </span>
              <span className="badge badge-neutral">
                <FileCheck2 size={13} /> Evidence-Grounded Preparation
              </span>
            </div>
            <h2>Resume-to-Job Alignment &amp; Skill Gaps</h2>
            <p className="intro-copy" style={{ marginTop: '8px' }}>
              Upload your PDF resume to extract technical competencies, verify evidence against your target role, correct any parsing discrepancies, and launch an adaptive preparation interview.
            </p>
          </div>
        </div>
      </section>

      {!analysis ? (
        <div className="upload-card">
          {error && (
            <div className="status-callout error" role="alert">
              <AlertCircle />
              <div>
                <strong>Resume Processing Notice</strong>
                <p className="form-hint">{error}</p>
              </div>
            </div>
          )}

          <form onSubmit={handleAnalyze} className="form-grid">
            <div className="form-field">
              <label className="form-label">Resume Document (PDF)</label>
              <div
                className={`upload-dropzone ${file ? 'has-file' : ''}`}
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                role="button"
                tabIndex={0}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="application/pdf,.pdf"
                  onChange={handleFileChange}
                  style={{ display: 'none' }}
                />
                <div className={`upload-icon ${file ? 'success' : ''}`}>
                  {file ? <FileCheck2 /> : <FileUp />}
                </div>
                {file ? (
                  <div>
                    <strong style={{ fontSize: '13px', color: '#2e7d56' }}>{file.name}</strong>
                    <p className="form-hint">{(file.size / 1024).toFixed(0)} KB • Click to choose a different PDF</p>
                  </div>
                ) : (
                  <div>
                    <strong style={{ fontSize: '13px', color: 'var(--foreground)' }}>Click to upload or drag &amp; drop your resume</strong>
                    <p className="form-hint">PDF text format only • Maximum file size 5MB</p>
                  </div>
                )}
              </div>
              <p className="form-hint" style={{ color: '#8e7a84' }}>
                *Privacy Guarantee: Uploaded files are processed strictly for your authenticated student account and never shared.
              </p>
            </div>

            <div className="form-field">
              <label htmlFor="target-role-input" className="form-label">Target Job Role</label>
              <select
                id="target-role-input"
                className="form-select"
                value={targetRole}
                onChange={(e) => setTargetRole(e.target.value)}
                disabled={analyzing}
              >
                {supportedRoles.length > 0 ? (
                  supportedRoles.map((r) => (
                    <option key={r.role_name} value={r.role_name}>
                      {r.role_name}
                    </option>
                  ))
                ) : (
                  <>
                    <option value="Full Stack Engineer">Full Stack Engineer</option>
                    <option value="Frontend Specialist">Frontend Specialist</option>
                    <option value="Backend Systems">Backend Systems</option>
                    <option value="AI/ML Engineer">AI/ML Engineer</option>
                    <option value="DevOps & Cloud">DevOps &amp; Cloud</option>
                  </>
                )}
              </select>
            </div>

            <div className="form-field">
              <label htmlFor="exp-level-select" className="form-label">Target Seniority / Level</label>
              <select
                id="exp-level-select"
                className="form-select"
                value={experienceLevel}
                onChange={(e) => setExperienceLevel(e.target.value)}
                disabled={analyzing}
              >
                <option value="Entry-Level">Entry-Level</option>
                <option value="Mid-Level">Mid-Level</option>
                <option value="Senior">Senior</option>
                <option value="Lead">Lead / Staff</option>
              </select>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '14px' }}>
              <button
                type="submit"
                className="button button-primary"
                disabled={analyzing || !file}
                style={{ minWidth: '220px' }}
              >
                {analyzing ? (
                  <>
                    <Loader2 className="animate-spin" style={{ width: '15px', height: '15px' }} />
                    Extracting Skills &amp; Analyzing Gaps...
                  </>
                ) : (
                  <>
                    <Sparkles style={{ width: '15px', height: '15px' }} />
                    Extract Skills &amp; Analyze Gaps
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      ) : (
        <div>
          {/* Analysis Header Card */}
          <div className="analysis-header-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                  <span className="eyebrow">Preparation Profile Connected</span>
                  <span className={`pill-badge ${analysis.saved_to_db ? 'olive' : 'sand'}`}>
                    {analysis.saved_to_db ? 'Saved to MongoDB Atlas' : 'Session Stored'}
                  </span>
                </div>
                <h3 style={{ margin: 0, fontSize: '20px', fontWeight: 700 }}>
                  {analysis.target_role} ({analysis.experience_level})
                </h3>
              </div>
              <button
                className="button button-secondary"
                style={{ fontSize: '11px', minHeight: '34px' }}
                onClick={() => {
                  setAnalysis(null)
                  setFile(null)
                }}
              >
                <RotateCcw style={{ width: '13px', height: '13px' }} /> Upload Different Resume
              </button>
            </div>

            <p style={{ margin: '14px 0 0', fontSize: '13px', lineHeight: 1.6, color: 'var(--foreground)' }}>
              {analysis.role_readiness_summary}
            </p>

            {/* Truncation Disclosure Banner */}
            {analysis.is_truncated && (
              <div
                className="banner sand"
                style={{ marginTop: '14px', display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px', borderRadius: '8px', background: 'rgba(217, 119, 6, 0.08)', border: '1px solid rgba(217, 119, 6, 0.25)' }}
                data-testid="truncation-warning"
              >
                <AlertCircle style={{ width: '15px', height: '15px', flexShrink: 0, color: 'var(--accent-secondary)' }} />
                <span style={{ fontSize: '12px', lineHeight: 1.5 }}>
                  <strong>Document Length Limit Reached:</strong> Resume was parsed up to {analysis.analyzed_character_count ? `${analysis.analyzed_character_count.toLocaleString()} characters` : '12,000 characters'}. Content beyond this limit was omitted.
                </span>
              </div>
            )}

            {/* Success Notifications */}
            {skillSaveSuccess && (
              <div className="status-callout success" style={{ marginTop: '14px' }}>
                <CheckCircle2 style={{ width: '16px', height: '16px' }} />
                <span>{skillSaveSuccess}</span>
              </div>
            )}
            {roleUpdateSuccess && (
              <div className="status-callout success" style={{ marginTop: '14px' }}>
                <CheckCircle2 style={{ width: '16px', height: '16px' }} />
                <span>{roleUpdateSuccess}</span>
              </div>
            )}
            {error && (
              <div className="status-callout error" style={{ marginTop: '14px' }}>
                <AlertCircle style={{ width: '16px', height: '16px' }} />
                <span>{error}</span>
              </div>
            )}

            {/* PHASE 2: Extracted Skills & Interactive Skill Correction */}
            <div style={{ marginTop: '18px', paddingTop: '16px', borderTop: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', marginBottom: '8px' }}>
                <div>
                  <p className="form-label" style={{ margin: 0 }}>
                    Identified Resume Skills ({editedSkills.length})
                  </p>
                  <span style={{ fontSize: '11px', color: 'var(--muted)' }}>
                    Review and correct extracted skills. Click &times; to remove or type below to add missing competencies.
                  </span>
                </div>
                {JSON.stringify(editedSkills) !== JSON.stringify(analysis.extracted_skills) && (
                  <button
                    type="button"
                    className="button button-primary"
                    style={{ minHeight: '28px', fontSize: '11px', padding: '0 10px' }}
                    onClick={handleSaveSkillCorrections}
                    disabled={savingSkills}
                  >
                    {savingSkills ? <Loader2 className="animate-spin" size={12} /> : <Check size={12} />}
                    Save Skill Corrections
                  </button>
                )}
              </div>

              {/* Editable skill chips */}
              <div className="skill-chips">
                {editedSkills.map((skill, idx) => (
                  <span
                    key={idx}
                    className="skill-chip"
                    style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                  >
                    <span>{skill}</span>
                    <button
                      type="button"
                      onClick={() => handleRemoveSkill(skill)}
                      style={{
                        border: 'none',
                        background: 'transparent',
                        color: 'inherit',
                        cursor: 'pointer',
                        padding: '0 2px',
                        fontSize: '13px',
                        fontWeight: 700,
                        lineHeight: 1,
                      }}
                      title={`Remove ${skill}`}
                    >
                      &times;
                    </button>
                  </span>
                ))}
              </div>

              {/* Inline Add Skill Input */}
              <div style={{ display: 'flex', gap: '8px', marginTop: '10px', maxWidth: '380px' }}>
                <input
                  className="form-input"
                  style={{ height: '32px', fontSize: '12px' }}
                  placeholder="Add missing skill (e.g. GraphQL)..."
                  value={newSkillInput}
                  onChange={(e) => setNewSkillInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      handleAddSkill()
                    }
                  }}
                />
                <button
                  type="button"
                  className="button button-secondary"
                  style={{ minHeight: '32px', fontSize: '11.5px', padding: '0 10px' }}
                  onClick={handleAddSkill}
                  disabled={!newSkillInput.trim()}
                >
                  <Plus size={13} /> Add
                </button>
              </div>
            </div>

            {/* Education, Experience & Certifications (Phase 2 Evidence) */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginTop: '18px', paddingTop: '16px', borderTop: '1px solid var(--border)' }}>
              {/* Projects Highlights */}
              {analysis.projects_and_experience.length > 0 && (
                <div>
                  <p className="form-label" style={{ marginBottom: '6px' }}>Project Highlights</p>
                  <ul className="eval-list" style={{ margin: 0, paddingLeft: '18px', fontSize: '12px' }}>
                    {analysis.projects_and_experience.map((proj, idx) => (
                      <li key={idx} style={{ marginBottom: '4px' }}>{proj}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Education Evidence */}
              {analysis.education && analysis.education.length > 0 && (
                <div>
                  <p className="form-label" style={{ marginBottom: '6px' }}>Education</p>
                  <ul className="eval-list" style={{ margin: 0, paddingLeft: '18px', fontSize: '12px' }}>
                    {analysis.education.map((edu, idx) => (
                      <li key={idx} style={{ marginBottom: '4px' }}>{edu}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Work Experience / Internships */}
              {analysis.work_experience && analysis.work_experience.length > 0 && (
                <div>
                  <p className="form-label" style={{ marginBottom: '6px' }}>Work Experience / Internships</p>
                  <ul className="eval-list" style={{ margin: 0, paddingLeft: '18px', fontSize: '12px' }}>
                    {analysis.work_experience.map((exp, idx) => (
                      <li key={idx} style={{ marginBottom: '4px' }}>{exp}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Certifications */}
              {analysis.certifications && analysis.certifications.length > 0 && (
                <div>
                  <p className="form-label" style={{ marginBottom: '6px' }}>Certifications</p>
                  <ul className="eval-list" style={{ margin: 0, paddingLeft: '18px', fontSize: '12px' }}>
                    {analysis.certifications.map((cert, idx) => (
                      <li key={idx} style={{ marginBottom: '4px' }}>{cert}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* PHASE 3: Target Role Selection & Competency Benchmarking */}
            <div style={{ marginTop: '18px', paddingTop: '16px', borderTop: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', marginBottom: '8px' }}>
                <div>
                  <p className="form-label" style={{ margin: 0 }}>
                    Switch Target Job Role &amp; Re-analyze Competencies
                  </p>
                  <span style={{ fontSize: '11px', color: 'var(--muted)' }}>
                    Compare your verified resume against different supported technical tracks.
                  </span>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap', marginTop: '8px' }}>
                <select
                  className="form-select"
                  style={{ width: 'auto', minWidth: '220px', height: '34px', fontSize: '12px' }}
                  value={targetRole}
                  onChange={(e) => setTargetRole(e.target.value)}
                  disabled={updatingRole}
                >
                  {supportedRoles.length > 0 ? (
                    supportedRoles.map((r) => (
                      <option key={r.role_name} value={r.role_name}>
                        {r.role_name}
                      </option>
                    ))
                  ) : (
                    <>
                      <option value="Full Stack Engineer">Full Stack Engineer</option>
                      <option value="Frontend Specialist">Frontend Specialist</option>
                      <option value="Backend Systems">Backend Systems</option>
                      <option value="AI/ML Engineer">AI/ML Engineer</option>
                      <option value="DevOps & Cloud">DevOps &amp; Cloud</option>
                    </>
                  )}
                </select>

                <select
                  className="form-select"
                  style={{ width: 'auto', minWidth: '130px', height: '34px', fontSize: '12px' }}
                  value={experienceLevel}
                  onChange={(e) => setExperienceLevel(e.target.value)}
                  disabled={updatingRole}
                >
                  <option value="Entry-Level">Entry-Level</option>
                  <option value="Mid-Level">Mid-Level</option>
                  <option value="Senior">Senior</option>
                  <option value="Lead">Lead / Staff</option>
                </select>

                <button
                  type="button"
                  className="button button-secondary"
                  style={{ minHeight: '34px', fontSize: '11.5px', padding: '0 12px' }}
                  onClick={() => handleSelectRoleAndAnalyzeGaps(targetRole, experienceLevel)}
                  disabled={updatingRole || (targetRole === analysis.target_role && experienceLevel === analysis.experience_level)}
                >
                  {updatingRole ? (
                    <>
                      <Loader2 className="animate-spin" size={13} />
                      Updating Benchmark...
                    </>
                  ) : (
                    <>
                      <Target size={13} /> Apply Role &amp; Re-analyze Gaps
                    </>
                  )}
                </button>
              </div>

              {/* Target Role Benchmark Chips */}
              {analysis.target_role_benchmark && (
                <div style={{ marginTop: '12px' }}>
                  <div className="skill-chips" style={{ marginBottom: '6px' }}>
                    {analysis.target_role_benchmark.expected_competencies.map((comp, idx) => (
                      <span key={idx} className="skill-chip" title={comp.description} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        <strong>{comp.skill_name}</strong>
                        <span style={{ fontSize: '10px', color: '#68596b' }}>({comp.importance})</span>
                      </span>
                    ))}
                  </div>
                  <p className="form-hint" style={{ fontSize: '11px', color: '#8e7a84', margin: 0 }}>
                    *{analysis.target_role_benchmark.disclaimer}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* PHASE 4: Initial Skill Gaps Breakdown & Prioritization */}
          <div style={{ marginTop: '32px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: '8px' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 700 }}>Initial Role Competency &amp; Gap Breakdown</h3>
                <p className="form-hint" style={{ marginTop: '4px' }}>
                  Clear comparison of required competencies vs documented evidence from your resume.
                </p>
              </div>
            </div>

            {/* Filter Tabs */}
            <div className="category-filter-tabs">
              {categories.map((cat) => {
                const count =
                  cat === 'All'
                    ? analysis.skill_evaluations.length
                    : analysis.skill_evaluations.filter((e) => e.category === cat).length
                return (
                  <button
                    key={cat}
                    type="button"
                    className={`category-filter-tab ${activeCategory === cat ? 'is-active' : ''}`}
                    onClick={() => setActiveCategory(cat)}
                  >
                    {cat} ({count})
                  </button>
                )
              })}
            </div>

            {/* Skill Cards Grid */}
            <div className="skill-cards-grid">
              {filteredEvaluations.map((item, idx) => (
                <div key={idx} className="skill-card">
                  <div className="skill-card-top">
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span className="skill-card-name">{item.skill_name}</span>
                        {item.is_expected_for_role && (
                          <span className="pill-badge sand" style={{ fontSize: '9px', padding: '1px 6px' }}>
                            Role Expectation
                          </span>
                        )}
                      </div>
                      {item.normalized_skill && item.normalized_skill.toLowerCase() !== item.skill_name.toLowerCase() && (
                        <span style={{ display: 'block', fontSize: '10px', color: '#8e7a84', marginTop: '2px' }}>
                          Standardized: {item.normalized_skill}
                        </span>
                      )}
                    </div>
                    <span className={getCategoryBadgeClass(item.category)}>
                      {item.category}
                    </span>
                  </div>
                  <div className="skill-card-evidence">
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '3px' }}>
                      <strong style={{ fontSize: '10px', textTransform: 'uppercase', color: '#8e7a84' }}>
                        Resume Evidence
                      </strong>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        {item.is_source_grounded ? (
                          <span className="pill-badge olive" style={{ fontSize: '9px', padding: '1px 6px' }}>
                            ✓ Grounded Excerpt
                          </span>
                        ) : item.evidence_type === 'unverified' ? (
                          <span className="pill-badge terracotta" style={{ fontSize: '9px', padding: '1px 6px' }}>
                            ⚠ Unverified Claim
                          </span>
                        ) : (
                          <span className="pill-badge neutral" style={{ fontSize: '9px', padding: '1px 6px' }}>
                            Analytical Summary
                          </span>
                        )}
                        {item.requires_interview_validation && (
                          <span className="pill-badge terracotta" style={{ fontSize: '9px', padding: '1px 6px' }}>
                            Validation Needed
                          </span>
                        )}
                      </div>
                    </div>
                    {item.evidence}
                    {item.source_excerpt && (
                      <div style={{ marginTop: '6px', fontSize: '11px', color: '#4d5d53', fontStyle: 'italic', background: '#f5f7f5', padding: '4px 8px', borderRadius: '4px' }}>
                        &ldquo;{item.source_excerpt}&rdquo;
                      </div>
                    )}
                    {item.classification_rationale && (
                      <div style={{ marginTop: '8px', fontSize: '11px', color: '#5a4d5b', borderLeft: '2px solid #d4c8d8', paddingLeft: '8px', lineHeight: 1.4 }}>
                        <strong>Rationale:</strong> {item.classification_rationale}
                      </div>
                    )}
                  </div>
                  <div className="skill-card-relevance">
                    <strong>Relevance to Role:</strong> {item.relevance_to_role}
                  </div>
                </div>
              ))}
            </div>

            {/* Neutral Guidance Disclaimer */}
            <div className="status-callout info" style={{ marginTop: '20px' }}>
              <ShieldCheck />
              <div>
                <strong>Objective Assessment Standard</strong>
                <p className="form-hint">
                  Missing resume evidence is not proof of lack of actual ability. These categorized observations highlight high-value discussion points to validate during live interview scenarios.
                </p>
              </div>
            </div>
          </div>

          {/* PHASE 5 & 6: Launch Sequential Adaptive Interview */}
          <div className="personalized-questions-section" style={{ marginTop: '32px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '14px', marginBottom: '16px' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 700 }}>Adaptive Interview Preparation</h3>
                <p className="form-hint" style={{ marginTop: '4px' }}>
                  Questions adapt sequentially to your actual submitted answers, target role requirements, and remaining time.
                </p>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  className="button button-primary"
                  onClick={handleStartPracticeWithQuestions}
                  disabled={startingSession}
                  style={{ minHeight: '40px', padding: '0 18px', fontSize: '13px' }}
                >
                  {startingSession ? (
                    <>
                      <Loader2 className="animate-spin" style={{ width: '15px', height: '15px' }} />
                      Initializing Sequential Interview...
                    </>
                  ) : (
                    <>
                      <Play data-icon="inline-start" />
                      Start Sequential Adaptive Interview
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Preparation priority summary */}
            {analysis.skill_evaluations.some((e) => e.requires_interview_validation) && (
              <div
                style={{
                  padding: '16px',
                  background: '#F8FAFD',
                  borderRadius: '10px',
                  border: '1px solid var(--border)',
                  marginBottom: '16px',
                }}
              >
                <strong style={{ fontSize: '13px', color: '#1E293B', display: 'block', marginBottom: '8px' }}>
                  Initial Interview Prioritization Rationale
                </strong>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {analysis.skill_evaluations
                    .filter((e) => e.requires_interview_validation)
                    .slice(0, 3)
                    .map((gap, gIdx) => (
                      <div key={gIdx} style={{ fontSize: '12px', color: '#475569', lineHeight: 1.45 }}>
                        <strong style={{ color: 'var(--accent)' }}>#{gIdx + 1} {gap.skill_name}:</strong>{' '}
                        {gap.classification_rationale || gap.relevance_to_role || 'Targeted for initial interview validation.'}
                      </div>
                    ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function ReportView({
  sessionId,
  onNavigateHome,
  onStartNewInterview,
  currentRole = 'candidate',
}: {
  sessionId?: string | null
  onNavigateHome: () => void
  onStartNewInterview?: () => void
  currentRole?: 'candidate' | 'reviewer' | 'admin'
}) {
  const [lookupId, setLookupId] = useState<string>(sessionId || '')
  const [report, setReport] = useState<InterviewReportResponse | null>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  // Available reports & sessions state
  const [availableReports, setAvailableReports] = useState<AvailableReportItem[]>([])
  const [loadingAvailable, setLoadingAvailable] = useState<boolean>(false)
  const [availableError, setAvailableError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [expandedQuestionIds, setExpandedQuestionIds] = useState<Record<string, boolean>>({})

  const toggleQuestionExpand = (qId: string) => {
    setExpandedQuestionIds((prev) => ({ ...prev, [qId]: !prev[qId] }))
  }

  const copyToClipboard = async (text: string, labelId: string) => {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = text
        textarea.style.position = 'fixed'
        textarea.style.opacity = '0'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
      }
      setCopiedId(labelId)
      setTimeout(() => setCopiedId(null), 2500)
    } catch (err) {
      console.error('Failed to copy ID to clipboard:', err)
    }
  }

  const fetchAvailableReports = useCallback(async () => {
    setLoadingAvailable(true)
    setAvailableError(null)
    try {
      const items = await getAvailableReports()
      setAvailableReports(items)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve available sessions'
      setAvailableError(msg)
    } finally {
      setLoadingAvailable(false)
    }
  }, [])

  useEffect(() => {
    fetchAvailableReports()
  }, [fetchAvailableReports])

  const handleSelectSession = (sid: string) => {
    if (!sid) return
    setLookupId(sid)
  }

  // Chronological Event Timeline collapsible state (collapsed by default)
  const [timelineExpanded, setTimelineExpanded] = useState<boolean>(false)

  const loadReport = useCallback(async (id: string) => {
    if (!id.trim()) return
    setLoading(true)
    setError(null)
    try {
      const data = await getFinalReport(id.trim())
      setReport(data)
      if (data?.questions_performance) {
        const initialExpanded: Record<string, boolean> = {}
        data.questions_performance.forEach((qp) => {
          if (qp.is_evaluated) {
            initialExpanded[qp.question_id] = true
          }
        })
        setExpandedQuestionIds(initialExpanded)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve final report'
      setError(msg)
      setReport(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (sessionId) {
      setLookupId(sessionId)
      loadReport(sessionId)
    }
  }, [sessionId, loadReport])

  const handleLookupSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    loadReport(lookupId)
  }

  return (
    <div className="report-page">
      <section className="room-hero">
        <AnimatedMeshGradient />
        <div className="room-header">
          <div>
            <div className="badge-row" style={{ marginBottom: '8px' }}>
              <span className="badge badge-accent">
                <BarChart3 size={13} /> Module 04: Evaluation Reports
              </span>
              <span className="badge badge-neutral">
                <FileText size={13} /> Multi-Criterion Performance
              </span>
            </div>
            <h2>Final Interview Report</h2>
            <p className="intro-copy" style={{ marginTop: '8px' }}>
              Comprehensive performance assessment, criterion score metrics, resume-to-interview cross-referencing, and integrity summary.
            </p>
          </div>
          {report && (
            <button
              onClick={() => window.print()}
              className="button button-secondary report-print-btn"
              title="Open browser print dialogue to print or save as PDF"
            >
              <Printer style={{ width: '15px', height: '15px' }} />
              Print / Export PDF
            </button>
          )}
        </div>
      </section>

      {/* Session Lookup Bar if no active report */}
      {!report && !loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', marginTop: '24px' }}>
          {/* Quick Select & Search Card */}
          <div className="upload-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px', marginBottom: '14px' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Database style={{ width: '18px', height: '18px', color: 'var(--accent)' }} />
                  Select Interview Session or Report
                </h3>
                <p className="form-hint" style={{ marginTop: '4px', marginBottom: 0 }}>
                  Choose from existing sessions and reports authorized for your account, or search below.
                </p>
              </div>
              <button
                type="button"
                onClick={fetchAvailableReports}
                className="button button-secondary"
                style={{ fontSize: '12px', padding: '6px 12px' }}
                disabled={loadingAvailable}
                title="Refresh list of available sessions"
              >
                {loadingAvailable ? (
                  <Loader2 className="animate-spin" style={{ width: '13px', height: '13px' }} />
                ) : (
                  <RotateCcw style={{ width: '13px', height: '13px' }} />
                )}
                Refresh List
              </button>
            </div>

            {availableError && (
              <div className="status-callout error" role="alert" style={{ marginBottom: '16px' }}>
                <AlertCircle />
                <div>
                  <strong>Session Listing Notice</strong>
                  <p className="form-hint">{availableError}</p>
                </div>
              </div>
            )}

            {/* Dropdown Selector */}
            <div style={{ marginBottom: '16px' }}>
              <label htmlFor="available-session-dropdown" style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--foreground)', marginBottom: '6px' }}>
                Existing Sessions / Reports Dropdown:
              </label>
              <select
                id="available-session-dropdown"
                className="form-input"
                style={{ width: '100%', cursor: 'pointer' }}
                value={availableReports.some((r) => r.session_id === lookupId) ? lookupId : ''}
                onChange={(e) => {
                  const val = e.target.value
                  if (val) {
                    handleSelectSession(val)
                  }
                }}
                disabled={loadingAvailable || availableReports.length === 0}
              >
                <option value="">
                  {loadingAvailable
                    ? 'Loading sessions...'
                    : availableReports.length === 0
                    ? '-- No existing sessions found for account --'
                    : '-- Select an interview session to populate full ID --'}
                </option>
                {availableReports.map((item) => {
                  const dateStr = item.created_at
                    ? new Date(item.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
                    : 'Unknown Date'
                  const scoreLabel = item.overall_score !== null && item.overall_score !== undefined
                    ? ` • Score: ${Math.round(item.overall_score)}/100`
                    : ''
                  return (
                    <option key={item.session_id} value={item.session_id}>
                      {item.role} ({item.experience_level || 'Mid-Level'}) • {dateStr} • {item.report_status}{scoreLabel}
                    </option>
                  )
                })}
              </select>
            </div>

            {loadingAvailable && (
              <div style={{ padding: '24px', textAlign: 'center', color: 'var(--muted)', background: 'var(--card)', borderRadius: '12px', border: '1px dashed var(--border)', marginBottom: '16px' }}>
                <Loader2 className="animate-spin" style={{ width: '22px', height: '22px', margin: '0 auto 8px', color: 'var(--accent)' }} />
                <p style={{ margin: 0, fontSize: '13px' }}>Loading interview history from database...</p>
              </div>
            )}

            {!loadingAvailable && availableReports.length === 0 && (
              <div style={{ padding: '32px 16px', textAlign: 'center', background: 'var(--card)', borderRadius: '12px', border: '1px dashed var(--border)', marginBottom: '16px' }}>
                <Clock3 style={{ width: '32px', height: '32px', margin: '0 auto 10px', color: 'var(--muted)' }} />
                <h4 style={{ margin: '0 0 6px', fontSize: '15px', color: 'var(--foreground)' }}>No interview history found</h4>
                <p style={{ margin: 0, fontSize: '12.5px', color: 'var(--muted)', maxWidth: '440px', marginInline: 'auto' }}>
                  No interview sessions were found for your account. Complete an interview to generate reports and track competency progress.
                </p>
              </div>
            )}

            {/* Search filter for session list */}
            {availableReports.length > 0 && (
              <div style={{ marginBottom: '16px' }}>
                <div style={{ position: 'relative' }}>
                  <Search style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', width: '15px', height: '15px', color: 'var(--muted)' }} />
                  <input
                    className="form-input"
                    style={{ width: '100%', paddingLeft: '36px' }}
                    placeholder="Search sessions by role, status, mode, or ID..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
              </div>
            )}

            {/* Scrollable list of available session cards */}
            {availableReports.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxHeight: '320px', overflowY: 'auto', paddingRight: '4px' }}>
                {availableReports
                  .filter((item) => {
                    if (!searchQuery.trim()) return true
                    const q = searchQuery.toLowerCase().trim()
                    return (
                      item.role.toLowerCase().includes(q) ||
                      item.report_status.toLowerCase().includes(q) ||
                      item.session_id.toLowerCase().includes(q) ||
                      (item.interview_mode && item.interview_mode.toLowerCase().includes(q)) ||
                      (item.report_id && item.report_id.toLowerCase().includes(q)) ||
                      (item.resume_analysis_id && item.resume_analysis_id.toLowerCase().includes(q)) ||
                      (item.difficulty && item.difficulty.toLowerCase().includes(q)) ||
                      (item.experience_level && item.experience_level.toLowerCase().includes(q))
                    )
                  })
                  .map((item) => {
                    const isSelected = lookupId === item.session_id
                    const dateFormatted = item.created_at
                      ? new Date(item.created_at).toLocaleString('en-US', {
                          month: 'short',
                          day: 'numeric',
                          year: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })
                      : 'Date unknown'

                    const statusPillClass =
                      item.report_status === 'Report Ready' ? 'olive' : item.status === 'completed' ? 'sand' : 'neutral'

                    const isCoding = item.interview_mode === 'CODING'

                    return (
                      <div
                        key={item.session_id}
                        style={{
                          border: isSelected ? '2px solid var(--accent)' : '1.5px solid var(--border)',
                          background: isSelected ? 'var(--accent-soft)' : 'var(--card)',
                          borderRadius: '12px',
                          padding: '14px 16px',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '10px',
                          boxShadow: isSelected ? '0 4px 16px rgba(67, 56, 168, 0.12)' : 'var(--shadow-card)',
                          transition: 'all .2s ease',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '8px' }}>
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: '4px' }}>
                              <span style={{ fontWeight: 700, fontSize: '14px', color: 'var(--foreground)' }}>
                                {item.role}
                              </span>
                              {item.interview_mode && (
                                <span className="pill-badge neutral" style={{ fontSize: '10px' }}>
                                  {isCoding ? 'Coding' : 'Verbal'}
                                </span>
                              )}
                              <span className={`pill-badge ${statusPillClass}`} style={{ fontSize: '10px' }}>
                                {item.report_status}
                              </span>
                              {item.is_persisted === false ? (
                                <span className="pill-badge sand" style={{ fontSize: '10px' }} title="Session stored in temporary active memory only">
                                  Active Memory
                                </span>
                              ) : (
                                <span className="pill-badge olive" style={{ fontSize: '10px' }} title="Permanently persisted to MongoDB Atlas">
                                  Atlas Persisted
                                </span>
                              )}
                              {item.overall_score !== null && item.overall_score !== undefined && (
                                <span className="pill-badge olive" style={{ fontSize: '10px', fontWeight: 700 }}>
                                  Score: {Math.round(item.overall_score)}/100
                                </span>
                              )}
                            </div>
                            <p style={{ margin: 0, fontSize: '11px', color: 'var(--muted)' }}>
                              Level: <strong>{item.experience_level || 'Mid-Level'}</strong> • Difficulty: <strong>{item.difficulty || 'Standard'}</strong> • Created: {dateFormatted}
                            </p>
                          </div>

                          <div style={{ display: 'flex', gap: '6px' }}>
                            <button
                              type="button"
                              className="button button-secondary"
                              style={{ fontSize: '11px', padding: '5px 10px', minHeight: '30px' }}
                              onClick={() => handleSelectSession(item.session_id)}
                              title="Select full session ID for lookup"
                            >
                              {isSelected ? 'Selected' : 'Select ID'}
                            </button>
                            <button
                              type="button"
                              className="button button-primary"
                              style={{ fontSize: '11px', padding: '5px 12px', minHeight: '30px' }}
                              onClick={() => {
                                handleSelectSession(item.session_id)
                                loadReport(item.session_id)
                              }}
                            >
                              <FileText style={{ width: '12px', height: '12px' }} /> View Report
                            </button>
                          </div>
                        </div>

                        {/* Distinct Identifiers Row */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap', paddingTop: '8px', borderTop: '1px solid var(--border)' }}>
                          {/* Interview Session ID */}
                          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', background: 'var(--accent-soft)', border: '1px solid #D6DDF0', borderRadius: '6px', padding: '3px 8px', fontSize: '11px' }}>
                            <span style={{ color: 'var(--muted)', fontWeight: 600 }}>Session ID:</span>
                            <span style={{ fontFamily: 'monospace', fontWeight: 700, color: 'var(--accent)' }}>
                              {item.session_id.slice(0, 8)}...{item.session_id.slice(-4)}
                            </span>
                            <button
                              type="button"
                              onClick={() => copyToClipboard(item.session_id, `card-sess-${item.session_id}`)}
                              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '2px', display: 'inline-flex', alignItems: 'center', color: 'var(--accent)' }}
                              title="Copy Full Complete Interview Session ID"
                            >
                              {copiedId === `card-sess-${item.session_id}` ? (
                                <Check style={{ width: '12px', height: '12px', color: 'var(--success)' }} />
                              ) : (
                                <Copy style={{ width: '12px', height: '12px' }} />
                              )}
                              <span style={{ fontSize: '9px', marginLeft: '2px' }}>
                                {copiedId === `card-sess-${item.session_id}` ? 'Copied' : 'Copy'}
                              </span>
                            </button>
                          </div>

                          {/* Report ID if exists */}
                          {item.report_id && (
                            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', background: '#f5f5f7', border: '1px solid #e5e5ea', borderRadius: '6px', padding: '3px 8px', fontSize: '11px' }}>
                              <span style={{ color: 'var(--muted)', fontWeight: 600 }}>Report ID:</span>
                              <span style={{ fontFamily: 'monospace', color: '#5f5363' }}>
                                {item.report_id.slice(0, 8)}...{item.report_id.slice(-4)}
                              </span>
                              <button
                                type="button"
                                onClick={() => copyToClipboard(item.report_id!, `card-rep-${item.report_id}`)}
                                style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '2px', display: 'inline-flex', alignItems: 'center', color: '#5f5363' }}
                                title="Copy Full Interview Report ID"
                              >
                                {copiedId === `card-rep-${item.report_id}` ? (
                                  <Check style={{ width: '12px', height: '12px', color: 'var(--success)' }} />
                                ) : (
                                  <Copy style={{ width: '12px', height: '12px' }} />
                                )}
                                <span style={{ fontSize: '9px', marginLeft: '2px' }}>
                                  {copiedId === `card-rep-${item.report_id}` ? 'Copied' : 'Copy'}
                                </span>
                              </button>
                            </div>
                          )}

                          {/* Resume Analysis ID if linked */}
                          {item.resume_analysis_id && (
                            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', background: '#f5f5f7', border: '1px solid #e5e5ea', borderRadius: '6px', padding: '3px 8px', fontSize: '11px' }}>
                              <span style={{ color: 'var(--muted)', fontWeight: 600 }}>Resume ID:</span>
                              <span style={{ fontFamily: 'monospace', color: '#5f5363' }}>
                                {item.resume_analysis_id.slice(0, 8)}...{item.resume_analysis_id.slice(-4)}
                              </span>
                              <button
                                type="button"
                                onClick={() => copyToClipboard(item.resume_analysis_id!, `card-res-${item.resume_analysis_id}`)}
                                style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '2px', display: 'inline-flex', alignItems: 'center', color: '#5f5363' }}
                                title="Copy Full Resume Analysis ID"
                              >
                                {copiedId === `card-res-${item.resume_analysis_id}` ? (
                                  <Check style={{ width: '12px', height: '12px', color: 'var(--success)' }} />
                                ) : (
                                  <Copy style={{ width: '12px', height: '12px' }} />
                                )}
                                <span style={{ fontSize: '9px', marginLeft: '2px' }}>
                                  {copiedId === `card-res-${item.resume_analysis_id}` ? 'Copied' : 'Copy'}
                                </span>
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    )
                  })}
              </div>
            )}
          </div>

          {/* Direct Session ID Lookup Box */}
          <div className="upload-card">
            <h3 style={{ margin: '0 0 8px', fontSize: '16px', fontWeight: 700 }}>
              Lookup Session by Full Identifier
            </h3>
            <p className="form-hint" style={{ marginBottom: '14px' }}>
              The report endpoint requires the full <strong>Interview Session ID</strong> (e.g. <code>3fa85f64-5717-4562-b3fc-2c963f66afa6</code>). Selecting any item above populates this field with its complete, un-truncated session ID.
            </p>

            {error && (
              <div className="status-callout error" role="alert" style={{ marginBottom: '16px' }}>
                <AlertCircle />
                <div>
                  <strong>Report Retrieval Error</strong>
                  <p className="form-hint">{error}</p>
                </div>
              </div>
            )}

            <form onSubmit={handleLookupSubmit} style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
              <div style={{ flex: 1, minWidth: '280px', position: 'relative' }}>
                <input
                  className="form-input"
                  value={lookupId}
                  onChange={(e) => setLookupId(e.target.value)}
                  placeholder="e.g. 28badec8-0b9a-475a-b8ca-86c03769f620"
                  style={{ width: '100%', fontFamily: 'monospace', fontSize: '13px', paddingRight: lookupId ? '110px' : '14px' }}
                  required
                />
                {lookupId && (
                  <button
                    type="button"
                    onClick={() => copyToClipboard(lookupId, 'input-full')}
                    style={{
                      position: 'absolute',
                      right: '8px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: '#f2eef3',
                      border: '1px solid #e0d8e2',
                      borderRadius: '6px',
                      padding: '4px 8px',
                      fontSize: '11px',
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      color: '#655',
                    }}
                    title="Copy full input session ID"
                  >
                    {copiedId === 'input-full' ? (
                      <Check style={{ width: '12px', height: '12px', color: 'var(--success)' }} />
                    ) : (
                      <Copy style={{ width: '12px', height: '12px' }} />
                    )}
                    <span>{copiedId === 'input-full' ? 'Copied!' : 'Copy Full ID'}</span>
                  </button>
                )}
              </div>
              <button type="submit" className="button button-primary">
                <FileText style={{ width: '15px', height: '15px' }} /> Retrieve Report
              </button>
            </form>
          </div>
        </div>
      )}

      {loading && (
        <div className="empty-state" style={{ marginTop: '30px' }}>
          <Loader2 className="animate-spin" style={{ width: '28px', height: '28px', color: 'var(--accent)' }} />
          <h3 style={{ marginTop: '14px' }}>Generating Final Decision Intelligence Report...</h3>
          <p style={{ margin: 0, color: 'var(--muted)', fontSize: '12px' }}>
            Aggregating evaluated answers, scoring coverage, and cross-referencing skills...
          </p>
        </div>
      )}

      {report && (
        <div>
          {/* Metadata Card */}
          <div className="report-hero-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '14px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', flexWrap: 'wrap' }}>
                  <span className="eyebrow">Session Metadata</span>
                  <span className={`pill-badge ${report.saved_to_db ? 'olive' : 'sand'}`}>
                    {report.saved_to_db ? 'Saved to MongoDB Atlas' : 'Active In-Memory Only'}
                  </span>
                  <span className="pill-badge neutral" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                    <span>Session ID: {report.session_id.slice(0, 8)}...{report.session_id.slice(-4)}</span>
                    <button
                      type="button"
                      onClick={() => copyToClipboard(report.session_id, 'hero-sess')}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '2px 4px', display: 'inline-flex', alignItems: 'center', color: 'inherit' }}
                      title="Copy Full Interview Session ID"
                    >
                      {copiedId === 'hero-sess' ? <Check style={{ width: '12px', height: '12px', color: 'var(--success)' }} /> : <Copy style={{ width: '12px', height: '12px' }} />}
                      <span style={{ fontSize: '10px', marginLeft: '3px' }}>{copiedId === 'hero-sess' ? 'Copied' : 'Copy'}</span>
                    </button>
                  </span>
                  {report.report_id && (
                    <span className="pill-badge neutral" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                      <span>Report ID: {report.report_id.slice(0, 8)}...{report.report_id.slice(-4)}</span>
                      <button
                        type="button"
                        onClick={() => copyToClipboard(report.report_id, 'hero-rep')}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '2px 4px', display: 'inline-flex', alignItems: 'center', color: 'inherit' }}
                        title="Copy Full Interview Report ID"
                      >
                        {copiedId === 'hero-rep' ? <Check style={{ width: '12px', height: '12px', color: 'var(--success)' }} /> : <Copy style={{ width: '12px', height: '12px' }} />}
                        <span style={{ fontSize: '10px', marginLeft: '3px' }}>{copiedId === 'hero-rep' ? 'Copied' : 'Copy'}</span>
                      </button>
                    </span>
                  )}
                  {report.resume_comparison?.associated_analysis_id && (
                    <span className="pill-badge neutral" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                      <span>Resume ID: {report.resume_comparison.associated_analysis_id.slice(0, 8)}...</span>
                      <button
                        type="button"
                        onClick={() => copyToClipboard(report.resume_comparison!.associated_analysis_id, 'hero-res')}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '2px 4px', display: 'inline-flex', alignItems: 'center', color: 'inherit' }}
                        title="Copy Full Resume Analysis ID"
                      >
                        {copiedId === 'hero-res' ? <Check style={{ width: '12px', height: '12px', color: 'var(--success)' }} /> : <Copy style={{ width: '12px', height: '12px' }} />}
                        <span style={{ fontSize: '10px', marginLeft: '3px' }}>{copiedId === 'hero-res' ? 'Copied' : 'Copy'}</span>
                      </button>
                    </span>
                  )}
                </div>
                <h3 style={{ margin: 0, fontSize: '24px', fontWeight: 800 }}>
                  {report.role}
                </h3>
                <p style={{ margin: '4px 0 0', fontSize: '13px', color: 'var(--muted)' }}>
                  Level: <strong>{report.experience_level}</strong> • Difficulty: <strong>{report.difficulty}</strong> • Focus: {report.focus_areas}
                </p>
              </div>

              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  className="button button-secondary"
                  style={{ fontSize: '11px', minHeight: '34px' }}
                  onClick={() => {
                    setReport(null)
                    setLookupId('')
                  }}
                >
                  <RotateCcw style={{ width: '13px', height: '13px' }} /> Change Session
                </button>
              </div>
            </div>

            {/* Performance Score Hero Box */}
            <div className="report-score-hero">
              <div className="report-score-row">
                <div>
                  <span className="eyebrow" style={{ color: 'var(--accent)' }}>Overall Candidate Score</span>
                  <div className="report-big-score" style={{ marginTop: '4px' }}>
                    {report.overall_score !== null ? (
                      <>
                        <span className="val">{report.overall_score}</span>
                        <span className="denom">{(report.overall_score ?? 0) > 10 ? '/ 100' : '/ 10'}</span>
                      </>
                    ) : (
                      <span className="val" style={{ fontSize: '28px', color: '#9a8f9e' }}>
                        N/A (Insufficient Data)
                      </span>
                    )}
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '6px' }}>
                  <span className="report-coverage-badge">
                    <TrendingUp style={{ width: '14px', height: '14px', color: 'var(--accent)' }} />
                    {report.evaluated_questions} of {report.total_questions} Questions Evaluated ({report.evaluation_coverage_pct}% Coverage)
                  </span>
                  <span style={{ fontSize: '11px', color: 'var(--muted)' }}>
                    Answered: {report.answered_questions} • Unanswered: {report.unanswered_questions}
                  </span>
                </div>
              </div>

              {/* Criterion Breakdown Grid */}
              <div>
                <p className="form-label" style={{ marginBottom: '6px' }}>Criterion Performance Averages</p>
                <div className="report-crit-grid">
                  <div className="report-crit-box">
                    <span className="report-crit-title">Relevance</span>
                    <span className="report-crit-val">
                      {report.criterion_averages.relevance ? `${report.criterion_averages.relevance}/10` : '—'}
                    </span>
                  </div>
                  <div className="report-crit-box">
                    <span className="report-crit-title">Technical Depth</span>
                    <span className="report-crit-val">
                      {report.criterion_averages.technical_depth ? `${report.criterion_averages.technical_depth}/10` : '—'}
                    </span>
                  </div>
                  <div className="report-crit-box">
                    <span className="report-crit-title">Completeness</span>
                    <span className="report-crit-val">
                      {report.criterion_averages.completeness ? `${report.criterion_averages.completeness}/10` : '—'}
                    </span>
                  </div>
                  <div className="report-crit-box">
                    <span className="report-crit-title">Structure &amp; Flow</span>
                    <span className="report-crit-val">
                      {report.criterion_averages.structure_flow ? `${report.criterion_averages.structure_flow}/10` : '—'}
                    </span>
                  </div>
                  <div className="report-crit-box">
                    <span className="report-crit-title">Clarity</span>
                    <span className="report-crit-val">
                      {report.criterion_averages.clarity_conciseness ? `${report.criterion_averages.clarity_conciseness}/10` : '—'}
                    </span>
                  </div>
                  {report.criterion_averages.star_structure && (
                    <div className="report-crit-box">
                      <span className="report-crit-title">STAR Method</span>
                      <span className="report-crit-val">
                        {report.criterion_averages.star_structure}/10
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Formula & Coverage Note */}
              <p className="report-formula-note">
                <strong>Scoring Methodology:</strong> {report.scoring_formula_explanation}
              </p>
            </div>
          </div>

          {/* Executive Summary & Technical Readiness Assessment */}
          {report.executive_summary_details && (
            <div className="report-section-card" style={{ marginTop: '20px', borderLeft: '4px solid var(--accent)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '10px', marginBottom: '12px' }}>
                <div>
                  <span className="eyebrow" style={{ color: 'var(--accent)' }}>Executive Evaluation &amp; Interview Readiness</span>
                  <h4 style={{ margin: '4px 0 0', fontSize: '18px', fontWeight: 800 }}>
                    Technical Readiness Assessment
                  </h4>
                </div>
                <span
                  className={`pill-badge ${
                    report.executive_summary_details.readiness_level === 'Interview Ready'
                      ? 'olive'
                      : report.executive_summary_details.readiness_level === 'Borderline / Needs Practice'
                      ? 'sand'
                      : 'terracotta'
                  }`}
                  style={{ fontSize: '12px', padding: '6px 14px', fontWeight: 700 }}
                >
                  <Award style={{ width: '14px', height: '14px', display: 'inline', marginRight: '4px' }} />
                  {report.executive_summary_details.readiness_level}
                </span>
              </div>

              <p style={{ margin: '0 0 16px', fontSize: '13.5px', lineHeight: 1.6, color: 'var(--foreground)' }}>
                {report.executive_summary_details.readiness_summary}
              </p>

              {/* Explicit Scoring Formula & Coverage Metrics */}
              <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '14px 16px', marginBottom: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
                  <TrendingUp style={{ width: '14px', height: '14px', color: 'var(--accent)' }} />
                  <strong style={{ fontSize: '12px', color: '#1e293b' }}>Mathematical Score Calculation &amp; Coverage</strong>
                </div>
                <div style={{ fontSize: '12px', color: '#334155', fontFamily: 'monospace', background: '#ffffff', padding: '8px 12px', borderRadius: '6px', border: '1px solid #cbd5e1', marginBottom: '10px' }}>
                  {report.executive_summary_details.scoring_calculation}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '8px', fontSize: '11.5px' }}>
                  <div style={{ background: '#ffffff', padding: '6px 10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                    <span style={{ color: 'var(--muted)', display: 'block' }}>Attempted</span>
                    <strong style={{ fontSize: '13px' }}>{report.executive_summary_details.attempted_questions}</strong>
                  </div>
                  <div style={{ background: '#ffffff', padding: '6px 10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                    <span style={{ color: 'var(--muted)', display: 'block' }}>Answered</span>
                    <strong style={{ fontSize: '13px' }}>{report.executive_summary_details.answered_questions}</strong>
                  </div>
                  <div style={{ background: '#ffffff', padding: '6px 10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                    <span style={{ color: 'var(--muted)', display: 'block' }}>Evaluated</span>
                    <strong style={{ fontSize: '13px', color: '#2e7d56' }}>{report.executive_summary_details.evaluated_questions}</strong>
                  </div>
                  <div style={{ background: '#ffffff', padding: '6px 10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                    <span style={{ color: 'var(--muted)', display: 'block' }}>Unevaluated</span>
                    <strong style={{ fontSize: '13px', color: '#b45309' }}>{report.executive_summary_details.unevaluated_questions}</strong>
                  </div>
                  <div style={{ background: '#ffffff', padding: '6px 10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                    <span style={{ color: 'var(--muted)', display: 'block' }}>Coverage</span>
                    <strong style={{ fontSize: '13px' }}>{report.executive_summary_details.evaluation_coverage_pct}%</strong>
                  </div>
                </div>
              </div>

              {/* Recurring Mistakes Callout */}
              {report.executive_summary_details.recurring_mistakes.length > 0 && (
                <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: '10px', padding: '12px 14px', marginBottom: '14px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                    <AlertCircle style={{ width: '14px', height: '14px', color: '#b45309' }} />
                    <strong style={{ fontSize: '12px', color: '#92400e' }}>Recurring Mistakes Across Questions</strong>
                  </div>
                  <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '12px', color: '#78350f', lineHeight: 1.5 }}>
                    {report.executive_summary_details.recurring_mistakes.map((mis, idx) => (
                      <li key={idx}>{mis}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Strongest Competencies & Next Priorities Pills */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '14px', paddingTop: '10px', borderTop: '1px solid var(--border)' }}>
                {report.executive_summary_details.strongest_competencies.length > 0 && (
                  <div>
                    <span style={{ fontSize: '11px', fontWeight: 700, color: '#2e7d56', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>
                      Strongest Competencies
                    </span>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {report.executive_summary_details.strongest_competencies.map((comp, idx) => (
                        <span key={idx} className="pill-badge olive" style={{ fontSize: '11px' }}>
                          ✓ {comp}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {report.executive_summary_details.recommended_learning_priorities.length > 0 && (
                  <div>
                    <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>
                      Top Recommended Next Steps
                    </span>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {report.executive_summary_details.recommended_learning_priorities.map((prio, idx) => (
                        <span key={idx} className="pill-badge sand" style={{ fontSize: '11px' }}>
                          → {prio}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Executive Summary & Next Steps */}
          <div className="report-columns" style={{ marginTop: '20px' }}>
            <div className="report-section-card">
              <h4 className="report-section-title">
                <Sparkles style={{ width: '15px', height: '15px', color: 'var(--accent)' }} />
                Executive Summary
              </h4>
              <p style={{ margin: 0, fontSize: '13px', lineHeight: 1.6, color: 'var(--foreground)' }}>
                {report.executive_summary}
              </p>
            </div>

            <div className="report-section-card">
              <h4 className="report-section-title">
                <TrendingUp style={{ width: '15px', height: '15px', color: '#3b7556' }} />
                Recommended Next Steps
              </h4>
              <ul className="eval-list">
                {report.recommended_next_steps.map((step, idx) => (
                  <li key={idx}>{step}</li>
                ))}
              </ul>
            </div>
          </div>

          {/* Strengths & Priority Improvements */}
          <div className="report-columns" style={{ marginTop: '20px' }}>
            <div className="report-section-card">
              <h4 className="report-section-title">
                <CheckCircle2 style={{ width: '15px', height: '15px', color: '#2e7d56' }} />
                Validated Candidate Strengths
              </h4>
              {report.key_strengths.length > 0 ? (
                <ul className="eval-list">
                  {report.key_strengths.map((str, idx) => (
                    <li key={idx}>{str}</li>
                  ))}
                </ul>
              ) : (
                <p className="form-hint">No evaluated answer data available to confirm strengths yet.</p>
              )}
            </div>

            <div className="report-section-card">
              <h4 className="report-section-title">
                <AlertCircle style={{ width: '15px', height: '15px', color: 'var(--accent)' }} />
                Priority Development Areas
              </h4>
              {report.priority_improvements.length > 0 ? (
                <ul className="eval-list">
                  {report.priority_improvements.map((imp, idx) => (
                    <li key={idx}>{imp}</li>
                  ))}
                </ul>
              ) : (
                <p className="form-hint">No evaluated answer data available to identify development areas yet.</p>
              )}
            </div>
          </div>

          {/* Competency-Level Evidence & Mastery Breakdown */}
          {report.competencies_analysis && report.competencies_analysis.length > 0 && (
            <div style={{ marginTop: '34px' }}>
              <div style={{ marginBottom: '14px' }}>
                <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Layers style={{ width: '18px', height: '18px', color: 'var(--accent)' }} />
                  Competency-Level Evidence &amp; Mastery Breakdown
                </h3>
                <p className="form-hint" style={{ marginTop: '4px', marginBottom: 0 }}>
                  Aggregated evidence across evaluated questions. Unassessed competencies are preserved without negative bias.
                </p>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(310px, 1fr))', gap: '14px' }}>
                {report.competencies_analysis.map((comp, idx) => {
                  const isDemo = comp.status === 'Demonstrated'
                  const isNeeds = comp.status === 'Needs Further Assessment'
                  const badgeClass = isDemo ? 'olive' : isNeeds ? 'sand' : 'neutral'
                  return (
                    <div
                      key={idx}
                      className="report-section-card"
                      style={{
                        padding: '16px',
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                        gap: '12px',
                        borderTop: isDemo ? '3px solid #2e7d56' : isNeeds ? '3px solid #d97706' : '3px solid #94a3b8',
                      }}
                    >
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px', marginBottom: '8px' }}>
                          <div>
                            <h4 style={{ margin: 0, fontSize: '15px', fontWeight: 750 }}>{comp.competency_name}</h4>
                            <span style={{ fontSize: '11px', color: 'var(--muted)' }}>
                              {comp.evaluated_questions_count} of {comp.total_questions_count} Question(s) Evaluated
                            </span>
                          </div>
                          <span className={`pill-badge ${badgeClass}`} style={{ fontSize: '10px' }}>
                            {comp.status}
                          </span>
                        </div>

                        {comp.average_score !== null && comp.average_score !== undefined ? (
                          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginBottom: '10px' }}>
                            <span style={{ fontSize: '20px', fontWeight: 800, color: isDemo ? '#2e7d56' : '#b45309' }}>
                              {comp.average_score}
                            </span>
                            <span style={{ fontSize: '11px', color: 'var(--muted)' }}>/ 100 average</span>
                          </div>
                        ) : (
                          <div style={{ fontSize: '11.5px', color: 'var(--muted)', fontStyle: 'italic', marginBottom: '10px' }}>
                            Not yet assessed in this session
                          </div>
                        )}

                        {comp.demonstrated_strengths.length > 0 && (
                          <div style={{ marginBottom: '8px' }}>
                            <strong style={{ fontSize: '11px', color: '#2e7d56', display: 'block', marginBottom: '3px' }}>
                              Demonstrated Strengths:
                            </strong>
                            <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '11.5px', color: '#334155', lineHeight: 1.45 }}>
                              {comp.demonstrated_strengths.map((st, sIdx) => (
                                <li key={sIdx}>{st}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {comp.recurring_weaknesses.length > 0 && (
                          <div style={{ marginBottom: '8px' }}>
                            <strong style={{ fontSize: '11px', color: '#b45309', display: 'block', marginBottom: '3px' }}>
                              Recurring Focus Areas:
                            </strong>
                            <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '11.5px', color: '#475569', lineHeight: 1.45 }}>
                              {comp.recurring_weaknesses.map((w, wIdx) => (
                                <li key={wIdx}>{w}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>

                      {comp.supporting_evidence.length > 0 && (
                        <div style={{ paddingTop: '8px', borderTop: '1px solid #f1f5f9', fontSize: '10.5px', color: 'var(--muted)' }}>
                          <strong>Evidence Citations:</strong> {comp.supporting_evidence.join(' • ')}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Resume-to-Interview Cross Reference Section */}
          <div style={{ marginTop: '34px' }}>
            <h3 style={{ margin: '0 0 4px', fontSize: '18px', fontWeight: 700 }}>
              Resume-to-Interview Alignment &amp; Verification
            </h3>
            <p className="form-hint" style={{ marginBottom: '14px' }}>
              Comparison of documented resume skills against evaluated interview performance.
            </p>

            {report.has_resume_comparison && report.resume_comparison ? (
              <div className="report-section-card">
                <p style={{ margin: '0 0 12px', fontSize: '13px', lineHeight: 1.5, color: 'var(--foreground)' }}>
                  {report.resume_comparison.comparison_summary}
                </p>

                <div className="skill-cards-grid">
                  {report.resume_comparison.skills_comparison.map((item, idx) => {
                    const statusLabel = item.post_interview_status || item.interview_status
                    const isDemonstrated = statusLabel === 'Demonstrated in Interview'
                    const isPartially = statusLabel === 'Partially Demonstrated'
                    const isUnverified = statusLabel === 'Requires Further Validation'
                    const badgeClass = isDemonstrated ? 'olive' : isPartially ? 'sand' : isUnverified ? 'terracotta' : 'neutral'

                    return (
                      <div key={idx} className="skill-card">
                        <div className="skill-card-top" style={{ alignItems: 'flex-start', flexWrap: 'wrap', gap: '6px' }}>
                          <div>
                            <span className="skill-card-name">{item.skill_name}</span>
                            {item.role_importance && (
                              <span className="pill-badge neutral" style={{ fontSize: '10px', marginLeft: '6px' }}>
                                {item.role_importance}
                              </span>
                            )}
                          </div>
                          <span className={`pill-badge ${badgeClass}`}>
                            {statusLabel}
                          </span>
                        </div>

                        <div className="skill-card-evidence">
                          <strong style={{ display: 'block', fontSize: '10px', textTransform: 'uppercase', color: '#8e7a84', marginBottom: '3px' }}>
                            Resume Claim: {item.resume_evidence_category}
                          </strong>

                          {item.resume_source_excerpt && (
                            <div style={{ fontSize: '11px', color: 'var(--foreground-muted)', fontStyle: 'italic', marginBottom: '6px' }}>
                              Resume Grounding: &ldquo;{item.resume_source_excerpt}&rdquo;
                            </div>
                          )}

                          {item.question_text && (
                            <div style={{ fontSize: '11px', marginBottom: '3px' }}>
                              <strong>Target Question:</strong> {item.question_text}
                            </div>
                          )}

                          {item.candidate_answer_excerpt && (
                            <div style={{ fontSize: '11px', color: 'var(--foreground-muted)', fontStyle: 'italic', marginBottom: '4px' }}>
                              <strong>Answer Excerpt:</strong> &ldquo;{item.candidate_answer_excerpt}&rdquo;
                            </div>
                          )}

                          {item.status_rationale ? (
                            <div style={{ fontSize: '11px', color: 'var(--foreground)', marginTop: '4px' }}>
                              <strong>Evidence Rationale:</strong> {item.status_rationale}
                            </div>
                          ) : (
                            item.details
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>

                <p className="form-hint" style={{ marginTop: '12px' }}>
                  *Standard Note: Skills omitted from the resume or not tested during this session are not presumed to be absent.
                </p>
              </div>
            ) : (
              <div className="status-callout info">
                <ShieldCheck />
                <div>
                  <strong>No Associated Resume Analysis</strong>
                  <p className="form-hint">
                    This interview was created without an associated resume analysis. To generate resume-correlated alignment reports, start an interview from the Skill Gap Analysis workspace.
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Session Integrity Observations & Timeline Transparency */}
          <div style={{ marginTop: '34px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', marginBottom: '12px' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 700 }}>
                  Observed Session Presence &amp; Integrity Context
                </h3>
                <p className="form-hint" style={{ marginTop: '4px' }}>
                  Factual event summary recorded during the interview session.
                </p>
              </div>
              <span className="pill-badge olive">
                {report.integrity_summary.score_impact}
              </span>
            </div>

            {/* Presence Analytics Metric Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '12px', marginBottom: '16px' }}>
              <div className="report-crit-box" style={{ padding: '14px 16px' }}>
                <span className="report-crit-title">Cumulative Unfocused Duration</span>
                <span className="report-crit-val" style={{ color: 'var(--accent)', fontSize: '20px' }}>
                  {typeof report.integrity_summary.cumulative_unfocused_seconds === 'number'
                    ? `${report.integrity_summary.cumulative_unfocused_seconds.toFixed(1)}s`
                    : '0.0s'}
                </span>
                <p className="form-hint" style={{ fontSize: '10px', marginTop: '4px' }}>
                  Computed strictly from matched tab_hidden → tab_visible pairs.
                </p>
              </div>

              <div className="report-crit-box" style={{ padding: '14px 16px' }}>
                <span className="report-crit-title">Incomplete Intervals</span>
                <span className="report-crit-val" style={{ color: (report.integrity_summary.incomplete_intervals_count || 0) > 0 ? '#9c2a2a' : '#2e7d56', fontSize: '20px' }}>
                  {report.integrity_summary.incomplete_intervals_count || 0}
                </span>
                <p className="form-hint" style={{ fontSize: '10px', marginTop: '4px' }}>
                  Unmatched tab_hidden events are tracked as incomplete without fabricating duration.
                </p>
              </div>

              <div className="report-crit-box" style={{ padding: '14px 16px' }}>
                <span className="report-crit-title">Total Observed Events</span>
                <span className="report-crit-val" style={{ fontSize: '20px' }}>
                  {report.integrity_summary.total_events}
                </span>
                <p className="form-hint" style={{ fontSize: '10px', marginTop: '4px' }}>
                  Distinct browser and hardware context observations.
                </p>
              </div>
            </div>

            <div className="report-section-card">
              <div className="badge-row" style={{ marginBottom: '12px' }}>
                <span className="form-label" style={{ marginRight: '6px' }}>Event Summary:</span>
                {Object.keys(report.integrity_summary.events_summary).length > 0 ? (
                  Object.entries(report.integrity_summary.events_summary).map(([type, count]) => (
                    <span key={type} className="pill-badge neutral">
                      {type.replace('_', ' ')}: {count}
                    </span>
                  ))
                ) : (
                  <span className="form-hint">No unexpected browser or device events recorded.</span>
                )}
              </div>

              {/* Per-Question Distribution Badges */}
              {report.integrity_summary.events_by_question && Object.keys(report.integrity_summary.events_by_question).length > 0 && (
                <div className="badge-row" style={{ marginBottom: '16px', paddingTop: '8px', borderTop: '1px solid var(--border)' }}>
                  <span className="form-label" style={{ marginRight: '6px' }}>Distribution:</span>
                  {Object.entries(report.integrity_summary.events_by_question).map(([qid, count]) => {
                    const qPerf = report.questions_performance.find((qp) => qp.question_id === qid)
                    const label = qid === 'unassociated' ? 'Question not associated' : qPerf ? `Question ${qPerf.question_number}` : qid
                    return (
                      <span key={qid} className={`pill-badge ${qid === 'unassociated' ? 'sand' : 'neutral'}`}>
                        {label}: {count} {count === 1 ? 'event' : 'events'}
                      </span>
                    )
                  })}
                </div>
              )}

              {/* Chronological Event Timeline Collapsible Dropdown */}
              <div style={{ marginTop: '14px', paddingTop: '14px', borderTop: '1px solid var(--border)' }}>
                <button
                  type="button"
                  id="timeline-accordion-button"
                  aria-expanded={timelineExpanded}
                  aria-controls="chronological-event-timeline-panel"
                  onClick={() => setTimelineExpanded(!timelineExpanded)}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '10px 14px',
                    background: timelineExpanded ? 'var(--accent-soft, #f4f6fb)' : '#FFFFFF',
                    border: '1px solid var(--border)',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    textAlign: 'left',
                    color: 'var(--foreground)',
                    transition: 'all 0.15s ease',
                  }}
                  className="timeline-accordion-header"
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--foreground)' }}>
                      Chronological Event Timeline
                    </span>
                    <span className="pill-badge neutral" style={{ fontSize: '10px' }}>
                      {typeof report.integrity_summary.total_events === 'number'
                        ? `${report.integrity_summary.total_events} ${report.integrity_summary.total_events === 1 ? 'event' : 'events'}`
                        : `${report.integrity_summary.events_timeline?.length || 0} events`}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--muted)', fontSize: '11px' }}>
                    <span>{timelineExpanded ? 'Hide events' : 'Show events'}</span>
                    {timelineExpanded ? (
                      <ChevronUp style={{ width: '16px', height: '16px', color: 'var(--accent)' }} />
                    ) : (
                      <ChevronDown style={{ width: '16px', height: '16px', color: 'var(--muted)' }} />
                    )}
                  </div>
                </button>

                {timelineExpanded && (
                  <div
                    id="chronological-event-timeline-panel"
                    role="region"
                    aria-labelledby="timeline-accordion-button"
                    style={{ marginTop: '10px' }}
                  >
                    {report.integrity_summary.events_timeline && report.integrity_summary.events_timeline.length > 0 ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {report.integrity_summary.events_timeline.map((ev, idx) => {
                          const qPerf = ev.question_id
                            ? report.questions_performance.find((qp) => qp.question_id === ev.question_id)
                            : null
                          const timeStr = new Date(ev.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
                          return (
                            <div
                              key={ev.event_id || idx}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                flexWrap: 'wrap',
                                gap: '8px',
                                padding: '8px 12px',
                                background: '#fffaff',
                                border: '1px solid var(--border)',
                                borderRadius: '8px',
                                fontSize: '11px',
                              }}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                                <span style={{ color: 'var(--muted)', fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>
                                  {timeStr}
                                </span>
                                <span className="pill-badge neutral" style={{ fontSize: '9px' }}>
                                  {ev.event_type.replace(/_/g, ' ')}
                                </span>
                                {ev.duration_seconds && (
                                  <span style={{ color: 'var(--muted)', fontSize: '10px' }}>
                                    {ev.duration_seconds}s
                                  </span>
                                )}
                                {ev.detection_source && (
                                  <span className="pill-badge sand" style={{ fontSize: '8.5px' }}>
                                    {ev.detection_source}
                                  </span>
                                )}
                                {ev.status && (
                                  <span className={`pill-badge ${ev.status === 'resolved' ? 'olive' : 'neutral'}`} style={{ fontSize: '8.5px' }}>
                                    {ev.status}
                                  </span>
                                )}
                                {ev.details && typeof ev.details === 'object' && (ev.details as any).context && (
                                  <span style={{ color: 'var(--muted)', fontSize: '11px' }}>
                                    {(ev.details as any).context}
                                  </span>
                                )}
                              </div>

                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                {report.integrity_summary.candidate_explanations?.some((ce) => ce.event_id === ev.event_id) && (
                                  <span className="pill-badge sand" style={{ fontSize: '9px' }}>
                                    Candidate explanation attached
                                  </span>
                                )}
                                {ev.question_id ? (
                                  <span className="pill-badge olive" style={{ fontSize: '9px' }}>
                                    {qPerf ? `Question ${qPerf.question_number}` : `Question ID: ${ev.question_id}`}
                                  </span>
                                ) : (
                                  <span className="pill-badge neutral" style={{ fontSize: '9px', background: '#f5eff7' }}>
                                    Question not associated
                                  </span>
                                )}
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    ) : (
                      <p className="form-hint" style={{ marginTop: '8px', marginBottom: '4px' }}>
                        No timeline events recorded.
                      </p>
                    )}
                  </div>
                )}
              </div>

              {/* Potential Communication & Integrity Events Section */}
              {report.integrity_summary.potential_communication_events &&
                report.integrity_summary.potential_communication_events.length > 0 && (
                  <div
                    style={{
                      marginTop: '20px',
                      padding: '16px',
                      background: '#FFFBEB',
                      border: '1.5px solid #FCD34D',
                      borderRadius: '10px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                      <AlertCircle style={{ width: '18px', height: '18px', color: '#D97706', flexShrink: 0 }} />
                      <h4 style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: '#92400E' }}>
                        Potential Communication &amp; Integrity Events
                      </h4>
                      <span className="pill-badge sand" style={{ fontSize: '10px', marginLeft: 'auto' }}>
                        Potential Concern • Review Required
                      </span>
                    </div>
                    <p style={{ margin: '0 0 12px', fontSize: '11.5px', color: '#78350F', lineHeight: 1.45 }}>
                      Automated telemetry detected patterns consistent with potential secondary-party communication or ambient dialogue. In accordance with the Neutrality &amp; Fairness Commitment, this observation is flagged for human malpractice review and does NOT affect technical scores.
                    </p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {report.integrity_summary.potential_communication_events.map((commEvt, cIdx) => (
                        <div
                          key={commEvt.event_id || cIdx}
                          style={{
                            background: '#FFFFFF',
                            border: '1px solid #FDE68A',
                            borderRadius: '8px',
                            padding: '10px 12px',
                            fontSize: '11px',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '6px', marginBottom: '4px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span style={{ fontWeight: 600, color: '#92400E' }}>
                                {new Date(commEvt.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                              </span>
                              <span className="pill-badge neutral" style={{ fontSize: '9px', background: '#FEF3C7', color: '#92400E' }}>
                                {commEvt.evidence_source || 'Multimodal Telemetry'}
                              </span>
                              {commEvt.duration_seconds && (
                                <span style={{ color: 'var(--muted)', fontSize: '10px' }}>
                                  Duration: {commEvt.duration_seconds}s
                                </span>
                              )}
                            </div>
                            <span className="pill-badge sand" style={{ fontSize: '9px' }}>
                              Status: {commEvt.review_status || 'review_required'}
                            </span>
                          </div>
                          <p style={{ margin: '4px 0 0', color: '#4B5563', fontSize: '11.5px' }}>
                            {commEvt.event_description}
                          </p>
                          {commEvt.review_status && (
                            <p style={{ margin: '4px 0 0', fontSize: '10.5px', color: '#6B7280' }}>
                              <em>Evaluator Assessment: {commEvt.review_status}</em>
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

              {/* Neutrality & Fairness Commitment Callout */}
              <div className="status-callout info" style={{ marginTop: '18px', marginBottom: 0 }}>
                <ShieldCheck />
                <div>
                  <strong>Neutrality &amp; Fairness Commitment</strong>
                  <p className="form-hint">{report.integrity_summary.neutral_disclaimer}</p>
                  <p className="form-hint" style={{ marginTop: '4px', fontSize: '10px' }}>
                    *Observable window and tab changes can be caused by accidental actions, system notifications, or multi-monitor configurations and are strictly not proof of dishonesty. Scores are calculated entirely independently from these telemetry signals.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Personalized Technical Learning Roadmap */}
          {report.learning_roadmap && report.learning_roadmap.length > 0 && (
            <div style={{ marginTop: '34px' }}>
              <div style={{ marginBottom: '14px' }}>
                <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Target style={{ width: '18px', height: '18px', color: 'var(--accent)' }} />
                  Personalized Technical Learning Roadmap
                </h3>
                <p className="form-hint" style={{ marginTop: '4px', marginBottom: 0 }}>
                  Prioritized learning milestones sequenced from candidate interview gaps. Foundational concepts precede advanced topics.
                </p>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {report.learning_roadmap.map((item) => (
                  <div
                    key={item.priority_rank}
                    className="report-section-card"
                    style={{
                      padding: '16px 18px',
                      borderLeft: item.priority_rank === 1 ? '4px solid #4338A8' : item.priority_rank === 2 ? '4px solid #2e7d56' : '4px solid #d97706',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', marginBottom: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span
                          className={`pill-badge ${item.priority_rank === 1 ? 'terracotta' : item.priority_rank === 2 ? 'sand' : 'neutral'}`}
                          style={{ fontWeight: 700, fontSize: '11px' }}
                        >
                          Priority #{item.priority_rank}
                        </span>
                        <h4 style={{ margin: 0, fontSize: '15px', fontWeight: 750, color: 'var(--foreground)' }}>
                          {item.topic}
                        </h4>
                      </div>
                    </div>

                    <p style={{ margin: '0 0 10px', fontSize: '12.5px', color: '#475569', lineHeight: 1.5 }}>
                      <strong style={{ color: '#1e293b' }}>Why It Matters: </strong>
                      {item.why_it_matters}
                    </p>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '10px', background: '#f8fafc', padding: '12px 14px', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '12px' }}>
                      <div>
                        <strong style={{ color: 'var(--accent)', display: 'block', marginBottom: '2px' }}>1. What to Learn First:</strong>
                        <span style={{ color: '#334155' }}>{item.what_to_learn_first}</span>
                      </div>
                      <div>
                        <strong style={{ color: '#2e7d56', display: 'block', marginBottom: '2px' }}>2. Targeted Practice Drill:</strong>
                        <span style={{ color: '#334155' }}>{item.practice_exercise}</span>
                      </div>
                      <div>
                        <strong style={{ color: '#b45309', display: 'block', marginBottom: '2px' }}>3. Completion Criterion:</strong>
                        <span style={{ color: '#334155' }}>{item.completion_criterion}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Question-by-Question Granular Breakdown */}
          <div style={{ marginTop: '36px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', marginBottom: '14px' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 700 }}>
                  Detailed Question-by-Question Technical Assessment
                </h3>
                <p className="form-hint" style={{ marginTop: '4px', marginBottom: 0 }}>
                  In-depth analysis of candidate answers, rubric deduction mapping, solution breakdowns, and test outcomes.
                </p>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  className="button button-secondary"
                  style={{ fontSize: '11px', padding: '4px 10px', minHeight: '28px' }}
                  onClick={() => {
                    const allExp: Record<string, boolean> = {}
                    report.questions_performance.forEach((q) => {
                      allExp[q.question_id] = true
                    })
                    setExpandedQuestionIds(allExp)
                  }}
                >
                  Expand All
                </button>
                <button
                  type="button"
                  className="button button-secondary"
                  style={{ fontSize: '11px', padding: '4px 10px', minHeight: '28px' }}
                  onClick={() => setExpandedQuestionIds({})}
                >
                  Collapse All
                </button>
              </div>
            </div>

            <div className="report-q-list">
              {report.questions_performance.map((qp) => {
                const isExpanded = Boolean(expandedQuestionIds[qp.question_id])
                return (
                  <div key={qp.question_id} className="report-q-card" style={{ transition: 'all 0.2s ease' }}>
                    {/* Top Bar */}
                    <div className="report-q-top" style={{ cursor: 'pointer' }} onClick={() => toggleQuestionExpand(qp.question_id)}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                        <span className="pill-badge neutral" style={{ fontWeight: 700 }}>Question {qp.question_number}</span>
                        <span className="pill-badge sand">{qp.assessed_skill}</span>
                        <span className="pill-badge terracotta">{qp.difficulty}</span>
                        {qp.question_type && (
                          <span className="pill-badge neutral" style={{ fontSize: '10px' }}>
                            {qp.question_type.toUpperCase()}
                          </span>
                        )}
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        {qp.is_evaluated ? (
                          <span className="pill-badge olive" style={{ fontWeight: 750 }}>
                            Score: {qp.overall_score}{(qp.overall_score ?? 0) > 10 ? '/100' : '/10'}
                          </span>
                        ) : qp.is_answered ? (
                          <span className="pill-badge sand">Answered (Pending Eval)</span>
                        ) : (
                          <span className="pill-badge neutral">Unanswered</span>
                        )}
                        <button
                          type="button"
                          className="button button-secondary"
                          style={{ padding: '4px 8px', minHeight: '28px', border: 'none', background: 'transparent' }}
                          title={isExpanded ? 'Collapse analysis' : 'Expand full analysis'}
                        >
                          {isExpanded ? (
                            <ChevronUp style={{ width: '16px', height: '16px', color: 'var(--accent)' }} />
                          ) : (
                            <ChevronDown style={{ width: '16px', height: '16px', color: 'var(--muted)' }} />
                          )}
                        </button>
                      </div>
                    </div>

                    {/* Question Prompt */}
                    <p style={{ margin: '8px 0', fontSize: '14.5px', fontWeight: 650, color: 'var(--foreground)', lineHeight: 1.5 }}>
                      {qp.question_text}
                    </p>

                    {/* Collapsed Snippet Preview */}
                    {!isExpanded && (
                      <div>
                        {qp.candidate_answer_snippet && (
                          <div className="report-q-snippet" style={{ marginBottom: '4px' }}>
                            <strong>Answer Preview:</strong> &ldquo;{qp.candidate_answer_snippet}&rdquo;
                          </div>
                        )}
                        {qp.code_snippet && (
                          <div style={{ fontSize: '11px', color: 'var(--muted)', fontStyle: 'italic' }}>
                            Submitted code available • {qp.language || 'Code'} • Click to view full solution analysis
                          </div>
                        )}
                      </div>
                    )}

                    {/* Detailed Expanded View */}
                    {isExpanded && (
                      <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '18px', borderTop: '1px solid #f1f5f9', paddingTop: '16px' }}>
                        {/* Section A: Candidate's Actual Submission */}
                        <div style={{ background: '#f8fafc', padding: '14px 16px', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                            <strong style={{ fontSize: '12px', textTransform: 'uppercase', color: '#1e293b', display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <FileText style={{ width: '13px', height: '13px', color: 'var(--accent)' }} />
                              Candidate Actual Submission
                            </strong>
                            <span
                              className={`pill-badge ${
                                qp.answer_availability === 'available'
                                  ? 'olive'
                                  : qp.answer_availability === 'not_stored'
                                  ? 'sand'
                                  : 'neutral'
                              }`}
                              style={{ fontSize: '10px' }}
                            >
                              {qp.answer_availability === 'available'
                                ? 'Stored Response'
                                : qp.answer_availability === 'not_stored'
                                ? 'Text Not Stored'
                                : 'Unanswered'}
                            </span>
                          </div>

                          {qp.answer_availability === 'not_stored' ? (
                            <p style={{ margin: 0, fontSize: '12px', color: 'var(--muted)', fontStyle: 'italic' }}>
                              Original candidate answer transcript was not stored in session records for this question.
                            </p>
                          ) : qp.answer_availability === 'unanswered' ? (
                            <p style={{ margin: 0, fontSize: '12px', color: 'var(--muted)', fontStyle: 'italic' }}>
                              Candidate did not submit an answer for this question.
                            </p>
                          ) : (
                            <div>
                              {qp.full_candidate_answer ? (
                                <p style={{ margin: 0, fontSize: '13px', lineHeight: 1.6, color: '#1e293b', whiteSpace: 'pre-wrap' }}>
                                  {qp.full_candidate_answer}
                                </p>
                              ) : qp.candidate_answer_snippet ? (
                                <p style={{ margin: 0, fontSize: '13px', lineHeight: 1.6, color: '#1e293b' }}>
                                  {qp.candidate_answer_snippet}
                                </p>
                              ) : null}

                              {/* Coding Submission */}
                              {qp.full_code && (
                                <div style={{ marginTop: '10px', background: '#0f172a', color: '#e2e8f0', padding: '12px 14px', borderRadius: '8px', border: '1px solid #1e293b' }}>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                                    <span style={{ fontSize: '11px', fontWeight: 700, color: '#38bdf8' }}>
                                      Submitted Code ({qp.language || 'Python'})
                                    </span>
                                    {qp.tests_passed && (
                                      <span className="pill-badge olive" style={{ fontSize: '10px' }}>
                                        {qp.tests_passed}
                                      </span>
                                    )}
                                  </div>
                                  <pre style={{ margin: 0, fontFamily: 'monospace', fontSize: '12px', overflowX: 'auto', whiteSpace: 'pre-wrap' }}>
                                    {qp.full_code}
                                  </pre>
                                </div>
                              )}

                              {/* SQL Submission */}
                              {qp.sql_query && (
                                <div style={{ marginTop: '10px', background: '#0f172a', color: '#e2e8f0', padding: '12px 14px', borderRadius: '8px', border: '1px solid #1e293b' }}>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                                    <span style={{ fontSize: '11px', fontWeight: 700, color: '#38bdf8' }}>
                                      Submitted SQL Query
                                    </span>
                                    {qp.sql_status && (
                                      <span className="pill-badge olive" style={{ fontSize: '10px' }}>
                                        {qp.sql_status}
                                      </span>
                                    )}
                                  </div>
                                  <pre style={{ margin: 0, fontFamily: 'monospace', fontSize: '12px', overflowX: 'auto', whiteSpace: 'pre-wrap' }}>
                                    {qp.sql_query}
                                  </pre>
                                </div>
                              )}
                            </div>
                          )}
                        </div>

                        {/* Section B: What Candidate Got Right */}
                        {qp.strengths_detail && qp.strengths_detail.length > 0 && (
                          <div>
                            <strong style={{ fontSize: '12px', textTransform: 'uppercase', color: '#2e7d56', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
                              <CheckCircle2 style={{ width: '14px', height: '14px', color: '#2e7d56' }} />
                              What the Candidate Got Right
                            </strong>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                              {qp.strengths_detail.map((st, sIdx) => (
                                <div key={sIdx} style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', padding: '10px 12px' }}>
                                  <strong style={{ fontSize: '12.5px', color: '#166534', display: 'block', marginBottom: '2px' }}>
                                    ✓ {st.concept}
                                  </strong>
                                  <p style={{ margin: '0 0 6px', fontSize: '12px', color: '#14532d', lineHeight: 1.5 }}>
                                    {st.why_correct}
                                  </p>
                                  {st.evidence_quote && (
                                    <div style={{ fontSize: '11px', color: '#15803d', fontStyle: 'italic', background: '#dcfce7', padding: '4px 8px', borderRadius: '4px' }}>
                                      Evidence Quote: &ldquo;{st.evidence_quote}&rdquo;
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Section C: Weak Areas & Missing Concepts */}
                        {qp.weaknesses_detail && qp.weaknesses_detail.length > 0 && (
                          <div>
                            <strong style={{ fontSize: '12px', textTransform: 'uppercase', color: '#b45309', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
                              <AlertCircle style={{ width: '14px', height: '14px', color: '#b45309' }} />
                              Weak Areas &amp; Missing Concepts
                            </strong>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                              {qp.weaknesses_detail.map((wk, wIdx) => (
                                <div key={wIdx} style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: '8px', padding: '10px 12px' }}>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                                    <strong style={{ fontSize: '12.5px', color: '#92400e' }}>
                                      ⚠ {wk.concept}
                                    </strong>
                                    <span className="pill-badge sand" style={{ fontSize: '9.5px', textTransform: 'uppercase' }}>
                                      {wk.issue_type.replace('_', ' ')}
                                    </span>
                                  </div>
                                  <p style={{ margin: '0 0 6px', fontSize: '12px', color: '#78350f', lineHeight: 1.5 }}>
                                    {wk.technical_impact}
                                  </p>
                                  {wk.evidence_quote && (
                                    <div style={{ fontSize: '11px', color: '#854d0e', fontStyle: 'italic', background: '#fef3c7', padding: '4px 8px', borderRadius: '4px' }}>
                                      Evidence: {wk.evidence_quote}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Section D: Where Marks Were Lost (Rubric Deduction Mapping) */}
                        {qp.rubric_breakdown && qp.rubric_breakdown.length > 0 && (
                          <div>
                            <strong style={{ fontSize: '12px', textTransform: 'uppercase', color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
                              <BarChart3 style={{ width: '14px', height: '14px', color: 'var(--accent)' }} />
                              Where Marks Were Lost (Rubric Deduction Mapping)
                            </strong>
                            <div style={{ overflowX: 'auto', border: '1px solid #e2e8f0', borderRadius: '8px' }}>
                              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                                <thead>
                                  <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                                    <th style={{ padding: '8px 10px', color: '#475569' }}>Criterion</th>
                                    <th style={{ padding: '8px 10px', color: '#475569' }}>Expected Standard</th>
                                    <th style={{ padding: '8px 10px', color: '#475569' }}>Demonstrated Evidence</th>
                                    <th style={{ padding: '8px 10px', color: '#475569' }}>Score</th>
                                    <th style={{ padding: '8px 10px', color: '#475569' }}>Deduction Reason</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {qp.rubric_breakdown.map((rb, rIdx) => {
                                    const isFull = rb.score_awarded >= 9.5
                                    return (
                                      <tr key={rIdx} style={{ borderBottom: '1px solid #f1f5f9', background: rIdx % 2 === 0 ? '#ffffff' : '#fbfcfd' }}>
                                        <td style={{ padding: '8px 10px', fontWeight: 650, color: '#1e293b' }}>{rb.criterion_name}</td>
                                        <td style={{ padding: '8px 10px', color: '#64748b', fontSize: '11.5px' }}>{rb.expected_standard}</td>
                                        <td style={{ padding: '8px 10px', color: '#334155' }}>{rb.demonstrated_evidence}</td>
                                        <td style={{ padding: '8px 10px', fontWeight: 700, color: isFull ? '#2e7d56' : '#b45309' }}>
                                          {rb.score_awarded} / {rb.max_score}
                                        </td>
                                        <td style={{ padding: '8px 10px', color: isFull ? '#2e7d56' : '#b45309', fontSize: '11.5px' }}>
                                          {rb.deduction_reason}
                                        </td>
                                      </tr>
                                    )
                                  })}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}

                        {/* Section E: Correct Approach & Solution Analysis */}
                        {qp.solution_analysis && (
                          <div style={{ background: '#f8fafc', padding: '14px 16px', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                              <strong style={{ fontSize: '12px', textTransform: 'uppercase', color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <Sparkles style={{ width: '13px', height: '13px', color: 'var(--accent)' }} />
                                Correct Approach &amp; Exemplary Solution
                              </strong>
                              {qp.solution_analysis.verification_mode && (
                                <span className="pill-badge neutral" style={{ fontSize: '9.5px' }}>
                                  {qp.solution_analysis.verification_mode === 'verified_execution' ? 'Verified Sandbox Execution' : 'Static Code Review'}
                                </span>
                              )}
                            </div>

                            <p style={{ margin: '0 0 10px', fontSize: '12.5px', color: '#334155', lineHeight: 1.5 }}>
                              <strong>Expected Approach: </strong>
                              {qp.solution_analysis.expected_approach}
                            </p>

                            {/* Verbal Model Answer */}
                            {qp.solution_analysis.model_answer && (
                              <div style={{ background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: '8px', padding: '12px 14px', marginBottom: '10px' }}>
                                <strong style={{ fontSize: '11px', color: 'var(--accent)', textTransform: 'uppercase', display: 'block', marginBottom: '4px' }}>
                                  Exemplary Model Answer:
                                </strong>
                                <p style={{ margin: '0 0 8px', fontSize: '12.5px', color: '#1e293b', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                                  {qp.solution_analysis.model_answer}
                                </p>
                                {qp.solution_analysis.why_model_is_stronger && (
                                  <div style={{ fontSize: '11.5px', color: '#475569', borderTop: '1px solid #f1f5f9', paddingTop: '6px' }}>
                                    <strong style={{ color: '#2e7d56' }}>Why this solution is stronger: </strong>
                                    {qp.solution_analysis.why_model_is_stronger}
                                  </div>
                                )}
                              </div>
                            )}

                            {/* Coding Test Results Table */}
                            {qp.solution_analysis.is_coding && qp.solution_analysis.test_cases && qp.solution_analysis.test_cases.length > 0 && (
                              <div style={{ marginBottom: '10px' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                                  <strong style={{ fontSize: '11px', color: '#1e293b', textTransform: 'uppercase' }}>
                                    Automated Test Results ({qp.solution_analysis.test_cases_summary || ''})
                                  </strong>
                                </div>
                                <div style={{ overflowX: 'auto', border: '1px solid #cbd5e1', borderRadius: '6px' }}>
                                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11.5px' }}>
                                    <thead>
                                      <tr style={{ background: '#f1f5f9', borderBottom: '1px solid #cbd5e1' }}>
                                        <th style={{ padding: '6px 8px', textAlign: 'left' }}>Test Case</th>
                                        <th style={{ padding: '6px 8px', textAlign: 'left' }}>Input</th>
                                        <th style={{ padding: '6px 8px', textAlign: 'left' }}>Expected</th>
                                        <th style={{ padding: '6px 8px', textAlign: 'left' }}>Actual</th>
                                        <th style={{ padding: '6px 8px', textAlign: 'left' }}>Status</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {qp.solution_analysis.test_cases.map((tc, tcIdx) => (
                                        <tr key={tcIdx} style={{ borderBottom: '1px solid #f1f5f9', background: tc.passed ? '#f0fdf4' : '#fef2f2' }}>
                                          <td style={{ padding: '6px 8px', fontFamily: 'monospace' }}>{tc.test_case_id}</td>
                                          <td style={{ padding: '6px 8px', fontFamily: 'monospace' }}>{tc.input}</td>
                                          <td style={{ padding: '6px 8px', fontFamily: 'monospace' }}>{tc.expected_output}</td>
                                          <td style={{ padding: '6px 8px', fontFamily: 'monospace' }}>{tc.actual_output || '—'}</td>
                                          <td style={{ padding: '6px 8px', fontWeight: 700, color: tc.passed ? '#2e7d56' : '#dc2626' }}>
                                            {tc.passed ? '✓ PASSED' : '✗ FAILED'}
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            )}

                            {/* Coding Algorithmic Complexity */}
                            {qp.solution_analysis.is_coding && (
                              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '8px', fontSize: '11.5px', marginBottom: '10px' }}>
                                <div style={{ background: '#ffffff', padding: '6px 10px', borderRadius: '6px', border: '1px solid #cbd5e1' }}>
                                  <strong style={{ color: 'var(--accent)' }}>Time Complexity: </strong>
                                  <span>{qp.solution_analysis.time_complexity || 'O(N)'}</span>
                                </div>
                                <div style={{ background: '#ffffff', padding: '6px 10px', borderRadius: '6px', border: '1px solid #cbd5e1' }}>
                                  <strong style={{ color: '#2e7d56' }}>Space Complexity: </strong>
                                  <span>{qp.solution_analysis.space_complexity || 'O(1)'}</span>
                                </div>
                              </div>
                            )}

                            {/* Corrected Reference Code */}
                            {qp.solution_analysis.corrected_code && (
                              <div style={{ background: '#0f172a', color: '#e2e8f0', padding: '12px 14px', borderRadius: '8px', border: '1px solid #1e293b' }}>
                                <strong style={{ fontSize: '11px', color: '#38bdf8', textTransform: 'uppercase', display: 'block', marginBottom: '6px' }}>
                                  Corrected Reference Implementation:
                                </strong>
                                <pre style={{ margin: 0, fontFamily: 'monospace', fontSize: '11.5px', overflowX: 'auto', whiteSpace: 'pre-wrap' }}>
                                  {qp.solution_analysis.corrected_code}
                                </pre>
                              </div>
                            )}
                          </div>
                        )}

                        {/* Section F: Actionable Improvement */}
                        {qp.actionable_improvement && (
                          <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '8px', padding: '12px 14px' }}>
                            <strong style={{ fontSize: '11.5px', color: '#1e40af', textTransform: 'uppercase', display: 'block', marginBottom: '6px' }}>
                              Actionable Improvement &amp; Targeted Practice Drill
                            </strong>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '8px', fontSize: '12px' }}>
                              <div>
                                <strong style={{ color: '#1e3a8a' }}>Specific Correction: </strong>
                                <span style={{ color: '#1e40af' }}>{qp.actionable_improvement.specific_correction}</span>
                              </div>
                              <div>
                                <strong style={{ color: '#1e3a8a' }}>Concept to Study: </strong>
                                <span style={{ color: '#1e40af' }}>{qp.actionable_improvement.concept_to_study}</span>
                              </div>
                              <div>
                                <strong style={{ color: '#1e3a8a' }}>Targeted Exercise: </strong>
                                <span style={{ color: '#1e40af' }}>{qp.actionable_improvement.targeted_exercise}</span>
                              </div>
                              <div>
                                <strong style={{ color: '#1e3a8a' }}>Resolution Criterion: </strong>
                                <span style={{ color: '#1e40af' }}>{qp.actionable_improvement.resolution_criterion}</span>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>

          {/* Action Card: Next Preparation Cycle */}
          <div
            style={{
              marginTop: '32px',
              background: 'linear-gradient(135deg, #182744 0%, #2A3B5C 100%)',
              borderRadius: '16px',
              padding: '28px 24px',
              color: '#FFFFFF',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '18px',
            }}
          >
            <div>
              <h4 style={{ margin: '0 0 6px', fontSize: '17px', fontWeight: 700, color: '#FFFFFF' }}>
                Ready for Your Next Preparation Attempt?
              </h4>
              <p style={{ margin: 0, fontSize: '13px', color: '#D0D7E5', maxWidth: '580px', lineHeight: 1.5 }}>
                Review your priority improvement areas and attempt another personalized interview session to validate remaining competencies.
              </p>
            </div>
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={onStartNewInterview || onNavigateHome}
                className="button button-primary"
                style={{
                  fontSize: '13px',
                  padding: '8px 18px',
                  background: 'var(--accent, #4338A8)',
                  color: '#FFFFFF',
                }}
              >
                <Sparkles style={{ width: '14px', height: '14px' }} />
                <span>Start Next Interview Session</span>
              </button>
              <button
                type="button"
                onClick={onNavigateHome}
                className="button button-outline"
                style={{
                  fontSize: '13px',
                  padding: '8px 16px',
                  background: 'rgba(255, 255, 255, 0.1)',
                  borderColor: 'rgba(255, 255, 255, 0.25)',
                  color: '#FFFFFF',
                }}
              >
                Return to Dashboard
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function InterviewIQWorkspace({
  defaultTab,
  allowedRole,
}: {
  defaultTab?: string
  allowedRole?: 'candidate' | 'reviewer' | 'admin'
} = {}) {
  const { user, role: authRole, logout, devSwitchRole } = useAuth()
  const router = useRouter()
  const role = (authRole || allowedRole || 'candidate') as 'candidate' | 'reviewer' | 'admin'
  const userName = user?.name || (role === 'reviewer' ? 'Reviewer' : role === 'admin' ? 'Administrator' : 'Student')

  const initialTab = defaultTab || 'Overview'
  const [active, setActive] = useState(initialTab)
  const [activeSession, setActiveSession] = useState<InterviewSessionResponse | null>(null)
  const [activeMediaStream, setActiveMediaStream] = useState<MediaStream | null>(null)
  const [reportedSessionId, setReportedSessionId] = useState<string | null>(null)
  const [mobileNav, setMobileNav] = useState(false)

  const handleRoleChange = async (targetRole: 'candidate' | 'reviewer' | 'admin') => {
    try {
      await devSwitchRole(targetRole)
      if (targetRole === 'reviewer') {
        router.push('/reviewer')
      } else if (targetRole === 'admin') {
        router.push('/admin')
      } else {
        router.push('/candidate')
      }
    } catch (err) {
      console.error('Failed to switch demo role:', err)
    }
  }

  const handleLogout = () => {
    if (activeMediaStream) {
      activeMediaStream.getTracks().forEach((t) => t.stop())
      setActiveMediaStream(null)
    }
    logout()
    router.push('/login?logged_out=true')
  }

  const handleStartSession = (session: InterviewSessionResponse) => {
    setActiveSession(session)
    if (session.interview_mode === 'VERBAL') {
      setActive('Verbal Interview')
    } else {
      setActive('Coding Interview')
    }
  }

  const handleStartTechnical = () => {
    setActive('Coding Interview')
  }

  const handleStartVideo = () => {
    setActive('Verbal Interview')
  }

  const handleViewReport = (sessionId: string) => {
    setReportedSessionId(sessionId)
    setActive('Reports')
  }

  const getPageTitle = () => {
    if (active === 'Coding Interview' || active === 'Technical Assessment' || active === 'Start Interview')
      return 'Coding Interview'
    if (active === 'Verbal Interview' || active === 'Video Practice') return 'Verbal Interview'
    if (active === 'Skill Gap Analysis') return 'Resume & Skill Gap Intelligence'
    if (active === 'Candidate Intelligence') return 'Candidate Decision Intelligence'
    if (active === 'Reports' || active === 'Interview History' || active === 'Interview history')
      return 'Interview History & Reports'
    if (active === 'Communication Coach') return 'Communication Assistant'
    return 'Overview'
  }

  return (
    <div className="app-shell">
      <AppSidebar active={active} onNavigate={setActive} currentRole={role} onLogout={handleLogout} />
      <div className={`mobile-nav ${mobileNav ? 'open' : ''}`}>
        <AppSidebar
          active={active}
          onNavigate={(label) => {
            setActive(label)
            setMobileNav(false)
          }}
          currentRole={role}
          onLogout={handleLogout}
        />
      </div>
      <div className="main-shell">
        <Topbar
          title={getPageTitle()}
          onMenu={() => setMobileNav(true)}
          currentRole={role}
          userName={userName}
          onSwitchRole={handleRoleChange}
          onLogout={handleLogout}
        />
        {active === 'Coding Interview' || active === 'Technical Assessment' || active === 'Start Interview' ? (
          <InterviewRoom
            initialSession={activeSession?.interview_mode === 'CODING' ? activeSession : null}
            initialStream={activeMediaStream}
            onStreamChange={setActiveMediaStream}
            initialMode="technical"
            targetInterviewMode="CODING"
            onViewReport={handleViewReport}
            onExit={() => {
              if (activeMediaStream) {
                activeMediaStream.getTracks().forEach((t) => t.stop())
                setActiveMediaStream(null)
              }
              setActiveSession(null)
              setActive('Overview')
            }}
          />
        ) : active === 'Verbal Interview' || active === 'Video Practice' ? (
          <InterviewRoom
            initialSession={activeSession?.interview_mode === 'VERBAL' ? activeSession : null}
            initialStream={activeMediaStream}
            onStreamChange={setActiveMediaStream}
            initialMode="video"
            targetInterviewMode="VERBAL"
            onViewReport={handleViewReport}
            onExit={() => {
              if (activeMediaStream) {
                activeMediaStream.getTracks().forEach((t) => t.stop())
                setActiveMediaStream(null)
              }
              setActiveSession(null)
              setActive('Overview')
            }}
          />
        ) : active === 'Skill Gap Analysis' ? (
          <SkillGapView onStartInterview={handleStartSession} />
        ) : active === 'Candidate Intelligence' ? (
          <CandidateDecisionDashboard />
        ) : active === 'Reports' || active === 'Interview History' || active === 'Interview history' ? (
          <ReportView
            sessionId={reportedSessionId || activeSession?.session_id}
            onNavigateHome={() => setActive('Overview')}
            onStartNewInterview={() => setActive('Skill Gap Analysis')}
            currentRole={role}
          />
        ) : active === 'Communication Coach' ? (
          <CommunicationAssistant
            initialRole="Senior Full Stack Engineer"
            sessionId={activeSession?.session_id}
          />
        ) : (
          <Overview
            userName={userName}
            currentRole={role}
            onStartTechnical={handleStartTechnical}
            onStartVideo={handleStartVideo}
            onViewReport={handleViewReport}
            onNavigate={setActive}
            activeSession={activeSession}
            onResumeInterview={() =>
              setActive(activeSession?.interview_mode === 'VERBAL' ? 'Verbal Interview' : 'Coding Interview')
            }
          />
        )}
      </div>
    </div>
  )
}
