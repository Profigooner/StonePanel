from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from ..deps import require_auth
from .models import MkdirRequest, RenameRequest, WriteFileRequest

router = APIRouter(prefix="/api/files", tags=["files"])


def _get_service(request: Request):
    return request.app.state.file_service


@router.get("/list")
async def list_directory(
    request: Request, path: str = "/", _=Depends(require_auth)
):
    svc = _get_service(request)
    try:
        items = svc.list_directory(path)
        return {"path": path, "items": [item.model_dump() for item in items]}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))


@router.get("/read")
async def read_file(path: str, request: Request, _=Depends(require_auth)):
    svc = _get_service(request)
    try:
        content = svc.read_file(path)
        return {"path": path, "content": content}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))


@router.get("/download")
async def download_file(path: str, request: Request, _=Depends(require_auth)):
    svc = _get_service(request)
    try:
        resolved = svc._resolve_path(path)
        if not resolved.is_file():
            raise HTTPException(404, "Not a file")
        return FileResponse(str(resolved), filename=resolved.name)
    except PermissionError as e:
        raise HTTPException(403, str(e))


@router.put("/write")
async def write_file(req: WriteFileRequest, request: Request, _=Depends(require_auth)):
    svc = _get_service(request)
    try:
        svc.write_file(req.path, req.content)
        return {"status": "ok"}
    except PermissionError as e:
        raise HTTPException(403, str(e))


@router.post("/upload")
async def upload_file(
    path: str,
    request: Request,
    file: UploadFile = File(...),
    _=Depends(require_auth),
):
    svc = _get_service(request)
    try:
        content = await file.read()
        resolved = svc._resolve_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_bytes(content)
        return {"status": "ok", "path": path}
    except PermissionError as e:
        raise HTTPException(403, str(e))


@router.post("/mkdir")
async def mkdir(req: MkdirRequest, request: Request, _=Depends(require_auth)):
    svc = _get_service(request)
    try:
        svc.mkdir(req.path)
        return {"status": "ok"}
    except PermissionError as e:
        raise HTTPException(403, str(e))


@router.post("/rename")
async def rename(req: RenameRequest, request: Request, _=Depends(require_auth)):
    svc = _get_service(request)
    try:
        svc.rename(req.old_path, req.new_path)
        return {"status": "ok"}
    except (FileNotFoundError, PermissionError) as e:
        raise HTTPException(400, str(e))


@router.delete("/delete")
async def delete(path: str, request: Request, _=Depends(require_auth)):
    svc = _get_service(request)
    try:
        svc.delete(path)
        return {"status": "ok"}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))


@router.get("/info")
async def file_info(path: str, request: Request, _=Depends(require_auth)):
    svc = _get_service(request)
    try:
        info = svc.get_info(path)
        return info.model_dump()
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))
