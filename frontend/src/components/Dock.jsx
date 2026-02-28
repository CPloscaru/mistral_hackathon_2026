/**
 * Dock - macOS-style vertical dock fixed to the right side
 *
 * Slides in after the SMART objective typewriter completes.
 * 3 tool icons with staggered animation, hover scale, and active glow.
 */

import { useState, useEffect, useRef, useCallback } from 'react'

const TOOLS = [
  { id: 'admin', icon: '\uD83D\uDCCB', label: 'Administratif', tooltip: 'Checklist administrative' },
  { id: 'calendar', icon: '\uD83D\uDCC5', label: 'Calendrier', tooltip: 'Calendrier des actions' },
  { id: 'crm', icon: '\uD83D\uDCBC', label: 'Clients', tooltip: 'Clients & Facturation' },
]

const STAGGER_DELAY = 200 // ms between each icon appearing

function Dock({ visible, activeTool, onSelectTool }) {
  const [visibleItems, setVisibleItems] = useState([])
  const roRef = useRef(null)

  // Callback ref: observe dock height as soon as DOM node mounts
  const dockRef = useCallback((node) => {
    if (roRef.current) {
      roRef.current.disconnect()
      roRef.current = null
    }
    if (!node) return
    const ro = new ResizeObserver(([entry]) => {
      document.documentElement.style.setProperty(
        '--dock-height',
        `${entry.borderBoxSize[0].blockSize}px`
      )
    })
    ro.observe(node)
    roRef.current = ro
  }, [])

  useEffect(() => {
    if (!visible) {
      setVisibleItems([])
      return
    }

    // Stagger the icons appearing one by one
    TOOLS.forEach((tool, i) => {
      setTimeout(() => {
        setVisibleItems(prev => [...prev, tool.id])
      }, i * STAGGER_DELAY)
    })
  }, [visible])

  if (!visible) return null

  return (
    <div className="dock" ref={dockRef}>
      {TOOLS.map(tool => (
        <div
          key={tool.id}
          className={`dock__item ${visibleItems.includes(tool.id) ? 'dock__item--visible' : ''} ${activeTool === tool.id ? 'dock__item--active' : ''}`}
          data-tooltip={tool.tooltip}
          onClick={() => onSelectTool(activeTool === tool.id ? null : tool.id)}
        >
          <div className="dock__icon">{tool.icon}</div>
          <span className="dock__label">{tool.label}</span>
        </div>
      ))}
    </div>
  )
}

export default Dock
