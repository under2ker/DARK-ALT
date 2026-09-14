from pydantic import BaseModel, Field, field_validator
from .auth import USERNAME_RE

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3,max_length=40)
    password: str = Field(min_length=8,max_length=128)
    @field_validator("username")
    @classmethod
    def valid_username(cls,value):
        if not USERNAME_RE.fullmatch(value): raise ValueError("Use letters, numbers, underscore or hyphen")
        return value.lower()

class LoginRequest(BaseModel):
    username: str
    password: str

class CollectionRequest(BaseModel):
    name: str = Field(min_length=1,max_length=100)
    description: str|None = Field(default=None,max_length=500)

class DownloadRequest(BaseModel):
    variant: str = Field(default="ORIGINAL",max_length=30)

class PreferencesRequest(BaseModel):
    preferred_moods: list[str] = Field(default_factory=list,max_length=10)
    preferred_tones: list[str] = Field(default_factory=list,max_length=3)
    preferred_resolutions: list[str] = Field(default_factory=list,max_length=6)
    default_download_preset: str = Field(default="ORIGINAL",pattern="^(ORIGINAL|4K|2K|FHD)$")
    allow_questionable: bool = False

    @field_validator("preferred_moods","preferred_tones","preferred_resolutions")
    @classmethod
    def normalized_values(cls,values):
        return list(dict.fromkeys(str(value).strip().upper() for value in values if str(value).strip()))
