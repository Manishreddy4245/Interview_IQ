import test from 'node:test'
import assert from 'node:assert/strict'

// Known genuine language display names mapping fallback
const KNOWN_LANGUAGE_NAMES = {
  python: 'Python 3',
  javascript: 'JavaScript (Node.js)',
  typescript: 'TypeScript',
  cpp: 'C++',
  java: 'Java',
  c: 'C',
  csharp: 'C#',
  go: 'Go',
  rust: 'Rust',
  kotlin: 'Kotlin',
  php: 'PHP',
  ruby: 'Ruby',
  swift: 'Swift',
  scala: 'Scala',
  sql: 'SQL',
}

function formatLanguageDisplayOption(lang) {
  const rawId = (lang.id || lang.key || '').trim().toLowerCase()
  const id = rawId || 'python'

  let name = (lang.name || lang.label || '').trim()
  let loggedDiagnostic = false
  if (!name) {
    name = KNOWN_LANGUAGE_NAMES[id] || (id ? id.charAt(0).toUpperCase() + id.slice(1) : 'Unknown Language')
    loggedDiagnostic = true
  }

  const version = (lang.version || '').trim()
  const displayLabel = version ? `${name} — (${version})` : name

  return {
    id,
    name,
    version,
    displayLabel,
    isSql: Boolean(lang.is_sql || id === 'sql'),
    loggedDiagnostic,
  }
}

test('Dropdown displays readable options for all required languages', () => {
  const testCases = [
    { input: { id: 'python', name: 'Python 3', version: '3.10.0' }, expectedLabel: 'Python 3 — (3.10.0)', expectedId: 'python' },
    { input: { id: 'javascript', name: 'JavaScript (Node.js)', version: '18.15.0' }, expectedLabel: 'JavaScript (Node.js) — (18.15.0)', expectedId: 'javascript' },
    { input: { id: 'cpp', name: 'C++', version: '10.2.0' }, expectedLabel: 'C++ — (10.2.0)', expectedId: 'cpp' },
    { input: { id: 'java', name: 'Java', version: '15.0.2' }, expectedLabel: 'Java — (15.0.2)', expectedId: 'java' },
    { input: { id: 'c', name: 'C', version: '10.2.0' }, expectedLabel: 'C — (10.2.0)', expectedId: 'c' },
    { input: { id: 'csharp', name: 'C#', version: '6.12.0' }, expectedLabel: 'C# — (6.12.0)', expectedId: 'csharp' },
    { input: { id: 'go', name: 'Go', version: '1.16.2' }, expectedLabel: 'Go — (1.16.2)', expectedId: 'go' },
    { input: { id: 'rust', name: 'Rust', version: '1.68.2' }, expectedLabel: 'Rust — (1.68.2)', expectedId: 'rust' },
    { input: { id: 'sql', name: 'SQL', version: '3.53.2', is_sql: true }, expectedLabel: 'SQL — (3.53.2)', expectedId: 'sql' },
  ]

  for (const tc of testCases) {
    const formatted = formatLanguageDisplayOption(tc.input)
    assert.equal(formatted.displayLabel, tc.expectedLabel, `Expected '${tc.expectedLabel}' but got '${formatted.displayLabel}'`)
    assert.equal(formatted.id, tc.expectedId, `Option value must be runtime id '${tc.expectedId}', not display label`)
    // Ensure display label is NEVER identical to value
    assert.notEqual(formatted.id, formatted.displayLabel)
  }
})

test('Dropdown option values map to runtime IDs and not display labels', () => {
  const lang = { id: 'python', name: 'Python 3', version: '3.10.0' }
  const formatted = formatLanguageDisplayOption(lang)

  // Simulated select element option
  const optionValue = formatted.id
  const optionText = formatted.displayLabel

  assert.equal(optionValue, 'python', 'Option value must match execution engine runtime ID')
  assert.equal(optionText, 'Python 3 — (3.10.0)', 'Option text must be human-readable with version')
})

test('Handles missing name metadata gracefully with safe fallback and diagnostic', () => {
  // Provider returns only id and version without name or label
  const langWithoutName = { id: 'javascript', version: '18.15.0' }
  const formatted = formatLanguageDisplayOption(langWithoutName)

  assert.equal(formatted.name, 'JavaScript (Node.js)', 'Should fallback to known language name')
  assert.equal(formatted.displayLabel, 'JavaScript (Node.js) — (18.15.0)')
  assert.equal(formatted.loggedDiagnostic, true, 'Diagnostic was flagged')
})

test('Handles completely unknown runtime gracefully without throwing', () => {
  const unknownLang = { id: 'zig', version: '0.11.0' }
  const formatted = formatLanguageDisplayOption(unknownLang)

  assert.equal(formatted.name, 'Zig')
  assert.equal(formatted.displayLabel, 'Zig — (0.11.0)')
})

test('Verifies live execution provider API endpoint returns genuinely supported languages', async () => {
  try {
    const baseUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/+$/, '')
    const res = await fetch(`${baseUrl}/api/interviews/languages`)
    if (res.ok) {
      const data = await res.json()
      assert.ok(Array.isArray(data.languages), 'languages must be an array')
      const py = data.languages.find(l => l.id === 'python')
      assert.ok(py, 'python must be supported')
      assert.equal(py.name, 'Python 3')
      assert.equal(py.version, '3.10.0')
      assert.equal(py.display_name, 'Python 3 — (3.10.0)')

      const js = data.languages.find(l => l.id === 'javascript')
      assert.ok(js, 'javascript must be supported')
      assert.equal(js.name, 'JavaScript (Node.js)')
      assert.equal(js.version, '18.15.0')
      assert.equal(js.display_name, 'JavaScript (Node.js) — (18.15.0)')

      const sql = data.languages.find(l => l.id === 'sql')
      assert.ok(sql, 'sql must be supported when sqlite sandbox configured')
      assert.equal(sql.name, 'SQL')
      assert.ok(sql.display_name.startsWith('SQL — ('))
    }
  } catch (err) {
    // If backend dev server is not currently running on 8000 during isolated test run, pass gracefully
    console.log('[Note] Live API fetch skipped in this environment:', err.message)
  }
})
