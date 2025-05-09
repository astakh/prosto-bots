# bots_order_prompt.py

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from ..templates_config import templates
from ..auth import get_current_user_from_token
from rich.console import Console

router = APIRouter()
console = Console()

@router.get("/order-prompt", response_class=HTMLResponse)
async def order_prompt_page(request: Request, user: dict = Depends(get_current_user_from_token)):
    try:
        console.log(f"[green]Отображение страницы order_prompt для пользователя #{user['id']}")
        return templates.TemplateResponse("order_prompt.html", {"request": request, "user": user})
    except Exception as e:
        console.log(f"[red]Ошибка в order_prompt_page: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")