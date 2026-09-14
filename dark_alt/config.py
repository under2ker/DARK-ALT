from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

class Settings:
    app_name = "DARK//ALT API"
    database_url = os.getenv("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'dark_alt.db').as_posix()}")
    providers_file = Path(os.getenv("PROVIDERS_FILE", ROOT / "providers.yaml"))
    user_agent = os.getenv("CRAWLER_USER_AGENT", "DARKALTBot/0.2 (https://example.org/darkalt; contact@example.org)")
    request_timeout = float(os.getenv("REQUEST_TIMEOUT", "15"))
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    jwt_secret = os.getenv("JWT_SECRET", "dark-alt-development-secret-change-in-production")
    jwt_algorithm = "HS256"
    access_token_hours = int(os.getenv("ACCESS_TOKEN_HOURS", "168"))
    admin_api_key = os.getenv("ADMIN_API_KEY", "dark-alt-local-admin")
    log_level = os.getenv("LOG_LEVEL", "INFO")
    environment = os.getenv("ENVIRONMENT", "development")
    backup_dir = Path(os.getenv("BACKUP_DIR", ROOT / "backups"))

settings = Settings()
