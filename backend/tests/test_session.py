"""Tests for the session management service."""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.services.session import Session, Message, SessionManager


class TestMessage:
    """Tests for Message dataclass."""

    def test_message_creation(self):
        """Test basic message creation."""
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert isinstance(msg.timestamp, datetime)
        assert msg.metadata == {}

    def test_message_with_metadata(self):
        """Test message with metadata."""
        msg = Message(
            role="assistant",
            content="Response",
            metadata={"sql_query": "SELECT * FROM test"}
        )
        assert msg.metadata["sql_query"] == "SELECT * FROM test"


class TestSession:
    """Tests for Session class."""

    def test_session_creation(self):
        """Test session creation."""
        session = Session(session_id="test-123")
        assert session.session_id == "test-123"
        assert len(session.messages) == 0
        assert isinstance(session.created_at, datetime)

    def test_add_message(self):
        """Test adding messages to session."""
        session = Session(session_id="test-123")
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there!")
        
        assert len(session.messages) == 2
        assert session.messages[0].role == "user"
        assert session.messages[1].role == "assistant"

    def test_get_history(self):
        """Test getting conversation history."""
        session = Session(session_id="test-123")
        for i in range(15):
            session.add_message("user", f"Message {i}")
        
        # Default limit is 10
        history = session.get_history(max_messages=10)
        assert len(history) == 10
        assert history[0]["content"] == "Message 5"  # First of last 10

    def test_get_context_for_llm(self):
        """Test getting LLM-formatted context."""
        session = Session(session_id="test-123")
        session.add_message("user", "Question")
        session.add_message("assistant", "Answer")
        
        context = session.get_context_for_llm()
        assert len(context) == 2
        assert context[0] == {"role": "user", "content": "Question"}
        assert context[1] == {"role": "assistant", "content": "Answer"}

    def test_last_activity_updates(self):
        """Test that last_activity updates when adding messages."""
        session = Session(session_id="test-123")
        initial_activity = session.last_activity
        
        # Wait a tiny bit and add a message
        import time
        time.sleep(0.01)
        session.add_message("user", "New message")
        
        assert session.last_activity > initial_activity


class TestSessionManager:
    """Tests for SessionManager class."""

    def test_create_session(self):
        """Test session creation."""
        manager = SessionManager()
        session = manager.create_session()
        
        assert session is not None
        assert session.session_id is not None
        assert len(session.session_id) > 0

    def test_get_existing_session(self):
        """Test retrieving an existing session."""
        manager = SessionManager()
        session1 = manager.create_session()
        session1.add_message("user", "Hello")
        
        session2 = manager.get_session(session1.session_id)
        
        assert session2 is not None
        assert session2.session_id == session1.session_id
        assert len(session2.messages) == 1

    def test_get_nonexistent_session(self):
        """Test retrieving a non-existent session."""
        manager = SessionManager()
        session = manager.get_session("nonexistent-id")
        assert session is None

    def test_get_or_create_with_existing(self):
        """Test get_or_create returns existing session."""
        manager = SessionManager()
        session1 = manager.create_session()
        
        session2 = manager.get_or_create_session(session1.session_id)
        assert session2.session_id == session1.session_id

    def test_get_or_create_without_id(self):
        """Test get_or_create creates new session when no ID."""
        manager = SessionManager()
        session = manager.get_or_create_session(None)
        assert session is not None

    def test_delete_session(self):
        """Test session deletion."""
        manager = SessionManager()
        session = manager.create_session()
        session_id = session.session_id
        
        result = manager.delete_session(session_id)
        assert result is True
        
        # Should no longer exist
        assert manager.get_session(session_id) is None

    def test_delete_nonexistent_session(self):
        """Test deleting a non-existent session."""
        manager = SessionManager()
        result = manager.delete_session("nonexistent")
        assert result is False

    def test_session_expiration(self):
        """Test that expired sessions are cleaned up."""
        manager = SessionManager(session_ttl_hours=0)  # Immediate expiration
        session = manager.create_session()
        session_id = session.session_id
        
        # Force last_activity to be old
        with patch.object(session, 'last_activity', datetime.now(timezone.utc) - timedelta(hours=1)):
            manager._sessions[session_id] = session
            retrieved = manager.get_session(session_id)
            assert retrieved is None

    def test_max_sessions_cleanup(self):
        """Test cleanup when max sessions reached."""
        manager = SessionManager(max_sessions=5)
        
        for _ in range(6):
            manager.create_session()
        
        new_session = manager.create_session()
        
        assert new_session is not None
        assert len(manager._sessions) <= manager.max_sessions


class TestSessionManagerConcurrency:
    """Tests for session manager thread safety."""

    def test_concurrent_session_creation(self):
        """Test creating sessions from multiple threads."""
        import threading
        
        manager = SessionManager()
        sessions = []
        errors = []
        
        def create_session():
            try:
                session = manager.create_session()
                sessions.append(session.session_id)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=create_session) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert len(sessions) == 10
        assert len(set(sessions)) == 10  # All unique
