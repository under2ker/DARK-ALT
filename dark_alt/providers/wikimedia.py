import html, re, httpx
from .base import BaseProvider, ProviderItem
from ..config import settings

class WikimediaProvider(BaseProvider):
    key = "wikimedia"
    name = "Wikimedia Commons"
    endpoint = "https://commons.wikimedia.org/w/api.php"

    async def fetch(self, limit: int = 20) -> list[ProviderItem]:
        params={"action":"query","format":"json","generator":"categorymembers",
            "gcmtitle":"Category:Featured pictures on Wikimedia Commons","gcmtype":"file",
            "gcmlimit":min(limit,50),"prop":"imageinfo","iiprop":"url|size|extmetadata","iiurlwidth":1200}
        async with httpx.AsyncClient(timeout=settings.request_timeout,headers={"User-Agent":settings.user_agent}) as client:
            response=await client.get(self.endpoint,params=params); response.raise_for_status()
            pages=response.json().get("query",{}).get("pages",{})
        results=[]
        for page in pages.values():
            info=(page.get("imageinfo") or [{}])[0]; meta=info.get("extmetadata",{}); url=info.get("url")
            if not url or not info.get("width") or not info.get("height"): continue
            title=re.sub(r"^File:","",page.get("title","Untitled"),flags=re.I)
            description=html.unescape(re.sub("<[^>]+>","",meta.get("ImageDescription",{}).get("value","")))[:1000]
            results.append(ProviderItem(external_id=str(page.get("pageid")),title=title,description=description or None,
                source_url=info.get("descriptionurl",url),image_url=url,thumbnail_url=info.get("thumburl",url),
                width=info["width"],height=info["height"],author=re.sub("<[^>]+>","",meta.get("Artist",{}).get("value",""))[:300] or None,
                license=meta.get("LicenseShortName",{}).get("value"),license_url=meta.get("LicenseUrl",{}).get("value"),tags=["wikimedia","featured"]))
        return results
