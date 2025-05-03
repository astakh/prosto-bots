from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from ..templates_config import templates
from ..auth import get_current_user_from_token
from ..database import get_db_connection
from ..models.avito import get_avito_token, fetch_avito_items
from ..config import AVITO_AUTH_URL, AVITO_CLIENT_ID, AVITO_REDIRECT_URI
import datetime as dt

router = APIRouter()

async def send_notification(telegram_id: str, text: str, conn):
    await conn.execute(
        "INSERT INTO notifications (telegram_id, text, status, created_at) VALUES ($1, $2, 'pending', NOW())",
        telegram_id, text
    )

@router.get("/avito", response_class=RedirectResponse)
async def avito_auth(bot_id: int, user: dict = Depends(get_current_user_from_token), conn=Depends(get_db_connection)):
    bot = await conn.fetchrow("SELECT * FROM bots WHERE id = $1 AND user_id = $2", bot_id, user["id"])
    if not bot:
        raise HTTPException(status_code=404, detail="Бот не найден")
    auth_url = f"{AVITO_AUTH_URL}?client_id={AVITO_CLIENT_ID}&redirect_uri={AVITO_REDIRECT_URI}&response_type=code&state={bot_id}"
    return RedirectResponse(url=auth_url)

@router.get("/avito/callback")
async def avito_callback(code: str, state: str, user: dict = Depends(get_current_user_from_token), conn=Depends(get_db_connection)):
    bot_id = int(state)
    bot = await conn.fetchrow("SELECT * FROM bots WHERE id = $1 AND user_id = $2", bot_id, user["id"])
    if not bot:
        raise HTTPException(status_code=404, detail="Бот не найден")
    
    existing_token = await conn.fetchrow("SELECT * FROM tokens WHERE access_token IN (SELECT access_token FROM tokens WHERE bot_id != $1)", bot_id)
    if existing_token:
        await conn.execute("UPDATE bots SET status = 'stopped' WHERE id = $1", existing_token["bot_id"])
        await send_notification(user["telegram_id"], f"Аккаунт Avito переключен на бота #{bot_id}. Предыдущий бот #{existing_token['bot_id']} остановлен.", conn)
    
    token_data = await get_avito_token(code)
    expires_at = dt.datetime.utcnow() + dt.timedelta(seconds=token_data["expires_in"])
    await conn.execute(
        """
        INSERT INTO tokens (bot_id, access_token, refresh_token, expires_at)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (bot_id) DO UPDATE SET access_token = $2, refresh_token = $3, expires_at = $4
        """,
        bot_id, token_data["access_token"], token_data.get("refresh_token"), expires_at
    )
    await conn.execute("UPDATE bots SET is_authorized = TRUE WHERE id = $1", bot_id)
    await send_notification(user["telegram_id"], f"Аккаунт Avito подключен к боту #{bot_id}.", conn)
    return RedirectResponse(url=f"/oauth/avito/select-items/{bot_id}", status_code=303)

@router.get("/avito/select-items/{bot_id}", response_class=HTMLResponse)
async def select_items_page(
    bot_id: int,
    request: Request,
    user: dict = Depends(get_current_user_from_token),
    conn=Depends(get_db_connection)
):
    bot = await conn.fetchrow("SELECT * FROM bots WHERE id = $1 AND user_id = $2", bot_id, user["id"])
    if not bot:
        raise HTTPException(status_code=404, detail="Бот не найден")
    
    if not bot["is_authorized"]:
        raise HTTPException(status_code=400, detail="Аккаунт Avito не привязан")
    
    token = await conn.fetchrow("SELECT access_token FROM tokens WHERE bot_id = $1", bot_id)
    if not token:
        raise HTTPException(status_code=400, detail="Аккаунт Avito не привязан")
    
    try:
        items = await fetch_avito_items(token["access_token"], bot_id, user["id"], conn)
    except HTTPException as e:
        await send_notification(user["telegram_id"], f"Ошибка получения объявлений для бота #{bot_id}: {e.detail}", conn)
        return templates.TemplateResponse(
            "select_items.html",
            {"request": request, "user": user, "bot": bot, "items": [], "errors": [e.detail]}
        )
    
    return templates.TemplateResponse(
        "select_items.html",
        {"request": request, "user": user, "bot": bot, "items": items, "errors": []}
    )

@router.post("/avito/select-items/{bot_id}", response_class=RedirectResponse)
async def save_selected_items(
    bot_id: int,
    item_ids: list[str] = Form(default=[]),
    user: dict = Depends(get_current_user_from_token),
    conn=Depends(get_db_connection)
):
    bot = await conn.fetchrow("SELECT * FROM bots WHERE id = $1 AND user_id = $2", bot_id, user["id"])
    if not bot:
        raise HTTPException(status_code=404, detail="Бот не найден")
    
    if not bot["is_authorized"]:
        raise HTTPException(status_code=400, detail="Аккаунт Avito не привязан")
    
    token = await conn.fetchrow("SELECT access_token FROM tokens WHERE bot_id = $1", bot_id)
    if not token:
        raise HTTPException(status_code=400, detail="Аккаунт Avito не привязан")
    
    try:
        items = await fetch_avito_items(token["access_token"], bot_id, user["id"], conn)
        if not items:
            items_data = {"all": True}
        else:
            items_data = {"all": False, "items": item_ids}
        
        await conn.execute(
            "UPDATE bots SET items = $1 WHERE id = $2",
            items_data, bot_id
        )
    except HTTPException as e:
        await send_notification(user["telegram_id"], f"Ошибка сохранения объявлений для бота #{bot_id}: {e.detail}", conn)
        return RedirectResponse(url="/bots", status_code=303)
    
    return RedirectResponse(url="/bots", status_code=303)