from urllib.parse import urlparse
import httpx
from urllib.robotparser import RobotFileParser

async def robots_allowed(url: str, user_agent: str, timeout: float = 10) -> bool:
    parsed=urlparse(url)
    if not parsed.scheme or not parsed.netloc: return False
    robots=f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser=RobotFileParser()
    try:
        async with httpx.AsyncClient(timeout=timeout,follow_redirects=True,headers={"User-Agent":user_agent}) as client:
            response=await client.get(robots)
        if response.status_code in {401,403}: return False
        if response.status_code>=400: return True
        parser.parse(response.text.splitlines())
        return parser.can_fetch(user_agent,url)
    except httpx.HTTPError:
        return False
