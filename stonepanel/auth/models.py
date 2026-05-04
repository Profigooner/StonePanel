from pydantic import BaseModel


class SetupRequest(BaseModel):
    password: str


class LoginRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class StatusResponse(BaseModel):
    setup_complete: bool
