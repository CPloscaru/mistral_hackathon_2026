/**
 * PrevisionsTool - Dashboard prévisions financières
 *
 * 4 zones :
 * 1. KPIs (3 cards) : objectif net, CA brut cible, missions restantes
 * 2. Graphiques : barres CA + donut répartition charges
 * 3. Tableau détail du calcul
 * 4. Barre de progression
 *
 * Props:
 * - sessionId: identifiant de session
 * - data: données inline (depuis SSE) — sinon fetch /tools/previsions
 */

import { useState, useEffect } from 'react'
import '../../styles/previsions.css'

function buildBackendUrl() {
  return `http://${window.location.hostname}:8000`
}

function PrevisionsTool({ sessionId, data: inlineData }) {
  const [previsions, setPrevisions] = useState(null)
  const [loading, setLoading] = useState(true)

  // Only use inline data if it contains actual previsions fields
  const validInline = inlineData && typeof inlineData.objectif_net === 'number' ? inlineData : null

  useEffect(() => {
    if (validInline) {
      setPrevisions(validInline)
      setLoading(false)
      return
    }
    if (!sessionId) {
      setLoading(false)
      return
    }

    // Always fetch from API when panel opens
    setLoading(true)
    async function fetchPrevisions() {
      try {
        const res = await fetch(`${buildBackendUrl()}/tools/previsions?session_id=${sessionId}`)
        if (res.ok) {
          const json = await res.json()
          if (json.previsions) setPrevisions(json.previsions)
        }
      } catch (e) {
        console.warn('Failed to fetch previsions:', e)
      } finally {
        setLoading(false)
      }
    }
    fetchPrevisions()
  }, [sessionId, validInline])

  if (loading) {
    return (
      <div className="prev-tool__loading">
        <div className="prev-tool__spinner" />
        <span>Calcul des prévisions en cours...</span>
      </div>
    )
  }

  if (!previsions) {
    return (
      <div className="prev-tool__empty">
        <div className="prev-tool__empty-icon">📊</div>
        <p>Aucune prévision financière disponible.</p>
        <p className="prev-tool__empty-hint">
          Demande une analyse financière dans le chat pour commencer.
        </p>
      </div>
    )
  }

  const {
    objectif_net = 0,
    ca_brut_cible = 0,
    taux_cotisations = 0,
    cotisations_montant = 0,
    ca_actuel = 0,
    ca_manquant = 0,
    tjm_moyen = 0,
    missions_restantes = 0,
    jours_restants = 0,
    details = {},
    source_cotisations = '',
    statut_juridique = '',
  } = previsions

  const progressPct = ca_brut_cible > 0 ? Math.min((ca_actuel / ca_brut_cible) * 100, 100) : 0
  const factures_payees = details.factures_payees || 0
  const factures_en_attente = details.factures_en_attente || 0
  const taux_pct = (taux_cotisations * 100).toFixed(1)
  const net_pct = ((1 - taux_cotisations) * 100).toFixed(1)

  // Donut SVG
  const donutRadius = 60
  const donutCirc = 2 * Math.PI * donutRadius
  const cotisOffset = donutCirc * (1 - taux_cotisations)

  return (
    <div className="prev-tool">
      {/* ZONE 1 — KPIs */}
      <div className="prev-tool__kpis">
        <div className="prev-tool__kpi prev-tool__kpi--green">
          <div className="prev-tool__kpi-label">Objectif net</div>
          <div className="prev-tool__kpi-value">{fmt(objectif_net)}</div>
          <div className="prev-tool__kpi-sub">avant IR</div>
        </div>
        <div className="prev-tool__kpi prev-tool__kpi--blue">
          <div className="prev-tool__kpi-label">CA brut cible</div>
          <div className="prev-tool__kpi-value">{fmt(ca_brut_cible)}</div>
          <div className="prev-tool__kpi-sub">annuel</div>
        </div>
        <div className="prev-tool__kpi prev-tool__kpi--orange">
          <div className="prev-tool__kpi-label">Missions restantes</div>
          <div className="prev-tool__kpi-value">{missions_restantes}</div>
          <div className="prev-tool__kpi-sub">~{jours_restants} jours</div>
        </div>
      </div>

      {/* ZONE 2 — Graphiques */}
      <div className="prev-tool__charts">
        {/* Bar chart */}
        <div className="prev-tool__chart-box">
          <h4 className="prev-tool__chart-title">Répartition du CA</h4>
          <div className="prev-tool__bars">
            <BarRow label="CA facturé" value={factures_payees} max={ca_brut_cible} color="#4ade80" />
            <BarRow label="En attente" value={factures_en_attente} max={ca_brut_cible} color="#fb923c" />
            <BarRow label="CA manquant" value={ca_manquant} max={ca_brut_cible} color="#f87171" />
          </div>
          <div className="prev-tool__bar-legend">
            Objectif : {fmt(ca_brut_cible)}
          </div>
        </div>

        {/* Donut chart */}
        <div className="prev-tool__chart-box">
          <h4 className="prev-tool__chart-title">Répartition charges</h4>
          <div className="prev-tool__donut-wrap">
            <svg viewBox="0 0 160 160" className="prev-tool__donut-svg">
              {/* Cotisations (background full circle) */}
              <circle
                cx="80" cy="80" r={donutRadius}
                fill="none" stroke="rgba(251, 146, 60, 0.4)" strokeWidth="20"
              />
              {/* Net (overlay partial circle) */}
              <circle
                cx="80" cy="80" r={donutRadius}
                fill="none" stroke="rgba(124, 58, 237, 0.5)" strokeWidth="20"
                strokeDasharray={`${cotisOffset} ${donutCirc}`}
                strokeDashoffset={donutCirc * 0.25}
                strokeLinecap="round"
              />
              <text x="80" y="75" textAnchor="middle" className="prev-tool__donut-amount">
                {fmt(objectif_net)}
              </text>
              <text x="80" y="95" textAnchor="middle" className="prev-tool__donut-label">
                net
              </text>
            </svg>
            <div className="prev-tool__donut-legend">
              <div className="prev-tool__legend-item">
                <span className="prev-tool__legend-dot" style={{ background: '#a78bfa' }} />
                Net ({net_pct}%)
              </div>
              <div className="prev-tool__legend-item">
                <span className="prev-tool__legend-dot" style={{ background: '#fb923c' }} />
                Cotisations ({taux_pct}%)
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ZONE 3 — Détail du calcul */}
      <div className="prev-tool__detail">
        <h4 className="prev-tool__detail-title">Détail du calcul</h4>
        <table className="prev-tool__table">
          <tbody>
            <DetailRow label="Objectif net annuel (avant IR)" value={fmt(objectif_net)} />
            <DetailRow label="Statut juridique" value={statut_juridique || '—'} />
            <DetailRow label={`Taux cotisations sociales`} value={`${taux_pct} %`} />
            <DetailRow label="CA brut nécessaire" value={fmt(ca_brut_cible)} highlight />
            <DetailRow label="CA actuel (factures)" value={fmt(ca_actuel)} />
            <DetailRow label="CA restant à facturer" value={fmt(ca_manquant)} highlight={ca_manquant > 0} />
            <DetailRow label="TJM moyen constaté" value={tjm_moyen ? `${fmt(tjm_moyen)}/jour` : '—'} />
            <DetailRow label="Jours facturables restants" value={`~${jours_restants} jours`} />
            <DetailRow label="Missions estimées" value={`${missions_restantes} missions`} />
          </tbody>
        </table>
        {source_cotisations && (
          <div className="prev-tool__source">
            Source : {source_cotisations}
          </div>
        )}
      </div>

      {/* ZONE 4 — Barre de progression */}
      <div className="prev-tool__progress">
        <div className="prev-tool__progress-header">
          <span>{progressPct.toFixed(1)}% de l'objectif atteint</span>
          <span>{fmt(ca_actuel)} / {fmt(ca_brut_cible)}</span>
        </div>
        <div className="prev-tool__progress-bar">
          <div
            className="prev-tool__progress-fill"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>
    </div>
  )
}

/* Helpers */

function fmt(n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('fr-FR', { maximumFractionDigits: 0 }) + ' €'
}

function BarRow({ label, value, max, color }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0
  return (
    <div className="prev-tool__bar-row">
      <span className="prev-tool__bar-label">{label}</span>
      <div className="prev-tool__bar-track">
        <div
          className="prev-tool__bar-fill"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span className="prev-tool__bar-value">{fmt(value)}</span>
    </div>
  )
}

function DetailRow({ label, value, highlight }) {
  return (
    <tr className={highlight ? 'prev-tool__row--highlight' : ''}>
      <td className="prev-tool__cell-label">{label}</td>
      <td className="prev-tool__cell-value">{value}</td>
    </tr>
  )
}

export default PrevisionsTool
