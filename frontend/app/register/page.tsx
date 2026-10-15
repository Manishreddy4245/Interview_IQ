'use client'

import React, { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/lib/auth-context'
import {
  UserPlus,
  User,
  Mail,
  Lock,
  Eye,
  EyeOff,
  AlertCircle,
  ArrowRight,
  ShieldCheck,
  ShieldAlert,
  Loader2,
} from 'lucide-react'

export default function RegisterPage() {
  const router = useRouter()
  const { register } = useAuth()

  const [name, setName] = useState('')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    const cleanName = name.trim()
    const cleanUsername = username.trim()
    const cleanEmail = email.trim()

    if (!cleanName || cleanName.length < 2) {
      setError('Please provide your full name (at least 2 characters).')
      return
    }

    if (!cleanUsername || cleanUsername.length < 3) {
      setError('Username must be at least 3 characters long.')
      return
    }

    if (!cleanUsername.replace('_', '').replace('-', '').match(/^[a-zA-Z0-9]+$/)) {
      setError('Username may only contain alphanumeric characters, underscores, and hyphens.')
      return
    }

    if (!password || password.length < 6) {
      setError('Password must be at least 6 characters long.')
      return
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match. Please re-enter.')
      return
    }

    setLoading(true)
    try {
      await register({
        name: cleanName,
        username: cleanUsername,
        email: cleanEmail || undefined,
        password,
      })
      router.push('/candidate')
    } catch (err: any) {
      console.error('Registration error:', err)
      setError(err.message || 'Failed to complete candidate registration. Please try again.')
    } finally {
      setLoading(false)
    }
  }

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
          <span style={{ fontSize: '13px', color: 'var(--muted, #4F607B)' }}>Already registered?</span>
          <Link
            href="/login"
            className="button button-outline"
            style={{ minHeight: '34px', padding: '0 14px', fontSize: '12.5px', textDecoration: 'none' }}
          >
            Sign In
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
            maxWidth: '480px',
            width: '100%',
            background: '#FFFFFF',
            border: '1.5px solid var(--border, #CCD8ED)',
            borderRadius: '16px',
            padding: '36px 32px',
            boxShadow: '0 10px 30px rgba(24, 39, 68, 0.07)',
          }}
        >
          <div style={{ textAlign: 'center', marginBottom: '22px' }}>
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
              <UserPlus style={{ width: '20px', height: '20px' }} />
            </div>
            <h1 style={{ fontSize: '22px', fontWeight: 700, margin: '0 0 6px', color: '#182744' }}>
              Create Candidate Account
            </h1>
            <p style={{ margin: 0, fontSize: '13px', color: 'var(--muted, #4F607B)' }}>
              Set up your private workspace for technical coding, voice simulation, and skill benchmarking.
            </p>
          </div>

          {/* Security Notice: Strict Candidate Registration */}
          <div
            style={{
              background: '#F8FAFE',
              border: '1px solid #DEE7F5',
              borderRadius: '10px',
              padding: '12px 14px',
              fontSize: '12px',
              color: '#4F607B',
              display: 'flex',
              gap: '10px',
              alignItems: 'flex-start',
              marginBottom: '20px',
            }}
          >
            <ShieldAlert style={{ width: '16px', height: '16px', color: 'var(--accent, #4338A8)', flexShrink: 0, marginTop: '2px' }} />
            <div>
              <strong style={{ color: '#182744', display: 'block', marginBottom: '2px' }}>Role-Governed Platform:</strong>
              Public registration provisions <strong>Candidate</strong> workspace privileges. Reviewer and Administrator
              accounts are strictly assigned by authorized system administrators.
            </div>
          </div>

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

          <form onSubmit={handleRegister} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <label
                htmlFor="register-name"
                style={{
                  display: 'block',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: '#182744',
                  marginBottom: '6px',
                }}
              >
                Full Name *
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  id="register-name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Jordan Lee"
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
              <label
                htmlFor="register-username"
                style={{
                  display: 'block',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: '#182744',
                  marginBottom: '6px',
                }}
              >
                Username *
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  id="register-username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. alex_mercer"
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
              <label
                htmlFor="register-email"
                style={{
                  display: 'block',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: '#182744',
                  marginBottom: '6px',
                }}
              >
                Email Address (Optional)
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  id="register-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="e.g. alex@example.com"
                  autoComplete="email"
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
                  }}
                  onFocus={(e) => (e.target.style.borderColor = 'var(--accent, #4338A8)')}
                  onBlur={(e) => (e.target.style.borderColor = 'var(--border, #CCD8ED)')}
                />
                <Mail
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
              <label
                htmlFor="register-password"
                style={{
                  display: 'block',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: '#182744',
                  marginBottom: '6px',
                }}
              >
                Password * (min 6 characters)
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  id="register-password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Create a password"
                  autoComplete="new-password"
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

            <div>
              <label
                htmlFor="register-confirm-password"
                style={{
                  display: 'block',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: '#182744',
                  marginBottom: '6px',
                }}
              >
                Confirm Password *
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  id="register-confirm-password"
                  type={showPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Confirm your password"
                  autoComplete="new-password"
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
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="button button-primary"
              style={{
                width: '100%',
                height: '42px',
                marginTop: '8px',
                fontSize: '13.5px',
                fontWeight: 650,
              }}
            >
              {loading ? (
                <>
                  <Loader2 className="animate-spin" style={{ width: '16px', height: '16px' }} />
                  <span>Registering Candidate Account...</span>
                </>
              ) : (
                <>
                  <span>Create Candidate Account</span>
                  <ArrowRight style={{ width: '15px', height: '15px' }} />
                </>
              )}
            </button>
          </form>

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
            <span>Practice history is private &amp; candidate-isolated.</span>
          </div>
        </div>
      </main>
    </div>
  )
}
