from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

class LeadCreate(BaseModel):
    name: str = Field(min_length=2,max_length=120)
    phone: str = Field(pattern=r'^\+?[0-9]{10,15}$')
    project_id: str
    source: Literal['property_portal','social_media','website','hoarding','other']
    preferred_configuration: Literal['2BHK','3BHK'] | None = None
    budget_max_inr: int | None = Field(default=None, ge=0, le=1_000_000_000)
    contact_consent: bool = False

class Login(BaseModel):
    email: str
    password: str

class BookRequest(BaseModel):
    project_id: str
    slot_id: str

class ConsentUpdate(BaseModel):
    contact_consent: bool

class SlotCreate(BaseModel):
    project_id: str
    starts_at: datetime
    ends_at: datetime
    @field_validator('starts_at','ends_at')
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('Timezone offset required')
        return value

class MessageCreate(BaseModel):
    message: str = Field(min_length=1,max_length=3000)
    language: Literal['en','hi','gu'] = 'en'
