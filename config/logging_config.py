"""
Модуль с конфигурацией логирования для приложения.
Позволяет централизованно настраивать уровни логирования для различных компонентов.
"""

import logging
import os
import sys
from dotenv import load_dotenv

# Загрузка переменных окружения для доступа к переменным логирования
load_dotenv()

# Базовый уровень логирования
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Путь к файлу лога
LOG_FILE = 'bot.log'

# Уровни логирования для отдельных компонентов
# Это позволяет настраивать уровень детализации логов для разных частей приложения
COMPONENT_LOG_LEVELS = {
    'telegram': os.getenv('TELEGRAM_LOG_LEVEL', 'INFO'),
    'telegram.ext': os.getenv('TELEGRAM_EXT_LOG_LEVEL', 'INFO'),
    'httpx': os.getenv('HTTPX_LOG_LEVEL', 'WARNING'),
    'httpcore': os.getenv('HTTPCORE_LOG_LEVEL', 'WARNING'),
    'yadisk': os.getenv('YADISK_LOG_LEVEL', 'INFO'),
}

def configure_logging():
    """
    Настраивает логирование для всего приложения.
    Устанавливает уровни логирования для разных компонентов, 
    добавляет обработчики для вывода в консоль и файл.
    """
    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)
    
    # Создаем форматтер для логов
    formatter = logging.Formatter(LOG_FORMAT)
    
    # Обработчик для вывода в консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Обработчик для записи в файл
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # Добавляем обработчики к корневому логгеру
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Устанавливаем уровни логирования для отдельных компонентов
    for logger_name, level in COMPONENT_LOG_LEVELS.items():
        logging.getLogger(logger_name).setLevel(level)
    
    # Логируем информацию о начале работы
    root_logger.info("Логирование настроено")
    
    return root_logger 