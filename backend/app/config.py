from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    database_url: str
    catalog_xlsx_path: Path = _PROJECT_ROOT / "articles_industriels_1000.xlsx"
    docx_template_path: Path = _PROJECT_ROOT / "offre_de_prix_BOSS.docx"
    cors_origins: str = ""
    embedding_provider: str = "mistral"  # openai | mistral
    embedding_model: str = "mistral-embed"
    embedding_dimension: int = 1024
    openai_api_key: str | None = None
    mistral_api_key: str | None = None
    llm_model: str = "mistral:mistral-small-latest"
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_base_url: str = "https://cloud.langfuse.com"
    vector_search_limit: int = 5
    vector_similarity_threshold: float = 0.75

    # Boîte mail test (IMAP Gmail / Outlook)
    mail_enabled: bool = False
    mail_provider: str = "gmail"  # gmail | outlook
    mail_inbox_address: str | None = None
    mail_imap_host: str = "imap.gmail.com"
    mail_imap_port: int = 993
    mail_imap_user: str | None = None
    mail_imap_password: str | None = None
    mail_imap_folder: str = "INBOX"
    mail_sync_limit: int = 20
    mail_sync_mark_read: bool = True

    # Webhook pour notifier Vercel des nouveaux emails
    vercel_webhook_url: str | None = None

    @field_validator("catalog_xlsx_path", "docx_template_path", mode="before")
    @classmethod
    def _resolve_path(cls, value: str | Path) -> Path:
        return Path(value).expanduser()

    @property
    def cors_origin_list(self) -> list[str]:
        if not self.cors_origins.strip():
            return []
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()

