# bots_index.py

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from ..templates_config import templates
from ..auth import get_current_user_from_token
from ..database import get_db_connection
from rich.console import Console
import datetime as dt

router = APIRouter()
console = Console()

@router.get("/", response_class=HTMLResponse)
async def bots_page(request: Request, user: dict = Depends(get_current_user_from_token), conn=Depends(get_db_connection)):
    try:
        bots = await conn.fetch("SELECT b.*, t.access_token FROM bots b LEFT JOIN tokens t ON b.id = t.bot_id WHERE b.user_id = $1", user["id"])
        trial_active = user["trial_end_date"] > dt.datetime.utcnow()
        console.log(f"[green]Fetched {len(bots)} bots for user #{user['id']}")
        return templates.TemplateResponse("bots.html", {"request": request, "user": user, "bots": bots, "trial_active": trial_active})
    except Exception as e:
        console.log(f"[red]Error in bots_page: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
