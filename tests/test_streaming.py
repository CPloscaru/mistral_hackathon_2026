"""
Tests pour la couche de persistance SQLite et les endpoints SSE de streaming.
Phase 2 — Plan 01 : Streaming backend + onboarding init.
"""
import json
import pytest
import pytest_asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Fixtures partagées
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_db_path(tmp_path):
    """Chemin vers une base de données temporaire pour les tests."""
    return str(tmp_path / "test_kameleon.db")


@pytest.fixture
def patched_db(tmp_db_path, monkeypatch):
    """
    Patch le module backend.session.db pour utiliser un chemin de DB temporaire.
    Retourne le module db patché + le chemin.
    """
    import backend.session.db as db_module
    monkeypatch.setattr(db_module, "DB_PATH", tmp_db_path)
    # Réinitialise la DB avec le nouveau chemin
    db_module.init_db()
    return db_module


# ---------------------------------------------------------------------------
# Tests de la couche SQLite (backend/session/db.py)
# ---------------------------------------------------------------------------


class TestSQLiteInit:
    """Tests pour init_db()."""

    def test_init_db_creates_table_without_error(self, patched_db):
        """init_db() crée la table sessions sans lever d'exception."""
        # La fixture patched_db appelle déjà init_db() — si ça ne lève pas, c'est OK
        assert patched_db is not None

    def test_init_db_is_idempotent(self, patched_db):
        """Appeler init_db() plusieurs fois ne provoque pas d'erreur."""
        patched_db.init_db()
        patched_db.init_db()


class TestSQLitePersist:
    """Tests pour save_session() et load_session()."""

    def test_load_unknown_session_returns_none(self, patched_db):
        """load_session retourne None pour un session_id inconnu."""
        result = patched_db.load_session("session-inexistante")
        assert result is None

    def test_save_and_load_round_trip(self, patched_db):
        """save_session + load_session effectue un aller-retour correct."""
        patched_db.save_session(
            session_id="sess-001",
            persona="creator",
            assistant_name="Andy",
            maturity_level=2,
            onboarding_data={"activite": "photographe"},
        )
        result = patched_db.load_session("sess-001")

        assert result is not None
        assert result["session_id"] == "sess-001"
        assert result["persona"] == "creator"
        assert result["assistant_name"] == "Andy"
        assert result["maturity_level"] == 2
        assert result["onboarding_data"] == {"activite": "photographe"}

    def test_save_session_upsert(self, patched_db):
        """save_session avec le même session_id met à jour l'enregistrement existant."""
        patched_db.save_session(
            session_id="sess-002",
            persona="merchant",
            assistant_name=None,
            maturity_level=1,
            onboarding_data={},
        )
        patched_db.save_session(
            session_id="sess-002",
            persona="merchant",
            assistant_name="Andy",
            maturity_level=3,
            onboarding_data={"nom": "Marc Durand"},
        )
        result = patched_db.load_session("sess-002")

        assert result["assistant_name"] == "Andy"
        assert result["maturity_level"] == 3
        assert result["onboarding_data"] == {"nom": "Marc Durand"}

    def test_load_session_onboarding_data_is_dict(self, patched_db):
        """load_session retourne onboarding_data comme dict (pas comme string JSON)."""
        patched_db.save_session(
            session_id="sess-003",
            persona="merchant",
            assistant_name=None,
            maturity_level=1,
            onboarding_data={"produit": "savon"},
        )
        result = patched_db.load_session("sess-003")
        assert isinstance(result["onboarding_data"], dict)

    def test_save_session_with_none_assistant_name(self, patched_db):
        """save_session accepte assistant_name=None."""
        patched_db.save_session(
            session_id="sess-004",
            persona="creator",
            assistant_name=None,
            maturity_level=1,
            onboarding_data={},
        )
        result = patched_db.load_session("sess-004")
        assert result is not None
        assert result["assistant_name"] is None


class TestSessionManagerSQLite:
    """Tests d'intégration SessionManager <-> SQLite."""

    @pytest.fixture
    def fresh_manager(self, tmp_db_path, monkeypatch):
        """
        Crée un SessionManager frais avec une DB temporaire.
        Patche db.DB_PATH avant instanciation pour éviter la DB de prod.
        """
        import backend.session.db as db_module
        monkeypatch.setattr(db_module, "DB_PATH", tmp_db_path)

        # Patch create_swarm pour éviter les appels Mistral
        with patch("backend.session.manager.create_swarm") as mock_create_swarm:
            mock_swarm = MagicMock()
            mock_create_swarm.return_value = mock_swarm

            from backend.session.manager import SessionManager
            manager = SessionManager()
            yield manager, mock_create_swarm

    def test_get_or_create_session_loads_from_sqlite_on_cache_miss(
        self, fresh_manager, patched_db
    ):
        """
        SessionManager charge depuis SQLite si session_id absent du cache mémoire.
        """
        manager, mock_create_swarm = fresh_manager

        # Enregistre directement en DB (simule un redémarrage)
        patched_db.save_session(
            session_id="sess-persist-001",
            persona="creator",
            assistant_name="Andy",
            maturity_level=2,
            onboarding_data={"activite": "photographe"},
        )

        # Le manager n'a pas cette session en mémoire
        assert manager.get_session("sess-persist-001") is None

        # get_or_create_session doit trouver la session en DB
        session = manager.get_or_create_session("sess-persist-001", "creator")

        assert session is not None
        assert session["session_id"] == "sess-persist-001"
        assert session["persona"] == "creator"
        assert session["assistant_name"] == "Andy"
        assert session["maturity_level"] == 2

    def test_update_session_state_persists_to_sqlite(self, fresh_manager, patched_db):
        """
        update_session_state() met à jour en mémoire ET persiste en SQLite.
        """
        manager, mock_create_swarm = fresh_manager

        session = manager.get_or_create_session("sess-update-001", "creator")

        manager.update_session_state(
            session_id="sess-update-001",
            assistant_name="Lisa",
            maturity_level=3,
            onboarding_data={"activite": "artiste"},
        )

        # Vérifie que la mémoire est mise à jour
        in_memory = manager.get_session("sess-update-001")
        assert in_memory["assistant_name"] == "Lisa"
        assert in_memory["maturity_level"] == 3

        # Vérifie la persistance SQLite via une nouvelle lecture directe
        db_record = patched_db.load_session("sess-update-001")
        assert db_record is not None
        assert db_record["assistant_name"] == "Lisa"
        assert db_record["maturity_level"] == 3
        assert db_record["onboarding_data"] == {"activite": "artiste"}


# ---------------------------------------------------------------------------
# Tests des endpoints SSE (backend/routes/chat_stream.py)
# ---------------------------------------------------------------------------


def make_fake_swarm_events(tokens: list[str], include_maturity_sentinel: bool = False):
    """
    Génère une liste d'événements swarm simulés pour les tests SSE.
    Simule les événements multiagent_node_stream + multiagent_result.
    """
    events = []
    for token in tokens:
        events.append({
            "type": "multiagent_node_stream",
            "event": {"data": token},
        })
    if include_maturity_sentinel:
        events.append({
            "type": "multiagent_node_stream",
            "event": {"data": "Voici la suite. [ONBOARDING_COMPLETE]"},
        })
    events.append({
        "type": "multiagent_result",
        "event": {"data": ""},
    })
    return events


async def async_iter(items):
    """Convertit une liste en async iterable pour mocker stream_async."""
    for item in items:
        yield item


@pytest.fixture
def app_client():
    """Client HTTP async pour tester les endpoints FastAPI."""
    from backend.main import app
    return app


class TestChatStreamEndpoint:
    """Tests pour POST /chat/stream."""

    @pytest.mark.asyncio
    async def test_stream_returns_200(self, app_client):
        """POST /chat/stream retourne status 200."""
        import httpx

        mock_events = make_fake_swarm_events(["Bonjour", " à", " toi"])

        with patch("backend.session.manager.create_swarm") as mock_create:
            mock_swarm = MagicMock()
            mock_swarm.stream_async = MagicMock(return_value=async_iter(mock_events))
            mock_create.return_value = mock_swarm

            # Re-create session_manager with mocked create_swarm
            with patch("backend.routes.chat_stream.session_manager") as mock_sm:
                mock_session = {
                    "session_id": "test-sess",
                    "persona": "creator",
                    "seed_data": {},
                    "agent": mock_swarm,
                    "maturity_level": 1,
                    "active_widgets": [],
                    "assistant_name": None,
                }
                mock_sm.get_or_create_session.return_value = mock_session
                mock_sm.update_session_state = MagicMock()

                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app_client),
                    base_url="http://sophie.localhost:8000",
                ) as client:
                    response = await client.post(
                        "/chat/stream",
                        json={"message": "Bonjour", "session_id": "test-sess"},
                        headers={"host": "sophie.localhost:8000"},
                    )
                    assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_stream_content_type_is_event_stream(self, app_client):
        """POST /chat/stream retourne Content-Type text/event-stream."""
        import httpx

        mock_events = make_fake_swarm_events(["Bonjour"])

        with patch("backend.routes.chat_stream.session_manager") as mock_sm:
            mock_swarm = MagicMock()
            mock_swarm.stream_async = MagicMock(return_value=async_iter(mock_events))
            mock_session = {
                "session_id": "test-sess",
                "persona": "creator",
                "seed_data": {},
                "agent": mock_swarm,
                "maturity_level": 1,
                "active_widgets": [],
                "assistant_name": None,
            }
            mock_sm.get_or_create_session.return_value = mock_session
            mock_sm.update_session_state = MagicMock()

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_client),
                base_url="http://sophie.localhost:8000",
            ) as client:
                response = await client.post(
                    "/chat/stream",
                    json={"message": "Bonjour", "session_id": "test-sess"},
                    headers={"host": "sophie.localhost:8000"},
                )
                assert "text/event-stream" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_stream_yields_token_events(self, app_client):
        """POST /chat/stream retourne des événements SSE avec event: token."""
        import httpx

        mock_events = make_fake_swarm_events(["Bonjour", " Sophie"])

        with patch("backend.routes.chat_stream.session_manager") as mock_sm:
            mock_swarm = MagicMock()
            mock_swarm.stream_async = MagicMock(return_value=async_iter(mock_events))
            mock_session = {
                "session_id": "test-sess",
                "persona": "creator",
                "seed_data": {},
                "agent": mock_swarm,
                "maturity_level": 1,
                "active_widgets": [],
                "assistant_name": None,
            }
            mock_sm.get_or_create_session.return_value = mock_session
            mock_sm.update_session_state = MagicMock()

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_client),
                base_url="http://sophie.localhost:8000",
            ) as client:
                response = await client.post(
                    "/chat/stream",
                    json={"message": "Bonjour", "session_id": "test-sess"},
                    headers={"host": "sophie.localhost:8000"},
                )
                body = response.text
                assert "event: token" in body
                assert "data:" in body

    @pytest.mark.asyncio
    async def test_stream_yields_done_event_with_active_widgets(self, app_client):
        """POST /chat/stream retourne un event: done avec active_widgets."""
        import httpx

        mock_events = make_fake_swarm_events(["Bonjour"])

        with patch("backend.routes.chat_stream.session_manager") as mock_sm:
            mock_swarm = MagicMock()
            mock_swarm.stream_async = MagicMock(return_value=async_iter(mock_events))
            mock_session = {
                "session_id": "test-sess",
                "persona": "creator",
                "seed_data": {},
                "agent": mock_swarm,
                "maturity_level": 1,
                "active_widgets": ["widget-finances"],
                "assistant_name": None,
            }
            mock_sm.get_or_create_session.return_value = mock_session
            mock_sm.update_session_state = MagicMock()

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_client),
                base_url="http://sophie.localhost:8000",
            ) as client:
                response = await client.post(
                    "/chat/stream",
                    json={"message": "Bonjour", "session_id": "test-sess"},
                    headers={"host": "sophie.localhost:8000"},
                )
                body = response.text
                assert "event: done" in body
                assert "active_widgets" in body

    @pytest.mark.asyncio
    async def test_stream_filters_empty_tokens(self, app_client):
        """POST /chat/stream ne retourne pas de lignes data vides."""
        import httpx

        # Inclut des tokens vides dans les événements
        events = [
            {"type": "multiagent_node_stream", "event": {"data": "  "}},  # espace uniquement
            {"type": "multiagent_node_stream", "event": {"data": ""}},    # vide
            {"type": "multiagent_node_stream", "event": {"data": "Bonjour"}},
            {"type": "multiagent_result", "event": {"data": ""}},
        ]

        with patch("backend.routes.chat_stream.session_manager") as mock_sm:
            mock_swarm = MagicMock()
            mock_swarm.stream_async = MagicMock(return_value=async_iter(events))
            mock_session = {
                "session_id": "test-sess",
                "persona": "creator",
                "seed_data": {},
                "agent": mock_swarm,
                "maturity_level": 1,
                "active_widgets": [],
                "assistant_name": None,
            }
            mock_sm.get_or_create_session.return_value = mock_session
            mock_sm.update_session_state = MagicMock()

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_client),
                base_url="http://sophie.localhost:8000",
            ) as client:
                response = await client.post(
                    "/chat/stream",
                    json={"message": "Bonjour", "session_id": "test-sess"},
                    headers={"host": "sophie.localhost:8000"},
                )
                body = response.text
                # Vérifie que Bonjour est présent (token non-vide)
                assert "Bonjour" in body


class TestChatInitEndpoint:
    """Tests pour GET /chat/init."""

    @pytest.mark.asyncio
    async def test_init_returns_sse_stream_for_sophie(self, app_client):
        """GET /chat/init retourne un flux SSE pour la persona sophie (creator)."""
        import httpx

        mock_events = make_fake_swarm_events(["Bonjour ! Comment veux-tu m'appeler ?"])

        with patch("backend.routes.chat_stream.session_manager") as mock_sm:
            mock_swarm = MagicMock()
            mock_swarm.stream_async = MagicMock(return_value=async_iter(mock_events))
            mock_session = {
                "session_id": "init-sess",
                "persona": "creator",
                "seed_data": {},
                "agent": mock_swarm,
                "maturity_level": 1,
                "active_widgets": [],
                "assistant_name": None,
            }
            mock_sm.get_or_create_session.return_value = mock_session
            mock_sm.update_session_state = MagicMock()

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_client),
                base_url="http://sophie.localhost:8000",
            ) as client:
                response = await client.get(
                    "/chat/init",
                    params={"session_id": "init-sess"},
                    headers={"host": "sophie.localhost:8000"},
                )
                assert response.status_code == 200
                assert "text/event-stream" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_init_works_for_non_sophie_persona(self, app_client):
        """GET /chat/init fonctionne aussi pour les personas non-sophie (marc)."""
        import httpx

        mock_events = make_fake_swarm_events(["Bienvenue !"])

        with patch("backend.routes.chat_stream.session_manager") as mock_sm:
            mock_swarm = MagicMock()
            mock_swarm.stream_async = MagicMock(return_value=async_iter(mock_events))
            mock_session = {
                "session_id": "init-marc-sess",
                "persona": "merchant",
                "seed_data": {},
                "agent": mock_swarm,
                "maturity_level": 1,
                "active_widgets": [],
                "assistant_name": None,
            }
            mock_sm.get_or_create_session.return_value = mock_session
            mock_sm.update_session_state = MagicMock()

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_client),
                base_url="http://marc.localhost:8000",
            ) as client:
                response = await client.get(
                    "/chat/init",
                    params={"session_id": "init-marc-sess"},
                    headers={"host": "marc.localhost:8000"},
                )
                assert response.status_code == 200


class TestMaturitySentinel:
    """Tests pour la détection du sentinel [ONBOARDING_COMPLETE]."""

    @pytest.mark.asyncio
    async def test_maturity_sentinel_triggers_maturity_update_event(self, app_client):
        """
        [ONBOARDING_COMPLETE] dans un token déclenche un event: maturity_update
        et est retiré du flux de tokens.
        """
        import httpx

        events = [
            {"type": "multiagent_node_stream", "event": {"data": "Super, tu as tout configuré ! [ONBOARDING_COMPLETE]"}},
            {"type": "multiagent_result", "event": {"data": ""}},
        ]

        with patch("backend.routes.chat_stream.session_manager") as mock_sm:
            mock_swarm = MagicMock()
            mock_swarm.stream_async = MagicMock(return_value=async_iter(events))
            mock_session = {
                "session_id": "maturity-sess",
                "persona": "creator",
                "seed_data": {},
                "agent": mock_swarm,
                "maturity_level": 1,
                "active_widgets": [],
                "assistant_name": None,
            }
            mock_sm.get_or_create_session.return_value = mock_session
            mock_sm.update_session_state = MagicMock()

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_client),
                base_url="http://sophie.localhost:8000",
            ) as client:
                response = await client.post(
                    "/chat/stream",
                    json={"message": "Test", "session_id": "maturity-sess"},
                    headers={"host": "sophie.localhost:8000"},
                )
                body = response.text
                # Le sentinel doit déclencher maturity_update
                assert "event: maturity_update" in body
                # Le sentinel brut ne doit pas apparaître dans les tokens
                assert "[ONBOARDING_COMPLETE]" not in body

    @pytest.mark.asyncio
    async def test_maturity_sentinel_calls_update_session_state(self, app_client):
        """
        [ONBOARDING_COMPLETE] déclenche session_manager.update_session_state().
        """
        import httpx

        events = [
            {"type": "multiagent_node_stream", "event": {"data": "Parfait ! [ONBOARDING_COMPLETE]"}},
            {"type": "multiagent_result", "event": {"data": ""}},
        ]

        with patch("backend.routes.chat_stream.session_manager") as mock_sm:
            mock_swarm = MagicMock()
            mock_swarm.stream_async = MagicMock(return_value=async_iter(events))
            mock_session = {
                "session_id": "maturity-call-sess",
                "persona": "creator",
                "seed_data": {},
                "agent": mock_swarm,
                "maturity_level": 1,
                "active_widgets": [],
                "assistant_name": None,
            }
            mock_sm.get_or_create_session.return_value = mock_session
            mock_sm.update_session_state = MagicMock()

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_client),
                base_url="http://sophie.localhost:8000",
            ) as client:
                await client.post(
                    "/chat/stream",
                    json={"message": "Test", "session_id": "maturity-call-sess"},
                    headers={"host": "sophie.localhost:8000"},
                )
                # update_session_state doit avoir été appelé
                mock_sm.update_session_state.assert_called()
