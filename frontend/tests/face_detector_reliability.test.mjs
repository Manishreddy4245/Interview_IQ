import test from 'node:test'
import assert from 'node:assert/strict'
import {
  detectFacesFromRgba,
  isVideoFrameReady,
  waitForVideoReady,
  detectFacesInFrame,
  runPreflightFaceCheck,
  deduplicateFaces,
  FaceVisibilityTracker,
} from '../lib/face-detector.ts'

// Helper: Synthetic face generator
function createSyntheticFaceBuffer(width, height, faceX, faceY, faceSize, skinType) {
  const data = new Uint8ClampedArray(width * height * 4).fill(210)
  drawSyntheticFaceOn(data, width, height, faceX, faceY, faceSize, skinType)
  return data
}

function drawSyntheticFaceOn(data, width, height, faceX, faceY, faceSize, skinType) {
  const rx = faceSize * 0.44
  const ry = faceSize * 0.58
  const cx = faceX + faceSize / 2
  const cy = faceY + faceSize / 2

  let baseR = 195, baseG = 150, baseB = 120
  if (skinType === 'dark') {
    baseR = 90; baseG = 65; baseB = 50
  } else if (skinType === 'fair') {
    baseR = 235; baseG = 200; baseB = 180
  } else if (skinType === 'grayscale') {
    baseR = 140; baseG = 140; baseB = 140
  }

  for (let y = Math.max(0, Math.floor(cy - ry)); y < Math.min(height, Math.ceil(cy + ry)); y++) {
    for (let x = Math.max(0, Math.floor(cx - rx)); x < Math.min(width, Math.ceil(cx + rx)); x++) {
      const dx = (x - cx) / rx
      const dy = (y - cy) / ry
      if (dx * dx + dy * dy <= 1.0) {
        const idx = (y * width + x) * 4
        data[idx] = baseR
        data[idx + 1] = baseG
        data[idx + 2] = baseB
        data[idx + 3] = 255
      }
    }
  }

  // Draw eye sockets (darker bands)
  const eyeY1 = Math.round(faceY + faceSize * 0.32)
  const eyeY2 = Math.round(faceY + faceSize * 0.44)
  const leftEyeX1 = Math.round(faceX + faceSize * 0.18)
  const leftEyeX2 = Math.round(faceX + faceSize * 0.40)
  const rightEyeX1 = Math.round(faceX + faceSize * 0.60)
  const rightEyeX2 = Math.round(faceX + faceSize * 0.82)

  const eyeDarkness = skinType === 'dark' ? 35 : 45
  for (let y = eyeY1; y <= eyeY2 && y < height; y++) {
    for (let x = leftEyeX1; x <= leftEyeX2 && x < width; x++) {
      const idx = (y * width + x) * 4
      data[idx] = Math.max(0, baseR - eyeDarkness)
      data[idx + 1] = Math.max(0, baseG - eyeDarkness)
      data[idx + 2] = Math.max(0, baseB - eyeDarkness)
    }
    for (let x = rightEyeX1; x <= rightEyeX2 && x < width; x++) {
      const idx = (y * width + x) * 4
      data[idx] = Math.max(0, baseR - eyeDarkness)
      data[idx + 1] = Math.max(0, baseG - eyeDarkness)
      data[idx + 2] = Math.max(0, baseB - eyeDarkness)
    }
  }

  // Draw bright nose bridge
  const noseY1 = Math.round(faceY + faceSize * 0.28)
  const noseY2 = Math.round(faceY + faceSize * 0.58)
  const noseX1 = Math.round(faceX + faceSize * 0.44)
  const noseX2 = Math.round(faceX + faceSize * 0.56)
  for (let y = noseY1; y <= noseY2 && y < height; y++) {
    for (let x = noseX1; x <= noseX2 && x < width; x++) {
      const idx = (y * width + x) * 4
      data[idx] = Math.min(255, baseR + 25)
      data[idx + 1] = Math.min(255, baseG + 25)
      data[idx + 2] = Math.min(255, baseB + 25)
    }
  }

  // Draw bright cheeks
  const cheekY1 = Math.round(faceY + faceSize * 0.50)
  const cheekY2 = Math.round(faceY + faceSize * 0.68)
  for (let y = cheekY1; y <= cheekY2 && y < height; y++) {
    for (let x = leftEyeX1; x <= leftEyeX2 && x < width; x++) {
      const idx = (y * width + x) * 4
      data[idx] = Math.min(255, baseR + 15)
      data[idx + 1] = Math.min(255, baseG + 15)
      data[idx + 2] = Math.min(255, baseB + 15)
    }
    for (let x = rightEyeX1; x <= rightEyeX2 && x < width; x++) {
      const idx = (y * width + x) * 4
      data[idx] = Math.min(255, baseR + 15)
      data[idx + 1] = Math.min(255, baseG + 15)
      data[idx + 2] = Math.min(255, baseB + 15)
    }
  }
}

// Mock video element helper
function createMockVideo({
  videoWidth = 640,
  videoHeight = 480,
  readyState = 4,
  paused = false,
  ended = false,
  faceType = 'medium',
  faceCount = 1,
} = {}) {
  const w = 160
  const h = 120
  let buffer

  if (faceCount === 0) {
    buffer = new Uint8ClampedArray(w * h * 4).fill(210)
  } else if (faceCount === 1) {
    buffer = createSyntheticFaceBuffer(w, h, 45, 18, 65, faceType)
  } else if (faceCount === 2) {
    buffer = new Uint8ClampedArray(w * h * 4).fill(210)
    drawSyntheticFaceOn(buffer, w, h, 8, 22, 50, 'fair')
    drawSyntheticFaceOn(buffer, w, h, 100, 22, 50, 'medium')
  }

  const mockCanvas = {
    width: w,
    height: h,
    getContext: (type) => ({
      drawImage: () => {},
      getImageData: () => ({ data: buffer }),
    }),
  }

  const video = {
    videoWidth,
    videoHeight,
    readyState,
    paused,
    ended,
    srcObject: {},
    _mockCanvas: mockCanvas,
  }

  return { video, mockCanvas }
}

test('detectFacesFromRgba: accurately detects single face with medium skin tone', () => {
  const w = 160, h = 120
  const data = createSyntheticFaceBuffer(w, h, 45, 18, 65, 'medium')
  const result = detectFacesFromRgba(w, h, data)

  assert.equal(result.available, true)
  assert.equal(result.faceCount, 1)
  assert.equal(result.candidateVisible, true)
  assert.equal(result.multiplePeople, false)
  assert.ok(result.faces[0].confidence >= 0.5)
})

test('detectFacesFromRgba: accurately detects single face with dark skin complexion (no skin tone exclusion)', () => {
  const w = 160, h = 120
  const data = createSyntheticFaceBuffer(w, h, 45, 18, 65, 'dark')
  const result = detectFacesFromRgba(w, h, data)

  assert.equal(result.available, true)
  assert.equal(result.faceCount, 1)
  assert.equal(result.candidateVisible, true)
  assert.ok(result.faces[0].confidence >= 0.5)
})

test('detectFacesFromRgba: accurately detects single face in pure grayscale (0 saturation, white balance invariant)', () => {
  const w = 160, h = 120
  const data = createSyntheticFaceBuffer(w, h, 45, 18, 65, 'grayscale')
  const result = detectFacesFromRgba(w, h, data)

  assert.equal(result.available, true)
  assert.equal(result.faceCount, 1)
  assert.equal(result.candidateVisible, true)
  assert.ok(result.faces[0].confidence >= 0.5)
})

test('detectFacesFromRgba: reports 0 faces for empty frame without false positives', () => {
  const w = 160, h = 120
  const emptyData = new Uint8ClampedArray(w * h * 4).fill(190)
  const result = detectFacesFromRgba(w, h, emptyData)

  assert.equal(result.available, true)
  assert.equal(result.faceCount, 0)
  assert.equal(result.candidateVisible, false)
  assert.equal(result.multiplePeople, false)
})

test('detectFacesFromRgba: accurately detects multiple faces (2 people)', () => {
  const w = 160, h = 120
  const multiData = new Uint8ClampedArray(w * h * 4).fill(210)
  drawSyntheticFaceOn(multiData, w, h, 8, 22, 50, 'fair')
  drawSyntheticFaceOn(multiData, w, h, 100, 22, 50, 'medium')
  const result = detectFacesFromRgba(w, h, multiData)

  assert.equal(result.available, true)
  assert.equal(result.faceCount, 2)
  assert.equal(result.candidateVisible, true)
  assert.equal(result.multiplePeople, true)
})

test('deduplicateFaces: suppresses overlapping and nested duplicate bounding boxes for the same face', () => {
  const duplicateBoxes = [
    { box: { x: 50, y: 25, width: 45, height: 55 }, confidence: 0.95 },
    { box: { x: 55, y: 35, width: 35, height: 40 }, confidence: 0.88 },
  ]
  const deduplicated = deduplicateFaces(duplicateBoxes)

  assert.equal(deduplicated.length, 1, 'Overlapping duplicate detections of one face should merge to 1')
  assert.equal(deduplicated[0].confidence, 0.95)
})

test('deduplicateFaces: suppresses vertically aligned anatomical duplicates (eyes vs chin/mouth)', () => {
  const verticalBoxes = [
    { box: { x: 54, y: 20, width: 40, height: 48 }, confidence: 0.94 },
    { box: { x: 56, y: 50, width: 36, height: 44 }, confidence: 0.85 },
  ]
  const deduplicated = deduplicateFaces(verticalBoxes)

  assert.equal(deduplicated.length, 1, 'Vertically stacked sub-face boxes on same person should merge to 1')
})

test('deduplicateFaces: preserves two genuine distinct people in frame', () => {
  const twoPeopleBoxes = [
    { box: { x: 15, y: 25, width: 45, height: 55 }, confidence: 0.95 },
    { box: { x: 100, y: 25, width: 45, height: 55 }, confidence: 0.92 },
  ]
  const deduplicated = deduplicateFaces(twoPeopleBoxes)

  assert.equal(deduplicated.length, 2, 'Two separated individuals must be preserved as 2 distinct faces')
})

test('isVideoFrameReady: correctly evaluates video readiness and dimensions', () => {
  assert.equal(isVideoFrameReady(null), false)
  assert.equal(isVideoFrameReady({ videoWidth: 0, videoHeight: 0, readyState: 0 }), false)
  assert.equal(isVideoFrameReady({ videoWidth: 640, videoHeight: 480, readyState: 1 }), false)
  assert.equal(isVideoFrameReady({ videoWidth: 640, videoHeight: 480, readyState: 2 }), true)
  assert.equal(isVideoFrameReady({ videoWidth: 640, videoHeight: 480, readyState: 4 }), true)
})

test('waitForVideoReady: resolves true when video reaches readyState', async () => {
  const mockVid = { videoWidth: 0, videoHeight: 0, readyState: 0 }
  setTimeout(() => {
    mockVid.videoWidth = 640
    mockVid.videoHeight = 480
    mockVid.readyState = 3
  }, 100)

  const ready = await waitForVideoReady(mockVid, 500)
  assert.equal(ready, true)
})

test('waitForVideoReady: returns false on unready timeout without crashing', async () => {
  const unreadyVid = { videoWidth: 0, videoHeight: 0, readyState: 0 }
  const ready = await waitForVideoReady(unreadyVid, 150)
  assert.equal(ready, false)
})

test('detectFacesInFrame: returns unavailable when video is not ready (prevents false candidate absent)', async () => {
  const unreadyVid = { videoWidth: 0, videoHeight: 0, readyState: 0 }
  const result = await detectFacesInFrame(unreadyVid)

  assert.equal(result.available, false)
  assert.equal(result.source, 'unavailable')
  assert.ok(result.errorMessage.includes('Video stream frames not ready'))
})

test('runPreflightFaceCheck: delayed video initialization reports "initializing", never "Candidate not visible"', async () => {
  const unreadyVid = { videoWidth: 0, videoHeight: 0, readyState: 0 }
  const check = await runPreflightFaceCheck(unreadyVid, 400, 100)

  assert.equal(check.ready, false)
  assert.equal(check.status, 'initializing')
  assert.ok(check.message.includes('initializing'))
  assert.ok(!check.message.includes('Candidate not visible'))
})

test('runPreflightFaceCheck: one visible face passes verification', async () => {
  const { video, mockCanvas } = createMockVideo({ faceCount: 1, faceType: 'medium' })
  globalThis.document = {
    createElement: () => mockCanvas,
  }

  const check = await runPreflightFaceCheck(video, 600, 150)

  assert.equal(check.ready, true)
  assert.equal(check.status, 'verified')
  assert.equal(check.currentFaceCount, 1)
  assert.ok(check.message.includes('verified'))
})

test('runPreflightFaceCheck: no face in frame genuinely reports "no_face"', async () => {
  const { video, mockCanvas } = createMockVideo({ faceCount: 0 })
  globalThis.document = {
    createElement: () => mockCanvas,
  }

  const check = await runPreflightFaceCheck(video, 600, 150)

  assert.equal(check.ready, false)
  assert.equal(check.status, 'no_face')
  assert.equal(check.currentFaceCount, 0)
  assert.ok(check.message.includes('Candidate not visible'))
})

test('runPreflightFaceCheck: two distinct visible faces sustained across frames reports "multiple_faces"', async () => {
  const { video, mockCanvas } = createMockVideo({ faceCount: 2 })
  globalThis.document = {
    createElement: () => mockCanvas,
  }

  const check = await runPreflightFaceCheck(video, 600, 150)

  assert.equal(check.ready, false)
  assert.equal(check.status, 'multiple_faces')
  assert.ok(check.currentFaceCount > 1)
  assert.ok(check.message.includes('Multiple people detected'))
})

test('runPreflightFaceCheck: temporary single-frame fluctuation does NOT trigger false multiple-person warning', async () => {
  let sampleIndex = 0
  const w = 160, h = 120
  const singleFaceBuf = createSyntheticFaceBuffer(w, h, 45, 18, 65, 'medium')
  const multiFaceBuf = new Uint8ClampedArray(w * h * 4).fill(210)
  drawSyntheticFaceOn(multiFaceBuf, w, h, 8, 22, 50, 'fair')
  drawSyntheticFaceOn(multiFaceBuf, w, h, 100, 22, 50, 'medium')

  const fluctuatingCanvas = {
    width: w,
    height: h,
    getContext: () => ({
      drawImage: () => {},
      getImageData: () => {
        // Sample 0: temporary 1-frame multi-face blip
        // Samples 1, 2, 3: consistent 1 face
        const buf = (sampleIndex === 0) ? multiFaceBuf : singleFaceBuf
        sampleIndex++
        return { data: buf }
      },
    }),
  }

  const video = {
    videoWidth: 640,
    videoHeight: 480,
    readyState: 4,
    paused: false,
    ended: false,
    srcObject: {},
  }

  globalThis.document = {
    createElement: () => fluctuatingCanvas,
  }

  const check = await runPreflightFaceCheck(video, 600, 150)

  assert.equal(check.ready, true, 'Temporary fluctuation should stabilize and pass')
  assert.equal(check.status, 'verified', 'Must clear transient multiple-person warning and verify')
  assert.equal(check.currentFaceCount, 1)
})

test('runPreflightFaceCheck: detector error reports appropriate error status', async () => {
  const errorCanvas = {
    width: 160,
    height: 120,
    getContext: () => null, // causes Canvas 2D context creation failed
  }

  const video = {
    videoWidth: 640,
    videoHeight: 480,
    readyState: 4,
    paused: false,
    ended: false,
    srcObject: {},
  }

  globalThis.document = {
    createElement: () => errorCanvas,
  }

  const check = await runPreflightFaceCheck(video, 400, 100)

  assert.equal(check.ready, false)
  assert.equal(check.status, 'error')
  assert.ok(check.message.includes('unavailable') || check.message.includes('failed'))
})
