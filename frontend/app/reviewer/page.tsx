'use client'

import ProtectedRoute from '@/components/protected-route'
import InterviewIQWorkspace from '@/components/interviewiq-workspace'

export default function ReviewerPage() {
  return (
    <ProtectedRoute allowedRoles={['reviewer', 'admin']}>
      <InterviewIQWorkspace allowedRole="reviewer" defaultTab="Candidate Intelligence" />
    </ProtectedRoute>
  )
}
