from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from ..templates_config import templates
from ..auth import get_current_user_from_token
from ..database import get_db_connection
from ..models.avito import fetch_avito_items
from ..config import SERVICE_CONFIG
import datetime as dt
import json
import re

router = APIRouter()

async def send_notification(telegram_id: str, text: str, conn):
    await conn.execute(
        "INSERT INTO notifications (telegram_id, text, status, created_at) VALUES ($1, $2, 'pending', NOW())",
        telegram_id, text
    )

def validate_format(text: str, field_name: str) -> list:
    if not text.strip():
        return []
    lines = text.strip().split("\n")
    result = []
    pattern = r"^\[([^\]]+)\]\s+\[(.+)\]$"
    for line in lines:
        match = re.match(pattern, line.strip())
        if not match:
            raise HTTPException(status_code=400, detail=f"Неверный формат строки в {field_name}: {line}")
        name, description = match.groups()
        result.append({"name": name, "description": description})
    return result

@router.get("/", response_class=HTMLResponse)
async def bots_page(request: Request, user: dict = Depends(get_current_user_from_token), conn=Depends(get_db_connection)):
    bots = await conn.fetch("SELECT b.*, t.access_token FROM bots b LEFT JOIN tokens t ON b.id = t.bot_id WHERE b.user_id = $1", user["id"])
    trial_active = user["trial_end_date"] > dt.datetime.utcnow()
    return templates.TemplateResponse("bots.html", {"request": request, "user": user, "bots": bots, "trial_active": trial_active})

@router.post("/create", response_class=RedirectResponse)
async def create_bot(
    request: Request,
    prompt: str = Form(...),
    parameters: str = Form(default=""),
    actions: str = Form(default=""),
    user: dict = Depends(get_current_user_from_token),
    conn=Depends(get_db_connection)
):
    bot_count = await conn.fetchval("SELECT COUNT(*) FROM bots WHERE user_id = $1", user["id"])
    trial_active = user["trial_end_date"] > dt.datetime.utcnow()
    
    if bot_count >= 1 and not trial_active and user["balance"] < SERVICE_CONFIG["bot_daily_cost"]:
        await send_notification(user["telegram_id"], "Недостаточно средств для создания бота. Пополните баланс.", conn)
        raise HTTPException(status_code=400, detail="Недостаточно средств")
    
    try:
        parameters_json = validate_format(parameters, "parameters")
        actions_json = validate_format(actions, "actions")
    except HTTPException as e:
        raise e
    
    await conn.execute(
        """
        INSERT INTO bots (user_id, prompt, status, items, is_authorized, parameters, actions)
        VALUES ($1, $2, 'stopped', NULL, FALSE, $3, $4)
        """,
        user["id"], prompt, json.dumps(parameters_json), json.dumps(actions_json)
    )
    bot_id = await conn.fetchval("SELECT id FROM bots WHERE user_id = $1 ORDER BY ID DESC LIMIT 1", user["id"])
    await send_notification(user["telegram_id"], f"Бот #{bot_id} создан!", conn)
    return RedirectResponse(url="/bots", status_code=303)

@router.get("/{bot_id}/edit", response_class=HTMLResponse)
async def edit_bot_page(
    bot_id: int, request: Request, user: dict = Depends(get_current_user_from_token), conn=Depends(get_db_connection)
):
    bot = await conn.fetchrow("SELECT * FROM bots WHERE id = $1 AND user_id = $2", bot_id, user["id"])
    if not bot:
        raise HTTPException(status_code=404, detail="Бот не найден")
    return templates.TemplateResponse("edit_prompt.html", {"request": request, "user": user, "bot": bot, "errors": []})

@router.post("/{bot_id}/update", response_class=RedirectResponse)
async def update_bot(
    bot_id: int,
    prompt: str = Form(...),
    parameters: str = Form(default=""),
    actions: str = Form(default=""),
    user: dict = Depends(get_current_user_from_token),
    conn=Depends(get_db_connection)
):
    bot = await conn.fetchrow("SELECT * FROM bots WHERE id = $1 AND user_id = $2", bot_id, user["id"])
    if not bot:
        raise HTTPException(status_code=404, detail="Бот не найден")
    
    try:
        parameters_json = validate_format(parameters, "parameters")
        actions_json = validate_format(actions, "actions")
    except HTTPException as e:
        raise e
    
    await conn.execute(
        "UPDATE bots SET prompt = $1, parameters = $2, actions = $3 WHERE id = $4",
        prompt, json.dumps(parameters_json), json.dumps(actions_json), bot_id
    )
    await send_notification(user["telegram_id"], f"Промпт бота #{bot_id} обновлен.", conn)
    return RedirectResponse(url="/bots", status_code=303)

@router.post("/{bot_id}/activate", response_class=RedirectResponse)
async def activate_bot(
    bot_id: int, user: dict = Depends(get_current_user_from_token), conn=Depends(get_db_connection)
):
    bot = await conn.fetchrow("SELECT * FROM bots WHERE id = $1 AND user_id = $2", bot_id, user["id"])
    if not bot:
        raise HTTPException(status_code=404, detail="Бот не найден")
    
    if not bot["is_authorized"]:
        await send_notification(user["telegram_id"], f"Бот #{bot_id} не может быть активирован: привяжите аккаунт Avito.", conn)
        raise HTTPException(status_code=400, detail="Привяжите аккаунт Avito")
    
    if bot["items"] is None:
        await send_notification(user["telegram_id"], f"Бот #{bot_id} не может быть активирован: выберите объявления.", conn)
        raise HTTPException(status_code=400, detail="Выберите объявления")
    
    trial_active = user["trial_end_date"] > dt.datetime.utcnow()
    if not trial_active and user["balance"] < SERVICE_CONFIG["bot_daily_cost"]:
        await send_notification(user["telegram_id"], f"Недостаточно средств для активации бота #{bot_id}. Пополните баланс.", conn)
        raise HTTPException(status_code=400, detail="Недостаточно средств")
    
    await conn.execute("UPDATE bots SET status = 'active' WHERE id = $1", bot_id)
    await send_notification(user["telegram_id"], f"Бот #{bot_id} активирован!", conn)
    return RedirectResponse(url="/bots", status_code=303)

@router.post("/{bot_id}/stop", response_class=RedirectResponse)
async def stop_bot(
    bot_id: int, user: dict = Depends(get_current_user_from_token), conn=Depends(get_db_connection)
):
    bot = await conn.fetchrow("SELECT * FROM bots WHERE id = $1 AND user_id = $2", bot_id, user["id"])
    if not bot:
        raise HTTPException(status_code=404, detail="Бот не найден")
    await conn.execute("UPDATE bots SET status = 'stopped' WHERE id = $1", bot_id)
    await send_notification(user["telegram_id"], f"Бот #{bot_id} остановлен.", conn)
    return RedirectResponse(url="/bots", status_code=303)

@router.post("/{bot_id}/delete", response_class=RedirectResponse)
async def delete_bot(
    bot_id: int, user: dict = Depends(get_current_user_from_token), conn=Depends(get_db_connection)
):
    bot = await conn.fetchrow("SELECT * FROM bots WHERE id = $1 AND user_id = $2", bot_id, user["id"])
    if not bot:
        raise HTTPException(status_code=404, detail="Бот не найден")
    
    await conn.execute("DELETE FROM tokens WHERE bot_id = $1", bot_id)
    await conn.execute("DELETE FROM messages WHERE bot_id = $1", bot_id)
    await conn.execute("DELETE FROM notifications WHERE telegram_id = $1 AND text LIKE $2", user["telegram_id"], f"%Бот #{bot_id}%")
    await conn.execute("DELETE FROM bots WHERE id = $1", bot_id)
    
    await send_notification(user["telegram_id"], f"Бот #{bot_id} удален.", conn)
    return RedirectResponse(url="/bots", status_code=303)

@router.get("/{bot_id}/edit-items", response_class=HTMLResponse)
async def edit_items_page(
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

@router.get("/order-prompt", response_class=HTMLResponse)
async def order_prompt_page(request: Request, user: dict = Depends(get_current_user_from_token)):
    return templates.TemplateResponse("order_prompt.html", {"request": request, "user": user})

@router.get("/balance", response_class=HTMLResponse)
async def balance_page(request: Request, user: dict = Depends(get_current_user_from_token)):
    return templates.TemplateResponse("balance.html", {"request": request, "user": user, "SERVICE_CONFIG": SERVICE_CONFIG})

@router.get("/top-up", response_class=HTMLResponse)
async def top_up_page(request: Request, user: dict = Depends(get_current_user_from_token)):
    return templates.TemplateResponse("top_up.html", {"request": request, "user": user})