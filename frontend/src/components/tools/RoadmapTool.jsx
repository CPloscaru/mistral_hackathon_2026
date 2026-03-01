/**
 * RoadmapTool - Roadmap visuelle du plan SMART avec timeline verticale
 *
 * Props:
 * - sessionId: identifiant de session
 * - data: { phases: [...], objectif_smart: "..." } — inline depuis ui_component SSE
 */

import { useState, useEffect } from 'react'

function buildBackendUrl() {
  return `http://${window.location.hostname}:8000`
}

/**
 * Détermine le statut d'une phase par rapport à la date du jour.
 * Heuristique simple basée sur le titre de la phase :
 * - "Semaine 1" → 0-7j
 * - "Semaines 2-3" → 7-21j
 * - "Mois 1-2" → 21-60j
 * etc.
 */
function getPhaseStatus(phaseIndex, totalPhases) {
  // Simple heuristique : première phase = en cours, suivantes = à venir
  // On marque la première comme "current" si on est dans les premières semaines
  const now = new Date()
  // Pour une roadmap typique de 3 phases sur ~3 mois,
  // on considère qu'on est dans la phase proportionnelle au temps écoulé
  // Mais sans dates exactes, on marque simplement la première comme "current"
  if (phaseIndex === 0) return 'current'
  return 'future'
}

function RoadmapTool({ sessionId, data: inlineData }) {
  const [roadmap, setRoadmap] = useState(inlineData || null)
  const [loading, setLoading] = useState(!inlineData)

  useEffect(() => {
    if (inlineData) {
      setRoadmap(inlineData)
      setLoading(false)
      return
    }
    if (!sessionId) return

    // Fallback: fetch from /tools/roadmap (DB-first)
    async function fetchRoadmap() {
      try {
        const res = await fetch(`${buildBackendUrl()}/tools/roadmap?session_id=${sessionId}`)
        if (res.ok) {
          const json = await res.json()
          if (json.phases && json.phases.length > 0) {
            setRoadmap({
              phases: json.phases,
              objectif_smart: json.objectif_smart || '',
            })
          }
        }
      } catch (e) {
        console.warn('Failed to fetch roadmap:', e)
      } finally {
        setLoading(false)
      }
    }
    fetchRoadmap()
  }, [sessionId, inlineData])

  if (loading) {
    return (
      <div className="roadmap-tool__loading">
        <div className="roadmap-tool__spinner" />
        <span>Chargement de la roadmap...</span>
      </div>
    )
  }

  if (!roadmap || !roadmap.phases || roadmap.phases.length === 0) {
    return (
      <div className="roadmap-tool__empty">
        Aucune roadmap disponible pour cette session.
      </div>
    )
  }

  const { phases, objectif_smart } = roadmap

  return (
    <div className="roadmap-tool">
      {/* Bannière objectif SMART */}
      {objectif_smart && (
        <div className="roadmap-tool__banner">
          <div className="roadmap-tool__banner-icon">🎯</div>
          <p className="roadmap-tool__banner-text">{objectif_smart}</p>
        </div>
      )}

      {/* Timeline verticale */}
      <div className="roadmap-tool__timeline">
        {phases.map((phase, i) => {
          const status = getPhaseStatus(i, phases.length)
          return (
            <div key={i} className={`roadmap-tool__node roadmap-tool__node--${status}`}>
              <div className="roadmap-tool__node-line">
                <div className="roadmap-tool__node-dot" />
                {i < phases.length - 1 && <div className="roadmap-tool__node-connector" />}
              </div>
              <div className="roadmap-tool__node-content">
                <h4 className="roadmap-tool__node-title">{phase.titre}</h4>
                <p className="roadmap-tool__node-objectif">{phase.objectif}</p>
                <ul className="roadmap-tool__node-actions">
                  {(phase.actions || []).map((action, j) => (
                    <li key={j} className="roadmap-tool__action">{action}</li>
                  ))}
                </ul>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default RoadmapTool
