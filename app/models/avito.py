import json
import httpx
from fastapi import HTTPException
from ..config import AVITO_TOKEN_URL, AVITO_API_URL, AVITO_CLIENT_ID, AVITO_CLIENT_SECRET
from ..database import get_db_connection
from ..models.deepseek import query_deepseek

async def get_avito_token(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            AVITO_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": AVITO_CLIENT_ID,
                "client_secret": AVITO_CLIENT_SECRET
            }
        )
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Ошибка получения токена Avito")
        return response.json()

async def refresh_avito_token(refresh_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            AVITO_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": AVITO_CLIENT_ID,
                "client_secret": AVITO_CLIENT_SECRET
            }
        )
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Ошибка обновления токена Avito")
        return response.json()

async def fetch_avito_items(access_token: str, bot_id: int, user_id: str, conn) -> list:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{AVITO_API_URL}/items",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Ошибка получения объявлений Avito")
        return response.json().get("items", [])

async def process_avito_message(bot_id: int, message: dict, conn, user: dict):
    bot = await conn.fetchrow("SELECT * FROM bots WHERE id = $1 AND user_id = $2", bot_id, user["id"])
    if not bot:
        raise HTTPException(status_code=404, detail="Бот не найден")
    
    previous_messages = await conn.fetch(
        "SELECT text, response FROM messages WHERE bot_id = $1 AND is_test = FALSE ORDER BY timestamp ASC",
        bot_id
    )
    
    def enhance_prompt(bot: dict) -> str:
        parameters = json.loads(bot["parameters"])
        actions = json.loads(bot["actions"])
        
        parameters_text = "\n".join(f"[{p['name']}] [{p['description']}]" for p in parameters) if parameters else ""
        actions_text = "\n".join(f"[{a['name']}] [{a['description']}]" for a in actions) if actions else ""
        
        return f"""{bot["prompt"]}
    
    В процессе диалога ты должен собрать следующие данные (список параметров):
    {parameters_text}
    В каждом ответе обновляй/дополняй данные.
    
    В процессе диалога ты должен совершать действия для каждого твоего ответа, если это уместно на данном этапе диалога:
    {actions_text}
    
    Отвечай в формате JSON, который будет иметь такую структуру:
    {{
      "response": "string(твой ответ пользователю)",
      "actions": [{{"action": "string(название действия из списка твоих действий)", "value": "string(параметры действия)"}}, {{"action": "string()", "value": "string()"}}],
      "parameters": [{{"parameter": "string()", "value": "string()"}}, {{"parameter": "string(название параметра из списка параметров)", "value": "string(значение параметра)"}}]
    }}"""
    
    enhanced_prompt = enhance_prompt(bot)
    response = await query_deepseek(enhanced_prompt, message["text"], previous_messages, conn, user["telegram_id"])
    
    await conn.execute(
        """
        INSERT INTO messages (bot_id, text, response, status, is_test, timestamp)
        VALUES ($1, $2, $3, $4, FALSE, NOW())
        """,
        bot_id, message["text"], json.dumps(response, ensure_ascii=False), response.get("status", "Обработано")
    )
    
    return response