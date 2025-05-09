# oauth_avito.py

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from ..config import AVITO_AUTH_URL, AVITO_CLIENT_ID, AVITO_REDIRECT_URI
from ..auth import get_current_user_from_token
from ..database import get_db_connection
from rich.console import Console

router = APIRouter(prefix="/oauth", tags=["oauth"])
console = Console()

@router.get("/avito", response_class=RedirectResponse)
async def avito_auth(bot_id: int, user: dict = Depends(get_current_user_from_token), conn=Depends(get_db_connection)):
    try:
        bot = await conn.fetchrow("SELECT * FROM bots WHERE id = $1 AND user_id = $2", bot_id, user["id"])
        if not bot:
            console.log(f"[red]Bot #{bot_id} not found for user #{user['id']}")
            raise HTTPException(status_code=404, detail="Бот не найден")
        auth_url = f"{AVITO_AUTH_URL}?client_id={AVITO_CLIENT_ID}&redirect_uri={AVITO_REDIRECT_URI}&response_type=code&state={bot_id}&scope=messenger:read,messenger:write,items:info"
        console.log(f"[green]Redirecting to Avito auth for bot #{bot_id}")
        return RedirectResponse(url=auth_url)
    except Exception as e:
        console.log(f"[red]Error in avito_auth: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")