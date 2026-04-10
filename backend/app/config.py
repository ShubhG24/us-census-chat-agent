from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    snowflake_account: str
    snowflake_user: str
    snowflake_password: str
    snowflake_database: str = "US_OPEN_CENSUS_DATA__NEIGHBORHOOD_INSIGHTS__FREE_DATASET"
    snowflake_schema: str = "PUBLIC"
    snowflake_warehouse: str = "COMPUTE_WH"

    anthropic_api_key: str
    anthropic_model: str = "claude-haiku-4-5-20251001"

    app_name: str = "US Census Chat Agent"
    debug: bool = False

    query_timeout_seconds: int = 30
    max_result_rows: int = 1000
    schema_refresh_minutes: int = 30
    max_query_retries: int = 2

    max_conversation_history: int = 10


@lru_cache()
def get_settings() -> Settings:
    return Settings()
