import os
from dotenv import load_dotenv
from datetime import datetime
import json
from pathlib import Path
import logging

# Загрузка переменных окружения из файла .env
load_dotenv()

# Токены
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
YANDEX_DISK_TOKEN = os.getenv('YANDEX_DISK_TOKEN')

# ID администраторов
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

# Директории и файлы
DATA_DIR = Path('data')
UPLOAD_DIR = DATA_DIR / 'uploads'  # Директория для временного хранения загружаемых файлов
FOLDERS_FILE = DATA_DIR / 'allowed_folders.json'
USERS_FILE = DATA_DIR / 'allowed_users.json'

# Настройки логирования
LOG_LEVEL = getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper())

# Генерация текущего таймштампа в формате "дата_время"
def get_current_timestamp():
    """Возвращает текущий таймштамп в формате YYYYMMDD_HHMMSS"""
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")

# Функция для проверки прав администратора
def is_admin(user_id):
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

# Проверка обязательных переменных окружения
def validate_config():
    """Проверяет наличие всех необходимых переменных окружения и создает необходимые директории"""
    required_vars = ['TELEGRAM_TOKEN', 'YANDEX_DISK_TOKEN']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise ValueError(f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
    
    # Создаем директории, если они еще не существуют
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
    # Создаем файлы с разрешенными папками и пользователями, если они еще не существуют
    if not FOLDERS_FILE.exists():
        with open(FOLDERS_FILE, 'w') as f:
            json.dump([], f)
    
    if not USERS_FILE.exists():
        with open(USERS_FILE, 'w') as f:
            json.dump([], f) 