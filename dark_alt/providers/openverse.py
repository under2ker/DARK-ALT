import os
import httpx
from .base import BaseProvider, ProviderItem
from ..config import settings

class OpenverseProvider(BaseProvider):
    key="openverse"
    name="Openverse"
    endpoint="https://api.openverse.org/v1/images/"

    async def fetch(self,limit:int=20)->list[ProviderItem]:
        token=os.getenv("OPENVERSE_ACCESS_TOKEN")
        if not token: raise RuntimeError("OPENVERSE_ACCESS_TOKEN is not configured")
        headers={"User-Agent":settings.user_agent,"Authorization":f"Bearer {token}"}
        params={"q":"desktop wallpaper landscape","page_size":min(limit,50),"mature":"false"}
        async with httpx.AsyncClient(timeout=settings.request_timeout,headers=headers) as client:
            response=await client.get(self.endpoint,params=params); response.raise_for_status(); data=response.json()
        items=[]
        for row in data.get("results",[]):
            width=row.get("width") or 0; height=row.get("height") or 0
            image_url=row.get("url"); thumbnail=row.get("thumbnail") or image_url
            if not image_url or not width or not height: continue
            items.append(ProviderItem(external_id=str(row["id"]),title=row.get("title") or "Untitled",
                description=None,source_url=row.get("foreign_landing_url") or image_url,image_url=image_url,
                thumbnail_url=thumbnail,width=width,height=height,author=row.get("creator"),license=(row.get("license") or "").upper() or None,
                license_url=row.get("license_url"),tags=[t.get("name") for t in row.get("tags",[])[:10] if t.get("name")]))
        return items
