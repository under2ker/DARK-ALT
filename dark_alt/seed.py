from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Wallpaper

SEED=[
("obsidian-horizon","OBSIDIAN HORIZON","CYBERPUNK","4K",3840,2160,"DARK","https://images.unsplash.com/photo-1519608487953-e999c86e7455?auto=format&fit=crop&w=1600&q=90",94),
("nocturne-07","NOCTURNE // 07","ABSTRACT","4K",3840,2160,"DARK","https://images.unsplash.com/photo-1511497584788-876760111969?auto=format&fit=crop&w=1600&q=90",91),
("void-signal","VOID SIGNAL","SPACE","5K",5120,2880,"DARK","https://images.unsplash.com/photo-1462331940025-496dfbfc7564?auto=format&fit=crop&w=1600&q=90",97),
("concrete-dreams","CONCRETE DREAMS","ARCHITECTURE","4K",3840,2160,"NEUTRAL","https://images.unsplash.com/photo-1487958449943-2429e8be8625?auto=format&fit=crop&w=1600&q=90",89)]

def seed_database(db: Session):
    if db.scalar(select(Wallpaper.id).limit(1)): return
    for slug,title,category,res,w,h,tone,url,score in SEED:
        db.add(Wallpaper(slug=slug,title=title,source="DARK//ALT DEMO",source_url=url,image_url=url,thumbnail_url=url,
            width=w,height=h,ratio="16:9",orientation="landscape",resolution=res,tone=tone,tags=[category.lower(),tone.lower()],
            categories=[category],quality_score=score,provider_key="demo",provider_external_id=slug))
    db.commit()
