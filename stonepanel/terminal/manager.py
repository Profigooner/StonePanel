import fcntl
import os
import pty
import select
import signal
import struct
import termios
import uuid
from typing import Optional


class TerminalSession:
    def __init__(self, session_id: str, shell: str | None = None):
        self.session_id = session_id
        self.shell = shell or os.environ.get("SHELL", "/bin/bash")
        self.pid: int | None = None
        self.fd: int | None = None
        self.alive = False

    def start(self, rows: int = 24, cols: int = 80):
        pid, fd = pty.fork()
        if pid == 0:
            # Child: exec shell
            os.execvp(self.shell, [self.shell])
        else:
            # Parent
            self.pid = pid
            self.fd = fd
            self.alive = True
            self.resize(rows, cols)
            # Non-blocking reads
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    def resize(self, rows: int, cols: int):
        if self.fd is not None:
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, winsize)

    def write(self, data: bytes):
        if self.fd is not None and self.alive:
            os.write(self.fd, data)

    def read(self, max_bytes: int = 65536) -> bytes | None:
        if self.fd is None or not self.alive:
            return None
        try:
            return os.read(self.fd, max_bytes)
        except (OSError, IOError):
            return None

    def stop(self):
        if self.pid and self.alive:
            try:
                os.kill(self.pid, signal.SIGTERM)
                os.waitpid(self.pid, os.WNOHANG)
            except (ProcessLookupError, ChildProcessError):
                pass
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
        self.alive = False

    def check_alive(self) -> bool:
        if self.pid is None:
            self.alive = False
            return False
        try:
            pid, _ = os.waitpid(self.pid, os.WNOHANG)
            if pid != 0:
                self.alive = False
        except ChildProcessError:
            self.alive = False
        return self.alive


def pty_read(fd: int, timeout: float = 0.1) -> bytes | None:
    """Blocking read from PTY fd with select timeout."""
    try:
        r, _, _ = select.select([fd], [], [], timeout)
        if r:
            return os.read(fd, 65536)
    except (OSError, ValueError):
        return None
    return None


class TerminalManager:
    def __init__(self):
        self.sessions: dict[str, TerminalSession] = {}

    def create_session(self, rows: int = 24, cols: int = 80) -> TerminalSession:
        session_id = str(uuid.uuid4())
        session = TerminalSession(session_id)
        session.start(rows, cols)
        self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[TerminalSession]:
        session = self.sessions.get(session_id)
        if session and session.check_alive():
            return session
        if session and not session.alive:
            session.stop()
            del self.sessions[session_id]
        return None

    def kill_session(self, session_id: str) -> bool:
        session = self.sessions.pop(session_id, None)
        if session:
            session.stop()
            return True
        return False

    def list_sessions(self) -> list[dict]:
        dead = [sid for sid, s in self.sessions.items() if not s.check_alive()]
        for sid in dead:
            self.sessions[sid].stop()
            del self.sessions[sid]
        return [
            {"session_id": s.session_id, "alive": s.alive}
            for s in self.sessions.values()
        ]

    def cleanup(self):
        for session in self.sessions.values():
            session.stop()
        self.sessions.clear()
