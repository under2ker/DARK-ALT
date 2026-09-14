from contextlib import asynccontextmanager
from datetime import datetime, timezone
import asyncio
from io import BytesIO
from typing import Literal
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, RedirectResponse, StreamingResponse
from sqlalchemy import String, and_, cast, desc, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .crawler import crawl_provider
from .database import Base, SessionLocal, engine, get_db
from .models import AuditLog, Collection, CollectionItem, CrawlJob, Download, Favorite, ImageAnalysis, ProviderState, SearchEvent, SemanticProfile, User, UserPreference, ViewEvent, Wallpaper
from .image_analysis import analyze_pending
from .provider_registry import load_provider_config, set_provider_enabled
from .seed import seed_database
from .tasks import analyze_pending_task, classify_pending_task, crawl_provider_task
from .auth import create_token, current_user, hash_password, optional_user, verify_password
from .schemas import CollectionRequest, DownloadRequest, LoginRequest, PreferencesRequest, RegisterRequest
from .download_service import fetch_source, inspect_source_size, render_variant, resolve_size
from .semantic import classify_pending
from .similarity import rank_similar
from .admin_security import require_admin_key
from .middleware import RateLimitMiddleware, RequestContextMiddleware, SecurityHeadersMiddleware
from .logging_config import configure_logging
from .config import settings
from .preferences import get_or_create_preferences, serialize_preferences

def serialize(w: Wallpaper, db:Session|None=None):
    profile=db.scalar(select(SemanticProfile).where(SemanticProfile.wallpaper_id==w.id)) if db else None
    return {"id":w.slug,"title":w.title,"description":w.description,"tags":w.tags,"categories":w.categories,
        "category":w.categories[0] if w.categories else None,"resolution":w.resolution,"width":w.width,"height":w.height,
        "ratio":w.ratio,"orientation":w.orientation,"tone":w.tone,"source":w.source,"source_url":w.source_url,
        "author":w.author,"license":w.license,"license_url":w.license_url,"image_url":w.image_url,"thumbnail_url":w.thumbnail_url,
        "dominant_color":w.dominant_color,"brightness":w.brightness,"moods":profile.moods if profile else [],
        "scene":profile.scene if profile else None,"style":profile.style if profile else None,
        "quality_score":round(w.quality_score,1),"indexed_at":w.indexed_at}

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.logger=configure_logging(settings.log_level)
    Base.metadata.create_all(engine)
    with SessionLocal() as db: seed_database(db)
    yield

app=FastAPI(title="DARK//ALT API",version="0.9.0",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:8080","http://127.0.0.1:8080"],allow_methods=["GET","POST","DELETE"],allow_headers=["*"])
app.add_middleware(RateLimitMiddleware,requests_per_minute=240)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestContextMiddleware)

@app.get("/api/health")
def health(db:Session=Depends(get_db)):
    providers=db.scalar(select(func.count(ProviderState.id))) or 0
    return {"status":"ok","service":"dark-alt-api","version":"0.9.0","environment":settings.environment,"wallpapers":db.scalar(select(func.count(Wallpaper.id))),"providers":providers,"timestamp":datetime.now(timezone.utc).isoformat()}

@app.get("/api/ready")
def readiness(db:Session=Depends(get_db)):
    try:
        db.execute(text("SELECT 1")); return {"status":"ready","database":"ok"}
    except Exception as exc:
        raise HTTPException(503,"Database unavailable") from exc

@app.get("/metrics",response_class=PlainTextResponse)
def metrics(db:Session=Depends(get_db)):
    values={"wallpapers":db.scalar(select(func.count(Wallpaper.id))) or 0,"users":db.scalar(select(func.count(User.id))) or 0,
        "favorites":db.scalar(select(func.count(Favorite.id))) or 0,"downloads":db.scalar(select(func.count(Download.id))) or 0,
        "views":db.scalar(select(func.count(ViewEvent.id))) or 0,"searches":db.scalar(select(func.count(SearchEvent.id))) or 0,
        "crawl_jobs":db.scalar(select(func.count(CrawlJob.id))) or 0}
    lines=[]
    for key,value in values.items():
        lines.extend([f"# HELP dark_alt_{key} Total {key}",f"# TYPE dark_alt_{key} gauge",f"dark_alt_{key} {value}"])
    return "\n".join(lines)+"\n"

@app.get("/api/wallpapers")
def wallpapers(q:str|None=None,resolution:str|None=None,ratio:str|None=None,tone:str|None=None,source:str|None=None,mood:str|None=None,category:str|None=None,
        orientation:str|None=None,license:str|None=None,is_ai:bool|None=None,width_min:int|None=Query(None,ge=1),width_max:int|None=Query(None,ge=1),
        height_min:int|None=Query(None,ge=1),height_max:int|None=Query(None,ge=1),quality_min:float|None=Query(None,ge=0,le=100),quality_max:float|None=Query(None,ge=0,le=100),
        sort:str=Query("newest",pattern="^(newest|quality|popular)$"),
        brightness_min:float|None=Query(None,ge=0,le=1),brightness_max:float|None=Query(None,ge=0,le=1),nsfw_max:float|None=Query(None,ge=0,le=1),
        limit:int=Query(24,ge=1,le=100),cursor:int=Query(0,ge=0),db:Session=Depends(get_db),user:User|None=Depends(optional_user)):
    stmt=select(Wallpaper).outerjoin(SemanticProfile,SemanticProfile.wallpaper_id==Wallpaper.id)
    if q:
        for term in q.split():
            pattern=f"%{term}%"; stmt=stmt.where(or_(Wallpaper.title.ilike(pattern),Wallpaper.description.ilike(pattern),
                cast(Wallpaper.tags,String).ilike(pattern),cast(Wallpaper.categories,String).ilike(pattern),
                cast(SemanticProfile.moods,String).ilike(pattern),cast(SemanticProfile.generated_tags,String).ilike(pattern),
                SemanticProfile.scene.ilike(pattern),SemanticProfile.style.ilike(pattern)))
    if resolution: stmt=stmt.where(Wallpaper.resolution==resolution.upper())
    if ratio: stmt=stmt.where(Wallpaper.ratio==ratio)
    if tone: stmt=stmt.where(Wallpaper.tone==tone.upper())
    if source: stmt=stmt.where(Wallpaper.source.ilike(f"%{source}%"))
    if mood: stmt=stmt.where(SemanticProfile.moods.contains(mood.lower()))
    if category: stmt=stmt.where(Wallpaper.categories.contains(category.upper()))
    if orientation: stmt=stmt.where(Wallpaper.orientation==orientation.lower())
    if license: stmt=stmt.where(Wallpaper.license.ilike(f"%{license}%"))
    if is_ai is not None: stmt=stmt.where(Wallpaper.is_ai==is_ai)
    if width_min is not None: stmt=stmt.where(Wallpaper.width>=width_min)
    if width_max is not None: stmt=stmt.where(Wallpaper.width<=width_max)
    if height_min is not None: stmt=stmt.where(Wallpaper.height>=height_min)
    if height_max is not None: stmt=stmt.where(Wallpaper.height<=height_max)
    if quality_min is not None: stmt=stmt.where(Wallpaper.quality_score>=quality_min)
    if quality_max is not None: stmt=stmt.where(Wallpaper.quality_score<=quality_max)
    if brightness_min is not None: stmt=stmt.where(Wallpaper.brightness>=brightness_min)
    if brightness_max is not None: stmt=stmt.where(Wallpaper.brightness<=brightness_max)
    preference=get_or_create_preferences(db,user) if user else None
    allowed_nsfw=nsfw_max if nsfw_max is not None else (.5 if preference and preference.allow_questionable else .15)
    stmt=stmt.where(Wallpaper.nsfw_score<=allowed_nsfw)
    if sort=="newest":
        rows=db.scalars(stmt.where(Wallpaper.id>cursor).order_by(Wallpaper.id).limit(limit+1)).all()
        has_more=len(rows)>limit; rows=rows[:limit]
    else:
        rows=db.scalars(stmt.order_by(desc(Wallpaper.quality_score)).limit(limit)).all(); has_more=False
    if q and cursor==0:
        db.add(SearchEvent(user_id=user.id if user else None,query=q,result_count=db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)); db.commit()
    return {"items":[serialize(w,db) for w in rows],"total":db.scalar(select(func.count()).select_from(stmt.subquery())),"next_cursor":rows[-1].id if sort=="newest" and has_more and rows else None}

@app.get("/api/wallpapers/{slug}")
def wallpaper(slug:str,db:Session=Depends(get_db)):
    item=db.scalar(select(Wallpaper).where(Wallpaper.slug==slug))
    if not item: raise HTTPException(404,"Wallpaper not found")
    return serialize(item,db)

@app.get("/api/search")
def search(q:str=Query(min_length=1),limit:int=24,db:Session=Depends(get_db),user:User|None=Depends(optional_user)):
    result=wallpapers(q=q,resolution=None,ratio=None,tone=None,source=None,mood=None,category=None,orientation=None,license=None,is_ai=None,
        width_min=None,width_max=None,height_min=None,height_max=None,quality_min=None,quality_max=None,sort="quality",
        brightness_min=None,brightness_max=None,nsfw_max=None,limit=limit,cursor=0,db=db,user=user)
    return result

@app.get("/api/trending")
def trending(period:str="today",limit:int=12,db:Session=Depends(get_db)):
    views=select(ViewEvent.wallpaper_id,func.count(ViewEvent.id).label("views")).group_by(ViewEvent.wallpaper_id).subquery()
    favs=select(Favorite.wallpaper_id,func.count(Favorite.id).label("favorites")).group_by(Favorite.wallpaper_id).subquery()
    downloads=select(Download.wallpaper_id,func.count(Download.id).label("downloads")).group_by(Download.wallpaper_id).subquery()
    score=(func.coalesce(views.c.views,0)*1+func.coalesce(favs.c.favorites,0)*5+func.coalesce(downloads.c.downloads,0)*3+Wallpaper.quality_score/10)
    rows=db.scalars(select(Wallpaper).outerjoin(views,views.c.wallpaper_id==Wallpaper.id).outerjoin(favs,favs.c.wallpaper_id==Wallpaper.id).outerjoin(downloads,downloads.c.wallpaper_id==Wallpaper.id).order_by(desc(score)).limit(limit)).all()
    return {"period":period,"items":[serialize(w,db) for w in rows]}

@app.get("/api/recommendations")
def recommendations(limit:int=Query(12,ge=1,le=50),user:User=Depends(current_user),db:Session=Depends(get_db)):
    liked=db.scalars(select(Wallpaper).join(Favorite,Favorite.wallpaper_id==Wallpaper.id).where(Favorite.user_id==user.id)).all()
    preference=get_or_create_preferences(db,user)
    if not liked:
        rows=db.scalars(select(Wallpaper).order_by(desc(Wallpaper.quality_score)).limit(200)).all()
        def preference_score(item):
            profile=db.scalar(select(SemanticProfile).where(SemanticProfile.wallpaper_id==item.id))
            score=item.quality_score/5
            if item.tone in preference.preferred_tones: score+=15
            if item.resolution in preference.preferred_resolutions: score+=12
            if profile: score+=sum(8 for mood in profile.moods if mood.upper() in preference.preferred_moods)
            return score
        ranked=sorted(rows,key=preference_score,reverse=True)[:limit]
        strategy="preference_fallback" if any([preference.preferred_moods,preference.preferred_tones,preference.preferred_resolutions]) else "quality_fallback"
        return {"strategy":strategy,"items":[serialize(w,db) for w in ranked]}
    liked_ids={x.id for x in liked}; aggregate={}
    for source in liked:
        for score,item,reasons in rank_similar(db,source,max(limit*3,20)):
            if item.id in liked_ids: continue
            current=aggregate.get(item.id,{"score":0,"hits":0,"item":item,"reasons":set()})
            current["score"]+=score;current["hits"]+=1;current["reasons"].update(reasons);aggregate[item.id]=current
    ranked=sorted(aggregate.values(),key=lambda x:(x["score"]/x["hits"],x["hits"]),reverse=True)[:limit]
    return {"strategy":"favorites_similarity","items":[{**serialize(x["item"],db),"recommendation_score":round(x["score"]/x["hits"],2),"reasons":sorted(x["reasons"])} for x in ranked]}

@app.get("/api/similar/{slug}")
def similar(slug:str,limit:int=8,db:Session=Depends(get_db)):
    target=db.scalar(select(Wallpaper).where(Wallpaper.slug==slug))
    if not target: raise HTTPException(404,"Wallpaper not found")
    ranked=rank_similar(db,target,limit)
    return {"items":[{**serialize(w,db),"similarity_score":score,"similarity_reasons":reasons} for score,w,reasons in ranked]}

@app.post("/api/views/{slug}",status_code=201)
def record_view(slug:str,user:User|None=Depends(optional_user),db:Session=Depends(get_db)):
    wallpaper=db.scalar(select(Wallpaper).where(Wallpaper.slug==slug))
    if not wallpaper: raise HTTPException(404,"Wallpaper not found")
    db.add(ViewEvent(user_id=user.id if user else None,wallpaper_id=wallpaper.id)); db.commit()
    return {"status":"recorded","wallpaper_id":slug}

@app.get("/api/recently-viewed")
def recently_viewed(limit:int=Query(20,ge=1,le=100),user:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.execute(select(ViewEvent,Wallpaper).join(Wallpaper,Wallpaper.id==ViewEvent.wallpaper_id).where(ViewEvent.user_id==user.id).order_by(desc(ViewEvent.viewed_at)).limit(limit*3)).all()
    seen=set(); items=[]
    for event,wallpaper in rows:
        if wallpaper.id in seen: continue
        seen.add(wallpaper.id); items.append({"viewed_at":event.viewed_at,"wallpaper":serialize(wallpaper,db)})
        if len(items)>=limit: break
    return {"items":items}

@app.get("/api/search/history")
def search_history(limit:int=Query(20,ge=1,le=100),user:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(SearchEvent).where(SearchEvent.user_id==user.id).order_by(desc(SearchEvent.searched_at)).limit(limit*3)).all()
    seen=set(); items=[]
    for row in rows:
        if row.query.lower() in seen: continue
        seen.add(row.query.lower()); items.append({"query":row.query,"result_count":row.result_count,"searched_at":row.searched_at})
        if len(items)>=limit: break
    return {"items":items}

@app.delete("/api/recently-viewed")
def clear_recently_viewed(user:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(ViewEvent).where(ViewEvent.user_id==user.id)).all()
    for row in rows: db.delete(row)
    db.commit(); return {"status":"cleared","count":len(rows)}

@app.delete("/api/search/history")
def clear_search_history(user:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(SearchEvent).where(SearchEvent.user_id==user.id)).all()
    for row in rows: db.delete(row)
    db.commit(); return {"status":"cleared","count":len(rows)}

@app.get("/api/data-export")
def export_user_data(user:User=Depends(current_user),db:Session=Depends(get_db)):
    return {"exported_at":datetime.now(timezone.utc).isoformat(),"user":{"id":user.id,"username":user.username,"created_at":user.created_at},
        "preferences":serialize_preferences(get_or_create_preferences(db,user)),"favorites":favorites(user,db)["items"],
        "collections":collections(user,db)["items"],"recently_viewed":recently_viewed(100,user,db)["items"],
        "search_history":search_history(100,user,db)["items"],"downloads":download_history(100,user,db)["items"]}

@app.get("/api/sources")
def sources(db:Session=Depends(get_db)):
    states={s.key:s for s in db.scalars(select(ProviderState)).all()}
    items=[]
    for key,cfg in load_provider_config().items():
        s=states.get(key); items.append({"key":key,"name":s.name if s else key.title(),"enabled":cfg.get("enabled",False),
            "status":s.status if s else ("DISABLED" if not cfg.get("enabled") else "READY"),"images_discovered":s.images_discovered if s else 0,
            "images_accepted":s.images_accepted if s else 0,"duplicates":s.duplicates if s else 0,"last_success_at":s.last_success_at if s else None})
    return {"items":items}

@app.get("/api/colors")
def colors(db:Session=Depends(get_db)):
    stmt=select(Wallpaper.dominant_color,func.count(Wallpaper.id)).where(Wallpaper.dominant_color.is_not(None)).group_by(Wallpaper.dominant_color).order_by(desc(func.count(Wallpaper.id))).limit(24)
    rows=db.execute(stmt).all()
    return {"items":[{"color":color,"count":count} for color,count in rows]}

@app.get("/api/moods")
def moods(db:Session=Depends(get_db)):
    counts={}
    for profile in db.scalars(select(SemanticProfile)).all():
        for mood in profile.moods: counts[mood]=counts.get(mood,0)+1
    return {"items":[{"mood":key,"count":value} for key,value in sorted(counts.items(),key=lambda x:(-x[1],x[0]))]}

@app.get("/api/categories")
def categories(db:Session=Depends(get_db)):
    counts={}
    for wallpaper in db.scalars(select(Wallpaper)).all():
        for category in wallpaper.categories: counts[category]=counts.get(category,0)+1
    return {"items":[{"category":key,"count":value} for key,value in sorted(counts.items(),key=lambda x:(-x[1],x[0]))]}

@app.get("/api/tags")
def tags(limit:int=Query(60,ge=1,le=200),db:Session=Depends(get_db)):
    counts={}
    for wallpaper in db.scalars(select(Wallpaper)).all():
        for tag in wallpaper.tags: counts[tag.lower()]=counts.get(tag.lower(),0)+1
    for profile in db.scalars(select(SemanticProfile)).all():
        for tag in profile.generated_tags: counts[tag.lower()]=counts.get(tag.lower(),0)+1
    return {"items":[{"tag":key,"count":value} for key,value in sorted(counts.items(),key=lambda x:(-x[1],x[0]))[:limit]]}

@app.post("/api/auth/register",status_code=201)
def register(payload:RegisterRequest,db:Session=Depends(get_db)):
    if db.scalar(select(User).where(User.username==payload.username)): raise HTTPException(409,"Username is already registered")
    user=User(username=payload.username,password_hash=hash_password(payload.password)); db.add(user); db.commit(); db.refresh(user)
    return {"access_token":create_token(user),"token_type":"bearer","user":{"id":user.id,"username":user.username}}

@app.post("/api/auth/login")
def login(payload:LoginRequest,db:Session=Depends(get_db)):
    user=db.scalar(select(User).where(User.username==payload.username.lower()))
    if not user or not verify_password(payload.password,user.password_hash): raise HTTPException(401,"Invalid username or password")
    return {"access_token":create_token(user),"token_type":"bearer","user":{"id":user.id,"username":user.username}}

@app.get("/api/auth/me")
def me(user:User=Depends(current_user)):
    return {"id":user.id,"username":user.username,"created_at":user.created_at}

@app.get("/api/settings")
def settings_endpoint(user:User=Depends(current_user),db:Session=Depends(get_db)):
    return serialize_preferences(get_or_create_preferences(db,user))

@app.put("/api/settings")
def update_settings(payload:PreferencesRequest,user:User=Depends(current_user),db:Session=Depends(get_db)):
    preference=get_or_create_preferences(db,user)
    preference.preferred_moods=payload.preferred_moods; preference.preferred_tones=payload.preferred_tones
    preference.preferred_resolutions=payload.preferred_resolutions; preference.default_download_preset=payload.default_download_preset
    preference.allow_questionable=payload.allow_questionable; db.commit(); db.refresh(preference)
    return serialize_preferences(preference)

@app.get("/api/favorites")
def favorites(user:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(Wallpaper).join(Favorite,Favorite.wallpaper_id==Wallpaper.id).where(Favorite.user_id==user.id).order_by(desc(Favorite.created_at))).all()
    return {"items":[serialize(w,db) for w in rows],"total":len(rows)}

@app.post("/api/favorites/{slug}",status_code=201)
def add_favorite(slug:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    wallpaper=db.scalar(select(Wallpaper).where(Wallpaper.slug==slug))
    if not wallpaper: raise HTTPException(404,"Wallpaper not found")
    if not db.scalar(select(Favorite).where(Favorite.user_id==user.id,Favorite.wallpaper_id==wallpaper.id)):
        db.add(Favorite(user_id=user.id,wallpaper_id=wallpaper.id)); db.commit()
    return {"status":"saved","wallpaper_id":slug}

@app.delete("/api/favorites/{slug}")
def remove_favorite(slug:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=db.scalar(select(Favorite).join(Wallpaper,Wallpaper.id==Favorite.wallpaper_id).where(Favorite.user_id==user.id,Wallpaper.slug==slug))
    if row: db.delete(row); db.commit()
    return {"status":"removed","wallpaper_id":slug}

@app.get("/api/collections")
def collections(user:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(Collection).where(Collection.user_id==user.id).order_by(desc(Collection.created_at))).all()
    return {"items":[{"id":c.id,"name":c.name,"description":c.description,"count":db.scalar(select(func.count(CollectionItem.id)).where(CollectionItem.collection_id==c.id)),"created_at":c.created_at} for c in rows]}

@app.post("/api/collections",status_code=201)
def create_collection(payload:CollectionRequest,user:User=Depends(current_user),db:Session=Depends(get_db)):
    collection=Collection(user_id=user.id,name=payload.name.strip(),description=payload.description); db.add(collection)
    try: db.commit(); db.refresh(collection)
    except IntegrityError: db.rollback(); raise HTTPException(409,"A collection with this name already exists")
    return {"id":collection.id,"name":collection.name,"description":collection.description,"count":0}

@app.get("/api/collections/{collection_id}")
def collection_detail(collection_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    collection=db.scalar(select(Collection).where(Collection.id==collection_id,Collection.user_id==user.id))
    if not collection: raise HTTPException(404,"Collection not found")
    rows=db.scalars(select(Wallpaper).join(CollectionItem,CollectionItem.wallpaper_id==Wallpaper.id).where(CollectionItem.collection_id==collection.id)).all()
    return {"id":collection.id,"name":collection.name,"description":collection.description,"items":[serialize(w,db) for w in rows]}

@app.post("/api/collections/{collection_id}/items/{slug}",status_code=201)
def add_collection_item(collection_id:int,slug:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    collection=db.scalar(select(Collection).where(Collection.id==collection_id,Collection.user_id==user.id))
    wallpaper=db.scalar(select(Wallpaper).where(Wallpaper.slug==slug))
    if not collection or not wallpaper: raise HTTPException(404,"Collection or wallpaper not found")
    if not db.scalar(select(CollectionItem).where(CollectionItem.collection_id==collection.id,CollectionItem.wallpaper_id==wallpaper.id)):
        db.add(CollectionItem(collection_id=collection.id,wallpaper_id=wallpaper.id)); db.commit()
    return {"status":"saved","collection_id":collection.id,"wallpaper_id":slug}

@app.delete("/api/collections/{collection_id}/items/{slug}")
def remove_collection_item(collection_id:int,slug:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    collection=db.scalar(select(Collection).where(Collection.id==collection_id,Collection.user_id==user.id))
    if not collection: raise HTTPException(404,"Collection not found")
    item=db.scalar(select(CollectionItem).join(Wallpaper,Wallpaper.id==CollectionItem.wallpaper_id).where(CollectionItem.collection_id==collection.id,Wallpaper.slug==slug))
    if item: db.delete(item); db.commit()
    return {"status":"removed"}

@app.post("/api/downloads/{slug}",status_code=201)
def track_download(slug:str,payload:DownloadRequest,user:User|None=Depends(optional_user),db:Session=Depends(get_db)):
    wallpaper=db.scalar(select(Wallpaper).where(Wallpaper.slug==slug))
    if not wallpaper: raise HTTPException(404,"Wallpaper not found")
    db.add(Download(user_id=user.id if user else None,wallpaper_id=wallpaper.id,variant=payload.variant.upper())); db.commit()
    return {"download_url":wallpaper.image_url,"variant":payload.variant.upper()}

@app.get("/api/downloads")
def download_history(limit:int=Query(30,ge=1,le=100),user:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.execute(select(Download,Wallpaper).join(Wallpaper,Wallpaper.id==Download.wallpaper_id).where(Download.user_id==user.id).order_by(desc(Download.downloaded_at)).limit(limit)).all()
    return {"items":[{"id":download.id,"variant":download.variant,"downloaded_at":download.downloaded_at,"wallpaper":serialize(wallpaper,db)} for download,wallpaper in rows]}

@app.get("/api/downloads/{slug}/file")
async def download_file(slug:str,preset:Literal["ORIGINAL","4K","2K","FHD","CUSTOM"]="ORIGINAL",
        mode:Literal["fit","fill","crop","center","stretch","blur_background"]="fit",
        format:Literal["JPEG","PNG","WEBP"]="JPEG",width:int|None=Query(None,ge=320,le=7680),
        height:int|None=Query(None,ge=240,le=4320),quality:int=Query(88,ge=50,le=96),allow_upscale:bool=False,
        user:User|None=Depends(optional_user),db:Session=Depends(get_db)):
    wallpaper=db.scalar(select(Wallpaper).where(Wallpaper.slug==slug))
    if not wallpaper: raise HTTPException(404,"Wallpaper not found")
    provider_config=load_provider_config().get(wallpaper.provider_key,{"can_download":True})
    if not provider_config.get("can_download",False): raise HTTPException(403,"Source does not permit downloads")
    db.add(Download(user_id=user.id if user else None,wallpaper_id=wallpaper.id,variant=preset)); db.commit()
    if preset=="ORIGINAL": return RedirectResponse(wallpaper.image_url,status_code=307)
    try:
        raw=await fetch_source(wallpaper.image_url)
        actual_size=await asyncio.to_thread(inspect_source_size,raw)
        target=resolve_size(actual_size,preset,width,height,allow_upscale)
        rendered,mime,extension=await asyncio.to_thread(render_variant,raw,target,mode,format,quality)
    except (ValueError,OSError) as exc: raise HTTPException(422,str(exc))
    filename=f"dark-alt-{wallpaper.slug}-{target[0]}x{target[1]}.{extension}"
    return StreamingResponse(BytesIO(rendered),media_type=mime,headers={"Content-Disposition":f'attachment; filename="{filename}"',"X-Dark-Alt-Size":f"{target[0]}x{target[1]}"})

@app.get("/api/download-options/{slug}")
def download_options(slug:str,db:Session=Depends(get_db)):
    wallpaper=db.scalar(select(Wallpaper).where(Wallpaper.slug==slug))
    if not wallpaper: raise HTTPException(404,"Wallpaper not found")
    options=[{"preset":"ORIGINAL","width":wallpaper.width,"height":wallpaper.height,"upscale":False}]
    for name,(width,height) in {"4K":(3840,2160),"2K":(2560,1440),"FHD":(1920,1080)}.items():
        scale=min(1,wallpaper.width/width,wallpaper.height/height)
        options.append({"preset":name,"width":int(width*scale),"height":int(height*scale),"upscale":scale<1})
    return {"wallpaper_id":slug,"options":options,"modes":["fit","fill","crop","center","stretch","blur_background"],"formats":["JPEG","PNG","WEBP"]}

@app.post("/admin/providers/{provider_key}/crawl")
async def run_crawl(provider_key:str,limit:int=Query(12,ge=1,le=50),db:Session=Depends(get_db),admin=Depends(require_admin_key)):
    try: job=await crawl_provider(db,provider_key,limit)
    except ValueError as exc: raise HTTPException(404,str(exc))
    db.add(AuditLog(action="provider.crawl",target=provider_key,detail={"job_id":job.id,"status":job.status,"accepted":job.accepted,"duplicates":job.duplicates}));db.commit()
    return {"job_id":job.id,"status":job.status,"discovered":job.discovered,"accepted":job.accepted,"duplicates":job.duplicates,"rejected":job.rejected,"error":job.error}

@app.post("/admin/providers/{provider_key}/enqueue")
def enqueue_crawl(provider_key:str,limit:int=Query(20,ge=1,le=50),admin=Depends(require_admin_key)):
    if provider_key not in load_provider_config(): raise HTTPException(404,"Provider not found")
    task=crawl_provider_task.delay(provider_key,limit)
    return {"task_id":task.id,"status":"QUEUED"}

@app.post("/admin/providers/{provider_key}/enable")
def enable_provider(provider_key:str,db:Session=Depends(get_db),admin=Depends(require_admin_key)):
    try: config=set_provider_enabled(provider_key,True)
    except KeyError: raise HTTPException(404,"Provider not found")
    state=db.scalar(select(ProviderState).where(ProviderState.key==provider_key))
    if state: state.enabled=True; state.status="READY"
    db.add(AuditLog(action="provider.enable",target=provider_key,detail={"config":config}));db.commit()
    return {"key":provider_key,"enabled":True}

@app.post("/admin/providers/{provider_key}/disable")
def disable_provider(provider_key:str,db:Session=Depends(get_db),admin=Depends(require_admin_key)):
    try: config=set_provider_enabled(provider_key,False)
    except KeyError: raise HTTPException(404,"Provider not found")
    state=db.scalar(select(ProviderState).where(ProviderState.key==provider_key))
    if state: state.enabled=False; state.status="DISABLED"
    db.add(AuditLog(action="provider.disable",target=provider_key,detail={"config":config}));db.commit()
    return {"key":provider_key,"enabled":False}

@app.get("/admin/crawler/jobs")
def jobs(limit:int=25,db:Session=Depends(get_db)):
    rows=db.scalars(select(CrawlJob).order_by(desc(CrawlJob.id)).limit(limit)).all()
    return {"items":[{"id":j.id,"provider":j.provider.key,"status":j.status,"started_at":j.started_at,"finished_at":j.finished_at,
        "discovered":j.discovered,"accepted":j.accepted,"duplicates":j.duplicates,"rejected":j.rejected,"error":j.error} for j in rows]}

@app.post("/admin/analysis/run")
async def run_analysis(limit:int=Query(8,ge=1,le=30),db:Session=Depends(get_db),admin=Depends(require_admin_key)):
    results=await analyze_pending(db,limit)
    db.add(AuditLog(action="analysis.run",target="wallpapers",detail={"processed":len(results),"errors":sum(x.status=="ERROR" for x in results)}));db.commit()
    return {"processed":len(results),"success":sum(x.status=="SUCCESS" for x in results),
        "duplicates":sum(x.status=="DUPLICATE" for x in results),"errors":sum(x.status=="ERROR" for x in results)}

@app.post("/admin/analysis/enqueue")
def enqueue_analysis(limit:int=Query(20,ge=1,le=100),admin=Depends(require_admin_key)):
    task=analyze_pending_task.delay(limit)
    return {"task_id":task.id,"status":"QUEUED"}

@app.post("/admin/semantic/run")
def run_semantic(limit:int=Query(50,ge=1,le=500),db:Session=Depends(get_db),admin=Depends(require_admin_key)):
    profiles=classify_pending(db,limit)
    db.add(AuditLog(action="semantic.classify",target="wallpapers",detail={"processed":len(profiles)}));db.commit()
    return {"processed":len(profiles)}

@app.post("/admin/semantic/enqueue")
def enqueue_semantic(limit:int=Query(100,ge=1,le=500),admin=Depends(require_admin_key)):
    task=classify_pending_task.delay(limit)
    return {"task_id":task.id,"status":"QUEUED"}

@app.get("/admin/semantic/status")
def semantic_status(db:Session=Depends(get_db)):
    total=db.scalar(select(func.count(Wallpaper.id))) or 0; processed=db.scalar(select(func.count(SemanticProfile.id))) or 0
    return {"total":total,"processed":processed,"pending":max(0,total-processed)}

@app.get("/admin/audit")
def audit_log(limit:int=Query(50,ge=1,le=200),db:Session=Depends(get_db),admin=Depends(require_admin_key)):
    rows=db.scalars(select(AuditLog).order_by(desc(AuditLog.id)).limit(limit)).all()
    return {"items":[{"id":x.id,"action":x.action,"target":x.target,"detail":x.detail,"created_at":x.created_at} for x in rows]}

@app.get("/admin/analysis/status")
def analysis_status(db:Session=Depends(get_db)):
    total=db.scalar(select(func.count(Wallpaper.id))) or 0
    processed=db.scalar(select(func.count(ImageAnalysis.id))) or 0
    success=db.scalar(select(func.count(ImageAnalysis.id)).where(ImageAnalysis.status=="SUCCESS")) or 0
    duplicates=db.scalar(select(func.count(ImageAnalysis.id)).where(ImageAnalysis.status=="DUPLICATE")) or 0
    errors=db.scalar(select(func.count(ImageAnalysis.id)).where(ImageAnalysis.status=="ERROR")) or 0
    return {"total":total,"processed":processed,"pending":max(0,total-processed),"success":success,"duplicates":duplicates,"errors":errors}

@app.get("/admin/statistics")
def statistics(db:Session=Depends(get_db),admin=Depends(require_admin_key)):
    return {"wallpapers":db.scalar(select(func.count(Wallpaper.id))) or 0,
        "users":db.scalar(select(func.count(User.id))) or 0,
        "views":db.scalar(select(func.count(ViewEvent.id))) or 0,
        "favorites":db.scalar(select(func.count(Favorite.id))) or 0,
        "downloads":db.scalar(select(func.count(Download.id))) or 0,
        "searches":db.scalar(select(func.count(SearchEvent.id))) or 0,
        "crawl_jobs":db.scalar(select(func.count(CrawlJob.id))) or 0,
        "analysis":analysis_status(db),
        "semantic":semantic_status(db)}
