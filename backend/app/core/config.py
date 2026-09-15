from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_ROOT / "data"
MODELS_DIR = BACKEND_ROOT / "artifacts" / "models"


class Settings(BaseSettings):
    """
    Central config. Values are overridable via environment variables /
    a .env file -- nothing here is a secret, and no secret ever gets
    passed to the LLM/agent layer per the PRD's guardrails.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://postgres:lendai_dev@localhost:5432/lendai"
    policy_version: str = "PL_2026_V1"
    policy_config_path: Path = DATA_DIR / "personal_loan_policy_v1.json"
    tool_schemas_path: Path = DATA_DIR / "tool_schemas.json"

    # Guardrail: hard ceiling on tool calls per agent run (fail-safe escalation
    # to human review if exceeded -- see PRD "Guardrails").
    agent_max_steps: int = 12

    # Guardrail: wall-clock ceiling per individual tool call.
    tool_timeout_seconds: float = 5.0

    # Document OCR confidence floor below which evidence cannot silently pass.
    ocr_confidence_floor: float = 0.7

    cors_allow_origins: list[str] = ["*"]

    # Required to call POST /admin/bootstrap (see app/api/admin.py) -- a
    # one-time setup endpoint for environments with no shell access to the
    # database (e.g. Vercel serverless + a managed Postgres). None means
    # the endpoint always refuses.
    admin_bootstrap_token: str | None = None


settings = Settings()
