import pathlib
from pydantic_settings import BaseSettings


def _find_env() -> str | None:
    # Walk up from this file: backend/app/shared -> backend -> root -> parent
    here = pathlib.Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        cand = parent / ".env"
        if cand.is_file():
            return str(cand)
    return None


_ENV_FILE = _find_env()


class Settings(BaseSettings):
    LLM_PROVIDER: str = "stub"  # stub | anthropic | openai | ollama
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"
    DATABASE_URL: str = "sqlite:///./data/biomedeng.db"
    DATA_DIR: str = "./data"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    PUBMED_EMAIL: str = "you@example.com"
    PUBMED_TOOL: str = "biomedeng-harness"

    class Config:
        env_file = _ENV_FILE
        extra = "ignore"


settings = Settings()
