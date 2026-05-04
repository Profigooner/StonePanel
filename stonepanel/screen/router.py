from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import require_auth
from .service import ScreenService

router = APIRouter(prefix="/api/screen", tags=["screen"])


class CreateSessionRequest(BaseModel):
    type: str  # "screen" or "tmux"
    name: str
    command: str = ""


@router.get("/sessions")
async def list_sessions(_=Depends(require_auth)):
    sessions = await ScreenService.list_all()
    return {"sessions": sessions}


@router.get("/available")
async def check_available(_=Depends(require_auth)):
    return await ScreenService.check_available()


@router.post("/sessions")
async def create_session(req: CreateSessionRequest, _=Depends(require_auth)):
    if req.type not in ("screen", "tmux"):
        raise HTTPException(400, "type must be 'screen' or 'tmux'")
    if not req.name or not req.name.strip():
        raise HTTPException(400, "name is required")

    if req.type == "screen":
        ok = await ScreenService.create_screen(req.name.strip(), req.command)
    else:
        ok = await ScreenService.create_tmux(req.name.strip(), req.command)

    if not ok:
        raise HTTPException(500, f"Failed to create {req.type} session")
    return {"status": "created", "name": req.name.strip()}


@router.delete("/sessions/{session_type}/{session_id:path}")
async def kill_session(
    session_type: str, session_id: str, _=Depends(require_auth)
):
    if session_type == "screen":
        ok = await ScreenService.kill_screen(session_id)
    elif session_type == "tmux":
        ok = await ScreenService.kill_tmux(session_id)
    else:
        raise HTTPException(400, "type must be 'screen' or 'tmux'")

    if not ok:
        raise HTTPException(500, "Failed to kill session")
    return {"status": "killed"}
