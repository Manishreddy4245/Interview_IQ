'use client'

import ProtectedRoute from '@/components/protected-route'
import InterviewIQWorkspace from '@/components/interviewiq-workspace'

export default function AdminPage() {
  return (
    <ProtectedRoute allowedRoles={['admin']}>
      <InterviewIQWorkspace allowedRole="admin" />
    </ProtectedRoute>
  )
}
