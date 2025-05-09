from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.exception_handlers import http_exception_handler
from .auth import get_current_user_from_cookie, get_current_user_from_token, login_for_access_token
from .database import init_pool, close_pool, get_db_connection
from .routes.bots_index import router as bots_index_router
from .routes.bots_create import router as bots_create_router
from .routes.bots_edit import router as bots_edit_router
from .routes.bots_update import router as bots_update_router
from .routes.bots_activate import router as bots_activate_router
from .routes.bots_stop import router as bots_stop_router
from .routes.bots_delete import router as bots_delete_router
from .routes.bots_edit_items import router as bots_edit_items_router
from .routes.bots_order_prompt import router as bots_order_prompt_router
from .routes.balance import router as balance_router
from .routes import logs, test_mode
from .routes.oauth_avito import router as oauth_avito_router
from .routes.oauth_avito_callback import router as oauth_avito_callback_router
from .routes.oauth_select_items_get import router as oauth_select_items_get_router
from .routes.oauth_select_items_post import router as oauth_select_items_post_router
from .routes.avito_webhook import router as avito_webhook_router
from .config import COOKIE_NAME, SERVICE_CONFIG, TELEGRAM_BOT_NAME
from .utils import send_notification
import asyncio
import datetime as dt
from rich.console import Console
from .templates_config import templates

console = Console()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        console.log(f"[yellow]Unauthorized access, redirecting to login")
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
    return await http_exception_handler(request, exc)

@app.on_event("startup")
async def startup_event():
    await init_pool()
    console.log("[green]Database pool initialized")
    asyncio.create_task(charge_balance())

@app.on_event("shutdown")
async def shutdown_event():
    await close_pool()

async def charge_balance():
    from .database import _pool
    while True:
        async with _pool.acquire() as conn:
            users = await conn.fetch("SELECT * FROM users")
            for user in users:
                bots = await conn.fetch("SELECT * FROM bots WHERE user_id = $1 AND status = 'active'", user["id"])
                if not bots:
                    continue
                trial_active = user["trial_end_date"] > dt.datetime.utcnow()
                total_cost = len(bots) * SERVICE_CONFIG["bot_daily_cost"]
                
                if trial_active and len(bots) == 1:
                    continue
                
                if user["balance"] < total_cost:
                    for bot in bots:
                        await conn.execute("UPDATE bots SET status = 'stopped' WHERE id = $1", bot["id"])
                        await send_notification(user["telegram_id"], f"Баланс недостаточен для бота #{bot['id']}. Пополните баланс.", conn)
                else:
                    await conn.execute("UPDATE users SET balance = balance - $1 WHERE id = $2", total_cost, user["id"])
        
        await asyncio.sleep(86400)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, conn=Depends(get_db_connection)):
    user = await get_current_user_from_cookie(request, conn)
    return templates.TemplateResponse("index.html", {"request": request, "user": user, "config": {"TELEGRAM_BOT_NAME": TELEGRAM_BOT_NAME}})

@app.get("/auth/login", response_class=HTMLResponse)
async def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "errors": []})

@app.post("/auth/login", response_class=HTMLResponse)
async def login_post(request: Request, conn=Depends(get_db_connection)):
    form = await request.form()
    username = form.get("username")
    password = form.get("password")
    errors = []
    if not username:
        errors.append("Введите логин")
    if not password:
        errors.append("Введите пароль")
    if not errors:
        try:
            response = RedirectResponse("/", status_code=status.HTTP_302_FOUND)
            await login_for_access_token(response=response, username=username, password=password, conn=conn)
            console.log("[green]Login successful")
            return response
        except HTTPException:
            errors.append("Неверный логин или пароль")
    return templates.TemplateResponse("login.html", {"request": request, "errors": errors})

@app.get("/auth/logout", response_class=HTMLResponse)
async def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie(COOKIE_NAME)
    return response

app.include_router(bots_index_router, prefix="/bots")
app.include_router(bots_create_router, prefix="/bots")
app.include_router(bots_edit_router, prefix="/bots")
app.include_router(bots_update_router, prefix="/bots")
app.include_router(bots_activate_router, prefix="/bots")
app.include_router(bots_stop_router, prefix="/bots")
app.include_router(bots_delete_router, prefix="/bots")
app.include_router(bots_edit_items_router, prefix="/bots")
app.include_router(bots_order_prompt_router, prefix="/bots")
app.include_router(balance_router)
app.include_router(logs.router, prefix="/logs")
app.include_router(oauth_avito_router, prefix="/oauth")
app.include_router(oauth_avito_callback_router, prefix="/oauth")
app.include_router(oauth_select_items_get_router, prefix="/oauth")
app.include_router(oauth_select_items_post_router, prefix="/oauth")
app.include_router(test_mode.router, prefix="/test")
app.include_router(avito_webhook_router, prefix="/avito")