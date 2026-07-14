from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    search_provider: str = os.getenv("SEARCH_PROVIDER", "brave").lower()
    brave_search_api_key: str = os.getenv("BRAVE_SEARCH_API_KEY", "")
    serper_api_key: str = os.getenv("SERPER_API_KEY", "")

    llm_provider: str = os.getenv("LLM_PROVIDER", "deepseek").lower()
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5.6-terra")

    database_path: Path = Path(os.getenv("DATABASE_PATH", "data/regulatory_library.sqlite3"))
    max_search_results: int = int(os.getenv("MAX_SEARCH_RESULTS", "25"))
    max_deep_search_results: int = int(os.getenv("MAX_DEEP_SEARCH_RESULTS", "60"))
    deep_search_queries: int = int(os.getenv("DEEP_SEARCH_QUERIES", "4"))
    max_fetch_chars: int = int(os.getenv("MAX_FETCH_CHARS", "60000"))
    request_timeout: int = int(os.getenv("REQUEST_TIMEOUT", "25"))


SETTINGS = Settings()
