import datetime as dt
from typing import Dict, Optional
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security.utils import get_authorization_scheme_param
import jwt
from jwt import PyJWTError as JWTError
from passlib.handlers.bcrypt import bcrypt
from rich.console import Console
from .config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, COOKIE_NAME, SERVICE_CONFIG
from .database import get_db_connection

console = Console()

async def check_user_exists(telegram_id: str, conn=Depends(get_db_connection)) -> bool:
    return await conn.fetchval("SELECT EXISTS(SELECT 1 FROM users WHERE telegram_id = $1)", telegram_id)

async def check_username_exists(username: str, conn=Depends(get_db_connection)) -> bool:
    return await conn.fetchval("SELECT EXISTS(SELECT 1 FROM users WHERE username = $1)", username)

async def register_user(telegram_id: str, username: str, password: str, conn=Depends(get_db_connection)):
    if await check_username_exists(username, conn):
        raise HTTPException(status_code=400, detail="Username already taken")
    if await check_user_exists(telegram_id, conn):
        raise HTTPException(status_code=400, detail="Telegram ID already registered")
    
    hashed_password = bcrypt.hash(password)
    trial_end = dt.datetime.utcnow() + dt.timedelta(days=SERVICE_CONFIG["free_period_days"])
    await conn.execute(
        """
        INSERT INTO users (telegram_id, username, password_hash, registration_date, trial_end_date, balance)
        VALUES ($1, $2, $3, NOW(), $4, 0.00)
        """,
        telegram_id, username, hashed_password, trial_end
    )

async def get_user(username: str, conn=Depends(get_db_connection)) -> Optional[dict]:
    row = await conn.fetchrow("SELECT * FROM users WHERE username = $1", username)
    return dict(row) if row else None

async def authenticate_user(username: str, plain_password: str, conn=Depends(get_db_connection)) -> Optional[dict]:
    user = await get_user(username, conn)
    if not user or not bcrypt.verify(plain_password, user["password_hash"]):
        return False
    return user

async def oauth2_scheme(request: Request) -> Optional[str]:
    authorization: str = request.cookies.get(COOKIE_NAME)
    scheme, param = get_authorization_scheme_param(authorization)
    if not authorization or scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return param

def create_access_token(data: Dict) -> str:
    to_encode = data.copy()
    expire = dt.datetime.utcnow() + dt.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials."
    )
    token = token.removeprefix("Bearer").strip()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("username")
        if username is None:
            raise credentials_exception
    except JWTError as e:
        console.log(f"[red]JWT Error: {e}")
        raise credentials_exception
    return {"username": username}

async def get_current_user_from_token(token: str = Depends(oauth2_scheme), conn=Depends(get_db_connection)) -> dict:
    user_data = decode_token(token)
    db_user = await get_user(user_data["username"], conn)
    if not db_user:
        raise HTTPException(status_code=401, detail="User not found")
    return db_user

async def get_current_user_from_cookie(request: Request, conn=Depends(get_db_connection)) -> Optional[dict]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    user_data = decode_token(token)
    return await get_user(user_data["username"], conn)

async def login_for_access_token(response: Response, username: str, password: str, conn=Depends(get_db_connection)) -> Dict[str, str]:
    user = await authenticate_user(username, password, conn)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = create_access_token(data={"username": user["username"]})
    response.set_cookie(
        key=COOKIE_NAME,
        value=f"Bearer {access_token}",
        httponly=True
    )
    return {COOKIE_NAME: access_token, "token_type": "bearer"}