/**
 * useSession - Fetches the active session from the backend
 *
 * Single-user app: the backend resolves the active session from DB.
 * No more session_id in URL or sessionStorage.
 */

import { useState, useEffect } from 'react'

function buildBackendUrl() {
  const hostname = window.location.hostname
  return `http://${hostname}:8000`
}

const BACKEND_URL = buildBackendUrl()

export function useSession() {
  const [sessionId, setSessionId] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchActiveSession(retries = 5) {
      for (let i = 0; i < retries; i++) {
        try {
          const res = await fetch(`${BACKEND_URL}/session/active`)
          if (res.ok) {
            const data = await res.json()
            if (data.session_id) {
              setSessionId(data.session_id)
              setLoading(false)
              return
            }
          }
          break // Server responded but no session — don't retry
        } catch (e) {
          console.warn(`Failed to fetch active session (attempt ${i + 1}/${retries}):`, e)
          if (i < retries - 1) {
            await new Promise(r => setTimeout(r, 1000))
          }
        }
      }
      // No session found after retries — generate one client-side
      setSessionId(crypto.randomUUID())
      setLoading(false)
    }
    fetchActiveSession()
  }, [])

  function refreshSession() {
    setLoading(true)
    fetch(`${BACKEND_URL}/session/active`)
      .then(res => res.json())
      .then(data => {
        setSessionId(data.session_id || crypto.randomUUID())
      })
      .catch(e => console.warn('Failed to refresh session:', e))
      .finally(() => setLoading(false))
  }

  return { sessionId, loading, refreshSession }
}
