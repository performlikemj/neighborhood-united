import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react'
import { api, setTokens, clearTokens, blacklistRefreshToken } from '../api'
import { jwtDecode } from 'jwt-decode'

const AuthContext = createContext(null)

function pickRoleFromServerOrPrev(serverRole, prev){
  if (serverRole === 'chef' || serverRole === 'customer') return serverRole
  return prev?.current_role || 'customer'
}

export function AuthProvider({ children }){
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const hasFetchedOnce = useRef(false)
  
  // Chef Preview Mode: Track if user has access to chefs in their area
  // null = not checked yet, true = chefs available, false = no chefs
  const [hasChefAccess, setHasChefAccess] = useState(null)
  const [chefAccessLoading, setChefAccessLoading] = useState(false)
  const lastCheckedPostal = useRef(null)
  
  // Multi-chef support: Track connected chefs for customer
  const [connectedChefs, setConnectedChefs] = useState([])
  const [connectedChefsLoading, setConnectedChefsLoading] = useState(false)
  const hasFetchedChefs = useRef(false)

  // Check if any verified chef serves the user's area
  const checkChefAvailability = useCallback(async (forceCheck = false) => {
    const isDev = Boolean(import.meta?.env?.DEV)
    
    // Don't check if user is a chef (they always have "access")
    if (user?.is_chef) {
      setHasChefAccess(true)
      return true
    }
    
    // Get current postal code
    const currentPostal = user?.address?.postalcode || user?.address?.input_postalcode || user?.postal_code || ''
    const currentCountry = user?.address?.country || ''
    
    // Skip if no address info
    if (!currentPostal || !currentCountry) {
      if (isDev) console.debug('[Auth] checkChefAvailability: no postal/country, setting hasChefAccess=false')
      setHasChefAccess(false)
      return false
    }
    
    // Skip if we already checked this postal code (unless forced)
    const postalKey = `${currentPostal}:${currentCountry}`
    if (!forceCheck && lastCheckedPostal.current === postalKey) {
      if (isDev) console.debug('[Auth] checkChefAvailability: already checked this postal code')
      return
    }
    
    setChefAccessLoading(true)
    try {
      if (isDev) console.debug('[Auth] checkChefAvailability: checking', { postalKey })
      const resp = await api.get('/chefs/api/availability/')
      const data = resp?.data || {}
      const available = Boolean(data?.has_chef)
      
      setHasChefAccess(available)
      if (isDev) console.debug('[Auth] checkChefAvailability result:', { available, data })
      return available
    } catch (e) {
      if (isDev) console.warn('[Auth] checkChefAvailability failed:', e?.response?.status)
      // On error, assume no access (fail safe for preview mode)
      setHasChefAccess(false)
      return false
    } finally {
      lastCheckedPostal.current = postalKey  // Mark as checked regardless of success/failure
      setChefAccessLoading(false)
    }
  }, [user?.is_chef, user?.address?.postalcode, user?.address?.input_postalcode, user?.postal_code, user?.address?.country])  // Removed hasChefAccess from deps

  async function fetchUserAndAddressOnce(){
    const isDev = Boolean(import.meta?.env?.DEV)
    if (isDev){
      const stack = (new Error('fetchUserAndAddressOnce trace').stack || '')
        .split('\n')
        .slice(2, 7)
        .map(line => line.trim())
      console.debug('[Auth] fetchUserAndAddressOnce invoked', {
        hasFetched: hasFetchedOnce.current,
        stack
      })
    }
    if (hasFetchedOnce.current){
      if (isDev){
        console.debug('[Auth] fetchUserAndAddressOnce skipped (already fetched once)')
      }
      return
    }
    hasFetchedOnce.current = true
    try{
      if (isDev){
        console.debug('[Auth] fetchUserAndAddressOnce issuing request')
      }
      // Single API call - address is now included in user_details response
      const uRes = await api.get('/auth/api/user_details/')
      const base = uRes?.data || {}
      
      // Normalize address data for consistent frontend access
      const address = base.address || null
      const postal = address?.input_postalcode || address?.postalcode || ''
      
      setUser(prev => {
        const role = pickRoleFromServerOrPrev(base?.current_role, prev)
        return {
          ...prev,
          ...base,
          is_chef: Boolean(base?.is_chef),
          current_role: role,
          household_member_count: Math.max(1, Number(base?.household_member_count || 1)),
          address: address ? { ...address, postalcode: postal } : null,
          postal_code: postal
        }
      })
    } finally {
      if (isDev){
        console.debug('[Auth] fetchUserAndAddressOnce completed', {
          hasFetched: hasFetchedOnce.current
        })
      }
      setLoading(false)
    }
  }

  useEffect(()=>{
    const token = localStorage.getItem('accessToken')
    if (!token){ setLoading(false); return }
    try{
      const claims = jwtDecode(token)
      setUser(prev => ({ ...(prev||{}), id: claims.user_id }))
    }catch{}
    fetchUserAndAddressOnce().catch((e)=>{ console.warn('[Auth] initial load failed', e?.response?.status); setLoading(false) })
  }, [])

  // Check chef availability when user/address loads or changes
  useEffect(() => {
    // Only check if we have a user and we're done loading
    if (loading || !user?.id) return
    
    // Check chef availability after user is loaded
    const postal = user?.address?.postalcode || user?.address?.input_postalcode || user?.postal_code
    if (postal) {
      checkChefAvailability()
    } else {
      // No postal code = no chef access
      setHasChefAccess(false)
    }
  }, [loading, user?.id, user?.address?.postalcode, user?.address?.input_postalcode, user?.postal_code, checkChefAvailability])

  // Fetch connected chefs for customers
  const fetchConnectedChefs = useCallback(async (forceRefresh = false) => {
    const isDev = Boolean(import.meta?.env?.DEV)
    
    // Skip if user is a chef (chefs don't have "connected chefs")
    if (user?.is_chef && user?.current_role === 'chef') {
      setConnectedChefs([])
      hasFetchedChefs.current = true
      return []
    }
    
    // Skip if already fetched (unless forced)
    if (!forceRefresh && hasFetchedChefs.current) {
      return
    }
    
    setConnectedChefsLoading(true)
    try {
      if (isDev) console.debug('[Auth] fetchConnectedChefs: fetching')
      const resp = await api.get('/customer_dashboard/api/my-chefs/')
      const chefs = resp?.data?.chefs || []
      setConnectedChefs(chefs)
      if (isDev) console.debug('[Auth] fetchConnectedChefs result:', { count: chefs.length })
      return chefs
    } catch (e) {
      if (isDev) console.warn('[Auth] fetchConnectedChefs failed:', e?.response?.status)
      setConnectedChefs([])
      return []
    } finally {
      hasFetchedChefs.current = true  // Mark as fetched regardless of success/failure
      setConnectedChefsLoading(false)
    }
  }, [user?.is_chef, user?.current_role])  // Removed connectedChefs from deps to prevent infinite loop

  // Fetch connected chefs when user loads and is a customer
  useEffect(() => {
    if (loading || !user?.id) return
    if (user?.current_role !== 'chef') {
      fetchConnectedChefs()
    }
  }, [loading, user?.id, user?.current_role, fetchConnectedChefs])

  const login = async (username, password) => {
    // Use URL-encoded form to avoid CORS preflight on Content-Type
    const form = new URLSearchParams()
    form.set('username', username)
    form.set('password', password)
    const resp = await api.post('/auth/api/login/', form)
    if (resp.data?.access || resp.data?.refresh){ setTokens({ access: resp.data?.access, refresh: resp.data?.refresh }) }
    // If backend returns a user snapshot (incl. measurement_system), prime UI immediately
    try{
      if (resp?.data?.user && typeof resp.data.user === 'object'){
        const base = resp.data.user
        setUser(prev => ({
          ...(prev||{}),
          ...base,
          is_chef: Boolean(base?.is_chef),
          current_role: pickRoleFromServerOrPrev(base?.current_role, prev),
          household_member_count: Math.max(1, Number(base?.household_member_count || 1))
        }))
      }
    }catch{}
    hasFetchedOnce.current = false
    await fetchUserAndAddressOnce()
    return user
  }

  const logout = async () => {
    await blacklistRefreshToken()
    clearTokens()
    setUser(null)
    setHasChefAccess(null)
    lastCheckedPostal.current = null
    setConnectedChefs([])
    hasFetchedChefs.current = false
  }

  const register = async (payload) => {
    const body = payload && payload.user ? payload : { user: payload }
    const resp = await api.post('/auth/api/register/', body, { skipUserId: true })
    if (resp.data.access && resp.data.refresh){
      setTokens({ access: resp.data.access, refresh: resp.data.refresh })
      hasFetchedOnce.current = false
      await fetchUserAndAddressOnce()
      return user
    } else {
      await login(payload.username, payload.password)
    }
  }

  const refreshUser = async () => {
    try{
      // Single API call - address is now included in user_details response
      const u = await api.get('/auth/api/user_details/')
      const userData = u?.data || {}
      
      // Normalize address data for consistent frontend access
      const address = userData.address || null
      const postal = address?.input_postalcode || address?.postalcode || ''
      
      setUser(prev => ({
        ...(prev||{}),
        ...userData,
        is_chef: Boolean(userData?.is_chef),
        current_role: pickRoleFromServerOrPrev(userData?.current_role, prev),
        address: address ? { ...address, postalcode: postal } : prev?.address || null,
        postal_code: postal || prev?.postal_code
      }))
    }catch{}
  }

  const switchRole = async (role) => {
    const token = localStorage.getItem('accessToken')
    const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
    const resp = await api.post('/auth/api/switch_role/', role ? { role } : {}, { headers })
    // Option C: backend returns authoritative user and optionally new tokens
    const payload = resp?.data || {}
    if (payload.access || payload.refresh){
      try{ setTokens({ access: payload.access, refresh: payload.refresh }) }catch{}
    }
    if (payload.user){
      setUser(prev => ({ ...(prev||{}), ...(payload.user||{}), is_chef: Boolean(payload?.user?.is_chef), current_role: pickRoleFromServerOrPrev(payload?.user?.current_role, prev) }))
      return payload?.user?.current_role || role
    }
    // Fallback if response did not include user (compat mode)
    const u = await api.get('/auth/api/user_details/')
    setUser(prev => ({ ...(prev||{}), ...(u.data||{}), is_chef: Boolean(u.data?.is_chef), current_role: pickRoleFromServerOrPrev(u.data?.current_role, prev), household_member_count: Math.max(1, Number((u.data||{}).household_member_count || 1)) }))
    return u?.data?.current_role || role
  }

  return (
    <AuthContext.Provider value={{ 
      user, 
      setUser, 
      login, 
      logout, 
      register, 
      refreshUser, 
      switchRole, 
      loading,
      // Chef Preview Mode
      hasChefAccess,
      chefAccessLoading,
      checkChefAvailability,
      // Multi-chef support (Client Portal)
      connectedChefs,
      connectedChefsLoading,
      fetchConnectedChefs,
      hasChefConnection: connectedChefs.length > 0,
      singleChef: connectedChefs.length === 1 ? connectedChefs[0] : null,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(){
  return useContext(AuthContext)
}
