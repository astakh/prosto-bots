import json
from openai import OpenAI
from ..config import DS_API_KEY, DS_API_URL
from rich.console import Console

console = Console()

async def query_deepseek(prompt: str, message: str, previous_messages: list, conn, telegram_id: str) -> dict:
    client = OpenAI(api_key=DS_API_KEY, base_url=DS_API_URL)
    
    # Формируем историю сообщений
    messages = [{"role": "system", "content": prompt}]
    for msg in previous_messages:
        messages.append({"role": "user", "content": msg["text"]})
        if msg["response"]:
            try:
                json_response = json.loads(msg["response"])
                messages.append({"role": "assistant", "content": json.dumps(json_response, ensure_ascii=False)})
            except json.JSONDecodeError:
                messages.append({"role": "assistant", "content": msg["response"]})
    
    # Добавляем текущее сообщение
    messages.append({"role": "user", "content": message})
    
    for _ in range(2):
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                stream=False,
                response_format={'type': 'json_object'},
                temperature=1.0
            )
            raw_answer = response.choices[0].message.content
            json_response = json.loads(raw_answer)
            
            # Проверяем наличие обязательных полей
            if not all(key in json_response for key in ["response", "actions", "parameters"]):
                console.log(f"[red]Invalid JSON format: {raw_answer}")
                continue
            
            # Выполняем действия
            for action in json_response.get("actions", []):
                if action.get("action") == "уведомить":
                    await conn.execute(
                        "INSERT INTO notifications (telegram_id, text, status, created_at) VALUES ($1, $2, 'pending', NOW())",
                        telegram_id,
                        action.get("value")
                    )
                    console.log(f"[green]Notification added: {action.get('value')}")
            
            return json_response
        except json.JSONDecodeError as e:
            console.log(f"[red]JSON Parse Error: {e}, raw: {raw_answer}")
        except Exception as e:
            console.log(f"[red]DeepSeek Error: {e}")
    
    return {
        "response": "Свяжемся позже",
        "actions": [],
        "parameters": [],
        "status": "Требуется ручная обработка"
    }