/**
 * PersonalAssistant - Post-onboarding page with spinner + SMART objective + Dock tools
 *
 * Flow:
 * 1. Mount: fetch session info (prenom) + trigger Swarm via POST /chat/stream
 * 2. Show orbital spinner for at least 3 seconds
 * 3. When plan_ready SSE event arrives AND 3s elapsed → transition to SMART display
 * 4. Typewriter effect for the objectif_smart text
 * 5. After typewriter → slide-in Dock with 3 tool icons (staggered)
 * 6. Click tool → opens ToolPanel overlay left of Dock
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import Dock from './Dock'
import ToolPanel from './ToolPanel'
import AdminTool from './tools/AdminTool'
import CalendarTool from './tools/CalendarTool'
import CRMTool from './tools/CRMTool'
import '../styles/dock.css'

function buildBackendUrl() {
  const hostname = window.location.hostname
  return `http://${hostname}:8000`
}

const BACKEND_URL = buildBackendUrl()
const MIN_SPINNER_MS = 3000
const TYPEWRITER_SPEED = 30 // ms per character

function PersonalAssistant({ personaConfig }) {
  const [searchParams] = useSearchParams()
  const sessionId = searchParams.get('session_id')

  const [phase, setPhase] = useState('loading') // loading | spinner | objectif
  const [prenom, setPrenom] = useState(null)
  const [plan, setPlan] = useState(null)
  const [typedText, setTypedText] = useState('')
  const [showCursor, setShowCursor] = useState(true)
  const [spinnerExiting, setSpinnerExiting] = useState(false)
  const [dockVisible, setDockVisible] = useState(false)
  const skipAnimationRef = useRef(false)
  const [selectedTool, setSelectedTool] = useState(null)

  const spinnerStartRef = useRef(null)
  const planReadyRef = useRef(null)
  const startedRef = useRef(false)

  // Fetch session info + trigger Swarm
  useEffect(() => {
    if (!sessionId || startedRef.current) return
    startedRef.current = true

    async function init() {
      // Fetch session info (prenom + cached plan)
      let cachedPlan = null
      try {
        const res = await fetch(`${BACKEND_URL}/chat/session-info?session_id=${sessionId}`)
        if (res.ok) {
          const data = await res.json()
          if (data.prenom) setPrenom(data.prenom)
          if (data.plan) cachedPlan = data.plan
        }
      } catch (e) {
        console.warn('Failed to fetch session info:', e)
      }

      // If plan already exists, skip Swarm and show it directly
      if (cachedPlan && cachedPlan.objectif_smart) {
        skipAnimationRef.current = true
        setPlan(cachedPlan)
        setTypedText(cachedPlan.objectif_smart)
        setShowCursor(false)
        setDockVisible(true)
        setPhase('objectif')
        return
      }

      // Start spinner
      setPhase('spinner')
      spinnerStartRef.current = Date.now()

      // Trigger Swarm
      try {
        const response = await fetch(`${BACKEND_URL}/chat/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: '__PLAN__', session_id: sessionId }),
        })

        if (!response.ok) throw new Error(`HTTP ${response.status}`)

        // Read SSE stream
        await readPlanStream(response)
      } catch (err) {
        console.error('Swarm plan error:', err)
        // Fallback: show error after min spinner time
        await waitMinSpinner()
        setPhase('objectif')
      }
    }
    init()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  const waitMinSpinner = useCallback(async () => {
    const elapsed = Date.now() - (spinnerStartRef.current || Date.now())
    const remaining = MIN_SPINNER_MS - elapsed
    if (remaining > 0) {
      await new Promise((r) => setTimeout(r, remaining))
    }
  }, [])

  const readPlanStream = useCallback(async (response) => {
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let currentEventType = null
    let currentDataLines = []
    let receivedPlan = null

    function processBuffer() {
      const normalized = buffer.replace(/\r\n/g, '\n')
      const lines = normalized.split('\n')
      const lastLine = lines.pop()
      buffer = lastLine === undefined ? '' : lastLine

      for (const line of lines) {
        if (line === '') {
          // Dispatch event
          if (currentEventType && currentDataLines.length > 0) {
            const eventData = currentDataLines.join('\n')

            if (currentEventType === 'plan_ready') {
              try {
                receivedPlan = JSON.parse(eventData)
                planReadyRef.current = receivedPlan
              } catch (e) {
                console.warn('Failed to parse plan_ready:', eventData)
              }
            }
            // progress, maturity_update, done — just ignore for the spinner
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

    try {
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
    } catch (err) {
      console.error('SSE read error:', err)
    } finally {
      reader.releaseLock()
    }

    // Transition to objectif after min spinner time
    await waitMinSpinner()

    if (receivedPlan) {
      setPlan(receivedPlan)
      // Animate spinner exit
      setSpinnerExiting(true)
      await new Promise((r) => setTimeout(r, 500))
      setPhase('objectif')
    } else {
      setPhase('objectif')
    }
  }, [waitMinSpinner])

  // Typewriter effect for objectif_smart
  useEffect(() => {
    if (phase !== 'objectif' || !plan?.objectif_smart) return
    if (skipAnimationRef.current) return

    const text = plan.objectif_smart
    let i = 0
    setTypedText('')
    setShowCursor(true)

    const interval = setInterval(() => {
      i++
      setTypedText(text.slice(0, i))
      if (i >= text.length) {
        clearInterval(interval)
        // Keep cursor blinking for a bit, then show dock
        setTimeout(() => {
          setShowCursor(false)
          setDockVisible(true)
        }, 1500)
      }
    }, TYPEWRITER_SPEED)

    return () => clearInterval(interval)
  }, [phase, plan])

  const displayName = prenom || 'toi'

  return (
    <div className="personal-assistant">
      <div className="personal-assistant__header">
        <h1>Assistant personnel de {displayName}</h1>
      </div>

      {(phase === 'spinner' || phase === 'loading') && (
        <div className={`spinner-overlay ${spinnerExiting ? 'spinner-overlay--exiting' : ''}`}>
          <div className="spinner-box">
            <div className="leo blue-orbit" />
            <div className="leo green-orbit" />
            <div className="leo red-orbit" />
            <div className="leo white-orbit w1" />
            <div className="leo white-orbit w2" />
            <div className="leo white-orbit w3" />
          </div>
          <p className="spinner-label">
            Je prépare ton plan personnalisé...
          </p>
        </div>
      )}

      {phase === 'objectif' && plan && (
        <div className="smart-display">
          <p className="smart-display__objectif">
            {typedText}
            {showCursor && <span className="smart-display__cursor" />}
          </p>
        </div>
      )}

      {phase === 'objectif' && !plan && (
        <div className="smart-display">
          <p className="smart-display__objectif">
            Oups, un problème est survenu lors de la préparation de ton plan.
          </p>
        </div>
      )}

      {/* Dock macOS — slides in after typewriter */}
      <Dock
        visible={dockVisible}
        activeTool={selectedTool}
        onSelectTool={setSelectedTool}
      />

      {/* Tool Panel — opens left of dock */}
      {selectedTool && (
        <ToolPanel tool={selectedTool} onClose={() => setSelectedTool(null)}>
          {selectedTool === 'admin' && <AdminTool sessionId={sessionId} />}
          {selectedTool === 'calendar' && <CalendarTool sessionId={sessionId} />}
          {selectedTool === 'crm' && <CRMTool sessionId={sessionId} />}
        </ToolPanel>
      )}
    </div>
  )
}

export default PersonalAssistant
