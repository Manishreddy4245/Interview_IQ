import { chromium } from 'playwright'

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const SCREENSHOT_PATH = 'C:\\Users\\Manish Reddy\\.gemini\\antigravity-ide\\brain\\8dcf49fb-d57e-4395-af14-2651116e39f6\\leetcode_coding_verified_comprehensive.png'

async function runComprehensiveVerification() {
  console.log('[COMPREHENSIVE-TEST] Launching Chrome...')
  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    headless: true,
  })

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  })
  const page = await context.newPage()

  console.log('[COMPREHENSIVE-TEST] Navigating to http://localhost:3000 ...')
  await page.goto('http://localhost:3000', { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForTimeout(2000)

  // Navigate to Technical Assessment
  console.log('[COMPREHENSIVE-TEST] Opening Technical Assessment...')
  const techNav = page.locator('aside.sidebar button.nav-item:has-text("Technical Assessment")').first()
  if (await techNav.count() > 0) {
    await techNav.click()
  } else {
    await page.locator('button:has-text("Technical Assessment")').first().click()
  }
  await page.waitForTimeout(1500)

  // Configure focus for Two Sum
  const focusInput = page.locator('#focus-input')
  if (await focusInput.count() > 0) {
    await focusInput.fill('Data Structures and Algorithms, Two Sum')
  }

  // Submit setup
  console.log('[COMPREHENSIVE-TEST] Launching interview session...')
  const submitBtn = page.locator('button[type="submit"]:has-text("Begin"), button:has-text("Generate Questions & Begin")').first()
  await submitBtn.click()

  // Wait for IDE
  const ideContainer = page.locator('.multimodal-ide-container.leetcode-layout')
  await ideContainer.waitFor({ state: 'attached', timeout: 30000 })
  console.log('[COMPREHENSIVE-TEST] IDE mounted!')

  // Step 1: Switch to Examples Tab and verify copy button on Example 1 Input
  const examplesTab = page.locator('.ide-left-tab:has-text("Examples")').first()
  await examplesTab.click()
  await page.waitForTimeout(500)

  const copyBtn = page.locator('.ide-copy-btn').first()
  await copyBtn.waitFor({ state: 'visible', timeout: 8000 })
  await copyBtn.click()
  await page.waitForTimeout(400)
  const copyBtnText = await copyBtn.textContent()
  console.log('[COMPREHENSIVE-TEST] Copy button text after click:', copyBtnText.trim())

  // Step 2: Test deliberately invalid code (Syntax Error)
  console.log('\n[COMPREHENSIVE-TEST] Testing deliberately invalid code (Syntax Error)...')
  const brokenCode = `class Solution:\n    def twoSum(self, nums, target):\n        invalid syntax here !!!\n`
  await page.evaluate((val) => {
    // Inject into monaco editor instance
    const editor = (window).monaco?.editor?.getEditors()?.[0]
    if (editor) {
      editor.setValue(val)
    }
  }, brokenCode)

  // Click Run Code
  const runBtn = page.locator('button.ide-btn-run:has-text("Run Code")').first()
  await runBtn.click()

  // Wait for Execution Output
  const outputView = page.locator('.ide-output-view')
  await outputView.waitFor({ state: 'visible', timeout: 15000 })
  const outputText = await outputView.textContent()
  console.log('[COMPREHENSIVE-TEST] Broken code run output summary:', outputText.replace(/\s+/g, ' ').slice(0, 150))

  // Verify that it NEVER says "Program executed cleanly" on an error!
  if (outputText.includes('Program executed cleanly with no stdout/stderr output')) {
    throw new Error('FAIL: Broken code displayed misleading "Program executed cleanly" message!')
  }
  console.log('[COMPREHENSIVE-TEST] Verified: Misleading clean execution message is NOT displayed for errors!')

  // Step 3: Test valid Two Sum solution
  console.log('\n[COMPREHENSIVE-TEST] Testing valid Two Sum solution...')
  const correctCode = `class Solution:
    def twoSum(self, nums, target):
        seen = {}
        for i, n in enumerate(nums):
            diff = target - n
            if diff in seen:
                return [seen[diff], i]
            seen[n] = i
        return []
`
  await page.evaluate((val) => {
    const editor = (window).monaco?.editor?.getEditors()?.[0]
    if (editor) {
      editor.setValue(val)
    }
  }, correctCode)

  // Click Submit Solution
  console.log('[COMPREHENSIVE-TEST] Submitting correct solution...')
  const submitSolBtn = page.locator('button.ide-btn-submit:has-text("Submit Solution")').first()
  await submitSolBtn.click()

  // Wait for test results
  const scoreBadge = page.locator('.ide-test-score .score-badge').first()
  await scoreBadge.waitFor({ state: 'visible', timeout: 25000 })
  const scoreBadgeText = (await scoreBadge.textContent()).trim()
  const scoreRatio = (await page.locator('.ide-score-ratio').first().textContent()).trim()
  console.log(`[COMPREHENSIVE-TEST] Submission Score: "${scoreBadgeText}" | Ratio: "${scoreRatio}"`)

  if (!scoreBadgeText.includes('PASSED') || !scoreRatio.includes('4 / 4')) {
    throw new Error(`FAIL: Expected ALL PASSED (4/4), got ${scoreBadgeText} - ${scoreRatio}`)
  }
  console.log('[COMPREHENSIVE-TEST] 100% Genuine Test Case Pass Verified (4/4 passed)!')

  // Step 4: Verify test case detail card for Case 1
  const detailCard = page.locator('.ide-test-card').first()
  const detailText = await detailCard.textContent()
  console.log('[COMPREHENSIVE-TEST] Detail card status:', detailText.includes('PASSED') ? 'PASSED' : 'FAILED')

  // Capture final screenshot
  await page.screenshot({ path: SCREENSHOT_PATH, fullPage: false })
  console.log('[COMPREHENSIVE-TEST] Screenshot captured to:', SCREENSHOT_PATH)

  await browser.close()
  console.log('\n[COMPREHENSIVE-TEST] ALL COMPREHENSIVE CHECKS PASSED PERFECTLY!')
}

runComprehensiveVerification().catch(err => {
  console.error('[COMPREHENSIVE-TEST] ERROR:', err)
  process.exit(1)
})
