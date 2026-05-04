import asyncio
import json

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect

from ..deps import require_auth
from .manager import pty_read

router = APIRouter(prefix="/api/terminal", tags=["terminal"])


@router.get("/sessions")
async def list_sessions(request: Request, _=Depends(require_auth)):
    manager = request.app.state.terminal_manager
    return {"sessions": manager.list_sessions()}


@router.post("/sessions")
async def create_session(
    request: Request, rows: int = 24, cols: int = 80, _=Depends(require_auth)
):
    manager = request.app.state.terminal_manager
    session = manager.create_session(rows=rows, cols=cols)
    return {"session_id": session.session_id}


@router.delete("/sessions/{session_id}")
async def kill_session(session_id: str, request: Request, _=Depends(require_auth)):
    manager = request.app.state.terminal_manager
    if manager.kill_session(session_id):
        return {"status": "killed"}
    return {"status": "not_found"}


@router.websocket("/ws/{session_id}")
async def terminal_ws(websocket: WebSocket, session_id: str):
    await websocket.accept()

    # Authenticate via query param
    token = websocket.query_params.get("token")
    auth_service = websocket.app.state.auth_service
    if not token or not auth_service.verify_token(token):
        await websocket.send_json({"error": "Unauthorized"})
        await websocket.close(code=4001)
        return

    # Resolve session
    manager = websocket.app.state.terminal_manager
    session = manager.get_session(session_id)
    if not session:
        await websocket.send_json({"error": "Session not found"})
        await websocket.close(code=4004)
        return

    # PTY -> WebSocket read loop
    async def read_from_pty():
        loop = asyncio.get_event_loop()
        while session.check_alive():
            try:
                data = await loop.run_in_executor(None, pty_read, session.fd)
                if data:
                    await websocket.send_bytes(data)
            except Exception:
                break
        # Shell exited
        try:
            await websocket.close(code=1000, reason="Shell exited")
        except Exception:
            pass

    read_task = asyncio.create_task(read_from_pty())

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break

            if "bytes" in message:
                session.write(message["bytes"])
            elif "text" in message:
                text = message["text"]
                try:
                    msg = json.loads(text)
                    if msg.get("type") == "resize":
                        session.resize(msg.get("rows", 24), msg.get("cols", 80))
                    elif msg.get("type") == "input":
                        session.write(msg["data"].encode())
                    else:
                        session.write(text.encode())
                except (json.JSONDecodeError, KeyError):
                    session.write(text.encode())
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        read_task.cancel()
        try:
            await read_task
        except asyncio.CancelledError:
            pass
