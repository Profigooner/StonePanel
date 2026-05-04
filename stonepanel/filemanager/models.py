from pydantic import BaseModel


class FileInfo(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int
    modified: float
    permissions: str


class WriteFileRequest(BaseModel):
    path: str
    content: str


class RenameRequest(BaseModel):
    old_path: str
    new_path: str


class MkdirRequest(BaseModel):
    path: str
