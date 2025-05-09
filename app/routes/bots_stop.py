# bots_stop.py

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from ..auth import get_current_user_from_token
from ..database import get_db_connection
from ..utils import send_notification
from rich.console import Console

router = APIRouter()
console = Console()

@router.post("/{bot_id}/stop", response_class=RedirectResponse)
async def stop_bot(
    bot_id: int, user: dict = Depends(get_current_user_from_token), conn=Depends(get_db_connection)
):
    try:
        bot = await conn.fetchrow("SELECT * FROM bots WHERE id = $1 AND user_id = $2", bot_id, user["id"])
        if not bot:
            console.log(f"[red]Бот #{bot_id} не найден для пользователя #{user['id']}")
            raise HTTPException(status_code=404, detail="Бот не найден")
        await conn.execute("UPDATE bots SET status = 'stopped' WHERE id = $1", bot_id)
        await send_notification(user["telegram_id"], f"Бот #{bot_id} остановлен.", conn)
        console.log(f"[green]Бот #{bot_id} остановлен")
        return RedirectResponse(url="/bots", status_code=303)
    except Exception as e:
        console.log(f"[red]Ошибка в stop_bot: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")