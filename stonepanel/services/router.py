from fastapi import APIRouter, Depends, HTTPException

from ..deps import require_auth
from .service import SystemdService, _validate_name, ALLOWED_ACTIONS

router = APIRouter(prefix="/api/services", tags=["services"])


@router.get("/available")
async def check_available(_=Depends(require_auth)):
    available = await SystemdService.is_available()
    return {"available": available}


@router.get("/units")
async def list_units(
    type: str = "service",
    state: str | None = None,
    _=Depends(require_auth),
):
    units = await SystemdService.list_services(unit_type=type, state=state)
    return {"units": units}


@router.get("/units/{name}")
async def get_unit(name: str, _=Depends(require_auth)):
    if not _validate_name(name):
        raise HTTPException(400, "Invalid service name")
    status = await SystemdService.get_status(name)
    if not status:
        raise HTTPException(404, "Service not found")
    return status


@router.post("/units/{name}/{action}")
async def unit_action(name: str, action: str, _=Depends(require_auth)):
    if not _validate_name(name):
        raise HTTPException(400, "Invalid service name")
    if action not in ALLOWED_ACTIONS:
        raise HTTPException(400, f"Action must be one of: {', '.join(sorted(ALLOWED_ACTIONS))}")
    ok, msg = await SystemdService.action(name, action)
    if not ok:
        raise HTTPException(500, msg)
    return {"status": msg}


@router.get("/units/{name}/logs")
async def get_logs(
    name: str,
    lines: int = 100,
    since: str | None = None,
    _=Depends(require_auth),
):
    if not _validate_name(name):
        raise HTTPException(400, "Invalid service name")
    logs = await SystemdService.get_logs(name, lines=lines, since=since)
    return {"logs": logs}
