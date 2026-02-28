/**
 * ChatView - Full chat layout
 *
 * Layout:
 * - Header (sticky top): assistant name + avatar
 * - Messages area (scrollable): message bubbles + typing indicator
 * - ChatInput (sticky bottom): text input + send/mic/attachment buttons
 *
 * Features:
 * - Auto-scrolls to bottom on new messages
 * - Shows TypingIndicator when streaming and last assistant message is empty
 * - Mobile-first: 100dvh viewport, safe area insets for iOS
 */

import { useEffect, useRef } from 'react'
import Header from './Header'
import MessageBubble from './MessageBubble'
import TypingIndicator from './TypingIndicator'
import ChatInput from './ChatInput'

function ChatView({ personaConfig, sessionId, chat }) {
  const {
    assistantName,
    assistantGender,
    isOnboarding,
  } = personaConfig

  const {
    messages,
    isStreaming,
    maturityLevel,
    sendMessage,
  } = chat

  const scrollAnchorRef = useRef(null)

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (scrollAnchorRef.current) {
      scrollAnchorRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])

  // Show typing indicator when streaming and last assistant message has no content yet
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
        assistantName={assistantName}
        assistantGender={assistantGender}
        maturityLevel={maturityLevel}
        isOnboarding={isOnboarding}
      />

      <main className="chat-messages" aria-live="polite" aria-label="Messages">
        {messages.map((msg) => {
          // Skip streaming assistant messages with empty content — TypingIndicator handles that
          if (msg.role === 'assistant' && msg.content === '' && msg.streaming) {
            return null
          }
          return <MessageBubble key={msg.id} message={msg} />
        })}

        {/* Typing indicator: 3 dots before first token */}
        {showTypingIndicator && <TypingIndicator />}

        {/* Scroll anchor */}
        <div ref={scrollAnchorRef} className="chat-messages__scroll-anchor" />
      </main>

      <ChatInput
        onSend={handleSend}
        disabled={isStreaming}
      />
    </div>
  )
}

export default ChatView
