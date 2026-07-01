"""Auth API routes — login, session, user management"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from szyg.auth import (
    authenticate, get_current_user, list_users, create_user,
    update_user, delete_user, toggle_user_active,
    LoginRequest, Token, User,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)


def require_admin(creds: HTTPAuthorizationCredentials = Depends(security)) -> User:
    if not creds:
        raise HTTPException(401, "Authentication required")
    user = get_current_user(creds.credentials)
    if not user:
        raise HTTPException(401, "Invalid token")
    if user.role != "admin":
        raise HTTPException(403, "Admin only")
    return user


async def optional_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> User | None:
    if not creds:
        return None
    return get_current_user(creds.credentials)


@router.post("/login", response_model=Token)
async def login(req: LoginRequest):
    token = authenticate(req.username, req.password)
    if not token:
        raise HTTPException(401, "用户名或密码错误")
    return token


@router.get("/session", response_model=User | None)
async def session(user: User | None = Depends(optional_user)):
    return user


@router.get("/users", response_model=list[User])
async def users(admin: User = Depends(require_admin)):
    return list_users()


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "user"
    email: str = ""
    oem_id: str | None = None


@router.post("/users", response_model=User)
async def add_user(
    req: CreateUserRequest, admin: User = Depends(require_admin),
):
    user = create_user(req.username, req.password, req.role, req.email, req.oem_id)
    if not user:
        raise HTTPException(400, "用户名已存在")
    return user


@router.put("/users/{user_id}", response_model=User)
async def update_user_endpoint(
    user_id: int, email: str | None = None, role: str | None = None,
    admin: User = Depends(require_admin),
):
    user = update_user(user_id, email=email, role=role)
    if not user:
        raise HTTPException(404, "用户不存在")
    return user


@router.delete("/users/{user_id}")
async def delete_user_endpoint(user_id: int, admin: User = Depends(require_admin)):
    if delete_user(user_id):
        return {"ok": True}
    raise HTTPException(404, "用户不存在")


@router.put("/users/{user_id}/toggle", response_model=User)
async def toggle_user_endpoint(user_id: int, admin: User = Depends(require_admin)):
    user = toggle_user_active(user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    return user
