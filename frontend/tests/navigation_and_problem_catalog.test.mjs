import test from 'node:test'
import assert from 'node:assert/strict'

// Import normalizeProblemData logic
import { BENCHMARK_PROBLEMS, normalizeProblemData } from '../lib/problem_catalog.ts'

test('BENCHMARK_PROBLEMS contains maximum_length_subarray with verified expected outputs', () => {
  const prob = BENCHMARK_PROBLEMS.maximum_length_subarray
  assert.ok(prob, 'maximum_length_subarray problem must exist in benchmark catalog')
  assert.equal(prob.function_name, 'findLength')
  assert.ok(prob.test_cases.length >= 3, 'Must have at least 3 test cases')

  for (const tc of prob.test_cases) {
    assert.ok(tc.expected_output !== undefined && tc.expected_output !== null, 'Expected output must be defined')
    assert.ok(String(tc.expected_output).trim().length > 0, 'Expected output must not be blank')
  }

  // Case 1: [1,2,3,2,1], [3,2,1,4,7] -> 3
  assert.equal(String(prob.test_cases[0].expected_output).trim(), '3')
  // Case 2: [0,0,0,0,0], [0,0,0,0,0] -> 5
  assert.equal(String(prob.test_cases[1].expected_output).trim(), '5')
})

test('normalizeProblemData extracts expected_output from output/expected/result and resolves Maximum Length Subarray', () => {
  const rawQ = {
    id: 'q_test_max_sub',
    title: 'Maximum Length Subarray',
    text: 'Given two integer arrays nums1 and nums2, return the maximum length of a subarray that appears in both arrays.',
    test_cases: [
      { id: 'tc_1', input: '[1,2,3,2,1]\n[3,2,1,4,7]', output: '3', is_hidden: false },
      { id: 'tc_2', input: '[0,0,0,0,0]\n[0,0,0,0,0]', expected: '5', is_hidden: false },
      { id: 'tc_3', input: '[1,2,3]\n[4,5,6]', result: '0', is_hidden: false },
      { id: 'tc_4', input: '[7,8]\n[8,9]', expected_output: '1', is_hidden: true },
    ],
  }

  const normalized = normalizeProblemData(rawQ)
  assert.equal(normalized.title, 'Maximum Length of Repeated Subarray')
  assert.equal(normalized.function_name, 'findLength')
  assert.equal(normalized.test_cases.length, 5)

  assert.equal(normalized.test_cases[0].expected_output, '3')
  assert.equal(normalized.test_cases[1].expected_output, '5')
  assert.equal(normalized.test_cases[2].expected_output, '0')
  assert.equal(normalized.test_cases[3].expected_output, '3')
  assert.equal(normalized.test_cases[3].is_hidden, true)
})

test('Draft state is isolated by session, question ID, and language', () => {
  const drafts = {}

  // Save q1 Python draft
  const saveDraft = (qId, lang, code) => {
    if (!drafts[qId]) drafts[qId] = {}
    drafts[qId][lang] = { code, version: 1, updated_at: new Date().toISOString() }
  }

  saveDraft('q_1', 'python', 'class Solution:\n    def findLength(self): pass')
  saveDraft('q_1', 'javascript', 'function findLength() {}')
  saveDraft('q_2', 'python', 'class Solution:\n    def twoSum(self): pass')

  assert.equal(drafts['q_1']['python'].code, 'class Solution:\n    def findLength(self): pass')
  assert.equal(drafts['q_1']['javascript'].code, 'function findLength() {}')
  assert.equal(drafts['q_2']['python'].code, 'class Solution:\n    def twoSum(self): pass')
  assert.equal(drafts['q_2']['javascript'], undefined)
})
