/**
 * BudgetTool - Budget prévisionnel avec charges, revenus et seuil de rentabilité
 *
 * Props:
 * - sessionId: identifiant de session
 * - data: données budget inline (depuis ui_component SSE) — sinon fetch /tools/budget
 */

import { useState, useEffect } from 'react'

function buildBackendUrl() {
  return `http://${window.location.hostname}:8000`
}

function BudgetTool({ sessionId, data: inlineData }) {
  const [budget, setBudget] = useState(inlineData || null)
  const [loading, setLoading] = useState(!inlineData)

  useEffect(() => {
    if (inlineData) {
      setBudget(inlineData)
      setLoading(false)
      return
    }
    if (!sessionId) return

    async function fetchBudget() {
      try {
        const res = await fetch(`${buildBackendUrl()}/tools/budget?session_id=${sessionId}`)
        if (res.ok) {
          const json = await res.json()
          if (json.budget_data) setBudget(json.budget_data)
        }
      } catch (e) {
        console.warn('Failed to fetch budget:', e)
      } finally {
        setLoading(false)
      }
    }
    fetchBudget()
  }, [sessionId, inlineData])

  if (loading) {
    return (
      <div className="budget-tool__loading">
        <div className="budget-tool__spinner" />
        <span>Chargement du budget...</span>
      </div>
    )
  }

  if (!budget) {
    return (
      <div className="budget-tool__empty">
        Aucune donnée de budget disponible pour cette session.
      </div>
    )
  }

  const charges = budget.charges_mensuelles || []
  const revenus = budget.revenus_estimes
  const seuil = budget.seuil_rentabilite

  const totalCharges = charges.reduce((sum, c) => sum + (c.montant || 0), 0)

  // Seuil progress
  const seuilRatio = seuil && seuil.ca_minimum_mensuel > 0
    ? Math.min((seuil.charges_fixes_mensuelles / seuil.ca_minimum_mensuel) * 100, 100)
    : 0

  return (
    <div className="budget-tool">
      {/* Section 1: Charges mensuelles */}
      <h3 className="budget-tool__section-title">Charges mensuelles</h3>
      <div className="budget-tool__charges">
        {charges.map((charge, i) => (
          <div key={i} className="budget-tool__charge-row">
            <div className="budget-tool__charge-info">
              <span className="budget-tool__charge-label">{charge.label}</span>
              <span className={`budget-tool__badge budget-tool__badge--${charge.type}`}>
                {charge.type === 'obligatoire' ? 'Obligatoire' : 'Recommandé'}
              </span>
            </div>
            <span className="budget-tool__charge-montant">
              {charge.montant?.toLocaleString('fr-FR')} €
            </span>
          </div>
        ))}
        <div className="budget-tool__charge-total">
          <span>Total mensuel</span>
          <span className="budget-tool__charge-total-value">
            {totalCharges.toLocaleString('fr-FR')} €
          </span>
        </div>
      </div>

      {/* Section 2: Revenus estimés */}
      {revenus && (
        <>
          <h3 className="budget-tool__section-title">Revenus estimés</h3>
          <div className="budget-tool__revenus">
            <div className="budget-tool__card">
              <div className="budget-tool__card-value">
                {revenus.tjm_suggere?.toLocaleString('fr-FR')} €
              </div>
              <div className="budget-tool__card-label">TJM suggéré</div>
            </div>
            <div className="budget-tool__card">
              <div className="budget-tool__card-value">
                {revenus.jours_par_mois}
              </div>
              <div className="budget-tool__card-label">Jours / mois</div>
            </div>
            <div className="budget-tool__card">
              <div className="budget-tool__card-value">
                {revenus.ca_mensuel_estime?.toLocaleString('fr-FR')} €
              </div>
              <div className="budget-tool__card-label">CA mensuel estimé</div>
            </div>
          </div>
        </>
      )}

      {/* Section 3: Seuil de rentabilité */}
      {seuil && (
        <>
          <h3 className="budget-tool__section-title">Seuil de rentabilité</h3>
          <div className="budget-tool__seuil">
            <div className="budget-tool__seuil-bar-container">
              <div className="budget-tool__seuil-labels">
                <span>Charges fixes : {seuil.charges_fixes_mensuelles?.toLocaleString('fr-FR')} €/mois</span>
                <span>CA minimum : {seuil.ca_minimum_mensuel?.toLocaleString('fr-FR')} €/mois</span>
              </div>
              <div className="budget-tool__seuil-bar">
                <div
                  className="budget-tool__seuil-fill"
                  style={{ width: `${seuilRatio}%` }}
                />
              </div>
              <div className="budget-tool__seuil-info">
                Minimum <strong>{seuil.jours_minimum}</strong> jour{seuil.jours_minimum > 1 ? 's' : ''} facturé{seuil.jours_minimum > 1 ? 's' : ''} / mois pour couvrir les charges
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default BudgetTool
