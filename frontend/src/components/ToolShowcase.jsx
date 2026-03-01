/**
 * ToolShowcase — Animation de présentation des outils du dock.
 *
 * 1. Message d'intro : reveal cinématique segment par segment → glisse en haut
 * 2. Chaque outil apparaît au centre avec sa description LLM (~3.5s)
 * 3. L'outil "shrink + slide" vers le mini-dock en bas
 * 4. onComplete() quand tout est terminé
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react'

const INTRO_REVEAL_STAGGER_MS = 600  // délai entre chaque segment
const INTRO_HOLD_AFTER_REVEAL_MS = 1400 // pause après le dernier segment révélé
const INTRO_SLIDE_MS = 800       // durée de l'animation slide vers le haut
const DISPLAY_DURATION_MS = 3500 // durée d'affichage par outil
const EXIT_ANIMATION_MS = 700   // durée de l'animation de sortie

function ToolShowcase({ tools, prenom, onComplete }) {
  const [introPhase, setIntroPhase] = useState('revealing') // revealing → hold → sliding → top
  const [currentIndex, setCurrentIndex] = useState(-1)
  const [phase, setPhase] = useState('idle')
  const [dockedTools, setDockedTools] = useState([])
  const timerRef = useRef(null)

  const displayName = prenom || 'toi'

  // Segments du message — découpage sémantique pour le reveal
  const introSegments = useMemo(() => [
    `${displayName}, après analyse,`,
    `voici les outils que je te recommande`,
    `et auxquels tu auras accès dans un premier temps.`,
    `Ne t'inquiète pas, on fera évoluer tout ça`,
    `en fonction de l'évolution de ton besoin.`,
  ], [displayName])

  // Durée totale du reveal = tous les segments + hold
  const totalRevealMs = introSegments.length * INTRO_REVEAL_STAGGER_MS + INTRO_HOLD_AFTER_REVEAL_MS

  // Séquence intro
  useEffect(() => {
    if (introPhase === 'revealing') {
      const t = setTimeout(() => setIntroPhase('hold'), totalRevealMs)
      return () => clearTimeout(t)
    }
    if (introPhase === 'hold') {
      // Petit beat avant de slider
      const t = setTimeout(() => setIntroPhase('sliding'), 200)
      return () => clearTimeout(t)
    }
    if (introPhase === 'sliding') {
      const t = setTimeout(() => setIntroPhase('top'), INTRO_SLIDE_MS)
      return () => clearTimeout(t)
    }
  }, [introPhase, totalRevealMs])

  const showNext = useCallback(() => {
    setCurrentIndex(prev => {
      const next = prev + 1
      if (next >= tools.length) {
        setTimeout(() => onComplete(), 400)
        return prev
      }
      setPhase('entering')
      return next
    })
  }, [tools.length, onComplete])

  // Démarrer les outils une fois l'intro en haut
  useEffect(() => {
    if (introPhase === 'top' && tools.length > 0 && currentIndex === -1) {
      const t = setTimeout(() => showNext(), 400)
      return () => clearTimeout(t)
    }
  }, [introPhase, tools.length, currentIndex, showNext])

  // Cycle d'animation pour chaque outil
  useEffect(() => {
    if (phase === 'entering') {
      const t = setTimeout(() => setPhase('visible'), 100)
      return () => clearTimeout(t)
    }
    if (phase === 'visible') {
      timerRef.current = setTimeout(() => setPhase('exiting'), DISPLAY_DURATION_MS)
      return () => clearTimeout(timerRef.current)
    }
    if (phase === 'exiting') {
      const t = setTimeout(() => {
        setDockedTools(prev => [...prev, tools[currentIndex]])
        setPhase('idle')
        showNext()
      }, EXIT_ANIMATION_MS)
      return () => clearTimeout(t)
    }
  }, [phase, currentIndex, tools, showNext])

  const currentTool = currentIndex >= 0 && currentIndex < tools.length ? tools[currentIndex] : null

  // Déterminer la classe de transition pour le conteneur intro
  const introContainerClass = introPhase === 'sliding' || introPhase === 'top'
    ? 'tool-showcase__intro tool-showcase__intro--top'
    : 'tool-showcase__intro tool-showcase__intro--center'

  return (
    <div className="tool-showcase">
      {/* Message d'intro avec reveal segment par segment */}
      <div className={introContainerClass}>
        <p className="tool-showcase__intro-text">
          {introSegments.map((segment, i) => (
            <span
              key={i}
              className="tool-showcase__intro-segment"
              style={{ animationDelay: `${i * INTRO_REVEAL_STAGGER_MS}ms` }}
            >
              {segment}{' '}
            </span>
          ))}
        </p>
      </div>

      {/* Outil courant au centre */}
      {currentTool && phase !== 'idle' && (
        <div className={`tool-showcase__center tool-showcase__center--${phase}`}>
          <div className="dock__icon tool-showcase__icon-large">{currentTool.icon}</div>
          <h2 className="tool-showcase__title">{currentTool.title}</h2>
          {currentTool.description && (
            <p className="tool-showcase__description">{currentTool.description}</p>
          )}
        </div>
      )}

      {/* Mini-dock progressif en bas */}
      {dockedTools.length > 0 && (
        <div className="tool-showcase__dock">
          {dockedTools.map(tool => (
            <div key={tool.type} className="tool-showcase__dock-item">
              <div className="dock__icon">{tool.icon}</div>
              <span className="dock__label">{tool.title}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default ToolShowcase
