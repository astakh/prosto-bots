import json
import httpx
from fastapi import HTTPException
from ..config import AVITO_TOKEN_URL, AVITO_API_URL, AVITO_CLIENT_ID, AVITO_CLIENT_SECRET, AVITO_API_URL_ITEMS, AVITO_WEBHOOK_URL
from ..database import get_db_connection
from ..models.deepseek import query_deepseek
import datetime as dt
from rich.console import Console

console = Console()

async def get_avito_token(code: str, bot_id: int) -> dict:
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
            console.log(f"[red]Ошибка получения токена Avito: {response.status_code}, {response.text}")
            raise HTTPException(status_code=400, detail="Ошибка получения токена Avito")
        
        token_data = response.json()
        # Save token to database
        async with get_db_connection() as conn:
            expires_at = dt.datetime.utcnow() + dt.timedelta(seconds=token_data["expires_in"])
            await conn.execute(
                """
                INSERT INTO tokens (bot_id, access_token, refresh_token, expires_at, scope)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (bot_id) DO UPDATE
                SET access_token = $2, refresh_token = $3, expires_at = $4, scope = $5
                """,
                bot_id, token_data["access_token"], token_data.get("refresh_token"), expires_at, token_data.get("scope")
            )
            # Subscribe to webhooks
            await subscribe_avito_webhook(bot_id, token_data["access_token"], token_data["user_id"])
        
        return token_data

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
            console.log(f"[red]Ошибка обновления токена Avito: {response.status_code}, {response.text}")
            raise HTTPException(status_code=400, detail="Ошибка обновления токена Avito")
        return response.json()

async def get_valid_token(bot_id: int, conn) -> str:
    token = await conn.fetchrow("SELECT * FROM tokens WHERE bot_id = $1", bot_id)
    if not token:
        raise HTTPException(status_code=400, detail="Токен для бота не найден")
    
    if token["expires_at"] < dt.datetime.utcnow():
        token_data = await refresh_avito_token(token["refresh_token"])
        expires_at = dt.datetime.utcnow() + dt.timedelta(seconds=token_data["expires_in"])
        await conn.execute(
            """
            UPDATE tokens 
            SET access_token = $1, refresh_token = $2, expires_at = $3
            WHERE bot_id = $4
            """,
            token_data["access_token"], token_data.get("refresh_token"), expires_at, bot_id
        )
        return token_data["access_token"]
    
    return token["access_token"]

async def subscribe_avito_webhook(bot_id: int, access_token: str, account_id: int):
    webhook_url = f"{AVITO_WEBHOOK_URL}/{account_id}"
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{AVITO_API_URL}/messenger/v3/webhook",
            json={"url": webhook_url},
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if response.status_code not in (200, 201):
            console.log(f"[red]Ошибка подписки на вебхук Avito для бота #{bot_id}: {response.status_code}, {response.text}")
            raise HTTPException(status_code=400, detail=f"Ошибка подписки на вебхук Avito: {response.status_code}")
        console.log(f"[green]Успешно подписан вебхук для бота #{bot_id} на URL: {webhook_url}")

async def fetch_avito_items(bot_id: int, user_id: str, conn) -> list:
    console.log("[yellow]go fetch_avito_items")
    access_token = await get_valid_token(bot_id, conn)
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{AVITO_API_URL_ITEMS}?per_page=50",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        console.log(f"[yellow]Avito API response: {response.status_code}, {response.text}")
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Ошибка получения объявлений Avito: {response.status_code}, {response.text}")
        items = response.json().get("resources", [])
        console.log(f"[green]Fetched {len(items)} items for bot #{bot_id}")
        return items

async def process_avito_message(bot_id: int, message: dict, conn, user: dict):
    bot = await conn.fetchrow("SELECT * FROM bots WHERE id = $1 AND user_id = $2", bot_id, user["id"])
    if not bot:
        raise HTTPException(status_code=404, detail="Бот не найден")
    
    previous_messages = await conn.fetch(
        "SELECT text, response FROM messages WHERE bot_id = $1 AND is_test = FALSE ORDER BY TIMESTAMP ASC",
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
        INSERT INTO messages (bot_id, text, response, status, is_test, TIMESTAMP, account_id)
        VALUES ($1, $2, $3, $4, FALSE, NOW(), $5)
        """,
        bot_id, message["text"], json.dumps(response, ensure_ascii=False), response.get("status", "Обработано"), message.get("user_id")
    )
    
    return response