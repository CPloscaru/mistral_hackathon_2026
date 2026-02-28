---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: in-progress
last_updated: "2026-02-28T12:09:46Z"
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 8
  completed_plans: 6
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-28)

**Core value:** The experience auto-customizes for each user — both the UI and the agent capabilities — through natural conversation.
**Current focus:** Phase 2 — Streaming Chat + Onboarding

## Current Position

Phase: 2 of 4 (Streaming Chat + Onboarding)
Plan: 2 of 2 in current phase
Status: Phase 2 complete
Last activity: 2026-02-28 — Plan 02 complete: React chat UI with iMessage bubbles, SSE streaming, subdomain persona routing

Progress: [████████░░] 50%

## Performance Metrics

**Velocity:**
- Total plans completed: 6
- Average duration: 8 min
- Total execution time: 0.73 hours (Phase 1) + Phase 2 ongoing

*Updated after each plan completion*

## Accumulated Context

### Decisions

- **Swarm architecture**: 5 functional agents (Clients, Finances, Planning, Création, Activité) + coordinator (Mistral Large) via Strands Swarm
- **Agents by function, not persona**: persona = tone injection in system prompt, not separate agents
- **Subdomains**: sophie.localhost (onboarding), lea.localhost (quotidien), marc.localhost (quotidien)
- **Agent-led onboarding**: Sophie only — agent initiates conversation and guides through questions
- **Pre-configured workspaces**: Léa and Marc start with seed data loaded
- **Persona evolution**: predefined maturity levels with scripted transitions (Sophie: 4 levels, Léa: 3, Marc: 3)
- **Two user modes**: Lanceur (Sophie — "aide-moi à démarrer") vs Installé (Léa/Marc — "aide-moi au quotidien")
- Model routing by function: 3B (Planning), 8B (Clients/Finances/Activité), 14B (Création), Large (Coordinator)
- Seed data per persona prevents empty-state problem during demo (except Sophie who starts empty)
- No auth or real DB persistence — throwaway hackathon code

### Decisions (Plan 01)

- **strands-agents-mistral does not exist as pip package**: MistralModel is built into strands-agents via mistralai dependency — `from strands.models.mistral import MistralModel` works
- **PERSONA_TONES dict established**: stores name/style/description per persona for system prompt injection in factory.py
- **Seed data categories differ by persona**: Léa has projets[], Marc has stock[] — reflects their different business models

### Decisions (Plan 02)

- **PERSONA_TONES defined in prompts.py (not config.py)**: config.py has a richer structured dict for UI metadata; prompts.py has simple tone strings for system prompt injection — coexist for different purposes
- **Coordinator receives data summary (counts only)**: coordinator must stay focused on routing, not answer domain questions directly — only functional agents get detailed data
- **Creation agent (14B) receives clients[] seed data**: needs client context to personalize content generation (emails, posts) to actual client names and sectors
- **Each SlidingWindowConversationManager is a new instance per agent**: prevents shared conversation state across agents within same session

### Decisions (Plan 04)

- **Mock mistralai.Mistral (not MistralModel) for routing tests**: MistralModel.get_config() only returns real model_id if MistralModel is actually instantiated — mocking the HTTP client layer preserves this
- **swarm.nodes is a dict keyed by agent name**: access via swarm.nodes[name].executor to get the Agent instance for config inspection
- **null_callback_handler is a function stored in agent.callback_handler**: when callback_handler=None is passed to Agent constructor, Strands uses null_callback_handler internally

### Decisions (Plan 03)

- **SubdomainMiddleware defaults to creator for unknown subdomains**: safer than error, Sophie is the onboarding persona
- **session_manager is a module-level singleton**: one shared instance per process — correct for hackathon in-memory storage
- **SwarmResult text extraction tries coordinator node first**: handles cases where coordinator delegates entirely to functional agent
- **Seed data loaded once at SessionManager init**: avoids repeated disk reads for static demo data

### Decisions (02-01: Streaming Backend + SQLite)

- **httpx.ASGITransport required for async SSE tests**: httpx 0.28+ removed `app=` kwarg from AsyncClient — use `transport=httpx.ASGITransport(app=app)` pattern
- **DB_PATH as module-level string**: allows monkeypatching in tests with tmp_path without touching production DB
- **[ONBOARDING_COMPLETE] sentinel handling**: stripped from token before yielding, emits separate maturity_update SSE event, triggers update_session_state() call
- **Coordinator onboarding instructions appended only for creator persona**: freelance/merchant coordinator prompt unchanged

### Decisions (02-02: Frontend Chat UI)

- **SSE buffering strategy**: split buffer on `\n\n` for complete messages, keep last incomplete part — handles chunks correctly
- **Functional updater form always in setMessages**: avoids stale closure bugs with concurrent state updates during streaming
- **Typing indicator logic**: shown when isStreaming && lastMsg.content === '' && lastMsg.streaming — disappears on first token
- **Burger menu gated on maturityLevel**: hidden during Sophie onboarding (maturityLevel === 1), appears at maturityLevel >= 2

### Decisions (02-03: Integration + Onboarding Swarm)

- **Swarm onboarding dédié pour Sophie (creator, maturity=1)**: 4 agents (coordinator Large, profiler 8B, recherche 14B + Brave, expert_fr 8B) au lieu du swarm standard
- **Brave Search API tool**: `@tool web_search` dans backend/tools/web_search.py — nécessite BRAVE_SEARCH_API_KEY dans .env
- **Base de connaissances FR intégrée au prompt expert_fr**: statuts juridiques, obligations, aides, calcul TJM — pas de RAG/vector DB
- **MVP = Sophie + Marc uniquement**: Léa reste dans le code mais ignorée en démo
- **Checklist d'infos onboarding**: le coordinator collecte prénom, activité, XP, blocages, objectifs puis délègue au profiler pour le plan final
- **Markdown rendering dans les bulles**: parseMarkdown() avec bold/italic + dangerouslySetInnerHTML
- **Vite default index.css supprimé**: causait un layout shift horizontal au chargement (place-items:center)

### Pending Todos

- [ ] Script demo Sophie: refaire en mode API-only (httpx calls, pas playwright) pour que l'utilisateur voie en direct dans son navigateur
- [ ] Scénariser Marc (day-to-day): définir les turns de conversation pour la démo artisan savonnier
- [ ] Ajouter BRAVE_SEARCH_API_KEY dans .env (clé gratuite sur brave.com/search/api/)
- [ ] Finaliser checkpoint 02-03: SUMMARY.md + vérification phase
- [ ] Tester le handoff coordinator → profiler/recherche/expert_fr en fin d'onboarding
- [ ] Transition post-onboarding: swap du swarm onboarding vers le swarm day-to-day après [ONBOARDING_COMPLETE]

### Blockers/Concerns

- Check Mistral workspace rate limits at `admin.mistral.ai/plateforme/limits` before starting
- Validate Strands Swarm `stream_async` event structure against installed version
- 6 model instances in one swarm (coordinator + 5 agents) — verify Mistral rate limits handle concurrent calls

## Session Continuity

Last session: 2026-02-28
Stopped at: Phase 2 en cours — Plans 02-01 et 02-02 exécutés, 02-03 checkpoint en cours. Swarm onboarding implémenté et fonctionnel. Script demo Sophie à refaire en API-only. Scénario Marc à définir.
Resume file: None
