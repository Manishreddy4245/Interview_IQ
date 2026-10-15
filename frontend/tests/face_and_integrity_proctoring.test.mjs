import test from 'node:test'
import assert from 'node:assert/strict'
import { ExternalCommunicationDetector } from '../lib/communication-detector.ts'
import { FaceVisibilityTracker } from '../lib/face-detector.ts'

test('ExternalCommunicationDetector: ordinary speech with 1 face produces no anomaly', () => {
  const detector = new ExternalCommunicationDetector({ cooldownMs: 1000 })

  const res1 = detector.evaluate({
    facesDetected: 1,
    isSpeechActive: true,
    currentTranscript: 'I implemented a binary search tree to optimize query lookup times.',
    questionId: 'q1',
  })

  assert.equal(res1, null, 'Ordinary candidate verbal explanation should not trigger communication alert')
})

test('ExternalCommunicationDetector: detects multiple people speaking and returns active incident', () => {
  const detector = new ExternalCommunicationDetector({ cooldownMs: 1000 })

  const res = detector.evaluate({
    facesDetected: 2,
    isSpeechActive: true,
    currentTranscript: 'Yes, looking at the code right now.',
    questionId: 'q1',
  })

  assert.ok(res !== null, 'Multimodal multiple faces + active speech should trigger communication incident')
  assert.equal(res.status, 'active')
  assert.equal(res.incidentActive, true)
  assert.equal(res.type, 'possible_external_communication')
  assert.ok(res.warningMessage.includes('Communication with another person has been detected'))
  assert.equal(res.evidenceSource, 'multimodal_audio_visual')
})

test('ExternalCommunicationDetector: detects external question dialogue prompt in transcript', () => {
  const detector = new ExternalCommunicationDetector({ cooldownMs: 1000 })

  const res = detector.evaluate({
    facesDetected: 1,
    isSpeechActive: true,
    currentTranscript: 'Can you tell me the answer for this database question?',
    questionId: 'q2',
  })

  assert.ok(res !== null, 'External query prompt should trigger warning')
  assert.equal(res.status, 'active')
  assert.equal(res.incidentActive, true)
  assert.ok(res.warningMessage.includes('Communication with another person has been detected'))
})

test('ExternalCommunicationDetector: deduplicates continuous incident and avoids duplicate pop-ups', () => {
  const detector = new ExternalCommunicationDetector({ cooldownMs: 5000 })

  const res1 = detector.evaluate({
    facesDetected: 2,
    isSpeechActive: true,
    currentTranscript: 'Hold on, checking the solution.',
    questionId: 'q1',
  })
  assert.ok(res1 !== null && res1.status === 'active')

  // Immediate second evaluation during same continuous incident
  const res2 = detector.evaluate({
    facesDetected: 2,
    isSpeechActive: true,
    currentTranscript: 'Hold on, checking the solution again.',
    questionId: 'q1',
  })
  assert.ok(res2 !== null)
  assert.equal(res2.isNewIncident, false, 'Subsequent evaluation within same incident is marked isNewIncident: false')
})

test('ExternalCommunicationDetector: resolves incident after return to baseline candidate speech', () => {
  const detector = new ExternalCommunicationDetector({ cooldownMs: 100 })

  const res1 = detector.evaluate({
    facesDetected: 2,
    isSpeechActive: true,
    currentTranscript: 'Checking with someone.',
    questionId: 'q1',
  })
  assert.ok(res1 !== null && res1.status === 'active')

  // Return to normal single candidate speech after quiet transition
  const resResolved = detector.evaluate({
    facesDetected: 1,
    isSpeechActive: false,
    currentTranscript: 'I will now continue independently.',
    questionId: 'q1',
  })

  assert.ok(resResolved !== null, 'Should return resolution transition event')
  assert.equal(resResolved.status, 'resolved')
  assert.equal(resResolved.incidentActive, false)
})

test('FaceVisibilityTracker: temporal window prevents alerts on brief frame blips and confirms sustained anomalies', () => {
  const anomalies = []
  const tracker = new FaceVisibilityTracker({
    sampleIntervalMs: 100,
    absenceThresholdMs: 300,
    multipleThresholdMs: 200,
    recoveryThresholdMs: 200,
    minConfidence: 0.5,
    onAnomaly: (anom) => anomalies.push(anom),
  })

  // 1. Initial valid frame: 1 face
  tracker.processDetectionResult({
    available: true,
    source: 'browser_shape_detector',
    faceCount: 1,
    faces: [{ x: 50, y: 50, width: 40, height: 40, confidence: 0.9 }],
    candidateVisible: true,
    multiplePeople: false,
  })
  assert.equal(anomalies.length, 0, 'Normal 1 face should not trigger anomaly')

  // 2. Brief blip: 100ms without face (< 300ms threshold)
  tracker.processDetectionResult({
    available: true,
    source: 'browser_shape_detector',
    faceCount: 0,
    faces: [],
    candidateVisible: false,
    multiplePeople: false,
  })
  assert.equal(anomalies.length, 0, 'Brief 100ms blip should not trigger absence alert')

  // 3. Sustained absence: 2 more ticks of 100ms (total 300ms >= 300ms)
  tracker.processDetectionResult({
    available: true,
    source: 'browser_shape_detector',
    faceCount: 0,
    faces: [],
    candidateVisible: false,
    multiplePeople: false,
  })
  tracker.processDetectionResult({
    available: true,
    source: 'browser_shape_detector',
    faceCount: 0,
    faces: [],
    candidateVisible: false,
    multiplePeople: false,
  })
  assert.equal(anomalies.length, 1)
  assert.equal(anomalies[0].type, 'face_not_detected')

  // 4. Candidate returns: sustained single face for recovery threshold (200ms = 2 ticks)
  tracker.processDetectionResult({
    available: true,
    source: 'browser_shape_detector',
    faceCount: 1,
    faces: [{ x: 50, y: 50, width: 40, height: 40, confidence: 0.9 }],
    candidateVisible: true,
    multiplePeople: false,
  })
  // After tick 1: still recovering
  assert.equal(anomalies.length, 1)

  // After tick 2: reached 200ms recovery threshold
  tracker.processDetectionResult({
    available: true,
    source: 'browser_shape_detector',
    faceCount: 1,
    faces: [{ x: 50, y: 50, width: 40, height: 40, confidence: 0.9 }],
    candidateVisible: true,
    multiplePeople: false,
  })
  assert.equal(anomalies.length, 2)
  assert.equal(anomalies[1].type, 'candidate_visibility_recovered')

  // 5. Secondary person appears for 200ms (2 ticks of multiple faces)
  tracker.processDetectionResult({
    available: true,
    source: 'browser_shape_detector',
    faceCount: 2,
    faces: [
      { x: 20, y: 50, width: 30, height: 30, confidence: 0.9 },
      { x: 80, y: 50, width: 30, height: 30, confidence: 0.9 },
    ],
    candidateVisible: true,
    multiplePeople: true,
  })
  tracker.processDetectionResult({
    available: true,
    source: 'browser_shape_detector',
    faceCount: 2,
    faces: [
      { x: 20, y: 50, width: 30, height: 30, confidence: 0.9 },
      { x: 80, y: 50, width: 30, height: 30, confidence: 0.9 },
    ],
    candidateVisible: true,
    multiplePeople: true,
  })
  assert.equal(anomalies.length, 3)
  assert.equal(anomalies[2].type, 'multiple_faces_detected')

  // 6. Secondary person leaves -> restores to 1 face for 200ms
  tracker.processDetectionResult({
    available: true,
    source: 'browser_shape_detector',
    faceCount: 1,
    faces: [{ x: 50, y: 50, width: 40, height: 40, confidence: 0.9 }],
    candidateVisible: true,
    multiplePeople: false,
  })
  tracker.processDetectionResult({
    available: true,
    source: 'browser_shape_detector',
    faceCount: 1,
    faces: [{ x: 50, y: 50, width: 40, height: 40, confidence: 0.9 }],
    candidateVisible: true,
    multiplePeople: false,
  })
  assert.equal(anomalies.length, 4)
  assert.equal(anomalies[3].type, 'multiple_faces_resolved')

  // 7. Detector failure reports monitoring limitation, NOT absence
  tracker.processDetectionResult({
    available: false,
    source: 'unavailable',
    faceCount: 0,
    faces: [],
    candidateVisible: false,
    multiplePeople: false,
    errorMessage: 'Camera permission denied or canvas failure',
  })
  assert.equal(anomalies.length, 5)
  assert.equal(anomalies[4].type, 'detector_unavailable')
  assert.notEqual(anomalies[4].type, 'face_not_detected')
})
