from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel.ext.asyncio.session import AsyncSession

from app.controllers.auth import login_user, register_user
from app.db.session import get_session
from app.dependencies import get_current_active_user
from app.schemas.auth import UserRead, UserRegister

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserRead, status_code=201)
async def register(data: UserRegister, session: AsyncSession = Depends(get_session)):
    return await register_user(data, session)


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
):
    result = await login_user(form_data.username, form_data.password, session)
    return {
        "access_token": result["access_token"],
        "token_type": "bearer",
        "user": result["user"],
    }


@router.get("/me", response_model=UserRead)
async def me(current_user=Depends(get_current_active_user)):
    return current_user
