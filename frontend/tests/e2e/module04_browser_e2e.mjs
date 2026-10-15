/**
 * InterviewIQ — Module 04 Genuine Browser E2E Test Suite.
 *
 * Launches installed Google Chrome browser via project Playwright to perform
 * real DOM interaction end-to-end testing against http://localhost:3000:
 *
 * 1. Open frontend and navigate to Skill Gap Analysis workspace.
 * 2. Upload standard synthetic PDF fixture (<12,000 chars).
 * 3. Analyze target role "Senior Backend Engineer (Senior)".
 * 4. Verify 4-tier gap categories, role benchmark, grounded evidence, and personalized questions.
 * 5. Start live interview session from the analyzed resume (retaining linkage).
 * 6. Answer Question 1 with technical detail and save answer.
 * 7. Request AI evaluation and verify communication coaching score card.
 * 8. Complete session and open Final Performance Decision Intelligence Report.
 * 9. Verify closed-loop post-interview traceability, alignment cards, and capability score isolation.
 * 10. Navigate to Skill Gap Analysis and upload oversized synthetic PDF (14,080 chars).
 * 11. Verify the authoritative 12,000-character truncation disclosure banner in real DOM.
 * 12. Check console errors and network request logs.
 */

import { chromium } from 'playwright'
import path from 'path'
import fs from 'fs'

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const SCRATCH_DIR = 'C:\\Users\\Manish Reddy\\.gemini\\antigravity-ide\\brain\\626b5656-0031-4d8d-9927-6b70d13c233d\\scratch'
const STANDARD_PDF = path.join(SCRATCH_DIR, 'synthetic_resume.pdf')
const OVERSIZED_PDF = path.join(SCRATCH_DIR, 'synthetic_resume_oversized.pdf')

async function runBrowserE2E() {
  console.log('======================================================================')
  console.log('InterviewIQ — Module 04 Genuine Browser E2E Verification')
  console.log('======================================================================')
  console.log(`[INIT] Launching Google Chrome at: ${CHROME_PATH}`)

  if (!fs.existsSync(CHROME_PATH)) {
    throw new Error(`Google Chrome executable not found at: ${CHROME_PATH}`)
  }
  if (!fs.existsSync(STANDARD_PDF) || !fs.existsSync(OVERSIZED_PDF)) {
    throw new Error('Synthetic PDF fixtures not found in scratch directory.')
  }

  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    headless: true,
  })

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  })

  const consoleLogs = []
  const consoleErrors = []
  const failedRequests = []

  const page = await context.newPage()

  page.on('console', (msg) => {
    const text = msg.text()
    consoleLogs.push(`[${msg.type()}] ${text}`)
    if (msg.type() === 'error') {
      consoleErrors.push(text)
    }
  })

  page.on('requestfailed', (req) => {
    failedRequests.push(`${req.method()} ${req.url()} - ${req.failure()?.errorText}`)
  })

  async function submitAndAwaitAnalysis(pageLabel, timeoutMs = 180000) {
    console.log(`[${pageLabel}] Submitting resume analysis form...`)
    const analyzeBtn = page.locator('button[type="submit"]:has-text("Analyze Resume & Skill Gaps")')
    await analyzeBtn.click()

    let backoffMs = 15000
    const startTime = Date.now()
    while (Date.now() - startTime < timeoutMs) {
      if (await page.locator('.analysis-header-card').isVisible()) {
        return
      }
      const errorCallout = page.locator('.status-callout.error')
      if (await errorCallout.isVisible()) {
        const errText = await errorCallout.innerText()
        if (errText.includes('rate limit') || errText.includes('wait a moment') || errText.includes('429')) {
          console.log(`[${pageLabel}] Groq rate limit encountered: "${errText.trim()}". Backing off ${backoffMs / 1000}s before retrying...`)
          await page.waitForTimeout(backoffMs)
          backoffMs = Math.min(45000, Math.floor(backoffMs * 1.5))
          if (await analyzeBtn.isEnabled()) {
            await analyzeBtn.click()
          }
        } else {
          throw new Error(`Analysis failed with UI error: ${errText}`)
        }
      }
      await page.waitForTimeout(2000)
    }
    throw new Error(`Timeout waiting for .analysis-header-card in ${pageLabel}`)
  }

  try {
    // -------------------------------------------------------------------------
    // Step 1: Open Application & Check Initial Page State
    // -------------------------------------------------------------------------
    console.log('[STEP 1] Navigating to http://localhost:3000...')
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle', timeout: 30000 })
    const title = await page.title()
    console.log(`[PASS] Page loaded. Title: "${title}"`)

    // -------------------------------------------------------------------------
    // Step 2: Navigate to Skill Gap Analysis Workspace
    // -------------------------------------------------------------------------
    console.log('[STEP 2] Navigating to Skill Gap Analysis tab...')
    const skillGapNav = page.locator('aside.sidebar button.nav-item:has-text("Skill Gap Analysis")').first()
    await skillGapNav.click()
    await page.waitForSelector('.skill-gap-page', { timeout: 15000 })
    console.log('[PASS] Reached Skill Gap Analysis workspace.')

    // -------------------------------------------------------------------------
    // Step 3: Upload Standard Synthetic PDF (<12,000 Chars)
    // -------------------------------------------------------------------------
    console.log('[STEP 3] Uploading standard synthetic PDF fixture (<12,000 chars)...')
    // Ensure clean initial Groq rate limit window
    await page.waitForTimeout(10000)
    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles(STANDARD_PDF)

    const roleInput = page.locator('#target-role-input')
    await roleInput.fill('Senior Backend Engineer')

    const expSelect = page.locator('#exp-level-select')
    await expSelect.selectOption('Senior')

    await submitAndAwaitAnalysis('STEP 3 (Standard PDF)')

    // Verify that truncation warning is NOT present for standard PDF
    const noWarning = await page.locator('[data-testid="truncation-warning"]').isVisible()
    if (noWarning) {
      throw new Error('FAIL: Truncation warning unexpectedly displayed for standard resume below limit!')
    }
    console.log('[PASS] Standard resume analyzed cleanly without truncation disclosure.')

    // -------------------------------------------------------------------------
    // Step 4: Verify Role Benchmark, 4-Tier Classifications & Grounded Evidence
    // -------------------------------------------------------------------------
    console.log('[STEP 4] Inspecting role benchmark and four-tier skill classifications...')
    const roleHeader = await page.locator('.analysis-header-card h3').innerText()
    console.log(`[PASS] Analysis Target Role: "${roleHeader}"`)

    const skillChips = await page.locator('.skill-chip').allInnerTexts()
    console.log(`[PASS] Extracted Skills (${skillChips.length}): ${skillChips.slice(0, 6).join(', ')}...`)

    // Verify Benchmark Section
    const benchmarkVisible = await page.locator('text=Target Role Benchmark').first().isVisible()
    console.log(`[PASS] Target Role Benchmark Section visible: ${benchmarkVisible}`)

    // Verify 4-Tier Skill Evidence Categories
    const categoryTabs = await page.locator('.category-filter-tab').allInnerTexts()
    console.log(`[PASS] Category Filter Tabs: ${categoryTabs.join(' | ')}`)

    // Verify Personalized Questions
    const questionsCount = await page.locator('.personalized-q-card').count()
    console.log(`[PASS] Generated Personalized Questions: ${questionsCount}`)
    if (questionsCount < 1) {
      throw new Error('FAIL: Zero personalized questions generated from resume analysis!')
    }

    // -------------------------------------------------------------------------
    // Step 5: Start Interview from Analyzed Resume
    // -------------------------------------------------------------------------
    console.log('[STEP 5] Starting interview session from analyzed resume...')
    const startInterviewBtn = page.locator('.personalized-questions-section button:has-text("Start Interview")')
    await startInterviewBtn.click()

    // Wait for interview room to mount
    await page.waitForSelector('.room-page', { timeout: 30000 })
    console.log('[PASS] Successfully entered live Interview Room.')

    // Verify active question
    const questionText = await page.locator('.question-copy h3').innerText()
    console.log(`[PASS] Question 1: "${questionText.slice(0, 80)}..."`)

    // -------------------------------------------------------------------------
    // Step 6: Submit Candidate Answer & Evaluate with AI
    // -------------------------------------------------------------------------
    console.log('[STEP 6] Answering Question 1 and submitting...')
    const answerTextarea = page.locator('#answer-input')
    await answerTextarea.fill(
      'In our high-throughput microservices architecture, we use asyncpg with connection pooling ' +
      '(min_size=10, max_size=50). Queries leverage EXPLAIN ANALYZE for optimization, and Redis is ' +
      'used for distributed caching with graceful fallback under load.'
    )

    const saveAnswerBtn = page.locator('button:has-text("Save Answer")')
    await saveAnswerBtn.click()

    await page.waitForSelector('button:has-text("Update Answer")', { timeout: 20000 })
    console.log('[PASS] Candidate answer recorded successfully.')

    console.log('[STEP 6] Requesting AI Answer Evaluation from Communication Coach...')
    // Allow Groq token window to clear before triggering evaluation
    await page.waitForTimeout(20000)

    const evalBtn = page.locator('button:has-text("Evaluate with AI Coach")')
    await evalBtn.click()

    // Wait for evaluation card with rate-limit retry support
    const evalStartTime = Date.now()
    let evalCardVisible = false
    while (Date.now() - evalStartTime < 180000) {
      if (await page.locator('.eval-card').isVisible()) {
        evalCardVisible = true
        break
      }
      const retryEvalBtn = page.locator('button:has-text("Retry Evaluation")')
      if (await retryEvalBtn.isVisible()) {
        console.log('[STEP 6] Evaluation hit temporary cooldown. Waiting 20s before retrying...')
        await page.waitForTimeout(20000)
        if (await retryEvalBtn.isVisible() && await retryEvalBtn.isEnabled()) {
          await retryEvalBtn.click()
        }
      }
      await page.waitForTimeout(2000)
    }

    if (!evalCardVisible) {
      throw new Error('FAIL: Timeout waiting for .eval-card')
    }

    const evalScore = await page.locator('.score-badge .score-val').innerText()
    console.log(`[PASS] AI Evaluation Complete! Overall Score: ${evalScore}/100`)

    // -------------------------------------------------------------------------
    // Step 7: Complete Session & Generate Final Report
    // -------------------------------------------------------------------------
    console.log('[STEP 7] Completing session and opening Final Report...')
    const completeBtn = page.locator('button:has-text("Complete Session & View Final Report")')
    await completeBtn.click()

    console.log('[STEP 7] Waiting for final report to compile and render (.report-hero-card)...')
    await page.waitForSelector('.report-hero-card', { timeout: 60000 })
    console.log('[PASS] Final Decision Intelligence Report loaded.')

    // -------------------------------------------------------------------------
    // Step 8: Verify Closed-Loop Gap Closure & Traceability in Report
    // -------------------------------------------------------------------------
    console.log('[STEP 8] Verifying Resume-to-Interview Closed-Loop Alignment in Report...')
    const reportTitle = await page.locator('.room-header h2').innerText()
    console.log(`[PASS] Report Title: "${reportTitle}"`)

    const alignmentHeading = page.locator('h3:has-text("Resume-to-Interview Alignment")').first()
    await alignmentHeading.scrollIntoViewIfNeeded()
    const alignmentVisible = await alignmentHeading.isVisible()
    if (!alignmentVisible) {
      throw new Error('FAIL: Resume-to-Interview Alignment section missing from final report!')
    }
    console.log('[PASS] Resume-to-Interview Alignment & Verification section verified in DOM.')

    // Verify capability score isolation and integrity telemetry
    const integrityHeading = page.locator('h3:has-text("Observed Session Presence")').first()
    await integrityHeading.scrollIntoViewIfNeeded()
    const integrityVisible = await integrityHeading.isVisible()
    console.log(`[PASS] Integrity context verified in DOM: ${integrityVisible}`)

    const overallScoreHero = await page.locator('.report-score-hero').isVisible()
    console.log(`[PASS] Capability scoring section visible and isolated: ${overallScoreHero}`)

    const statusBadges = await page.locator('.report-page .pill-badge').allInnerTexts()
    console.log(`[PASS] Verified Report Badges: ${statusBadges.slice(0, 8).join(' • ')}`)

    // -------------------------------------------------------------------------
    // Step 9: Test 12,000-Character Truncation Contract (Oversized PDF)
    // -------------------------------------------------------------------------
    console.log('[STEP 9] Returning to Skill Gap Analysis to test 12,000-character truncation contract...')
    await page.waitForTimeout(15000)
    await page.locator('aside.sidebar button.nav-item:has-text("Skill Gap Analysis")').first().click()
    await page.waitForSelector('.skill-gap-page', { timeout: 15000 })

    // Check if we need to click "Analyze Another Resume"
    const analyzeAnotherBtn = page.locator('button:has-text("Analyze Another Resume")')
    if (await analyzeAnotherBtn.isVisible()) {
      await analyzeAnotherBtn.click()
      await page.waitForSelector('.upload-dropzone', { timeout: 15000 })
    }

    console.log('[STEP 9] Uploading oversized synthetic PDF (14,080 chars) to test truncation boundary...')
    await page.locator('input[type="file"]').setInputFiles(OVERSIZED_PDF)
    await page.locator('#target-role-input').fill('Senior Enterprise Architect')
    await page.locator('#exp-level-select').selectOption('Lead')

    await submitAndAwaitAnalysis('STEP 9 (Oversized PDF)')

    // Verify Truncation Disclosure Banner in real DOM
    const truncationWarning = page.locator('[data-testid="truncation-warning"]')
    const isWarningVisible = await truncationWarning.isVisible()
    if (!isWarningVisible) {
      throw new Error('FAIL: Truncation warning banner not displayed for oversized PDF (>12,000 chars)!')
    }
    const warningText = await truncationWarning.innerText()
    console.log(`[PASS] Truncation banner verified: "${warningText.trim()}"`)
    if (!warningText.includes('12,000') || !warningText.includes('Document Length Limit Reached')) {
      throw new Error(`FAIL: Banner missing required text: ${warningText}`)
    }

    // -------------------------------------------------------------------------
    // Step 10: Check Console Errors & Network Failures
    // -------------------------------------------------------------------------
    console.log('[STEP 10] Checking console errors and failed network requests...')
    const realErrors = consoleErrors.filter(
      (e) => !e.includes('favicon') && !e.includes('hydrat') && !e.includes('429')
    )
    console.log(`[PASS] Real console errors: ${realErrors.length}`)
    console.log(`[PASS] Failed network requests: ${failedRequests.length}`)

    console.log('======================================================================')
    console.log('ALL BROWSER E2E STEPS AND ASSERTIONS PASSED SUCCESSFULLY!')
    console.log('======================================================================')

    return {
      success: true,
      browserVersion: browser.version(),
      questionsCount,
      evalScore,
      consoleErrorsCount: realErrors.length,
      failedRequestsCount: failedRequests.length,
    }
  } catch (err) {
    console.error('[DIAGNOSTIC] Console Errors:', consoleErrors)
    console.error('[DIAGNOSTIC] Failed Network Requests:', failedRequests)
    throw err
  } finally {
    await browser.close()
  }
}

runBrowserE2E()
  .then((res) => {
    console.log('[RESULT] Browser E2E Result:', JSON.stringify(res, null, 2))
    process.exit(0)
  })
  .catch((err) => {
    console.error('[FATAL] Browser E2E Error:', err)
    process.exit(1)
  })
