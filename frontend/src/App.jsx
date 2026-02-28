/**
 * App - Root component with subdomain-aware persona routing
 *
 * Routes:
 * - / → ChatView (onboarding conversation)
 * - /personal-assistant → PersonalAssistant (spinner + SMART plan)
 */

import { useEffect, useRef } from 'react'
import { Routes, Route, useNavigate } from 'react-router-dom'
import { useSubdomain } from './hooks/useSubdomain'
import { useSession } from './hooks/useSession'
import { useChat } from './hooks/useChat'
import ChatView from './components/ChatView'
import PersonalAssistant from './components/PersonalAssistant'

function OnboardingPage({ personaConfig, sessionId, chat }) {
  const { persona } = personaConfig
  const { maturityLevel, initChat, loadHistory } = chat
  const navigate = useNavigate()
  const initCalledRef = useRef(false)

  // On mount: load history first, then decide whether to initChat
  useEffect(() => {
    if (!sessionId) return
    if (initCalledRef.current) return
    initCalledRef.current = true

    async function bootstrap() {
      const hasHistory = await loadHistory(sessionId)
      if (!hasHistory && persona === 'creator' && maturityLevel === 1) {
        initChat(sessionId)
      }
    }
    bootstrap()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  // Pass navigate to chat hook for redirect on ready_for_plan
  useEffect(() => {
    chat.setOnReadyForPlan(() => {
      navigate(`/personal-assistant?session_id=${sessionId}`)
    })
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

function App() {
  const personaConfig = useSubdomain()
  const { sessionId } = useSession()
  const chat = useChat()

  return (
    <Routes>
      <Route
        path="/"
        element={
          <OnboardingPage
            personaConfig={personaConfig}
            sessionId={sessionId}
            chat={chat}
          />
        }
      />
      <Route
        path="/personal-assistant"
        element={
          <PersonalAssistant
            personaConfig={personaConfig}
            sessionId={sessionId}
          />
        }
      />
    </Routes>
  )
}

export default App
