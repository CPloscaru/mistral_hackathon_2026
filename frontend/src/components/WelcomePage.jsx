/**
 * WelcomePage - Landing page avec avatar Kameleon et transition portail
 */

import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import '../styles/welcome.css'

function WelcomePage() {
  const navigate = useNavigate()
  const [launching, setLaunching] = useState(false)

  const handleLaunch = useCallback(() => {
    if (launching) return
    setLaunching(true)
    // Navigate after the portal animation completes
    setTimeout(() => navigate('/chat'), 750)
  }, [launching, navigate])

  return (
    <div className={`welcome${launching ? ' welcome--launching' : ''}`}>
      {/* Ambient background rings */}
      <div className="welcome__ring welcome__ring--1" />
      <div className="welcome__ring welcome__ring--2" />
      <div className="welcome__ring welcome__ring--3" />

      <div className="welcome__content">
        <div className="welcome__avatar-wrap">
          <div className="welcome__avatar-glow" />
          <div className="welcome__avatar" role="img" aria-label="Avatar Kameleon">
            🦎
          </div>
        </div>

        <h1 className="welcome__title">Kameleon</h1>
        <p className="welcome__subtitle">
          Votre assistant IA pour piloter votre activité
        </p>

        <button
          className="welcome__cta"
          onClick={handleLaunch}
          disabled={launching}
        >
          <span className="welcome__cta-label">Commencer</span>
          <span className="welcome__cta-shimmer" />
        </button>
      </div>

      {/* Full-screen portal overlay */}
      <div className="welcome__portal" />
    </div>
  )
}

export default WelcomePage
