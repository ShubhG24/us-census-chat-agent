import re
import json
import asyncio
import logging
from typing import AsyncGenerator, Optional
from dataclasses import dataclass

import anthropic

from app.config import Settings
from app.services.snowflake import SnowflakeService
from app.services.session import Session, SessionManager
from app.services.guardrails import GuardrailsService, ValidationResult
from app.prompts.templates import (
    SYSTEM_PROMPT,
    RESULT_INTERPRETATION_PROMPT,
    SQL_CORRECTION_PROMPT,
    ERROR_RESPONSE_TEMPLATES,
    EXAMPLE_QUESTIONS,
)

logger = logging.getLogger(__name__)

_E2E_TIMEOUT_SECONDS = 60


@dataclass
class AgentResponse:
    """Response from the chat agent."""
    message: str
    sql_query: Optional[str] = None
    query_results: Optional[dict] = None
    error: Optional[str] = None
    session_id: str = ""


class ChatAgent:
    """Core chat agent for handling user queries."""
    
    def __init__(
        self,
        settings: Settings,
        snowflake_service: SnowflakeService,
        session_manager: SessionManager,
        guardrails: Optional[GuardrailsService] = None,
        client: Optional[anthropic.AsyncAnthropic] = None,
    ):
        self.settings = settings
        self.snowflake = snowflake_service
        self.sessions = session_manager
        self.guardrails = guardrails or GuardrailsService(settings)
        self.client = client or anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    
    async def process_message(
        self,
        message: str,
        session_id: Optional[str] = None,
    ) -> AgentResponse:
        """Process a user message and return a response."""
        session = self.sessions.get_or_create_session(session_id)
        
        validation = await self.guardrails.validate_user_input(message)
        if not validation.is_valid:
            response_text = self._build_validation_error_response(validation)
            return AgentResponse(
                message=response_text,
                session_id=session.session_id,
                error=validation.reason
            )
        
        session.add_message("user", message)
        
        try:
            response = await asyncio.wait_for(
                self._generate_response(message, session),
                timeout=_E2E_TIMEOUT_SECONDS,
            )
            
            sanitized_msg = self.guardrails.sanitize_output(response.message)
            response.message = sanitized_msg

            session.add_message("assistant", sanitized_msg, {
                "sql_query": response.sql_query,
                "has_results": response.query_results is not None
            })
            
            response.session_id = session.session_id
            return response

        except asyncio.TimeoutError:
            logger.warning("End-to-end timeout reached for process_message")
            return AgentResponse(
                message=ERROR_RESPONSE_TEMPLATES["query_timeout"],
                session_id=session.session_id,
                error="timeout"
            )
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            error_msg = self._handle_error(e)
            return AgentResponse(
                message=error_msg,
                session_id=session.session_id,
                error="processing_error"
            )
    
    async def process_message_stream(
        self,
        message: str,
        session_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Process a user message and stream the response."""
        session = self.sessions.get_or_create_session(session_id)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + _E2E_TIMEOUT_SECONDS
        
        validation = await self.guardrails.validate_user_input(message)
        if not validation.is_valid:
            response_text = self._build_validation_error_response(validation)
            yield json.dumps({
                "type": "error",
                "content": response_text,
                "session_id": session.session_id
            })
            return
        
        session.add_message("user", message)
        
        yield json.dumps({
            "type": "session",
            "session_id": session.session_id
        })

        def _remaining() -> float:
            return max(deadline - loop.time(), 0.1)
        
        try:
            schema_summary = self.snowflake.get_schema_summary()
            system_prompt = SYSTEM_PROMPT.format(schema=schema_summary)
            
            conversation_history = session.get_context_for_llm(
                self.settings.max_conversation_history
            )
            
            full_response = ""
            sql_query = None
            query_succeeded = False
            
            async with self.client.messages.stream(
                model=self.settings.anthropic_model,
                max_tokens=800,
                system=[{
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=conversation_history,
            ) as stream:
                async for text in stream.text_stream:
                    full_response += text
                    if loop.time() >= deadline:
                        raise asyncio.TimeoutError()
            
            sql_query = self._extract_sql(full_response)
            
            if not sql_query:
                clean_text = full_response.strip()
                if clean_text:
                    yield json.dumps({
                        "type": "text",
                        "content": clean_text
                    })
            
            if sql_query:
                yield json.dumps({
                    "type": "sql",
                    "query": sql_query
                })
                
                sql_validation = self.guardrails.validate_sql(
                    sql_query, 
                    self.snowflake.get_table_names()
                )
                
                if not sql_validation.is_valid:
                    error_content = f"\n\nI generated an invalid query: {sql_validation.reason}"
                    full_response += error_content
                    yield json.dumps({
                        "type": "error",
                        "content": error_content
                    })
                else:
                    status_msg = "\n\n*Running query*\n"
                    full_response += status_msg
                    yield json.dumps({
                        "type": "status",
                        "content": status_msg
                    })
                    
                    max_retries = self.settings.max_query_retries
                    query_succeeded = False
                    current_sql = sql_query
                    
                    for attempt in range(1 + max_retries):
                        result = await asyncio.wait_for(
                            self.snowflake.execute_query(current_sql),
                            timeout=_remaining(),
                        )
                        
                        if result["success"]:
                            query_succeeded = True
                            sql_query = current_sql
                            break
                        
                        query_error = result.get("error", "Unknown error")
                        if attempt < max_retries:
                            retry_msg = f"*Query attempt {attempt + 1} failed, retrying with corrected SQL...*\n"
                            full_response += retry_msg
                            yield json.dumps({
                                "type": "status",
                                "content": retry_msg
                            })
                            corrected = await self._correct_sql(
                                message, current_sql, query_error,
                                self.snowflake.get_schema_summary(),
                            )
                            if corrected and corrected != current_sql:
                                cv = self.guardrails.validate_sql(
                                    corrected,
                                    self.snowflake.get_table_names()
                                )
                                if cv.is_valid:
                                    current_sql = corrected
                                    yield json.dumps({
                                        "type": "sql",
                                        "query": current_sql
                                    })
                                    continue
                            break
                    
                    if query_succeeded:
                        interpretation_chunks = []
                        async for chunk in self._interpret_results_stream(
                            message, sql_query, result, session,
                        ):
                            if loop.time() >= deadline:
                                raise asyncio.TimeoutError()
                            interpretation_chunks.append(chunk)
                            yield json.dumps({
                                "type": "text_delta",
                                "content": chunk
                            })
                        interpretation = "".join(interpretation_chunks)
                        full_response += interpretation
                    else:
                        err_msg = "\n\nThe query could not be completed. Try rephrasing your question."
                        full_response += err_msg
                        yield json.dumps({
                            "type": "error",
                            "content": err_msg
                        })
            
            sanitized = self.guardrails.sanitize_output(full_response)
            session.add_message("assistant", sanitized, {
                "sql_query": sql_query,
                "has_results": sql_query is not None and query_succeeded,
            })
            
            yield json.dumps({
                "type": "done",
                "session_id": session.session_id
            })

        except asyncio.TimeoutError:
            logger.warning("End-to-end timeout reached for streaming response")
            yield json.dumps({
                "type": "error",
                "content": ERROR_RESPONSE_TEMPLATES["query_timeout"],
                "session_id": session.session_id,
            })
        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            error_msg = self._handle_error(e)
            yield json.dumps({
                "type": "error",
                "content": error_msg,
                "session_id": session.session_id
            })
    
    async def _generate_response(
        self,
        message: str,
        session: Session,
    ) -> AgentResponse:
        """Generate a response using the LLM, with automatic retry on SQL errors."""
        schema_summary = self.snowflake.get_schema_summary()
        system_prompt = SYSTEM_PROMPT.format(schema=schema_summary)
        
        conversation_history = session.get_context_for_llm(
            self.settings.max_conversation_history
        )
        
        response = await self.client.messages.create(
            model=self.settings.anthropic_model,
            max_tokens=800,
            system=[{
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=conversation_history,
        )
        
        if not response.content:
            return AgentResponse(
                message="I couldn't generate a response right now. Please try again.",
                error="empty_llm_response",
            )
        response_text = response.content[0].text
        
        sql_query = self._extract_sql(response_text)
        
        if sql_query:
            sql_validation = self.guardrails.validate_sql(
                sql_query, 
                self.snowflake.get_table_names()
            )
            
            if not sql_validation.is_valid:
                return AgentResponse(
                    message=f"I tried to generate a query but encountered an issue: {sql_validation.reason}. Could you try rephrasing your question?",
                    sql_query=sql_query,
                    error=sql_validation.reason
                )
            
            max_retries = self.settings.max_query_retries
            last_error = None
            for attempt in range(1 + max_retries):
                result = await self.snowflake.execute_query(sql_query)
                
                if result["success"]:
                    interpretation = await self._interpret_results(
                        message, sql_query, result, session
                    )
                    return AgentResponse(
                        message=interpretation,
                        sql_query=sql_query,
                        query_results=result
                    )
                
                last_error = result.get("error", "Unknown error")
                if attempt < max_retries:
                    logger.info(f"Query attempt {attempt + 1} failed, retrying: {last_error}")
                    corrected = await self._correct_sql(
                        message, sql_query, last_error, schema_summary
                    )
                    if corrected and corrected != sql_query:
                        sql_query = corrected
                        sql_validation = self.guardrails.validate_sql(
                            sql_query,
                            self.snowflake.get_table_names()
                        )
                        if not sql_validation.is_valid:
                            break
                    else:
                        break
            
            return AgentResponse(
                message="I had trouble executing the query. Could you provide more specifics about what you're looking for?",
                sql_query=sql_query,
                error=last_error or "query_execution_failed"
            )
        
        return AgentResponse(message=response_text)
    
    async def _correct_sql(
        self,
        question: str,
        failed_sql: str,
        error: str,
        schema_summary: str,
    ) -> Optional[str]:
        """Ask the LLM to fix a failed SQL query based on the error message."""
        try:
            prompt = SQL_CORRECTION_PROMPT.format(
                question=question,
                sql=failed_sql,
                error=error,
                schema=schema_summary,
            )
            response = await self.client.messages.create(
                model=self.settings.anthropic_model,
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )
            if not response.content:
                return None
            corrected = self._extract_sql(response.content[0].text)
            return corrected
        except Exception as e:
            logger.warning(f"SQL correction failed: {e}")
            return None
    
    def _extract_sql(self, response: str) -> Optional[str]:
        """Extract SQL query from LLM response."""
        patterns = [
            r'```sql\s*(.*?)\s*```',
            r'```\s*((?:SELECT|WITH)\b.*?)\s*```',
        ]
        
        for pattern in patterns:
            matches = list(re.finditer(pattern, response, re.DOTALL | re.IGNORECASE))
            if matches:
                return matches[-1].group(1).strip()
        
        bare = re.search(
            r'(?:^|\n)((?:SELECT|WITH)\b[^`]*?(?:;|\n\n|$))',
            response,
            re.DOTALL | re.IGNORECASE,
        )
        if bare:
            candidate = bare.group(1).strip().rstrip(';')
            if len(candidate) > 20:
                return candidate

        return None
    
    _FOLLOWUP_RE = re.compile(
        r'\b(that|those|it|they|them|their|its|both|these|same|this|there'
        r'|compare|comparison|versus|vs|difference|higher|lower)\b',
        re.IGNORECASE,
    )

    def _needs_conversation_context(self, question: str) -> bool:
        """Check if the question references prior context."""
        q = question.strip()
        if len(q) < 30:
            return True
        return bool(self._FOLLOWUP_RE.search(q))

    def _build_interpretation_prompt(
        self,
        question: str,
        sql: str,
        result: dict,
        session: Optional[Session] = None,
    ) -> Optional[str]:
        """Build the interpretation prompt. Returns None if no data."""
        if not result["data"]:
            return None

        results_str = self._format_results_for_llm(result)

        context_block = ""
        if session and self._needs_conversation_context(question):
            recent = session.get_recent_messages(2)
            if recent:
                lines = []
                for msg in recent:
                    role = "User" if msg["role"] == "user" else "Assistant"
                    lines.append(f"{role}: {msg['content'][:150]}")
                context_block = "\nPrior exchange:\n" + "\n".join(lines) + "\n"

        return RESULT_INTERPRETATION_PROMPT.format(
            question=question,
            sql=sql,
            results=results_str,
            conversation_context=context_block,
        )

    async def _interpret_results(
        self,
        question: str,
        sql: str,
        result: dict,
        session: Optional[Session] = None,
    ) -> str:
        """Generate natural language interpretation of query results (non-streaming)."""
        prompt = self._build_interpretation_prompt(question, sql, result, session)
        if prompt is None:
            return "The query returned no results. This might mean the data you're looking for isn't available in the census database, or the search criteria were too specific."

        response = await self.client.messages.create(
            model=self.settings.anthropic_model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )

        if not response.content:
            return "The query returned results, but I had trouble interpreting them. Please try rephrasing your question."
        return response.content[0].text

    async def _interpret_results_stream(
        self,
        question: str,
        sql: str,
        result: dict,
        session: Optional[Session] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream natural language interpretation token-by-token."""
        prompt = self._build_interpretation_prompt(question, sql, result, session)
        if prompt is None:
            yield "The query returned no results. This might mean the data you're looking for isn't available in the census database, or the search criteria were too specific."
            return

        async with self.client.messages.stream(
            model=self.settings.anthropic_model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield text
    
    def _format_results_for_llm(self, result: dict) -> str:
        """Format query results as a markdown table for token-efficient LLM interpretation."""
        data = result.get("data", [])
        columns = result.get("columns", [])
        row_count = result.get("row_count", 0)
        has_more = result.get("has_more", False)
        
        if not data:
            return "No results"
        
        display_data = data[:20]
        
        header = " | ".join(columns)
        separator = " | ".join("---" for _ in columns)
        rows = [
            " | ".join(str(row.get(c, "")) for c in columns)
            for row in display_data
        ]
        
        table = f"{header}\n{separator}\n" + "\n".join(rows)
        more_note = " (more available)" if has_more else ""
        summary = f"Total rows returned: {row_count}{more_note}"
        
        if len(data) > 20:
            summary += f"\n(Showing first 20 of {len(data)} rows)"
        
        return f"{summary}\n\n{table}"
    
    def _build_validation_error_response(self, validation: ValidationResult) -> str:
        """Build a user-friendly response for validation errors."""
        parts = [validation.reason.strip()]
        if validation.suggestion and validation.suggestion.strip():
            parts.append(validation.suggestion.strip())
        else:
            parts.append("Happy to explore something like:")
            parts.append("\n".join(f"• {q}" for q in EXAMPLE_QUESTIONS[:3]))
        return "\n\n".join(parts)
    
    def _handle_error(self, error: Exception) -> str:
        """Handle errors and return user-friendly messages."""
        error_str = str(error).lower()
        
        if "connection" in error_str or "network" in error_str:
            return ERROR_RESPONSE_TEMPLATES["connection_error"]
        
        if "timeout" in error_str:
            return ERROR_RESPONSE_TEMPLATES["query_timeout"]
        
        if "rate" in error_str and "limit" in error_str:
            return "I'm receiving too many requests right now. Please wait a moment and try again."
        
        if "ambiguous" in error_str:
            return ERROR_RESPONSE_TEMPLATES["ambiguous_query"].format(
                clarification_needed="Could you specify which state, county, or metric you're interested in?"
            )
        
        return "I encountered an issue processing your request. Please try rephrasing your question."
    
    def get_welcome_message(self) -> str:
        """Get a welcome message for new sessions."""
        return """Hello! I'm your **US Census data assistant**. I can help you explore population statistics and demographics for the United States.

I have access to **2019 and 2020 American Community Survey** data including:
- **Population** — Total counts, age distribution, gender breakdown by state/county
- **Race and ethnicity** — Racial composition, Hispanic/Latino origin
- **Education** — High school, bachelor's, master's, and doctorate attainment
- **Income** — Median household income, income brackets
- **Housing** — Home values, rent, occupancy, owner vs. renter
- **Employment** — Labor force status, commuting patterns
- **Health insurance** — Coverage types
- **Households** — Family types, marital status

**Click a question below to get started.**"""
