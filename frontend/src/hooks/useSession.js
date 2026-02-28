/**
 * useSession - Manages session ID persistence across page refreshes
 *
 * Uses sessionStorage to persist session_id within the browser tab.
 * Generates a new UUID v4 if none exists.
 */

import { useState } from 'react'

/**
 * Build a session key scoped to the current subdomain.
 * Prevents session_id sharing between sophie/lea/marc subdomains
 * when they share the same registrable domain (localhost).
 */
function getSessionKey() {
  const parts = window.location.hostname.split('.')
  const subdomain = parts.length >= 2 ? parts[0].toLowerCase() : 'default'
  return `kameleon_session_id_${subdomain}`
}

function getOrCreateSessionId() {
  const SESSION_KEY = getSessionKey()
  let sessionId = sessionStorage.getItem(SESSION_KEY)
  if (!sessionId) {
    sessionId = crypto.randomUUID()
    sessionStorage.setItem(SESSION_KEY, sessionId)
  }
  return sessionId
}

export function useSession() {
  const [sessionId, setSessionId] = useState(() => getOrCreateSessionId())

  function resetSession() {
    const newId = crypto.randomUUID()
    sessionStorage.setItem(getSessionKey(), newId)
    setSessionId(newId)
  }

  return { sessionId, resetSession }
}
