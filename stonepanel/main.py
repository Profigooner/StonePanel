from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth.router import router as auth_router
from .auth.service import AuthService
from .config import Settings
from .filemanager.router import router as files_router
from .filemanager.service import FileManagerService
from .terminal.manager import TerminalManager
from .terminal.router import router as terminal_router


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
        yield
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

    return app


app = create_app()
