"""รหัสผ่านและ JWT"""
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from envelope import ApiError

_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def _expires_in() -> timedelta:
    """อ่าน JWT_EXPIRES_IN แบบ 7d, 12h, 30m, 90s หรือตัวเลขเปล่าเป็นวินาที"""
    raw = os.getenv("JWT_EXPIRES_IN", "7d").strip()
    if raw[-1] in _UNITS:
        return timedelta(seconds=int(raw[:-1]) * _UNITS[raw[-1]])
    return timedelta(seconds=int(raw))


def _secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise ApiError("INTERNAL_ERROR", "ยังไม่ได้ตั้งค่า JWT_SECRET ใน .env")
    return secret


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def make_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": user_id, "iat": now, "exp": now + _expires_in()}, _secret(), algorithm="HS256")


def read_token(token: str) -> str:
    """คืน user_id ถ้า token ถูกต้องและยังไม่หมดอายุ"""
    try:
        payload = jwt.decode(token, _secret(), algorithms=["HS256"], options={"require": ["exp", "sub"]})
    except jwt.ExpiredSignatureError:
        raise ApiError("UNAUTHORIZED", "เซสชันหมดอายุ กรุณาเข้าสู่ระบบใหม่")
    except jwt.InvalidTokenError:
        raise ApiError("UNAUTHORIZED", "กรุณาเข้าสู่ระบบก่อน")
    return payload["sub"]