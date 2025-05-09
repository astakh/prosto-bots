# oauth_avito_callback.py

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from ..config import AVITO_REDIRECT_URI
from ..auth import get_current_user_from_token
from ..database import get_db_connection
from ..models.avito import get_avito_token
from ..utils import send_notification
from rich.console import Console
import datetime as dt

router = APIRouter(prefix="/oauth", tags=["oauth"])
console = Console()

@router.get("/avito/callback")
async def avito_callback(code: str, state: str, user: dict = Depends(get_current_user_from_token), conn=Depends(get_db_connection)):
    try:
        # Проверка state
        try:
            bot_id = int(state)
        except ValueError:
            console.log(f"[red]Invalid state value: {state}")
            raise HTTPException(status_code=400, detail="Неверный параметр state")

        # Проверка существования бота
        bot = await conn.fetchrow("SELECT * FROM bots WHERE id = $1 AND user_id = $2", bot_id, user["id"])
        if not bot:
            console.log(f"[red]Bot #{bot_id} not found for user #{user['id']}")
            raise HTTPException(status_code=404, detail="Бот не найден")

        # Проверка существующих токенов
        existing_token = await conn.fetchrow(
            "SELECT * FROM tokens WHERE access_token IN (SELECT access_token FROM tokens WHERE bot_id != $1)",
            bot_id
        )
        if existing_token:
            await conn.execute("UPDATE bots SET status = 'stopped' WHERE id = $1", existing_token["bot_id"])
            await send_notification(
                user["telegram_id"],
                f"Аккаунт Avito переключен на бота #{bot_id}. Предыдущий бот #{existing_token['bot_id']} остановлен.",
                conn
            )

        # Получение токена
        token_data = await get_avito_token(code, bot_id)
        if not all(key in token_data for key in ["access_token", "expires_in"]):
            console.log(f"[red]Invalid token data from Avito: {token_data}")
            raise HTTPException(status_code=400, detail="Неверный ответ от Avito API")

        expires_at = dt.datetime.utcnow() + dt.timedelta(seconds=token_data["expires_in"])
        await conn.execute(
            """
            INSERT INTO tokens (bot_id, access_token, refresh_token, expires_at, scope)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (bot_id) DO UPDATE SET access_token = $2, refresh_token = $3, expires_at = $4, scope = $5
            """,
            bot_id, token_data["access_token"], token_data.get("refresh_token"), expires_at, token_data.get("scope", "messenger:read,messenger:write,items:info")
        )
        await conn.execute("UPDATE bots SET is_authorized = TRUE WHERE id = $1", bot_id)
        await send_notification(user["telegram_id"], f"Аккаунт Avito подключен к bоту #{bot_id}.", conn)
        console.log(f"[green]Successfully authorized bot #{bot_id}")
        return RedirectResponse(url=f"/oauth/avito/select-items/{bot_id}", status_code=303)

    except HTTPException as e:
        console.log(f"[red]HTTPException in avito_callback: {str(e)}")
        raise
    except Exception as e:
        console.log(f"[red]Error in avito_callback: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")