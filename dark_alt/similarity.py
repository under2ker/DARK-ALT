import math
import imagehash
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import ImageAnalysis, SemanticProfile, Wallpaper

def _rgb(color):
    if not color or len(color)!=7:return None
    try:return tuple(int(color[i:i+2],16) for i in (1,3,5))
    except ValueError:return None

def _jaccard(left,right):
    a,b=set(left or []),set(right or [])
    return len(a&b)/len(a|b) if a|b else 0

def rank_similar(db:Session,target:Wallpaper,limit:int=12):
    candidates=db.scalars(select(Wallpaper).where(Wallpaper.id!=target.id)).all()
    analyses={x.wallpaper_id:x for x in db.scalars(select(ImageAnalysis)).all()}
    profiles={x.wallpaper_id:x for x in db.scalars(select(SemanticProfile)).all()}
    ta=analyses.get(target.id); tp=profiles.get(target.id); scored=[]
    for item in candidates:
        score=0.0; reasons=[]; ia=analyses.get(item.id); ip=profiles.get(item.id)
        tag_score=_jaccard((target.tags or [])+(target.categories or []),(item.tags or [])+(item.categories or []))
        if tag_score: score+=tag_score*25; reasons.append("tags")
        mood_score=_jaccard(tp.moods if tp else [],ip.moods if ip else [])
        if mood_score: score+=mood_score*15; reasons.append("mood")
        if target.ratio==item.ratio: score+=12; reasons.append("ratio")
        left,right=_rgb(target.dominant_color),_rgb(item.dominant_color)
        if left and right:
            distance=math.sqrt(sum((a-b)**2 for a,b in zip(left,right)))
            color_score=max(0,1-distance/441.7); score+=color_score*23
            if color_score>.65: reasons.append("color")
        if ta and ia and ta.phash and ia.phash:
            distance=imagehash.hex_to_hash(ta.phash)-imagehash.hex_to_hash(ia.phash)
            visual=max(0,1-distance/64); score+=visual*20
            if visual>.75: reasons.append("visual")
        score+=min(5,item.quality_score/20)
        scored.append((round(score,2),item,list(dict.fromkeys(reasons))))
    return sorted(scored,key=lambda row:row[0],reverse=True)[:limit]
