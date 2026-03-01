"""Test script: create session, inject onboarding, trigger Swarm, check tools_data."""
import requests
import json
import uuid

session_id = str(uuid.uuid4())
print(f"New session: {session_id}")

# Create session
r = requests.get(f"http://sophie.localhost:8000/chat/init?session_id={session_id}", stream=True)
for chunk in r.iter_content(512):
    break
r.close()

# Inject onboarding
profile = {
    "prenom": "Sophie",
    "activite": "Designer graphique freelance",
    "experience": "3 ans en agence, 6 mois en freelance",
    "situation": "En transition, quitte son CDI dans 1 mois",
    "statut_administratif": "Auto-entrepreneur en cours de création",
    "clients": "3 clients réguliers, 2 prospects",
    "blocages": "Administratif (URSSAF, ACRE, CFE), facturation, trouver plus de clients",
    "outils_actuels": "Excel pour les factures, rien d autre",
    "objectif": "Vivre du freelance à 100% dans 3 mois, structurer son activité",
}
requests.post(
    f"http://sophie.localhost:8000/chat/inject-onboarding",
    json={"session_id": session_id, "profile": profile},
)

# Trigger plan
print("Triggering Swarm...")
r = requests.post(
    f"http://sophie.localhost:8000/chat/stream",
    json={"message": "__PLAN__", "session_id": session_id},
    stream=True,
    timeout=180,
)

events = []
buffer = ""
current_event = None
current_data = []
progress_count = 0

for chunk in r.iter_content(chunk_size=None, decode_unicode=True):
    buffer += chunk
    while "\n" in buffer:
        line, buffer = buffer.split("\n", 1)
        line = line.strip()
        if line == "":
            if current_event and current_data:
                data_str = "\n".join(current_data)
                events.append((current_event, data_str))
                if current_event == "progress":
                    progress_count += 1
                else:
                    print(f"  EVENT: {current_event} ({len(data_str)} chars)")
            current_event = None
            current_data = []
        elif line.startswith("event: "):
            current_event = line[7:]
        elif line.startswith("data: "):
            current_data.append(line[6:])

print(f"\nTotal events: {len(events)} ({progress_count} progress)")

found_plan = False
for evt_type, evt_data in events:
    if evt_type == "plan_ready":
        found_plan = True
        plan = json.loads(evt_data)
        print(f"\nobjective: {plan.get('objectif_smart', 'MISSING')[:100]}")
        print(f"phases: {len(plan.get('phases', []))}")
        tools = plan.get("tools_data")
        if tools:
            print(f"\n=== TOOLS DATA ===")
            ac = tools.get("admin_checklist", [])
            print(f"admin_checklist: {len(ac)} items")
            for item in ac[:3]:
                print(f"  - {item.get('label')} -> {item.get('url', 'no url')}")
            ce = tools.get("calendar_events", [])
            print(f"calendar_events: {len(ce)} events")
            for ev in ce[:3]:
                print(f"  - {ev.get('date')} | {ev.get('titre')} ({ev.get('type')})")
        else:
            print("tools_data ABSENT")
        break

if not found_plan:
    print("\nNo plan_ready event found!")
    for evt_type, evt_data in events:
        if evt_type == "token":
            print(f"Token content (first 500): {evt_data[:500]}")

print(f"\nSession ID: {session_id}")
print(f"URL: http://sophie.localhost:5173/personal-assistant?session_id={session_id}")
