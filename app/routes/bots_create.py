# bots_create.py

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from ..templates_config import templates
from ..auth import get_current_user_from_token
from ..database import get_db_connection
from ..config import SERVICE_CONFIG
from ..utils import send_notification, validate_format
from rich.console import Console
import json
import datetime as dt

router = APIRouter()
console = Console()

@router.post("/create", response_class=RedirectResponse)
async def create_bot(
    request: Request,
    prompt: str = Form(...),
    parameters: str = Form(default=""),
    actions: str = Form(default=""),
    user: dict = Depends(get_current_user_from_token),
    conn=Depends(get_db_connection)
):
    try:
        bot_count = await conn.fetchval("SELECT COUNT(*) FROM bots WHERE user_id = $1", user["id"])
        trial_active = user["trial_end_date"] > dt.datetime.utcnow()
        
        if bot_count >= 1 and not trial_active and user["balance"] < SERVICE_CONFIG["bot_daily_cost"]:
            await send_notification(user["telegram_id"], "Недостаточно средств для создания бота. Пополните баланс.", conn)
            raise HTTPException(status_code=400, detail="Недостаточно средств")
        
        parameters_json = validate_format(parameters, "parameters")
        actions_json = validate_format(actions, "actions")
        
        await conn.execute(
            """
            INSERT INTO bots (user_id, prompt, status, items, is_authorized, parameters, actions)
            VALUES ($1, $2, 'stopped', NULL, FALSE, $3, $4)
            """,
            user["id"], prompt, json.dumps(parameters_json), json.dumps(actions_json)
        )
        bot_id = await conn.fetchval("SELECT id FROM bots WHERE user_id = $1 ORDER BY ID DESC LIMIT 1", user["id"])
        await send_notification(user["telegram_id"], f"Бот #{bot_id} создан!", conn)
        console.log(f"[green]Bot #{bot_id} создан для пользователя #{user['id']}")
        return RedirectResponse(url="/bots", status_code=303)
    except HTTPException as e:
        raise
    except Exception as e:
        console.log(f"[red]Ошибка в create_bot: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")