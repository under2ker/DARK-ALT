from collections import defaultdict, deque
from time import monotonic
import logging
from uuid import uuid4
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response=await call_next(request)
        response.headers.setdefault("X-Content-Type-Options","nosniff")
        response.headers.setdefault("X-Frame-Options","DENY")
        response.headers.setdefault("Referrer-Policy","strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy","camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("X-Request-ID",request.state.request_id)
        return response

class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.request_id=str(uuid4())
        started=monotonic(); response=await call_next(request)
        logging.getLogger("dark_alt.request").info("request_complete",extra={"request_id":request.state.request_id,"method":request.method,"path":request.url.path,"status_code":response.status_code,"duration_ms":round((monotonic()-started)*1000,2)})
        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute=120):
        super().__init__(app); self.limit=requests_per_minute; self.buckets=defaultdict(deque)
    async def dispatch(self, request, call_next):
        if request.url.path.startswith("/api") or request.url.path.startswith("/admin"):
            key=request.client.host if request.client else "unknown"; now=monotonic(); bucket=self.buckets[key]
            while bucket and now-bucket[0]>60: bucket.popleft()
            if len(bucket)>=self.limit:
                return JSONResponse({"detail":"Rate limit exceeded","request_id":getattr(request.state,"request_id",str(uuid4()))},status_code=429,headers={"Retry-After":"60"})
            bucket.append(now)
        return await call_next(request)
