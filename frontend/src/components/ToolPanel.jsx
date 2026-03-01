/**
 * ToolPanel - Full-screen overlay panel that opens above the dock
 *
 * Generic container that renders the selected tool component with
 * slide-in animation and a close button. Title comes from the A2UI registry.
 */

import { useState, useEffect } from 'react'

function ToolPanel({ tool, title, onClose, children }) {
  const [closing, setClosing] = useState(false)

  useEffect(() => {
    setClosing(false)
  }, [tool])

  function handleClose() {
    setClosing(true)
    setTimeout(() => onClose(), 250)
  }

  if (!tool) return null

  return (
    <div className={`tool-panel-overlay ${closing ? 'tool-panel-overlay--closing' : ''}`}>
      <div className="tool-panel">
        <div className="tool-panel__header">
          <h2 className="tool-panel__title">{title || tool}</h2>
          <button className="tool-panel__close" onClick={handleClose} aria-label="Fermer">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="3" y1="3" x2="13" y2="13" />
              <line x1="13" y1="3" x2="3" y2="13" />
            </svg>
          </button>
        </div>
        <div className="tool-panel__content">
          {children}
        </div>
      </div>
    </div>
  )
}

export default ToolPanel
