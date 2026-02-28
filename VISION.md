# Vision Kameleon

## Pourquoi Kameleon existe

Les petits créateurs, auto-entrepreneurs et très petites PME n'ont ni le temps, ni l'argent, ni les compétences pour utiliser des outils complexes (CRM, comptabilité, gestion de projet, calendrier...). Ils jonglent entre WhatsApp, des fichiers Excel, des post-its et leur mémoire. Résultat : ils passent du temps sur des tâches "annexes" au lieu de se concentrer sur leur métier.

Kameleon est un **assistant IA conversationnel qui réduit l'abstraction**. L'utilisateur parle naturellement, et l'IA gère tout en arrière-plan — clients, factures, planning, contenu. Pas de menus, pas de formulaires, pas de courbe d'apprentissage.

## Principe fondamental

**L'utilisateur ne sait pas qu'il utilise un CRM, un outil de facturation ou un gestionnaire de projet.** Il parle à son assistant comme il parlerait à un collègue de confiance. L'IA comprend, agit, et affiche les informations pertinentes.

## Architecture multi-agents (Swarm)

Kameleon utilise le pattern **Swarm** de Strands Agents SDK. Un coordinateur (Mistral Large) reçoit chaque message et le transmet au bon agent spécialiste via `handoff_to_agent`.

### Coordinator (Mistral Large 3)
- Reçoit tous les messages utilisateur
- Comprend l'intention et route vers le bon agent fonctionnel
- Gère la détection de persona pendant l'onboarding
- L'utilisateur ne voit qu'un seul assistant — le routage est invisible

### 5 Agents fonctionnels

Les agents sont organisés par **fonction métier**, pas par persona. La personnalité (ton, style) est injectée dans chaque agent selon la persona active.

| Agent | Fonction | Questions typiques | Modèle |
|-------|----------|-------------------|--------|
| **Clients** | Gestion des contacts, suivi relations, relances | *"Mes clients cette semaine"*, *"Relance Marie Dupont"* | Ministral 8B |
| **Finances** | Factures, CA, dépenses, devis, trésorerie | *"J'ai des factures impayées ?"*, *"Mon CA ce mois"* | Ministral 8B |
| **Planning** | Agenda, deadlines, rappels, organisation | *"C'est quoi demain ?"*, *"Ma deadline la plus proche"* | Ministral 3B |
| **Création** | Rédaction, idées, posts, emails, contenus | *"Écris un post Instagram"*, *"Rédige un mail de relance"* | Ministral 14B |
| **Activité** | Stock, projets en cours, avancement, produits | *"Mon stock de croissants"*, *"Où en est le projet StartupTech"* | Ministral 8B |

### Logique de personnalité

La persona ne change pas l'agent, elle change le **ton** :
- **Sophie (Creator)** : fun, créatif, emojis, parle comme un ami créatif
- **Marc (Merchant)** : chaleureux, direct, pratique, parle comme un associé de confiance

Chaque agent reçoit dans son system prompt :
1. Sa spécialisation fonctionnelle (ce qu'il sait faire)
2. Le ton de la persona active (comment il parle)
3. Les données seed de la persona (ce qu'il sait sur l'utilisateur)

## Deux modes d'utilisation

Kameleon accompagne deux profils fondamentalement différents :

### Le Lanceur — "Aide-moi à démarrer"
- Auto-entrepreneur qui se lance, créateur débutant
- **Ne sait pas ce qu'il ne sait pas** — a besoin de guidance
- L'IA agit comme un **mentor/coach** : checklist, étapes, explications haut niveau
- L'accompagnement est progressif : d'abord les grandes lignes, puis du détail quand l'utilisateur demande de l'aide
- Pas de données existantes — tout se construit au fil de la conversation

### L'Installé — "Aide-moi au quotidien"
- Pro en activité, a déjà ses clients, ses factures, son planning
- **Sait ce qu'il fait** mais veut déléguer les tâches "annexes"
- L'IA agit comme un **assistant/bras droit** : exécute, résume, rappelle, rédige
- Interface seedée avec des données riches dès le départ

## Architecture MVP — sous-domaines par use case

Chaque persona a son propre **sous-domaine local**, comme si c'était un espace utilisateur distinct :

| Sous-domaine | Persona | Mode | État initial |
|-------------|---------|------|-------------|
| `sophie.localhost` | Sophie | **Onboarding** | Espace vierge — l'agent guide Sophie avec des questions pour configurer son espace |
| `marc.localhost` | Marc | **Quotidien** | Espace pré-configuré avec seed data — assistant commerçant |

### Onboarding piloté par l'agent (Sophie uniquement)

Sur `sophie.localhost`, l'agent **initie la conversation**. C'est lui qui commence, pas l'utilisateur. Il guide Sophie avec des questions pour comprendre sa situation et configurer son espace :

1. L'agent se présente et demande ce que Sophie veut faire
2. Il pose des questions sur son projet (plateforme, niche, expérience...)
3. Il collecte les infos nécessaires (nom, activité, objectifs...)
4. Une fois qu'il a tout → il configure l'espace et propose une checklist de lancement
5. La conversation continue en mode accompagnement

**C'est le seul use case avec onboarding.** Léa et Marc arrivent sur un espace déjà configuré.

### Espaces pré-configurés (Léa et Marc)

Sur `marc.localhost`, tout est déjà en place :
- Seed data chargée (clients, stock, finances, calendrier)
- L'agent connaît déjà l'utilisateur
- On montre directement l'utilisation au quotidien

## 2 Personas de démo

| # | Persona | Sous-domaine | Ce qu'on démontre |
|---|---------|-------------|------------------|
| 1 | **Sophie** | `sophie.localhost` | Onboarding guidé par l'agent → checklist de lancement → accompagnement progressif → évolution de la persona |
| 2 | **Marc** | `marc.localhost` | Assistant commerçant — stock, clients, fournisseurs, planning production |

**Ordre de démo :** Sophie (wow du "l'IA me prend par la main") → Marc (wow du "l'IA gère mon quotidien, même outil, besoin totalement différent")

## Persona évolutive — niveaux de maturité

La persona n'est pas figée. L'utilisateur progresse au fil de ses interactions et l'assistant s'adapte. Chaque persona a des **niveaux prédéfinis** qui déterminent ce que l'IA propose.

Pour le MVP, les transitions sont **scriptées** (détection par mots-clés dans la conversation). En production, la détection serait automatique via analyse conversationnelle.

### Sophie (Creator) — 4 niveaux

| Niveau | Nom | L'IA agit comme... | Déclencheur (scripté) | Seed data |
|--------|-----|---------------------|----------------------|-----------|
| 1 | **Débutante** | Coach/mentor — checklist de lancement | État initial | Aucune — tout se construit |
| 2 | **En cours** | Guide — aide sur les premiers contenus | "J'ai créé mon auto-entreprise" / "J'ai mon Instagram" | Premiers contenus, compte créé |
| 3 | **Active** | Assistant — gestion collabs, analytics | "J'ai mes premiers abonnés" / "J'ai une collab" | Collabs, contenus publiés, quelques clients |
| 4 | **Avancée** | Stratège — scaling, diversification | "J'ai 1000 abonnés" / "Je veux scaler" | Données riches (= seed data complète actuelle) |

### Marc (Merchant) — 3 niveaux

| Niveau | Nom | L'IA agit comme... | Déclencheur (scripté) | Seed data |
|--------|-----|---------------------|----------------------|-----------|
| 1 | **Nouveau** | Coach — aide au lancement du commerce | Si détecté pendant onboarding | Stock initial, pas de clients réguliers |
| 2 | **Établi** | Bras droit — gestion quotidienne | État par défaut (démo) | Clients fidèles, stock, fournisseurs |
| 3 | **En croissance** | Conseiller — expansion, second point de vente | "Je veux ouvrir un deuxième" / "Je recrute" | Données étendues, multi-sites |

### Impact technique

Le niveau de maturité est stocké dans la session et injecté dans le system prompt de chaque agent :
- **Niveau** → détermine le **mode** de l'agent (coach vs assistant vs stratège)
- **Seed data** → ajustée selon le niveau (vide pour débutant, riche pour installé)
- **UI** → les widgets proposés changent selon le niveau (checklist pour débutant, dashboard pour installé)

### Scénario démo (scripté)

1. **`sophie.localhost`** → L'agent dit bonjour et pose sa première question → onboarding conversationnel
2. Sophie répond aux questions → l'agent configure l'espace progressivement → checklist de lancement
3. Sophie avance → "J'ai créé mon auto-entreprise" → **transition niveau 2** → l'IA propose maintenant des idées de premiers contenus
4. On montre que l'assistant évolue AVEC l'utilisateur
5. **`marc.localhost`** → Espace déjà riche → "Mon stock de baguettes ?" → réponse immédiate avec les vraies données

## Le moment clé : le morphing

L'UI se transforme avec des transitions animées quand le contexte évolue :
- **Sophie :** le morphing arrive progressivement au fil de l'onboarding — l'interface se construit sous les yeux de l'utilisateur
- **Léa et Marc :** l'interface est déjà riche dès le départ — le morphing se manifeste par des micro-transitions (nouveaux widgets, tableau de bord qui se densifie) au fil de l'utilisation

Les transitions de niveau peuvent aussi déclencher des **micro-morphings** : nouveaux widgets qui apparaissent, ton qui évolue, suggestions qui changent.

## Cible utilisateur

- Petits créateurs de contenu (débutants ou établis)
- Auto-entrepreneurs qui se lancent
- Très petites PME (< 5 personnes)
- Commerçants de proximité
- Freelances

**Point commun :** ils ne veulent pas apprendre un outil. Ils veulent que ça marche en parlant.

---
*Dernière mise à jour : 2026-02-28 — Swarm 5 agents fonctionnels + sous-domaines par persona + onboarding piloté par l'agent (Sophie) + persona évolutive*
