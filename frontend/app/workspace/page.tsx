'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import ProtectedRoute from '@/components/protected-route'
import { Loader2 } from 'lucide-react'

function WorkspaceRouter() {
  const { role, isLoading, isAuthenticated } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!isLoading && isAuthenticated && role) {
      if (role === 'reviewer') {
        router.replace('/reviewer')
      } else if (role === 'admin') {
        router.replace('/admin')
      } else {
        router.replace('/candidate')
      }
    }
  }, [role, isLoading, isAuthenticated, router])

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        background: 'var(--background, #F3F6FC)',
        gap: '14px',
        color: 'var(--foreground, #182744)',
        fontFamily: 'Inter, system-ui, sans-serif',
      }}
    >
      <Loader2 className="animate-spin" style={{ width: '32px', height: '32px', color: 'var(--accent, #4338A8)' }} />
      <p style={{ fontSize: '14px', color: 'var(--muted, #4F607B)' }}>Routing to your authorized workspace...</p>
    </div>
  )
}

export default function WorkspacePage() {
  return (
    <ProtectedRoute>
      <WorkspaceRouter />
    </ProtectedRoute>
  )
}
