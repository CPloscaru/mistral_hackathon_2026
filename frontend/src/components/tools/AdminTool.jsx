/**
 * AdminTool - Interactive administrative checklist
 *
 * Fetches checklist from GET /tools/admin-checklist
 * Toggle items via POST /tools/admin-checklist/toggle
 * Progress bar + external links
 */

import { useState, useEffect } from 'react'

function buildBackendUrl() {
  return `http://${window.location.hostname}:8000`
}

function AdminTool({ sessionId }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!sessionId) return
    fetch(`${buildBackendUrl()}/tools/admin-checklist?session_id=${sessionId}`)
      .then(r => r.json())
      .then(data => {
        setItems(data.items || [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [sessionId])

  async function handleToggle(itemId) {
    // Optimistic update
    setItems(prev => prev.map(it =>
      it.id === itemId ? { ...it, done: !it.done } : it
    ))

    try {
      const res = await fetch(`${buildBackendUrl()}/tools/admin-checklist/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: itemId }),
      })
      const data = await res.json()
      setItems(prev => prev.map(it =>
        it.id === itemId ? { ...it, done: data.done } : it
      ))
    } catch (e) {
      // Revert on error
      setItems(prev => prev.map(it =>
        it.id === itemId ? { ...it, done: !it.done } : it
      ))
    }
  }

  if (loading) {
    return <div className="crm-tool__empty">Chargement...</div>
  }

  const doneCount = items.filter(it => it.done).length
  const total = items.length
  const progress = total > 0 ? (doneCount / total) * 100 : 0

  return (
    <div>
      <div className="admin-tool__progress">
        <span className="admin-tool__progress-label">
          {doneCount}/{total} {total <= 1 ? 'étape complétée' : 'étapes complétées'}
        </span>
        <div className="admin-tool__progress-bar">
          <div
            className="admin-tool__progress-fill"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {items.length === 0 ? (
        <div className="crm-tool__empty">Aucune démarche administrative pour le moment.</div>
      ) : (
        items.map(item => (
          <div
            key={item.id}
            className={`admin-tool__item ${item.done ? 'admin-tool__item--done' : ''}`}
          >
            <input
              type="checkbox"
              className="admin-tool__checkbox"
              checked={item.done}
              onChange={() => handleToggle(item.id)}
            />
            <div className="admin-tool__content">
              <div className="admin-tool__label">{item.label}</div>
              {item.description && (
                <div className="admin-tool__description">{item.description}</div>
              )}
              {item.url && (
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="admin-tool__link"
                >
                  Accéder au site officiel ↗
                </a>
              )}
            </div>
          </div>
        ))
      )}
    </div>
  )
}

export default AdminTool
