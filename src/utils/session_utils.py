"""
Модуль для управления пользовательскими сессиями.
Содержит утилиты для работы с сессиями пользователей, отслеживания активности и таймаутов.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Константы для ключей сессий
SESSION_TIMEOUT = timedelta(minutes=30)  # Время, через которое сессия считается устаревшей
SESSION_DATA = "session_data"
SESSION_UPDATED = "session_updated"
CURRENT_FOLDER = "current_folder"
CURRENT_PATH = "current_path"
FOLDER_HISTORY = "folder_history"
TEMP_MESSAGES = "temp_messages"
USER_DATA = "user_data"

def get_session_data(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> Dict[str, Any]:
    """
    Получает данные сессии пользователя, создает новую сессию, если её нет.
    
    Args:
        context: Контекст обработчика
        user_id: ID пользователя
        
    Returns:
        Словарь с данными сессии
    """
    user_data = context.user_data
    if not user_data:
        user_data = {}
        context.user_data = user_data
    
    if SESSION_DATA not in user_data:
        user_data[SESSION_DATA] = {}
    
    if SESSION_UPDATED not in user_data:
        user_data[SESSION_UPDATED] = datetime.now()
    else:
        # Обновляем время последнего доступа к сессии
        user_data[SESSION_UPDATED] = datetime.now()
    
    return user_data[SESSION_DATA]

def is_session_expired(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """
    Проверяет, не истекла ли сессия пользователя.
    
    Args:
        context: Контекст обработчика
        user_id: ID пользователя
        
    Returns:
        True, если сессия истекла, иначе False
    """
    user_data = context.user_data
    if not user_data or SESSION_UPDATED not in user_data:
        return True
    
    last_updated = user_data[SESSION_UPDATED]
    return datetime.now() - last_updated > SESSION_TIMEOUT

def reset_session(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """
    Сбрасывает сессию пользователя.
    
    Args:
        context: Контекст обработчика
        user_id: ID пользователя
    """
    user_data = context.user_data
    if user_data:
        user_data[SESSION_DATA] = {}
        user_data[SESSION_UPDATED] = datetime.now()
        logger.debug(f"Сессия для пользователя {user_id} сброшена")

def set_session_value(context: ContextTypes.DEFAULT_TYPE, user_id: int, key: str, value: Any) -> None:
    """
    Устанавливает значение в сессии пользователя.
    
    Args:
        context: Контекст обработчика
        user_id: ID пользователя
        key: Ключ для значения
        value: Значение для сохранения
    """
    session_data = get_session_data(context, user_id)
    session_data[key] = value
    logger.debug(f"Установлено значение сессии для пользователя {user_id}: {key}={value}")

def get_session_value(context: ContextTypes.DEFAULT_TYPE, user_id: int, key: str, default: Any = None) -> Any:
    """
    Получает значение из сессии пользователя.
    
    Args:
        context: Контекст обработчика
        user_id: ID пользователя
        key: Ключ для значения
        default: Значение по умолчанию, если ключ не найден
        
    Returns:
        Значение из сессии или значение по умолчанию
    """
    session_data = get_session_data(context, user_id)
    return session_data.get(key, default)

def remove_session_value(context: ContextTypes.DEFAULT_TYPE, user_id: int, key: str) -> None:
    """
    Удаляет значение из сессии пользователя.
    
    Args:
        context: Контекст обработчика
        user_id: ID пользователя
        key: Ключ для удаления
    """
    session_data = get_session_data(context, user_id)
    if key in session_data:
        del session_data[key]
        logger.debug(f"Удалено значение сессии для пользователя {user_id}: {key}")

def add_temp_message(context: ContextTypes.DEFAULT_TYPE, user_id: int, message_id: int) -> None:
    """
    Добавляет ID сообщения в список временных сообщений для последующего удаления.
    
    Args:
        context: Контекст обработчика
        user_id: ID пользователя
        message_id: ID сообщения
    """
    session_data = get_session_data(context, user_id)
    if TEMP_MESSAGES not in session_data:
        session_data[TEMP_MESSAGES] = []
    
    session_data[TEMP_MESSAGES].append(message_id)

def get_temp_messages(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> List[int]:
    """
    Получает список ID временных сообщений.
    
    Args:
        context: Контекст обработчика
        user_id: ID пользователя
        
    Returns:
        Список ID сообщений
    """
    session_data = get_session_data(context, user_id)
    return session_data.get(TEMP_MESSAGES, [])

def clear_temp_messages(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """
    Очищает список временных сообщений.
    
    Args:
        context: Контекст обработчика
        user_id: ID пользователя
    """
    session_data = get_session_data(context, user_id)
    if TEMP_MESSAGES in session_data:
        session_data[TEMP_MESSAGES] = []

async def delete_temp_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Удаляет все временные сообщения пользователя.
    
    Args:
        update: Объект обновления Telegram
        context: Контекст обработчика
    """
    if not update.effective_chat:
        return
    
    user_id = update.effective_chat.id
    chat_id = update.effective_chat.id
    
    temp_messages = get_temp_messages(context, user_id)
    if not temp_messages:
        return
    
    for message_id in temp_messages:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            logger.debug(f"Удалено временное сообщение {message_id} в чате {chat_id}")
        except Exception as e:
            logger.error(f"Ошибка при удалении сообщения {message_id} в чате {chat_id}: {e}")
    
    clear_temp_messages(context, user_id)

def set_current_folder(context: ContextTypes.DEFAULT_TYPE, user_id: int, folder_id: str, path: str) -> None:
    """
    Устанавливает текущую папку и путь для пользователя.
    
    Args:
        context: Контекст обработчика
        user_id: ID пользователя
        folder_id: ID папки
        path: Путь к папке
    """
    session_data = get_session_data(context, user_id)
    session_data[CURRENT_FOLDER] = folder_id
    session_data[CURRENT_PATH] = path
    
    # Добавляем в историю навигации
    if FOLDER_HISTORY not in session_data:
        session_data[FOLDER_HISTORY] = []
    
    session_data[FOLDER_HISTORY].append((folder_id, path))
    
    # Ограничиваем историю до 10 последних папок
    if len(session_data[FOLDER_HISTORY]) > 10:
        session_data[FOLDER_HISTORY] = session_data[FOLDER_HISTORY][-10:]

def get_current_folder(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> Optional[str]:
    """
    Получает ID текущей папки пользователя.
    
    Args:
        context: Контекст обработчика
        user_id: ID пользователя
        
    Returns:
        ID текущей папки или None
    """
    session_data = get_session_data(context, user_id)
    return session_data.get(CURRENT_FOLDER)

def get_current_path(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> str:
    """
    Получает текущий путь пользователя.
    
    Args:
        context: Контекст обработчика
        user_id: ID пользователя
        
    Returns:
        Текущий путь или пустую строку
    """
    session_data = get_session_data(context, user_id)
    return session_data.get(CURRENT_PATH, "")

def get_folder_history(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> List[tuple]:
    """
    Получает историю навигации по папкам.
    
    Args:
        context: Контекст обработчика
        user_id: ID пользователя
        
    Returns:
        Список кортежей (folder_id, path)
    """
    session_data = get_session_data(context, user_id)
    return session_data.get(FOLDER_HISTORY, []) 