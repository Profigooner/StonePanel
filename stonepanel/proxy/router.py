from fastapi import APIRouter, Depends, HTTPException, Request

from ..deps import require_auth
from .models import ProxyRuleCreate, ProxyRuleUpdate
from .service import ProxyService

router = APIRouter(prefix="/api/proxy", tags=["proxy"])


def get_proxy_service(request: Request) -> ProxyService:
    return request.app.state.proxy_service


# --- Rule CRUD ---


@router.get("/rules")
async def list_rules(
    service: ProxyService = Depends(get_proxy_service),
    _=Depends(require_auth),
):
    return {"rules": [r.model_dump() for r in service.load_rules()]}


@router.post("/rules", status_code=201)
async def create_rule(
    data: ProxyRuleCreate,
    service: ProxyService = Depends(get_proxy_service),
    _=Depends(require_auth),
):
    rule = service.create_rule(data)
    return rule.model_dump()


@router.get("/rules/{rule_id}")
async def get_rule(
    rule_id: str,
    service: ProxyService = Depends(get_proxy_service),
    _=Depends(require_auth),
):
    rule = service.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule.model_dump()


@router.put("/rules/{rule_id}")
async def update_rule(
    rule_id: str,
    data: ProxyRuleUpdate,
    service: ProxyService = Depends(get_proxy_service),
    _=Depends(require_auth),
):
    rule = service.update_rule(rule_id, data)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule.model_dump()


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    service: ProxyService = Depends(get_proxy_service),
    _=Depends(require_auth),
):
    if not service.delete_rule(rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"ok": True}


@router.post("/rules/{rule_id}/enable")
async def enable_rule(
    rule_id: str,
    service: ProxyService = Depends(get_proxy_service),
    _=Depends(require_auth),
):
    rule = service.enable_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule.model_dump()


@router.post("/rules/{rule_id}/disable")
async def disable_rule(
    rule_id: str,
    service: ProxyService = Depends(get_proxy_service),
    _=Depends(require_auth),
):
    rule = service.disable_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule.model_dump()


# --- Caddy management ---


@router.get("/caddy/status")
async def caddy_status(
    service: ProxyService = Depends(get_proxy_service),
    _=Depends(require_auth),
):
    status = await service.get_caddy_status()
    return status.model_dump()


@router.post("/apply")
async def apply_config(
    service: ProxyService = Depends(get_proxy_service),
    _=Depends(require_auth),
):
    running = await service.caddy.is_running()
    if not running:
        raise HTTPException(status_code=503, detail="Caddy is not running")
    success = await service.apply_config()
    if not success:
        raise HTTPException(status_code=500, detail="Failed to apply config to Caddy")
    return {"ok": True}


@router.post("/caddy/start")
async def start_caddy(
    service: ProxyService = Depends(get_proxy_service),
    _=Depends(require_auth),
):
    if await service.caddy.is_running():
        return {"ok": True, "message": "Caddy is already running"}
    success = await service.caddy.start()
    if not success:
        raise HTTPException(status_code=500, detail="Failed to start Caddy")
    return {"ok": True}


@router.post("/caddy/stop")
async def stop_caddy(
    service: ProxyService = Depends(get_proxy_service),
    _=Depends(require_auth),
):
    success = await service.caddy.stop()
    if not success:
        raise HTTPException(status_code=500, detail="Failed to stop Caddy")
    return {"ok": True}


# --- Status & stats ---


@router.get("/status")
async def proxy_status(
    service: ProxyService = Depends(get_proxy_service),
    _=Depends(require_auth),
):
    caddy = await service.get_caddy_status()
    rules = service.load_rules()
    return {
        "caddy": caddy.model_dump(),
        "rules_total": len(rules),
        "rules_enabled": sum(1 for r in rules if r.enabled),
    }
