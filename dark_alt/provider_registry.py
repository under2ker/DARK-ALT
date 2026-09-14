import yaml
from pathlib import Path
from .config import settings
from .providers import PROVIDER_CLASSES

def load_provider_config() -> dict:
    if not settings.providers_file.exists(): return {}
    return yaml.safe_load(settings.providers_file.read_text(encoding="utf-8")) or {}

def enabled_providers():
    return [(PROVIDER_CLASSES[key](),values) for key,values in load_provider_config().items()
            if values.get("enabled") and key in PROVIDER_CLASSES]

def set_provider_enabled(key: str, enabled: bool) -> dict:
    config=load_provider_config()
    if key not in config: raise KeyError(key)
    config[key]["enabled"]=enabled
    temporary=settings.providers_file.with_suffix(".yaml.tmp")
    temporary.write_text(yaml.safe_dump(config,sort_keys=False,allow_unicode=True),encoding="utf-8")
    temporary.replace(settings.providers_file)
    return config[key]
