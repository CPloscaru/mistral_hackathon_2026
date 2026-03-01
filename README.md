# Kameleon

Adaptive AI assistant for French freelancers and small business owners.

Kameleon guides users from zero — through a conversational onboarding — to a personalized dashboard powered by an AI that understands their situation, pain points and goals.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.14, FastAPI, Uvicorn, SSE (sse-starlette) |
| Agent SDK | [Strands Agents](https://strandsagents.com) |
| AI | Mistral AI (API) |
| Database | SQLite |
| Frontend | React 19, Vite 7, React Router 7 |
| Web search | Brave Search API |

---

## Getting Started

### Prerequisites

- Python 3.12+ with `venv`
- Node.js 18+
- A Mistral API key

### Installation

```bash
# Backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend && npm install && cd ..
```

### Environment Variables

Create a `.env` file at the project root:

```env
MISTRAL_API=sk-...
BRAVE_API_KEY=BSA...        # optional, for web search
```

### Running

```bash
# Normal mode — starts backend + frontend, opens the browser
./scripts/start.sh

# Auto mode — resets the DB, runs the full LLM-driven onboarding test
./scripts/start.sh auto

# Resume mode — keeps the DB, reopens the dashboard directly
./scripts/start.sh resume
```

Backend runs on `http://localhost:8000`, frontend on `http://localhost:5173`.

---

## Multi-Agent Architecture: "Agents as Tools"

The core pattern is **"Agents as Tools"** from the Strands SDK: the main orchestrator owns sub-agents declared as `@tool`. Each sub-agent is a standalone Strands agent with its own model, system prompt and tools. The orchestrator decides which sub-agent to call based on the user's request.

No Swarm, no remote A2A protocol — everything is local, synchronous, in-process.

---

## User Journey and Models Used

### Phase 1 — Conversational Onboarding

The onboarding agent leads a natural conversation in 4-7 exchanges to collect the user's profile.

| Step | What happens | Model |
|---|---|---|
| Welcome | The agent introduces itself, asks the user to pick its name (Andy or Lisa) | `mistral-large-2512` |
| Collection | First name, business activity, experience level, current situation, blockers, goals | `mistral-large-2512` |
| Trigger | Once minimum data is collected, the agent emits `[READY_FOR_PLAN]` + a JSON profile | `mistral-large-2512` |

**Why `mistral-large` here?** Onboarding requires conversational nuance, empathy and the ability to produce a clean JSON at the end of the collection.

### Phase 2 — Sequential Workflow (backend, no user interaction)

Once the profile is collected, 4 automatic steps run server-side. The frontend displays an animated stepper.

| Step | What happens | Model | Why this model |
|---|---|---|---|
| **Profile analysis** | Situation summary + 4-8 prioritized objectives (urgency/impact) | `magistral-medium-2509` | Structured reasoning, JSON output validated by Pydantic |
| **Tool mapping** | Each objective is assigned to a dashboard tool type | `magistral-medium-2509` | Same analytical logic, context enriched by the previous step |
| **Roadmap generation** | SMART objective + 3-5 phases with concrete actions | `magistral-medium-2509` | Structured planning, consistency with previous steps |
| **UI construction** | Dynamic activation of dock components | Deterministic (no LLM) | Pure logic: translates the mapping into UI events |

Each workflow step uses an externalized prompt (`backend/agents/prompts/*.txt`) and passes its result as context to the next step.

### Phase 2.5 — Tool Showcase

| What happens | Model | Why |
|---|---|---|
| Generates personalized descriptions for each activated tool | `ministral-8b-2512` | Simple copywriting task, 8B is more than enough and cheaper |

### Phase 3 — Dashboard and Daily Orchestrator

The user lands on their dashboard with a macOS-style dock. All conversation goes through the orchestrator.

**Main orchestrator**

| Component | Model | Role |
|---|---|---|
| Orchestrator (Marc) | `mistral-large-2512` | Understands intent, routes to the right sub-agent, manages dialogue |

**Sub-agents (declared as `@tool` on the orchestrator)**

| Sub-agent | Model | Tools | Domain |
|---|---|---|---|
| `objectifs_agent` | `magistral-small-2509` | `manage_objectifs` | Goal tracking |
| `budget_agent` | `magistral-small-2509` | `manage_budget` | Budget forecasting |
| `admin_agent` | `magistral-small-2509` | `manage_admin` | Administrative checklist |
| `calendar_agent` | `magistral-small-2509` | `manage_calendar` | Action calendar |
| `roadmap_agent` | `magistral-small-2509` | `manage_roadmap` | Action plan tracking |
| `crm_agent` | `mistral-large-2512` | `manage_crm`, `display_data_table` | Clients and invoicing |
| `financial_agent` | `magistral-medium-2509` | `web_search`, `manage_crm`, `manage_previsions` | Financial forecasting |

**Why this model hierarchy?**
- `magistral-small` for simple sub-agents (CRUD + formatting) — fast and cost-effective
- `magistral-medium` for tasks requiring reasoning (finance, analysis)
- `mistral-large` for the orchestrator (complex routing) and CRM (rich data, tables)

**Direct orchestrator tools (not sub-agents)**

| Tool | Function |
|---|---|
| `propose_choices` | Displays clickable buttons in the chat (HITL) |
| `display_data_table` | Renders a data table inline |
| `suggest_specialist_chat` | Makes a dock icon bounce to redirect to a specialist |
| `activate_dock_component` | Dynamically adds a tool to the dock |
| `manage_statut_juridique` | Read/update legal status |

### Legal Specialist (dedicated chat)

| Component | Model | Tools |
|---|---|---|
| Legal agent | `magistral-medium-2509` | `web_search`, `manage_statut_juridique` |

Accessible via the "Chat" dock icon. Lives in its own panel, independent from the orchestrator.

---

## Dashboard Tools

| Tool | Description |
|---|---|
| My Goals | Prioritized objectives from onboarding, progress tracking |
| Clients & Invoicing (CRM) | Client management, invoices, overdue reminders, raw invoice import |
| Administrative Checklist | Checkable to-do list for administrative tasks |
| Action Calendar | Events, deadlines, action dates |
| Budget Forecast | Expenses, revenue, projected balance |
| Plan Roadmap | Phase-by-phase action plan with SMART objective |
| Financial Forecasts | Target revenue, contributions, daily rate, remaining missions |
| Talk to a Specialist | Dedicated chat with the legal agent |

---

## Project Structure

```
backend/
  agents/
    orchestrator.py          # Main orchestrator (Marc)
    onboarding_chat.py       # Conversational onboarding agent
    onboarding_workflow.py   # Sequential post-collection workflow
    financial_swarm.py       # Financial forecasting sub-agent
    specialist_juridique.py  # Legal specialist for freelancers
    prompts/                 # Externalized prompts (.txt)
  models/
    magistral.py             # Magistral wrapper (filters thinking tokens)
  routes/
    chat_init.py             # GET /chat/init — first onboarding message
    chat_onboarding.py       # POST /chat/onboarding — sequential workflow
    chat_stream.py           # POST /chat/stream — main streaming endpoint
    chat_common.py           # Session and history
    tools.py                 # REST CRUD for all tools
  session/
    db.py                    # SQLite — table creation and queries
    manager.py               # Session management
  tools/                     # Strands tools (@tool) for agents
    objectifs.py, crm.py, budget.py, admin.py,
    calendar.py, roadmap.py, previsions.py,
    profil.py, interaction.py, ui_components.py,
    web_search.py
  config.py                  # Model constants and configuration
  main.py                    # FastAPI entry point

frontend/
  src/
    App.jsx                  # React routes
    components/
      WelcomePage.jsx        # Landing page
      ChatView.jsx           # Onboarding view (chat)
      PersonalAssistant.jsx  # Full post-onboarding dashboard
      Dock.jsx               # macOS-style dock
      ComponentRegistry.js   # Dynamic tool component registry
      tools/                 # Individual tool components
    hooks/
      useChat.js             # SSE streaming hook
      useSession.js          # Session management hook
    styles/                  # CSS

scripts/
  start.sh                  # Launch (normal / auto / resume)
  01_first_step_onboarding.py  # Auto test: LLM plays the user
  02_second_step_plan.py       # Auto test: triggers the workflow
  seed_roadmap.py              # Roadmap data seeding
```

---

## Mistral Models Summary

| Model | Size | Used for |
|---|---|---|
| `mistral-large-2512` | Large | Orchestrator, onboarding, CRM |
| `magistral-medium-2509` | Medium | Workflow (analysis, mapping, roadmap), finance, legal specialist |
| `magistral-small-2509` | Small | Simple sub-agents (goals, budget, admin, calendar, roadmap) |
| `ministral-8b-2512` | 8B | Tool descriptions, invoice parsing |
| `ministral-3b-2512` | 3B | Available, not currently used |
| `ministral-14b-2512` | 14B | Available, not currently used |
