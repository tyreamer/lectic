from dataclasses import dataclass, field
import os
from pathlib import Path
from uuid import UUID

VERSION = "pilot-1"
ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    data: Path = field(default_factory=lambda: Path(os.getenv("LECTIC_CLOUD_DATA", "~/.lectic-pilot")).expanduser().resolve())
    database: str = field(default_factory=lambda: os.getenv("LECTIC_DATABASE_URL", ""))
    supabase_url: str = field(default_factory=lambda: os.getenv("SUPABASE_URL", "").rstrip("/"))
    publishable_key: str = field(default_factory=lambda: os.getenv("SUPABASE_PUBLISHABLE_KEY", ""))
    secret_key: str = field(default_factory=lambda: os.getenv("SUPABASE_SECRET_KEY", ""))
    origin: str = field(default_factory=lambda: os.getenv("LECTIC_ORIGIN", "http://127.0.0.1:8780").rstrip("/"))
    model: str = field(default_factory=lambda: os.getenv("LECTIC_MODEL", "gpt-5-mini"))
    transcription_model: str = "whisper-1"
    max_sources: int = field(default_factory=lambda: int(os.getenv("LECTIC_MAX_SOURCES", "20")))
    max_upload: int = field(default_factory=lambda: int(os.getenv("LECTIC_MAX_UPLOAD_BYTES", str(100 * 1024**2))))
    max_storage: int = field(default_factory=lambda: int(os.getenv("LECTIC_MAX_STORAGE_BYTES", str(1024**3))))
    max_seconds: int = field(default_factory=lambda: int(os.getenv("LECTIC_MAX_MEDIA_SECONDS", "900")))
    monthly_microdollars: int = field(default_factory=lambda: int(os.getenv("LECTIC_AI_BUDGET_MICRODOLLARS", "30000000")))
    invite_limit: int = 10
    dev: bool = field(default_factory=lambda: os.getenv("LECTIC_DEV", "") == "1")
    chat_enabled: bool = field(default_factory=lambda: os.getenv("LECTIC_CHAT_ENABLED", "") == "1")

    @property
    def mcp_resource(self):
        return self.origin + "/mcp"

    def validate(self):
        if self.dev:
            if self.origin not in {"http://127.0.0.1:8780", "http://localhost:8780"}:
                raise ValueError("Development mode is restricted to the loopback preview.")
        elif not all((self.database.startswith("postgresql"), self.supabase_url.startswith("https://"),
                      self.publishable_key, self.secret_key, self.origin.startswith("https://"))):
            raise ValueError("Production requires a dedicated PostgreSQL database, Supabase keys and HTTPS origin.")
        self.data.mkdir(parents=True, exist_ok=True)

    def account_dir(self, owner: str) -> Path:
        # Only validated UUIDs can become server-controlled path components.
        return self.data / "accounts" / str(UUID(owner))

    def home(self, owner: str) -> Path:
        return self.account_dir(owner) / "home"

    def allows_origin(self, origin: str) -> bool:
        if self.dev:
            return origin in {"http://127.0.0.1:8780", "http://localhost:8780"}
        return origin == self.origin

    @property
    def db_url(self):
        return self.database or "sqlite:///" + (self.data / "pilot.sqlite").as_posix()
