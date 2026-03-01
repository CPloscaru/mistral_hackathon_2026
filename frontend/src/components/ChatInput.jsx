/**
 * ChatInput - Message input bar (fixed bottom)
 *
 * - Text input (single line for mobile)
 * - Send button: enabled only when input is non-empty
 * - Mic button: visible but disabled (greyed out, no interaction)
 * - Attachment button: visible but disabled (greyed out, no interaction)
 * - Enter key submits; input clears after send
 */

import { useState, useRef, useEffect } from 'react'

function ChatInput({ onSend, disabled }) {
  const [text, setText] = useState('')
  const textareaRef = useRef(null)

  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 120) + 'px'
  }, [text])

  function handleSend() {
    const trimmed = text.trim()
    if (!trimmed) return
    onSend(trimmed)
    setText('')
  }

  function handleKeyDown(e) {
    // Enter (without Shift) submits
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const canSend = text.trim().length > 0 && !disabled

  return (
    <div className="chat-input-bar" role="form" aria-label="Zone de saisie">
      {/* Attachment button — disabled */}
      <button
        className="chat-input-bar__icon-btn chat-input-bar__icon-btn--disabled"
        type="button"
        disabled
        aria-label="Pièce jointe (bientôt disponible)"
        tabIndex={-1}
      >
        📎
      </button>

      {/* Text input */}
      <textarea
        ref={textareaRef}
        className="chat-input-bar__field"
        rows={2}
        placeholder="Message…"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        aria-label="Votre message"
      />

      {/* Mic button — disabled */}
      <button
        className="chat-input-bar__icon-btn chat-input-bar__icon-btn--disabled"
        type="button"
        disabled
        aria-label="Microphone (bientôt disponible)"
        tabIndex={-1}
      >
        🎤
      </button>

      {/* Send button */}
      <button
        className="chat-input-bar__send-btn"
        type="button"
        onClick={handleSend}
        disabled={!canSend}
        aria-label="Envoyer"
      >
        ↑
      </button>
    </div>
  )
}

export default ChatInput
