'use client'

import React, { useEffect } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import { ShieldAlert, Loader2, ArrowRight } from 'lucide-react'

interface ProtectedRouteProps {
  children: React.ReactNode
  allowedRoles?: ('candidate' | 'reviewer' | 'admin')[]
}

export default function ProtectedRoute({ children, allowedRoles }: ProtectedRouteProps) {
  const { user, role, isLoading, isAuthenticated } = useAuth()
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      const redirectUrl = `/login?redirect=${encodeURIComponent(pathname)}`
      router.replace(redirectUrl)
    }
  }, [isLoading, isAuthenticated, router, pathname])

  if (isLoading) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          background: 'var(--background, #F3F6FC)',
          gap: '16px',
          color: 'var(--foreground, #182744)',
          fontFamily: 'Inter, system-ui, sans-serif',
        }}
      >
        <div
          style={{
            display: 'grid',
            placeItems: 'center',
            width: '48px',
            height: '48px',
            borderRadius: '12px',
            background: 'var(--accent, #4338A8)',
            color: '#FFFFFF',
            boxShadow: '0 4px 14px rgba(67, 56, 168, 0.25)',
          }}
        >
          <Loader2 className="animate-spin" style={{ width: '24px', height: '24px' }} />
        </div>
        <div style={{ textAlign: 'center' }}>
          <p style={{ margin: 0, fontWeight: 600, fontSize: '15px' }}>Verifying Permissions</p>
          <p style={{ margin: '4px 0 0', fontSize: '13px', color: 'var(--muted, #4F607B)' }}>
            Checking role claims and session token with backend...
          </p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          background: 'var(--background, #F3F6FC)',
          gap: '12px',
          color: 'var(--muted, #4F607B)',
        }}
      >
        <p style={{ fontSize: '14px' }}>Redirecting to secure login...</p>
      </div>
    )
  }

  // Role validation
  if (allowedRoles && role && !allowedRoles.includes(role)) {
    const targetWorkspace = role === 'candidate' ? '/candidate' : role === 'reviewer' ? '/reviewer' : '/admin'

    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          background: 'var(--background, #F3F6FC)',
          padding: '24px',
          fontFamily: 'Inter, system-ui, sans-serif',
        }}
      >
        <div
          style={{
            maxWidth: '520px',
            width: '100%',
            background: '#FFFFFF',
            border: '1.5px solid var(--border, #CCD8ED)',
            borderRadius: '16px',
            padding: '36px 32px',
            boxShadow: '0 8px 30px rgba(24, 39, 68, 0.08)',
            textAlign: 'center',
          }}
        >
          <div
            style={{
              width: '56px',
              height: '56px',
              margin: '0 auto 20px',
              borderRadius: '14px',
              background: '#FEE2E2',
              color: '#DC2626',
              display: 'grid',
              placeItems: 'center',
            }}
          >
            <ShieldAlert style={{ width: '28px', height: '28px' }} />
          </div>

          <h2
            style={{
              fontSize: '20px',
              fontWeight: 700,
              color: '#182744',
              margin: '0 0 10px',
            }}
          >
            Access Forbidden (403)
          </h2>

          <p
            style={{
              fontSize: '13.5px',
              color: '#4F607B',
              lineHeight: 1.6,
              margin: '0 0 20px',
            }}
          >
            Your account role is <strong>{role.toUpperCase()}</strong> ({user?.name}). This workspace route requires{' '}
            <strong>{allowedRoles.join(' or ').toUpperCase()}</strong> permissions.
          </p>

          <div
            style={{
              background: '#F8FAFE',
              border: '1px solid #DEE7F5',
              borderRadius: '10px',
              padding: '12px 16px',
              fontSize: '12.5px',
              color: '#4F607B',
              textAlign: 'left',
              marginBottom: '24px',
            }}
          >
            <p style={{ margin: '0 0 4px', fontWeight: 600, color: '#182744' }}>Role Isolation Active:</p>
            <p style={{ margin: 0, fontSize: '12px' }}>
              Candidate and reviewer workflows are strictly isolated on the backend. Candidate accounts cannot view hiring
              manager decision intelligence or cross-candidate records.
            </p>
          </div>

          <button
            onClick={() => router.push(targetWorkspace)}
            className="button button-primary"
            style={{ width: '100%', minHeight: '42px', fontSize: '13.5px' }}
          >
            <span>Return to Authorized {role.charAt(0).toUpperCase() + role.slice(1)} Workspace</span>
            <ArrowRight style={{ width: '16px', height: '16px' }} />
          </button>
        </div>
      </div>
    )
  }

  return <>{children}</>
}
