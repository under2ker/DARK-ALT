import hashlib, re
from urllib.parse import urlsplit, urlunsplit

def slugify(value: str) -> str:
    result = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return result[:150] or hashlib.sha1(value.encode()).hexdigest()[:12]

def clean_url(url: str) -> str:
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, p.path, p.query, ""))

def ratio_label(width: int, height: int) -> str:
    ratio = width / max(height, 1)
    choices = {"16:9":16/9,"16:10":1.6,"21:9":21/9,"32:9":32/9,"4:3":4/3,"9:16":9/16}
    return min(choices, key=lambda key: abs(choices[key] - ratio))

def resolution_label(width: int, height: int) -> str:
    longest=max(width,height)
    if longest>=7680:return "8K"
    if longest>=5120:return "5K"
    if longest>=3840:return "4K"
    if longest>=2560:return "2K"
    if longest>=1920:return "FHD"
    return "HD"
