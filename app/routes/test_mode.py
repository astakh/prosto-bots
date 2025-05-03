from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from ..auth import get_current_user_from_token
from ..database import get_db_connection
from ..models.deepseek import query_deepseek
from ..templates_config import templates
import datetime as dt
import json

router = APIRouter()

@router.get("/{bot_id}", response_class=HTMLResponse)
async def test_mode_page(
    bot_id: int, request: Request, user: dict = Depends(get_current_user_from_token), conn=Depends(get_db_connection)
):
    bot = await conn.fetchrow("SELECT * FROM bots WHERE id = $1 AND user_id = $2", bot_id, user["id"])
    if not bot:
        raise HTTPException(status_code=404, detail="Бот не найден")
    messages = await conn.fetch(
        "SELECT * FROM messages WHERE bot_id = $1 AND is_test = TRUE ORDER BY timestamp DESC", bot_id
    )
    return templates.TemplateResponse(
        "test_mode.html", {"request": request, "user": user, "bot": bot, "messages": messages}
    )

@router.post("/{bot_id}/send", response_class=RedirectResponse)
async def send_test_message(
    bot_id: int,
    message: str = Form(...),
    user: dict = Depends(get_current_user_from_token),
    conn=Depends(get_db_connection),
):
    bot = await conn.fetchrow("SELECT * FROM bots WHERE id = $1 AND user_id = $2", bot_id, user["id"])
    if not bot:
        raise HTTPException(status_code=404, detail="Бот не найден")

    previous_messages = await conn.fetch(
        "SELECT text, response FROM messages WHERE bot_id = $1 AND is_test = TRUE ORDER BY timestamp DESC", bot_id
    )

    def enhance_prompt(prompt: str, parameters: str, actions: str):
        param_list = json.loads(parameters) if parameters else []
        action_list = json.loads(actions) if actions else []
        enhanced = (
            f"{prompt}\n\n"
            f"Доступные параметры: {', '.join([p['name'] for p in param_list])}\n"
            f"Доступные действия: {', '.join([a['name'] for a in action_list])}\n"
            "Отвечай строго в формате JSON с полями: response (строка), actions (массив объектов), parameters (массив объектов), status (строка)."
        )
        return enhanced

    prompt = enhance_prompt(bot["prompt"], bot["parameters"], bot["actions"])
    response = await query_deepseek(
        prompt=prompt,
        message=message,
        previous_messages=previous_messages,
        conn=conn,
        telegram_id=user["telegram_id"],
    )

    await conn.execute(
        """
        INSERT INTO messages (bot_id, text, response, status, is_test, timestamp)
        VALUES ($1, $2, $3, $4, TRUE, NOW())
        """,
        bot_id,
        message,
        json.dumps(response, ensure_ascii=False),
        response.get("status", "Обработано"),
    )

    await conn.execute(
        "INSERT INTO notifications (telegram_id, text, status, created_at) VALUES ($1, $2, 'pending', NOW())",
        user["telegram_id"],
        f"Тестовое сообщение для бота #{bot_id} обработано.",
    )

    return RedirectResponse(url=f"/test/{bot_id}", status_code=303)

@router.post("/{bot_id}/reset", response_class=RedirectResponse)
async def reset_test_messages(
    bot_id: int, user: dict = Depends(get_current_user_from_token), conn=Depends(get_db_connection)
):
    bot = await conn.fetchrow("SELECT * FROM bots WHERE id = $1 AND user_id = $2", bot_id, user["id"])
    if not bot:
        raise HTTPException(status_code=404, detail="Бот не найден")

    await conn.execute("DELETE FROM messages WHERE bot_id = $1 AND is_test = TRUE", bot_id)

    await conn.execute(
        "INSERT INTO notifications (telegram_id, text, status, created_at) VALUES ($1, $2, 'pending', NOW())",
        user["telegram_id"],
        f"Тестовый диалог для бота #{bot_id} сброшен.",
    )

    return RedirectResponse(url=f"/test/{bot_id}", status_code=303)