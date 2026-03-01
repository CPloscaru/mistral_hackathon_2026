/**
 * Dock - macOS-style horizontal dock fixed to the bottom
 *
 * Slides in after the SMART objective typewriter completes.
 * Dynamically renders tool icons from the `tools` prop (A2UI pattern).
 */

import { useState, useEffect, useRef, useCallback } from 'react'

const STAGGER_DELAY = 200 // ms between each icon appearing

function Dock({ visible, tools = [], activeTool, bouncingTool, onSelectTool }) {
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
    if (!visible || tools.length === 0) {
      setVisibleItems([])
      return
    }

    // Stagger the icons appearing one by one
    tools.forEach((tool, i) => {
      setTimeout(() => {
        setVisibleItems(prev => [...prev, tool.id])
      }, i * STAGGER_DELAY)
    })
  }, [visible, tools])

  if (!visible || tools.length === 0) return null

  return (
    <div className="dock" ref={dockRef}>
      {tools.map(tool => (
        <div
          key={tool.id}
          className={`dock__item ${visibleItems.includes(tool.id) ? 'dock__item--visible' : ''} ${activeTool === tool.id ? 'dock__item--active' : ''} ${bouncingTool === tool.id ? 'dock__item--bouncing' : ''}`}
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
