/**
 * PersonalAssistant - Page post-onboarding avec stepper animé + chat central + dock
 *
 * Flux :
 * 1. Mount: fetch session info → lance le workflow via POST /chat/onboarding
 * 2. Stepper animé : 3 étapes (analyse, priorités, interface)
 * 3. Transition : stepper fade out → dock slide in + chat central
 * 4. Premier message assistant = résumé de ce qui a été fait
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useSession } from '../hooks/useSession'
import Dock from './Dock'
import ToolShowcase from './ToolShowcase'
import ToolPanel from './ToolPanel'
import ChatInput from './ChatInput'
import { getComponent } from './ComponentRegistry'
import '../styles/dock.css'

function buildBackendUrl() {
  const hostname = window.location.hostname
  return `http://${hostname}:8000`
}

const BACKEND_URL = buildBackendUrl()
const MIN_STEP_DISPLAY_MS = 2500 // temps minimum d'affichage par étape

function PersonalAssistant() {
  const { sessionId, loading: sessionLoading } = useSession()

  const [phase, setPhase] = useState('loading') // loading | stepper | showcase | ready
  const [prenom, setPrenom] = useState(null)
  const [selectedTool, setSelectedTool] = useState(null)

  // Stepper state
  const [steps, setSteps] = useState([
    { step: 1, label: 'Analyse de votre profil', status: 'pending', summary: '' },
    { step: 2, label: 'Identification de vos priorités', status: 'pending', summary: '' },
    { step: 3, label: 'Mise en place de votre interface', status: 'pending', summary: '' },
  ])
  const [stepperExiting, setStepperExiting] = useState(false)

  // A2UI — active components from backend
  const [activeComponents, setActiveComponents] = useState([])

  // Chat central
  const [chatMessages, setChatMessages] = useState([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [answeredInteractions, setAnsweredInteractions] = useState({}) // msgIndex -> choiceId
  const chatEndRef = useRef(null)

  // Showcase — tool descriptions from LLM
  const [toolDescriptions, setToolDescriptions] = useState([])
  const welcomeMessageRef = useRef(null)

  // Dock
  const [dockVisible, setDockVisible] = useState(false)
  const [bouncingTool, setBouncingTool] = useState(null)
  const bounceTimerRef = useRef(null)

  const startedRef = useRef(false)
  const stepTimestamps = useRef({})

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages])

  // Fetch session info + trigger workflow
  useEffect(() => {
    if (sessionLoading || !sessionId || startedRef.current) return
    startedRef.current = true

    async function init() {
      // Fetch session info (prenom + cached active_components)
      try {
        const res = await fetch(`${BACKEND_URL}/chat/session-info?session_id=${sessionId}`)
        if (res.ok) {
          const data = await res.json()
          console.log('[PA] session-info response:', JSON.stringify(data).slice(0, 300))

          // Session introuvable côté backend — ne pas lancer le workflow
          if (data.error) {
            console.warn('[PA] Session introuvable, pas de workflow à lancer')
            setPhase('ready')
            return
          }

          if (data.prenom) setPrenom(data.prenom)

          // Si déjà post-onboarding, skip le stepper
          if (data.active_components && data.active_components.length > 0 && data.maturity_level >= 2) {
            console.log('[PA] Session déjà complète, skip stepper')
            setActiveComponents(data.active_components)
            setDockVisible(true)
            setPhase('ready')

            // Charger le welcome message depuis l'historique
            const histRes = await fetch(`${BACKEND_URL}/chat/history?session_id=${sessionId}&chat_type=main`)
            if (histRes.ok) {
              const histData = await histRes.json()
              if (histData.messages && histData.messages.length > 0) {
                setChatMessages(histData.messages.map(m => ({ role: m.role, content: m.content })))
              }
            }
            return
          }
        }
      } catch (e) {
        console.warn('[PA] Failed to fetch session info:', e)
        setPhase('ready')
        return
      }

      // Lancer le workflow
      setPhase('stepper')
      await runWorkflow()
    }
    init()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, sessionLoading])

  async function waitMinStepTime(stepNum) {
    const started = stepTimestamps.current[stepNum]
    if (!started) return
    const elapsed = Date.now() - started
    const remaining = MIN_STEP_DISPLAY_MS - elapsed
    if (remaining > 0) {
      await new Promise(r => setTimeout(r, remaining))
    }
  }

  async function runWorkflow() {
    try {
      const response = await fetch(`${BACKEND_URL}/chat/onboarding?session_id=${sessionId}`, {
        method: 'POST',
      })

      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let currentEventType = null
      let currentDataLines = []
      const collectedComponents = []
      let welcomeMessage = null

      // Queue pour traiter les événements avec les délais min
      const eventQueue = []
      let processing = false

      async function processEvent(eventType, eventData) {
        if (eventType === 'step_update') {
          try {
            const data = JSON.parse(eventData)
            stepTimestamps.current[data.step] = Date.now()
            setSteps(prev => prev.map(s =>
              s.step === data.step ? { ...s, status: 'in_progress' } : s
            ))
          } catch { /* ignore */ }
        } else if (eventType === 'step_done') {
          try {
            const data = JSON.parse(eventData)
            // Attendre le temps minimum d'affichage
            await waitMinStepTime(data.step)
            setSteps(prev => prev.map(s =>
              s.step === data.step ? { ...s, status: 'done', summary: data.summary || '' } : s
            ))
          } catch { /* ignore */ }
        } else if (eventType === 'ui_component') {
          try {
            const comp = JSON.parse(eventData)
            if (comp.action === 'activate') {
              collectedComponents.push(comp)
            }
          } catch { /* ignore */ }
        } else if (eventType === 'welcome_message') {
          try {
            const data = JSON.parse(eventData)
            welcomeMessage = data.content
          } catch { /* ignore */ }
        } else if (eventType === 'done') {
          // Attendre le temps min de la dernière étape
          await waitMinStepTime(3)

          // Appliquer les composants collectés
          if (collectedComponents.length > 0) {
            setActiveComponents(collectedComponents)
          }

          // Sauvegarder le welcome message pour après le showcase
          if (welcomeMessage) {
            welcomeMessageRef.current = welcomeMessage
          }

          // Transition stepper → showcase
          setStepperExiting(true)
          await new Promise(r => setTimeout(r, 600))
          setPhase('showcase')

          // Lancer le call tool-showcase en arrière-plan
          fetchToolDescriptions(collectedComponents)
        }
      }

      async function processQueue() {
        if (processing) return
        processing = true
        while (eventQueue.length > 0) {
          const { type, data } = eventQueue.shift()
          await processEvent(type, data)
        }
        processing = false
      }

      function processBuffer() {
        const normalized = buffer.replace(/\r\n/g, '\n')
        const lines = normalized.split('\n')
        const lastLine = lines.pop()
        buffer = lastLine === undefined ? '' : lastLine

        for (const line of lines) {
          if (line === '') {
            if (currentEventType && currentDataLines.length > 0) {
              const eventData = currentDataLines.join('\n')
              eventQueue.push({ type: currentEventType, data: eventData })
              processQueue()
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

      // Attendre que la queue finisse
      while (eventQueue.length > 0 || processing) {
        await new Promise(r => setTimeout(r, 100))
      }

    } catch (err) {
      console.error('Workflow error:', err)
      setPhase('ready')
    }
  }

  async function fetchToolDescriptions(components) {
    try {
      const response = await fetch(`${BACKEND_URL}/chat/tool-showcase?session_id=${sessionId}`, {
        method: 'POST',
      })
      if (!response.ok) {
        // Fallback: utiliser les composants sans description
        setToolDescriptions(components.map(c => ({
          type: c.type, title: c.title, icon: c.icon, description: '',
        })))
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let currentEventType = null
      let currentDataLines = []
      const descriptions = []

      function processBuffer() {
        const normalized = buffer.replace(/\r\n/g, '\n')
        const lines = normalized.split('\n')
        const lastLine = lines.pop()
        buffer = lastLine === undefined ? '' : lastLine

        for (const line of lines) {
          if (line === '') {
            if (currentEventType && currentDataLines.length > 0) {
              const eventData = currentDataLines.join('\n')
              if (currentEventType === 'tool_description') {
                try {
                  const desc = JSON.parse(eventData)
                  descriptions.push(desc)
                  setToolDescriptions([...descriptions])
                } catch { /* ignore */ }
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
      console.error('Tool showcase fetch error:', err)
      // Fallback
      setToolDescriptions(components.map(c => ({
        type: c.type, title: c.title, icon: c.icon, description: '',
      })))
    }
  }

  const handleShowcaseComplete = useCallback(async () => {
    setPhase('ready')
    setDockVisible(true)

    // Charger l'historique complet (onboarding + welcome) depuis la DB
    try {
      const histRes = await fetch(`${BACKEND_URL}/chat/history?session_id=${sessionId}&chat_type=main`)
      if (histRes.ok) {
        const histData = await histRes.json()
        if (histData.messages && histData.messages.length > 0) {
          setChatMessages(histData.messages.map(m => ({ role: m.role, content: m.content })))
          return
        }
      }
    } catch (e) {
      console.warn('[PA] Failed to load history after showcase:', e)
    }

    // Fallback: juste le welcome message
    if (welcomeMessageRef.current) {
      setChatMessages([{ role: 'assistant', content: welcomeMessageRef.current }])
    }
  }, [sessionId])

  const handleSendMessage = useCallback(async (text) => {
    if (!text.trim() || isStreaming) return

    setChatMessages(prev => [...prev, { role: 'user', content: text }])
    setIsStreaming(true)

    try {
      const response = await fetch(`${BACKEND_URL}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: sessionId }),
      })

      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let currentEventType = null
      let currentDataLines = []
      let assistantText = ''
      let assistantMsgIndex = null

      setChatMessages(prev => {
        assistantMsgIndex = prev.length
        return [...prev, { role: 'assistant', content: '' }]
      })

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
                setChatMessages(prev => {
                  const updated = [...prev]
                  if (assistantMsgIndex !== null && assistantMsgIndex < updated.length) {
                    updated[assistantMsgIndex] = { role: 'assistant', content: assistantText }
                  }
                  return updated
                })
              } else if (currentEventType === 'interaction') {
                try {
                  const interactionData = JSON.parse(eventData)
                  if (interactionData.type === 'activate_component') {
                    // Activer un nouveau composant dans le dock
                    setActiveComponents(prev => {
                      const exists = prev.some(c => c.type === interactionData.component_type)
                      if (exists) return prev
                      return [...prev, {
                        action: 'activate',
                        type: interactionData.component_type,
                        id: interactionData.id,
                        title: interactionData.title,
                        icon: interactionData.icon,
                        data: interactionData.data,
                      }]
                    })
                  } else if (interactionData.type === 'dock_bounce') {
                    // Faire bouncer l'icône du dock
                    if (bounceTimerRef.current) clearTimeout(bounceTimerRef.current)
                    setBouncingTool(interactionData.tool_id)
                    bounceTimerRef.current = setTimeout(() => setBouncingTool(null), 5000)
                  } else {
                    setChatMessages(prev => [...prev, { role: interactionData.type === 'data_table' ? 'data_table' : 'interaction', ...interactionData }])
                  }
                } catch { /* ignore */ }
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
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Oups, une erreur est survenue. Réessaie !'
      }])
    } finally {
      setIsStreaming(false)
    }
  }, [sessionId, isStreaming])

  // Build dock tools from activeComponents
  const dockTools = activeComponents.map(c => ({
    id: c.type,
    icon: c.icon,
    label: c.title,
    tooltip: c.title,
  }))

  const displayName = prenom || 'toi'

  // Dynamic tool rendering via registry
  const renderSelectedTool = () => {
    if (!selectedTool) return null
    const entry = getComponent(selectedTool)
    const compData = activeComponents.find(c => c.type === selectedTool)
    if (!entry) return null
    const Comp = entry.component
    return (
      <ToolPanel
        tool={selectedTool}
        title={compData?.title || entry.defaultTitle}
        onClose={() => setSelectedTool(null)}
      >
        <Comp sessionId={sessionId} data={compData?.data} />
      </ToolPanel>
    )
  }

  return (
    <div className="personal-assistant">
      {/* Stepper */}
      {phase === 'stepper' && (
        <div className={`stepper-overlay ${stepperExiting ? 'stepper-overlay--exiting' : ''}`}>
          <div className="stepper">
            <h2 className="stepper__title">Préparation de ton espace, {displayName}</h2>
            <div className="stepper__steps">
              {steps.map(s => (
                <div key={s.step} className={`stepper__step stepper__step--${s.status}`}>
                  <div className="stepper__step-indicator">
                    {s.status === 'done' && (
                      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                        <path d="M4 9L7.5 12.5L14 5.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    )}
                    {s.status === 'in_progress' && (
                      <div className="stepper__spinner" />
                    )}
                    {s.status === 'pending' && (
                      <span className="stepper__step-number">{s.step}</span>
                    )}
                  </div>
                  <div className="stepper__step-content">
                    <div className="stepper__step-label">{s.label}</div>
                    {s.summary && s.status === 'done' && (
                      <div className="stepper__step-summary">{s.summary}</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Loading */}
      {phase === 'loading' && (
        <div className="stepper-overlay">
          <div className="stepper">
            <h2 className="stepper__title">Chargement...</h2>
          </div>
        </div>
      )}

      {/* Showcase — présentation animée des outils */}
      {phase === 'showcase' && toolDescriptions.length > 0 && (
        <ToolShowcase
          tools={toolDescriptions}
          prenom={prenom}
          onComplete={handleShowcaseComplete}
        />
      )}

      {/* Interface principale — chat central + dock */}
      {phase === 'ready' && (
        <>
          <div className="personal-assistant__header">
            <h1>Assistant personnel de {displayName}</h1>
          </div>

          <div className={`personal-assistant__chat ${selectedTool ? 'personal-assistant__chat--hidden' : ''}`}>
            <div className="personal-assistant__messages">
              {chatMessages.map((msg, i) => (
                msg.role === 'data_table' ? (
                  <div key={i} className="personal-assistant__msg personal-assistant__msg--data-table">
                    <div className="data-table__title">{msg.title}</div>
                    <table className="data-table__table">
                      <thead>
                        <tr>{(msg.columns || []).map((col, j) => <th key={j}>{col}</th>)}</tr>
                      </thead>
                      <tbody>
                        {(msg.rows || []).map((row, j) => (
                          <tr key={j}>{row.map((cell, k) => <td key={k}>{cell}</td>)}</tr>
                        ))}
                      </tbody>
                    </table>
                    {msg.summary && <div className="data-table__summary">{msg.summary}</div>}
                  </div>
                ) : msg.role === 'interaction' ? (
                  <div key={i} className="personal-assistant__msg personal-assistant__msg--interaction">
                    <div className="interaction__question">{msg.question}</div>
                    <div className="interaction__choices">
                      {(msg.choices || []).map(choice => {
                        const answered = answeredInteractions[i]
                        const isSelected = answered === choice.id
                        return (
                          <button
                            key={choice.id}
                            className={`interaction__choice-btn${isSelected ? ' interaction__choice-btn--selected' : ''}`}
                            onClick={() => {
                              setAnsweredInteractions(prev => ({ ...prev, [i]: choice.id }))
                              handleSendMessage(choice.label)
                            }}
                            disabled={isStreaming || answered !== undefined}
                          >
                            {choice.label}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                ) : (
                  <div key={i} className={`personal-assistant__msg personal-assistant__msg--${msg.role}`}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                  </div>
                )
              ))}
              <div ref={chatEndRef} />
            </div>
            <ChatInput onSend={handleSendMessage} disabled={isStreaming} />
          </div>
        </>
      )}

      {/* Dock — slides in after stepper */}
      <Dock
        visible={dockVisible}
        tools={dockTools}
        activeTool={selectedTool}
        bouncingTool={bouncingTool}
        onSelectTool={(toolId) => {
          if (toolId === bouncingTool) {
            setBouncingTool(null)
            if (bounceTimerRef.current) clearTimeout(bounceTimerRef.current)
          }
          setSelectedTool(toolId)
        }}
      />

      {/* Tool Panel — dynamic rendering via ComponentRegistry */}
      {renderSelectedTool()}
    </div>
  )
}

export default PersonalAssistant
