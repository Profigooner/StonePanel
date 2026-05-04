import secrets
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "StonePanel"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 6767

    # Auth
    secret_key: str = secrets.token_urlsafe(32)
    access_token_expire_minutes: int = 1440  # 24h

    # Data
    data_dir: Path = Path.home() / ".stonepanel"

    # File manager root
    file_root: str = "/"

    # Proxy / Caddy
    caddy_admin_url: str = "http://localhost:2019"
    caddy_binary: str = "caddy"

    # WAF
    waf_enabled: bool = False

    # Dev
    dev_mode: bool = False

    model_config = {"env_prefix": "STONEPANEL_"}
