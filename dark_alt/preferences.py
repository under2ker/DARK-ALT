from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import User, UserPreference

def get_or_create_preferences(db: Session, user: User) -> UserPreference:
    preference=db.scalar(select(UserPreference).where(UserPreference.user_id==user.id))
    if not preference:
        preference=UserPreference(user_id=user.id); db.add(preference); db.commit(); db.refresh(preference)
    return preference

def serialize_preferences(preference: UserPreference):
    return {"preferred_moods":preference.preferred_moods,"preferred_tones":preference.preferred_tones,
        "preferred_resolutions":preference.preferred_resolutions,"default_download_preset":preference.default_download_preset,
        "allow_questionable":preference.allow_questionable,"updated_at":preference.updated_at}
