from contextlib import asynccontextmanager
from pathlib import Path

import psutil
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .auth.router import router as auth_router
from .auth.service import AuthService
from .config import Settings
from .filemanager.router import router as files_router
from .filemanager.service import FileManagerService
from .proxy.caddy import CaddyClient
from .proxy.health import HealthChecker
from .proxy.router import router as proxy_router
from .proxy.service import ProxyService
from .screen.router import router as screen_router
from .system.router import router as system_router
from .waf.router import internal_router as waf_internal_router
from .waf.router import router as waf_router
from .waf.service import WAFService
from .terminal.manager import TerminalManager
from .terminal.router import router as terminal_router

FRONTEND_DIR = Path(__file__).parent / "frontend"


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.auth_service = AuthService(
            data_dir=settings.data_dir,
            secret_key=settings.secret_key,
            expire_minutes=settings.access_token_expire_minutes,
        )
        app.state.terminal_manager = TerminalManager()
        app.state.file_service = FileManagerService(root_path=settings.file_root)

        # Proxy
        caddy_client = CaddyClient(
            admin_url=settings.caddy_admin_url,
            binary=settings.caddy_binary,
        )
        waf_check_url = (
            f"http://localhost:{settings.port}/internal/waf/check"
            if settings.waf_enabled
            else ""
        )
        app.state.proxy_service = ProxyService(
            data_dir=settings.data_dir,
            caddy=caddy_client,
            waf_check_url=waf_check_url,
        )
        app.state.health_checker = HealthChecker()
        app.state.health_checker.start(app.state.proxy_service.load_rules)

        # WAF
        app.state.waf_service = WAFService(data_dir=settings.data_dir)

        psutil.cpu_percent(interval=None)  # prime CPU measurement
        yield
        app.state.health_checker.stop()
        app.state.terminal_manager.cleanup()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    if settings.dev_mode:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(auth_router)
    app.include_router(terminal_router)
    app.include_router(files_router)
    app.include_router(system_router)
    app.include_router(screen_router)
    app.include_router(proxy_router)
    app.include_router(waf_router)
    app.include_router(waf_internal_router)

    # Serve frontend
    if FRONTEND_DIR.exists():

        @app.get("/")
        async def serve_frontend():
            return FileResponse(FRONTEND_DIR / "index.html")

        app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    return app


app = create_app()
