from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "KB Market Survey"
    app_env: str = "local"
    app_timezone: str = "Asia/Phnom_Penh"

    db_host: str = "localhost"
    db_port: int = 5438
    db_name: str = "survey_form_db"
    db_user: str = "postgres"
    db_password: str = "2005"
    database_url: str | None = None

    kobo_base_url: str = "https://kf.kobotoolbox.org"
    kobo_token: str = ""
    kobo_asset_uid: str = ""

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    template_path: str = "templates/template_by_dealer.xlsx"
    export_dir: str = "exports"
    auto_sync_before_report: bool = False
    auto_sync_enabled: bool = True
    auto_sync_interval_minutes: int = 1
    auto_sync_interval_seconds: int = 10
    libreoffice_path: str = ""

    # AI summary provider: google or ollama
    ai_provider: str = "ollama"
    ai_summary_enabled: bool = False
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ai_summary_timeout: int = 600
    ai_summary_temperature: float = 0.1
    ai_summary_num_ctx: int = 4096

    # Google Gemini AI summary
    google_api_key: str = ""
    google_model: str = "gemini-2.0-flash"

    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"postgresql+psycopg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def template_file(self) -> Path:
        p = Path(self.template_path)
        return p if p.is_absolute() else BASE_DIR / p

    @property
    def export_path(self) -> Path:
        p = Path(self.export_dir)
        return p if p.is_absolute() else BASE_DIR / p

settings = Settings()
