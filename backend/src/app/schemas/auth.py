import uuid

from sqlmodel import SQLModel

from app.models.user import UserRole


class UserRegister(SQLModel):
    username: str
    email: str
    password: str


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"
    user_id: uuid.UUID


class UserRead(SQLModel):
    id: uuid.UUID
    username: str
    email: str
    is_active: bool
    role: UserRole
