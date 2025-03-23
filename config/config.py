import os
from dotenv import load_dotenv
from datetime import datetime

# Загрузка переменных окружения из файла .env
load_dotenv()

# Токены
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
YANDEX_DISK_TOKEN = os.getenv('YANDEX_DISK_TOKEN')

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

# Генерация текущего таймштампа в формате "дата_время"
def get_current_timestamp():
    """Возвращает текущий таймштамп в формате YYYYMMDD_HHMMSS"""
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")

# Проверка обязательных переменных окружения
def validate_config():
    """Проверяет наличие всех необходимых переменных окружения"""
    required_vars = ['TELEGRAM_TOKEN', 'YANDEX_DISK_TOKEN']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise ValueError(f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}") 