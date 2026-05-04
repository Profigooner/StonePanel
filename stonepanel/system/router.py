import platform
import time

import psutil
from fastapi import APIRouter, Depends

from ..deps import require_auth

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/info")
async def system_info(_=Depends(require_auth)):
    mem = psutil.virtual_memory()
    return {
        "hostname": platform.node(),
        "os": f"{platform.system()} {platform.release()}",
        "arch": platform.machine(),
        "python": platform.python_version(),
        "uptime": time.time() - psutil.boot_time(),
        "cpu_count": psutil.cpu_count(),
        "total_memory": mem.total,
    }


@router.get("/stats")
async def system_stats(_=Depends(require_auth)):
    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    net = psutil.net_io_counters()
    return {
        "cpu_percent": cpu,
        "memory": {
            "total": mem.total,
            "used": mem.used,
            "percent": mem.percent,
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "percent": disk.percent,
        },
        "network": {
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
        },
    }


@router.get("/processes")
async def top_processes(
    sort_by: str = "cpu", limit: int = 15, _=Depends(require_auth)
):
    procs = []
    for p in psutil.process_iter(
        ["pid", "name", "cpu_percent", "memory_percent", "username", "status"]
    ):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    key = "cpu_percent" if sort_by == "cpu" else "memory_percent"
    procs.sort(key=lambda x: x.get(key) or 0, reverse=True)
    return {"processes": procs[:limit]}
