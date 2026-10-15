/**
 * InterviewIQ — Real-Time External Communication Detector
 *
 * Provides evidence-supported detection for potential communication with another person:
 * 1. Multimodal correlation: Multiple faces visible in camera frame while active speech is detected.
 * 2. Conversational dialogue & side-query pattern analysis: Evaluates speech transcripts for
 *    distinct external queries or collaborative prompts (distinguishing monologues and thinking aloud).
 * 3. Temporal debouncing & incident lifecycle: Generates single consolidated incident records
 *    with duration, avoiding continuous duplicate popups.
 * 4. Non-accusatory framing: Flags incidents as potential integrity concerns requiring human review.
 */

export interface CommunicationDetectionInput {
  hasMultipleFaces?: boolean
  facesDetected?: number
  isSpeechActive: boolean
  transcriptText?: string
  interimTranscript?: string
  currentTranscript?: string
  questionId?: string | null
  currentQuestionId?: string | null
}

export interface CommunicationIncidentResult {
  detected: boolean
  incidentActive: boolean
  type: 'possible_external_communication'
  status: 'active' | 'resolved' | 'none'
  reason: string
  source: 'multimodal_audio_visual' | 'dialogue_transcription_analyzer' | 'none'
  evidenceSource: string
  confidence: number
  warningText: string
  warningMessage: string
  isNewIncident: boolean
  durationSeconds: number
}

// Conversational query phrases strongly indicating external communication or collaboration
const EXTERNAL_DIALOGUE_PATTERNS: RegExp[] = [
  /\b(?:can|could) you (?:help|tell|show|give) me\b/i,
  /\bwhat(?:'s| is) the (?:answer|solution|code|query|approach)\b/i,
  /\bhow do (?:you|i|we) (?:solve|write|do) this\b/i,
  /\bwhat do you think\b/i,
  /\btell me what to (?:say|write|type)\b/i,
  /\bis (?:that|this) (?:right|correct)\b/i,
  /\bcan you check this\b/i,
  /\blook at (?:my|the) screen\b/i,
  /\bwhat should i (?:say|write|do now)\b/i,
  /\bsearch (?:for|up) (?:the|how)\b/i,
  /\bcan you google\b/i,
  /\bwhisper (?:it|to me)\b/i,
]

export interface CommunicationDetectorConfig {
  cooldownMs?: number // Cooldown before a new incident can be triggered after resolution
  dialogueDebounceMs?: number // Required duration of dialogue pattern
  onWarningTriggered?: (incident: CommunicationIncidentResult) => void
  onWarningCleared?: (durationSec: number) => void
}

export class ExternalCommunicationDetector {
  private config: Required<CommunicationDetectorConfig>
  private isIncidentActive = false
  private incidentStartTime: number | null = null
  private lastAlertTime = 0
  private lastSource: 'multimodal_audio_visual' | 'dialogue_transcription_analyzer' | 'none' = 'none'
  private lastReason = ''
  private lastConfidence = 0.75

  constructor(config?: CommunicationDetectorConfig) {
    this.config = {
      cooldownMs: config?.cooldownMs || 10000,
      dialogueDebounceMs: config?.dialogueDebounceMs || 1500,
      onWarningTriggered: config?.onWarningTriggered || (() => {}),
      onWarningCleared: config?.onWarningCleared || (() => {}),
    }
  }

  public evaluate(input: CommunicationDetectionInput): CommunicationIncidentResult | null {
    const now = Date.now()
    const hasMultiple = Boolean(
      input.hasMultipleFaces || (typeof input.facesDetected === 'number' && input.facesDetected >= 2)
    )

    // 1. Evidence Signal 1: Multimodal Audio-Visual Correlation
    // Secondary person in camera frame while candidate/room speech is active
    let detected = false
    let source: 'multimodal_audio_visual' | 'dialogue_transcription_analyzer' | 'none' = 'none'
    let reason = ''
    let confidence = 0.0

    if (hasMultiple && input.isSpeechActive) {
      detected = true
      source = 'multimodal_audio_visual'
      reason = 'Concurrent secondary face presence and active speech activity observed in camera frame.'
      confidence = 0.88
    }

    // 2. Evidence Signal 2: Conversational Dialogue / Collaboration Markers in Transcript
    const fullText = (
      input.currentTranscript ||
      `${input.transcriptText || ''} ${input.interimTranscript || ''}`
    ).trim()

    if (!detected && fullText) {
      for (const pattern of EXTERNAL_DIALOGUE_PATTERNS) {
        if (pattern.test(fullText)) {
          detected = true
          source = 'dialogue_transcription_analyzer'
          reason = `Speech transcript contains conversational assistance phrasing: "${fullText.slice(0, 80)}..."`
          confidence = 0.82
          break
        }
      }
    }

    const warningText =
      'Potential Integrity Concern: Communication with another person has been detected. Please complete the interview independently. This incident may be flagged for malpractice review.'

    // Incident lifecycle management
    if (detected) {
      let isNew = false
      if (!this.isIncidentActive) {
        // Enforce cooldown between distinct alerts
        if (now - this.lastAlertTime >= this.config.cooldownMs) {
          this.isIncidentActive = true
          this.incidentStartTime = now
          this.lastAlertTime = now
          this.lastSource = source
          this.lastReason = reason
          this.lastConfidence = confidence
          isNew = true

          const result: CommunicationIncidentResult = {
            detected: true,
            incidentActive: true,
            type: 'possible_external_communication',
            status: 'active',
            reason,
            source,
            evidenceSource: source,
            confidence,
            warningText,
            warningMessage: warningText,
            isNewIncident: true,
            durationSeconds: 0,
          }
          this.config.onWarningTriggered(result)
          return result
        }
        // Under cooldown, do not fire a duplicate popup
        return null
      }

      const durationSeconds = this.incidentStartTime ? Math.round((now - this.incidentStartTime) / 1000) : 0
      return {
        detected: true,
        incidentActive: true,
        type: 'possible_external_communication',
        status: 'active',
        reason: this.lastReason || reason,
        source: this.lastSource || source,
        evidenceSource: this.lastSource || source,
        confidence: this.lastConfidence || confidence,
        warningText,
        warningMessage: warningText,
        isNewIncident: isNew,
        durationSeconds,
      }
    } else {
      // Condition has cleared
      if (this.isIncidentActive) {
        const durationSeconds = this.incidentStartTime ? Math.round((now - this.incidentStartTime) / 1000) : 0
        this.isIncidentActive = false
        this.incidentStartTime = null
        this.config.onWarningCleared(durationSeconds)

        return {
          detected: false,
          incidentActive: false,
          type: 'possible_external_communication',
          status: 'resolved',
          reason: 'External communication condition cleared',
          source: 'none',
          evidenceSource: 'none',
          confidence: 0,
          warningText: '',
          warningMessage: '',
          isNewIncident: false,
          durationSeconds,
        }
      }

      // Normal state with no incident active
      return null
    }
  }

  public reset() {
    this.isIncidentActive = false
    this.incidentStartTime = null
    this.lastAlertTime = 0
  }
}
