import logging
import json as _json

from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional

from app.rate_limit import limiter
from app.services.agent import ChatAgent
from app.services.session import session_manager

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    message: str
    session_id: str
    sql_query: Optional[str] = None
    error: Optional[str] = None


class SessionResponse(BaseModel):
    """Response model for session endpoints."""
    session_id: str
    message_count: int
    created_at: str


def get_agent(request: Request) -> ChatAgent:
    """Get the singleton chat agent from app state."""
    return request.app.state.agent


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("10/minute")
async def chat(request: Request, chat_request: ChatRequest):
    """Process a chat message and return a response."""
    agent = get_agent(request)
    
    try:
        response = await agent.process_message(
            message=chat_request.message,
            session_id=chat_request.session_id,
        )
        
        return ChatResponse(
            message=response.message,
            session_id=response.session_id,
            sql_query=response.sql_query,
            error=response.error,
        )
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again."
        )


@router.post("/chat/stream")
@limiter.limit("10/minute")
async def chat_stream(request: Request, chat_request: ChatRequest):
    """Process a chat message and stream the response."""
    agent = get_agent(request)
    
    async def generate():
        try:
            async for chunk in agent.process_message_stream(
                message=chat_request.message,
                session_id=chat_request.session_id,
            ):
                yield f"data: {chunk}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            yield f"data: {_json.dumps({'type': 'error', 'content': 'An unexpected error occurred. Please try again.'})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/session/new", response_model=SessionResponse)
async def create_session():
    """Create a new conversation session."""
    session = session_manager.create_session()
    
    return SessionResponse(
        session_id=session.session_id,
        message_count=0,
        created_at=session.created_at.isoformat(),
    )


@router.get("/session/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get information about an existing session."""
    session = session_manager.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionResponse(
        session_id=session.session_id,
        message_count=len(session.messages),
        created_at=session.created_at.isoformat(),
    )


@router.get("/session/{session_id}/history")
async def get_session_history(
    session_id: str,
    limit: int = Query(default=50, ge=1, le=200),
):
    """Get the conversation history for a session."""
    session = session_manager.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session_id,
        "messages": session.get_history(max_messages=limit),
    }


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a conversation session."""
    deleted = session_manager.delete_session(session_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"message": "Session deleted", "session_id": session_id}


@router.get("/welcome")
async def get_welcome(request: Request):
    """Get the welcome message for new users."""
    agent = get_agent(request)
    return {"message": agent.get_welcome_message()}


@router.get("/schema")
async def get_schema(request: Request):
    """Get a high-level summary of available data (no raw internals)."""
    snowflake_service = request.app.state.snowflake
    
    table_names = snowflake_service.get_table_names()
    return {
        "available_tables_count": len(table_names),
        "summary": "US Census Bureau ACS data (2019-2020) including population, race, education, income, housing, employment, and health insurance at state and county levels.",
    }
