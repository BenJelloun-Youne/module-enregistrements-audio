from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr

from app.models import UserRole


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserResponse(UserBase):
    id: int
    is_active: bool
    role: UserRole
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        use_enum_values = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None
