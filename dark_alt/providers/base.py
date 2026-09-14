from dataclasses import dataclass, field

@dataclass
class ProviderItem:
    external_id: str
    title: str
    source_url: str
    image_url: str
    thumbnail_url: str
    width: int
    height: int
    author: str | None = None
    license: str | None = None
    license_url: str | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)

class BaseProvider:
    key = "base"
    name = "Base provider"
    async def fetch(self, limit: int = 20) -> list[ProviderItem]: raise NotImplementedError
