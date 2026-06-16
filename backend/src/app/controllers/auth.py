import uuid

from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import User
from app.schemas.auth import UserRead, UserRegister


async def register_user(data: UserRegister, session: AsyncSession) -> UserRead:
    result = await session.exec(
        select(User).where((User.username == data.username) | (User.email == data.email))
    )
    if result.first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered.",
        )

    user = User(
        username=data.username,
        email=data.email,
        hashed_password=get_password_hash(data.password),
    )
    session.add(user)
    await session.flush()  # sends INSERT, all Python-side defaults already set
    await session.commit()
    return UserRead.model_validate(user)


async def login_user(email: str, password: str, session: AsyncSession) -> dict:
    result = await session.exec(select(User).where(User.email == email))
    user = result.first()

    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled.",
        )

    access_token = create_access_token(subject=str(user.id))
    return {"access_token": access_token, "user": UserRead.model_validate(user)}


async def get_current_user(token_sub: str, session: AsyncSession) -> User:
    user = await session.get(User, uuid.UUID(token_sub))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive.",
        )
    return user
