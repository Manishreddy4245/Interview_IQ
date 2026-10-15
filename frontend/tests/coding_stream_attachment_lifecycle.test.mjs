import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { isVideoFrameReady, FaceVisibilityTracker } from '../lib/face-detector.ts'

test('Camera Stream Attachment & Playback: Workspace source code guarantees', () => {
  const workspaceSrc = fs.readFileSync(
    path.resolve(process.cwd(), 'components/interviewiq-workspace.tsx'),
    'utf-8',
  )

  // 1. Video playback explicitly handles play promise
  assert.ok(
    workspaceSrc.includes('const playPromise = videoEl.play()') &&
    workspaceSrc.includes('if (playPromise !== undefined) {') &&
    workspaceSrc.includes('await playPromise'),
    'videoEl.play() promise must be explicitly awaited and handled',
  )

  // 2. autoPlay, muted, playsInline are set before/during playback to satisfy browser policies
  assert.ok(
    workspaceSrc.includes('videoEl.muted = true') &&
    workspaceSrc.includes('videoEl.playsInline = true') &&
    workspaceSrc.includes('videoEl.autoplay = true'),
    'videoEl must be configured with muted, playsInline, and autoplay before play()',
  )

  // 3. Callback ref guarantees video attaches whenever mounted in DOM
  assert.ok(
    workspaceSrc.includes('const setVideoRef = useCallback(') &&
    workspaceSrc.includes('ref={setVideoRef}'),
    'Video element in InterviewRoom must use callback ref setVideoRef to ensure attachment on mount',
  )

  // 4. Proctoring Stream Active is displayed ONLY when video frame is active and dimensions are non-zero
  assert.ok(
    workspaceSrc.includes("deviceState === 'ready' && videoFrameActive && !isCameraInterrupted"),
    'Proctoring Stream Active must only be shown when deviceState is ready, videoFrameActive is true, and not interrupted',
  )

  // 5. Distinct initializing state shown while stream frames are rendering
  assert.ok(
    workspaceSrc.includes('Initializing Proctoring Stream...'),
    'Initializing Proctoring Stream indicator must be present for pending or zero-dimension frames',
  )

  // 6. Preflight stream handoff does not stop tracks on InterviewSetup unmount
  assert.ok(
    workspaceSrc.includes('!hasTransferredStreamRef.current'),
    'InterviewSetup unmount cleanup must not terminate tracks when stream has transferred to the room',
  )

  // 7. FaceVisibilityTracker is gated by active video frames and live deviceState
  assert.ok(
    workspaceSrc.includes("!videoRef.current || deviceState !== 'ready' || !videoFrameActive || isCameraInterrupted"),
    'FaceVisibilityTracker must not start or tick on zero-dimension, unready, or interrupted video elements',
  )
})

test('isVideoFrameReady: correctly blocks zero-dimension or paused video elements', () => {
  // Mock element with zero dimensions (like when paused or before first frame renders)
  const blackVideo = {
    readyState: 2, // HAVE_CURRENT_DATA
    videoWidth: 0,
    videoHeight: 0,
    paused: false,
    ended: false,
  }
  assert.equal(isVideoFrameReady(blackVideo), false, '0x0 video element must not be reported as ready frame')

  const pausedVideo = {
    readyState: 4, // HAVE_ENOUGH_DATA
    videoWidth: 640,
    videoHeight: 480,
    paused: true,
    ended: false,
  }
  assert.equal(isVideoFrameReady(pausedVideo), false, 'Paused video must not be reported as ready frame')

  const endedVideo = {
    readyState: 4,
    videoWidth: 640,
    videoHeight: 480,
    paused: false,
    ended: true,
  }
  assert.equal(isVideoFrameReady(endedVideo), false, 'Ended video must not be reported as ready frame')

  const liveVideo = {
    readyState: 4,
    videoWidth: 640,
    videoHeight: 480,
    paused: false,
    ended: false,
  }
  assert.equal(isVideoFrameReady(liveVideo), true, 'Playing video with non-zero dimensions must be reported as ready')
})

test('FaceVisibilityTracker: does not trigger candidate absence on unready video element', async () => {
  const anomalies = []
  const tracker = new FaceVisibilityTracker({
    sampleIntervalMs: 50,
    absenceThresholdMs: 100,
    multipleFaceThresholdMs: 100,
    onAnomaly: (a) => anomalies.push(a),
  })

  // Start with a black/unready video element
  const unreadyVideo = {
    readyState: 0,
    videoWidth: 0,
    videoHeight: 0,
    paused: true,
    ended: false,
  }

  tracker.start(unreadyVideo)
  // Wait longer than absence threshold
  await new Promise((r) => setTimeout(r, 180))
  tracker.stop()

  const absenceAlerts = anomalies.filter((a) => a.type === 'face_not_detected' || a.type === 'candidate_out_of_frame')
  assert.equal(absenceAlerts.length, 0, 'No candidate absence anomaly should be raised while video frame is unready/black')
})
