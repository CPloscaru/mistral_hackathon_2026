/**
 * CRMTool - Clients & Facturation with drag-and-drop JSON import
 *
 * Drop zone for JSON files -> POST /tools/crm/import (agent parsing)
 * Client cards + factures table with colored statut badges
 * Stats: total CA, factures en attente, taux de recouvrement
 * Relance column + modal for sending reminders
 */

import { useState, useEffect, useRef, useCallback } from 'react'


function buildBackendUrl() {
  return `http://${window.location.hostname}:8000`
}

const STATUT_LABELS = {
  payee: 'Payée',
  en_attente: 'En attente',
  en_retard: 'En retard',
}

function CRMTool({ sessionId }) {
  const [clients, setClients] = useState([])
  const [factures, setFactures] = useState([])
  const [loading, setLoading] = useState(true)
  const [importing, setImporting] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const fileInputRef = useRef(null)
  const dropzoneRef = useRef(null)

  // Relances state
  const [relances, setRelances] = useState([])
  const [relanceModal, setRelanceModal] = useState(null) // facture object or null

  useEffect(() => {
    if (!sessionId) return
    Promise.all([
      fetch(`${buildBackendUrl()}/tools/crm?session_id=${sessionId}`).then(r => r.json()),
      fetch(`${buildBackendUrl()}/tools/crm/relances?session_id=${sessionId}`).then(r => r.json()),
    ])
      .then(([crmData, relancesData]) => {
        setClients(crmData.clients || [])
        setFactures(crmData.factures || [])
        setRelances(relancesData.relances || [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [sessionId])

  const handleImport = useCallback(async (jsonContent) => {
    setImporting(true)
    try {
      let parsed
      if (typeof jsonContent === 'string') {
        parsed = JSON.parse(jsonContent)
      } else {
        parsed = jsonContent
      }
      const facturesArray = Array.isArray(parsed) ? parsed : [parsed]

      const res = await fetch(`${buildBackendUrl()}/tools/crm/import`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, factures: facturesArray }),
      })
      const data = await res.json()
      setClients(data.clients || [])
      setFactures(data.factures || [])
    } catch (e) {
      console.error('Import failed:', e)
    } finally {
      setImporting(false)
    }
  }, [sessionId])

  // Drag-and-drop handlers via React events + global blocker that skips dropzone
  useEffect(() => {
    function blockAll(e) {
      // Don't block if the target is inside the dropzone
      if (dropzoneRef.current && dropzoneRef.current.contains(e.target)) return
      e.preventDefault()
    }
    window.addEventListener('dragover', blockAll)
    window.addEventListener('drop', blockAll)
    return () => {
      window.removeEventListener('dragover', blockAll)
      window.removeEventListener('drop', blockAll)
    }
  }, [])

  function handleDragEnter(e) {
    e.preventDefault()
    setDragActive(true)
  }

  function handleDragOver(e) {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
  }

  function handleDragLeave(e) {
    e.preventDefault()
    // Only deactivate if leaving the dropzone itself
    if (!dropzoneRef.current.contains(e.relatedTarget)) {
      setDragActive(false)
    }
  }

  function handleDrop(e) {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    const file = e.dataTransfer.files[0]
    if (!file) return

    if (file.type === 'application/json' || file.name.endsWith('.json')) {
      const reader = new FileReader()
      reader.onload = (ev) => handleImport(ev.target.result)
      reader.readAsText(file)
    }
  }

  function handleFileSelect(e) {
    const file = e.target.files[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (ev) => handleImport(ev.target.result)
      reader.readAsText(file)
    }
  }

  // Relance helpers
  function getRelanceStatus(factureId) {
    const factureRelances = relances.filter(r => r.facture_id === factureId)
    if (factureRelances.length === 0) return 'none'
    if (factureRelances.some(r => r.statut === 'envoyee')) return 'envoyee'
    if (factureRelances.some(r => r.statut === 'brouillon')) return 'brouillon'
    return 'none'
  }

  async function handleSendRelance(relanceId) {
    try {
      const res = await fetch(`${buildBackendUrl()}/tools/crm/relances/${relanceId}/send`, {
        method: 'POST',
      })
      const data = await res.json()
      if (data.ok) {
        setRelances(prev => prev.map(r => r.id === relanceId ? { ...r, statut: 'envoyee', date_envoi: data.relance?.date_envoi } : r))
        setRelanceModal(null)
      }
    } catch (e) {
      console.error('Send relance failed:', e)
    }
  }

  async function handleDeleteRelance(relanceId) {
    try {
      const res = await fetch(`${buildBackendUrl()}/tools/crm/relances/${relanceId}`, {
        method: 'DELETE',
      })
      const data = await res.json()
      if (data.ok) {
        setRelances(prev => prev.filter(r => r.id !== relanceId))
      }
    } catch (e) {
      console.error('Delete relance failed:', e)
    }
  }

  if (loading) {
    return <div className="crm-tool__empty">Chargement...</div>
  }

  // Stats
  const totalCA = factures.reduce((sum, f) => sum + (f.montant || 0), 0)
  const enAttente = factures.filter(f => f.statut === 'en_attente')
  const payees = factures.filter(f => f.statut === 'payee')
  const montantEnAttente = enAttente.reduce((sum, f) => sum + (f.montant || 0), 0)
  const tauxRecouvrement = factures.length > 0
    ? Math.round((payees.length / factures.length) * 100)
    : 0

  // Map client_id to client name
  const clientMap = {}
  clients.forEach(c => { clientMap[c.id] = c })

  // Count factures per client
  const facturesPerClient = {}
  factures.forEach(f => {
    if (f.client_id) {
      facturesPerClient[f.client_id] = (facturesPerClient[f.client_id] || 0) + 1
    }
  })

  // Modal facture relances
  const modalRelances = relanceModal
    ? relances.filter(r => r.facture_id === relanceModal.id)
    : []

  return (
    <div>
      {/* Drop zone */}
      <div
        ref={dropzoneRef}
        className={`crm-tool__dropzone ${dragActive ? 'crm-tool__dropzone--active' : ''}`}
        onClick={() => fileInputRef.current?.click()}
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className="crm-tool__dropzone-icon">{'\uD83D\uDCC2'}</div>
        <div className="crm-tool__dropzone-text">
          Dépose tes factures ici (JSON)
        </div>
        <div className="crm-tool__dropzone-hint">
          ou clique pour sélectionner un fichier
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".json"
          style={{ display: 'none' }}
          onChange={handleFileSelect}
        />
      </div>

      {importing && (
        <div className="crm-tool__importing">
          <div className="crm-tool__importing-spinner" />
          Analyse des factures en cours...
        </div>
      )}

      {/* Stats */}
      {(clients.length > 0 || factures.length > 0) && (
        <div className="crm-tool__stats">
          <div className="crm-tool__stat">
            <div className="crm-tool__stat-value">{totalCA.toLocaleString('fr-FR')} €</div>
            <div className="crm-tool__stat-label">Chiffre d'affaires total</div>
          </div>
          <div className="crm-tool__stat">
            <div className="crm-tool__stat-value">{montantEnAttente.toLocaleString('fr-FR')} €</div>
            <div className="crm-tool__stat-label">En attente de paiement</div>
          </div>
          <div className="crm-tool__stat">
            <div className="crm-tool__stat-value">{tauxRecouvrement}%</div>
            <div className="crm-tool__stat-label">Taux de recouvrement</div>
          </div>
        </div>
      )}

      {/* Clients */}
      {clients.length > 0 && (
        <>
          <h3 className="crm-tool__section-title">Clients ({clients.length})</h3>
          <div className="crm-tool__clients">
            {clients.map(client => (
              <div key={client.id} className="crm-tool__client-card">
                <div className="crm-tool__client-name">{client.nom}</div>
                {client.email && <div className="crm-tool__client-email">{client.email}</div>}
                {client.secteur && <div className="crm-tool__client-secteur">{client.secteur}</div>}
                <div className="crm-tool__client-factures-count">
                  {facturesPerClient[client.id] || 0} facture(s)
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Factures */}
      {factures.length > 0 && (
        <>
          <h3 className="crm-tool__section-title">Factures ({factures.length})</h3>
          <div className="crm-tool__factures-wrapper">
          <table className="crm-tool__factures-table">
            <thead>
              <tr>
                <th>N°</th>
                <th>Client</th>
                <th>Montant</th>
                <th>Émission</th>
                <th>Échéance</th>
                <th>Statut</th>
                <th>Relance</th>
              </tr>
            </thead>
            <tbody>
              {factures.map(f => {
                const relStatus = getRelanceStatus(f.id)
                const isPaid = f.statut === 'payee'
                return (
                  <tr key={f.id}>
                    <td>{f.numero}</td>
                    <td>{clientMap[f.client_id]?.nom || '—'}</td>
                    <td>{(f.montant || 0).toLocaleString('fr-FR')} {f.devise || '€'}</td>
                    <td>{f.date_emission || '—'}</td>
                    <td>{f.date_echeance || '—'}</td>
                    <td>
                      <span className={`crm-tool__badge crm-tool__badge--${f.statut}`}>
                        {STATUT_LABELS[f.statut] || f.statut}
                      </span>
                    </td>
                    <td>
                      {isPaid ? (
                        <span className="crm-tool__relance-na">N/A</span>
                      ) : (
                        <button
                          className={`crm-tool__relance-btn crm-tool__relance-btn--${relStatus}`}
                          onClick={() => setRelanceModal(f)}
                          title={
                            relStatus === 'envoyee' ? 'Relance envoyée' :
                            relStatus === 'brouillon' ? 'Brouillon de relance' :
                            'Aucune relance'
                          }
                        >
                          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                            <path d="M2 3h12v10H2V3zm0 0l6 5 6-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          </div>
        </>
      )}

      {clients.length === 0 && factures.length === 0 && !importing && (
        <div className="crm-tool__empty">
          Aucun client ni facture pour le moment. Dépose un fichier JSON pour commencer.
        </div>
      )}

      {/* Relance Modal */}
      {relanceModal && (
        <div className="crm-tool__modal-overlay" onClick={() => setRelanceModal(null)}>
          <div className="crm-tool__modal" onClick={e => e.stopPropagation()}>
            <div className="crm-tool__modal-header">
              <h3>Relance — {relanceModal.numero} / {clientMap[relanceModal.client_id]?.nom || 'Client'}</h3>
              <button className="crm-tool__modal-close" onClick={() => setRelanceModal(null)}>×</button>
            </div>
            <div className="crm-tool__modal-body">
              {modalRelances.length === 0 ? (
                <p className="crm-tool__modal-empty">
                  Aucune relance pour cette facture. Demande à Marc de générer une relance dans le chat.
                </p>
              ) : (
                modalRelances.map(rel => (
                  <div key={rel.id} className="crm-tool__relance-card">
                    <div className="crm-tool__relance-meta">
                      <span className={`crm-tool__badge crm-tool__badge--relance-${rel.statut}`}>
                        {rel.statut === 'envoyee' ? 'Envoyée' : rel.statut === 'brouillon' ? 'Brouillon' : rel.statut}
                      </span>
                      <span className="crm-tool__relance-date">
                        {rel.date_envoi ? `Envoyée le ${rel.date_envoi}` : `Créée le ${rel.date_creation}`}
                      </span>
                    </div>
                    <div className="crm-tool__relance-field">
                      <label>Destinataire</label>
                      <div>{clientMap[rel.client_id]?.email || '—'}</div>
                    </div>
                    <div className="crm-tool__relance-field">
                      <label>Objet</label>
                      <div>{rel.objet}</div>
                    </div>
                    <div className="crm-tool__relance-field">
                      <label>Corps</label>
                      <div className="crm-tool__relance-corps">{rel.corps}</div>
                    </div>
                    {rel.statut === 'brouillon' && (
                      <div className="crm-tool__relance-actions">
                        <button
                          className="crm-tool__relance-send-btn"
                          onClick={() => handleSendRelance(rel.id)}
                        >
                          Envoyer
                        </button>
                        <button
                          className="crm-tool__relance-delete-btn"
                          onClick={() => handleDeleteRelance(rel.id)}
                        >
                          Supprimer
                        </button>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default CRMTool
