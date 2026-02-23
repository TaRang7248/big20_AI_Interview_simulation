import React, { createContext, useContext, useState, useCallback } from 'react'
import { authApi } from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
    const [user, setUser] = useState(() => {
        try {
            const saved = localStorage.getItem('imh_user')
            return saved ? JSON.parse(saved) : null
        } catch {
            return null
        }
    })

    const login = useCallback(async (username, password) => {
        const res = await authApi.login({ username, password })
        const { token, user_id, name, user_type } = res.data
        const userData = { user_id, name, user_type }
        localStorage.setItem('imh_token', token)
        localStorage.setItem('imh_user', JSON.stringify(userData))
        setUser(userData)
        return userData
    }, [])

    const logout = useCallback(() => {
        localStorage.removeItem('imh_token')
        localStorage.removeItem('imh_user')
        setUser(null)
    }, [])

    const isAdmin = user?.user_type === 'ADMIN'
    const isCandidate = user?.user_type === 'CANDIDATE'

    return (
        <AuthContext.Provider value={{ user, login, logout, isAdmin, isCandidate }}>
            {children}
        </AuthContext.Provider>
    )
}

export function useAuth() {
    const ctx = useContext(AuthContext)
    if (!ctx) throw new Error('useAuth must be used within AuthProvider')
    return ctx
}
