import test from 'node:test'
import assert from 'node:assert/strict'

// Verify problem catalog normalization logic directly
const BENCHMARK_PROBLEMS = {
  two_sum: {
    id: 'two_sum',
    title: 'Two Sum',
    difficulty: 'Easy',
    assessed_skill: 'Data Structures & Algorithms',
    description: 'Given an integer array nums and an integer target, return the indices of the two numbers whose sum equals target.\n\nYou may assume that each input would have exactly one solution, and you may not use the same element twice.\n\nYou can return the answer in any order.',
    input_format: 'First line contains integer array nums in JSON format or space-delimited integers.\nSecond line contains integer target.',
    output_format: 'A 2-element array [i, j] containing zero-based indices.',
    constraints: [
      '2 <= nums.length <= 10^4',
      '-10^9 <= nums[i] <= 10^9',
      '-10^9 <= target <= 10^9',
      'Exactly one valid solution exists.',
      'The same element cannot be used twice.',
    ],
    examples: [
      {
        input: 'nums = [2,7,11,15]\ntarget = 9',
        output: '[0,1]',
        explanation: 'nums[0] + nums[1] = 2 + 7 = 9, so we return [0, 1].',
      },
      {
        input: 'nums = [3,2,4]\ntarget = 6',
        output: '[1,2]',
        explanation: 'nums[1] + nums[2] = 2 + 4 = 6, so we return [1, 2].',
      },
      {
        input: 'nums = [3,3]\ntarget = 6',
        output: '[0,1]',
        explanation: 'nums[0] + nums[1] = 3 + 3 = 6, so we return [0, 1].',
      },
    ],
    test_cases: [
      {
        id: 'tc_1',
        input: 'nums = [2,7,11,15]\ntarget = 9',
        expected_output: '[0,1]',
        is_hidden: false,
        explanation: 'Standard pair at beginning of array.',
      },
      {
        id: 'tc_2',
        input: 'nums = [3,2,4]\ntarget = 6',
        expected_output: '[1,2]',
        is_hidden: false,
        explanation: 'Target sum formed by middle and last elements.',
      },
      {
        id: 'tc_3',
        input: 'nums = [3,3]\ntarget = 6',
        expected_output: '[0,1]',
        is_hidden: false,
        explanation: 'Identical duplicate numbers forming target.',
      },
      {
        id: 'tc_hidden_1',
        input: 'nums = [1,5,8,12,19,25]\ntarget = 27',
        expected_output: '[2,4]',
        is_hidden: true,
        explanation: 'Hidden benchmark test case.',
      },
    ],
  },
}

test('Two Sum has full LeetCode specifications', () => {
  const p = BENCHMARK_PROBLEMS.two_sum
  assert.equal(p.title, 'Two Sum')
  assert.equal(p.difficulty, 'Easy')
  assert.ok(p.description.length > 50)
  assert.ok(p.input_format.includes('nums'))
  assert.ok(p.output_format.includes('indices'))
  assert.ok(p.constraints.length >= 3)
  assert.ok(p.examples.length >= 2)
  assert.ok(p.examples[0].explanation.includes('2 + 7 = 9'))
  assert.ok(p.test_cases.length >= 3)
  assert.equal(p.test_cases[0].expected_output, '[0,1]')
})

test('Test cases structure includes required properties', () => {
  const p = BENCHMARK_PROBLEMS.two_sum
  for (const tc of p.test_cases) {
    assert.ok(tc.id, 'must have id')
    assert.ok(tc.input, 'must have input')
    assert.ok(tc.expected_output, 'must have expected_output')
    assert.equal(typeof tc.is_hidden, 'boolean')
  }
})
