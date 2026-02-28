/**
 * useChat - Main SSE stream consumer hook
 *
 * Handles:
 * - sendMessage(text): POST /chat/stream with SSE streaming response
 * - initChat(sessionId): GET /chat/init for Sophie onboarding (agent-initiated)
 * - SSE event types: token, maturity_update, done, error
 *
 * Uses functional updater form in setMessages to avoid stale closure issues.
 */

import { useState, useCallback } from 'react'

const BACKEND_URL = 'http://localhost:8000'

async function readSSEStream(response, onToken, onMaturityUpdate, onDone, onError) {
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // Process complete SSE messages (separated by double newlines)
      const parts = buffer.split('\n\n')
      // Keep the last part which may be incomplete
      buffer = parts.pop() || ''

      for (const part of parts) {
        if (!part.trim()) continue

        const lines = part.split('\n')
        let eventType = null
        let eventData = null

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            eventData = line.slice(6)
          }
        }

        if (!eventType || eventData === null) continue

        if (eventType === 'token') {
          onToken(eventData)
        } else if (eventType === 'maturity_update') {
          try {
            const parsed = JSON.parse(eventData)
            onMaturityUpdate(parsed.level)
          } catch (e) {
            console.warn('Failed to parse maturity_update:', eventData)
          }
        } else if (eventType === 'done') {
          onDone()
        } else if (eventType === 'error') {
          try {
            const parsed = JSON.parse(eventData)
            onError(parsed.error || 'Erreur inconnue')
          } catch (e) {
            onError(eventData)
          }
        }
      }
    }
  } catch (err) {
    onError(err.message || 'Erreur de connexion')
  } finally {
    reader.releaseLock()
  }
}

export function useChat() {
  const [messages, setMessages] = useState([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [maturityLevel, setMaturityLevel] = useState(1)
  const [assistantName, setAssistantName] = useState(null)

  /**
   * Shared SSE response handler
   * assistantMsgId: the id of the assistant message to stream tokens into
   */
  const handleSSEResponse = useCallback(async (response, assistantMsgId) => {
    await readSSEStream(
      response,
      // onToken
      (token) => {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMsgId
              ? { ...msg, content: msg.content + token }
              : msg
          )
        )
      },
      // onMaturityUpdate
      (level) => {
        setMaturityLevel(level)
      },
      // onDone
      () => {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMsgId
              ? { ...msg, streaming: false }
              : msg
          )
        )
        setIsStreaming(false)
      },
      // onError
      (errorMsg) => {
        console.error('SSE error:', errorMsg)
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMsgId
              ? {
                  ...msg,
                  content: 'Oups, un problème est survenu. Réessaie.',
                  streaming: false,
                }
              : msg
          )
        )
        setIsStreaming(false)
      }
    )
  }, [])

  /**
   * sendMessage - User sends a message, streams assistant response
   */
  const sendMessage = useCallback(async (text, sessionId) => {
    if (!text.trim() || isStreaming) return

    const userMsgId = Date.now()
    const assistantMsgId = Date.now() + 1

    setMessages((prev) => [
      ...prev,
      { role: 'user', content: text, id: userMsgId },
      { role: 'assistant', content: '', id: assistantMsgId, streaming: true },
    ])
    setIsStreaming(true)

    try {
      const response = await fetch(`${BACKEND_URL}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: sessionId }),
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      await handleSSEResponse(response, assistantMsgId)
    } catch (err) {
      console.error('sendMessage error:', err)
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? {
                ...msg,
                content: 'Oups, un problème est survenu. Réessaie.',
                streaming: false,
              }
            : msg
        )
      )
      setIsStreaming(false)
    }
  }, [isStreaming, handleSSEResponse])

  /**
   * initChat - Agent-initiated greeting for Sophie onboarding
   * Called automatically on mount for creator persona
   */
  const initChat = useCallback(async (sessionId) => {
    const assistantMsgId = Date.now()

    setMessages((prev) => [
      ...prev,
      { role: 'assistant', content: '', id: assistantMsgId, streaming: true },
    ])
    setIsStreaming(true)

    try {
      const response = await fetch(
        `${BACKEND_URL}/chat/init?session_id=${sessionId}`,
        { method: 'GET' }
      )

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      await handleSSEResponse(response, assistantMsgId)
    } catch (err) {
      console.error('initChat error:', err)
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? {
                ...msg,
                content: 'Oups, un problème est survenu. Réessaie.',
                streaming: false,
              }
            : msg
        )
      )
      setIsStreaming(false)
    }
  }, [handleSSEResponse])

  return {
    messages,
    isStreaming,
    maturityLevel,
    assistantName,
    setAssistantName,
    sendMessage,
    initChat,
  }
}
