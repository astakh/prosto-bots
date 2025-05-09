# bots_edit.py

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from ..templates_config import templates
from ..auth import get_current_user_from_token
from ..database import get_db_connection
from rich.console import Console

router = APIRouter()
console = Console()

@router.get("/{bot_id}/edit", response_class=HTMLResponse)
async def edit_bot_page(
    bot_id: int, request: Request, user: dict = Depends(get_current_user_from_token), conn=Depends(get_db_connection)
):
    try:
        bot = await conn.fetchrow("SELECT * FROM bots WHERE id = $1 AND user_id = $2", bot_id, user["id"])
        if not bot:
            console.log(f"[red]Бот #{bot_id} не найден для пользователя #{user['id']}")
            raise HTTPException(status_code=404, detail="Бот не найден")
        console.log(f"[green]Отображение страницы редактирования для бота #{bot_id}")
        return templates.TemplateResponse("edit_prompt.html", {"request": request, "user": user, "bot": bot, "errors": []})
    except Exception as e:
        console.log(f"[red]Ошибка в edit_bot_page: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")