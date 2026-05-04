from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from ..deps import require_auth
from .models import (
    GeoBlockCreate,
    IPListEntry,
    RateLimitCreate,
    RateLimitUpdate,
    RequestData,
    WAFConfig,
    WAFRuleCreate,
    WAFRuleUpdate,
)
from .service import WAFService

router = APIRouter(prefix="/api/waf", tags=["waf"])
internal_router = APIRouter(tags=["waf-internal"])


def get_waf_service(request: Request) -> WAFService:
    return request.app.state.waf_service


# --- Config ---


@router.get("/config")
async def get_config(
    service: WAFService = Depends(get_waf_service),
    _=Depends(require_auth),
):
    return service.load_config().model_dump()


@router.put("/config")
async def update_config(
    data: WAFConfig,
    service: WAFService = Depends(get_waf_service),
    _=Depends(require_auth),
):
    return service.save_config(data).model_dump()


# --- Custom rules ---


@router.get("/rules")
async def list_rules(
    service: WAFService = Depends(get_waf_service),
    _=Depends(require_auth),
):
    return {"rules": [r.model_dump() for r in service.load_rules()]}


@router.post("/rules", status_code=201)
async def create_rule(
    data: WAFRuleCreate,
    service: WAFService = Depends(get_waf_service),
    _=Depends(require_auth),
):
    return service.create_rule(data).model_dump()


@router.put("/rules/{rule_id}")
async def update_rule(
    rule_id: str,
    data: WAFRuleUpdate,
    service: WAFService = Depends(get_waf_service),
    _=Depends(require_auth),
):
    rule = service.update_rule(rule_id, data)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule.model_dump()


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    service: WAFService = Depends(get_waf_service),
    _=Depends(require_auth),
):
    if not service.delete_rule(rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"ok": True}


@router.post("/rules/test")
async def test_rule(
    data: RequestData,
    service: WAFService = Depends(get_waf_service),
    _=Depends(require_auth),
):
    decision = service.engine.evaluate(data)
    return decision.model_dump()


# --- OWASP rules ---


@router.get("/owasp/rules")
async def list_owasp_rules(
    service: WAFService = Depends(get_waf_service),
    _=Depends(require_auth),
):
    return {"rules": [r.model_dump() for r in service.get_owasp_rules()]}


@router.put("/owasp/rules/{rule_id}")
async def toggle_owasp_rule(
    rule_id: str,
    enabled: bool,
    service: WAFService = Depends(get_waf_service),
    _=Depends(require_auth),
):
    rule = service.update_owasp_rule(rule_id, enabled)
    if not rule:
        raise HTTPException(status_code=404, detail="OWASP rule not found")
    return rule.model_dump()


# --- IP lists ---


@router.get("/ip-lists")
async def get_ip_lists(
    service: WAFService = Depends(get_waf_service),
    _=Depends(require_auth),
):
    return service.load_ip_lists().model_dump()


@router.post("/ip-lists/whitelist")
async def add_to_whitelist(
    entry: IPListEntry,
    service: WAFService = Depends(get_waf_service),
    _=Depends(require_auth),
):
    return service.add_to_whitelist(entry).model_dump()


@router.post("/ip-lists/blacklist")
async def add_to_blacklist(
    entry: IPListEntry,
    service: WAFService = Depends(get_waf_service),
    _=Depends(require_auth),
):
    return service.add_to_blacklist(entry).model_dump()


@router.delete("/ip-lists/{list_type}/{address:path}")
async def remove_from_list(
    list_type: str,
    address: str,
    service: WAFService = Depends(get_waf_service),
    _=Depends(require_auth),
):
    if list_type not in ("whitelist", "blacklist"):
        raise HTTPException(status_code=400, detail="list_type must be 'whitelist' or 'blacklist'")
    if not service.remove_from_list(list_type, address):
        raise HTTPException(status_code=404, detail="IP not found in list")
    return {"ok": True}


# --- Rate limits ---


@router.get("/rate-limits")
async def list_rate_limits(
    service: WAFService = Depends(get_waf_service),
    _=Depends(require_auth),
):
    return {"rules": [r.model_dump() for r in service.load_rate_limits()]}


@router.post("/rate-limits", status_code=201)
async def create_rate_limit(
    data: RateLimitCreate,
    service: WAFService = Depends(get_waf_service),
    _=Depends(require_auth),
):
    return service.create_rate_limit(data).model_dump()


@router.put("/rate-limits/{rule_id}")
async def update_rate_limit(
    rule_id: str,
    data: RateLimitUpdate,
    service: WAFService = Depends(get_waf_service),
    _=Depends(require_auth),
):
    rule = service.update_rate_limit(rule_id, data)
    if not rule:
        raise HTTPException(status_code=404, detail="Rate limit rule not found")
    return rule.model_dump()


@router.delete("/rate-limits/{rule_id}")
async def delete_rate_limit(
    rule_id: str,
    service: WAFService = Depends(get_waf_service),
    _=Depends(require_auth),
):
    if not service.delete_rate_limit(rule_id):
        raise HTTPException(status_code=404, detail="Rate limit rule not found")
    return {"ok": True}


# --- Geo rules ---


@router.get("/geo-rules")
async def list_geo_rules(
    service: WAFService = Depends(get_waf_service),
    _=Depends(require_auth),
):
    return {"rules": [r.model_dump() for r in service.load_geo_rules()]}


@router.post("/geo-rules", status_code=201)
async def create_geo_rule(
    data: GeoBlockCreate,
    service: WAFService = Depends(get_waf_service),
    _=Depends(require_auth),
):
    return service.create_geo_rule(data).model_dump()


@router.delete("/geo-rules/{rule_id}")
async def delete_geo_rule(
    rule_id: str,
    service: WAFService = Depends(get_waf_service),
    _=Depends(require_auth),
):
    if not service.delete_geo_rule(rule_id):
        raise HTTPException(status_code=404, detail="Geo rule not found")
    return {"ok": True}


# --- Logs ---


@router.get("/logs")
async def query_logs(
    start_time: float = None,
    end_time: float = None,
    source_ip: str = None,
    category: str = None,
    action: str = None,
    limit: int = 100,
    offset: int = 0,
    service: WAFService = Depends(get_waf_service),
    _=Depends(require_auth),
):
    entries = service.query_logs(
        start_time=start_time,
        end_time=end_time,
        source_ip=source_ip,
        category=category,
        action=action,
        limit=limit,
        offset=offset,
    )
    return {"logs": entries, "count": len(entries)}


@router.get("/logs/stats")
async def log_stats(
    hours: int = 24,
    service: WAFService = Depends(get_waf_service),
    _=Depends(require_auth),
):
    return service.get_log_stats(hours=hours)


# --- Dashboard ---


@router.get("/dashboard")
async def dashboard(
    service: WAFService = Depends(get_waf_service),
    _=Depends(require_auth),
):
    config = service.load_config()
    stats = service.get_log_stats(hours=24)
    rules = service.load_rules()
    owasp_rules = service.get_owasp_rules()
    ip_lists = service.load_ip_lists()

    return {
        "config": config.model_dump(),
        "stats": stats,
        "custom_rules_count": len(rules),
        "owasp_rules_enabled": sum(1 for r in owasp_rules if r.enabled),
        "owasp_rules_total": len(owasp_rules),
        "whitelist_count": len(ip_lists.whitelist),
        "blacklist_count": len(ip_lists.blacklist),
    }


# --- Internal WAF check endpoint (for Caddy forward_auth) ---


@internal_router.post("/internal/waf/check")
async def waf_check(request: Request):
    """Called by Caddy's forward_auth directive to check if a request should be allowed."""
    waf_service: WAFService = request.app.state.waf_service

    # Extract request data from headers (set by Caddy)
    source_ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or request.client.host
        if request.client
        else "0.0.0.0"
    )
    method = request.headers.get("x-forwarded-method", request.method)
    uri = request.headers.get("x-forwarded-uri", str(request.url))
    host = request.headers.get("x-forwarded-host", "")

    # Parse URL components
    url = f"{host}{uri}" if host else uri
    path = uri.split("?")[0] if "?" in uri else uri
    query = uri.split("?")[1] if "?" in uri else ""

    req_data = RequestData(
        source_ip=source_ip,
        method=method,
        url=url,
        path=path,
        query_string=query,
        headers=dict(request.headers),
        user_agent=request.headers.get("user-agent", ""),
        cookies=request.headers.get("cookie", ""),
    )

    decision = waf_service.check_request(req_data)

    if decision.allowed:
        return JSONResponse(status_code=200, content={"status": "allowed"})

    return JSONResponse(
        status_code=403,
        content={
            "status": "blocked",
            "reason": decision.details,
            "rule": decision.rule_name,
        },
    )
