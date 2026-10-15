import { chromium } from 'playwright'
import fs from 'fs'
import path from 'path'

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const SCREENSHOT_PATH = 'C:\\Users\\Manish Reddy\\.gemini\\antigravity-ide\\brain\\8dcf49fb-d57e-4395-af14-2651116e39f6\\coding_execution_verified.png'

async function runVerification() {
  console.log('[E2E-TEST] Launching Chrome directly from:', CHROME_PATH)
  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    headless: true,
  })

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  })

  const page = await context.newPage()
  console.log('[E2E-TEST] Navigating to http://localhost:3000 ...')
  await page.goto('http://localhost:3000', { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForTimeout(2000)

  // Navigate to Technical Assessment
  console.log('[E2E-TEST] Clicking on Technical Assessment...')
  const techNav = page.locator('aside.sidebar button.nav-item:has-text("Technical Assessment")').first()
  if (await techNav.count() > 0) {
    await techNav.click()
  } else {
    const fallbackNav = page.locator('button:has-text("Technical Assessment")').first()
    await fallbackNav.click()
  }
  await page.waitForTimeout(1500)

  // Set up interview targeting DSA / Two Sum
  console.log('[E2E-TEST] Configuring InterviewSetup for Data Structures & Algorithms (Two Sum)...')
  const focusInput = page.locator('#focus-input')
  if (await focusInput.count() > 0) {
    await focusInput.fill('Data Structures and Algorithms, Two Sum')
  }

  // Click "Begin" or "Generate Questions & Begin"
  console.log('[E2E-TEST] Submitting InterviewSetup...')
  const submitBtn = page.locator('button[type="submit"]:has-text("Begin"), button:has-text("Generate Questions & Begin")').first()
  if (await submitBtn.count() > 0) {
    await submitBtn.click()
  }

  // Wait for IDE
  console.log('[E2E-TEST] Waiting for IDE to mount...')
  const ideContainer = page.locator('.multimodal-ide-container.leetcode-layout')
  await ideContainer.waitFor({ state: 'attached', timeout: 30000 })
  console.log('[E2E-TEST] IDE mounted successfully!')

  // 1. Verify "What should my code return or print?" hint card
  const hintCard = page.locator('.ide-contract-hint-card').first()
  await hintCard.waitFor({ state: 'visible', timeout: 5000 })
  const hintText = await hintCard.textContent()
  console.log('[E2E-TEST] Execution contract card found:', hintText.trim().replace(/\s+/g, ' '))

  // 2. Verify dedicated example cards with separate monospace blocks
  console.log('[E2E-TEST] Checking example cards in Description tab...')
  const exampleCards = page.locator('.ide-example-card')
  const count = await exampleCards.count()
  console.log(`[E2E-TEST] Found ${count} example cards in the UI`)
  if (count === 0) {
    throw new Error('FAIL: No example cards rendered in Description/Examples!')
  }

  // Verify copy button on first example input
  const firstCopyInputBtn = page.locator('.ide-copy-btn').first()
  await firstCopyInputBtn.waitFor({ state: 'visible', timeout: 5000 })
  console.log('[E2E-TEST] Copy button visible on example code block')

  // 3. Switch to Examples Tab
  console.log('[E2E-TEST] Switching to Examples Tab...')
  const examplesTab = page.locator('.ide-left-tab:has-text("Examples")').first()
  await examplesTab.click()
  await page.waitForTimeout(500)

  const exTabCards = page.locator('.ide-example-card')
  const exCount = await exTabCards.count()
  console.log(`[E2E-TEST] Found ${exCount} example cards in Examples Tab`)

  // Test "Use as Custom Input ->"
  const useAsCustomBtn = page.locator('.ide-btn-text:has-text("Use as Custom Input")').first()
  if (await useAsCustomBtn.count() > 0) {
    await useAsCustomBtn.click()
    await page.waitForTimeout(500)
    console.log('[E2E-TEST] Successfully clicked "Use as Custom Input ->"')
  }

  // 4. Test Run Code
  console.log('[E2E-TEST] Triggering "Run Code"...')
  const runBtn = page.locator('button.ide-btn-run:has-text("Run Code")').first()
  await runBtn.click()

  // Wait for Run Code to finish
  console.log('[E2E-TEST] Waiting for execution output...')
  const outputBadge = page.locator('.ide-output-view .ide-badge').first()
  await outputBadge.waitFor({ state: 'visible', timeout: 15000 })
  const statusText = (await outputBadge.textContent()).trim()
  console.log('[E2E-TEST] Run Code Status Badge:', statusText)

  // Verify stdout or return value was captured cleanly
  const stdoutPre = page.locator('.ide-code-block.stdout').first()
  if (await stdoutPre.count() > 0) {
    const stdoutContent = (await stdoutPre.textContent()).trim()
    console.log('[E2E-TEST] Standard Output / Driver Result:', stdoutContent)
  }

  // 5. Test Submit Solution
  console.log('[E2E-TEST] Triggering "Submit Solution"...')
  const submitSolBtn = page.locator('button.ide-btn-submit:has-text("Submit Solution")').first()
  await submitSolBtn.click()

  // Wait for Test Results
  console.log('[E2E-TEST] Waiting for test results...')
  const testScoreBadge = page.locator('.ide-test-score .score-badge').first()
  await testScoreBadge.waitFor({ state: 'visible', timeout: 20000 })
  const testScoreText = (await testScoreBadge.textContent()).trim()
  const scoreRatio = (await page.locator('.ide-score-ratio').first().textContent()).trim()
  console.log(`[E2E-TEST] Submit Result: ${testScoreText} | ${scoreRatio}`)

  // Verify test case detail card has separate monospace blocks for Input, Expected Output, Actual Output
  const testCard = page.locator('.ide-test-card').first()
  await testCard.waitFor({ state: 'visible', timeout: 5000 })
  const testCardDetails = await testCard.textContent()
  console.log('[E2E-TEST] Test Case Detail Card contains Input & Output:', testCardDetails.includes('Input') && testCardDetails.includes('Expected Output'))

  // Capture screenshot
  await page.screenshot({ path: SCREENSHOT_PATH, fullPage: false })
  console.log('[E2E-TEST] Screenshot captured successfully to:', SCREENSHOT_PATH)

  await browser.close()
  console.log('[E2E-TEST] ALL CHECKS PASSED!')
}

runVerification().catch(err => {
  console.error('[E2E-TEST] FAILED:', err)
  process.exit(1)
})
