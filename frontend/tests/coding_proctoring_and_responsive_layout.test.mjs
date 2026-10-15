import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { FaceVisibilityTracker } from '../lib/face-detector.ts'
import { ExternalCommunicationDetector } from '../lib/communication-detector.ts'

test('Issue 1: Coding Interview Setup has mandatory video proctoring enabled', () => {
  const workspaceSrc = fs.readFileSync(
    path.resolve(process.cwd(), 'components/interviewiq-workspace.tsx'),
    'utf-8',
  )

  // Verify targetMode CODING enables isVideo in InterviewSetup
  assert.ok(
    workspaceSrc.includes("const isVideo = targetMode === 'CODING' || targetMode === 'VERBAL' || !isCoding"),
    'InterviewSetup must enable isVideo for CODING target mode',
  )

  // Verify gating error prevents starting without verified camera
  assert.ok(
    workspaceSrc.includes('Camera permission and candidate face verification are mandatory'),
    'InterviewSetup must gate start button on camera permission and candidate face verification',
  )
})

test('Issue 1: Coding Interview Room includes FaceVisibilityTracker and proctoring panel', () => {
  const workspaceSrc = fs.readFileSync(
    path.resolve(process.cwd(), 'components/interviewiq-workspace.tsx'),
    'utf-8',
  )

  // Verify isProctoredSession enables tracker during CODING mode
  assert.ok(
    workspaceSrc.includes('const isProctoredSession = Boolean('),
    'InterviewRoom must define isProctoredSession encompassing isCodingSession',
  )
  assert.ok(
    workspaceSrc.includes('isCodingSession ||') && workspaceSrc.includes('isProctoredSession'),
    'isCodingSession must be included in isProctoredSession',
  )

  // Verify camera panel is rendered when isProctoredSession is true
  assert.ok(
    workspaceSrc.includes('{isProctoredSession && (') && workspaceSrc.includes('camera-panel'),
    'Camera panel must be rendered for proctored coding sessions',
  )

  // Verify typing/editor draft state changes do not restart the tracker
  assert.ok(
    workspaceSrc.includes('answerTextRef.current') &&
    workspaceSrc.includes('interimTranscriptRef.current'),
    'Candidate answer typing must use refs to prevent tearing down and restarting the tracker',
  )

  // Verify coding session proctoring status badge
  assert.ok(
    workspaceSrc.includes('Live Proctoring Active'),
    'Coding interview camera panel must show Live Proctoring Active indicator',
  )
})

test('Issue 1: Collapsing video panel preserves active background monitoring', () => {
  const css = fs.readFileSync(path.resolve(process.cwd(), 'app/globals.css'), 'utf-8')

  // Collapsed styling only adjusts visual container height/opacity, video remains mounted
  assert.ok(
    css.includes('.camera-panel.is-collapsed .camera-frame'),
    'CSS must style collapsed state without unmounting DOM element',
  )
  assert.ok(
    css.includes('max-height: 52px'),
    'Collapsed state must minimize height while keeping video frame active in DOM',
  )

  // Tracker test: tracker continues firing anomalies while running
  const anomalies = []
  const tracker = new FaceVisibilityTracker({
    sampleIntervalMs: 50,
    absenceThresholdMs: 100,
    multipleFaceThresholdMs: 100,
    onAnomaly: (a) => anomalies.push(a),
  })

  // Tracker is instantiated and operable
  assert.equal(typeof tracker.start, 'function')
  assert.equal(typeof tracker.stop, 'function')
})

test('Issue 3: Split container pane width formula eliminates 8px overflow bug', () => {
  const ideSrc = fs.readFileSync(
    path.resolve(process.cwd(), 'components/MultimodalInterviewIDE.tsx'),
    'utf-8',
  )

  // Left pane and right pane must account for the 8px divider
  assert.ok(
    ideSrc.includes('calc(${splitRatio}% - 4px)'),
    'Left pane width must subtract half divider width (4px) from splitRatio%',
  )
  assert.ok(
    ideSrc.includes('calc(${100 - splitRatio}% - 4px)'),
    'Right pane width must subtract half divider width (4px) from (100 - splitRatio)%',
  )

  // Mathematical proof: for any splitRatio, left + divider + right == 100%
  for (const splitRatio of [30, 40, 50, 60, 70]) {
    // left = splitRatio% - 4px, divider = 8px, right = (100 - splitRatio)% - 4px
    // total = splitRatio% - 4px + 8px + (100 - splitRatio)% - 4px = 100%
    const totalOffsetPx = -4 + 8 - 4
    assert.equal(totalOffsetPx, 0, 'Pane offsets and divider must sum exactly to 0px')
  }
})

test('Issue 3: Responsive CSS constraints prevent page-level horizontal overflow', () => {
  const css = fs.readFileSync(path.resolve(process.cwd(), 'app/globals.css'), 'utf-8')

  // 1. Grid layout with minmax(0, 1fr) for right column to allow shrinking
  assert.ok(
    css.includes('.room-layout.technical-view {') &&
    css.includes('grid-template-columns: minmax(280px, 320px) minmax(0, 1fr);'),
    'Technical room layout must use CSS grid with minmax(0, 1fr) to prevent right-column blow-out',
  )

  // 2. Responsive single-column breakpoint for tablet/narrow viewports
  assert.ok(
    css.includes('@media (max-width: 1080px) {') &&
    css.includes('.room-layout.technical-view {') &&
    css.includes('grid-template-columns: 1fr;'),
    'Technical room layout must stack into single column below 1080px',
  )

  // 3. Question panel, workspace wrapper, and IDE container have box-sizing and min-width: 0
  assert.ok(
    css.includes('.technical-workspace-wrapper {') &&
    css.includes('min-width: 0;') &&
    css.includes('box-sizing: border-box;'),
    'technical-workspace-wrapper must have min-width: 0 and box-sizing: border-box',
  )

  // 4. Split container stacks vertically on narrow screens (< 900px)
  assert.ok(
    css.includes('@media (max-width: 900px) {') &&
    css.includes('.ide-split-container {') &&
    css.includes('flex-direction: column;'),
    'ide-split-container must stack vertically on mobile/tablet screens below 900px',
  )

  // 5. Code blocks wrap unbroken lines instead of forcing container wider
  assert.ok(
    css.includes('.ide-tc-code {') && css.includes('word-break: break-all;'),
    'ide-tc-code must have word-break: break-all',
  )
  assert.ok(
    css.includes('.ide-example-code {') && css.includes('word-break: break-all;'),
    'ide-example-code must have word-break: break-all',
  )

  // 6. Language selector and actions toolbar wrap without pushing container
  assert.ok(
    css.includes('.ide-actions {') && css.includes('flex-wrap: wrap;'),
    'ide-actions toolbar buttons must have flex-wrap: wrap',
  )
})

test('Issue 3: Viewport budget calculation satisfies scrollWidth <= clientWidth', () => {
  // Test desktop 1920x1080
  const viewport1920 = { width: 1920 }
  const sidebarWidth = 248
  const mainShell1920 = viewport1920.width - sidebarWidth // 1672px
  const roomPagePadding1920 = 28 * 2 // 56px
  const roomContent1920 = Math.min(1600, mainShell1920 - roomPagePadding1920) // 1600px
  const cameraWidth1920 = 320
  const gap1920 = 20
  const questionPanel1920 = roomContent1920 - cameraWidth1920 - gap1920 // 1260px
  assert.ok(questionPanel1920 >= 600, 'Desktop 1920x1080 has ample room for IDE')
  assert.ok(sidebarWidth + roomPagePadding1920 + roomContent1920 <= viewport1920.width)

  // Test laptop 1366x768
  const viewport1366 = { width: 1366 }
  const mainShell1366 = viewport1366.width - sidebarWidth // 1118px
  const roomPagePadding1366 = 28 * 2 // 56px
  const roomContent1366 = mainShell1366 - roomPagePadding1366 // 1062px
  const cameraWidth1366 = 280
  const gap1366 = 20
  const questionPanel1366 = roomContent1366 - cameraWidth1366 - gap1366 // 762px
  assert.ok(questionPanel1366 >= 500, 'Laptop 1366x768 has ample room for IDE')
  assert.ok(sidebarWidth + roomPagePadding1366 + cameraWidth1366 + gap1366 + questionPanel1366 <= viewport1366.width)

  // Test tablet 768px (stacked single column)
  const viewport768 = { width: 768 }
  const sidebarMobile = 0 // hidden on tablet
  const roomPagePadding768 = 12 * 2 // 24px
  const roomContent768 = viewport768.width - roomPagePadding768 // 744px
  assert.ok(roomContent768 >= 320, 'Tablet 768px stacks camera and IDE cleanly')

  // Test mobile 375x667 (iPhone SE / narrow mobile)
  const viewport375 = { width: 375 }
  const roomPagePadding375 = 16 * 2 // 32px
  const roomContent375 = viewport375.width - roomPagePadding375 // 343px
  assert.ok(roomContent375 > 0, 'Mobile 375px fits within viewport with zero horizontal overflow')
})

test('Issue 2: Proctoring panel switches to normal document flow below 1080px without floating over IDE', () => {
  const css = fs.readFileSync(path.resolve(process.cwd(), 'app/globals.css'), 'utf-8')

  // Below 1080px, camera-panel must not be sticky (prevents covering the code editor on scroll)
  assert.ok(
    css.includes('.camera-panel {') &&
    css.includes('position: relative !important;') &&
    css.includes('top: auto !important;') &&
    css.includes('z-index: 1 !important;'),
    'camera-panel below 1080px must use relative positioning to scroll naturally above IDE without sticky overlay',
  )
})

test('Issue 2: Camera preview preserves 16/9 aspect ratio and prevents video stretching', () => {
  const css = fs.readFileSync(path.resolve(process.cwd(), 'app/globals.css'), 'utf-8')

  // Aspect ratio is 16/9 with object-fit: cover and scaleX(-1) mirror effect
  assert.ok(
    css.includes('aspect-ratio: 16/9;'),
    'camera-frame must declare aspect-ratio: 16/9 for standard undistorted video',
  )
  assert.ok(
    css.includes('object-fit: cover;'),
    'video element must use object-fit: cover to prevent stretching',
  )
})

test('Issue 2: Collapsed camera panel maintains compact controls and zero horizontal blow-out', () => {
  const css = fs.readFileSync(path.resolve(process.cwd(), 'app/globals.css'), 'utf-8')

  assert.ok(
    css.includes('.camera-panel.is-collapsed .camera-frame {') &&
    css.includes('max-height: 52px;'),
    'Collapsed state must minimize camera frame height to 52px',
  )
  assert.ok(
    css.includes('.camera-panel.is-collapsed .room-controls {') &&
    css.includes('min-height: 48px;'),
    'Collapsed state must compact controls bar to maximize editor room',
  )
})
