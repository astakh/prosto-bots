from fastapi import HTTPException
from rich.console import Console
import re

console = Console()

async def send_notification(telegram_id: str, text: str, conn):
    try:
        await conn.execute(
            "INSERT INTO notifications (telegram_id, text, status, created_at) VALUES ($1, $2, 'pending', NOW())",
            telegram_id, text
        )
        console.log(f"[green]Notification sent to telegram_id {telegram_id}: {text}")
    except Exception as e:
        console.log(f"[red]Failed to send notification: {str(e)}")

def validate_format(text: str, field_name: str) -> list:
    if not text.strip():
        return []
    lines = text.strip().split("\n")
    result = []
    pattern = r"^\[([^\]]+)\]\s+\[(.+)\]$"
    for line in lines:
        match = re.match(pattern, line.strip())
        if not match:
            raise HTTPException(status_code=400, detail=f"Неверный формат строки в {field_name}: {line}")
        name, description = match.groups()
        result.append({"name": name, "description": description})
    return result