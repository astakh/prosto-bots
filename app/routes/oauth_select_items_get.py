# oauth_select_items_get.py 

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from ..templates_config import templates
from ..auth import get_current_user_from_token
from ..database import get_db_connection
from ..models.avito import fetch_avito_items
from ..utils import send_notification
from rich.console import Console

router = APIRouter(prefix="/oauth", tags=["oauth"])
console = Console()

@router.get("/avito/select-items/{bot_id}", response_class=HTMLResponse)
async def select_items_page(
    bot_id: int,
    request: Request,
    user: dict = Depends(get_current_user_from_token),
    conn=Depends(get_db_connection)
):
    try:
        bot = await conn.fetchrow("SELECT * FROM bots WHERE id = $1 AND user_id = $2", bot_id, user["id"])
        if not bot:
            console.log(f"[red]Bot #{bot_id} not found for user #{user['id']}")
            raise HTTPException(status_code=404, detail="Бот не найден")
        
        if not bot["is_authorized"]:
            console.log(f"[red]Bot #{bot_id} not authorized")
            raise HTTPException(status_code=400, detail="Аккаунт Avito не привязан")
        
        token = await conn.fetchrow("SELECT access_token FROM tokens WHERE bot_id = $1", bot_id)
        if not token:
            console.log(f"[red]No token found for bot #{bot_id}")
            raise HTTPException(status_code=400, detail="Аккаунт Avito не привязан")
        
        items = await fetch_avito_items(bot_id, user["id"], conn)
        return templates.TemplateResponse(
            "select_items.html",
            {"request": request, "user": user, "bot": bot, "items": items, "errors": []}
        )
    except HTTPException as e:
        console.log(f"[red]Error in select_items_page: {str(e)}")
        await send_notification(user["telegram_id"], f"Ошибка получения объявлений для бота #{bot_id}: {e.detail}", conn)
        return templates.TemplateResponse(
            "select_items.html",
            {"request": request, "user": user, "bot": bot, "items": [], "errors": [e.detail]}
        )
    except Exception as e:
        console.log(f"[red]Unexpected error in select_items_page: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")