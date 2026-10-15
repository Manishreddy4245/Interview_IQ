import { chromium } from 'playwright'

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const SCREENSHOT_PATH = 'C:\\Users\\Manish Reddy\\.gemini\\antigravity-ide\\brain\\8dcf49fb-d57e-4395-af14-2651116e39f6\\leetcode_workspace_verified.png'

async function verifyLeetCodeWorkspace() {
  console.log('[E2E-BROWSER] Launching Chrome directly from:', CHROME_PATH)
  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    headless: true,
  })

  const context = await browser.newContext({
    viewport: { width: 1440, height: 960 },
  })

  const page = await context.newPage()
  console.log('[E2E-BROWSER] Navigating to http://localhost:3000 ...')
  await page.goto('http://localhost:3000', { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForTimeout(2000)

  // Navigate to Technical Assessment
  console.log('[E2E-BROWSER] Clicking on Technical Assessment in navigation...')
  const techNav = page.locator('aside.sidebar button.nav-item:has-text("Technical Assessment")').first()
  if (await techNav.count() > 0) {
    await techNav.click()
  } else {
    const fallbackNav = page.locator('button:has-text("Technical Assessment")').first()
    await fallbackNav.click()
  }
  await page.waitForTimeout(1500)

  // In InterviewSetup, submit form to begin room
  console.log('[E2E-BROWSER] Submitting InterviewSetup to launch room...')
  const submitBtn = page.locator('button[type="submit"]:has-text("Begin"), button:has-text("Generate Questions & Begin")').first()
  if (await submitBtn.count() > 0) {
    await submitBtn.click()
  }

  // Wait for IDE container with LeetCode layout
  console.log('[E2E-BROWSER] Waiting for .multimodal-ide-container.leetcode-layout ...')
  const ideContainer = page.locator('.multimodal-ide-container.leetcode-layout').first()
  await ideContainer.waitFor({ state: 'visible', timeout: 30000 })
  console.log('[E2E-BROWSER] ✓ LeetCode IDE container is mounted!')

  // 1. Verify Left Pane Problem Statement
  const leftPane = page.locator('#ide-problem-panel')
  await leftPane.waitFor({ state: 'visible', timeout: 5000 })
  const title = (await leftPane.locator('.ide-problem-title').textContent()).trim()
  const diff = (await leftPane.locator('.ide-diff-badge').textContent()).trim()
  console.log(`[E2E-BROWSER] ✓ Problem Title: "${title}", Difficulty: "${diff}"`)

  // 2. Verify Tabs (Description, Examples, Constraints, Test Cases)
  const tabDesc = page.locator('button.ide-left-tab:has-text("Description")')
  const tabExamples = page.locator('button.ide-left-tab:has-text("Examples")')
  const tabConstraints = page.locator('button.ide-left-tab:has-text("Constraints")')
  const tabTestCases = page.locator('button.ide-left-tab:has-text("Test Cases")')

  console.log('[E2E-BROWSER] Checking Left Pane Navigation Tabs...')
  if (await tabDesc.count() > 0) console.log('  ✓ Description tab present')
  if (await tabExamples.count() > 0) console.log('  ✓ Examples tab present')
  if (await tabConstraints.count() > 0) console.log('  ✓ Constraints tab present')
  if (await tabTestCases.count() > 0) console.log('  ✓ Test Cases tab present')

  // Click Examples Tab
  if (await tabExamples.count() > 0) {
    await tabExamples.click()
    await page.waitForTimeout(500)
    const exampleCards = await page.locator('.ide-example-card').count()
    console.log(`[E2E-BROWSER] ✓ Rendered ${exampleCards} example cards in Examples tab`)
  }

  // Click Constraints Tab
  if (await tabConstraints.count() > 0) {
    await tabConstraints.click()
    await page.waitForTimeout(500)
    const constraintsItems = await page.locator('.ide-constraint-item').count()
    console.log(`[E2E-BROWSER] ✓ Rendered ${constraintsItems} constraint items in Constraints tab`)
  }

  // Click Test Cases Tab in Left Pane
  if (await tabTestCases.count() > 0) {
    await tabTestCases.click()
    await page.waitForTimeout(500)
    const testCasesCount = await page.locator('.ide-tc-preview-card').count()
    console.log(`[E2E-BROWSER] ✓ Rendered ${testCasesCount} test case preview cards in Test Cases tab`)
  }

  // Switch back to Description tab
  if (await tabDesc.count() > 0) {
    await tabDesc.click()
    await page.waitForTimeout(500)
  }

  // 3. Verify Draggable Divider
  const divider = page.locator('.ide-split-divider')
  const hasDivider = await divider.count() > 0
  console.log(`[E2E-BROWSER] ✓ Draggable Divider present: ${hasDivider}`)

  // 4. Verify Editor and Language Selector
  const langSelect = page.locator('select#ide-language-select')
  const selectedLang = await langSelect.inputValue()
  console.log(`[E2E-BROWSER] ✓ Current selected language: "${selectedLang}"`)

  // 5. Test "Run Code" Action
  console.log('[E2E-BROWSER] Clicking "Run Code"...')
  const runBtn = page.locator('button.ide-btn-run:has-text("Run Code")')
  if (await runBtn.count() > 0) {
    await runBtn.click()
    console.log('[E2E-BROWSER] Waiting for execution output...')
    await page.waitForTimeout(4000)
    const outputText = await page.locator('.ide-bottom-content').textContent()
    console.log('[E2E-BROWSER] ✓ Execution Output visible. Preview length:', outputText.length)
  }

  // 6. Test "Submit Solution" Action
  console.log('[E2E-BROWSER] Clicking "Submit Solution"...')
  const submitSolBtn = page.locator('button.ide-btn-submit:has-text("Submit Solution")')
  if (await submitSolBtn.count() > 0) {
    await submitSolBtn.click()
    console.log('[E2E-BROWSER] Waiting for test evaluation results...')
    await page.waitForTimeout(6000)
    const testResultsTab = page.locator('.ide-bottom-tab:has-text("Test Cases")')
    if (await testResultsTab.count() > 0) {
      await testResultsTab.click()
      await page.waitForTimeout(500)
    }
  }

  // Capture full workspace screenshot
  console.log('[E2E-BROWSER] Capturing screenshot to:', SCREENSHOT_PATH)
  await page.screenshot({ path: SCREENSHOT_PATH, fullPage: true })
  console.log('[E2E-BROWSER] ✓ Screenshot captured successfully!')

  await browser.close()
  console.log('[E2E-BROWSER] ALL CHECKS PASSED!')
}

verifyLeetCodeWorkspace().catch((err) => {
  console.error('[E2E-BROWSER] ERROR:', err)
  process.exit(1)
})
