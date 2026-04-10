from typing import Optional
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
import uuid
from threading import Lock


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Message:
    """Represents a single message in a conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=_utcnow)
    metadata: dict = field(default_factory=dict)


@dataclass
class Session:
    """Represents a conversation session."""
    session_id: str
    messages: list[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utcnow)
    last_activity: datetime = field(default_factory=_utcnow)
    _lock: Lock = field(default_factory=Lock, repr=False, compare=False)
    
    def add_message(self, role: str, content: str, metadata: dict = None) -> None:
        """Add a message to the conversation history."""
        with self._lock:
            self.messages.append(Message(
                role=role,
                content=content,
                metadata=metadata or {}
            ))
            self.last_activity = _utcnow()
    
    def get_history(self, max_messages: int = 10) -> list[dict]:
        """Get the recent conversation history."""
        with self._lock:
            recent = self.messages[-max_messages:] if len(self.messages) > max_messages else list(self.messages)
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat()
            }
            for msg in recent
        ]
    
    def get_recent_messages(self, count: int = 4) -> list[dict]:
        """Get the most recent messages as simple role/content dicts."""
        with self._lock:
            recent = self.messages[-count:] if len(self.messages) > count else list(self.messages)
        return [{"role": msg.role, "content": msg.content} for msg in recent]

    def get_context_for_llm(self, max_messages: int = 10) -> list[dict]:
        """Get conversation history formatted for LLM."""
        with self._lock:
            recent = self.messages[-max_messages:] if len(self.messages) > max_messages else list(self.messages)
        return [
            {"role": msg.role, "content": msg.content}
            for msg in recent
        ]


class SessionManager:
    """Manages conversation sessions in memory."""
    
    def __init__(self, max_sessions: int = 1000, session_ttl_hours: int = 24):
        self._sessions: dict[str, Session] = {}
        self._lock = Lock()
        self.max_sessions = max_sessions
        self.session_ttl = timedelta(hours=session_ttl_hours)
    
    def create_session(self) -> Session:
        """Create a new session."""
        with self._lock:
            self._cleanup_expired_sessions()
            
            session_id = str(uuid.uuid4())
            session = Session(session_id=session_id)
            self._sessions[session_id] = session
            self._enforce_session_limit()
            return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get an existing session by ID."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                if _utcnow() - session.last_activity > self.session_ttl:
                    del self._sessions[session_id]
                    return None
                return session
            return None
    
    def get_or_create_session(self, session_id: Optional[str] = None) -> Session:
        """Get existing session or create a new one (atomic)."""
        with self._lock:
            if session_id:
                session = self._sessions.get(session_id)
                if session:
                    if _utcnow() - session.last_activity <= self.session_ttl:
                        return session
                    del self._sessions[session_id]

            self._cleanup_expired_sessions()
            new_id = str(uuid.uuid4())
            session = Session(session_id=new_id)
            self._sessions[new_id] = session
            self._enforce_session_limit()
            return session
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False
    
    def _cleanup_expired_sessions(self) -> None:
        """Remove expired sessions. Must be called with _lock held."""
        now = _utcnow()
        expired = [
            sid for sid, session in self._sessions.items()
            if now - session.last_activity > self.session_ttl
        ]
        for sid in expired:
            del self._sessions[sid]

    def _enforce_session_limit(self) -> None:
        """Drop oldest sessions when count exceeds max_sessions. Must be called with _lock held."""
        if len(self._sessions) <= self.max_sessions:
            return
        excess = len(self._sessions) - self.max_sessions
        sorted_sessions = sorted(
            self._sessions.items(),
            key=lambda x: x[1].last_activity,
        )
        for sid, _ in sorted_sessions[:excess]:
            del self._sessions[sid]


session_manager = SessionManager()
