/**
 * InterviewIQ — Real-Time Face Visibility & Secondary Person Detector
 *
 * Provides:
 * 1. Hardware-accelerated Shape Detection API (window.FaceDetector) where supported,
 *    with robust duplicate detection filtering.
 * 2. High-performance client-side Multi-Scale Integral Anthropometric Cascade Analyzer
 *    for universal browser execution without external dependencies.
 *    (Detects real faces across all complexions, lighting, and grayscale frames).
 * 3. Spatial deduplication to eliminate duplicate detections of the same face (e.g.
 *    face vs landmark boxes, overlapping scale boxes, or chin/mouth fragments).
 * 4. Preflight verification requiring consistent candidate visibility before session start,
 *    with temporal stabilization so temporary single-frame fluctuations do not cause
 *    false "Multiple people detected" warnings.
 * 5. Explicit distinction between "Face detected", "No face detected",
 *    "Detector initializing", and "Detection unavailable/error".
 */

export interface BoundingBox {
  x: number
  y: number
  width: number
  height: number
}

export interface DetectedFace {
  box: BoundingBox
  confidence: number
}

export type FaceDetectionSource =
  | 'shape_detection_api'
  | 'structural_integral_cascade'
  | 'canvas_chroma_cascade'
  | 'browser_shape_detector'
  | 'unavailable'

export interface FaceDetectionResult {
  available: boolean
  source: FaceDetectionSource
  faceCount: number
  facesCount?: number
  faces: DetectedFace[]
  candidateVisible: boolean
  multiplePeople: boolean
  errorMessage?: string
}

export type PreflightStatus = 'verified' | 'no_face' | 'multiple_faces' | 'initializing' | 'error'

export interface PreflightCheckResult {
  ready: boolean
  consecutiveDurationMs: number
  currentFaceCount: number
  source: string
  status: PreflightStatus
  error?: string
  message: string
}

let nativeDetectorInstance: any = null
let nativeDetectorChecked = false

function getNativeDetector(): any | null {
  if (nativeDetectorChecked) return nativeDetectorInstance
  nativeDetectorChecked = true
  if (typeof window !== 'undefined' && 'FaceDetector' in window) {
    try {
      nativeDetectorInstance = new (window as any).FaceDetector({
        fastMode: true,
        maxDetectedFaces: 5,
      })
    } catch {
      nativeDetectorInstance = null
    }
  }
  return nativeDetectorInstance
}

/**
 * Validates whether the given video element has active dimensions and decoded frames.
 */
export function isVideoFrameReady(video: HTMLVideoElement | HTMLCanvasElement): boolean {
  if (!video) return false
  if (typeof HTMLCanvasElement !== 'undefined' && video instanceof HTMLCanvasElement) {
    return video.width > 0 && video.height > 0
  }
  if (typeof HTMLVideoElement !== 'undefined' && video instanceof HTMLVideoElement) {
    const minReady = typeof HTMLMediaElement !== 'undefined' ? (HTMLMediaElement.HAVE_CURRENT_DATA ?? 2) : 2
    return video.videoWidth > 0 && video.videoHeight > 0 && video.readyState >= minReady && !video.paused && !video.ended
  }
  // Generic / mock object support in headless tests
  const anyVid = video as any
  if (anyVid && (anyVid.videoWidth > 0 || anyVid.width > 0)) {
    if (anyVid.paused === true || anyVid.ended === true) return false
    if (typeof anyVid.readyState === 'number') {
      return anyVid.readyState >= 2
    }
    return true
  }
  return false
}

/**
 * Polls until the video element has loaded metadata and begun decoding frames.
 */
export async function waitForVideoReady(
  video: HTMLVideoElement | HTMLCanvasElement,
  timeoutMs = 3000,
): Promise<boolean> {
  const startTime = Date.now()
  while (Date.now() - startTime < timeoutMs) {
    if (isVideoFrameReady(video)) return true
    await new Promise((r) => setTimeout(r, 60))
  }
  return isVideoFrameReady(video)
}

/**
 * Spatial deduplication to merge multiple bounding boxes representing the same face.
 * Handles:
 * 1. Overlapping scale boxes (IoU >= 0.15 or IoM >= 0.25).
 * 2. Nested / close-center boxes (center distance < 0.85 * max dimension).
 * 3. Vertical anatomical alignment on the same individual (eyes + mouth/chin/beard).
 * 4. Center containment (one box's center inside the other).
 * 5. Eliminates weak secondary detections when a strong primary face is present.
 */
export function deduplicateFaces(faces: DetectedFace[]): DetectedFace[] {
  if (!faces || faces.length <= 1) return faces || []

  // Sort by confidence descending, then by area descending
  const sorted = [...faces].sort((a, b) => {
    if (Math.abs(b.confidence - a.confidence) > 0.05) {
      return b.confidence - a.confidence
    }
    return (b.box.width * b.box.height) - (a.box.width * a.box.height)
  })

  const unique: DetectedFace[] = []
  const remaining = [...sorted]

  while (remaining.length > 0) {
    const best = remaining.shift()!
    unique.push(best)

    const bBox = best.box
    const bCx = bBox.x + bBox.width / 2
    const bCy = bBox.y + bBox.height / 2
    const bDim = Math.max(bBox.width, bBox.height)

    for (let i = remaining.length - 1; i >= 0; i--) {
      const cur = remaining[i]
      const cBox = cur.box
      const cCx = cBox.x + cBox.width / 2
      const cCy = cBox.y + cBox.height / 2
      const cDim = Math.max(cBox.width, cBox.height)

      const dist = Math.hypot(bCx - cCx, bCy - cCy)

      const interW = Math.max(0, Math.min(bBox.x + bBox.width, cBox.x + cBox.width) - Math.max(bBox.x, cBox.x))
      const interH = Math.max(0, Math.min(bBox.y + bBox.height, cBox.y + cBox.height) - Math.max(bBox.y, cBox.y))
      const interArea = interW * interH
      const minArea = Math.min(bBox.width * bBox.height, cBox.width * cBox.height)
      const iom = minArea > 0 ? interArea / minArea : 0
      const unionArea = bBox.width * bBox.height + cBox.width * cBox.height - interArea
      const iou = unionArea > 0 ? interArea / unionArea : 0

      // Condition 1: Direct geometric overlap (IoU >= 0.15 or IoM >= 0.25)
      const hasOverlap = iou >= 0.15 || iom >= 0.25

      // Condition 2: Centers within face radius
      const isClose = dist < Math.max(bDim, cDim) * 0.85

      // Condition 3: Vertical anatomical alignment on same person (head / face / chin)
      const xDiff = Math.abs(bCx - cCx)
      const yDiff = Math.abs(bCy - cCy)
      const isVerticallyAligned = xDiff < Math.min(bBox.width, cBox.width) * 0.55 &&
                                  yDiff < Math.max(bBox.height, cBox.height) * 1.25

      // Condition 4: One box center falls inside the other
      const bContainsC = cCx >= bBox.x && cCx <= bBox.x + bBox.width &&
                         cCy >= bBox.y && cCy <= bBox.y + bBox.height
      const cContainsB = bCx >= cBox.x && bCx <= cBox.x + cBox.width &&
                         bCy >= cBox.y && bCy <= cBox.y + cBox.height

      if (hasOverlap || isClose || isVerticallyAligned || bContainsC || cContainsB) {
        remaining.splice(i, 1)
      }
    }
  }

  // Filter out weak secondary detections when a strong primary face is present
  if (unique.length > 1) {
    const maxConf = Math.max(...unique.map((f) => f.confidence))
    if (maxConf >= 0.90) {
      return unique.filter((f) => f.confidence >= 0.80)
    }
  }

  return unique
}

/**
 * Integral-Image Anthropometric Haar & Structural Face Detector
 * Operates on downscaled grayscale luma with integral representations (SAT & SAT^2).
 * Robust across skin complexions, camera white-balance shifts, and lighting variations.
 */
export function detectFacesFromRgba(
  width: number,
  height: number,
  data: Uint8ClampedArray | Uint8Array,
  options: { minConfidence?: number } = {},
): FaceDetectionResult {
  const minConfidence = options.minConfidence || 0.48
  if (!width || !height || width < 20 || height < 20 || !data || data.length < width * height * 4) {
    return {
      available: false,
      source: 'unavailable',
      faceCount: 0,
      facesCount: 0,
      faces: [],
      candidateVisible: false,
      multiplePeople: false,
      errorMessage: 'Frame dimensions or image buffer invalid.',
    }
  }

  // 1. Build Grayscale Luma map
  const gray = new Float32Array(width * height)
  for (let i = 0; i < width * height; i++) {
    const idx = i * 4
    gray[i] = 0.299 * data[idx] + 0.587 * data[idx + 1] + 0.114 * data[idx + 2]
  }

  // 2. Build Integral Image (SAT) and Squared Integral Image (SAT^2)
  const stride = width + 1
  const sat = new Float64Array((width + 1) * (height + 1))
  const satSq = new Float64Array((width + 1) * (height + 1))

  for (let y = 0; y < height; y++) {
    let rowSum = 0
    let rowSumSq = 0
    const rowOffset = y * width
    const satOffset = (y + 1) * stride
    const satPrevOffset = y * stride

    for (let x = 0; x < width; x++) {
      const val = gray[rowOffset + x]
      rowSum += val
      rowSumSq += val * val
      sat[satOffset + x + 1] = sat[satPrevOffset + x + 1] + rowSum
      satSq[satOffset + x + 1] = satSq[satPrevOffset + x + 1] + rowSumSq
    }
  }

  function rectMean(x1: number, y1: number, x2: number, y2: number): number {
    x1 = Math.max(0, Math.min(width, Math.round(x1)))
    x2 = Math.max(0, Math.min(width, Math.round(x2)))
    y1 = Math.max(0, Math.min(height, Math.round(y1)))
    y2 = Math.max(0, Math.min(height, Math.round(y2)))
    const area = (x2 - x1) * (y2 - y1)
    if (area <= 0) return 0
    const s = sat[y2 * stride + x2] - sat[y1 * stride + x2] - sat[y2 * stride + x1] + sat[y1 * stride + x1]
    return s / area
  }

  function rectStdDev(x1: number, y1: number, x2: number, y2: number, mean: number): number {
    x1 = Math.max(0, Math.min(width, Math.round(x1)))
    x2 = Math.max(0, Math.min(width, Math.round(x2)))
    y1 = Math.max(0, Math.min(height, Math.round(y1)))
    y2 = Math.max(0, Math.min(height, Math.round(y2)))
    const area = (x2 - x1) * (y2 - y1)
    if (area <= 1) return 1
    const sSq = satSq[y2 * stride + x2] - satSq[y1 * stride + x2] - satSq[y2 * stride + x1] + satSq[y1 * stride + x1]
    const variance = (sSq / area) - (mean * mean)
    return Math.sqrt(Math.max(0, variance))
  }

  // 3. Multi-Scale Sliding Window Cascade Evaluation
  const candidateDetections: DetectedFace[] = []

  const minDim = Math.min(width, height)
  const windowScales = [0.28, 0.38, 0.50, 0.65, 0.80]

  for (const scale of windowScales) {
    const boxW = Math.round(minDim * scale)
    const boxH = Math.round(boxW * 1.25)
    if (boxW > width || boxH > height) continue

    const stepX = Math.max(6, Math.round(boxW * 0.12))
    const stepY = Math.max(6, Math.round(boxH * 0.12))

    for (let y = 0; y <= height - boxH; y += stepY) {
      for (let x = 0; x <= width - boxW; x += stepX) {
        const mean = rectMean(x, y, x + boxW, y + boxH)
        const std = rectStdDev(x, y, x + boxW, y + boxH, mean)

        // Stage 1: Reject uniform, solid or flat background
        if (std < 8.0) continue

        // Stage 2: Forehead vs Eye band contrast (Classic Haar 1: Forehead is brighter than eye band)
        const foreheadMean = rectMean(x + boxW * 0.15, y + boxH * 0.05, x + boxW * 0.85, y + boxH * 0.22)
        const eyeBandMean = rectMean(x + boxW * 0.12, y + boxH * 0.25, x + boxW * 0.88, y + boxH * 0.45)
        const eyeForeheadDiff = foreheadMean - eyeBandMean
        if (eyeForeheadDiff < 1.0) continue

        // Stage 3: Cheeks vs Eye band contrast
        const cheekMean = rectMean(x + boxW * 0.15, y + boxH * 0.48, x + boxW * 0.85, y + boxH * 0.70)
        const eyeCheekDiff = cheekMean - eyeBandMean
        if (eyeCheekDiff < -1.0) continue

        // Stage 4: Central Nose Bridge vs Left & Right Eye Sockets
        const noseMean = rectMean(x + boxW * 0.38, y + boxH * 0.26, x + boxW * 0.62, y + boxH * 0.62)
        const leftEyeMean = rectMean(x + boxW * 0.12, y + boxH * 0.26, x + boxW * 0.38, y + boxH * 0.46)
        const rightEyeMean = rectMean(x + boxW * 0.62, y + boxH * 0.26, x + boxW * 0.88, y + boxH * 0.46)
        const noseEyeDiff = noseMean - (leftEyeMean + rightEyeMean) / 2
        if (noseMean < leftEyeMean + 2 || noseMean < rightEyeMean + 2) continue

        // Stage 5: Bilateral Eye Socket Balance
        const eyeDiff = Math.abs(leftEyeMean - rightEyeMean)
        const eyeDiffRatio = eyeDiff / (std + 1)
        if (eyeDiffRatio > 0.65 || eyeDiff > 18.0) continue

        // Stage 6: Combined Structural Anthropometric Score
        const sEyeForehead = Math.max(-0.5, Math.min(1.5, eyeForeheadDiff / (std * 0.35 + 1)))
        const sEyeCheek = Math.max(-0.5, Math.min(1.5, eyeCheekDiff / (std * 0.35 + 1)))
        const sNoseEye = Math.max(-0.5, Math.min(1.5, noseEyeDiff / (std * 0.35 + 1)))
        const sSymmetry = 1.0 - Math.min(1.0, eyeDiffRatio / 0.6)

        const structuralScore = (sEyeForehead * 0.35) + (sEyeCheek * 0.25) + (sNoseEye * 0.25) + (sSymmetry * 0.15)

        if (structuralScore >= 0.20 && (eyeForeheadDiff >= 3.0 || noseEyeDiff >= 3.0) && (eyeForeheadDiff + noseEyeDiff >= 7.0)) {
          let skinBonus = 0
          const sampleCx = Math.round(x + boxW / 2)
          const sampleCy = Math.round(y + boxH * 0.4)
          const pIdx = (sampleCy * width + sampleCx) * 4
          const r = data[pIdx]
          const g = data[pIdx + 1]
          const b = data[pIdx + 2]
          const cb = 128 - 0.168736 * r - 0.331264 * g + 0.5 * b
          const cr = 128 + 0.5 * r - 0.418688 * g - 0.081312 * b
          if (cb >= 70 && cb <= 135 && cr >= 125 && cr <= 180) {
            skinBonus = 0.12
          }

          const confidence = Math.min(0.99, Math.max(0.40, 0.45 + structuralScore * 0.40 + skinBonus))
          if (confidence >= minConfidence) {
            candidateDetections.push({
              box: { x, y, width: boxW, height: boxH },
              confidence: Math.round(confidence * 100) / 100,
            })
          }
        }
      }
    }
  }

  // 4. Deduplicate and suppress overlapping / stacked boxes
  const deduplicated = deduplicateFaces(candidateDetections)
  const faceCount = deduplicated.length

  return {
    available: true,
    source: 'structural_integral_cascade',
    faceCount,
    facesCount: faceCount,
    faces: deduplicated,
    candidateVisible: faceCount >= 1,
    multiplePeople: faceCount > 1,
  }
}

/**
 * Universal client-side Canvas Frame Analyzer.
 * Operates on downscaled canvas frames (160x120) with sub-5ms execution time.
 */
function analyzeFrameWithCanvas(
  video: HTMLVideoElement | HTMLCanvasElement,
  offscreenCanvas?: HTMLCanvasElement,
): FaceDetectionResult {
  try {
    const targetW = 160
    const targetH = 120

    let canvas = offscreenCanvas
    if (!canvas || typeof canvas.getContext !== 'function') {
      if (typeof document !== 'undefined') {
        canvas = document.createElement('canvas')
      } else {
        return {
          available: false,
          source: 'unavailable',
          faceCount: 0,
          facesCount: 0,
          faces: [],
          candidateVisible: false,
          multiplePeople: false,
          errorMessage: 'Canvas element not available in execution environment.',
        }
      }
    }

    canvas.width = targetW
    canvas.height = targetH
    const ctx = canvas.getContext('2d', { willReadFrequently: true })
    if (!ctx) {
      return {
        available: false,
        source: 'unavailable',
        faceCount: 0,
        facesCount: 0,
        faces: [],
        candidateVisible: false,
        multiplePeople: false,
        errorMessage: 'Canvas 2D context creation failed.',
      }
    }

    ctx.drawImage(video as any, 0, 0, targetW, targetH)
    const imgData = ctx.getImageData(0, 0, targetW, targetH)

    return detectFacesFromRgba(targetW, targetH, imgData.data)
  } catch (err: unknown) {
    return {
      available: false,
      source: 'unavailable',
      faceCount: 0,
      facesCount: 0,
      faces: [],
      candidateVisible: false,
      multiplePeople: false,
      errorMessage: err instanceof Error ? err.message : 'Canvas frame analysis failed.',
    }
  }
}

/**
 * Detect faces in an active video or canvas element.
 * Prioritizes window.FaceDetector (Shape Detection API) with fallback to Structural Cascade,
 * ensuring deduplication is applied to both sources.
 */
export async function detectFacesInFrame(
  video: HTMLVideoElement | HTMLCanvasElement,
  offscreenCanvas?: HTMLCanvasElement,
): Promise<FaceDetectionResult> {
  // Guard against unready video element
  if (!isVideoFrameReady(video)) {
    return {
      available: false,
      source: 'unavailable',
      faceCount: 0,
      facesCount: 0,
      faces: [],
      candidateVisible: false,
      multiplePeople: false,
      errorMessage: 'Video stream frames not ready (videoWidth/Height is zero or readyState < 2).',
    }
  }

  const nativeDetector = getNativeDetector()
  if (nativeDetector) {
    try {
      const rawFaces: any[] = await nativeDetector.detect(video)
      const mappedFaces: DetectedFace[] = rawFaces.map((f: any) => ({
        box: {
          x: Math.round(f.boundingBox.x),
          y: Math.round(f.boundingBox.y),
          width: Math.round(f.boundingBox.width),
          height: Math.round(f.boundingBox.height),
        },
        confidence: 0.95,
      }))
      // Filter out duplicate bounding boxes for the same face
      const faces = deduplicateFaces(mappedFaces)
      const count = faces.length
      return {
        available: true,
        source: 'shape_detection_api',
        faceCount: count,
        facesCount: count,
        faces,
        candidateVisible: count >= 1,
        multiplePeople: count > 1,
      }
    } catch {
      // Native detector failed; fallback to structural cascade analyzer
    }
  }

  // Universal Structural Cascade Analyzer
  return analyzeFrameWithCanvas(video, offscreenCanvas)
}

/**
 * Preflight Candidate Visibility Check with Temporal Stabilization.
 * Requires consistent single-face detection to verify readiness.
 * Applies temporal stabilization: brief/isolated detection fluctuations do NOT trigger
 * false "multiple people" warnings. Multiple distinct faces must be sustained across
 * consecutive frames to trigger an alert.
 */
export async function runPreflightFaceCheck(
  video: HTMLVideoElement,
  requiredDurationMs = 1500,
  sampleIntervalMs = 300,
): Promise<PreflightCheckResult> {
  // 1. Ensure video frames are ready
  const isReady = await waitForVideoReady(video, 3000)
  if (!isReady) {
    return {
      ready: false,
      consecutiveDurationMs: 0,
      currentFaceCount: 0,
      source: 'unavailable',
      status: 'initializing',
      error: 'Camera video stream is still initializing frames.',
      message: 'Camera video frames are still initializing. Please wait a moment...',
    }
  }

  const samplesRequired = Math.max(3, Math.ceil(requiredDurationMs / sampleIntervalMs))
  const maxSamples = samplesRequired + 3 // Allow up to 3 extra samples to stabilize brief fluctuations

  let consecutiveSingleSamples = 0
  let consecutiveMultipleSamples = 0
  let consecutiveZeroSamples = 0
  let lastFaceCount = 0
  let detectionSource = 'unavailable'
  let errorEncountered: string | null = null

  for (let i = 0; i < maxSamples; i++) {
    const result = await detectFacesInFrame(video)
    detectionSource = result.source
    lastFaceCount = result.faceCount

    if (!result.available) {
      errorEncountered = result.errorMessage || 'Face detection service unavailable.'
      if (!isVideoFrameReady(video)) {
        return {
          ready: false,
          consecutiveDurationMs: 0,
          currentFaceCount: 0,
          source: result.source,
          status: 'initializing',
          error: 'Video stream paused or frames not decoding.',
          message: 'Camera video frames are still initializing...',
        }
      }
      consecutiveSingleSamples = 0
      consecutiveMultipleSamples = 0
    } else if (result.faceCount === 1) {
      consecutiveSingleSamples++
      consecutiveMultipleSamples = 0
      consecutiveZeroSamples = 0
    } else if (result.faceCount > 1) {
      consecutiveMultipleSamples++
      consecutiveSingleSamples = 0
      consecutiveZeroSamples = 0
    } else {
      consecutiveZeroSamples++
      consecutiveSingleSamples = 0
      consecutiveMultipleSamples = 0
    }

    // Condition A: Confirmed single candidate face across 3 consecutive valid samples
    if (consecutiveSingleSamples >= 3) {
      return {
        ready: true,
        consecutiveDurationMs: consecutiveSingleSamples * sampleIntervalMs,
        currentFaceCount: 1,
        source: detectionSource,
        status: 'verified',
        message: 'Candidate visibility verified: 1 face confirmed consistently. Camera ready.',
      }
    }

    // Condition B: Multiple distinct people confirmed across 3 consecutive samples (sustained presence)
    if (consecutiveMultipleSamples >= 3) {
      return {
        ready: false,
        consecutiveDurationMs: 0,
        currentFaceCount: lastFaceCount,
        source: detectionSource,
        status: 'multiple_faces',
        message: 'Multiple people detected — only the candidate should be visible during this interview.',
      }
    }

    if (i < maxSamples - 1) {
      await new Promise((r) => setTimeout(r, sampleIntervalMs))
    }
  }

  // After loop, evaluate stabilized terminal state:
  if (consecutiveSingleSamples >= 2) {
    return {
      ready: true,
      consecutiveDurationMs: consecutiveSingleSamples * sampleIntervalMs,
      currentFaceCount: 1,
      source: detectionSource,
      status: 'verified',
      message: 'Candidate visibility verified: 1 face confirmed consistently.',
    }
  }

  if (consecutiveMultipleSamples >= 2) {
    return {
      ready: false,
      consecutiveDurationMs: 0,
      currentFaceCount: lastFaceCount,
      source: detectionSource,
      status: 'multiple_faces',
      message: 'Multiple people detected — only the candidate should be visible during this interview.',
    }
  }

  if (errorEncountered && consecutiveZeroSamples === 0) {
    return {
      ready: false,
      consecutiveDurationMs: 0,
      currentFaceCount: 0,
      source: detectionSource,
      status: 'error',
      error: errorEncountered,
      message: `Detection unavailable: ${errorEncountered}`,
    }
  }

  return {
    ready: false,
    consecutiveDurationMs: 0,
    currentFaceCount: lastFaceCount,
    source: detectionSource,
    status: 'no_face',
    message: 'Candidate not visible — please position your face directly in the camera frame and re-run check.',
  }
}

/**
 * Sliding Window Visibility & Secondary Person Tracker.
 * Debounces frame-level detections over time to prevent false alerts.
 */
export interface TrackerConfig {
  sampleIntervalMs?: number // Default: 800ms
  absenceThresholdMs?: number // Default: 5000ms (5s of sustained missing face)
  multipleThresholdMs?: number // Default: 2500ms (2.5s of sustained secondary person)
  multipleFaceThresholdMs?: number // Alias
  recoveryThresholdMs?: number // Default: 2000ms (2s of sustained single face)
  minConfidence?: number
  onAbsenceWarning?: (active: boolean, durationSec: number) => void
  onMultiplePeopleWarning?: (active: boolean, count: number, durationSec: number) => void
  onDetectorFailure?: (message: string) => void
  onAnomaly?: (anomaly: {
    type: 'face_not_detected' | 'candidate_out_of_frame' | 'candidate_visibility_recovered' | 'multiple_faces_detected' | 'multiple_faces_resolved' | 'detector_unavailable'
    duration?: number
    confidence?: number
    details?: any
  }) => void
  onFaceStatusChange?: (result: FaceDetectionResult) => void
}

export class FaceVisibilityTracker {
  public config: Required<TrackerConfig>
  private timerId: any = null
  private videoElement: HTMLVideoElement | null = null
  private offscreenCanvas: HTMLCanvasElement

  private consecutiveAbsentMs = 0
  private consecutiveMultipleMs = 0
  private consecutiveSingleMs = 0

  public isAbsentAlertActive = false
  public isMultipleAlertActive = false
  private lastMultipleCount = 2

  private absenceStartTime: number | null = null
  private multipleStartTime: number | null = null

  constructor(config?: TrackerConfig) {
    const multipleThresh = config?.multipleFaceThresholdMs || config?.multipleThresholdMs || 2500
    this.config = {
      sampleIntervalMs: config?.sampleIntervalMs || 800,
      absenceThresholdMs: config?.absenceThresholdMs || 5000,
      multipleThresholdMs: multipleThresh,
      multipleFaceThresholdMs: multipleThresh,
      recoveryThresholdMs: config?.recoveryThresholdMs || 2000,
      minConfidence: config?.minConfidence || 0.5,
      onAbsenceWarning: config?.onAbsenceWarning || (() => {}),
      onMultiplePeopleWarning: config?.onMultiplePeopleWarning || (() => {}),
      onDetectorFailure: config?.onDetectorFailure || (() => {}),
      onAnomaly: config?.onAnomaly || (() => {}),
      onFaceStatusChange: config?.onFaceStatusChange || (() => {}),
    }
    this.offscreenCanvas = typeof document !== 'undefined' ? document.createElement('canvas') : ({} as any)
  }

  public start(video: HTMLVideoElement) {
    this.stop()
    this.videoElement = video
    this.timerId = setInterval(this.tick.bind(this), this.config.sampleIntervalMs)
  }

  public stop() {
    if (this.timerId !== null) {
      clearInterval(this.timerId)
      this.timerId = null
    }
    this.reset()
  }

  public reset() {
    this.consecutiveAbsentMs = 0
    this.consecutiveMultipleMs = 0
    this.consecutiveSingleMs = 0
    this.isAbsentAlertActive = false
    this.isMultipleAlertActive = false
    this.absenceStartTime = null
    this.multipleStartTime = null
  }

  public processDetectionResult(result: FaceDetectionResult) {
    this.config.onFaceStatusChange(result)

    if (!result.available) {
      this.config.onDetectorFailure(result.errorMessage || 'Detection service unavailable')
      this.config.onAnomaly({
        type: 'detector_unavailable',
        details: { reason: result.errorMessage, source: result.source },
      })
      return
    }

    const dt = this.config.sampleIntervalMs

    // Scenario A: No face detected (0 faces)
    if (result.faceCount === 0) {
      this.consecutiveAbsentMs += dt
      this.consecutiveMultipleMs = 0
      this.consecutiveSingleMs = 0

      if (this.absenceStartTime === null) {
        this.absenceStartTime = Date.now()
      }

      if (this.consecutiveAbsentMs >= this.config.absenceThresholdMs && !this.isAbsentAlertActive) {
        this.isAbsentAlertActive = true
        const durationSec = Math.round((Date.now() - this.absenceStartTime) / 1000)
        this.config.onAbsenceWarning(true, durationSec)
        this.config.onAnomaly({
          type: 'face_not_detected',
          duration: durationSec,
          confidence: 0.9,
          details: { source: result.source },
        })
      }

      if (this.isMultipleAlertActive) {
        this.isMultipleAlertActive = false
        const durationSec = this.multipleStartTime ? Math.round((Date.now() - this.multipleStartTime) / 1000) : 0
        this.config.onMultiplePeopleWarning(false, 0, durationSec)
        this.config.onAnomaly({
          type: 'multiple_faces_resolved',
          duration: durationSec,
        })
        this.multipleStartTime = null
      }
    }
    // Scenario B: Exactly 1 face detected (Expected Baseline)
    else if (result.faceCount === 1) {
      this.consecutiveSingleMs += dt
      this.consecutiveAbsentMs = 0
      this.consecutiveMultipleMs = 0

      if (this.isAbsentAlertActive && this.consecutiveSingleMs >= this.config.recoveryThresholdMs) {
        this.isAbsentAlertActive = false
        const durationSec = this.absenceStartTime ? Math.round((Date.now() - this.absenceStartTime) / 1000) : 0
        this.config.onAbsenceWarning(false, durationSec)
        this.config.onAnomaly({
          type: 'candidate_visibility_recovered',
          duration: durationSec,
        })
        this.absenceStartTime = null
      }

      if (this.isMultipleAlertActive && this.consecutiveSingleMs >= this.config.recoveryThresholdMs) {
        this.isMultipleAlertActive = false
        const durationSec = this.multipleStartTime ? Math.round((Date.now() - this.multipleStartTime) / 1000) : 0
        this.config.onMultiplePeopleWarning(false, 1, durationSec)
        this.config.onAnomaly({
          type: 'multiple_faces_resolved',
          duration: durationSec,
        })
        this.multipleStartTime = null
      }
    }
    // Scenario C: Multiple faces detected (> 1 faces)
    else if (result.faceCount > 1) {
      this.consecutiveMultipleMs += dt
      this.consecutiveAbsentMs = 0
      this.consecutiveSingleMs = 0
      this.lastMultipleCount = result.faceCount

      if (this.multipleStartTime === null) {
        this.multipleStartTime = Date.now()
      }

      if (this.isAbsentAlertActive) {
        this.isAbsentAlertActive = false
        const durationSec = this.absenceStartTime ? Math.round((Date.now() - this.absenceStartTime) / 1000) : 0
        this.config.onAbsenceWarning(false, durationSec)
        this.config.onAnomaly({
          type: 'candidate_visibility_recovered',
          duration: durationSec,
        })
        this.absenceStartTime = null
      }

      if (this.consecutiveMultipleMs >= this.config.multipleThresholdMs && !this.isMultipleAlertActive) {
        this.isMultipleAlertActive = true
        const durationSec = Math.round((Date.now() - this.multipleStartTime) / 1000)
        this.config.onMultiplePeopleWarning(true, result.faceCount, durationSec)
        this.config.onAnomaly({
          type: 'multiple_faces_detected',
          duration: durationSec,
          confidence: 0.88,
          details: { count: result.faceCount, source: result.source },
        })
      }
    }
  }

  private async tick() {
    if (!this.videoElement) return
    if (this.videoElement.paused || this.videoElement.ended || !this.videoElement.srcObject) return
    if (!isVideoFrameReady(this.videoElement)) return

    const result = await detectFacesInFrame(this.videoElement, this.offscreenCanvas)
    this.processDetectionResult(result)
  }
}
