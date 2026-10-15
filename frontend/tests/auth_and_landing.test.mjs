import test from 'node:test'
import assert from 'node:assert/strict'

// Role definitions
const ROLE_CANDIDATE = 'candidate'
const ROLE_REVIEWER = 'reviewer'
const ROLE_ADMIN = 'admin'

// Route permission mapping
const ROUTE_PERMISSIONS = {
  '/candidate': [ROLE_CANDIDATE, ROLE_ADMIN],
  '/reviewer': [ROLE_REVIEWER, ROLE_ADMIN],
  '/admin': [ROLE_ADMIN],
}

/**
 * Route guard evaluation function simulating client & edge authorization
 */
function evaluateRouteAccess(targetPath, user) {
  if (!user || !user.token) {
    return {
      allowed: false,
      action: 'redirect_login',
      redirectUrl: `/login?redirect=${encodeURIComponent(targetPath)}`,
    }
  }

  const allowedRoles = ROUTE_PERMISSIONS[targetPath]
  if (!allowedRoles) {
    return { allowed: true, action: 'proceed' }
  }

  if (allowedRoles.includes(user.role)) {
    return { allowed: true, action: 'proceed' }
  }

  // Denied due to insufficient privileges
  const fallbackWorkspace =
    user.role === ROLE_CANDIDATE ? '/candidate' : user.role === ROLE_REVIEWER ? '/reviewer' : '/admin'

  return {
    allowed: false,
    action: 'forbidden',
    statusCode: 403,
    fallbackWorkspace,
    reason: `Role '${user.role}' lacks permission for '${targetPath}'. Required: ${allowedRoles.join(', ')}`,
  }
}

/**
 * Candidate registration sanitization simulating privilege escalation prevention
 */
function sanitizeCandidateRegistration(payload) {
  const username = (payload.username || '').trim()
  const name = (payload.name || '').trim()
  const password = payload.password || ''
  const email = (payload.email || '').trim().toLowerCase() || null

  if (!name || name.length < 2) {
    throw new Error('Name must be at least 2 characters')
  }
  if (!username || username.length < 3) {
    throw new Error('Username must be at least 3 characters')
  }
  if (!password || password.length < 6) {
    throw new Error('Password must be at least 6 characters')
  }

  // Privilege escalation protection: Role is ALWAYS candidate
  return {
    username,
    name,
    email,
    role: ROLE_CANDIDATE,
  }
}

test('Unauthenticated user attempting to access protected route is redirected to login with redirect param', () => {
  const res = evaluateRouteAccess('/candidate', null)
  assert.equal(res.allowed, false)
  assert.equal(res.action, 'redirect_login')
  assert.equal(res.redirectUrl, '/login?redirect=%2Fcandidate')

  const resReviewer = evaluateRouteAccess('/reviewer', null)
  assert.equal(resReviewer.allowed, false)
  assert.equal(resReviewer.action, 'redirect_login')
  assert.equal(resReviewer.redirectUrl, '/login?redirect=%2Freviewer')
})

test('Candidate is allowed to access /candidate but forbidden from /reviewer and /admin', () => {
  const candidateUser = { username: 'candidate_demo', role: ROLE_CANDIDATE, token: 'fake.jwt.token' }

  // Candidate accessing /candidate
  const candRes = evaluateRouteAccess('/candidate', candidateUser)
  assert.equal(candRes.allowed, true)
  assert.equal(candRes.action, 'proceed')

  // Candidate attempting to access /reviewer
  const revRes = evaluateRouteAccess('/reviewer', candidateUser)
  assert.equal(revRes.allowed, false)
  assert.equal(revRes.action, 'forbidden')
  assert.equal(revRes.statusCode, 403)
  assert.equal(revRes.fallbackWorkspace, '/candidate')

  // Candidate attempting to access /admin
  const admRes = evaluateRouteAccess('/admin', candidateUser)
  assert.equal(admRes.allowed, false)
  assert.equal(admRes.action, 'forbidden')
  assert.equal(admRes.statusCode, 403)
  assert.equal(admRes.fallbackWorkspace, '/candidate')
})

test('Reviewer is allowed on /reviewer but forbidden from /admin', () => {
  const reviewerUser = { username: 'reviewer_demo', role: ROLE_REVIEWER, token: 'fake.jwt.token' }

  const revRes = evaluateRouteAccess('/reviewer', reviewerUser)
  assert.equal(revRes.allowed, true)
  assert.equal(revRes.action, 'proceed')

  const admRes = evaluateRouteAccess('/admin', reviewerUser)
  assert.equal(admRes.allowed, false)
  assert.equal(admRes.action, 'forbidden')
  assert.equal(admRes.statusCode, 403)
  assert.equal(admRes.fallbackWorkspace, '/reviewer')
})

test('Admin is authorized across /candidate, /reviewer, and /admin', () => {
  const adminUser = { username: 'admin_demo', role: ROLE_ADMIN, token: 'fake.jwt.token' }

  assert.equal(evaluateRouteAccess('/candidate', adminUser).allowed, true)
  assert.equal(evaluateRouteAccess('/reviewer', adminUser).allowed, true)
  assert.equal(evaluateRouteAccess('/admin', adminUser).allowed, true)
})

test('Candidate registration prevents privilege escalation even if attacker passes role: admin', () => {
  const maliciousPayload = {
    username: 'hacker_bob',
    name: 'Bob Hacker',
    password: 'ComplexPassword123!',
    email: 'bob@hacker.io',
    role: 'admin', // Attack vector attempting self-assignment of admin role
  }

  const clean = sanitizeCandidateRegistration(maliciousPayload)
  assert.equal(clean.role, ROLE_CANDIDATE, 'Role must strictly remain candidate')
  assert.notEqual(clean.role, 'admin')
})

test('Candidate registration validates username and password constraints', () => {
  assert.throws(() => {
    sanitizeCandidateRegistration({ username: 'ab', name: 'Test User', password: '123' })
  }, /Username must be at least 3 characters/)

  assert.throws(() => {
    sanitizeCandidateRegistration({ username: 'valid_user', name: 'Test User', password: '123' })
  }, /Password must be at least 6 characters/)
})

test('Post-login redirection preserves requested route only if role is authorized', () => {
  function getRedirectDestination(requestedPath, userRole) {
    if (!requestedPath || requestedPath === '/') {
      return userRole === ROLE_REVIEWER ? '/reviewer' : userRole === ROLE_ADMIN ? '/admin' : '/candidate'
    }

    if (requestedPath === '/reviewer' && userRole === ROLE_CANDIDATE) {
      return '/candidate' // Candidate diverted from reviewer workspace
    }

    if (requestedPath === '/admin' && userRole !== ROLE_ADMIN) {
      return userRole === ROLE_REVIEWER ? '/reviewer' : '/candidate'
    }

    return requestedPath
  }

  // Candidate with candidate destination
  assert.equal(getRedirectDestination('/candidate', ROLE_CANDIDATE), '/candidate')

  // Candidate attempting reviewer destination diverted to candidate workspace
  assert.equal(getRedirectDestination('/reviewer', ROLE_CANDIDATE), '/candidate')

  // Reviewer with reviewer destination
  assert.equal(getRedirectDestination('/reviewer', ROLE_REVIEWER), '/reviewer')

  // Reviewer attempting admin destination diverted to reviewer workspace
  assert.equal(getRedirectDestination('/admin', ROLE_REVIEWER), '/reviewer')

  // Admin allowed on all
  assert.equal(getRedirectDestination('/admin', ROLE_ADMIN), '/admin')
})
