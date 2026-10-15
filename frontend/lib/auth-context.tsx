'use client'

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import {
  getAuthToken,
  getAuthUser,
  loginUser,
  registerCandidate,
  logoutUser,
  switchDemoRole,
  getCurrentUserProfile,
  type UserProfile,
  type LoginRequest,
  type RegisterRequest,
  type TokenResponse,
} from '@/lib/api'

interface AuthContextType {
  user: UserProfile | null
  token: string | null
  role: 'candidate' | 'reviewer' | 'admin' | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (credentials: LoginRequest) => Promise<TokenResponse>
  register: (payload: RegisterRequest) => Promise<TokenResponse>
  logout: () => void
  devSwitchRole: (role: 'candidate' | 'reviewer' | 'admin') => Promise<TokenResponse>
  refreshProfile: () => Promise<UserProfile | null>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)

  const refreshProfile = useCallback(async (): Promise<UserProfile | null> => {
    const existingToken = getAuthToken()
    if (!existingToken) {
      setUser(null)
      setToken(null)
      return null
    }

    try {
      const profile = await getCurrentUserProfile()
      setUser(profile)
      setToken(existingToken)
      return profile
    } catch (err) {
      console.warn('Session verification failed, logging out:', err)
      logoutUser()
      setUser(null)
      setToken(null)
      return null
    }
  }, [])

  useEffect(() => {
    let mounted = true
    const initAuth = async () => {
      const cachedToken = getAuthToken()
      const cachedUser = getAuthUser()

      if (cachedToken && cachedUser) {
        setUser(cachedUser)
        setToken(cachedToken)
      }

      if (cachedToken) {
        try {
          const profile = await getCurrentUserProfile()
          if (mounted) {
            setUser(profile)
            setToken(cachedToken)
          }
        } catch {
          if (mounted) {
            setUser(null)
            setToken(null)
          }
        }
      }

      if (mounted) {
        setIsLoading(false)
      }
    }

    initAuth()

    return () => {
      mounted = false
    }
  }, [])

  const login = async (credentials: LoginRequest): Promise<TokenResponse> => {
    setIsLoading(true)
    try {
      const res = await loginUser(credentials)
      setToken(res.access_token)
      // Verify and fetch verified full profile with permissions
      const profile = await getCurrentUserProfile()
      setUser(profile)
      return res
    } finally {
      setIsLoading(false)
    }
  }

  const register = async (payload: RegisterRequest): Promise<TokenResponse> => {
    setIsLoading(true)
    try {
      const res = await registerCandidate(payload)
      setToken(res.access_token)
      const profile = await getCurrentUserProfile()
      setUser(profile)
      return res
    } finally {
      setIsLoading(false)
    }
  }

  const logout = () => {
    logoutUser()
    setUser(null)
    setToken(null)
  }

  const devSwitchRole = async (targetRole: 'candidate' | 'reviewer' | 'admin'): Promise<TokenResponse> => {
    setIsLoading(true)
    try {
      const res = await switchDemoRole(targetRole)
      setToken(res.access_token)
      const profile = await getCurrentUserProfile()
      setUser(profile)
      return res
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        role: (user?.role as any) || null,
        isLoading,
        isAuthenticated: !!token && !!user,
        login,
        register,
        logout,
        devSwitchRole,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
