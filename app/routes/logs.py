from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from ..templates_config import templates
from ..auth import get_current_user_from_token
from ..database import get_db_connection

router = APIRouter()

@router.get("/{bot_id}", response_class=HTMLResponse)
async def logs_page(
    bot_id: int, request: Request, user: dict = Depends(get_current_user_from_token), conn=Depends(get_db_connection)
):
    bot = await conn.fetchrow("SELECT * FROM bots WHERE id = $1 AND user_id = $2", bot_id, user["id"])
    if not bot:
        raise HTTPException(status_code=404, detail="Бот не найден")
    messages = await conn.fetch("SELECT * FROM messages WHERE bot_id = $1 ORDER BY timestamp DESC", bot_id)
    return templates.TemplateResponse("logs.html", {"request": request, "user": user, "bot": bot, "messages": messages})