# balance.py

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from ..templates_config import templates
from ..auth import get_current_user_from_token
from ..config import SERVICE_CONFIG
from rich.console import Console

router = APIRouter()
console = Console()

@router.get("/balance", response_class=HTMLResponse)
async def balance_page(request: Request, user: dict = Depends(get_current_user_from_token)):
    try:
        console.log(f"[green]Отображение страницы balance для пользователя #{user['id']}")
        return templates.TemplateResponse("balance.html", {"request": request, "user": user, "SERVICE_CONFIG": SERVICE_CONFIG})
    except Exception as e:
        console.log(f"[red]Ошибка в balance_page: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@router.get("/top-up", response_class=HTMLResponse)
async def top_up_page(request: Request, user: dict = Depends(get_current_user_from_token)):
    try:
        console.log(f"[green]Отображение страницы top_up для пользователя #{user['id']}")
        return templates.TemplateResponse("top_up.html", {"request": request, "user": user})
    except Exception as e:
        console.log(f"[red]Ошибка в top_up_page: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")