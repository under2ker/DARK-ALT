import httpx
from .base import BaseProvider, ProviderItem
from ..config import settings

class NASAProvider(BaseProvider):
    key="nasa"
    name="NASA Image and Video Library"
    endpoint="https://images-api.nasa.gov/search"

    async def fetch(self,limit:int=20)->list[ProviderItem]:
        params={"q":"space earth nebula","media_type":"image","page_size":min(limit,25)}
        headers={"User-Agent":settings.user_agent}
        async with httpx.AsyncClient(timeout=settings.request_timeout,headers=headers,follow_redirects=True) as client:
            response=await client.get(self.endpoint,params=params);response.raise_for_status()
            rows=response.json().get("collection",{}).get("items",[])
            results=[]
            for row in rows:
                data=(row.get("data") or [{}])[0]; links=row.get("links") or []
                preview=next((x for x in links if x.get("render")=="image"),None)
                if not preview or not data.get("nasa_id"):continue
                original=preview["href"]
                try:
                    manifest=await client.get(row["href"]);manifest.raise_for_status()
                    assets=manifest.json(); original=next((x.replace("http://","https://") for x in assets if "~orig." in x),original)
                except (httpx.HTTPError,ValueError):pass
                results.append(ProviderItem(external_id=data["nasa_id"],title=data.get("title") or data["nasa_id"],
                    description=(data.get("description") or "")[:1000] or None,source_url=f"https://images.nasa.gov/details/{data['nasa_id']}",
                    image_url=original,thumbnail_url=preview["href"],width=preview.get("width") or 1280,height=preview.get("height") or 720,
                    author=data.get("photographer") or data.get("center"),license="NASA Media Usage Guidelines",
                    license_url="https://www.nasa.gov/nasa-brand-center/images-and-media/",tags=["nasa","space"]+(data.get("keywords") or [])[:8]))
            return results
