from io import BytesIO
from PIL import Image, ImageFilter, ImageOps
import httpx

from .config import settings

MAX_SOURCE_BYTES = 40 * 1024 * 1024
MAX_OUTPUT_PIXELS = 33_177_600  # 8K UHD
PRESETS = {"4K":(3840,2160),"2K":(2560,1440),"FHD":(1920,1080)}
FORMATS = {"JPEG":("JPEG","image/jpeg","jpg"),"PNG":("PNG","image/png","png"),"WEBP":("WEBP","image/webp","webp")}

async def fetch_source(url: str) -> bytes:
    chunks=[]; size=0
    async with httpx.AsyncClient(timeout=30,headers={"User-Agent":settings.user_agent},follow_redirects=True) as client:
        async with client.stream("GET",url) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                size+=len(chunk)
                if size>MAX_SOURCE_BYTES: raise ValueError("Source image exceeds 40 MB limit")
                chunks.append(chunk)
    return b"".join(chunks)

def resolve_size(source_size: tuple[int,int], preset: str, width: int|None, height: int|None, allow_upscale: bool):
    if preset=="CUSTOM":
        if not width or not height: raise ValueError("Custom preset requires width and height")
        target=(width,height)
    else: target=PRESETS[preset]
    if target[0]*target[1]>MAX_OUTPUT_PIXELS: raise ValueError("Requested output exceeds 8K pixel limit")
    if not allow_upscale:
        scale=min(1,source_size[0]/target[0],source_size[1]/target[1])
        target=(max(1,int(target[0]*scale)),max(1,int(target[1]*scale)))
    return target

def inspect_source_size(raw: bytes) -> tuple[int,int]:
    with Image.open(BytesIO(raw)) as image:
        return ImageOps.exif_transpose(image).size

def render_variant(raw: bytes, target: tuple[int,int], mode: str, output_format: str, quality: int) -> tuple[bytes,str,str]:
    with Image.open(BytesIO(raw)) as source:
        source.load(); image=ImageOps.exif_transpose(source).convert("RGB")
        if mode in {"fill","crop"}: result=ImageOps.fit(image,target,method=Image.Resampling.LANCZOS)
        elif mode=="stretch": result=image.resize(target,Image.Resampling.LANCZOS)
        elif mode=="center":
            foreground=ImageOps.contain(image,target,method=Image.Resampling.LANCZOS)
            result=Image.new("RGB",target,(0,0,0)); result.paste(foreground,((target[0]-foreground.width)//2,(target[1]-foreground.height)//2))
        elif mode=="blur_background":
            background=ImageOps.fit(image,target,method=Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(radius=max(target)/75))
            foreground=ImageOps.contain(image,target,method=Image.Resampling.LANCZOS)
            background.paste(foreground,((target[0]-foreground.width)//2,(target[1]-foreground.height)//2)); result=background
        else:
            foreground=ImageOps.contain(image,target,method=Image.Resampling.LANCZOS)
            result=Image.new("RGB",target,(0,0,0)); result.paste(foreground,((target[0]-foreground.width)//2,(target[1]-foreground.height)//2))
        fmt,mime,extension=FORMATS[output_format]
        output=BytesIO(); kwargs={"optimize":True}
        if fmt in {"JPEG","WEBP"}: kwargs["quality"]=quality
        result.save(output,fmt,**kwargs)
        return output.getvalue(),mime,extension
