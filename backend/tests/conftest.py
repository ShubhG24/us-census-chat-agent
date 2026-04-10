"""Shared pytest fixtures."""
import pytest
import os

# Set test environment variables before importing app modules
os.environ.setdefault("SNOWFLAKE_ACCOUNT", "test_account")
os.environ.setdefault("SNOWFLAKE_USER", "test_user")
os.environ.setdefault("SNOWFLAKE_PASSWORD", "test_password")
os.environ.setdefault("SNOWFLAKE_DATABASE", "test_db")
os.environ.setdefault("SNOWFLAKE_SCHEMA", "public")
os.environ.setdefault("SNOWFLAKE_WAREHOUSE", "test_wh")
os.environ.setdefault("ANTHROPIC_API_KEY", "test_api_key")


@pytest.fixture(autouse=True)
def reset_session_manager():
    """Reset session manager between tests."""
    from app.services.session import session_manager
    session_manager._sessions.clear()
    yield
    session_manager._sessions.clear()
