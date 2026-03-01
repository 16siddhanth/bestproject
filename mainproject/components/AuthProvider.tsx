"use client"

import { createContext, useContext, useState, useEffect, type ReactNode } from "react"
import { useRouter } from "next/navigation"

interface AuthContextType {
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  signup: (userData: any) => Promise<void>
  logout: () => void
  loading: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    // Check authentication status on mount
    const authStatus = localStorage.getItem("veggiefeed_auth")
    setIsAuthenticated(!!authStatus)
    setLoading(false)
  }, [])

  const login = async (email: string, password: string) => {
    // Mock authentication - in real app, this would call Supabase
    setLoading(true)
    await new Promise((resolve) => setTimeout(resolve, 1000))
    localStorage.setItem("veggiefeed_auth", "true")
    setIsAuthenticated(true)
    setLoading(false)
  }

  const signup = async (userData: any) => {
    // Mock authentication - in real app, this would call Supabase
    setLoading(true)
    await new Promise((resolve) => setTimeout(resolve, 1000))
    localStorage.setItem("veggiefeed_auth", "true")
    setIsAuthenticated(true)
    setLoading(false)
  }

  const logout = () => {
    localStorage.removeItem("veggiefeed_auth")
    setIsAuthenticated(false)
    router.push("/")
  }

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        login,
        signup,
        logout,
        loading,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
