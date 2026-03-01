/**
 * ObjectifsTool — CRUD visuel des objectifs utilisateur
 *
 * Fetch GET /tools/objectifs au mount.
 * Edit inline + suppression avec confirmation.
 * Pas de création (les objectifs sont générés par l'agent).
 */

import { useState, useEffect } from 'react'

function buildBackendUrl() {
  return `http://${window.location.hostname}:8000`
}

const URGENCE_OPTIONS = ['haute', 'moyenne', 'basse']
const IMPACT_OPTIONS = ['haut', 'moyen', 'bas']

function badgeClass(level) {
  if (['haute', 'haut'].includes(level)) return 'objectifs-tool__badge--high'
  if (['moyenne', 'moyen'].includes(level)) return 'objectifs-tool__badge--medium'
  return 'objectifs-tool__badge--low'
}

function ObjectifsTool({ sessionId }) {
  const [objectifs, setObjectifs] = useState([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState(null)
  const [editForm, setEditForm] = useState({})
  const [confirmDeleteId, setConfirmDeleteId] = useState(null)

  useEffect(() => {
    fetchObjectifs()
  }, [])

  async function fetchObjectifs() {
    try {
      const res = await fetch(`${buildBackendUrl()}/tools/objectifs`)
      if (res.ok) {
        const json = await res.json()
        setObjectifs(json.objectifs || [])
      }
    } catch (e) {
      console.warn('Failed to fetch objectifs:', e)
    } finally {
      setLoading(false)
    }
  }

  function startEdit(obj) {
    setEditingId(obj.id)
    setEditForm({
      objectif: obj.objectif,
      justification: obj.justification || '',
      urgence: obj.urgence,
      impact: obj.impact,
    })
  }

  function cancelEdit() {
    setEditingId(null)
    setEditForm({})
  }

  async function saveEdit(id) {
    try {
      const res = await fetch(`${buildBackendUrl()}/tools/objectifs/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editForm),
      })
      if (res.ok) {
        const json = await res.json()
        if (json.ok && json.objectif) {
          setObjectifs(prev => prev.map(o => o.id === id ? json.objectif : o))
        }
      }
    } catch (e) {
      console.warn('Failed to update objectif:', e)
    }
    setEditingId(null)
    setEditForm({})
  }

  async function deleteObjectif(id) {
    try {
      const res = await fetch(`${buildBackendUrl()}/tools/objectifs/${id}`, {
        method: 'DELETE',
      })
      if (res.ok) {
        setObjectifs(prev => prev.filter(o => o.id !== id))
      }
    } catch (e) {
      console.warn('Failed to delete objectif:', e)
    }
    setConfirmDeleteId(null)
  }

  if (loading) {
    return (
      <div className="objectifs-tool__loading">
        <div className="objectifs-tool__spinner" />
        <span>Chargement des objectifs...</span>
      </div>
    )
  }

  if (objectifs.length === 0) {
    return (
      <div className="objectifs-tool__empty">
        Aucun objectif pour le moment.
      </div>
    )
  }

  return (
    <div className="objectifs-tool">
      {objectifs.map(obj => (
        <div key={obj.id} className="objectifs-tool__card">
          {editingId === obj.id ? (
            /* ── Mode édition ── */
            <div className="objectifs-tool__edit-form">
              <label className="objectifs-tool__edit-label">
                Objectif
                <input
                  type="text"
                  className="objectifs-tool__edit-input"
                  value={editForm.objectif}
                  onChange={e => setEditForm({ ...editForm, objectif: e.target.value })}
                />
              </label>
              <label className="objectifs-tool__edit-label">
                Justification
                <textarea
                  className="objectifs-tool__edit-textarea"
                  value={editForm.justification}
                  onChange={e => setEditForm({ ...editForm, justification: e.target.value })}
                  rows={2}
                />
              </label>
              <div className="objectifs-tool__edit-selects">
                <label className="objectifs-tool__edit-label">
                  Urgence
                  <select
                    className="objectifs-tool__edit-select"
                    value={editForm.urgence}
                    onChange={e => setEditForm({ ...editForm, urgence: e.target.value })}
                  >
                    {URGENCE_OPTIONS.map(v => <option key={v} value={v}>{v}</option>)}
                  </select>
                </label>
                <label className="objectifs-tool__edit-label">
                  Impact
                  <select
                    className="objectifs-tool__edit-select"
                    value={editForm.impact}
                    onChange={e => setEditForm({ ...editForm, impact: e.target.value })}
                  >
                    {IMPACT_OPTIONS.map(v => <option key={v} value={v}>{v}</option>)}
                  </select>
                </label>
              </div>
              <div className="objectifs-tool__edit-actions">
                <button className="objectifs-tool__btn objectifs-tool__btn--save" onClick={() => saveEdit(obj.id)}>
                  Enregistrer
                </button>
                <button className="objectifs-tool__btn objectifs-tool__btn--cancel" onClick={cancelEdit}>
                  Annuler
                </button>
              </div>
            </div>
          ) : (
            /* ── Mode lecture ── */
            <>
              <div className="objectifs-tool__card-header">
                <span className="objectifs-tool__rang">#{obj.rang}</span>
                <span className="objectifs-tool__titre">{obj.objectif}</span>
              </div>
              <div className="objectifs-tool__badges">
                <span className={`objectifs-tool__badge ${badgeClass(obj.urgence)}`}>
                  Urgence : {obj.urgence}
                </span>
                <span className={`objectifs-tool__badge ${badgeClass(obj.impact)}`}>
                  Impact : {obj.impact}
                </span>
                {obj.tool_type && (
                  <span className="objectifs-tool__badge objectifs-tool__badge--tool">
                    {obj.tool_type}
                  </span>
                )}
              </div>
              {obj.justification && (
                <p className="objectifs-tool__justification">{obj.justification}</p>
              )}
              {obj.raison && (
                <p className="objectifs-tool__raison">
                  <strong>Outil :</strong> {obj.raison}
                </p>
              )}
              <div className="objectifs-tool__card-actions">
                <button className="objectifs-tool__btn objectifs-tool__btn--edit" onClick={() => startEdit(obj)}>
                  Modifier
                </button>
                {confirmDeleteId === obj.id ? (
                  <span className="objectifs-tool__confirm-delete">
                    Confirmer ?{' '}
                    <button className="objectifs-tool__btn objectifs-tool__btn--danger" onClick={() => deleteObjectif(obj.id)}>
                      Oui
                    </button>
                    <button className="objectifs-tool__btn objectifs-tool__btn--cancel" onClick={() => setConfirmDeleteId(null)}>
                      Non
                    </button>
                  </span>
                ) : (
                  <button className="objectifs-tool__btn objectifs-tool__btn--delete" onClick={() => setConfirmDeleteId(obj.id)}>
                    Supprimer
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      ))}
    </div>
  )
}

export default ObjectifsTool
