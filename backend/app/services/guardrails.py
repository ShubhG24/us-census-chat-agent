import logging
import re
import json
from typing import Optional
from dataclasses import dataclass

import anthropic

from app.config import Settings

logger = logging.getLogger(__name__)

from app.prompts.templates import (
    TOPIC_VALIDATION_PROMPT,
    ERROR_RESPONSE_TEMPLATES,
    EXAMPLE_QUESTIONS,
)


@dataclass
class ValidationResult:
    """Result of a validation check."""
    is_valid: bool
    reason: str
    suggestion: Optional[str] = None


_STRIP_STRINGS_RE = re.compile(r"'(?:[^'\\]|\\.)*'", re.DOTALL)


class GuardrailsService:
    """Service for validating inputs and outputs."""
    
    FORBIDDEN_SQL_KEYWORDS = [
        r'\bINSERT\b', r'\bUPDATE\b', r'\bDELETE\b', r'\bDROP\b',
        r'\bCREATE\b', r'\bALTER\b', r'\bTRUNCATE\b', r'\bGRANT\b',
        r'\bREVOKE\b', r'\bEXEC\b', r'\bEXECUTE\b', r'\bMERGE\b',
    ]
    
    FORBIDDEN_SCHEMA_PATTERNS = [
        r'\bINFORMATION_SCHEMA\b',
        r'\bACCOUNT_USAGE\b',
        r'\bSNOWFLAKE\s*\.\s*ACCOUNT_USAGE\b',
        r'\bSHOW\s+\w+',
        r'\bDESCRIBE\s+USER\b',
        r'\bSHOW\s+GRANTS\b',
    ]
    
    INJECTION_PATTERNS = [
        r'ignore\s+(previous|all|above)\s+instructions',
        r'disregard\s+(previous|all|above)',
        r'forget\s+(everything|all|previous)',
        r'you\s+are\s+now\s+',
        r'act\s+as\s+if',
        r'pretend\s+(to\s+be|you\s+are)',
        r'new\s+instructions:',
        r'system\s+prompt:',
    ]
    
    CENSUS_KEYWORDS = [
        'population', 'census', 'demographic', 'age', 'gender', 'sex',
        'race', 'ethnicity', 'housing', 'household', 'income', 'poverty',
        'education', 'employment', 'state', 'county', 'city', 'region',
        'birth', 'death', 'migration', 'density', 'urban', 'rural',
        'married', 'single', 'family', 'children', 'elderly', 'median',
        'average', 'total', 'percent', 'growth', 'decline', 'change',
        'american', 'united states', 'usa', 'us ', 'california', 'texas',
        'new york', 'florida', 'illinois', 'people', 'citizens', 'residents',
        'renter', 'owner', 'occupied', 'bachelor', 'degree', 'hispanic', 'latino',
        'white', 'black', 'asian', 'native', 'commute', 'insurance', 'veteran',
    ]
    
    LOCATION_NAMES = [
        'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado',
        'connecticut', 'delaware', 'florida', 'georgia', 'hawaii', 'idaho',
        'illinois', 'indiana', 'iowa', 'kansas', 'kentucky', 'louisiana',
        'maine', 'maryland', 'massachusetts', 'michigan', 'minnesota',
        'mississippi', 'missouri', 'montana', 'nebraska', 'nevada',
        'new hampshire', 'new jersey', 'new mexico', 'new york', 'north carolina',
        'north dakota', 'ohio', 'oklahoma', 'oregon', 'pennsylvania',
        'rhode island', 'south carolina', 'south dakota', 'tennessee', 'texas',
        'utah', 'vermont', 'virginia', 'washington', 'west virginia',
        'wisconsin', 'wyoming', 'dc', 'puerto rico',
        'los angeles', 'chicago', 'houston', 'phoenix', 'philadelphia',
        'san antonio', 'san diego', 'dallas', 'san jose', 'austin',
        'jacksonville', 'san francisco', 'seattle', 'denver', 'boston',
        'detroit', 'miami', 'atlanta', 'minneapolis', 'brooklyn', 'queens',
        'bronx', 'manhattan', 'staten island', 'las vegas', 'portland',
    ]
    
    FOLLOWUP_PATTERNS = [
        r'^(what|how)\s+about\s+',
        r'^and\s+(what|how|the)\s+',
        r'^(same|similar)\s+(for|in|question)',
        r'^(show|tell)\s+me\s+(the\s+)?(same|that)',
        r'^compare\s+(it|this|that)\s+(to|with)',
        r'^(now|ok|okay)\s+(what|how|show)',
        r'^for\s+\w+\s*\??$',
    ]
    
    def __init__(self, settings: Settings, client: Optional[anthropic.AsyncAnthropic] = None):
        self.settings = settings
        self.client = client or anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    
    async def validate_user_input(self, message: str) -> ValidationResult:
        """Validate user input for safety and relevance."""
        message_lower = message.lower()
        
        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, message_lower, re.IGNORECASE):
                return ValidationResult(
                    is_valid=False,
                    reason="Something about that message didn't look like a normal data question, so I didn't process it.",
                    suggestion="Ask me in your own words about US population, a state or county, housing, income, or demographics."
                )
        
        if len(message) > 2000:
            return ValidationResult(
                is_valid=False,
                reason="That's a bit too long for me to take in at once—could you trim it to under 2,000 characters?",
                suggestion="A shorter question works best. Try focusing on one place or one topic (e.g. population or median income)."
            )
        
        if len(message.strip()) < 2:
            return ValidationResult(
                is_valid=False,
                reason="Could you add a bit more—what would you like to know about US Census data?",
                suggestion="For example: \"What's the population of Ohio?\" or \"How does renter share compare in Texas?\""
            )
        
        has_census_keyword = any(
            keyword in message_lower 
            for keyword in self.CENSUS_KEYWORDS
        )
        
        is_valid_greeting = any(
            greeting in message_lower 
            for greeting in ['hello', 'hi', 'help', 'what can you do', 'what data', 'hey', 'good morning', 'good afternoon']
        )
        
        math_pattern = r'^\s*\d+\s*[\+\-\*\/\×\÷x]\s*\d+\s*$'
        if re.search(math_pattern, message_lower, re.IGNORECASE):
            return ValidationResult(
                is_valid=False,
                reason="Quick math isn't really my lane—I'm here to pull real numbers from US Census data for you.",
                suggestion="Ask something like median household income in a state, or population by county."
            )
        
        if is_valid_greeting and len(message) < 50:
            return ValidationResult(is_valid=True, reason="Valid greeting")
        
        if has_census_keyword:
            return ValidationResult(is_valid=True, reason="Input validated")
        
        for pattern in self.FOLLOWUP_PATTERNS:
            if re.search(pattern, message_lower, re.IGNORECASE):
                return ValidationResult(is_valid=True, reason="Follow-up question")
        
        has_location = any(
            loc in message_lower 
            for loc in self.LOCATION_NAMES
        )
        if has_location and len(message) < 100:
            return ValidationResult(is_valid=True, reason="Location-based query")
        
        return await self._validate_topic_with_llm(message)
    
    _TOPIC_VALIDATION_MODEL = "claude-haiku-4-5-20251001"

    async def _validate_topic_with_llm(self, message: str) -> ValidationResult:
        """Use LLM to validate topic relevance. Fails closed on errors."""
        try:
            response = await self.client.messages.create(
                model=self._TOPIC_VALIDATION_MODEL,
                max_tokens=200,
                messages=[{
                    "role": "user",
                    "content": TOPIC_VALIDATION_PROMPT.format(message=message)
                }]
            )
            
            if not response.content:
                raise ValueError("Empty LLM response")
            content = response.content[0].text
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end > start:
                result = json.loads(content[start:end + 1])
                return ValidationResult(
                    is_valid=result.get("is_valid", False),
                    reason=result.get("reason", "Topic validation failed"),
                    suggestion=result.get("suggested_reformulation")
                )
        except Exception as e:
            logger.warning(f"Topic validation error: {e}")
        
        return ValidationResult(
            is_valid=False,
            reason="I wasn't able to verify your question right now. Could you try again?",
            suggestion="Try asking about US population, demographics, income, or housing data."
        )
    
    def validate_sql(self, sql: str, available_tables: list[str]) -> ValidationResult:
        """Validate SQL query for safety."""
        sql_no_strings = _STRIP_STRINGS_RE.sub("''", sql)
        sql_upper = sql_no_strings.upper()
        
        for pattern in self.FORBIDDEN_SQL_KEYWORDS:
            if re.search(pattern, sql_upper):
                return ValidationResult(
                    is_valid=False,
                    reason=f"Query contains forbidden operation",
                    suggestion="Only SELECT queries are allowed."
                )
        
        for pattern in self.FORBIDDEN_SCHEMA_PATTERNS:
            if re.search(pattern, sql_upper):
                return ValidationResult(
                    is_valid=False,
                    reason="Query cannot access system or metadata schemas directly",
                    suggestion="Only SELECT from data tables is allowed."
                )
        
        sql_clean = re.sub(r'/\*.*?\*/', '', sql_no_strings, flags=re.DOTALL)
        sql_clean = re.sub(r'--.*$', '', sql_clean, flags=re.MULTILINE)
        sql_clean = sql_clean.strip()
        
        first_keyword = sql_clean.upper().split()[0] if sql_clean.split() else ""
        if first_keyword not in ('SELECT', 'WITH'):
            return ValidationResult(
                is_valid=False,
                reason="Query must be a SELECT or WITH statement",
                suggestion="Please use SELECT to query data."
            )
        
        if sql.count(';') > 1:
            return ValidationResult(
                is_valid=False,
                reason="Multiple statements not allowed",
                suggestion="Please use a single query."
            )
        
        tables_mentioned = self._extract_table_references(sql)
        cte_names = self._extract_cte_names(sql)
        available_upper = [t.upper() for t in available_tables]
        cte_upper = {n.upper() for n in cte_names}
        
        invalid_tables = [
            t for t in tables_mentioned 
            if t.upper() not in available_upper and t.upper() not in cte_upper
        ]
        
        if invalid_tables and available_tables:
            return ValidationResult(
                is_valid=False,
                reason=f"References unknown tables: {', '.join(invalid_tables)}",
                suggestion=f"Available tables: {', '.join(available_tables[:5])}"
            )
        
        return ValidationResult(is_valid=True, reason="SQL validated")
    
    def _extract_table_references(self, sql: str) -> list[str]:
        """Extract table names from SQL after FROM / JOIN."""
        tables: list[str] = []

        unquoted = [
            r'\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            r'\bJOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        ]
        for pattern in unquoted:
            tables.extend(re.findall(pattern, sql, re.IGNORECASE))

        quoted = [
            r'\bFROM\s+(?:[a-zA-Z_][a-zA-Z0-9_]*\.)?"([^"]+)"',
            r'\bJOIN\s+(?:[a-zA-Z_][a-zA-Z0-9_]*\.)?"([^"]+)"',
        ]
        for pattern in quoted:
            tables.extend(re.findall(pattern, sql, re.IGNORECASE))

        return list(dict.fromkeys(tables))
    
    def _extract_cte_names(self, sql: str) -> list[str]:
        """Extract CTE alias names from WITH clauses so they aren't flagged as unknown tables."""
        names: list[str] = []
        pattern = r'\bWITH\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+AS\s*\('
        match = re.search(pattern, sql, re.IGNORECASE)
        if match:
            names.append(match.group(1))
        for m in re.finditer(r'\)\s*,\s*([a-zA-Z_][a-zA-Z0-9_]*)\s+AS\s*\(', sql, re.IGNORECASE):
            names.append(m.group(1))
        return names
    
    def get_off_topic_response(self, message: str) -> str:
        """Generate a helpful off-topic response."""
        template = ERROR_RESPONSE_TEMPLATES["off_topic"]
        
        suggestions = "\n".join(f"• {q}" for q in EXAMPLE_QUESTIONS[:3])
        redirect = f"If you'd like to try something in my wheelhouse:\n{suggestions}"
        
        return template.format(redirect_suggestion=redirect)
    
    def get_error_response(self, error_type: str, **kwargs) -> str:
        """Get a user-friendly error response."""
        template = ERROR_RESPONSE_TEMPLATES.get(
            error_type, 
            "I encountered an issue processing your request. Please try again."
        )
        
        try:
            return template.format(**kwargs)
        except KeyError:
            return template
    
    def sanitize_output(self, response: str) -> str:
        """Sanitize the output before sending to user."""
        patterns_to_remove = [
            r'api[_-]?key[:\s]*[a-zA-Z0-9-]+',
            r'password[:\s]*\S+',
            r'secret[:\s]*\S+',
            r'token[:\s]*[a-zA-Z0-9-]+',
        ]
        
        sanitized = response
        for pattern in patterns_to_remove:
            sanitized = re.sub(pattern, '[REDACTED]', sanitized, flags=re.IGNORECASE)
        
        return sanitized
