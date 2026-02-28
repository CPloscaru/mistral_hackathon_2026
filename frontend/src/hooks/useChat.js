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

/**
 * Build the backend URL, preserving the subdomain from the current page's hostname.
 * This ensures SubdomainMiddleware on the backend resolves the correct persona.
 *
 * Examples:
 *   sophie.localhost:5173 → http://sophie.localhost:8000
 *   marc.localhost:5173   → http://marc.localhost:8000
 *   localhost:5173        → http://localhost:8000 (fallback)
 */
function buildBackendUrl() {
  const hostname = window.location.hostname
  return `http://${hostname}:8000`
}

const BACKEND_URL = buildBackendUrl()

/**
 * Dispatch a parsed SSE event to the appropriate callback.
 */
function dispatchSSEEvent(eventType, dataLines, onToken, onMaturityUpdate, onDone, onError, onReadyForPlan) {
  if (!eventType) return

  // SSE spec: multiple data: fields are joined with \n
  const eventData = dataLines.join('\n')

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
  } else if (eventType === 'ready_for_plan') {
    // Onboarding phase 1 complete — backend will process the plan separately
    // Treat as done for the streaming UI: stop the loader, re-enable input
    if (onReadyForPlan) {
      try {
        const parsed = JSON.parse(eventData)
        onReadyForPlan(parsed.profile || {})
      } catch (e) {
        onReadyForPlan({})
      }
    } else {
      onDone()
    }
  } else if (eventType === 'error') {
    try {
      const parsed = JSON.parse(eventData)
      onError(parsed.error || 'Erreur inconnue')
    } catch (e) {
      onError(eventData)
    }
  }
}

async function readSSEStream(response, onToken, onMaturityUpdate, onDone, onError, onReadyForPlan) {
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  // Current event being assembled
  let currentEventType = null
  let currentDataLines = []

  /**
   * Process all complete lines in the buffer.
   * SSE spec: events are terminated by a blank line.
   * sse_starlette uses CRLF (\r\n) — we normalize to LF first.
   */
  function processBuffer() {
    // Normalize CRLF to LF for consistent parsing
    const normalized = buffer.replace(/\r\n/g, '\n')

    // Split into lines, keeping track of position
    const lines = normalized.split('\n')

    // The last element may be an incomplete line — keep it in buffer
    // (unless the buffer ended with \n, in which case last element is '')
    const lastLine = lines.pop()
    buffer = lastLine === undefined ? '' : lastLine

    for (const line of lines) {
      if (line === '') {
        // Blank line: dispatch the current event
        dispatchSSEEvent(currentEventType, currentDataLines, onToken, onMaturityUpdate, onDone, onError, onReadyForPlan)
        currentEventType = null
        currentDataLines = []
      } else if (line.startsWith('event: ')) {
        currentEventType = line.slice(7).trim()
      } else if (line.startsWith('data: ')) {
        currentDataLines.push(line.slice(6))
      } else if (line.startsWith('data')) {
        // data with no space after colon = empty data field
        currentDataLines.push('')
      }
      // Ignore comment lines (starting with ':') and id:/retry: fields
    }
  }

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        // Flush any remaining buffer content
        buffer += '\n' // Force processing of last incomplete event if any
        processBuffer()
        break
      }

      buffer += decoder.decode(value, { stream: true })
      processBuffer()
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
      },
      // onReadyForPlan — profil collecté, plan en préparation
      (_profile) => {
        // Stop streaming — input is re-enabled
        // The backend will send the plan as a subsequent message when ready
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMsgId
              ? { ...msg, streaming: false }
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
