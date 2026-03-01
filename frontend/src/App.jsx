/**
 * App - Root component avec routing onboarding → personal assistant
 *
 * Routes:
 * - / → WelcomePage
 * - /chat → ChatView (onboarding conversation)
 * - /personal-assistant → PersonalAssistant (stepper + chat + dock)
 */

import { useEffect, useRef } from 'react'
import { Routes, Route, useNavigate } from 'react-router-dom'
import { useSession } from './hooks/useSession'
import { useChat } from './hooks/useChat'
import ChatView from './components/ChatView'
import PersonalAssistant from './components/PersonalAssistant'
import WelcomePage from './components/WelcomePage'

function OnboardingPage({ sessionId, chat }) {
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
      if (!hasHistory && maturityLevel === 1) {
        initChat(sessionId)
      }
    }
    bootstrap()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  return (
    <ChatView
      sessionId={sessionId}
      chat={chat}
      onGoToAssistant={() => navigate('/personal-assistant')}
    />
  )
}

function App() {
  const { sessionId, loading } = useSession()
  const chat = useChat()

  if (loading) {
    return null
  }

  return (
    <Routes>
      <Route path="/" element={<WelcomePage />} />
      <Route
        path="/chat"
        element={
          <OnboardingPage
            sessionId={sessionId}
            chat={chat}
          />
        }
      />
      <Route
        path="/personal-assistant"
        element={
          <PersonalAssistant />
        }
      />
    </Routes>
  )
}

export default App
