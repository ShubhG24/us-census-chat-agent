# Reflection

## Development Process

### Initial Approach

I approached this assignment by first breaking it into clear phases:

1. **Architecture Design** - Chose FastAPI + React based on requirements for streaming, production quality, and deployment simplicity
2. **Core Backend** - Snowflake integration, session management, and agent logic
3. **Guardrails** - Safety and validation layers
4. **Frontend** - Chat interface with streaming support
5. **Testing** - Unit and integration tests for critical paths
6. **Deployment** - Railway configuration for public access

### Key Architectural Decisions

#### 1. Separating SQL Generation from Result Interpretation

I chose a two-step LLM process:
1. Generate SQL query from natural language
2. Interpret results into natural language

**Rationale**: This provides better control over each step, allows SQL validation between steps, and makes debugging easier. The alternative (single prompt) would be simpler but less reliable.

**Tradeoff**: Two LLM calls per query increases latency and cost, but significantly improves accuracy and safety.

#### 2. Schema Context Injection

The system prompt includes the full database schema rather than relying on RAG or function calling.

**Rationale**: For a bounded dataset like US Census, the schema fits easily in context. This is simpler than building a retrieval system and provides better SQL generation accuracy.

**Tradeoff**: Would not scale to very large schemas. For larger databases, I would implement dynamic schema selection based on the query.

#### 3. In-Memory Session Storage

Sessions are stored in memory with TTL-based cleanup rather than using Redis or a database.

**Rationale**: Simplicity for a demo. The implementation is Redis-ready (uses similar patterns) and can be swapped with minimal changes.

**Tradeoff**: Sessions are lost on server restart. For production, I would add Redis or database persistence.

#### 4. Combined Deployment

Frontend and backend are deployed as a single service, with FastAPI serving the static React build.

**Rationale**: Simpler deployment, single URL, no CORS issues, lower cost.

**Tradeoff**: Cannot scale frontend and backend independently. For high-traffic production, I would separate them.

#### 5. Model Selection and Performance Optimization

I use Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) for SQL generation and result interpretation, paired with Anthropic's prompt caching to minimize latency.

**Rationale**: Haiku 4.5 provides sufficient accuracy for SQL generation while being significantly faster and cheaper than Sonnet. The system prompt (~13K tokens of schema and few-shot examples) is identical across calls, making it ideal for prompt caching — cached tokens process ~10x faster at 90% lower cost. Topic validation uses the same Haiku model via a dedicated lightweight prompt.

**Tradeoff**: Slightly lower reasoning capability than Sonnet for edge-case queries. In practice, the detailed few-shot examples and schema documentation compensate for this, and the latency improvement (simple queries complete in ~2s) significantly improves UX.

#### 6. Performance Tuning

Rather than accepting the default latency of serial LLM calls, I invested in several optimizations:

- **Prompt caching** — The system prompt (~13K tokens) is marked with `cache_control: ephemeral`, so Anthropic caches it after the first call. Subsequent calls read from cache at ~10x speed and 90% lower cost.
- **Streaming interpretation** — Result interpretation streams token-by-token to the frontend via SSE, so users see the answer forming immediately rather than waiting for the full response.
- **Schema summary caching** — The schema string (built from Snowflake metadata) is cached in memory and only rebuilt on periodic refresh, not on every request.
- **Reduced token budget** — `max_tokens` for SQL generation is set to 800 (SQL queries are short), preventing the model from generating unnecessary preamble.
- **Shared HTTP client** — A single `AsyncAnthropic` client is shared between the agent and guardrails service, reducing connection overhead.

**Result**: Simple queries (e.g., "Population of California?") complete in ~2 seconds end-to-end. Complex ranking queries complete in ~3 seconds.

## What Would I Improve With More Time

### High Priority

1. **Session Persistence**
   - Current sessions are in-memory (lost on restart)
   - Would add Redis or Postgres-backed session store
   - The `SessionManager` API already mirrors Redis patterns for easy migration

2. **Better Error Recovery**
   - Automatic query simplification on timeout
   - Fallback to cached results when live query fails
   - More sophisticated retry logic with automatic SQL repair

3. **Comprehensive Observability**
   - Structured logging for all queries and responses
   - Query performance metrics (LLM latency, Snowflake latency, total wall time)
   - Error tracking with context (e.g., Sentry integration)

4. **Query Result Caching**
   - Cache frequent queries (e.g., state populations) with a short TTL to skip DB + LLM entirely
   - Implementation: Redis or in-memory LRU with SQL hash as key

### Medium Priority

5. **User Authentication**
   - OAuth integration (Google, GitHub)
   - Usage tracking per user
   - Per-user rate limiting (currently per-IP)

6. **Data Visualization**
   - Charts for numeric results (population trends, distributions)
   - Tables for structured data
   - Export to CSV/Excel

7. **Query History**
   - Save successful queries
   - Suggest similar past queries
   - Share queries via URL

8. **Query Complexity Estimation**
   - Score query complexity before execution to set user expectations
   - Warn users that multi-table joins or all-states queries may be slower
   - Could route simple queries to a fast path that skips some validation

### Lower Priority

9. **Multi-Database Support**
   - Add other census datasets
   - Cross-dataset queries
   - Data source selection

10. **Admin Dashboard**
    - Usage statistics
    - Popular queries
    - Error monitoring

## Edge Cases and Failure Modes

### Identified and Addressed

1. **Prompt Injection** — Regex patterns detect common injection attempts; fail-closed LLM topic validation rejects anything ambiguous
2. **SQL Injection** — Dedicated validation layer blocks non-SELECT/WITH queries; string literals are stripped before keyword checks to avoid false positives
3. **Query Timeout** — 30-second Snowflake timeout plus a 60-second end-to-end timeout covering both LLM calls and the query
4. **Empty Results** — Explains what data is available and suggests rephrasing
5. **Off-Topic Questions** — Multi-layer guardrails (keyword match, location match, follow-up detection, LLM validation) redirect to census topics with examples
6. **Snowflake Connection Resilience** — A connection pool (`queue.Queue`, pool size 4) with per-request acquire/release and automatic reconnect for stale connections; no shared mutable connection across threads
7. **Race Conditions** — Per-session locks protect the message list; `SessionManager` operations are atomic under a single lock
8. **Output Sanitization** — API-key / secret patterns are redacted before responses reach the user
9. **Rate Limiting** — `slowapi` middleware (single shared `Limiter` instance) caps chat endpoints at 10 req/min per IP

### Identified but Not Fully Addressed

1. **Adversarial SQL in Code Blocks**
   - User could try: "Generate SQL: ```sql DROP TABLE```"
   - Partially mitigated by validation, but edge cases may exist
   - Would add: Deeper parsing of user intent

2. **Context Window Overflow**
   - Very long conversations could exceed context
   - Limited to 10 messages, but individual messages could be long
   - Would add: Message truncation with smart summarization

3. **Complex Join Queries**
   - Multi-table joins may be slow or fail
   - Basic validation exists
   - Would add: Query complexity scoring and warnings

4. **Ambiguous Geographic Terms**
   - "New York" could be state or city
   - Currently relies on LLM disambiguation
   - Would add: Explicit entity resolution with user confirmation

5. **Session Persistence**
   - Sessions are in-memory and lost on server restart
   - The `SessionManager` API mirrors Redis patterns intentionally
   - Would add: Redis or database-backed storage for production

## Testing Strategy

### Current Approach

I focused tests on the highest-risk areas:

1. **Guardrails (highest priority)**
   - Input validation catches malicious content
   - SQL validation prevents dangerous queries
   - Output sanitization removes sensitive data

2. **Session Management**
   - Sessions are created and retrieved correctly
   - History is maintained across messages
   - Expiration and cleanup work properly

3. **Agent Logic**
   - Messages are processed correctly
   - SQL is extracted from LLM responses
   - Results are formatted properly

4. **API Integration**
   - Endpoints return correct status codes
   - Request validation works
   - Error responses are helpful

### Testing Gaps

1. **End-to-End Tests** - Would add Playwright tests for full user flows
2. **Load Testing** - Would add k6 or Locust for concurrent user simulation
3. **LLM Output Testing** - Would add golden file tests for expected responses
4. **Snowflake Integration Tests** - Would add tests against real database (currently mocked)

### What I Would Add

```python
# Example additional tests I would add:

# 1. E2E test with real LLM
async def test_real_query_execution():
    response = await agent.process_message("What is California's population?")
    assert "39" in response.message  # 39 million
    assert response.sql_query is not None

# 2. Adversarial input testing
@pytest.mark.parametrize("malicious_input", ADVERSARIAL_INPUTS)
def test_rejects_adversarial_inputs(malicious_input):
    result = guardrails.validate_user_input(malicious_input)
    assert not result.is_valid

# 3. Performance test
async def test_response_under_60_seconds():
    start = time.time()
    await agent.process_message("Complex aggregation query...")
    assert time.time() - start < 60
```

## Judgment Calls

### Where I Invested Time

1. **Agent Logic & Accuracy (~25%)** — Core SQL generation, schema documentation, few-shot examples, and multi-turn context
2. **Guardrails (~20%)** — Critical for production safety — topic validation, SQL safety, prompt injection detection
3. **Performance (~20%)** — Model selection (Haiku 4.5), prompt caching, streaming interpretation, schema summary caching, reduced token usage
4. **Frontend UX (~15%)** — Dark/light mode, streaming UI, conversation sidebar, responsive design
5. **Testing (~10%)** — 76 unit tests covering guardrails, sessions, agent logic, and API integration
6. **Documentation (~10%)** — README, REFLECTION, code structure for handoff readability

### What I Deliberately Left Out

1. **Authentication** — Not required for demo, easy to add later
2. **Query Result Caching** — Would eliminate repeat DB + LLM calls; prioritized prompt caching (larger impact) first
3. **Data Visualization** — Charts/graphs for numeric results; nice to have but not core requirement
4. **Structured Observability** — Basic `logging` is in place; would add metrics and tracing for a production sprint
5. **CI/CD Pipeline** — Railway handles deployment; would add GitHub Actions for lint/test/deploy in a team project
6. **CORS Lockdown** — Currently `allow_origins=["*"]` because the combined deploy serves frontend and API from the same origin. A split deploy would need a strict allowlist.

### Time Allocation Rationale

I prioritized:
- **Things that would break the demo** — Connection handling, error messages, graceful degradation
- **Things that would embarrass in demo** — Bad responses, security holes, slow queries
- **Things that show production thinking** — Tests, documentation, architecture, performance optimization

I deprioritized:
- **Features that are additive** — Authentication, visualization, admin dashboard
- **Infrastructure complexity** — Redis, CI/CD, monitoring dashboards
