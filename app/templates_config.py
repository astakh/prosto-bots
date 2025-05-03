import json
from fastapi.templating import Jinja2Templates
from rich.console import Console

console = Console()

# Инициализация Jinja2Templates
templates = Jinja2Templates(directory="templates")

# Определение фильтра from_json
def from_json_filter(value):
    try:
        return json.loads(value)
    except json.JSONDecodeError as e:
        console.log(f"[red]JSON Decode Error in from_json filter: {e}, value: {value}")
        return {}

# Регистрация фильтра
templates.env.filters['from_json'] = from_json_filter
console.log("[green]Registered from_json filter")