import hmac
from fastapi import Header, HTTPException
from .config import settings

def require_admin_key(x_admin_key: str|None=Header(default=None)):
    if not x_admin_key or not hmac.compare_digest(x_admin_key,settings.admin_api_key):
        raise HTTPException(401,"Valid X-Admin-Key header required")
    return True
