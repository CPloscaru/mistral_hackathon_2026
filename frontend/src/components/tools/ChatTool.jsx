/**
 * ChatTool - Chat spécialisé contextuel ("Parler à un spécialiste")
 *
 * Ouvre un chat contextuel lié à des objectifs spécifiques.
 * Envoie les messages à /chat/stream avec le contexte des objectifs couverts.
 *
 * Props:
 * - sessionId: identifiant de session
 * - data: { objectifs: [...], specialite: "..." }
 */

import { useState, useRef, useEffect, useCallback } from 'react'

function buildBackendUrl() {
  return `http://${window.location.hostname}:8000`
}

const BACKEND_URL = buildBackendUrl()

function ChatTool({ sessionId, data, chatType: chatTypeProp = 'main' }) {
  const [messages, setMessages] = useState([])
  const [inputText, setInputText] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const messagesEndRef = useRef(null)

  const objectifs = data?.objectifs || []
  // Utiliser le chat_type des data (ex: "specialist_juridique") sinon la prop
  const chatType = data?.chat_type || chatTypeProp

  // Charger l'historique au mount
  useEffect(() => {
    if (!sessionId || !chatType) return
    async function loadHistory() {
      try {
        const res = await fetch(`${BACKEND_URL}/chat/history?session_id=${sessionId}&chat_type=${chatType}`)
        if (res.ok) {
          const data = await res.json()
          if (data.messages && data.messages.length > 0) {
            setMessages(data.messages.map(m => ({ role: m.role, content: m.content })))
          }
        }
      } catch (e) {
        console.warn('[ChatTool] Failed to load history:', e)
      }
    }
    loadHistory()
  }, [sessionId, chatType])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = useCallback(async () => {
    const text = inputText.trim()
    if (!text || isStreaming) return

    setMessages(prev => [...prev, { role: 'user', content: text }])
    setInputText('')
    setIsStreaming(true)

    try {
      const response = await fetch(`${BACKEND_URL}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: sessionId, chat_type: chatType }),
      })

      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let currentEventType = null
      let currentDataLines = []
      let assistantText = ''

      setMessages(prev => [...prev, { role: 'assistant', content: '' }])

      function processBuffer() {
        const normalized = buffer.replace(/\r\n/g, '\n')
        const lines = normalized.split('\n')
        const lastLine = lines.pop()
        buffer = lastLine === undefined ? '' : lastLine

        for (const line of lines) {
          if (line === '') {
            if (currentEventType && currentDataLines.length > 0) {
              const eventData = currentDataLines.join('\n')
              if (currentEventType === 'token') {
                assistantText += eventData
                setMessages(prev => {
                  const updated = [...prev]
                  updated[updated.length - 1] = { role: 'assistant', content: assistantText }
                  return updated
                })
              }
            }
            currentEventType = null
            currentDataLines = []
          } else if (line.startsWith('event: ')) {
            currentEventType = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            currentDataLines.push(line.slice(6))
          }
        }
      }

      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          buffer += '\n'
          processBuffer()
          break
        }
        buffer += decoder.decode(value, { stream: true })
        processBuffer()
      }
      reader.releaseLock()
    } catch (err) {
      console.error('Chat stream error:', err)
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Oups, une erreur est survenue. Réessaie !'
      }])
    } finally {
      setIsStreaming(false)
    }
  }, [inputText, isStreaming, sessionId, chatType])

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="chat-tool">
      {/* Contexte */}
      {objectifs.length > 0 && (
        <div className="chat-tool__context">
          <span className="chat-tool__context-label">Objectifs liés :</span>
          {objectifs.map((obj, i) => (
            <span key={i} className="chat-tool__context-tag">{obj}</span>
          ))}
        </div>
      )}

      {/* Messages */}
      <div className="chat-tool__messages">
        {messages.length === 0 && (
          <div className="chat-tool__empty">
            Pose ta question, je suis là pour t'aider.
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`chat-tool__msg chat-tool__msg--${msg.role}`}>
            {msg.content}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="chat-tool__input-bar">
        <textarea
          className="chat-tool__input"
          rows={1}
          placeholder="Message..."
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
        />
        <button
          className="chat-tool__send-btn"
          onClick={handleSend}
          disabled={!inputText.trim() || isStreaming}
        >
          &uarr;
        </button>
      </div>
    </div>
  )
}

export default ChatTool
