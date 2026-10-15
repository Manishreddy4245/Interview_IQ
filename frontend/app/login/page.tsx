'use client'

import React, { useState, useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/lib/auth-context'
import {
  Lock,
  User,
  Eye,
  EyeOff,
  AlertCircle,
  CheckCircle2,
  ArrowRight,
  ShieldCheck,
  Info,
  Loader2,
  Sparkles,
  UserCheck,
} from 'lucide-react'

function LoginForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { login, isAuthenticated, role, devSwitchRole } = useAuth()

  const redirectParam = searchParams.get('redirect')
  const expired = searchParams.get('expired') === 'true'
  const loggedOut = searchParams.get('logged_out') === 'true'
  const registered = searchParams.get('registered') === 'true'

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showForgotModal, setShowForgotModal] = useState(false)

  // If already authenticated and not loading, redirect to authorized workspace
  useEffect(() => {
    if (isAuthenticated && role) {
      const destination =
        redirectParam || (role === 'reviewer' ? '/reviewer' : role === 'admin' ? '/admin' : '/candidate')
      router.replace(destination)
    }
  }, [isAuthenticated, role, redirectParam, router])

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    const cleanUsername = username.trim()
    if (!cleanUsername) {
      setError('Please enter your username or email address.')
      return
    }
    if (!password) {
      setError('Please enter your password.')
      return
    }

    setLoading(true)
    try {
      const res = await login({ username: cleanUsername, password })
      // Check authorized redirect
      const userRole = res.role
      let targetRoute = redirectParam || (userRole === 'reviewer' ? '/reviewer' : userRole === 'admin' ? '/admin' : '/candidate')

      // Validate that role has permission for targetRoute
      if (targetRoute === '/reviewer' && userRole === 'candidate') {
        targetRoute = '/candidate'
      } else if (targetRoute === '/admin' && userRole !== 'admin') {
        targetRoute = userRole === 'reviewer' ? '/reviewer' : '/candidate'
      }

      router.push(targetRoute)
    } catch (err: any) {
      console.error('Login error:', err)
      setError(err.message || 'Invalid username or password. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleQuickFill = (u: string, p: string) => {
    setUsername(u)
    setPassword(p)
    setError(null)
  }

  const isDev = process.env.NODE_ENV !== 'production'

  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'var(--background, #F3F6FC)',
        display: 'flex',
        flexDirection: 'column',
        fontFamily: 'Inter, system-ui, sans-serif',
        color: 'var(--foreground, #182744)',
      }}
    >
      {/* Top Brand Bar */}
      <header
        style={{
          height: '64px',
          borderBottom: '1px solid var(--border, #CCD8ED)',
          background: '#FFFFFF',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 32px',
        }}
      >
        <Link
          href="/"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            textDecoration: 'none',
            color: 'var(--foreground, #182744)',
            fontWeight: 700,
            fontSize: '16px',
            letterSpacing: '-0.02em',
          }}
        >
          <span className="brand-mark" style={{ width: '30px', height: '30px', borderRadius: '8px', fontSize: '11px' }}>
            IQ
          </span>
          <span>InterviewIQ</span>
        </Link>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <span style={{ fontSize: '13px', color: 'var(--muted, #4F607B)' }}>New candidate?</span>
          <Link
            href="/register"
            className="button button-outline"
            style={{ minHeight: '34px', padding: '0 14px', fontSize: '12.5px', textDecoration: 'none' }}
          >
            Create Account
          </Link>
        </div>
      </header>

      {/* Main Container */}
      <main
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '40px 20px',
        }}
      >
        <div
          style={{
            maxWidth: '440px',
            width: '100%',
            background: '#FFFFFF',
            border: '1.5px solid var(--border, #CCD8ED)',
            borderRadius: '16px',
            padding: '36px 32px',
            boxShadow: '0 10px 30px rgba(24, 39, 68, 0.07)',
          }}
        >
          <div style={{ textAlign: 'center', marginBottom: '24px' }}>
            <div
              style={{
                width: '44px',
                height: '44px',
                margin: '0 auto 12px',
                borderRadius: '12px',
                background: 'var(--accent, #4338A8)',
                color: '#FFFFFF',
                display: 'grid',
                placeItems: 'center',
                boxShadow: '0 4px 12px rgba(67, 56, 168, 0.25)',
              }}
            >
              <Lock style={{ width: '20px', height: '20px' }} />
            </div>
            <h1 style={{ fontSize: '22px', fontWeight: 700, margin: '0 0 6px', color: '#182744' }}>
              Sign In to InterviewIQ
            </h1>
            <p style={{ margin: 0, fontSize: '13px', color: 'var(--muted, #4F607B)' }}>
              Enter your credentials to access your authorized workspace.
            </p>
          </div>

          {/* Context Alerts */}
          {expired && (
            <div
              style={{
                background: '#FEF2F2',
                border: '1px solid #FECACA',
                color: '#991B1B',
                borderRadius: '8px',
                padding: '10px 14px',
                fontSize: '12.5px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                marginBottom: '18px',
              }}
            >
              <AlertCircle style={{ width: '16px', height: '16px', flexShrink: 0 }} />
              <span>Your session has expired. Please authenticate again.</span>
            </div>
          )}

          {loggedOut && (
            <div
              style={{
                background: '#F0FDF4',
                border: '1px solid #BBF7D0',
                color: '#166534',
                borderRadius: '8px',
                padding: '10px 14px',
                fontSize: '12.5px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                marginBottom: '18px',
              }}
            >
              <CheckCircle2 style={{ width: '16px', height: '16px', flexShrink: 0 }} />
              <span>You have been safely signed out.</span>
            </div>
          )}

          {registered && (
            <div
              style={{
                background: '#F0FDF4',
                border: '1px solid #BBF7D0',
                color: '#166534',
                borderRadius: '8px',
                padding: '10px 14px',
                fontSize: '12.5px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                marginBottom: '18px',
              }}
            >
              <CheckCircle2 style={{ width: '16px', height: '16px', flexShrink: 0 }} />
              <span>Candidate account created successfully! Please sign in.</span>
            </div>
          )}

          {error && (
            <div
              style={{
                background: '#FEF2F2',
                border: '1px solid #FECACA',
                color: '#991B1B',
                borderRadius: '8px',
                padding: '10px 14px',
                fontSize: '12.5px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                marginBottom: '18px',
              }}
            >
              <AlertCircle style={{ width: '16px', height: '16px', flexShrink: 0 }} />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label
                htmlFor="login-username"
                style={{
                  display: 'block',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: '#182744',
                  marginBottom: '6px',
                }}
              >
                Username or Email
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  id="login-username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. candidate_demo or candidate@interviewiq.com"
                  autoComplete="username"
                  disabled={loading}
                  style={{
                    width: '100%',
                    height: '40px',
                    padding: '0 12px 0 36px',
                    borderRadius: '8px',
                    border: '1px solid var(--border, #CCD8ED)',
                    background: '#FFFFFF',
                    color: '#182744',
                    fontSize: '13px',
                    outline: 'none',
                    transition: 'border-color 150ms ease',
                  }}
                  onFocus={(e) => (e.target.style.borderColor = 'var(--accent, #4338A8)')}
                  onBlur={(e) => (e.target.style.borderColor = 'var(--border, #CCD8ED)')}
                />
                <User
                  style={{
                    position: 'absolute',
                    left: '11px',
                    top: '12px',
                    width: '16px',
                    height: '16px',
                    color: 'var(--muted, #4F607B)',
                    pointerEvents: 'none',
                  }}
                />
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                <label
                  htmlFor="login-password"
                  style={{
                    fontSize: '12px',
                    fontWeight: 600,
                    color: '#182744',
                  }}
                >
                  Password
                </label>
                <button
                  type="button"
                  onClick={() => setShowForgotModal(true)}
                  style={{
                    border: 0,
                    background: 'transparent',
                    fontSize: '11.5px',
                    color: 'var(--accent, #4338A8)',
                    cursor: 'pointer',
                    padding: 0,
                    fontWeight: 500,
                  }}
                >
                  Forgot password?
                </button>
              </div>
              <div style={{ position: 'relative' }}>
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  autoComplete="current-password"
                  disabled={loading}
                  style={{
                    width: '100%',
                    height: '40px',
                    padding: '0 36px 0 36px',
                    borderRadius: '8px',
                    border: '1px solid var(--border, #CCD8ED)',
                    background: '#FFFFFF',
                    color: '#182744',
                    fontSize: '13px',
                    outline: 'none',
                    transition: 'border-color 150ms ease',
                  }}
                  onFocus={(e) => (e.target.style.borderColor = 'var(--accent, #4338A8)')}
                  onBlur={(e) => (e.target.style.borderColor = 'var(--border, #CCD8ED)')}
                />
                <Lock
                  style={{
                    position: 'absolute',
                    left: '11px',
                    top: '12px',
                    width: '16px',
                    height: '16px',
                    color: 'var(--muted, #4F607B)',
                    pointerEvents: 'none',
                  }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  style={{
                    position: 'absolute',
                    right: '10px',
                    top: '11px',
                    background: 'transparent',
                    border: 0,
                    color: 'var(--muted, #4F607B)',
                    cursor: 'pointer',
                    padding: 0,
                  }}
                >
                  {showPassword ? <EyeOff style={{ width: '16px', height: '16px' }} /> : <Eye style={{ width: '16px', height: '16px' }} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="button button-primary"
              style={{
                width: '100%',
                height: '42px',
                marginTop: '6px',
                fontSize: '13.5px',
                fontWeight: 650,
              }}
            >
              {loading ? (
                <>
                  <Loader2 className="animate-spin" style={{ width: '16px', height: '16px' }} />
                  <span>Verifying Credentials...</span>
                </>
              ) : (
                <>
                  <span>Sign In to Workspace</span>
                  <ArrowRight style={{ width: '15px', height: '15px' }} />
                </>
              )}
            </button>
          </form>

          {/* Development Quick Credentials Helper */}
          {isDev && (
            <div
              style={{
                marginTop: '24px',
                paddingTop: '18px',
                borderTop: '1px dashed var(--border, #CCD8ED)',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  marginBottom: '10px',
                  fontSize: '11px',
                  fontWeight: 600,
                  color: 'var(--muted, #4F607B)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                }}
              >
                <Sparkles style={{ width: '12px', height: '12px', color: 'var(--accent, #4338A8)' }} />
                <span>Dev Test Accounts (1-Click Fill)</span>
              </div>
              <div style={{ display: 'flex' }}>
                <button
                  type="button"
                  onClick={() => handleQuickFill('candidate_demo', 'CandidatePass123!')}
                  style={{
                    flex: 1,
                    border: '1px solid #A7F3D0',
                    background: '#ECFDF5',
                    color: '#047857',
                    borderRadius: '8px',
                    padding: '8px 12px',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                  }}
                  title="Fill Student Account Credentials"
                >
                  <UserCheck style={{ width: '14px', height: '14px' }} />
                  <span>Student Demo Account (Candidate)</span>
                </button>
              </div>
            </div>
          )}

          <div
            style={{
              marginTop: '22px',
              textAlign: 'center',
              fontSize: '12px',
              color: 'var(--muted, #4F607B)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
          >
            <ShieldCheck style={{ width: '14px', height: '14px', color: '#10B981' }} />
            <span>Server-signed JWT tokens with salted PBKDF2 hashing.</span>
          </div>
        </div>
      </main>

      {/* Forgot Password Modal */}
      {showForgotModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(24, 39, 68, 0.45)',
            backdropFilter: 'blur(3px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
            zIndex: 100,
          }}
          onClick={() => setShowForgotModal(false)}
        >
          <div
            style={{
              maxWidth: '420px',
              width: '100%',
              background: '#FFFFFF',
              borderRadius: '14px',
              padding: '24px',
              boxShadow: '0 20px 40px rgba(0, 0, 0, 0.15)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
              <div
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '10px',
                  background: '#EEF2FF',
                  color: 'var(--accent, #4338A8)',
                  display: 'grid',
                  placeItems: 'center',
                }}
              >
                <Info style={{ width: '18px', height: '18px' }} />
              </div>
              <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: '#182744' }}>
                Account Recovery &amp; Password Reset
              </h3>
            </div>
            <p style={{ fontSize: '13px', color: 'var(--muted, #4F607B)', lineHeight: 1.6, margin: '0 0 16px' }}>
              To maintain interview integrity and prevent unauthorized credential overrides, password resets are
              authorized through platform administrators.
            </p>
            <div
              style={{
                background: '#F8FAFD',
                border: '1px solid var(--border, #CCD8ED)',
                borderRadius: '8px',
                padding: '12px',
                fontSize: '12px',
                color: '#182744',
                marginBottom: '18px',
              }}
            >
              <p style={{ margin: '0 0 4px', fontWeight: 600 }}>Default Recovery Contacts:</p>
              <p style={{ margin: '0 0 2px' }}>• Student Support: <code>support@interviewiq.com</code></p>
              <p style={{ margin: 0 }}>• Platform Administrator: <code>admin@interviewiq.com</code></p>
            </div>
            <button
              onClick={() => setShowForgotModal(false)}
              className="button button-primary"
              style={{ width: '100%', height: '38px', fontSize: '13px' }}
            >
              Understood
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '100vh',
            background: 'var(--background, #F3F6FC)',
          }}
        >
          <Loader2 className="animate-spin" style={{ width: '28px', height: '28px', color: 'var(--accent, #4338A8)' }} />
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  )
}
