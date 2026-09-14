from datetime import datetime, timezone
import colorsys
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import SemanticProfile, Wallpaper

SCENES={
    "space":{"space","nebula","planet","galaxy","moon","star"},
    "nature":{"nature","mountain","forest","ocean","river","landscape","flower","animal"},
    "city":{"city","urban","street","architecture","building","night"},
    "technology":{"technology","robot","computer","cyberpunk","sci-fi","aircraft"},
    "abstract":{"abstract","minimal","texture","pattern","geometry","art"},
}

def _hue_traits(color: str|None):
    if not color or len(color)!=7:return []
    r,g,b=(int(color[i:i+2],16)/255 for i in (1,3,5)); hue,sat,_=colorsys.rgb_to_hsv(r,g,b)
    traits=[]
    if sat>.48: traits.append("vivid")
    if hue<.1 or hue>.92: traits.append("warm")
    elif .1<=hue<.22: traits.append("warm")
    elif .45<=hue<.75: traits.append("cold")
    return traits

def classify(wallpaper: Wallpaper):
    words=set((wallpaper.title+" "+" ".join(wallpaper.tags or [])+" "+" ".join(wallpaper.categories or [])).lower().replace("/"," ").split())
    scene=max(SCENES,key=lambda key:len(words&SCENES[key])) if any(words&v for v in SCENES.values()) else "visual"
    traits=_hue_traits(wallpaper.dominant_color); brightness=wallpaper.brightness if wallpaper.brightness is not None else .5
    moods=[]
    if brightness<.36:moods.extend(["dark","atmospheric"])
    if brightness>.7:moods.append("calm")
    if "warm" in traits:moods.extend(["warm","cozy"])
    if "cold" in traits:moods.extend(["cold","cinematic"])
    if "vivid" in traits:moods.append("dramatic")
    if words&{"minimal","simple","geometry","abstract"}:moods.extend(["minimal","calm"])
    if words&{"space","sci-fi","cyberpunk","robot","technology"}:moods.extend(["futuristic","epic"])
    if words&{"storm","war","fire","horror","aggressive"}:moods.extend(["aggressive","dramatic"])
    if not moods:moods=["cinematic","atmospheric"]
    priority=["futuristic","epic","minimal","dark","atmospheric","cinematic","calm","cold","warm","cozy","dramatic","aggressive"]
    unique=list(dict.fromkeys(moods)); moods=sorted(unique,key=lambda mood:priority.index(mood) if mood in priority else len(priority))
    style="minimal" if "minimal" in moods else "futuristic" if "futuristic" in moods else "editorial"
    generated=sorted(words&set().union(*SCENES.values())|set(traits)|{scene,style})
    return {"moods":moods[:5],"generated_tags":generated[:15],"scene":scene,"style":style,"confidence":round(min(.95,.55+len(generated)*.035),2)}

def classify_pending(db: Session, limit: int=50):
    existing=select(SemanticProfile.wallpaper_id)
    rows=db.scalars(select(Wallpaper).where(Wallpaper.id.not_in(existing)).order_by(Wallpaper.id).limit(limit)).all()
    profiles=[]
    for wallpaper in rows:
        profile=SemanticProfile(wallpaper_id=wallpaper.id,**classify(wallpaper),classified_at=datetime.now(timezone.utc))
        db.add(profile); profiles.append(profile)
    db.commit()
    return profiles
