from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import require_auth
from .service import CronService

router = APIRouter(prefix="/api/cron", tags=["cron"])


class CronJobCreate(BaseModel):
    minute: str = "*"
    hour: str = "*"
    day: str = "*"
    month: str = "*"
    weekday: str = "*"
    command: str
    description: str = ""


class CronJobUpdate(BaseModel):
    minute: str | None = None
    hour: str | None = None
    day: str | None = None
    month: str | None = None
    weekday: str | None = None
    command: str | None = None
    description: str | None = None


class CronToggle(BaseModel):
    enabled: bool


class CronValidate(BaseModel):
    expression: str


@router.get("/jobs")
async def list_jobs(user: str | None = None, _=Depends(require_auth)):
    jobs = await CronService.list_jobs(user)
    return {"jobs": jobs}


@router.post("/jobs")
async def create_job(req: CronJobCreate, _=Depends(require_auth)):
    schedule = f"{req.minute} {req.hour} {req.day} {req.month} {req.weekday}"
    valid, msg = CronService.validate_schedule(schedule)
    if not valid:
        raise HTTPException(400, msg)
    if not req.command.strip():
        raise HTTPException(400, "command is required")

    job = await CronService.create_job(
        req.minute, req.hour, req.day, req.month, req.weekday,
        req.command.strip(), req.description.strip(),
    )
    if not job:
        raise HTTPException(500, "Failed to create cron job")
    return job


@router.put("/jobs/{job_id}")
async def update_job(job_id: str, req: CronJobUpdate, _=Depends(require_auth)):
    # Validate schedule if any schedule field is provided
    if any(f is not None for f in [req.minute, req.hour, req.day, req.month, req.weekday]):
        # Need current job to fill in missing fields
        jobs = await CronService.list_jobs()
        current = None
        for j in jobs:
            if j["id"] == job_id:
                current = j
                break
        if not current:
            raise HTTPException(404, "Job not found")

        parts = current["schedule"].split()
        test_schedule = "{} {} {} {} {}".format(
            req.minute if req.minute is not None else parts[0],
            req.hour if req.hour is not None else parts[1],
            req.day if req.day is not None else parts[2],
            req.month if req.month is not None else parts[3],
            req.weekday if req.weekday is not None else parts[4],
        )
        valid, msg = CronService.validate_schedule(test_schedule)
        if not valid:
            raise HTTPException(400, msg)

    job = await CronService.update_job(
        job_id,
        minute=req.minute, hour=req.hour, day=req.day,
        month=req.month, weekday=req.weekday,
        command=req.command, description=req.description,
    )
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, _=Depends(require_auth)):
    ok = await CronService.delete_job(job_id)
    if not ok:
        raise HTTPException(404, "Job not found")
    return {"status": "deleted"}


@router.post("/jobs/{job_id}/toggle")
async def toggle_job(job_id: str, req: CronToggle, _=Depends(require_auth)):
    ok = await CronService.toggle_job(job_id, req.enabled)
    if not ok:
        raise HTTPException(404, "Job not found")
    return {"status": "enabled" if req.enabled else "disabled"}


@router.post("/validate")
async def validate_schedule(req: CronValidate, _=Depends(require_auth)):
    valid, msg = CronService.validate_schedule(req.expression)
    return {"valid": valid, "message": msg}
