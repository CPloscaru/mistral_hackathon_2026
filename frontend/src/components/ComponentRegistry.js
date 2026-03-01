/**
 * ComponentRegistry — maps component types to React components.
 *
 * Used by PersonalAssistant to dynamically render tools activated by
 * the backend via ui_component SSE events (A2UI pattern).
 */

import AdminTool from './tools/AdminTool'
import CalendarTool from './tools/CalendarTool'
import CRMTool from './tools/CRMTool'
import BudgetTool from './tools/BudgetTool'
import RoadmapTool from './tools/RoadmapTool'
import ChatTool from './tools/ChatTool'
import ObjectifsTool from './tools/ObjectifsTool'
import PrevisionsTool from './tools/PrevisionsTool'

const REGISTRY = {
  admin:    { component: AdminTool,    defaultTitle: 'Checklist Administrative', defaultIcon: '\uD83D\uDCCB' },
  calendar: { component: CalendarTool, defaultTitle: 'Calendrier des Actions',  defaultIcon: '\uD83D\uDCC5' },
  crm:      { component: CRMTool,      defaultTitle: 'Clients & Facturation',   defaultIcon: '\uD83D\uDCBC' },
  budget:   { component: BudgetTool,   defaultTitle: 'Budget Pr\u00e9visionnel',     defaultIcon: '\uD83D\uDCB0' },
  roadmap:  { component: RoadmapTool,  defaultTitle: 'Roadmap du Plan',         defaultIcon: '\uD83D\uDDFA\uFE0F' },
  chat:     { component: ChatTool,     defaultTitle: 'Parler \u00e0 un sp\u00e9cialiste', defaultIcon: '\uD83D\uDCAC' },
  objectifs: { component: ObjectifsTool, defaultTitle: 'Mes Objectifs', defaultIcon: '🎯' },
  previsions: { component: PrevisionsTool, defaultTitle: 'Prévisions Financières', defaultIcon: '📊' },
}

export function getComponent(type) {
  return REGISTRY[type] || null
}

export default REGISTRY
