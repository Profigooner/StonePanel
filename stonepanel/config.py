import secrets
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "StonePanel"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 9800

    # Auth
    secret_key: str = secrets.token_urlsafe(32)
    access_token_expire_minutes: int = 1440  # 24h

    # Data
    data_dir: Path = Path.home() / ".stonepanel"

    # File manager root
    file_root: str = "/"

    # Dev
    dev_mode: bool = False

    model_config = {"env_prefix": "STONEPANEL_"}
