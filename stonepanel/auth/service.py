import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
from jose import JWTError, jwt


class AuthService:
    def __init__(self, data_dir: Path, secret_key: str, expire_minutes: int):
        self.data_dir = data_dir
        self.secret_key = secret_key
        self.expire_minutes = expire_minutes
        self.auth_file = data_dir / "auth.json"
        data_dir.mkdir(parents=True, exist_ok=True)

    def is_setup_complete(self) -> bool:
        return self.auth_file.exists()

    def setup_password(self, password: str) -> bool:
        if self.is_setup_complete():
            return False
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        self.auth_file.write_text(json.dumps({"password_hash": hashed}))
        return True

    def verify_password(self, password: str) -> bool:
        if not self.is_setup_complete():
            return False
        data = json.loads(self.auth_file.read_text())
        return bcrypt.checkpw(password.encode(), data["password_hash"].encode())

    def create_token(self) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=self.expire_minutes)
        return jwt.encode(
            {"exp": expire, "sub": "admin"}, self.secret_key, algorithm="HS256"
        )

    def verify_token(self, token: str) -> bool:
        try:
            jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return True
        except JWTError:
            return False
