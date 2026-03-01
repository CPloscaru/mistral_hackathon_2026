/**
 * ChatView - Full chat layout for onboarding
 *
 * Layout:
 * - Header (sticky top): assistant name + avatar
 * - Messages area (scrollable): message bubbles + typing indicator
 * - ChatInput (sticky bottom): text input + send/mic/attachment buttons
 */

import { useEffect, useRef } from 'react'
import Header from './Header'
import MessageBubble from './MessageBubble'
import TypingIndicator from './TypingIndicator'
import ChatInput from './ChatInput'

function ChatView({ sessionId, chat, onGoToAssistant }) {
  const {
    messages,
    isStreaming,
    maturityLevel,
    sendMessage,
    readyForPlan,
  } = chat

  const scrollAnchorRef = useRef(null)

  useEffect(() => {
    if (scrollAnchorRef.current) {
      scrollAnchorRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])

  const showTypingIndicator = (() => {
    if (!isStreaming) return false
    const lastMsg = messages[messages.length - 1]
    return lastMsg?.role === 'assistant' && lastMsg?.content === '' && lastMsg?.streaming === true
  })()

  function handleSend(text) {
    sendMessage(text, sessionId)
  }

  return (
    <div className="chat-container">
      <Header
        maturityLevel={maturityLevel}
        isOnboarding={true}
      />

      <main className="chat-messages" aria-live="polite" aria-label="Messages">
        {messages.map((msg) => {
          if (msg.role === 'assistant' && msg.content === '' && msg.streaming) {
            return null
          }
          return <MessageBubble key={msg.id} message={msg} />
        })}

        {showTypingIndicator && <TypingIndicator />}

        {readyForPlan && (
          <div className="chat-ready-banner">
            <p>Profil complété ! On passe à la suite ?</p>
            <button onClick={onGoToAssistant} className="chat-ready-btn">
              OK, allons-y !
            </button>
          </div>
        )}

        <div ref={scrollAnchorRef} className="chat-messages__scroll-anchor" />
      </main>

      <ChatInput
        onSend={handleSend}
        disabled={isStreaming || readyForPlan}
      />
    </div>
  )
}

export default ChatView
