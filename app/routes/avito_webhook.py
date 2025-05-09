# avito_webhook.py

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from ..database import get_db_connection
import json
from rich.console import Console

router = APIRouter(prefix="/avito", tags=["avito"])
console = Console()

class AvitoWebhookPayload(BaseModel):
    author_id: int
    chat_id: str
    chat_type: str
    content: dict
    created: int
    id: str
    item_id: int | None
    read: int | None
    type: str
    user_id: int

async def save_webhook_message(payload: AvitoWebhookPayload, account_id: int):
    async with get_db_connection() as conn:
        await conn.execute(
            """
            INSERT INTO messages (bot_id, text, response, status, is_test, timestamp, account_id)
            VALUES ($1, $2, $3, $4, FALSE, NOW(), $5)
            """,
            None,  # bot_id is NULL initially; will be mapped later
            payload.content.get("text", ""),  # Extract text from content
            json.dumps(dict(payload), ensure_ascii=False),  # Store full payload as response
            "Received",
            account_id
        )
        console.log(f"[green]Saved webhook message for account #{account_id}, message ID: {payload.id}")

@router.post("/webhook/{account_id}")
async def avito_webhook(account_id: int, payload: AvitoWebhookPayload, background_tasks: BackgroundTasks):
    try:
        # Save message asynchronously in the background
        background_tasks.add_task(save_webhook_message, payload, account_id)
        return JSONResponse(status_code=200, content={"ok": True})
    except Exception as e:
        console.log(f"[red]Ошибка обработки вебхука Avito для account #{account_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка обработки вебхука")