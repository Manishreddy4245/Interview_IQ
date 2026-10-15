'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import AnimatedMeshGradient from '@/components/animated-mesh-gradient'
import {
  Code2,
  Video,
  BarChart3,
  Award,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  Terminal,
  Mic,
  FileText,
  UserCheck,
  ChevronRight,
  Sparkles,
  Layers,
  Lock,
  Menu,
  X,
  ExternalLink,
} from 'lucide-react'

export default function LandingPage() {
  const { user, role, isAuthenticated, logout } = useAuth()
  const router = useRouter()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<'coding' | 'speech' | 'skillgap' | 'decision'>('coding')

  const isDev = process.env.NODE_ENV !== 'production'

  const getWorkspaceHref = () => {
    if (!isAuthenticated) return '/login'
    return '/candidate'
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        background: '#FFFFFF',
        color: 'var(--foreground, #182744)',
        fontFamily: 'Inter, system-ui, sans-serif',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* 1. NAVIGATION BAR */}
      <nav
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 50,
          background: 'rgba(255, 255, 255, 0.95)',
          backdropFilter: 'blur(8px)',
          borderBottom: '1px solid var(--border, #CCD8ED)',
          height: '68px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 32px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '32px' }}>
          <Link
            href="/"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              textDecoration: 'none',
              color: 'var(--foreground, #182744)',
              fontWeight: 700,
              fontSize: '17px',
              letterSpacing: '-0.02em',
            }}
          >
            <span
              className="brand-mark"
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '9px',
                background: 'var(--accent, #4338A8)',
                color: '#FFFFFF',
                display: 'grid',
                placeItems: 'center',
                fontSize: '12px',
                fontWeight: 700,
                boxShadow: '0 2px 8px rgba(67, 56, 168, 0.25)',
              }}
            >
              IQ
            </span>
            <span>InterviewIQ</span>
          </Link>

          {/* Desktop Nav Links */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '24px',
            }}
            className="desktop-nav-links"
          >
            <a
              href="#features"
              style={{
                fontSize: '13.5px',
                fontWeight: 500,
                color: 'var(--muted, #4F607B)',
                textDecoration: 'none',
                transition: 'color 150ms ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--accent, #4338A8)')}
              onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--muted, #4F607B)')}
            >
              Platform Features
            </a>
            <a
              href="#how-it-works"
              style={{
                fontSize: '13.5px',
                fontWeight: 500,
                color: 'var(--muted, #4F607B)',
                textDecoration: 'none',
                transition: 'color 150ms ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--accent, #4338A8)')}
              onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--muted, #4F607B)')}
            >
              How It Works
            </a>
            <a
              href="#workflow"
              style={{
                fontSize: '13.5px',
                fontWeight: 500,
                color: 'var(--muted, #4F607B)',
                textDecoration: 'none',
                transition: 'color 150ms ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--accent, #4338A8)')}
              onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--muted, #4F607B)')}
            >
              Student Workflow
            </a>
            <a
              href="#security"
              style={{
                fontSize: '13.5px',
                fontWeight: 500,
                color: 'var(--muted, #4F607B)',
                textDecoration: 'none',
                transition: 'color 150ms ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--accent, #4338A8)')}
              onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--muted, #4F607B)')}
            >
              Security &amp; RBAC
            </a>
          </div>
        </div>

        {/* Right CTA Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {isAuthenticated && user ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  background: '#F0F9FF',
                  border: '1px solid #BAE6FD',
                  borderRadius: '18px',
                  padding: '4px 10px',
                  fontSize: '11px',
                  fontWeight: 600,
                  color: '#0369a1',
                }}
              >
                <UserCheck style={{ width: '13px', height: '13px' }} />
                <span>{user.name} ({role?.toUpperCase()})</span>
              </div>
              <Link
                href={getWorkspaceHref()}
                className="button button-primary"
                style={{ textDecoration: 'none', minHeight: '36px', padding: '0 14px', fontSize: '13px' }}
              >
                <span>Go to Workspace</span>
                <ArrowRight style={{ width: '14px', height: '14px' }} />
              </Link>
              <button
                onClick={logout}
                className="button button-outline"
                style={{ minHeight: '36px', padding: '0 12px', fontSize: '12.5px' }}
              >
                Sign Out
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Link
                href="/login"
                className="button button-outline"
                style={{ textDecoration: 'none', minHeight: '38px', padding: '0 16px', fontSize: '13px' }}
              >
                Sign In
              </Link>
              <Link
                href="/register"
                className="button button-primary"
                style={{ textDecoration: 'none', minHeight: '38px', padding: '0 18px', fontSize: '13px' }}
              >
                <span>Get Started</span>
                <ArrowRight style={{ width: '14px', height: '14px' }} />
              </Link>
            </div>
          )}

          {/* Mobile hamburger button */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="icon-button"
            style={{ display: 'none' }}
            aria-label="Toggle navigation"
          >
            {mobileMenuOpen ? <X style={{ width: '20px', height: '20px' }} /> : <Menu style={{ width: '20px', height: '20px' }} />}
          </button>
        </div>
      </nav>

      {/* 2. HERO SECTION */}
      <section
        style={{
          position: 'relative',
          padding: '70px 24px 80px',
          overflow: 'hidden',
          background: 'linear-gradient(180deg, #FFFFFF 0%, #F5F8FE 100%)',
          borderBottom: '1px solid var(--border, #CCD8ED)',
        }}
      >
        <AnimatedMeshGradient />
        <div
          style={{
            maxWidth: '1100px',
            margin: '0 auto',
            position: 'relative',
            zIndex: 1,
            textAlign: 'center',
          }}
        >
          {/* Badge Pill */}
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              background: '#EEF2FF',
              border: '1px solid #CCD8ED',
              borderRadius: '24px',
              padding: '6px 14px',
              marginBottom: '20px',
              fontSize: '12px',
              fontWeight: 600,
              color: 'var(--accent, #4338A8)',
            }}
          >
            <Sparkles style={{ width: '14px', height: '14px' }} />
            <span>Real-World AI Interview Practice &amp; Decision Intelligence</span>
          </div>

          <h1
            style={{
              fontSize: 'clamp(32px, 4.5vw, 54px)',
              fontWeight: 800,
              lineHeight: 1.15,
              letterSpacing: '-0.035em',
              color: '#182744',
              margin: '0 auto 18px',
              maxWidth: '900px',
            }}
          >
            Master Technical Challenges, Voice Simulation &amp; Competency Gaps
          </h1>

          <p
            style={{
              fontSize: 'clamp(15px, 1.8vw, 17px)',
              lineHeight: 1.6,
              color: 'var(--muted, #4F607B)',
              maxWidth: '740px',
              margin: '0 auto 32px',
            }}
          >
            Practice algorithm coding in a live multi-language sandbox, rehearse verbal responses with speech telemetry,
            extract verifiable skills from your PDF resume, and generate objective rubric-grounded reports.
          </p>

          {/* Action CTAs */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '14px',
              flexWrap: 'wrap',
              marginBottom: '40px',
            }}
          >
            <Link
              href="/register"
              className="button button-primary"
              style={{
                textDecoration: 'none',
                minHeight: '46px',
                padding: '0 24px',
                fontSize: '14.5px',
                fontWeight: 650,
                boxShadow: '0 4px 14px rgba(67, 56, 168, 0.28)',
              }}
            >
              <span>Get Started Free</span>
              <ArrowRight style={{ width: '16px', height: '16px' }} />
            </Link>

            <Link
              href="/login"
              className="button button-secondary"
              style={{
                textDecoration: 'none',
                minHeight: '46px',
                padding: '0 22px',
                fontSize: '14px',
                fontWeight: 600,
              }}
            >
              <span>Sign In to Workspace</span>
            </Link>

            {isDev && (
              <Link
                href="/candidate"
                className="button button-outline"
                style={{
                  textDecoration: 'none',
                  minHeight: '46px',
                  padding: '0 16px',
                  fontSize: '13px',
                  color: '#059669',
                  borderColor: '#A7F3D0',
                  background: '#ECFDF5',
                }}
                title="Direct candidate access in development mode"
              >
                <span>[DEV] Live Candidate Demo</span>
              </Link>
            )}
          </div>

          {/* Feature Highlights Strip */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '24px',
              flexWrap: 'wrap',
              paddingTop: '20px',
              borderTop: '1px solid rgba(204, 216, 237, 0.6)',
              fontSize: '12.5px',
              fontWeight: 500,
              color: 'var(--muted, #4F607B)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <CheckCircle2 style={{ width: '15px', height: '15px', color: '#10B981' }} />
              <span>Monaco IDE &amp; Multi-Language Sandbox</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <CheckCircle2 style={{ width: '15px', height: '15px', color: '#10B981' }} />
              <span>Spoken Transcription &amp; Filler Word Counter</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <CheckCircle2 style={{ width: '15px', height: '15px', color: '#10B981' }} />
              <span>Resume PDF Skill Extraction</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <CheckCircle2 style={{ width: '15px', height: '15px', color: '#10B981' }} />
              <span>Server-Enforced RBAC &amp; Data Isolation</span>
            </div>
          </div>
        </div>
      </section>

      {/* 3. FOUR CORE PRODUCT FEATURE PILLARS */}
      <section
        id="features"
        style={{
          padding: '80px 24px',
          maxWidth: '1180px',
          margin: '0 auto',
          width: '100%',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '48px' }}>
          <p
            style={{
              textTransform: 'uppercase',
              letterSpacing: '0.12em',
              fontSize: '11px',
              fontWeight: 700,
              color: 'var(--accent, #4338A8)',
              margin: '0 0 8px',
            }}
          >
            Genuine Platform Capabilities
          </p>
          <h2
            style={{
              fontSize: 'clamp(26px, 3.2vw, 36px)',
              fontWeight: 800,
              letterSpacing: '-0.03em',
              color: '#182744',
              margin: '0 0 12px',
            }}
          >
            Four Integrated Pillars for Complete Interview Readiness
          </h2>
          <p
            style={{
              fontSize: '14.5px',
              color: 'var(--muted, #4F607B)',
              maxWidth: '650px',
              margin: '0 auto',
              lineHeight: 1.6,
            }}
          >
            Every feature runs on the actual InterviewIQ backend engine — tested with sandboxed execution,
            auditable telemetry, and strict RBAC isolation.
          </p>
        </div>

        {/* 4 Feature Cards Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: '24px',
          }}
        >
          {/* Card 1: Technical Assessment */}
          <div
            style={{
              background: '#FFFFFF',
              border: '1.5px solid var(--border, #CCD8ED)',
              borderRadius: '16px',
              padding: '28px 24px',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 2px 8px rgba(24, 39, 68, 0.05)',
              transition: 'all 200ms ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translateY(-3px)'
              e.currentTarget.style.borderColor = 'var(--accent, #4338A8)'
              e.currentTarget.style.boxShadow = '0 10px 24px rgba(67, 56, 168, 0.12)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0)'
              e.currentTarget.style.borderColor = 'var(--border, #CCD8ED)'
              e.currentTarget.style.boxShadow = '0 2px 8px rgba(24, 39, 68, 0.05)'
            }}
          >
            <div
              style={{
                width: '44px',
                height: '44px',
                borderRadius: '11px',
                background: '#EEF2FF',
                color: 'var(--accent, #4338A8)',
                display: 'grid',
                placeItems: 'center',
                marginBottom: '18px',
              }}
            >
              <Code2 style={{ width: '22px', height: '22px' }} />
            </div>
            <h3 style={{ fontSize: '17px', fontWeight: 700, margin: '0 0 8px', color: '#182744' }}>
              Technical Assessment
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--muted, #4F607B)', lineHeight: 1.6, margin: '0 0 16px', flex: 1 }}>
              Full Monaco code editor supporting Python, JavaScript, TypeScript, C++, Java, Go, Rust, and SQL. Run code
              against visible &amp; hidden test cases, inspect execution times, and execute queries against relational SQLite schemas.
            </p>
            <div style={{ borderTop: '1px solid #EEF2FF', paddingTop: '14px' }}>
              <Link
                href="/login?redirect=/candidate"
                style={{
                  fontSize: '12.5px',
                  fontWeight: 650,
                  color: 'var(--accent, #4338A8)',
                  textDecoration: 'none',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <span>Launch Coding IDE</span>
                <ChevronRight style={{ width: '14px', height: '14px' }} />
              </Link>
            </div>
          </div>

          {/* Card 2: AI Video & Spoken Practice Studio */}
          <div
            style={{
              background: '#FFFFFF',
              border: '1.5px solid var(--border, #CCD8ED)',
              borderRadius: '16px',
              padding: '28px 24px',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 2px 8px rgba(24, 39, 68, 0.05)',
              transition: 'all 200ms ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translateY(-3px)'
              e.currentTarget.style.borderColor = 'var(--accent, #4338A8)'
              e.currentTarget.style.boxShadow = '0 10px 24px rgba(67, 56, 168, 0.12)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0)'
              e.currentTarget.style.borderColor = 'var(--border, #CCD8ED)'
              e.currentTarget.style.boxShadow = '0 2px 8px rgba(24, 39, 68, 0.05)'
            }}
          >
            <div
              style={{
                width: '44px',
                height: '44px',
                borderRadius: '11px',
                background: '#ECFDF5',
                color: '#059669',
                display: 'grid',
                placeItems: 'center',
                marginBottom: '18px',
              }}
            >
              <Video style={{ width: '22px', height: '22px' }} />
            </div>
            <h3 style={{ fontSize: '17px', fontWeight: 700, margin: '0 0 8px', color: '#182744' }}>
              AI Video &amp; Voice Practice
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--muted, #4F607B)', lineHeight: 1.6, margin: '0 0 16px', flex: 1 }}>
              Simulate high-pressure video screens with live camera preview, natural speech synthesis question audio, real-time
              speech-to-text transcription, filler-word tracking (like, um, basically), and structured STAR framework advice.
            </p>
            <div style={{ borderTop: '1px solid #EEF2FF', paddingTop: '14px' }}>
              <Link
                href="/login?redirect=/candidate"
                style={{
                  fontSize: '12.5px',
                  fontWeight: 650,
                  color: 'var(--accent, #4338A8)',
                  textDecoration: 'none',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <span>Open Practice Studio</span>
                <ChevronRight style={{ width: '14px', height: '14px' }} />
              </Link>
            </div>
          </div>

          {/* Card 3: Skill Gap Analysis */}
          <div
            style={{
              background: '#FFFFFF',
              border: '1.5px solid var(--border, #CCD8ED)',
              borderRadius: '16px',
              padding: '28px 24px',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 2px 8px rgba(24, 39, 68, 0.05)',
              transition: 'all 200ms ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translateY(-3px)'
              e.currentTarget.style.borderColor = 'var(--accent, #4338A8)'
              e.currentTarget.style.boxShadow = '0 10px 24px rgba(67, 56, 168, 0.12)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0)'
              e.currentTarget.style.borderColor = 'var(--border, #CCD8ED)'
              e.currentTarget.style.boxShadow = '0 2px 8px rgba(24, 39, 68, 0.05)'
            }}
          >
            <div
              style={{
                width: '44px',
                height: '44px',
                borderRadius: '11px',
                background: '#F0F9FF',
                color: '#0284c7',
                display: 'grid',
                placeItems: 'center',
                marginBottom: '18px',
              }}
            >
              <BarChart3 style={{ width: '22px', height: '22px' }} />
            </div>
            <h3 style={{ fontSize: '17px', fontWeight: 700, margin: '0 0 8px', color: '#182744' }}>
              Skill Gap Analysis
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--muted, #4F607B)', lineHeight: 1.6, margin: '0 0 16px', flex: 1 }}>
              Upload your PDF resume to extract evidenced technical capabilities, benchmark against target job titles
              from Mid-Level to Staff, surface unevidenced gap areas, and auto-generate personalized practice questions.
            </p>
            <div style={{ borderTop: '1px solid #EEF2FF', paddingTop: '14px' }}>
              <Link
                href="/login?redirect=/candidate"
                style={{
                  fontSize: '12.5px',
                  fontWeight: 650,
                  color: 'var(--accent, #4338A8)',
                  textDecoration: 'none',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <span>Upload &amp; Analyze Resume</span>
                <ChevronRight style={{ width: '14px', height: '14px' }} />
              </Link>
            </div>
          </div>

          {/* Card 4: Performance Reports & Decision Intelligence */}
          <div
            style={{
              background: '#FFFFFF',
              border: '1.5px solid var(--border, #CCD8ED)',
              borderRadius: '16px',
              padding: '28px 24px',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 2px 8px rgba(24, 39, 68, 0.05)',
              transition: 'all 200ms ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translateY(-3px)'
              e.currentTarget.style.borderColor = 'var(--accent, #4338A8)'
              e.currentTarget.style.boxShadow = '0 10px 24px rgba(67, 56, 168, 0.12)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0)'
              e.currentTarget.style.borderColor = 'var(--border, #CCD8ED)'
              e.currentTarget.style.boxShadow = '0 2px 8px rgba(24, 39, 68, 0.05)'
            }}
          >
            <div
              style={{
                width: '44px',
                height: '44px',
                borderRadius: '11px',
                background: '#F5F3FF',
                color: '#7c3aed',
                display: 'grid',
                placeItems: 'center',
                marginBottom: '18px',
              }}
            >
              <Award style={{ width: '22px', height: '22px' }} />
            </div>
            <h3 style={{ fontSize: '17px', fontWeight: 700, margin: '0 0 8px', color: '#182744' }}>
              Reports &amp; Decision Intelligence
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--muted, #4F607B)', lineHeight: 1.6, margin: '0 0 16px', flex: 1 }}>
              Review objective multi-criterion rubric evaluations (technical depth, clarity, structure), auditable neutral
              integrity event timelines, and decision dossiers for verified Reviewers with zero automated hiring rejections.
            </p>
            <div style={{ borderTop: '1px solid #EEF2FF', paddingTop: '14px' }}>
              <Link
                href="/login?redirect=/reviewer"
                style={{
                  fontSize: '12.5px',
                  fontWeight: 650,
                  color: 'var(--accent, #4338A8)',
                  textDecoration: 'none',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <span>Inspect Hiring Dossiers</span>
                <ChevronRight style={{ width: '14px', height: '14px' }} />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* 4. HOW IT WORKS SECTION */}
      <section
        id="how-it-works"
        style={{
          background: '#F8FAFE',
          borderTop: '1px solid var(--border, #CCD8ED)',
          borderBottom: '1px solid var(--border, #CCD8ED)',
          padding: '80px 24px',
        }}
      >
        <div style={{ maxWidth: '1060px', margin: '0 auto' }}>
          <div style={{ textAlign: 'center', marginBottom: '48px' }}>
            <p
              style={{
                textTransform: 'uppercase',
                letterSpacing: '0.12em',
                fontSize: '11px',
                fontWeight: 700,
                color: 'var(--accent, #4338A8)',
                margin: '0 0 8px',
              }}
            >
              Transparent Workflow
            </p>
            <h2
              style={{
                fontSize: 'clamp(26px, 3.2vw, 36px)',
                fontWeight: 800,
                letterSpacing: '-0.03em',
                color: '#182744',
                margin: '0 0 12px',
              }}
            >
              How InterviewIQ Works
            </h2>
            <p style={{ fontSize: '14.5px', color: 'var(--muted, #4F607B)', maxWidth: '600px', margin: '0 auto' }}>
              From initial role target to verifiable skill verification in three objective steps.
            </p>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
              gap: '28px',
            }}
          >
            {/* Step 1 */}
            <div
              style={{
                background: '#FFFFFF',
                border: '1px solid var(--border, #CCD8ED)',
                borderRadius: '14px',
                padding: '28px 24px',
                position: 'relative',
              }}
            >
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  background: 'var(--accent, #4338A8)',
                  color: '#FFFFFF',
                  fontWeight: 700,
                  fontSize: '13px',
                  display: 'grid',
                  placeItems: 'center',
                  marginBottom: '16px',
                }}
              >
                1
              </div>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#182744', margin: '0 0 8px' }}>
                Define Role or Upload Resume
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--muted, #4F607B)', lineHeight: 1.6, margin: 0 }}>
                Select your target role and seniority, or upload an existing PDF resume. The system identifies demonstrated
                competencies and prioritizes unevidenced areas for targeted questioning.
              </p>
            </div>

            {/* Step 2 */}
            <div
              style={{
                background: '#FFFFFF',
                border: '1px solid var(--border, #CCD8ED)',
                borderRadius: '14px',
                padding: '28px 24px',
                position: 'relative',
              }}
            >
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  background: 'var(--accent, #4338A8)',
                  color: '#FFFFFF',
                  fontWeight: 700,
                  fontSize: '13px',
                  display: 'grid',
                  placeItems: 'center',
                  marginBottom: '16px',
                }}
              >
                2
              </div>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#182744', margin: '0 0 8px' }}>
                Practice in Real-Time Environments
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--muted, #4F607B)', lineHeight: 1.6, margin: 0 }}>
                Solve algorithmic code problems with sandbox test execution, run SQL queries against real schema fixtures,
                and answer behavioral prompts with real-time speech telemetry and pacing feedback.
              </p>
            </div>

            {/* Step 3 */}
            <div
              style={{
                background: '#FFFFFF',
                border: '1px solid var(--border, #CCD8ED)',
                borderRadius: '14px',
                padding: '28px 24px',
                position: 'relative',
              }}
            >
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  background: 'var(--accent, #4338A8)',
                  color: '#FFFFFF',
                  fontWeight: 700,
                  fontSize: '13px',
                  display: 'grid',
                  placeItems: 'center',
                  marginBottom: '16px',
                }}
              >
                3
              </div>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#182744', margin: '0 0 8px' }}>
                Review Objective Rubrics &amp; Reports
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--muted, #4F607B)', lineHeight: 1.6, margin: 0 }}>
                Receive transparent, objective feedback across technical depth, structure, and execution accuracy, grounded
                directly in your actual submitted answers and code executions.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 5. STUDENT-ONLY END-TO-END WORKFLOW */}
      <section
        id="workflow"
        style={{
          padding: '80px 24px',
          maxWidth: '1100px',
          margin: '0 auto',
          width: '100%',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '44px' }}>
          <p
            style={{
              textTransform: 'uppercase',
              letterSpacing: '0.12em',
              fontSize: '11px',
              fontWeight: 700,
              color: 'var(--accent, #4338A8)',
              margin: '0 0 8px',
            }}
          >
            Personalized Job Preparation
          </p>
          <h2
            style={{
              fontSize: 'clamp(26px, 3.2vw, 36px)',
              fontWeight: 800,
              letterSpacing: '-0.03em',
              color: '#182744',
              margin: '0 0 12px',
            }}
          >
            Student-Centric End-to-End Preparation Workflow
          </h2>
          <p style={{ fontSize: '14.5px', color: 'var(--muted, #4F607B)', maxWidth: '680px', margin: '0 auto' }}>
            A rigorous, evidence-grounded preparation pathway designed exclusively for engineering students to master technical interviews.
          </p>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
            gap: '20px',
          }}
        >
          {/* Step 1: Resume Upload & Extraction */}
          <div
            style={{
              background: '#FFFFFF',
              border: '1.5px solid #CCD8ED',
              borderRadius: '16px',
              padding: '24px 20px',
              boxShadow: '0 4px 14px rgba(67, 56, 168, 0.04)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <div>
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  background: '#EEF2FF',
                  color: 'var(--accent, #4338A8)',
                  padding: '4px 10px',
                  borderRadius: '16px',
                  fontSize: '11px',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  marginBottom: '14px',
                }}
              >
                Phases 1 &amp; 2
              </div>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#182744', margin: '0 0 8px' }}>
                Resume Parsing &amp; Skill Extraction
              </h3>
              <p style={{ fontSize: '12.5px', color: 'var(--muted, #4F607B)', lineHeight: 1.6, margin: '0 0 14px' }}>
                Upload your actual resume in PDF or text format. The system extracts verified technical skills, projects, and education.
              </p>
              <ul style={{ margin: '0 0 16px', paddingLeft: '16px', fontSize: '12px', color: 'var(--foreground, #182744)', lineHeight: 1.7 }}>
                <li>Identifies real skills &amp; project context</li>
                <li>Zero fabricated candidate profiles</li>
                <li>Interactive student correction workflow</li>
              </ul>
            </div>
            <div style={{ borderTop: '1px solid #EEF2FF', paddingTop: '10px', fontSize: '11.5px', color: '#6B7280' }}>
              ✦ Full student account data privacy
            </div>
          </div>

          {/* Step 2: Target Role & Pre-Interview Gap Analysis */}
          <div
            style={{
              background: '#FFFFFF',
              border: '1.5px solid #A7F3D0',
              borderRadius: '16px',
              padding: '24px 20px',
              boxShadow: '0 4px 14px rgba(16, 185, 129, 0.06)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <div>
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  background: '#ECFDF5',
                  color: '#047857',
                  padding: '4px 10px',
                  borderRadius: '16px',
                  fontSize: '11px',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  marginBottom: '14px',
                }}
              >
                Phases 3 &amp; 4
              </div>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#182744', margin: '0 0 8px' }}>
                Role Benchmarking &amp; Gap Analysis
              </h3>
              <p style={{ fontSize: '12.5px', color: 'var(--muted, #4F607B)', lineHeight: 1.6, margin: '0 0 14px' }}>
                Choose your target engineering role to benchmark your resume against standardized industry competencies.
              </p>
              <ul style={{ margin: '0 0 16px', paddingLeft: '16px', fontSize: '12px', color: 'var(--foreground, #182744)', lineHeight: 1.7 }}>
                <li>Categorizes competencies with clear evidence</li>
                <li>Pre-interview gap assessment &amp; score</li>
                <li>Establishes initial interview priorities</li>
              </ul>
            </div>
            <div style={{ borderTop: '1px solid #EEF2FF', paddingTop: '10px', fontSize: '11.5px', color: '#6B7280' }}>
              ✦ Role catalogs: Frontend, Backend, Full Stack, ML
            </div>
          </div>

          {/* Step 3: Sequential Adaptive Interview */}
          <div
            style={{
              background: '#FFFFFF',
              border: '1.5px solid #BAE6FD',
              borderRadius: '16px',
              padding: '24px 20px',
              boxShadow: '0 4px 14px rgba(2, 132, 199, 0.06)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <div>
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  background: '#F0F9FF',
                  color: '#0369a1',
                  padding: '4px 10px',
                  borderRadius: '16px',
                  fontSize: '11px',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  marginBottom: '14px',
                }}
              >
                Phases 5, 6 &amp; 7
              </div>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#182744', margin: '0 0 8px' }}>
                Sequential Adaptive Interview
              </h3>
              <p style={{ fontSize: '12.5px', color: 'var(--muted, #4F607B)', lineHeight: 1.6, margin: '0 0 14px' }}>
                Strict sequential interview progression. The backend issues one active question at a time and adapts dynamically.
              </p>
              <ul style={{ margin: '0 0 16px', paddingLeft: '16px', fontSize: '12px', color: 'var(--foreground, #182744)', lineHeight: 1.7 }}>
                <li>Zero future questions leaked to frontend</li>
                <li>Live answer evaluation before next question</li>
                <li>Adaptive difficulty and follow-up probes</li>
              </ul>
            </div>
            <div style={{ borderTop: '1px solid #EEF2FF', paddingTop: '10px', fontSize: '11.5px', color: '#6B7280' }}>
              ✦ Coding, Verbal, System Design &amp; SQL modes
            </div>
          </div>

          {/* Step 4: Post-Interview Gap & Improvement Plan */}
          <div
            style={{
              background: '#FFFFFF',
              border: '1.5px solid #DDD6FE',
              borderRadius: '16px',
              padding: '24px 20px',
              boxShadow: '0 4px 14px rgba(124, 58, 237, 0.06)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <div>
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  background: '#F5F3FF',
                  color: '#6d28d9',
                  padding: '4px 10px',
                  borderRadius: '16px',
                  fontSize: '11px',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  marginBottom: '14px',
                }}
              >
                Phases 8, 9 &amp; 10
              </div>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#182744', margin: '0 0 8px' }}>
                Updated Gap Analysis &amp; Feedback
              </h3>
              <p style={{ fontSize: '12.5px', color: 'var(--muted, #4F607B)', lineHeight: 1.6, margin: '0 0 14px' }}>
                Upon interview completion, receive an evidence-grounded report comparing resume claims with proven performance.
              </p>
              <ul style={{ margin: '0 0 16px', paddingLeft: '16px', fontSize: '12px', color: 'var(--foreground, #182744)', lineHeight: 1.7 }}>
                <li>Competencies updated from actual answers</li>
                <li>Identifies confirmed strengths &amp; weak areas</li>
                <li>Actionable improvement plan for next attempt</li>
              </ul>
            </div>
            <div style={{ borderTop: '1px solid #EEF2FF', paddingTop: '10px', fontSize: '11.5px', color: '#6B7280' }}>
              ✦ Persisted report &amp; progress on Student Dashboard
            </div>
          </div>
        </div>

        {/* Workflow CTA Banner */}
        <div
          style={{
            marginTop: '32px',
            background: 'linear-gradient(135deg, #182744 0%, #2A3B5C 100%)',
            borderRadius: '16px',
            padding: '32px 28px',
            color: '#FFFFFF',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '20px',
          }}
        >
          <div>
            <h3 style={{ fontSize: '19px', fontWeight: 800, margin: '0 0 6px', color: '#FFFFFF' }}>
              Start Your Personalized Student Preparation
            </h3>
            <p style={{ margin: 0, fontSize: '13.5px', color: '#D0D7E5', maxWidth: '580px', lineHeight: 1.5 }}>
              Upload your resume, select your target role, and practice with sequentially adaptive technical interviews designed to build verified engineering confidence.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <Link
              href="/register"
              className="button button-primary"
              style={{
                textDecoration: 'none',
                minHeight: '40px',
                padding: '0 20px',
                fontSize: '13.5px',
                background: 'var(--accent, #4338A8)',
                color: '#FFFFFF',
              }}
            >
              <span>Register as Student</span>
              <ArrowRight style={{ width: '15px', height: '15px' }} />
            </Link>
            <Link
              href="/login"
              className="button button-outline"
              style={{
                textDecoration: 'none',
                minHeight: '40px',
                padding: '0 18px',
                fontSize: '13.5px',
                background: 'rgba(255, 255, 255, 0.1)',
                borderColor: 'rgba(255, 255, 255, 0.25)',
                color: '#FFFFFF',
              }}
            >
              Sign In to Dashboard
            </Link>
          </div>
        </div>
      </section>

      {/* 6. SECURITY & RBAC CALLOUT */}
      <section
        id="security"
        style={{
          background: 'linear-gradient(180deg, #F8FAFE 0%, #EEF2FF 100%)',
          borderTop: '1px solid var(--border, #CCD8ED)',
          padding: '60px 24px',
        }}
      >
        <div
          style={{
            maxWidth: '900px',
            margin: '0 auto',
            background: '#FFFFFF',
            border: '1.5px solid var(--border, #CCD8ED)',
            borderRadius: '16px',
            padding: '36px',
            boxShadow: '0 8px 30px rgba(67, 56, 168, 0.08)',
            display: 'flex',
            gap: '24px',
            alignItems: 'center',
            flexWrap: 'wrap',
          }}
        >
          <div
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '14px',
              background: '#EEF2FF',
              color: 'var(--accent, #4338A8)',
              display: 'grid',
              placeItems: 'center',
              flexShrink: 0,
            }}
          >
            <ShieldCheck style={{ width: '30px', height: '30px' }} />
          </div>

          <div style={{ flex: 1, minWidth: '280px' }}>
            <h3 style={{ margin: '0 0 6px', fontSize: '18px', fontWeight: 700, color: '#182744' }}>
              Cryptographically Enforced Role-Based Security
            </h3>
            <p style={{ margin: 0, fontSize: '13.5px', color: 'var(--muted, #4F607B)', lineHeight: 1.6 }}>
              InterviewIQ does not rely on frontend-only guards. All session operations, dossier retrievals, and review submissions
              are authorized via HMAC-SHA256 signed JWT tokens on the FastAPI backend. Candidate-to-candidate data isolation
              is strictly verified.
            </p>
          </div>
        </div>
      </section>

      {/* 7. FOOTER */}
      <footer
        style={{
          borderTop: '1px solid var(--border, #CCD8ED)',
          background: '#FFFFFF',
          padding: '40px 32px 30px',
          marginTop: 'auto',
        }}
      >
        <div
          style={{
            maxWidth: '1100px',
            margin: '0 auto',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '20px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span
              className="brand-mark"
              style={{
                width: '28px',
                height: '28px',
                borderRadius: '8px',
                background: 'var(--accent, #4338A8)',
                color: '#FFFFFF',
                display: 'grid',
                placeItems: 'center',
                fontSize: '11px',
                fontWeight: 700,
              }}
            >
              IQ
            </span>
            <span style={{ fontWeight: 700, fontSize: '15px', color: '#182744' }}>InterviewIQ</span>
            <span style={{ fontSize: '12px', color: 'var(--muted, #4F607B)', marginLeft: '12px' }}>
              &copy; {new Date().getFullYear()} InterviewIQ Platform. Practice with intention.
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '20px', fontSize: '12.5px' }}>
            <Link href="/candidate" style={{ color: 'var(--muted, #4F607B)', textDecoration: 'none' }}>
              Candidate Workspace
            </Link>
            <Link href="/reviewer" style={{ color: 'var(--muted, #4F607B)', textDecoration: 'none' }}>
              Reviewer Portal
            </Link>
            <Link href="/admin" style={{ color: 'var(--muted, #4F607B)', textDecoration: 'none' }}>
              Admin Portal
            </Link>
            <Link href="/login" style={{ color: 'var(--accent, #4338A8)', fontWeight: 600, textDecoration: 'none' }}>
              Sign In
            </Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
