'use client'

import ProtectedRoute from '@/components/protected-route'
import InterviewIQWorkspace from '@/components/interviewiq-workspace'

export default function CandidatePage() {
  return (
    <ProtectedRoute allowedRoles={['candidate', 'admin']}>
      <InterviewIQWorkspace allowedRole="candidate" />
    </ProtectedRoute>
  )
}
