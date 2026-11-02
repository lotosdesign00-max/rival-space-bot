import sys
from pathlib import Path

# Добавляем все подпапки в пути поиска, чтобы импорты не ломались
root_dir = Path(__file__).parent
sys.path.append(str(root_dir))
for path in root_dir.glob("**/"):
    if path.is_dir() and not path.name.startswith((".", "_")):
        sys.path.append(str(path))

# Импортируем наш веб-сервер из main.py
# (Если main.py лежит в папке, например bot/, укажите: from bot.main import app)
from main import app
