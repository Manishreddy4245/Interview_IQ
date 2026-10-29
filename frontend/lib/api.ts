/**
 * InterviewIQ API Client
 * Typed client for communicating with the FastAPI backend.
 */

export interface HealthResponse {
  status: string
  service: string
  environment: string
}

export interface DatabaseHealthResponse {
  status: 'connected' | 'unreachable' | 'unconfigured' | 'error'
  detail: string
  database: string
}

export interface GroqHealthResponse {
  configured: boolean
  status: string
  detail: string
}

export interface InterviewSetupRequest {
  role: string
  experience_level: string
  difficulty: string
  focus_areas: string
  question_count?: number
  adaptive?: boolean
  duration_minutes?: number
  job_description?: string
  interview_mode?: 'CODING' | 'VERBAL' | string
}

export interface TestCase {
  id: string
  input: string
  expected_output: string
  is_hidden?: boolean
  explanation?: string | null
}

export interface TestCaseResult {
  test_case_id: string
  input: string
  expected_output: string
  actual_output: string
  passed: boolean
  is_hidden?: boolean
  execution_time_ms?: number | null
  error?: string | null
}

export interface CodeExecutionResponse {
  stdout: string
  stderr: string
  output: string
  exit_code: number
  execution_time_ms?: number | null
  memory_kb?: number | null
  status: string
  error?: string | null
  provider?: string | null
}

export interface CodeSubmissionResult {
  question_id: string
  language: string
  total_tests: number
  passed_tests: number
  all_passed: boolean
  results: TestCaseResult[]
  status: string
  compilation_error?: string | null
  provider_error?: string | null
  estimated_time_complexity?: string | null
  estimated_space_complexity?: string | null
}

export interface SQLExecutionResponse {
  columns: string[]
  rows: any[][]
  row_count: number
  execution_time_ms: number
  status: string
  error?: string | null
}

export interface SQLSubmissionResult {
  question_id: string
  is_correct: boolean
  columns: string[]
  actual_rows: any[][]
  expected_rows: any[][]
  row_count: number
  status: string
  error?: string | null
  optimization_feedback?: string | null
}

export interface SupportedLanguage {
  id: string
  key?: string
  name: string
  label?: string
  display_name?: string
  version: string
  piston_lang?: string
  file_name?: string
  monaco_language?: string
  file_extension?: string
  starter_template?: string
  is_sql?: boolean
}

export interface SQLFixtureTable {
  name: string
  table_name?: string
  row_count?: number
  columns: { name: string; type: string }[]
  sample_rows: Record<string, any>[]
}

export interface SQLFixtureMetadata {
  fixture_key: string
  tables: SQLFixtureTable[]
}

export interface QuestionItem {
  id: string
  question_number: number
  title?: string | null
  text: string
  assessed_skill: string
  normalized_skill?: string | null
  difficulty: string
  rubric: string
  selection_rationale?: string | null
  time_band?: 'comprehensive' | 'focused' | 'concise' | 'expired' | string | null
  gap_category?: string | null
  role_relevance?: string | null
  source_evidence?: string | null
  question_type?: 'verbal' | 'coding' | 'coding_dsa' | 'sql' | 'system_design' | 'multiple_choice' | string
  response_mode?: 'coding_ide' | 'verbal_speech_text' | 'system_design_text' | 'sql_sandbox' | 'multiple_choice' | string | null
  available_modes?: ('coding' | 'verbal' | 'system_design' | 'sql' | 'multiple_choice' | string)[] | null
  recommended_mode?: 'coding' | 'verbal' | 'system_design' | 'sql' | 'multiple_choice' | string | null
  code_template?: string | Record<string, string> | null
  test_cases?: TestCase[] | null
  sql_fixture?: string | null
  sql_schema?: string | null
  expected_sql_query?: string | null
  constraints?: string[] | null
  examples?: any[] | null
  input_format?: string | null
  output_format?: string | null
  options?: string[] | null
  concept?: string | null
  angle?: string | null
  adaptive_action?: string | null
  adaptive_reason?: string | null
}

export type CompetencyStatus = 'not_assessed' | 'needs_further_assessment' | 'demonstrated'

export interface CompetencySkillState {
  skill_name: string
  status: CompetencyStatus
  questions_evaluated: number
  average_score?: number | null
  latest_score?: number | null
  evidence_summary?: string | null
}

export interface SessionCompetencyState {
  session_id: string
  skills: Record<string, CompetencySkillState>
  current_difficulty: string
  total_evaluated_count: number
  updated_at: string
}

export interface InterviewSessionResponse {
  session_id: string
  role: string
  experience_level: string
  difficulty: string
  focus_areas: string
  questions: QuestionItem[]
  active_question_id?: string | null
  target_question_count?: number
  is_adaptive?: boolean
  resume_analysis_id?: string | null
  prioritized_competencies?: string[] | null
  competency_state?: SessionCompetencyState
  duration_minutes?: number
  job_description?: string | null
  interview_mode?: 'CODING' | 'VERBAL' | 'AMBIGUOUS' | string
  is_unreliable_mode?: boolean
  time_remaining_seconds?: number | null
  is_expired?: boolean
  created_at: string
  saved_to_db: boolean
  db_status: string
  db_message?: string
  drafts?: Record<string, Record<string, { code: string; version: number; updated_at: string }>>
}

export interface NextQuestionResponse {
  session_id: string
  question: QuestionItem
  active_question_id?: string | null
  current_difficulty: string
  question_number: number
  target_question_count: number
  is_last_question: boolean
  competency_state: SessionCompetencyState
  time_remaining_seconds?: number | null
  time_band?: 'comprehensive' | 'focused' | 'concise' | string | null
  saved_to_db: boolean
  db_status: string
  db_message?: string
}

export interface SubmitAnswerRequest {
  question_id: string
  answer_text?: string
  answer_mode?: 'coding' | 'verbal' | 'system_design' | 'sql' | 'multiple_choice' | string | null
  code?: string
  language?: string
  sql_query?: string
  execution_result?: any
  remaining_seconds?: number | null
}

export interface SubmitAnswerResponse {
  session_id: string
  question_id: string
  answer_mode?: string | null
  submitted_at: string
  saved_to_db: boolean
  db_status: string
  message: string
}

export interface SaveDraftRequest {
  language: string
  code: string
  version?: number
  updated_at?: string
}

export interface SaveDraftResponse {
  session_id: string
  question_id: string
  language: string
  version: number
  updated_at: string
  saved_to_db: boolean
  db_status: string
  message: string
}

export interface SessionDraftsResponse {
  session_id: string
  drafts: Record<string, Record<string, { code: string; version: number; updated_at: string }>>
}

export interface AdaptiveDecision {
  action: string
  current_topic?: string
  next_difficulty: string
  percentage: number
  strengths?: string[]
  missing_concepts?: string[]
  asked_topics?: string[]
  reason: string
}

export interface SubmitAndAdaptResponse {
  session_id: string
  question_id: string
  answer_mode?: string | null
  evaluation: AnswerEvaluationResponse
  next_question?: QuestionItem | null
  active_question_id?: string | null
  is_last_question: boolean
  is_complete?: boolean
  competency_state: SessionCompetencyState
  time_remaining_seconds?: number | null
  saved_to_db: boolean
  db_status: string
  adaptive_decision?: AdaptiveDecision | null
  stage_timings?: Record<string, number> | null
  message: string
}

export interface CriterionScore {
  score: number
  feedback: string
}

export interface CriterionScores {
  relevance: CriterionScore
  technical_depth: CriterionScore
  completeness: CriterionScore
  structure_flow: CriterionScore
  clarity_conciseness: CriterionScore
  star_structure?: CriterionScore
}

export interface AnswerEvaluationResponse {
  session_id: string
  question_id: string
  overall_score: number
  criterion_scores: CriterionScores
  strengths: string[]
  areas_for_improvement: string[]
  actionable_suggestions: string[]
  coaching_summary: string
  stronger_example_answer?: string | null
  recommended_practice?: string | null
  acoustic_disclaimer?: string
  evaluated_at: string
  saved_to_db: boolean
  db_status: string
  db_message?: string
  decision_support_disclaimer?: string
}

export type IntegrityEventType =
  | 'tab_hidden'
  | 'tab_visible'
  | 'window_blur'
  | 'window_focus'
  | 'camera_mic_granted'
  | 'camera_mic_denied'
  | 'camera_permission_denied'
  | 'camera_unavailable'
  | 'media_track_ended'
  | 'video_track_stopped'
  | 'video_track_ended'
  | 'stream_interrupted'
  | 'stream_recovered'
  | 'face_not_detected'
  | 'candidate_out_of_frame'
  | 'face_detected'
  | 'candidate_visibility_recovered'
  | 'multiple_faces_detected'
  | 'multiple_faces_resolved'
  | 'possible_external_communication'
  | 'communication_alert_cleared'
  | 'detector_unavailable'
  | 'detection_service_unavailable'
  | 'practice_started'
  | 'practice_paused'
  | 'session_completed'
  | 'interview_started'
  | 'interview_paused'
  | 'interview_resumed'
  | 'interview_completed'
  | 'interview_terminated'

export interface IntegrityEventCreate {
  event_type: IntegrityEventType
  timestamp?: string
  question_id?: string | null
  details?: Record<string, unknown>
  severity?: 'info' | 'warning' | 'critical' | string
  duration_seconds?: number | null
  detection_source?: string | null
  detection_confidence?: number | null
  status?: 'active' | 'resolved' | 'requiring_review' | 'recorded' | string
}

export interface IntegrityEventRecord {
  event_id: string
  session_id: string
  question_id?: string | null
  event_type: IntegrityEventType
  timestamp: string
  details?: Record<string, unknown>
  saved_to_db: boolean
  db_status: string
  severity?: 'info' | 'warning' | 'critical' | string
  duration_seconds?: number | null
  detection_source?: string | null
  detection_confidence?: number | null
  status?: 'active' | 'resolved' | 'requiring_review' | 'recorded' | string
}

export interface IntegrityEventsResponse {
  session_id: string
  events: IntegrityEventRecord[]
  total_events: number
  saved_to_db: boolean
  db_status: string
  db_message?: string
}

export interface HumanReviewAuditEntry {
  note_id: string
  reviewer_name?: string | null
  is_verified_identity: boolean
  identity_note?: string
  review_notes: string
  created_at: string
}

export interface HumanReviewAuditRequest {
  reviewer_name?: string | null
  review_notes: string
}

export interface CandidateExplanationRequest {
  event_id?: string | null
  explanation: string
}

export interface CandidateExplanationEntry {
  explanation_id: string
  session_id: string
  event_id?: string | null
  explanation: string
  status: string
  reviewer_outcome?: string | null
  decision_history?: ReviewerDecisionEntry[]
  is_verified_identity: boolean
  identity_note?: string
  created_at: string
  saved_to_db: boolean
  db_status: string
}

export interface ReviewerDecisionEntry {
  decision_id: string
  explanation_id: string
  status: string
  reviewer_name?: string | null
  reviewer_outcome?: string | null
  is_verified_identity: boolean
  identity_note?: string
  created_at: string
}

export interface ReviewerDecisionRequest {
  status?: 'pending_review' | 'reviewed'
  reviewer_name?: string | null
  reviewer_outcome?: string | null
}

export type SkillEvidenceCategory =
  | 'Demonstrated in resume'
  | 'Mentioned but insufficiently evidenced'
  | 'Not demonstrated in resume'
  | 'Requires interview validation'

export interface RoleBenchmarkCompetency {
  skill_name: string
  normalized_skill: string
  importance: string
  description: string
}

export interface TargetRoleBenchmark {
  target_role: string
  experience_level: string
  expected_competencies: RoleBenchmarkCompetency[]
  benchmark_source: string
  disclaimer: string
}

export interface SkillEvidenceItem {
  skill_name: string
  normalized_skill?: string | null
  category: SkillEvidenceCategory
  evidence: string
  relevance_to_role: string
  is_source_grounded?: boolean
  evidence_type?: string
  source_excerpt?: string | null
  is_expected_for_role?: boolean
  classification_rationale?: string | null
  requires_interview_validation?: boolean
}

export interface PersonalizedQuestionItem {
  id: string
  question_number: number
  text: string
  assessed_skill: string
  normalized_skill?: string | null
  gap_category?: string | null
  role_relevance?: string | null
  source_evidence?: string | null
  difficulty: string
  rubric: string
  rationale: string
}

export interface RoleCompetencyRequirement {
  skill_name: string
  normalized_skill: string
  importance: string
  expected_proficiency: string
  description: string
  evaluation_criteria: string
}

export interface RoleDefinition {
  role_id: string
  role_name: string
  description: string
  experience_levels: string[]
  supported_question_types: string[]
  competencies: RoleCompetencyRequirement[]
}

export interface ResumeAnalysisResult {
  analysis_id: string
  owner_id?: string | null
  target_role: string
  experience_level: string
  target_role_benchmark?: TargetRoleBenchmark | null
  extracted_skills: string[]
  projects_and_experience: string[]
  education?: string[]
  work_experience?: string[]
  certifications?: string[]
  skill_evaluations: SkillEvidenceItem[]
  personalized_questions: PersonalizedQuestionItem[]
  role_readiness_summary: string
  is_truncated?: boolean
  analyzed_character_count?: number | null
  created_at: string
  saved_to_db: boolean
  db_status: string
  db_message?: string
}

function resolveBackendBaseUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_URL
  if (envUrl && envUrl.trim().length > 0) {
    return envUrl.trim().replace(/\/+$/, '')
  }
  if (process.env.NODE_ENV === 'production' && typeof window !== 'undefined') {
    console.warn(
      '[InterviewIQ] NEXT_PUBLIC_API_URL is not defined in production environment variables. Ensure NEXT_PUBLIC_API_URL is set in your deployment configuration.'
    )
  }
  return 'http://localhost:8000'
}

const BACKEND_BASE_URL = resolveBackendBaseUrl()

/**
 * Fetch the general health status of the FastAPI service.
 */
export async function getBackendHealth(): Promise<HealthResponse> {
  const response = await fetch(`${BACKEND_BASE_URL}/health`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
    cache: 'no-store',
  })

  if (!response.ok) {
    throw new Error(`Backend health check failed: HTTP ${response.status}`)
  }

  return response.json()
}

/**
 * Fetch the MongoDB Atlas connectivity status.
 */
export async function getDatabaseHealth(): Promise<DatabaseHealthResponse> {
  const response = await fetch(`${BACKEND_BASE_URL}/health/db`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
    cache: 'no-store',
  })

  return response.json()
}

/**
 * Fetch the Groq client configuration readiness status.
 */
export async function getGroqHealth(): Promise<GroqHealthResponse> {
  const response = await fetch(`${BACKEND_BASE_URL}/health/groq`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
    cache: 'no-store',
  })

  return response.json()
}

/**
 * Setup an interview session and generate AI questions.
 */
export async function createInterviewSession(
  setup: InterviewSetupRequest,
): Promise<InterviewSessionResponse> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/interviews/setup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(setup),
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to create interview session: HTTP ${response.status}`)
  }

  return data
}

/**
 * Submit an answer for a specific question within a session.
 */
export async function submitQuestionAnswer(
  sessionId: string,
  payload: SubmitAnswerRequest,
): Promise<SubmitAnswerResponse> {
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/interviews/${encodeURIComponent(sessionId)}/answers`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to submit answer: HTTP ${response.status}`)
  }

  return data
}

/**
 * Save candidate code draft for a specific question in a session.
 */
export async function saveQuestionDraft(
  sessionId: string,
  questionId: string,
  payload: SaveDraftRequest,
): Promise<SaveDraftResponse> {
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/interviews/${encodeURIComponent(sessionId)}/questions/${encodeURIComponent(questionId)}/draft`,
    {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to save question draft: HTTP ${response.status}`)
  }

  return data
}

/**
 * Retrieve all saved code drafts for an interview session.
 */
export async function getSessionDrafts(sessionId: string): Promise<SessionDraftsResponse> {
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/interviews/${encodeURIComponent(sessionId)}/drafts`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to fetch session drafts: HTTP ${response.status}`)
  }

  return data
}

/**
 * Atomic submission, AI evaluation, and sequential adaptive next-question transition.
 */
export async function submitAndAdaptQuestion(
  sessionId: string,
  payload: SubmitAnswerRequest,
): Promise<SubmitAndAdaptResponse> {
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/interviews/${encodeURIComponent(sessionId)}/submit-and-adapt`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to submit and adapt question: HTTP ${response.status}`)
  }

  return data
}

export interface EvaluateAnswerPayload {
  answer_text?: string
  answer_mode?: string
  code?: string
  language?: string
  sql_query?: string
}

/**
 * Evaluate candidate's answer using Groq AI and communication coach.
 */
export async function evaluateAnswer(
  sessionId: string,
  questionId: string,
  payloadOrText?: string | EvaluateAnswerPayload,
): Promise<AnswerEvaluationResponse> {
  const bodyPayload =
    typeof payloadOrText === 'string'
      ? { answer_text: payloadOrText }
      : (payloadOrText || {})

  const response = await fetch(
    `${BACKEND_BASE_URL}/api/interviews/${encodeURIComponent(sessionId)}/questions/${encodeURIComponent(questionId)}/evaluate`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(bodyPayload),
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to evaluate answer: HTTP ${response.status}`)
  }

  return data
}

/**
 * Record an observable browser or media integrity event.
 */
export async function logIntegrityEvent(
  sessionId: string,
  payload: IntegrityEventCreate,
): Promise<IntegrityEventRecord> {
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/interviews/${encodeURIComponent(sessionId)}/integrity-events`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to record integrity event: HTTP ${response.status}`)
  }

  return data
}

/**
 * Retrieve the chronological integrity timeline for a session.
 */
export async function getIntegrityTimeline(
  sessionId: string,
): Promise<IntegrityEventsResponse> {
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/interviews/${encodeURIComponent(sessionId)}/integrity-events`,
    {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to retrieve integrity timeline: HTTP ${response.status}`)
  }

  return data
}

/**
 * Submit an auditable human review note for session integrity telemetry.
 */
export async function submitIntegrityReview(
  sessionId: string,
  payload: HumanReviewAuditRequest,
): Promise<HumanReviewAuditEntry> {
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/interviews/${encodeURIComponent(sessionId)}/integrity-review`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to submit review note: HTTP ${response.status}`)
  }

  return data
}

/**
 * Retrieve the audit trail of human review notes for a session.
 */
export async function getIntegrityReviews(
  sessionId: string,
): Promise<HumanReviewAuditEntry[]> {
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/interviews/${encodeURIComponent(sessionId)}/integrity-review`,
    {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to retrieve review notes: HTTP ${response.status}`)
  }

  return data
}

/**
 * Submit an auditable candidate contextual explanation or dispute for session integrity telemetry.
 */
export async function submitCandidateExplanation(
  sessionId: string,
  payload: CandidateExplanationRequest,
): Promise<CandidateExplanationEntry> {
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/interviews/${encodeURIComponent(sessionId)}/integrity-explanations`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to submit candidate explanation: HTTP ${response.status}`)
  }

  return data
}

/**
 * Retrieve the audit trail of candidate explanations for a session.
 */
export async function getCandidateExplanations(
  sessionId: string,
): Promise<CandidateExplanationEntry[]> {
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/interviews/${encodeURIComponent(sessionId)}/integrity-explanations`,
    {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to retrieve candidate explanations: HTTP ${response.status}`)
  }

  return data
}

/**
 * Submit an auditable human reviewer decision or determination note for a candidate explanation.
 */
export async function submitReviewerDecision(
  sessionId: string,
  explanationId: string,
  payload: ReviewerDecisionRequest,
): Promise<CandidateExplanationEntry> {
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/interviews/${encodeURIComponent(sessionId)}/integrity-explanations/${encodeURIComponent(explanationId)}/decision`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to record reviewer decision: HTTP ${response.status}`)
  }

  return data
}

/**
 * Retrieve session details by session ID.
 */
export async function getInterviewSession(
  sessionId: string,
): Promise<InterviewSessionResponse> {
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/interviews/${encodeURIComponent(sessionId)}`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to retrieve session: HTTP ${response.status}`)
  }

  return data
}

/**
 * Upload a PDF resume and perform role-specific skill gap analysis.
 */
export async function analyzeResume(
  file: File,
  targetRole: string,
  experienceLevel: string = 'Mid-Level',
): Promise<ResumeAnalysisResult> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('target_role', targetRole)
  formData.append('experience_level', experienceLevel)

  const token = getAuthToken()
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(`${BACKEND_BASE_URL}/api/resume/analyze`, {
    method: 'POST',
    headers,
    body: formData,
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to analyze resume: HTTP ${response.status}`)
  }

  return data
}

/**
 * Fetch the authenticated student's active resume analysis.
 */
export async function getMyResume(): Promise<ResumeAnalysisResult> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/resume/my-resume`, {
    method: 'GET',
    headers: getAuthHeaders(),
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to retrieve student resume: HTTP ${response.status}`)
  }

  return data
}

/**
 * Update candidate-verified skills on a resume analysis.
 */
export async function updateResumeSkills(
  analysisId: string,
  skills: string[],
): Promise<ResumeAnalysisResult> {
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/resume/${encodeURIComponent(analysisId)}/skills`,
    {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify({ skills }),
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to update skills: HTTP ${response.status}`)
  }

  return data
}

/**
 * Select a target job role and calculate initial skill-gap analysis.
 */
export async function selectTargetRole(
  analysisId: string,
  targetRole: string,
  experienceLevel: string = 'Mid-Level',
): Promise<ResumeAnalysisResult> {
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/resume/${encodeURIComponent(analysisId)}/select-role`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ target_role: targetRole, experience_level: experienceLevel }),
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to select role: HTTP ${response.status}`)
  }

  return data
}

/**
 * Retrieve the standardized catalog of supported job preparation roles.
 */
export async function getSupportedRoles(): Promise<RoleDefinition[]> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/roles`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to retrieve supported roles: HTTP ${response.status}`)
  }

  return data
}

/**
 * Retrieve standardized competency requirements for a specific role.
 */
export async function getRoleDefinition(roleName: string): Promise<RoleDefinition> {
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/roles/${encodeURIComponent(roleName)}`,
    {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to retrieve role details: HTTP ${response.status}`)
  }

  return data
}

/**
 * Fetch an existing resume analysis by ID.
 */
export async function getResumeAnalysis(
  analysisId: string,
): Promise<ResumeAnalysisResult> {
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/resume/${encodeURIComponent(analysisId)}`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to retrieve resume analysis: HTTP ${response.status}`)
  }

  return data
}

export interface StartInterviewFromResumeOptions {
  adaptive?: boolean
  difficulty?: string
  question_count?: number
  interview_mode?: 'CODING' | 'VERBAL' | string
}

/**
 * Start an active interview session from the personalized questions generated in a resume analysis.
 */
export async function startInterviewFromResume(
  analysisId: string,
  options?: StartInterviewFromResumeOptions,
): Promise<InterviewSessionResponse> {
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/resume/${encodeURIComponent(analysisId)}/start-interview`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: options ? JSON.stringify(options) : undefined,
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(
      data.detail || `Failed to start interview from resume analysis: HTTP ${response.status}`,
    )
  }

  return data
}

export interface CriterionAverageScores {
  relevance?: number | null
  technical_depth?: number | null
  completeness?: number | null
  structure_flow?: number | null
  clarity_conciseness?: number | null
  star_structure?: number | null
}

export interface ExecutiveSummaryDetails {
  overall_score?: number | null
  scoring_calculation: string
  total_questions: number
  attempted_questions: number
  answered_questions: number
  evaluated_questions: number
  unevaluated_questions: number
  evaluation_coverage_pct: number
  strongest_competencies: string[]
  priority_weaknesses: string[]
  recurring_mistakes: string[]
  readiness_level: string
  readiness_summary: string
  recommended_learning_priorities: string[]
}

export interface StrengthEvidenceDetail {
  concept: string
  why_correct: string
  evidence_quote?: string | null
}

export interface WeaknessEvidenceDetail {
  concept: string
  technical_impact: string
  issue_type: 'incorrect_statement' | 'missing_explanation' | 'incomplete_solution' | 'unassessed_area' | string
  evidence_quote?: string | null
}

export interface QuestionRubricDeduction {
  criterion_name: string
  expected_standard: string
  demonstrated_evidence: string
  missing_or_incorrect: string
  score_awarded: number
  max_score: number
  deduction_reason: string
}

export interface TestCaseExecutionRecord {
  test_case_id: string
  input: string
  expected_output: string
  actual_output?: string | null
  passed: boolean
  is_hidden?: boolean
  error?: string | null
}

export interface QuestionSolutionAnalysis {
  expected_approach: string
  model_answer?: string | null
  tradeoffs_and_terminology: string[]
  why_model_is_stronger?: string | null
  is_coding: boolean
  code_mistakes: string[]
  missed_edge_cases: string[]
  test_cases_summary?: string | null
  test_cases: TestCaseExecutionRecord[]
  optimal_algorithm?: string | null
  time_complexity?: string | null
  space_complexity?: string | null
  corrected_code?: string | null
  verification_mode: 'verified_execution' | 'static_analysis' | 'unverified' | string
}

export interface QuestionActionableImprovement {
  specific_correction: string
  concept_to_study: string
  targeted_exercise: string
  resolution_criterion: string
}

export interface QuestionPerformanceSummary {
  question_id: string
  question_number: number
  question_text: string
  assessed_skill: string
  difficulty: string
  is_answered: boolean
  is_evaluated: boolean
  overall_score?: number | null
  criterion_scores?: CriterionScores | null
  strengths: string[]
  areas_for_improvement: string[]
  candidate_answer_snippet?: string | null
  question_type?: string
  code_snippet?: string | null
  language?: string | null
  sql_query?: string | null
  tests_passed?: string | null
  sql_status?: string | null
  full_candidate_answer?: string | null
  full_code?: string | null
  answer_availability?: 'available' | 'not_stored' | 'unanswered' | string
  strengths_detail?: StrengthEvidenceDetail[]
  weaknesses_detail?: WeaknessEvidenceDetail[]
  rubric_breakdown?: QuestionRubricDeduction[]
  solution_analysis?: QuestionSolutionAnalysis | null
  actionable_improvement?: QuestionActionableImprovement | null
}

export interface CompetencyAnalysisItem {
  competency_name: string
  average_score?: number | null
  evaluated_questions_count: number
  total_questions_count: number
  status: 'Demonstrated' | 'Needs Further Assessment' | 'Insufficient Evidence' | string
  demonstrated_strengths: string[]
  recurring_weaknesses: string[]
  supporting_evidence: string[]
}

export interface PersonalizedRoadmapItem {
  priority_rank: number
  topic: string
  why_it_matters: string
  what_to_learn_first: string
  practice_exercise: string
  completion_criterion: string
}

export interface ResumeSkillComparisonItem {
  skill_name: string
  normalized_skill?: string | null
  target_role?: string | null
  role_importance?: string | null
  resume_evidence_category: string
  resume_evidence?: string | null
  resume_is_grounded?: boolean | null
  resume_source_excerpt?: string | null
  gap_priority_tier?: number | null
  selection_reason?: string | null
  question_id?: string | null
  question_text?: string | null
  candidate_answer_reference?: string | null
  candidate_answer_excerpt?: string | null
  evaluation_overall_score?: number | null
  criterion_feedback?: Record<string, any> | null
  strengths?: string[]
  areas_for_improvement?: string[]
  interview_status: string
  post_interview_status?: string
  status_rationale?: string | null
  requires_further_validation?: boolean
  details: string
}

export interface ResumeComparisonSection {
  associated_analysis_id: string
  target_role: string
  skills_comparison: ResumeSkillComparisonItem[]
  comparison_summary: string
  demonstrated_competencies_count?: number
  partially_demonstrated_count?: number
  requires_further_validation_count?: number
  unassessed_count?: number
}

export interface PotentialCommunicationEventRecord {
  event_id: string
  timestamp: string
  duration_seconds?: number | null
  event_description: string
  evidence_source: string
  confidence?: number | null
  warning_displayed: boolean
  review_status: string
  question_id?: string | null
  incident_type: string
}

export interface IntegrityReportSection {
  total_events: number
  events_summary: Record<string, number>
  events_timeline: IntegrityEventRecord[]
  cumulative_unfocused_seconds?: number
  incomplete_intervals_count?: number
  events_by_question?: Record<string, number>
  human_reviews?: HumanReviewAuditEntry[]
  candidate_explanations?: CandidateExplanationEntry[]
  potential_communication_events?: PotentialCommunicationEventRecord[]
  neutral_disclaimer: string
  score_impact: string
}

export interface InterviewReportResponse {
  report_id: string
  session_id: string
  created_at: string
  role: string
  experience_level: string
  difficulty: string
  focus_areas: string
  total_questions: number
  answered_questions: number
  unanswered_questions: number
  evaluated_questions: number
  evaluation_coverage_pct: number
  overall_score?: number | null
  score_status: 'calculated' | 'insufficient_data'
  scoring_formula_explanation: string
  criterion_averages: CriterionAverageScores
  key_strengths: string[]
  priority_improvements: string[]
  recommended_next_steps: string[]
  executive_summary: string
  questions_performance: QuestionPerformanceSummary[]
  has_resume_comparison: boolean
  resume_comparison?: ResumeComparisonSection | null
  integrity_summary: IntegrityReportSection
  executive_summary_details?: ExecutiveSummaryDetails | null
  competencies_analysis?: CompetencyAnalysisItem[]
  learning_roadmap?: PersonalizedRoadmapItem[]
  saved_to_db: boolean
  db_status: string
  db_message?: string
}

export interface AvailableReportItem {
  session_id: string
  report_id?: string | null
  resume_analysis_id?: string | null
  role: string
  experience_level?: string | null
  difficulty?: string | null
  status: string
  report_status: string
  overall_score?: number | null
  created_at?: string | null
  owner_id?: string | null
  interview_mode?: string | null
  is_persisted?: boolean | null
}

/**
 * Retrieve list of interview sessions and reports available to the current user.
 */
export async function getAvailableReports(): Promise<AvailableReportItem[]> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/interviews/available-reports`, {
    method: 'GET',
    headers: getAuthHeaders(),
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to retrieve available reports: HTTP ${response.status}`)
  }

  return data
}

/**
 * Generate or recompute the final decision intelligence report for an interview session.
 */
export async function generateFinalReport(
  sessionId: string,
): Promise<InterviewReportResponse> {
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/interviews/${encodeURIComponent(sessionId)}/report`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to generate report: HTTP ${response.status}`)
  }

  return data
}

/**
 * Retrieve an existing compiled report for an interview session.
 */
export async function getFinalReport(
  sessionId: string,
): Promise<InterviewReportResponse> {
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/interviews/${encodeURIComponent(sessionId)}/report`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to retrieve report: HTTP ${response.status}`)
  }

  return data
}


/**
 * Dynamically generate the next best adaptive question based on prior answers, remaining time, and competency gaps.
 */
export async function generateNextQuestion(
  sessionId: string,
  clientRemainingSeconds?: number,
): Promise<NextQuestionResponse> {
  const payload = clientRemainingSeconds !== undefined ? { client_remaining_seconds: clientRemainingSeconds } : {}
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/interviews/${encodeURIComponent(sessionId)}/next-question`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to generate next question: HTTP ${response.status}`)
  }

  return data
}

/**
 * Retrieve live competency tracking state and adapted difficulty for an interview session.
 */
export async function getSessionCompetencies(
  sessionId: string,
): Promise<SessionCompetencyState> {
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/interviews/${encodeURIComponent(sessionId)}/competencies`,
    {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to retrieve competencies: HTTP ${response.status}`)
  }

  return data
}

/**
 * Module 05: Candidate Decision Intelligence Interfaces & API Calls
 */

export interface CompetencyEvidenceItem {
  skill_name: string
  status: string
  category?: string | null
  evidence_text?: string | null
  source_type: 'resume' | 'interview_answer' | string
  role_importance?: string | null
}

export interface DecisionCriterionSummary {
  relevance?: number | null
  technical_depth?: number | null
  completeness?: number | null
  structure_flow?: number | null
  clarity_conciseness?: number | null
  star_structure?: number | null
}

export interface HumanReviewDecisionRecord {
  decision_id: string
  reviewer_name: string
  recommendation: string
  notes?: string | null
  timestamp: string
}

export interface HumanReviewDecisionRequest {
  reviewer_name: string
  recommendation: string
  notes?: string
}

export interface CandidateDossierItem {
  record_id: string
  record_type: 'resume_analysis' | 'interview_report' | 'interview_session' | string
  candidate_identifier: string
  target_role: string
  experience_level: string
  created_at?: string | null
  overall_score?: number | null
  scoring_status: string
  criterion_scores: DecisionCriterionSummary
  demonstrated_competencies: CompetencyEvidenceItem[]
  competency_gaps: CompetencyEvidenceItem[]
  key_strengths: string[]
  critical_improvements: string[]
  executive_summary?: string | null
  integrity_event_count: number
  cumulative_unfocused_seconds?: number | null
  linked_resume_id?: string | null
  linked_session_id?: string | null
  human_reviews: HumanReviewDecisionRecord[]
}

export interface DecisionOverviewResponse {
  total_records: number
  resume_analyses_count: number
  interview_reports_count: number
  interview_sessions_count: number
  dossiers: CandidateDossierItem[]
}

/**
 * Retrieve overview of real candidate decision intelligence dossiers.
 */
export async function getCandidateDecisionOverview(): Promise<DecisionOverviewResponse> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/decision/overview`, {
    method: 'GET',
    headers: getAuthHeaders(),
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to fetch decision overview: HTTP ${response.status}`)
  }

  return data
}

/**
 * Retrieve detailed dossier for a specific candidate or session record.
 */
export async function getCandidateDecisionDossier(
  recordId: string,
): Promise<CandidateDossierItem> {
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/decision/dossier/${encodeURIComponent(recordId)}`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to fetch dossier: HTTP ${response.status}`)
  }

  return data
}

/**
 * Submit an append-only human reviewer determination on a candidate dossier.
 */
export async function submitCandidateDecisionReview(
  recordId: string,
  payload: HumanReviewDecisionRequest,
): Promise<HumanReviewDecisionRecord> {
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/decision/dossier/${encodeURIComponent(recordId)}/review`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to submit review: HTTP ${response.status}`)
  }

  return data
}

// ==========================================
// Authentication & Role-Based Access Control
// ==========================================

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  password: string
  name: string
  email?: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
  user_id: string
  username: string
  name: string
  role: 'candidate' | 'reviewer' | 'admin'
}

export interface UserProfile {
  user_id: string
  username: string
  name: string
  role: 'candidate' | 'reviewer' | 'admin'
  permissions: string[]
}

let activeAuthToken: string | null = null
let activeAuthUser: UserProfile | null = null

export function getAuthToken(): string | null {
  if (typeof window !== 'undefined' && !activeAuthToken) {
    activeAuthToken = localStorage.getItem('interviewiq_jwt_token')
  }
  return activeAuthToken
}

export function setAuthToken(token: string | null) {
  activeAuthToken = token
  if (typeof window !== 'undefined') {
    if (token) localStorage.setItem('interviewiq_jwt_token', token)
    else localStorage.removeItem('interviewiq_jwt_token')
  }
}

export function getAuthUser(): UserProfile | null {
  if (typeof window !== 'undefined' && !activeAuthUser) {
    const raw = localStorage.getItem('interviewiq_auth_user')
    if (raw) {
      try {
        activeAuthUser = JSON.parse(raw)
      } catch {}
    }
  }
  return activeAuthUser
}

export function setAuthUser(user: UserProfile | null) {
  activeAuthUser = user
  if (typeof window !== 'undefined') {
    if (user) localStorage.setItem('interviewiq_auth_user', JSON.stringify(user))
    else localStorage.removeItem('interviewiq_auth_user')
  }
}

export function logoutUser() {
  setAuthToken(null)
  setAuthUser(null)
}

export function getAuthHeaders(): Record<string, string> {
  const token = getAuthToken()
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}

/**
 * Authenticate with credentials and receive a signed JWT token.
 */
export async function loginUser(payload: LoginRequest): Promise<TokenResponse> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Authentication failed: HTTP ${response.status}`)
  }

  setAuthToken(data.access_token)
  setAuthUser({
    user_id: data.user_id,
    username: data.username,
    name: data.name,
    role: data.role,
    permissions: [],
  })

  return data
}

/**
 * Register a new candidate account. Role is strictly candidate.
 */
export async function registerCandidate(payload: RegisterRequest): Promise<TokenResponse> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Registration failed: HTTP ${response.status}`)
  }

  setAuthToken(data.access_token)
  setAuthUser({
    user_id: data.user_id,
    username: data.username,
    name: data.name,
    role: data.role,
    permissions: [],
  })

  return data
}

/**
 * Obtain a genuine signed demo token for live role switching (candidate, reviewer, admin).
 * Protected on backend to development mode only.
 */
export async function switchDemoRole(role: 'candidate' | 'reviewer' | 'admin'): Promise<TokenResponse> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/auth/demo-token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ role }),
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to switch demo role: HTTP ${response.status}`)
  }

  setAuthToken(data.access_token)
  setAuthUser({
    user_id: data.user_id,
    username: data.username,
    name: data.name,
    role: data.role,
    permissions: [],
  })

  return data
}

/**
 * Get current authenticated user profile and active permissions.
 */
export async function getCurrentUserProfile(): Promise<UserProfile> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/auth/me`, {
    method: 'GET',
    headers: getAuthHeaders(),
  })

  const data = await response.json()
  if (!response.ok) {
    if (response.status === 401) {
      logoutUser()
    }
    throw new Error(data.detail || `Failed to get user profile: HTTP ${response.status}`)
  }

  setAuthUser(data)
  return data
}


// ==========================================
// Communication Assistant Types & Methods
// ==========================================

export interface DimensionDetail {
  score: number
  feedback: string
}

export interface TranscriptMetrics {
  word_count: number
  speaking_duration_seconds?: number | null
  words_per_minute?: number | null
  filler_word_count: number
  filler_words_detected: Record<string, number>
}

export interface CommunicationCoachRequest {
  message?: string
  transcript?: string | null
  practice_task?: 'question' | 'introduction' | 'improve_answer' | 'technical_concept'
  task_prompt?: string | null
  context_type?: 'general' | 'answer' | 'evaluation' | 'star_practice'
  context_text?: string | null
  target_role?: string | null
  session_id?: string | null
  recording_duration_seconds?: number | null
}

export interface StarBreakdown {
  situation: string
  task: string
  action: string
  result: string
}

export interface CommunicationCoachResponse {
  summary?: string
  coaching_advice: string
  dimension_scores?: Record<string, DimensionDetail>
  strengths?: string[]
  areas_for_improvement?: string[]
  actionable_tips: string[]
  star_breakdown?: StarBreakdown | null
  suggested_revision?: string | null
  next_practice_exercise?: string | null
  transcript_metrics?: TranscriptMetrics | null
  clarity_focus: string
  grounded_in_evidence: boolean
  disclaimer: string
  evaluation_mode?: 'ai' | 'deterministic_fallback'
}

/**
 * Request contextual interview communication advice and STAR structuring.
 */
export async function requestCommunicationCoach(
  payload: CommunicationCoachRequest,
): Promise<CommunicationCoachResponse> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/communication/coach`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Communication coach failed: HTTP ${response.status}`)
  }

  return data
}

/**
 * Retrieve list of genuine languages supported by the execution runner.
 */
export async function getSupportedLanguages(): Promise<{ languages: SupportedLanguage[] }> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/interviews/languages`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to fetch supported languages: HTTP ${response.status}`)
  }

  return data
}

/**
 * Execute candidate code in an isolated sandbox with optional custom stdin.
 */
export async function executeCode(payload: {
  language: string
  code: string
  stdin?: string
  question_id?: string
  function_name?: string
  session_id?: string
}): Promise<CodeExecutionResponse> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/interviews/execute-code`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to execute code: HTTP ${response.status}`)
  }

  return data
}

/**
 * Submit candidate code solution to run against question test cases.
 */
export async function submitCodeSolution(payload: {
  question_id: string
  language: string
  code: string
  verbal_explanation?: string
  session_id?: string
  test_cases?: TestCase[]
}): Promise<CodeSubmissionResult> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/interviews/submit-code`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to submit code solution: HTTP ${response.status}`)
  }

  return data
}

/**
 * Retrieve schema definition, columns, and sample records for a SQL fixture.
 */
export async function getSqlSchema(fixtureKey: string): Promise<SQLFixtureMetadata> {
  const response = await fetch(
    `${BACKEND_BASE_URL}/api/interviews/sql-schema/${encodeURIComponent(fixtureKey)}`,
    {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    },
  )

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to fetch SQL schema: HTTP ${response.status}`)
  }

  return data
}

/**
 * Execute candidate SQL query inside an ephemeral in-memory SQLite sandbox.
 */
export async function executeSql(payload: {
  query: string
  question_id?: string
}): Promise<SQLExecutionResponse> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/interviews/execute-sql`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to execute SQL query: HTTP ${response.status}`)
  }

  return data
}

/**
 * Submit candidate SQL query to evaluate against expected benchmark result set.
 */
export async function submitSqlSolution(payload: {
  question_id: string
  query: string
  verbal_explanation?: string
  session_id?: string
  expected_query?: string
  fixture_key?: string
}): Promise<SQLSubmissionResult> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/interviews/submit-sql`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(payload),
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Failed to submit SQL solution: HTTP ${response.status}`)
  }

  return data
}

export interface AudioTranscriptionResponse {
  transcript: string
  detected_language?: string
  model_used: string
  duration_seconds?: number | null
  file_size_bytes: number
}

/**
 * Transcribe candidate speech audio to text via server-side Whisper pipeline.
 * Accepts an audio Blob or File and submits multipart form data to POST /api/audio/transcribe.
 */
export async function transcribeAudio(
  audioBlob: Blob,
  options?: {
    sessionId?: string
    questionId?: string
    filename?: string
    language?: string
  },
): Promise<AudioTranscriptionResponse> {
  const formData = new FormData()
  const filename = options?.filename || (audioBlob.type.includes('wav') ? 'audio.wav' : 'audio.webm')
  formData.append('file', audioBlob, filename)

  if (options?.sessionId) {
    formData.append('session_id', options.sessionId)
  }
  if (options?.questionId) {
    formData.append('question_id', options.questionId)
  }
  if (options?.language) {
    formData.append('language', options.language)
  }

  const token = getAuthToken()
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(`${BACKEND_BASE_URL}/api/audio/transcribe`, {
    method: 'POST',
    headers,
    body: formData,
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `Audio transcription failed: HTTP ${response.status}`)
  }

  return data
}

export { BACKEND_BASE_URL }
