import shutil
import stat
from pathlib import Path

from .models import FileInfo


class FileManagerService:
    def __init__(self, root_path: str = "/"):
        self.root_path = Path(root_path).resolve()

    def _resolve_path(self, path: str) -> Path:
        """Resolve and confine path within root."""
        clean = path.lstrip("/")
        resolved = (self.root_path / clean).resolve() if clean else self.root_path
        try:
            resolved.relative_to(self.root_path)
        except ValueError:
            raise PermissionError("Access denied: path outside allowed directory")
        return resolved

    def _make_info(self, p: Path) -> FileInfo:
        st = p.stat()
        rel = p.relative_to(self.root_path)
        api_path = "/" + str(rel) if str(rel) != "." else "/"
        return FileInfo(
            name=p.name or "/",
            path=api_path,
            is_dir=p.is_dir(),
            size=st.st_size,
            modified=st.st_mtime,
            permissions=stat.filemode(st.st_mode),
        )

    def list_directory(self, path: str) -> list[FileInfo]:
        resolved = self._resolve_path(path)
        if not resolved.is_dir():
            raise FileNotFoundError(f"Not a directory: {path}")
        items = []
        for entry in sorted(
            resolved.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())
        ):
            try:
                items.append(self._make_info(entry))
            except (PermissionError, OSError):
                continue
        return items

    def read_file(self, path: str) -> str:
        resolved = self._resolve_path(path)
        if not resolved.is_file():
            raise FileNotFoundError(f"Not a file: {path}")
        return resolved.read_text()

    def write_file(self, path: str, content: str):
        resolved = self._resolve_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content)

    def delete(self, path: str):
        resolved = self._resolve_path(path)
        if not resolved.exists():
            raise FileNotFoundError(f"Not found: {path}")
        if resolved == self.root_path:
            raise PermissionError("Cannot delete root directory")
        if resolved.is_dir():
            shutil.rmtree(resolved)
        else:
            resolved.unlink()

    def mkdir(self, path: str):
        resolved = self._resolve_path(path)
        resolved.mkdir(parents=True, exist_ok=True)

    def rename(self, old_path: str, new_path: str):
        old_resolved = self._resolve_path(old_path)
        new_resolved = self._resolve_path(new_path)
        if not old_resolved.exists():
            raise FileNotFoundError(f"Not found: {old_path}")
        new_resolved.parent.mkdir(parents=True, exist_ok=True)
        old_resolved.rename(new_resolved)

    def get_info(self, path: str) -> FileInfo:
        resolved = self._resolve_path(path)
        if not resolved.exists():
            raise FileNotFoundError(f"Not found: {path}")
        return self._make_info(resolved)
