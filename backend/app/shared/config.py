from pydantic_settings import BaseSettings


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
        env_file = "../.env"
        extra = "ignore"


settings = Settings()
