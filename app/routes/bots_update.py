# bots_update.py

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from ..auth import get_current_user_from_token
from ..database import get_db_connection
from ..utils import send_notification, validate_format
from rich.console import Console
import json

router = APIRouter()
console = Console()

@router.post("/{bot_id}/update", response_class=RedirectResponse)
async def update_bot(
    bot_id: int,
    prompt: str = Form(...),
    parameters: str = Form(default=""),
    actions: str = Form(default=""),
    user: dict = Depends(get_current_user_from_token),
    conn=Depends(get_db_connection)
):
    try:
        bot = await conn.fetchrow("SELECT * FROM bots WHERE id = $1 AND user_id = $2", bot_id, user["id"])
        if not bot:
            console.log(f"[red]Бот #{bot_id} не найден для пользователя #{user['id']}")
            raise HTTPException(status_code=404, detail="Бот не найден")
        
        parameters_json = validate_format(parameters, "parameters")
        actions_json = validate_format(actions, "actions")
        
        await conn.execute(
            "UPDATE bots SET prompt = $1, parameters = $2, actions = $3 WHERE id = $4",
            prompt, json.dumps(parameters_json), json.dumps(actions_json), bot_id
        )
        await send_notification(user["telegram_id"], f"Промпт бота #{bot_id} обновлен.", conn)
        console.log(f"[green]Бот #{bot_id} обновлен")
        return RedirectResponse(url="/bots", status_code=303)
    except HTTPException as e:
        raise
    except Exception as e:
        console.log(f"[red]Ошибка в update_bot: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")