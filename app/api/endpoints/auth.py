from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from app.schemas.payloads import UserCreate, UserResponse, Token
from app.db.database import get_user_by_username, create_user, get_user_by_id, get_user_by_email
from app.core.security import verify_password, get_password_hash, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY
import jwt
from jwt.exceptions import InvalidTokenError
from datetime import timedelta

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception
        
    user = get_user_by_id(user_id)
    if user is None:
        raise credentials_exception
    return user

async def get_current_admin_user(current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Người dùng không có quyền quản trị viên"
        )
    return current_user

@router.post("/register", response_model=UserResponse)
def register(user_in: UserCreate):
    # 1. Kiểm tra username
    if get_user_by_username(user_in.username):
        raise HTTPException(status_code=400, detail="Username already registered")
        
    # 2. Kiểm tra email
    processed_email = user_in.email.lower()
    if get_user_by_email(processed_email):
        raise HTTPException(status_code=400, detail="Email already used")
    hashed_password = get_password_hash(user_in.password)
    user_id = create_user(user_in.username, hashed_password, processed_email)
    return UserResponse(id=user_id, username=user_in.username)

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["id"]}, expires_delta=access_token_expires
    )
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "is_admin": bool(user.get("is_admin", False))
    }
    # Trigger uvicorn reload
