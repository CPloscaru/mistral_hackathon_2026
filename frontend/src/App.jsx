/**
 * App - Root component with subdomain-aware persona routing
 *
 * Detects persona from hostname, manages session, and bootstraps chat.
 * Sophie (creator): triggers agent-initiated greeting on mount.
 * Lea/Marc: opens directly in assistant mode (no init call).
 */

import { useEffect, useRef } from 'react'
import { useSubdomain } from './hooks/useSubdomain'
import { useSession } from './hooks/useSession'
import { useChat } from './hooks/useChat'
import ChatView from './components/ChatView'

function App() {
  const personaConfig = useSubdomain()
  const { sessionId } = useSession()
  const chat = useChat()

  const { isOnboarding, persona } = personaConfig
  const { maturityLevel, initChat } = chat

  // Guard against React StrictMode double-invocation of useEffect
  const initCalledRef = useRef(false)

  // Sophie (creator): auto-trigger agent greeting on first mount
  useEffect(() => {
    if (persona === 'creator' && maturityLevel === 1 && sessionId) {
      if (initCalledRef.current) return
      initCalledRef.current = true
      initChat(sessionId)
    }
    // Only run once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  return (
    <ChatView
      personaConfig={personaConfig}
      sessionId={sessionId}
      chat={chat}
    />
  )
}

export default App
