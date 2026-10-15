'use client'

import React, { useEffect, useState } from 'react'
import AnimatedMeshGradient from '@/components/animated-mesh-gradient'
import {
  Award,
  CheckCircle2,
  AlertTriangle,
  ShieldCheck,
  FileText,
  User,
  Clock,
  Briefcase,
  TrendingUp,
  BarChart2,
  ArrowRight,
  Send,
  Loader2,
  RefreshCw,
  Search,
  Check,
  Layers,
  ShieldAlert,
} from 'lucide-react'
import {
  getCandidateDecisionOverview,
  getCandidateDecisionDossier,
  submitCandidateDecisionReview,
  switchDemoRole,
  getAuthUser,
  type DecisionOverviewResponse,
  type CandidateDossierItem,
  type HumanReviewDecisionRequest,
} from '@/lib/api'

export default function CandidateDecisionDashboard() {
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [isAuthBlocked, setIsAuthBlocked] = useState<boolean>(false)
  const [overview, setOverview] = useState<DecisionOverviewResponse | null>(null)
  const [selectedRecordId, setSelectedRecordId] = useState<string | null>(null)
  const [selectedDossier, setSelectedDossier] = useState<CandidateDossierItem | null>(null)
  const [submittingReview, setSubmittingReview] = useState<boolean>(false)

  // Human review form state
  const [reviewerName, setReviewerName] = useState<string>('')
  const [recommendation, setRecommendation] = useState<string>('Advance to Next Interview Round')
  const [reviewNotes, setReviewNotes] = useState<string>('')
  const [reviewSuccessMessage, setReviewSuccessMessage] = useState<string | null>(null)

  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)
      setIsAuthBlocked(false)
      const data = await getCandidateDecisionOverview()
      setOverview(data)
      if (data.dossiers.length > 0 && !selectedRecordId) {
        setSelectedRecordId(data.dossiers[0].record_id)
        setSelectedDossier(data.dossiers[0])
      } else if (selectedRecordId) {
        const matching = data.dossiers.find((d) => d.record_id === selectedRecordId)
        if (matching) setSelectedDossier(matching)
      }
    } catch (err: any) {
      console.error('Failed to load candidate decision overview:', err)
      const msg = err.message || ''
      if (
        msg.includes('401') ||
        msg.includes('403') ||
        msg.toLowerCase().includes('forbidden') ||
        msg.toLowerCase().includes('authentication')
      ) {
        setIsAuthBlocked(true)
        setError(null)
      } else {
        setError(msg || 'Failed to load candidate decision data.')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleSwitchToReviewer = async () => {
    try {
      setLoading(true)
      const res = await switchDemoRole('reviewer')
      setReviewerName(res.name)
      setIsAuthBlocked(false)
      await loadData()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleSelectRecord = async (recordId: string) => {
    setSelectedRecordId(recordId)
    setReviewSuccessMessage(null)
    const existing = overview?.dossiers.find((d) => d.record_id === recordId)
    if (existing) {
      setSelectedDossier(existing)
    }
    try {
      const detailed = await getCandidateDecisionDossier(recordId)
      setSelectedDossier(detailed)
    } catch (err) {
      console.error('Failed to load dossier detail:', err)
    }
  }

  const handleReviewSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedRecordId || !reviewerName.trim()) return

    try {
      setSubmittingReview(true)
      setReviewSuccessMessage(null)
      const payload: HumanReviewDecisionRequest = {
        reviewer_name: reviewerName.trim(),
        recommendation: recommendation.trim(),
        notes: reviewNotes.trim(),
      }
      await submitCandidateDecisionReview(selectedRecordId, payload)
      setReviewSuccessMessage('Human review determination successfully recorded in audit log.')
      setReviewNotes('')

      // Reload dossier
      const updated = await getCandidateDecisionDossier(selectedRecordId)
      setSelectedDossier(updated)
    } catch (err: any) {
      alert(`Error saving review: ${err.message}`)
    } finally {
      setSubmittingReview(false)
    }
  }

  return (
    <div className="page-content" style={{ paddingBottom: '40px' }}>
      {/* Top Banner & Governance Principles */}
      <section className="room-hero">
        <AnimatedMeshGradient />
        <div className="room-header" style={{ width: '100%', flexDirection: 'column', gap: '0' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px', width: '100%' }}>
            <div>
              <div className="badge-row" style={{ marginBottom: '8px' }}>
                <span className="badge badge-accent">
                  <Award size={13} /> Module 05: Decision Intelligence
                </span>
                <span className="badge badge-neutral">
                  <ShieldCheck size={13} /> Human-in-the-Loop Governance
                </span>
              </div>
              <h2>Candidate Decision Intelligence</h2>
              <p className="intro-copy">
                Evidence-grounded hiring intelligence synthesizing resume skill extraction, interview answer evaluations, skill-gap closure, and neutral integrity signals.
              </p>
            </div>

            <button
              onClick={loadData}
              className="button button-secondary"
              disabled={loading}
            >
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh Data
            </button>
          </div>

          {/* Database Inventory Counter / Status Row */}
          {overview && (
            <div style={{
              display: 'flex',
              gap: '16px',
              marginTop: '22px',
              paddingTop: '18px',
              borderTop: '1.5px solid var(--border, #CCD8ED)',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              width: '100%',
            }}>
              <div style={{ fontSize: '12.5px', color: 'var(--muted, #4F607B)' }}>
                <strong style={{ color: 'var(--foreground, #182744)', fontWeight: 700 }}>Real Records: </strong>
                {overview.total_records} profiles ({overview.resume_analyses_count} resume, {overview.interview_reports_count} reports, {overview.interview_sessions_count} practice sessions)
              </div>
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
                <span className="pill-badge olive" style={{ fontSize: '11px', textTransform: 'none', letterSpacing: 'normal' }}>
                  <CheckCircle2 size={13} /> Real Atlas Data • Zero Synthetic Data
                </span>
                <span className="pill-badge sand" style={{ fontSize: '11px', textTransform: 'none', letterSpacing: 'normal', color: '#1E40AF', background: '#EFF6FF', borderColor: '#BFDBFE' }}>
                  <AlertTriangle size={13} style={{ color: '#D97706' }} /> Independent Decision Support • No Automated Disqualifications
                </span>
              </div>
            </div>
          )}
        </div>
      </section>

      {isAuthBlocked && (
        <div
          style={{
            padding: '28px 24px',
            background: 'rgba(239, 68, 68, 0.08)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: '12px',
            marginBottom: '24px',
            textAlign: 'center',
          }}
        >
          <ShieldAlert size={40} color="#f87171" style={{ margin: '0 auto 12px' }} />
          <h3 style={{ fontSize: '18px', fontWeight: 600, color: '#f87171', margin: '0 0 8px 0' }}>
            Reviewer Authorization Required
          </h3>
          <p
            style={{
              maxWidth: '600px',
              margin: '0 auto 18px',
              fontSize: '13.5px',
              color: 'var(--muted)',
              lineHeight: '1.5',
            }}
          >
            Candidate Decision Intelligence contains sensitive evaluation profiles, gap breakdowns, and decision dossiers. Under backend-enforced RBAC, access is restricted strictly to verified Reviewers and Administrators.
          </p>
          {process.env.NODE_ENV !== 'production' ? (
            <button
              onClick={handleSwitchToReviewer}
              className="button button-primary"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 22px',
                borderRadius: '8px',
                fontSize: '13px',
                fontWeight: 500,
              }}
            >
              <CheckCircle2 size={16} /> [DEV ONLY] Authenticate as Reviewer (Sarah Chen)
            </button>
          ) : (
            <a
              href="/login?redirect=/reviewer"
              className="button button-primary"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 22px',
                borderRadius: '8px',
                fontSize: '13px',
                fontWeight: 500,
                textDecoration: 'none',
              }}
            >
              <CheckCircle2 size={16} /> Sign In with Authorized Reviewer Account
            </a>
          )}
        </div>
      )}

      {error && (
        <div style={{ padding: '16px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid #ef4444', borderRadius: '8px', color: '#ef4444', marginBottom: '20px' }}>
          {error}
        </div>
      )}

      {loading && !overview ? (
        <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--muted)' }}>
          <Loader2 size={32} className="animate-spin" style={{ margin: '0 auto 16px' }} />
          <p>Loading candidate decision intelligence dossiers...</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '24px' }}>
          {/* Left Column: Real Candidate Records List */}
          <aside>
            <h3 style={{ fontSize: '14px', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)', margin: '0 0 12px 0' }}>
              Candidate Dossiers ({overview?.dossiers.length || 0})
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {overview?.dossiers.map((dossier) => {
                const isSelected = dossier.record_id === selectedRecordId
                return (
                  <div
                    key={dossier.record_id}
                    onClick={() => handleSelectRecord(dossier.record_id)}
                    style={{
                      padding: '14px',
                      borderRadius: '10px',
                      background: isSelected ? 'var(--accent-soft)' : '#FFFFFF',
                      border: isSelected ? '2px solid var(--accent)' : '1.5px solid var(--border)',
                      boxShadow: isSelected ? '0 4px 14px rgba(79, 70, 181, 0.12)' : 'var(--shadow-card)',
                      cursor: 'pointer',
                      transition: 'all 0.18s cubic-bezier(0.16, 1, 0.3, 1)',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                      <span style={{ fontSize: '11px', fontWeight: 600, color: dossier.record_type === 'resume_analysis' ? '#38bdf8' : '#a78bfa', textTransform: 'uppercase' }}>
                        {dossier.record_type === 'resume_analysis' ? 'Resume Analysis' : 'Interview Report'}
                      </span>
                      {dossier.overall_score !== null && dossier.overall_score !== undefined && (
                        <span style={{ fontSize: '12px', fontWeight: 600, color: '#10b981' }}>
                          Score: {dossier.overall_score.toFixed(0)}/100
                        </span>
                      )}
                    </div>

                    <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--foreground)', marginBottom: '4px' }}>
                      {dossier.target_role}
                    </div>

                    <div style={{ fontSize: '12px', color: 'var(--muted)', display: 'flex', gap: '8px' }}>
                      <span>{dossier.experience_level}</span>
                      <span>•</span>
                      <span>{dossier.demonstrated_competencies.length} demonstrated</span>
                    </div>

                    <div style={{ fontSize: '11px', color: 'var(--muted-foreground, #64748b)', marginTop: '6px', fontFamily: 'monospace' }}>
                      ID: {dossier.record_id.slice(0, 16)}...
                    </div>
                  </div>
                )
              })}
            </div>
          </aside>

          {/* Right Column: Selected Dossier Detail */}
          <main>
            {selectedDossier ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {/* Dossier Header Card */}
                <div className="glass-panel" style={{ padding: '20px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
                    <div>
                      <div style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '4px' }}>
                        {selectedDossier.candidate_identifier}
                      </div>
                      <h3 style={{ fontSize: '20px', fontWeight: 600, color: 'var(--foreground)', margin: '0 0 8px 0' }}>
                        {selectedDossier.target_role} ({selectedDossier.experience_level})
                      </h3>
                      <div style={{ display: 'flex', gap: '12px', fontSize: '12px', color: 'var(--muted)' }}>
                        <span>Record Type: <strong>{selectedDossier.record_type}</strong></span>
                        <span>•</span>
                        <span>Status: <strong>{selectedDossier.scoring_status}</strong></span>
                        {selectedDossier.linked_session_id && (
                          <>
                            <span>•</span>
                            <span>Session ID: <code style={{ fontSize: '11px' }}>{selectedDossier.linked_session_id.slice(0, 8)}</code></span>
                          </>
                        )}
                      </div>
                    </div>

                    {selectedDossier.overall_score !== null && selectedDossier.overall_score !== undefined && (
                      <div style={{ textAlign: 'right', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid #10b981', padding: '10px 16px', borderRadius: '8px' }}>
                        <div style={{ fontSize: '11px', color: '#10b981', textTransform: 'uppercase', fontWeight: 600 }}>Overall Score</div>
                        <div style={{ fontSize: '26px', fontWeight: 700, color: '#10b981' }}>{selectedDossier.overall_score.toFixed(1)}/100</div>
                      </div>
                    )}
                  </div>

                  {/* Executive Summary */}
                  {selectedDossier.executive_summary && (
                    <div style={{ marginTop: '16px', padding: '14px', background: 'var(--surface-subtle, rgba(255, 255, 255, 0.03))', borderRadius: '6px', borderLeft: '3px solid var(--accent, #6366f1)' }}>
                      <div style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', color: 'var(--muted)', marginBottom: '4px' }}>
                        Evidence-Grounded Role Readiness Synthesis
                      </div>
                      <p style={{ fontSize: '13px', lineHeight: '1.5', margin: 0, color: 'var(--foreground)' }}>
                        {selectedDossier.executive_summary}
                      </p>
                    </div>
                  )}
                </div>

                {/* Multi-Dimensional Criterion Scores */}
                {(selectedDossier.criterion_scores.relevance !== null ||
                  selectedDossier.criterion_scores.technical_depth !== null ||
                  selectedDossier.criterion_scores.completeness !== null) && (
                  <div className="glass-panel" style={{ padding: '20px' }}>
                    <h4 style={{ fontSize: '14px', fontWeight: 600, margin: '0 0 14px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <BarChart2 size={16} /> Multi-Dimensional Evaluation Breakdown (Scale 1–10)
                    </h4>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '14px' }}>
                      {Object.entries({
                        'Relevance': selectedDossier.criterion_scores.relevance,
                        'Technical Depth': selectedDossier.criterion_scores.technical_depth,
                        'Completeness': selectedDossier.criterion_scores.completeness,
                        'Structure & Flow': selectedDossier.criterion_scores.structure_flow,
                        'Clarity': selectedDossier.criterion_scores.clarity_conciseness,
                        'STAR Behavioral': selectedDossier.criterion_scores.star_structure,
                      }).map(([label, val]) => (
                        val !== null && val !== undefined ? (
                          <div key={label} style={{ padding: '12px', background: 'var(--surface)', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
                            <div style={{ fontSize: '11px', color: 'var(--muted)', marginBottom: '4px' }}>{label}</div>
                            <div style={{ fontSize: '18px', fontWeight: 700, color: val >= 6 ? '#10b981' : val >= 4 ? '#f59e0b' : '#ef4444' }}>
                              {val.toFixed(1)} / 10
                            </div>
                            <div style={{ width: '100%', height: '4px', background: 'rgba(255, 255, 255, 0.1)', borderRadius: '2px', marginTop: '6px' }}>
                              <div style={{ width: `${Math.min(val * 10, 100)}%`, height: '100%', background: val >= 6 ? '#10b981' : val >= 4 ? '#f59e0b' : '#ef4444', borderRadius: '2px' }} />
                            </div>
                          </div>
                        ) : null
                      ))}
                    </div>
                  </div>
                )}

                {/* Demonstrated Competencies vs. Competency Gaps */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                  {/* Demonstrated */}
                  <div className="glass-panel" style={{ padding: '20px' }}>
                    <h4 style={{ fontSize: '14px', fontWeight: 600, margin: '0 0 14px 0', color: '#10b981', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <CheckCircle2 size={16} /> Demonstrated Competencies ({selectedDossier.demonstrated_competencies.length})
                    </h4>

                    {selectedDossier.demonstrated_competencies.length === 0 ? (
                      <p style={{ fontSize: '12px', color: 'var(--muted)', margin: 0 }}>No verified competencies recorded yet.</p>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        {selectedDossier.demonstrated_competencies.map((item, idx) => (
                          <div key={idx} style={{ padding: '10px', background: 'rgba(16, 185, 129, 0.05)', border: '1px solid rgba(16, 185, 129, 0.2)', borderRadius: '6px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                              <strong style={{ fontSize: '13px', color: 'var(--foreground)' }}>{item.skill_name}</strong>
                              <span style={{ fontSize: '10px', padding: '2px 6px', background: '#10b981', color: '#fff', borderRadius: '4px', fontWeight: 600 }}>
                                {item.source_type === 'resume' ? 'Resume' : 'Interview'}
                              </span>
                            </div>
                            <p style={{ fontSize: '12px', color: 'var(--muted)', margin: 0 }}>
                              {item.evidence_text}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Competency Gaps */}
                  <div className="glass-panel" style={{ padding: '20px' }}>
                    <h4 style={{ fontSize: '14px', fontWeight: 600, margin: '0 0 14px 0', color: '#f59e0b', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <AlertTriangle size={16} /> Identified Gaps & Validation Areas ({selectedDossier.competency_gaps.length})
                    </h4>

                    {selectedDossier.competency_gaps.length === 0 ? (
                      <p style={{ fontSize: '12px', color: 'var(--muted)', margin: 0 }}>No critical skill gaps identified.</p>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        {selectedDossier.competency_gaps.map((item, idx) => (
                          <div key={idx} style={{ padding: '10px', background: 'rgba(245, 158, 11, 0.05)', border: '1px solid rgba(245, 158, 11, 0.2)', borderRadius: '6px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                              <strong style={{ fontSize: '13px', color: 'var(--foreground)' }}>{item.skill_name}</strong>
                              <span style={{ fontSize: '10px', padding: '2px 6px', background: '#f59e0b', color: '#fff', borderRadius: '4px', fontWeight: 600 }}>
                                {item.status}
                              </span>
                            </div>
                            <p style={{ fontSize: '12px', color: 'var(--muted)', margin: 0 }}>
                              {item.evidence_text}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Neutral Integrity Signals Section */}
                <div className="glass-panel" style={{ padding: '20px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                    <h4 style={{ fontSize: '14px', fontWeight: 600, margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <ShieldCheck size={16} /> Observable Integrity Telemetry
                    </h4>
                    <span style={{ fontSize: '11px', color: 'var(--muted)' }}>
                      Factual browser events • Neutral audit logging only
                    </span>
                  </div>

                  <div style={{ display: 'flex', gap: '24px', marginTop: '14px', flexWrap: 'wrap' }}>
                    <div style={{ padding: '10px 16px', background: 'var(--surface)', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--muted)' }}>Total Observable Events</div>
                      <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--foreground)' }}>
                        {selectedDossier.integrity_event_count}
                      </div>
                    </div>
                    <div style={{ padding: '10px 16px', background: 'var(--surface)', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--muted)' }}>Cumulative Unfocused Duration</div>
                      <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--foreground)' }}>
                        {(selectedDossier.cumulative_unfocused_seconds || 0).toFixed(1)}s
                      </div>
                    </div>
                  </div>

                  <p style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '12px', marginBottom: 0 }}>
                    Notice: In strict adherence to integrity-review separation, observable telemetry events are preserved purely for human audit inspection and do not automatically reduce evaluation scores or generate AI disqualifications.
                  </p>
                </div>

                {/* Human Reviewer Determination Panel */}
                <div className="glass-panel" style={{ padding: '20px', border: '1px solid rgba(99, 102, 241, 0.3)' }}>
                  <h4 style={{ fontSize: '16px', fontWeight: 600, margin: '0 0 6px 0', color: 'var(--foreground)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <User size={16} /> Human Reviewer Determination & Recommendation
                  </h4>
                  <p style={{ fontSize: '12px', color: 'var(--muted)', margin: '0 0 16px 0' }}>
                    Record an auditable human hiring determination on this candidate dossier.
                  </p>

                  {reviewSuccessMessage && (
                    <div style={{ padding: '10px 14px', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid #10b981', borderRadius: '6px', color: '#10b981', fontSize: '13px', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Check size={14} /> {reviewSuccessMessage}
                    </div>
                  )}

                  <form onSubmit={handleReviewSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
                      <div>
                        <label style={{ display: 'block', fontSize: '12px', color: 'var(--muted)', marginBottom: '4px' }}>
                          Reviewer Name / Title *
                        </label>
                        <input
                          type="text"
                          className="input-field"
                          placeholder="e.g. Lead Technical Recruiter"
                          value={reviewerName}
                          onChange={(e) => setReviewerName(e.target.value)}
                          required
                          style={{ width: '100%' }}
                        />
                      </div>

                      <div>
                        <label style={{ display: 'block', fontSize: '12px', color: 'var(--muted)', marginBottom: '4px' }}>
                          Hiring Recommendation *
                        </label>
                        <select
                          className="input-field"
                          value={recommendation}
                          onChange={(e) => setRecommendation(e.target.value)}
                          style={{ width: '100%' }}
                        >
                          <option value="Advance to Next Interview Round">Advance to Next Interview Round</option>
                          <option value="Technical Follow-Up Required">Technical Follow-Up Required</option>
                          <option value="Practical Coding Assessment Needed">Practical Coding Assessment Needed</option>
                          <option value="Hold / Evaluate Additional Candidates">Hold / Evaluate Additional Candidates</option>
                        </select>
                      </div>
                    </div>

                    <div>
                      <label style={{ display: 'block', fontSize: '12px', color: 'var(--muted)', marginBottom: '4px' }}>
                        Reviewer Notes & Justification (Optional)
                      </label>
                      <textarea
                        className="input-field"
                        rows={3}
                        placeholder="Detail specific observations, questions to follow up on, or rationale..."
                        value={reviewNotes}
                        onChange={(e) => setReviewNotes(e.target.value)}
                        style={{ width: '100%' }}
                      />
                    </div>

                    <button
                      type="submit"
                      className="button button-primary"
                      disabled={submittingReview || !reviewerName.trim()}
                      style={{ alignSelf: 'flex-start', display: 'inline-flex', alignItems: 'center', gap: '8px' }}
                    >
                      {submittingReview ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                      Save Reviewer Determination
                    </button>
                  </form>

                  {/* Previous Audited Reviews */}
                  {selectedDossier.human_reviews.length > 0 && (
                    <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid var(--border-subtle)' }}>
                      <h5 style={{ fontSize: '12px', textTransform: 'uppercase', color: 'var(--muted)', margin: '0 0 10px 0' }}>
                        Recorded Determinations ({selectedDossier.human_reviews.length})
                      </h5>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {selectedDossier.human_reviews.map((rev) => (
                          <div key={rev.decision_id} style={{ padding: '10px 14px', background: 'var(--surface)', borderRadius: '6px', border: '1px solid var(--border-subtle)', fontSize: '12px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
                              <strong style={{ color: 'var(--foreground)' }}>{rev.reviewer_name}</strong>
                              <span style={{ color: '#10b981', fontWeight: 600 }}>{rev.recommendation}</span>
                            </div>
                            {rev.notes && <p style={{ margin: '4px 0 0', color: 'var(--muted)' }}>{rev.notes}</p>}
                            <div style={{ fontSize: '10px', color: 'var(--muted-foreground, #64748b)', marginTop: '4px' }}>
                              {new Date(rev.timestamp).toLocaleString()}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--muted)' }}>
                Select a candidate dossier from the left sidebar to view decision intelligence.
              </div>
            )}
          </main>
        </div>
      )}
    </div>
  )
}
