from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import os
import re

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User

security = HTTPBearer(auto_error=False)
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{3,40}$")

def hash_password(password: str) -> str:
    salt=os.urandom(16)
    key=hashlib.scrypt(password.encode(),salt=salt,n=2**14,r=8,p=1,dklen=64)
    return "scrypt$16384$"+base64.b64encode(salt).decode()+"$"+base64.b64encode(key).decode()

def verify_password(password: str, encoded: str) -> bool:
    try:
        method,cost,salt64,key64=encoded.split("$",3)
        if method!="scrypt": return False
        actual=hashlib.scrypt(password.encode(),salt=base64.b64decode(salt64),n=int(cost),r=8,p=1,dklen=64)
        return hmac.compare_digest(actual,base64.b64decode(key64))
    except (ValueError,TypeError): return False

def create_token(user: User) -> str:
    now=datetime.now(timezone.utc)
    payload={"sub":str(user.id),"username":user.username,"iat":now,"exp":now+timedelta(hours=settings.access_token_hours)}
    return jwt.encode(payload,settings.jwt_secret,algorithm=settings.jwt_algorithm)

def current_user(credentials:HTTPAuthorizationCredentials|None=Depends(security),db:Session=Depends(get_db)) -> User:
    if not credentials: raise HTTPException(401,"Authentication required",headers={"WWW-Authenticate":"Bearer"})
    try:
        payload=jwt.decode(credentials.credentials,settings.jwt_secret,algorithms=[settings.jwt_algorithm])
        user_id=int(payload["sub"])
    except (jwt.PyJWTError,KeyError,ValueError): raise HTTPException(401,"Invalid or expired token")
    user=db.scalar(select(User).where(User.id==user_id,User.is_active.is_(True)))
    if not user: raise HTTPException(401,"User not found or disabled")
    return user

def optional_user(credentials:HTTPAuthorizationCredentials|None=Depends(security),db:Session=Depends(get_db)) -> User|None:
    if not credentials: return None
    return current_user(credentials,db)
