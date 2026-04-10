"""Integration tests for the API endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch, MagicMock, PropertyMock

from app.main import app
from app.services.snowflake import SnowflakeService
from app.services.agent import ChatAgent
from app.services.guardrails import GuardrailsService, ValidationResult
from app.services.session import session_manager
from app.config import get_settings


@pytest.fixture
def mock_snowflake_service():
    """Create a mock Snowflake service."""
    service = Mock(spec=SnowflakeService)
    service._pool_initialized = True
    type(service).is_healthy = PropertyMock(return_value=True)
    service.schema_cache = {
        "tables": [
            {"name": "population", "type": "TABLE", "row_count": 1000, "comment": "Population data", "is_key_table": True}
        ],
        "table_details": {
            "population": {
                "columns": [
                    {"name": "state", "type": "VARCHAR", "nullable": False, "comment": "State name"},
                    {"name": "population", "type": "NUMBER", "nullable": False, "comment": "Population count"}
                ]
            }
        }
    }
    service.get_schema_summary.return_value = "## Tables\n- population"
    service.get_table_names.return_value = ["population"]
    service.execute_query = AsyncMock(return_value={
        "success": True,
        "data": [{"state": "California", "population": 39538223}],
        "columns": ["state", "population"],
        "row_count": 1,
        "has_more": False,
        "error": None
    })
    return service


@pytest.fixture
def client(mock_snowflake_service):
    """Create test client with mocked services."""
    app.state.snowflake = mock_snowflake_service

    with patch('app.services.guardrails.anthropic.AsyncAnthropic'):
        with patch('app.services.agent.anthropic.AsyncAnthropic') as mock_anthropic:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.content = [Mock(text="The population of California is 39,538,223.")]
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.return_value = mock_client

            settings = get_settings()
            guardrails = GuardrailsService(settings)
            guardrails.validate_user_input = AsyncMock(return_value=ValidationResult(is_valid=True, reason="ok"))
            guardrails.sanitize_output = lambda x: x

            agent = ChatAgent(
                settings=settings,
                snowflake_service=mock_snowflake_service,
                session_manager=session_manager,
                guardrails=guardrails,
            )
            agent.client = mock_client
            app.state.agent = agent

            yield TestClient(app)


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self, client):
        """Test health check returns 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_root_endpoint(self, client):
        """Test root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        assert "message" in response.json()


class TestChatEndpoint:
    """Tests for chat endpoint."""

    def test_chat_valid_message(self, client):
        """Test chat with valid message."""
        response = client.post(
            "/api/chat",
            json={"message": "What is the population of California?"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "session_id" in data

    def test_chat_creates_session(self, client):
        """Test that chat creates a session."""
        response = client.post(
            "/api/chat",
            json={"message": "Hello"}
        )
        
        assert response.status_code == 200
        assert response.json()["session_id"] is not None

    def test_chat_maintains_session(self, client):
        """Test that session is maintained across messages."""
        response1 = client.post(
            "/api/chat",
            json={"message": "Hello"}
        )
        session_id = response1.json()["session_id"]
        
        response2 = client.post(
            "/api/chat",
            json={"message": "Follow up question", "session_id": session_id}
        )
        
        assert response2.json()["session_id"] == session_id

    def test_chat_empty_message_rejected(self, client):
        """Test that empty messages are rejected."""
        response = client.post(
            "/api/chat",
            json={"message": ""}
        )
        
        assert response.status_code == 422

    def test_chat_long_message_rejected(self, client):
        """Test that very long messages are rejected."""
        response = client.post(
            "/api/chat",
            json={"message": "a" * 2500}
        )
        
        assert response.status_code == 422


class TestStreamEndpoint:
    """Tests for streaming chat endpoint."""

    def test_stream_returns_event_stream(self, client):
        """Test that stream endpoint returns SSE format."""
        response = client.post(
            "/api/chat/stream",
            json={"message": "Hello"}
        )
        
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]


class TestSessionEndpoints:
    """Tests for session management endpoints."""

    def test_create_session(self, client):
        """Test session creation endpoint."""
        response = client.post("/api/session/new")
        
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "created_at" in data

    def test_get_session(self, client):
        """Test getting session info."""
        create_response = client.post("/api/session/new")
        session_id = create_response.json()["session_id"]
        
        response = client.get(f"/api/session/{session_id}")
        
        assert response.status_code == 200
        assert response.json()["session_id"] == session_id

    def test_get_nonexistent_session(self, client):
        """Test getting a non-existent session."""
        response = client.get("/api/session/nonexistent-id")
        
        assert response.status_code == 404

    def test_get_session_history(self, client):
        """Test getting session history."""
        chat_response = client.post(
            "/api/chat",
            json={"message": "Hello"}
        )
        session_id = chat_response.json()["session_id"]
        
        response = client.get(f"/api/session/{session_id}/history")
        
        assert response.status_code == 200
        assert "messages" in response.json()

    def test_get_session_history_limit_cap(self, client):
        """Test that history limit is capped."""
        response = client.get("/api/session/some-id/history?limit=999")
        assert response.status_code == 422

    def test_delete_session(self, client):
        """Test session deletion."""
        create_response = client.post("/api/session/new")
        session_id = create_response.json()["session_id"]
        
        response = client.delete(f"/api/session/{session_id}")
        
        assert response.status_code == 200
        
        get_response = client.get(f"/api/session/{session_id}")
        assert get_response.status_code == 404


class TestSchemaEndpoint:
    """Tests for schema endpoint."""

    def test_get_schema(self, client):
        """Test schema endpoint returns sanitized info."""
        response = client.get("/api/schema")
        
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "available_tables_count" in data


class TestWelcomeEndpoint:
    """Tests for welcome message endpoint."""

    def test_get_welcome(self, client):
        """Test welcome endpoint returns message."""
        response = client.get("/api/welcome")
        
        assert response.status_code == 200
        assert "message" in response.json()
        assert len(response.json()["message"]) > 0
