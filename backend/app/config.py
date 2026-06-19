from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    database_url: str
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


settings = Settings()
