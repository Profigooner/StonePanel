from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer(auto_error=False)


def get_auth_service(request: Request):
    return request.app.state.auth_service


def get_settings(request: Request):
    return request.app.state.settings


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    auth_service = request.app.state.auth_service
    if not auth_service.verify_token(credentials.credentials):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return credentials.credentials
