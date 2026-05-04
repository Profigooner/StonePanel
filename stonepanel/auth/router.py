from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_auth_service
from .models import LoginRequest, SetupRequest, StatusResponse, TokenResponse
from .service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/status", response_model=StatusResponse)
async def auth_status(auth: AuthService = Depends(get_auth_service)):
    return StatusResponse(setup_complete=auth.is_setup_complete())


@router.post("/setup", response_model=TokenResponse)
async def setup(req: SetupRequest, auth: AuthService = Depends(get_auth_service)):
    if auth.is_setup_complete():
        raise HTTPException(400, "Already set up")
    if len(req.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    auth.setup_password(req.password)
    return TokenResponse(access_token=auth.create_token())


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, auth: AuthService = Depends(get_auth_service)):
    if not auth.is_setup_complete():
        raise HTTPException(400, "Setup not complete")
    if not auth.verify_password(req.password):
        raise HTTPException(401, "Invalid password")
    return TokenResponse(access_token=auth.create_token())
