# bots_activate.py

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from ..auth import get_current_user_from_token
from ..database import get_db_connection
from ..config import SERVICE_CONFIG
from ..utils import send_notification
from rich.console import Console
import datetime as dt

router = APIRouter()
console = Console()

@router.post("/{bot_id}/activate", response_class=RedirectResponse)
async def activate_bot(
    bot_id: int, user: dict = Depends(get_current_user_from_token), conn=Depends(get_db_connection)
):
    try:
        bot = await conn.fetchrow("SELECT * FROM bots WHERE id = $1 AND user_id = $2", bot_id, user["id"])
        if not bot:
            console.log(f"[red]Бот #{bot_id} не найден для пользователя #{user['id']}")
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
        console.log(f"[green]Бот #{bot_id} активирован")
        return RedirectResponse(url="/bots", status_code=303)
    except HTTPException as e:
        raise
    except Exception as e:
        console.log(f"[red]Ошибка в activate_bot: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")