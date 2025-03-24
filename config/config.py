import os
from dotenv import load_dotenv
from datetime import datetime
import json
from pathlib import Path

# Загрузка переменных окружения из файла .env
load_dotenv()

# Токены
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
YANDEX_DISK_TOKEN = os.getenv('YANDEX_DISK_TOKEN')

# ID администраторов
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

# Настройки логирования
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Настройки загрузки
UPLOAD_DIR = os.getenv('UPLOAD_DIR', 'Telegram_Bot_Uploads')

# Корневые директории на Яндекс.Диске
ROOT_DIRS = {
    "suppliers": "TD.Equipment.Suppliers",
    "clients": "TD.Equipment.Clients",
    "offers": "TD.Equipment.Offers"
}

# Файлы с информацией о разрешенных папках и пользователях
DATA_DIR = Path('data')
FOLDERS_FILE = DATA_DIR / 'allowed_folders.json'
USERS_FILE = DATA_DIR / 'allowed_users.json'

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
    
    # Создаем директорию для данных, если она еще не существует
    if not DATA_DIR.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Создаем файлы с разрешенными папками и пользователями, если они еще не существуют
    if not FOLDERS_FILE.exists():
        with open(FOLDERS_FILE, 'w') as f:
            json.dump([], f)
    
    if not USERS_FILE.exists():
        with open(USERS_FILE, 'w') as f:
            json.dump([], f) 